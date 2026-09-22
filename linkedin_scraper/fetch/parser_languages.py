"""Parst /details/languages/: Sprache, Sprachniveau.

Stand 2026-09 (SDUI v2): LazyColumn, client-seitig geladen
(Browser-Fetcher nötig). Einträge sind `<hr>`-getrennte `<div>`-Blöcke mit
  [0] Sprache
  [1] Niveau (z. B. „Verhandlungssicher")

Verifiziert gegen einen Browser-Dump (2026-09-10): Deutsch / Englisch / Französisch.
"""
import logging

from ..models import Language
from ..config import NOT_AVAILABLE
from .dom_utils import iter_sdui_entries, iter_detail_entries, SDUI_LANGUAGES

logger = logging.getLogger("linkedin_scraper")

_LEGACY_PREFIX = "profile_LanguageDetails"


def parse_languages_page(html: str) -> list[Language]:
    entries = iter_sdui_entries(html, SDUI_LANGUAGES) or iter_detail_entries(html, _LEGACY_PREFIX)
    if not entries:
        logger.warning("Keine Sprach-Einträge im HTML")
        return []

    languages: list[Language] = []
    for lines in entries:
        languages.append(Language(
            sprache=lines[0] if lines else NOT_AVAILABLE,
            niveau=lines[1] if len(lines) > 1 else NOT_AVAILABLE,
        ))
    return languages
