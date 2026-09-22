"""Parst overlay/contact-info/: E-Mail, Geburtstag.

Stand 2026 (SDUI): Die Kontaktdaten stehen nicht mehr als
Voyager-JSON, sondern nur noch im React-Flight-Payload der Seite, u. a. als
`"url":"mailto:<adresse>"` bzw. `"children":["<adresse>"]`. Wir ziehen die E-Mail
daher per Regex direkt aus dem Rohtext.

Der Geburtstag steht im gerenderten Overlay als zwei aufeinanderfolgende `<p>`:
`<p>Geburtstag</p><p>10. Mai</p>` (Tag + Monatsname, i. d. R. ohne Jahr). Deshalb wird
er primär strukturell über das Label-`<p>` und dessen Nachbar-`<p>` gelesen; die
`birthDateOn`-JSON- und die lose Textregex bleiben als Rückfall.
"""
import logging
import re

from ..config import NOT_AVAILABLE
from .dom_utils import get_soup

logger = logging.getLogger("linkedin_scraper")

_MAILTO = re.compile(r'mailto:([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})')
# "birthDateOn":{"month":9,"day":24}  bzw.  \"month\":9,\"day\":24 im escapten Flight-Payload
_BIRTH_JSON = re.compile(r'birthDateOn\\?"\s*:\s*\{[^}]*?month\\?"\s*:\s*(\d{1,2})[^}]*?day\\?"\s*:\s*(\d{1,2})')
# Sichtbarer Text im deutschen UI: "Geburtstag" gefolgt von "24. September" o. Ä.
_BIRTH_TEXT = re.compile(r'Geburtstag[^0-9]{0,200}?(\d{1,2})\.?\s*([A-Za-zÄÖÜäöü]+)')
# Wert-Zeile: "10. Mai" bzw. "10. Mai 1998".
_BIRTH_VALUE = re.compile(r'(\d{1,2})\.?\s+([A-Za-zÄÖÜäöü]+)(?:\s+(\d{4}))?')
_BIRTH_LABELS = ("geburtstag", "geburtsdatum", "birthday")

_MONTHS_DE = {
    "januar": 1, "februar": 2, "märz": 3, "april": 4, "mai": 5, "juni": 6,
    "juli": 7, "august": 8, "september": 9, "oktober": 10, "november": 11, "dezember": 12,
}


def parse_contact_info(html: str) -> dict:
    result = {"email": NOT_AVAILABLE, "geburtstag": NOT_AVAILABLE}

    mails = _MAILTO.findall(html)
    if mails:
        result["email"] = mails[0]
    else:
        logger.warning("Keine E-Mail im Kontakt-Overlay gefunden - evtl. nicht freigegeben oder Markup geändert")

    result["geburtstag"] = _extract_birthday(html)
    return result


def _format_birthday(day: int, month: int, year: str | None) -> str:
    return f"{day:02d}.{month:02d}.{year}" if year else f"{day:02d}.{month:02d}."


def _birth_from_value(text: str) -> str | None:
    m = _BIRTH_VALUE.search(text or "")
    if not m:
        return None
    month = _MONTHS_DE.get(m.group(2).lower())
    if not month:
        return None
    return _format_birthday(int(m.group(1)), month, m.group(3))


def _extract_birthday(html: str) -> str:
    # 1. Struktur: <p>Geburtstag</p><p>10. Mai</p>
    soup = get_soup(html)
    for label in soup.find_all("p"):
        if label.get_text(strip=True).rstrip(":").strip().lower() in _BIRTH_LABELS:
            sib = label.find_next_sibling("p")
            if sib is not None:
                val = _birth_from_value(sib.get_text(" ", strip=True))
                if val:
                    return val

    # 2. Escapeter Flight-Payload: "birthDateOn":{"month":5,"day":10}
    m = _BIRTH_JSON.search(html)
    if m:
        return _format_birthday(int(m.group(2)), int(m.group(1)), None)

    # 3. Loser Textfallback über den Rohtext
    m = _BIRTH_TEXT.search(html)
    if m:
        val = _birth_from_value(f"{m.group(1)}. {m.group(2)}")
        if val:
            return val

    return NOT_AVAILABLE
