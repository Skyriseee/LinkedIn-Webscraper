"""Parst /details/certifications/: Name, Aussteller, Ausstelldatum.

Stand 2026-09 (SDUI v2): LazyColumn, client-seitig geladen
(Browser-Fetcher nötig). Zeilen je Eintrag:
  [0] Name des Zertifikats
  [1] Aussteller
  [.] „Ausgestellt: <Datum> · Gültig bis: <Datum>" - wir nehmen nur das Ausstelldatum

Ab zwei Einträgen sind sie `<hr>`-getrennt (wie Ausbildung); bei genau einem Eintrag
gibt es keinen Trenner, dann greift `dom_utils._single_entry`. Der unter jedem
Zertifikat als „Kenntnisse:" angehängte verknüpfte Skill wird dort abgeschnitten.
Leerer Zustand → `[]` („Noch keine Informationen verfügbar").

Verifiziert 2026-09-10 (v0.7.2) gegen ein Testprofil mit einem Zertifikat:
name/aussteller/datum korrekt zugeordnet.
"""
import logging

from ..models import Certification
from ..config import NOT_AVAILABLE
from .dom_utils import (
    iter_sdui_entries, iter_detail_entries, looks_like_period, split_by_middot,
    SDUI_CERTIFICATIONS,
)

logger = logging.getLogger("linkedin_scraper")

_LEGACY_PREFIX = "profile_CertificationDetails"


def parse_certifications_page(html: str) -> list[Certification]:
    entries = iter_sdui_entries(html, SDUI_CERTIFICATIONS) or iter_detail_entries(html, _LEGACY_PREFIX)
    if not entries:
        logger.warning("Keine Zertifikats-Einträge im HTML")
        return []

    certifications: list[Certification] = []
    for lines in entries:
        name = lines[0] if lines else NOT_AVAILABLE
        aussteller = lines[1] if len(lines) > 1 and not looks_like_period(lines[1]) else NOT_AVAILABLE
        datum = NOT_AVAILABLE
        for ln in lines[1:]:
            if "Ausgestellt" in ln:
                teil = split_by_middot(ln.split(":", 1)[-1].strip())
                datum = teil[0] if teil else ln.split(":", 1)[-1].strip()
                break
            if looks_like_period(ln):
                datum = ln
                break
        certifications.append(Certification(name=name, aussteller=aussteller, datum=datum))
    return certifications
