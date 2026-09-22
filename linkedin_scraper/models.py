"""Datenmodelle für ein LinkedIn-Profil und seine Unterkategorien."""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class Experience:
    firma: str
    stelle: str
    arbeitsverhaeltnis: str
    standort: str
    zeitraum: str
    dauer: str


@dataclass
class Education:
    name: str
    fachrichtung: str
    zeitraum: str


@dataclass
class Certification:
    name: str
    aussteller: str
    datum: str


@dataclass
class Language:
    sprache: str
    niveau: str


@dataclass
class Profile:
    profile_url: str
    vorname: str = ""
    nachname: str = ""
    titel: str = ""
    ort: str = ""
    bundesland: str = ""
    land: str = ""
    email: str = ""
    geburtstag: str = ""
    experiences: list[Experience] = field(default_factory=list)
    educations: list[Education] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    certifications: list[Certification] = field(default_factory=list)
    languages: list[Language] = field(default_factory=list)
    # True, wenn die URL auf LinkedIns 404-Seite umgeleitet hat (Profil existiert nicht
    # mehr) - lässt csv_writer.py/json_writer.py dann config.PROFILE_NOT_FOUND ("404")
    # statt NOT_AVAILABLE ("N/A") ausgeben, siehe main.py:_not_found_profile.
    not_found: bool = False
