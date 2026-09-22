"""Parst /details/education/: Name, Fachrichtung, Zeitraum.

Stand 2026-09 (SDUI v2): Die Sektion kommt als LazyColumn und
wird client-seitig geladen - im reinen HTTP-Abruf steht sie nicht drin, es braucht den
Browser-Fetcher. Die Einträge sind `<div>`-Blöcke, durch `<hr>` getrennt; das alte
`entity-collection-item-`-Markup gibt es nicht mehr.

Verifiziert gegen einen Browser-Dump (2026-09-10): pro Eintrag die Textzeilen
  [0] Schule
  [1] Abschluss / Fachrichtung
  [.] Zeitraum (die Zeile, die eine Jahreszahl enthält)
Zeilen wie „Kenntnisse: …" oder „Note: 1,9" werden ignoriert.
"""
import logging

from ..models import Education
from ..config import NOT_AVAILABLE
from .dom_utils import (
    iter_sdui_entries, iter_detail_entries, looks_like_period, SDUI_EDUCATION,
)

logger = logging.getLogger("linkedin_scraper")

_LEGACY_PREFIX = "profile_EducationDetailsSection_"


def parse_education_page(html: str) -> list[Education]:
    entries = iter_sdui_entries(html, SDUI_EDUCATION) or iter_detail_entries(html, _LEGACY_PREFIX)
    if not entries:
        logger.warning("Keine Ausbildungs-Einträge im HTML")
        return []

    educations: list[Education] = []
    for lines in entries:
        name = lines[0] if lines else NOT_AVAILABLE
        fach = lines[1] if len(lines) > 1 and not looks_like_period(lines[1]) else NOT_AVAILABLE
        zeitraum = next((ln for ln in lines[1:] if looks_like_period(ln)), NOT_AVAILABLE)
        educations.append(Education(name=name, fachrichtung=fach, zeitraum=zeitraum))
    return educations
