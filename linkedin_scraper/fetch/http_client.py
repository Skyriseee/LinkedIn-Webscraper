"""HTTP-Client für die requests-basierten Abrufe - so nah wie möglich an einem echten Chrome.

Warum: LinkedIn erkennt einen nackten `requests`-Aufruf an drei Stellen sofort -
(1) TLS-/HTTP-2-Fingerprint (JA3), (2) unvollständiger, falsch sortierter Header-Satz,
(3) fehlende Sec-Fetch-/Referer-Kette. `HttpClient` adressiert (1) über `curl_cffi`
(Chrome-Impersonation) und (2)/(3) über einen vollständigen Header-Satz plus
`get(..., referer=...)`, das `Referer` und `Sec-Fetch-Site` je Navigation korrekt setzt.

Ohne installiertes `curl_cffi` fällt der Client auf `requests` zurück (schwächerer
Fingerprint) und protokolliert das.

Die öffentliche Fläche (`headers`, `cookies`, `get`) ist mit `requests.Session`
kompatibel, damit `session/validator.py` und `fetch/fetcher.py` unverändert damit
arbeiten.
"""
from __future__ import annotations

import logging

import requests as _plain_requests

from ..fingerprint import identity as _device_identity
from ..config import (
    FORCE_HTTP_ENGINE,
    HTTP_IDENTITY_AUTO,
    HTTP_IMPERSONATE,
    USER_AGENT,
    SEC_CH_UA,
    SEC_CH_UA_PLATFORM,
    ACCEPT_LANGUAGE,
    LI_CLIENT_VERSION,
    LI_LANG,
    LI_TIMEZONE,
)

logger = logging.getLogger("linkedin_scraper")

try:  # curl_cffi ist optional, aber dringend empfohlen
    from curl_cffi import requests as _curl_requests
    _HAVE_CURL = True
except ImportError:  # pragma: no cover - abhängig von der Umgebung
    _curl_requests = None
    _HAVE_CURL = False


def _fallback_accept_encoding() -> str:
    """Nur das ankündigen, was der requests-Pfad auch dekodieren kann.

    curl_cffi bringt Brotli/zstd mit; plain `requests` nicht. Ohne installiertes
    `brotli`/`brotlicffi` bzw. `zstandard` liefert der Server sonst einen Body,
    den urllib3 nicht auspackt - `.text` ist dann komprimierter Datenmüll
    (genau das Symptom bei den erzwungenen requests-Dumps).
    """
    codings = ["gzip", "deflate"]
    for mod in ("brotli", "brotlicffi"):
        try:
            __import__(mod)
            codings.append("br")
            break
        except ImportError:
            pass
    try:
        __import__("zstandard")
        codings.append("zstd")
    except ImportError:
        pass
    return ", ".join(codings)


_ACCEPT_HTML = (
    "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,"
    "image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"
)

# Header, die ein Chrome bei einer Top-Level-Navigation immer mitschickt.
_NAV_HEADERS = {
    "Accept": _ACCEPT_HTML,
    "Accept-Language": ACCEPT_LANGUAGE,
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Priority": "u=0, i",
}

def _identity() -> dict:
    """Die zu verwendende Geräte-Identität - abgeleitet oder fest aus der config."""
    if HTTP_IDENTITY_AUTO:
        return _device_identity()
    return {
        "user_agent": USER_AGENT, "sec_ch_ua": SEC_CH_UA,
        "sec_ch_ua_platform": SEC_CH_UA_PLATFORM, "impersonate": HTTP_IMPERSONATE,
        "detected": False,
    }


def _identity_headers() -> dict:
    """User-Agent + Client-Hints. Werden BEWUSST auch im curl_cffi-Pfad gesetzt:

    curl_cffi liefert für alle Chrome-Ziele eine macOS-UA. Da der Browser-Weg im selben
    Lauf mit demselben Session-Cookie als Windows-Chrome auftritt, wäre das ein
    Gerätewechsel mitten in der Sitzung. Der TLS-/HTTP-2-
    Fingerprint der Impersonation bleibt davon unberührt - der kodiert kein
    Betriebssystem.
    """
    ident = _identity()
    return {
        "User-Agent": ident["user_agent"],
        "sec-ch-ua": ident["sec_ch_ua"],
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": ident["sec_ch_ua_platform"],
    }


_FALLBACK_ONLY_HEADERS = {
    "Accept-Encoding": _fallback_accept_encoding(),
}

_COOKIE_DOMAIN = ".linkedin.com"

# Header, die die LinkedIn-Web-App bei einem internen /voyager/api-XHR mitschickt.
# `csrf-token` (= JSESSIONID ohne Anführungszeichen) wird pro Instanz ergänzt.
_VOYAGER_ACCEPT = "application/vnd.linkedin.normalized+json+2.1"


