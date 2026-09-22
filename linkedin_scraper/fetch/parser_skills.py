"""Parst /details/skills/: einfache Liste der Kenntnisse (nur Name).

Stand 2026-09 (SDUI v2): LazyColumn, client-seitig geladen
(Browser-Fetcher nötig). Die Sektion hat kein eigenes `data-testid` mehr; jede Kenntnis
ist ein Block aus Namenszeile + Kontextzeile(n) + „Kenntnisse bestätigen"-Button. Der
Name ist die erste Zeile jedes Blocks.

Verifiziert gegen einen Browser-Dump (2026-09-10).
"""
import logging

from .dom_utils import iter_sdui_entries, iter_detail_entries, SDUI_SKILLS

logger = logging.getLogger("linkedin_scraper")

_LEGACY_PREFIX = "profile_SkillDetails"


def parse_skills_page(html: str) -> list[str]:
    entries = iter_sdui_entries(html, SDUI_SKILLS) or iter_detail_entries(html, _LEGACY_PREFIX)
    if not entries:
        logger.warning("Keine Kenntnis-Einträge im HTML")
        return []

    namen: list[str] = []
    for lines in entries:
        if lines and lines[0] not in namen:
            namen.append(lines[0])
    return namen
