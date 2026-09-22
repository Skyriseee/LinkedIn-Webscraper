"""Baut aus den per Transport empfangenen Cookies einen HTTP-Client für den Scraper."""
import logging

from .transport_base import SessionTransport
from .validator import is_session_valid
from ..config import REQUIRED_COOKIES, SESSION_TRANSPORT_TIMEOUT_SECONDS
from ..fetch.http_client import HttpClient

logger = logging.getLogger("linkedin_scraper")


class SessionError(Exception):
    pass


def build_session(cookies: dict, quelle: str) -> HttpClient:
    """Baut aus einem Cookie-Satz einen validierten HttpClient.

    `quelle` dient nur der Protokollierung - sie sagt, ob die Cookies aus dem
    Tool-Browserprofil oder aus der Browser-Extension stammen.
    """
    missing = [c for c in REQUIRED_COOKIES if c not in cookies]
    if missing:
        raise SessionError(
            f"Fehlende Pflicht-Cookies: {missing} (Quelle: {quelle}). "
            f"Bist du bei LinkedIn eingeloggt?"
        )

    client = HttpClient(cookies)

    if not is_session_valid(client):
        raise SessionError(
            f"Session-Cookies übernommen (Quelle: {quelle}), aber der Login-Check ist "
            f"fehlgeschlagen - die Session ist vermutlich abgelaufen."
        )

    logger.info("Session geladen und validiert: %d Cookies aus %s.", len(cookies), quelle)
    return client


def load_session(transport: SessionTransport) -> HttpClient:
    data = transport.receive_session_data(timeout=SESSION_TRANSPORT_TIMEOUT_SECONDS)
    return build_session(data.get("cookies", {}), "Browser-Extension")
