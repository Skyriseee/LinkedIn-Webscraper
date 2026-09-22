"""Prüft, ob der HTTP-Client bei LinkedIn eingeloggt ist."""
import logging

from ..config import URL_SESSION_CHECK, REQUEST_TIMEOUT_SECONDS

logger = logging.getLogger("linkedin_scraper")


def is_session_valid(client) -> bool:
    """`client` ist ein fetch.http_client.HttpClient (oder etwas requests.Session-kompatibles)."""
    try:
        response = client.get(
            URL_SESSION_CHECK, timeout=REQUEST_TIMEOUT_SECONDS, allow_redirects=False
        )
    except Exception as exc:  # curl_cffi / requests werfen unterschiedliche Typen
        logger.error("Session-Check fehlgeschlagen: %s", exc)
        return False

    # Nicht eingeloggt -> Redirect auf /login, /authwall oder /checkpoint. Ein anderes
    if response.status_code in (301, 302, 303, 307, 308):
        location = response.headers.get("Location", "")
        if any(marker in location for marker in ("login", "authwall", "checkpoint")):
            return False
        return True
    return response.status_code == 200
