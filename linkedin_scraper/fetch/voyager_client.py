"""Zugriff auf LinkedIns interne Voyager-REST-API für die client-seitig nachgeladenen
Felder (E-Mail, Geburtstag, Ausbildung, Kenntnisse, Sprachen, Zertifikate).

Warum REST und nicht GraphQL: Die GraphQL-Endpunkte brauchen eine `queryId`, die sich
mit jedem Web-Release von LinkedIn ändert - das wäre im Code hart verdrahtet und würde
regelmäßig brechen. Die klassischen REST-Endpunkte (`profileView`, `profileContactInfo`)
sind seit Jahren stabil, brauchen keinen queryId und liefern alle sechs Felder in zwei
Aufrufen. Der Zugriff läuft über dieselbe warme Session wie der HTML-Weg (curl_cffi),
nur mit XHR-Headern (siehe `HttpClient.get_api`).

Falls LinkedIn diese Endpunkte einmal abschaltet, meldet `get_json` das sauber als
`VoyagerError` - dann bleibt der Browser-Fetcher (`USE_BROWSER_FOR_LAZY`) als Weg.
"""
from __future__ import annotations

import json
import logging
import time

from ..config import (
    MAX_RETRIES,
    RETRY_BACKOFF_BASE,
    REQUEST_TIMEOUT_SECONDS,
    VOYAGER_PROFILE_VIEW,
    VOYAGER_CONTACT_INFO,
    URL_PROFILE,
)
from ..rate_limiter import RateLimiter

logger = logging.getLogger("linkedin_scraper")


class VoyagerError(Exception):
    pass


class VoyagerClient:
    """Dünner Wrapper um `HttpClient.get_api` mit Delay und Retry/Backoff."""

    def __init__(self, client, rate_limiter: RateLimiter | None = None):
        self.client = client
        self.rate_limiter = rate_limiter or RateLimiter()

    def get_json(self, url: str, *, referer: str) -> dict:
        last_exc: Exception | None = None
        for attempt in range(1, MAX_RETRIES + 1):
            self.rate_limiter.wait()
            try:
                response = self.client.get_api(
                    url, timeout=REQUEST_TIMEOUT_SECONDS, referer=referer
                )
            except Exception as exc:  # curl_cffi / requests werfen unterschiedliche Typen
                last_exc = exc
                logger.warning("Voyager-Request-Fehler (Versuch %d/%d) für %s: %s",
                               attempt, MAX_RETRIES, url, exc)
                continue

            status = response.status_code
            if status == 200:
                try:
                    return json.loads(response.text)
                except ValueError as exc:
                    raise VoyagerError(f"Antwort von {url} ist kein JSON: {exc}") from exc

            if status in (403, 429):
                backoff = RETRY_BACKOFF_BASE * (2 ** (attempt - 1))
                logger.warning("Voyager-Status %d für %s - warte %.0fs (Versuch %d/%d)",
                               status, url, backoff, attempt, MAX_RETRIES)
                time.sleep(backoff)
                continue

            if status == 404:
                raise VoyagerError(f"Profil/Endpunkt nicht gefunden (404): {url}")

            raise VoyagerError(f"Unerwarteter Voyager-Status {status} für {url}")

        raise VoyagerError(f"Voyager-Abruf fehlgeschlagen nach {MAX_RETRIES} Versuchen: "
                           f"{url} ({last_exc})")

    # -- konkrete Endpunkte ----------------------------------------------------

    def profile_view(self, public_id: str) -> dict:
        return self.get_json(
            VOYAGER_PROFILE_VIEW.format(pid=public_id),
            referer=URL_PROFILE.format(slug=public_id),
        )

    def contact_info(self, public_id: str) -> dict:
        return self.get_json(
            VOYAGER_CONTACT_INFO.format(pid=public_id),
            referer=URL_PROFILE.format(slug=public_id),
        )
