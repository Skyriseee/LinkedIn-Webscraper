"""Mappt die Voyager-JSON-Antworten (`profileView`, `profileContactInfo`) auf die
Datenmodelle - für die sechs Felder, die über den HTML-Weg nicht kommen:
E-Mail, Geburtstag, Ausbildung, Kenntnisse, Sprachen, Zertifikate.

Die JSON-Struktur der klassischen REST-Endpunkte ist seit Jahren stabil:
`profileView` -> `educationView/skillView/languageView/certificationView.elements[]`,
`profileContactInfo` -> `emailAddress`, `birthDateOn:{month,day}`. Trotzdem wird überall
defensiv mit `.get()` gelesen und pro Feld auf `N/A` zurückgefallen, falls LinkedIn ein
Feld umbenennt (siehe Debug-Dump „voyager" in main.py, um die Rohantwort zu prüfen).
"""
from __future__ import annotations

import logging

from ..config import NOT_AVAILABLE
from ..models import Education, Certification, Language

logger = logging.getLogger("linkedin_scraper")

# LinkedIn-Enum -> deutsches UI-Label (Abgleich mit den verifizierten Browser-Dumps).
_PROFICIENCY_DE = {
    "NATIVE_OR_BILINGUAL": "Muttersprache oder zweisprachig",
    "FULL_PROFESSIONAL": "Verhandlungssicher",
    "PROFESSIONAL_WORKING": "Fließend",
    "LIMITED_WORKING": "Gute Kenntnisse",
    "ELEMENTARY": "Grundkenntnisse",
}

_MONTHS_DE_ABBR = {
    1: "Jan.", 2: "Feb.", 3: "März", 4: "Apr.", 5: "Mai", 6: "Juni",
    7: "Juli", 8: "Aug.", 9: "Sept.", 10: "Okt.", 11: "Nov.", 12: "Dez.",
}


def _view_elements(root: dict, view_name: str) -> list[dict]:
    """`root[view_name]['elements']`, auch wenn die Antwort in einem `data`-Objekt
    verschachtelt ist. Gibt `[]` zurück, wenn die View fehlt."""
    bases = [root]
    data = root.get("data")
    if isinstance(data, dict):
        bases.append(data)
    for base in bases:
        view = base.get(view_name)
        if isinstance(view, dict) and isinstance(view.get("elements"), list):
            return view["elements"]
    return []


def _fmt_month_year(date: dict | None) -> str:
    """{'year': 2023, 'month': 4} -> 'Apr. 2023'; nur Jahr -> '2023'; sonst ''."""
    if not isinstance(date, dict) or not date.get("year"):
        return ""
    year = date["year"]
    month = date.get("month")
    if month in _MONTHS_DE_ABBR:
        return f"{_MONTHS_DE_ABBR[month]} {year}"
    return str(year)


def _fmt_period(time_period: dict | None) -> str:
    """{'startDate': {...}, 'endDate': {...}} -> 'Apr. 2023–Okt. 2026'.
    Fehlt endDate, gilt 'Heute'. Ganz ohne Datum -> ''."""
    if not isinstance(time_period, dict):
        return ""
    start = _fmt_month_year(time_period.get("startDate"))
    end = _fmt_month_year(time_period.get("endDate"))
    if start and end:
        return f"{start}–{end}"
    if start:
        return f"{start}–Heute"
    return end or ""


# -- Ausbildung / Kenntnisse / Sprachen / Zertifikate aus profileView -----------

def parse_education(profile_view: dict) -> list[Education]:
    out: list[Education] = []
    for el in _view_elements(profile_view, "educationView"):
        name = el.get("schoolName") or NOT_AVAILABLE
        fach = " · ".join(p for p in (el.get("degreeName"), el.get("fieldOfStudy")) if p)
        out.append(Education(
            name=name,
            fachrichtung=fach or NOT_AVAILABLE,
            zeitraum=_fmt_period(el.get("timePeriod")) or NOT_AVAILABLE,
        ))
    return out


def parse_skills(profile_view: dict) -> list[str]:
    names = [el.get("name") for el in _view_elements(profile_view, "skillView") if el.get("name")]
    return names


def parse_languages(profile_view: dict) -> list[Language]:
    out: list[Language] = []
    for el in _view_elements(profile_view, "languageView"):
        prof = el.get("proficiency") or ""
        out.append(Language(
            sprache=el.get("name") or NOT_AVAILABLE,
            niveau=_PROFICIENCY_DE.get(prof, prof or NOT_AVAILABLE),
        ))
    return out


def parse_certifications(profile_view: dict) -> list[Certification]:
    out: list[Certification] = []
    for el in _view_elements(profile_view, "certificationView"):
        aussteller = el.get("authority")
        if not aussteller and isinstance(el.get("company"), dict):
            aussteller = el["company"].get("name")
        datum = _fmt_month_year((el.get("timePeriod") or {}).get("startDate"))
        out.append(Certification(
            name=el.get("name") or NOT_AVAILABLE,
            aussteller=aussteller or NOT_AVAILABLE,
            datum=datum or NOT_AVAILABLE,
        ))
    return out


def parse_profile_view(profile_view: dict) -> dict:
    """Alle vier Listen-Sektionen auf einmal."""
    return {
        "educations": parse_education(profile_view),
        "skills": parse_skills(profile_view),
        "languages": parse_languages(profile_view),
        "certifications": parse_certifications(profile_view),
    }


# -- E-Mail / Geburtstag aus profileContactInfo --------------------------------

def parse_contact_info_json(contact: dict) -> dict:
    result = {"email": NOT_AVAILABLE, "geburtstag": NOT_AVAILABLE}
    base = contact.get("data") if isinstance(contact.get("data"), dict) else contact

    email = base.get("emailAddress")
    if isinstance(email, dict):  # manche Varianten: {"emailAddress": {"email": "..."}}
        email = email.get("email") or email.get("emailAddress")
    if email:
        result["email"] = email
    else:
        logger.info("profileContactInfo enthält keine E-Mail - nicht freigegeben (N/A).")

    birth = base.get("birthDateOn") or base.get("birthDate")
    if isinstance(birth, dict) and birth.get("month") and birth.get("day"):
        result["geburtstag"] = f"{int(birth['day']):02d}.{int(birth['month']):02d}."

    return result