def _li_track_header() -> str:
    import json
    return json.dumps({
        "clientVersion": LI_CLIENT_VERSION,
        "mpVersion": LI_CLIENT_VERSION,
        "osName": "web",
        "timezoneOffset": 2,
        "timezone": LI_TIMEZONE,
        "deviceFormFactor": "DESKTOP",
        "mpName": "voyager-web",
        "displayDensity": 1,
        "displayWidth": 1920,
        "displayHeight": 1080,
    }, separators=(",", ":"))


class HttpClient:
    """Dünner Wrapper um curl_cffi bzw. requests mit realistischem Header-/Referer-Verhalten."""

    def __init__(self, cookies: dict[str, str]):
        use_curl = _HAVE_CURL and FORCE_HTTP_ENGINE != "requests"
        if FORCE_HTTP_ENGINE == "curl_cffi" and not _HAVE_CURL:
            raise RuntimeError("FORCE_HTTP_ENGINE='curl_cffi', aber das Paket fehlt.")

        ident = _identity()
        ident_headers = _identity_headers()

        if use_curl:
            self._session = _curl_requests.Session(impersonate=ident["impersonate"])
            self.engine = f"curl_cffi (impersonate={ident['impersonate']})"
            # Identitäts-Header auch hier setzen, damit HTTP-Weg und Browser-Weg
            # dasselbe Gerät melden (siehe _identity_headers).
            self._session.headers.update({**_NAV_HEADERS, **ident_headers})
        else:
            self._session = _plain_requests.Session()
            why = "erzwungen (FORCE_HTTP_ENGINE)" if FORCE_HTTP_ENGINE == "requests" else "Fallback"
            self.engine = f"requests ({why} - kein Chrome-TLS-Fingerprint)"
            self._session.headers.update({**_NAV_HEADERS, **ident_headers, **_FALLBACK_ONLY_HEADERS})
            if FORCE_HTTP_ENGINE != "requests":
                logger.warning(
                    "curl_cffi ist nicht installiert - Fallback auf requests. Für einen "
                    "echten Chrome-TLS-Fingerprint bitte `pip install curl_cffi` ausführen."
                )

        for name, value in cookies.items():
            try:
                self._session.cookies.set(name, value, domain=_COOKIE_DOMAIN)
            except Exception:  # pragma: no cover - je nach Cookie-Jar-Implementierung
                self._session.cookies.set(name, value)

        # csrf-token für /voyager/api-Calls: LinkedIn erwartet exakt den JSESSIONID-
        # Cookiewert ohne die umschließenden Anführungszeichen ("ajax:123..." -> ajax:123...).
        self.csrf_token = cookies.get("JSESSIONID", "").strip('"')

        logger.info("HTTP-Client: %s, %d Cookies übernommen.", self.engine, len(cookies))
        logger.info("HTTP-Identität: %s", ident_headers["User-Agent"])

    # -- requests.Session-kompatible Fläche --------------------------------

    @property
    def headers(self):
        return self._session.headers

    @property
    def cookies(self):
        return self._session.cookies

    def get(
        self,
        url: str,
        *,
        timeout: float,
        allow_redirects: bool = True,
        referer: str | None = None,
        same_site: bool = True,
    ):
        """GET mit passender Sec-Fetch-/Referer-Kette.

        `referer=None`   -> Einstieg (wie Adressleiste): Sec-Fetch-Site: none
        `referer=<url>`  -> Klick von dort: same-origin (bzw. same-site)
        """
        headers = {}
        if referer:
            headers["Referer"] = referer
            headers["Sec-Fetch-Site"] = "same-origin" if same_site else "same-site"
        else:
            headers["Sec-Fetch-Site"] = "none"
        return self._session.get(
            url, timeout=timeout, allow_redirects=allow_redirects, headers=headers
        )

    def get_api(
        self,
        url: str,
        *,
        timeout: float,
        referer: str,
        params: dict | None = None,
    ):
        """GET auf einen internen /voyager/api-Endpunkt (XHR-Semantik, JSON-Antwort).

        Setzt den Header-Satz, den die LinkedIn-Web-App bei so einem Call mitschickt:
        `csrf-token`, `x-restli-protocol-version`, `x-li-lang`, `x-li-track`,
        `accept: …normalized+json…` sowie `Sec-Fetch-*` für einen same-origin-XHR.
        `referer` sollte die Profilseite sein, von der aus der Call „ausgelöst" wird.
        """
        if not self.csrf_token:
            raise RuntimeError(
                "Kein csrf-token verfügbar - das JSESSIONID-Cookie fehlt in der Session. "
                "Ist die Extension aktuell (überträgt alle .linkedin.com-Cookies)?"
            )
        headers = {
            "Accept": _VOYAGER_ACCEPT,
            "csrf-token": self.csrf_token,
            "x-restli-protocol-version": "2.0.0",
            "x-li-lang": LI_LANG,
            "x-li-track": _li_track_header(),
            "x-li-page-instance": "urn:li:page:d_flagship3_profile_view_base;" + "0" * 22,
            "Referer": referer,
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
        }
        return self._session.get(url, timeout=timeout, headers=headers, params=params)

    def close(self) -> None:
        try:
            self._session.close()
        except Exception:  # pragma: no cover
            pass
