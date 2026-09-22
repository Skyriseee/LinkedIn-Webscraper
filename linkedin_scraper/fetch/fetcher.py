"""HTTP-GET mit menschenähnlichem Delay sowie Retry/Backoff bei 429/403/5xx."""
from __future__ import annotations
import logging
import time

from bs4 import BeautifulSoup

from ..config import MAX_RETRIES, RETRY_BACKOFF_BASE, REQUEST_TIMEOUT_SECONDS
from ..rate_limiter import RateLimiter

logger = logging.getLogger("linkedin_scraper")


class FetchError(Exception):
    pass


class ProfileNotFoundError(FetchError):
    """LinkedIn hat auf die 404-Seite umgeleitet - das Profil existiert unter dieser
    URL nicht (mehr), im Unterschied zu einem Profil, das existiert, aber Felder aus
    Privatsphäre-Gründen nicht zeigt (dort bleibt es bei FetchError/NOT_AVAILABLE).
    Eine Unterklasse von FetchError, damit ein `except FetchError` anderswo weiterhin
    greift; main.py:scrape_profile fängt gezielt diese speziellere Klasse zuerst ab."""
    pass


# LinkedIn zeigt bei einem Zugriff auf ein nicht (mehr) existierendes Profil nicht
# immer die saubere /404/-Umleitung - manchmal stürzt die React-App stattdessen in
# ihre generische Fehlerseite ("Leider ist ein Fehler aufgetreten" / "Seite
# aktualisieren"), vermutlich weil sie versucht, Daten für eine ungültige Profil-URL
# zu laden. Ohne diese Prüfung landet dieser Text unbemerkt als scheinbar echter
# Ausbildungs-/Kenntnis-/Sprachen-Eintrag im Ergebnis (Autor-Fund 2026-09-14 am neu
# gescrapten ~59-Profile-Korpus: betraf exakt die beiden bereits bekannten,
# bestätigt gelöschten Profile, 0 von 57 echten Profilen).
#
# WICHTIG (Autor-Fund 2026-09-14, Nachtrag): derselbe Text ist KEIN verlässliches
# 404-Signal auf Detailseiten ("/details/...") - ein inhaltsreiches, echt
# existierendes Profil kann dort ebenfalls landen (david-haslacher, 48 echte
# Kenntnisse, /details/skills/ zeigte denselben Fehlertext, obwohl das Profil
# unstrittig existiert und im normalen Browser normal lädt). Vermutlich ein
# Rendering-Absturz bei umfangreichem Inhalt, nicht spezifisch für gelöschte
# Profile. Nur auf der Kontakt-/Profilseite bleibt es das verlässliche 404-Signal -
# dort traten beide bislang bestätigten Fälle auf, beide ohne nennenswerten
# Seiteninhalt. `get_html()` prüft deshalb `"/details/" in url`, bevor es diesen
# Fund als `ProfileNotFoundError` statt als normalen `FetchError` wertet.
ERROR_BOUNDARY_MARKER = "Leider ist ein Fehler aufgetreten"


def _error_boundary_in_body(html: str) -> bool:
    """Prüft, ob ERROR_BOUNDARY_MARKER als tatsächlich gerenderter Inhalt im
    <body> steht - NICHT nur als LinkedIns statisches
    `<meta name="como-err" content="{&quot;title&quot;:&quot;Leider ist ein Fehler
    aufgetreten.&quot;,...}">`-Tag im <head>.

    ROOT CAUSE gefunden am 2026-09-14 (Autor-Fund): dieses
    Meta-Tag steht im <head> JEDER LinkedIn-Seite, unabhängig davon, ob tatsächlich
    ein Fehler vorliegt - bestätigt an einem frischen, per `_save_error_boundary_
    dump()` (v0.7.26) gesicherten Dump von martin-reimann-26902a26b/details/
    experience/ (zweifelsfrei korrekt geladen: enthält die echten, bereits mehrfach
    verifizierten Erfahrungsdaten) UND an vier weiteren historischen, zweifelsfrei
    korrekten Dumps (Zertifikate/Sprachen Martin Reimann, Profil kreuter92,
    Kenntnisse alisia-deichhardt) - alle fünf enthalten denselben Meta-Tag. Die
    bisherige rohe Substring-Suche über die komplette HTML (bis v0.7.26,
    `ERROR_BOUNDARY_MARKER in text`/`in page.content()`) matchte deshalb auf JEDER
    Seite, unabhängig vom tatsächlichen Zustand - das war die eigentliche Ursache
    ALLER "Fehlerseite"/"404"-Funde seit Einführung des Markers (v0.7.19), nicht
    Delays, Drosselung oder Rendering-Last bei umfangreichem Inhalt (siehe die
    inzwischen überholten Vermutungen in den Kommentaren oben und in v0.7.20-25).

    Beschränkt die Suche stattdessen auf `soup.body` (BeautifulSoup, wie
    dom_utils.get_soup) - ein Meta-Tag im <head> fällt damit raus, ein tatsächlich
    im Seiteninhalt gerenderter Fehlertext (der ursprüngliche v0.7.19-Verdachtsfall)
    würde weiterhin erkannt."""
    soup = BeautifulSoup(html, "html.parser")
    body = soup.body
    text = body.get_text() if body is not None else html
    return ERROR_BOUNDARY_MARKER in text


class Fetcher:
    """Holt HTML über einen HttpClient (curl_cffi/requests). `get_html(url, referer=...)`."""

    def __init__(self, client, rate_limiter: RateLimiter | None = None):
        self.client = client
        self.rate_limiter = rate_limiter or RateLimiter()

    def get_html(self, url: str, referer: str | None = None) -> str:
        last_exc: Exception | None = None
        for attempt in range(1, MAX_RETRIES + 1):
            self.rate_limiter.wait()
            try:
                response = self.client.get(
                    url, timeout=REQUEST_TIMEOUT_SECONDS, referer=referer
                )
            except Exception as exc:  # curl_cffi / requests werfen unterschiedliche Typen
                last_exc = exc
                logger.warning("Request-Fehler (Versuch %d/%d) für %s: %s", attempt, MAX_RETRIES, url, exc)
                continue

            if response.status_code == 200:
                final_url = str(getattr(response, "url", "") or "")
                if "/404" in final_url:
                    raise ProfileNotFoundError(
                        f"{url} existiert nicht (mehr) - umgeleitet auf {final_url}."
                    )
                if any(m in final_url for m in ("/login", "/authwall", "/checkpoint")):
                    raise FetchError(
                        f"Auf {final_url} umgeleitet für {url} - Session ungültig oder "
                        f"Bot-Check ausgelöst."
                    )
                # Manche Antworten kommen ohne Charset im Content-Type; LinkedIn ist UTF-8.
                try:
                    response.encoding = "utf-8"
                    text = response.text
                except Exception:
                    text = response.content.decode("utf-8", errors="replace")
                if _error_boundary_in_body(text):
                    if "/details/" in url:
                        raise FetchError(
                            f"{url} zeigt LinkedIns generische Fehlerseite - "
                            f"vermutlich ein Rendering-Problem bei umfangreichem "
                            f"Inhalt, kein Hinweis auf ein gelöschtes Profil (siehe "
                            f"ERROR_BOUNDARY_MARKER-Kommentar oben)."
                        )
                    raise ProfileNotFoundError(
                        f"{url} zeigt LinkedIns generische Fehlerseite statt echtem "
                        f"Inhalt (\"{ERROR_BOUNDARY_MARKER}\") - bisher nur bei "
                        f"gelöschten Profilen beobachtet."
                    )
                return text

            # 403/429 = Rate-Limit/Bot-Check, 5xx = (meist vorübergehender) Serverfehler
            # bei LinkedIn selbst - beides mit Backoff erneut versuchen (NFA1). Alles
            # andere (z.B. 404) ist kein Fall, den ein Retry lösen würde.
            if response.status_code in (403, 429) or 500 <= response.status_code < 600:
                backoff = RETRY_BACKOFF_BASE * (2 ** (attempt - 1))
                grund = ("evtl. Rate-Limit/Bot-Check" if response.status_code in (403, 429)
                         else "serverseitiger Fehler bei LinkedIn")
                logger.warning(
                    "Status %d für %s - %s. Warte %.0fs (Versuch %d/%d)",
                    response.status_code, url, grund, backoff, attempt, MAX_RETRIES,
                )
                time.sleep(backoff)
                continue

            raise FetchError(f"Unerwarteter Status {response.status_code} für {url}")

        raise FetchError(f"Abruf fehlgeschlagen nach {MAX_RETRIES} Versuchen: {url} ({last_exc})")
