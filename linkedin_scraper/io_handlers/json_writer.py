"""Schreibt je Profil eine eigene JSON-Datei (FA8: Serialisierung nach CSV *und* JSON).

Anders als die CSV (eine flache Tabelle, alle Profile in einer Datei, Mehrfach-
Kategorien über gestapelte Zeilen) bildet die JSON die verschachtelte Struktur des
Zielschemas aus Abschnitt 3.3.3 unmittelbar ab: Kopfdaten unter ``person``, dazu je eine
Liste für Berufserfahrung, Ausbildung, Kenntnisse, Zertifikate und Sprachen.

Eine Datei pro Nutzereingabe, benannt ``<Vorname>_<Nachname>_<TTMMJJJJ>.json`` mit dem
Datum des Laufs (z. B. ``Martin_Reimann_10092026.json``). So ist am Dateinamen ablesbar,
welches Profil zu welchem Erhebungszeitpunkt gehört - wichtig für die längsschnittliche
Wiedererhebung (NFA8).

Fehlende Skalarfelder werden hier als ``null`` geführt (FA6: „`null`-Kennzeichnung
fehlender Felder"); die CSV behält das Sentinel ``N/A``, weil eine leere Tabellenzelle
dort mehrdeutig wäre. Leere Kategorien sind ``[]``.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import date
from pathlib import Path

from .. import __version__
from ..config import NOT_AVAILABLE, PROFILE_NOT_FOUND
from ..models import Profile

logger = logging.getLogger("linkedin_scraper")

_PERSON_FIELDS = ["vorname", "nachname", "titel", "ort", "bundesland", "land", "email", "geburtstag"]
_EXPERIENCE_FIELDS = ["firma", "stelle", "arbeitsverhaeltnis", "standort", "zeitraum", "dauer"]
_EDUCATION_FIELDS = ["name", "fachrichtung", "zeitraum"]
_CERTIFICATION_FIELDS = ["name", "aussteller", "datum"]
_LANGUAGE_FIELDS = ["sprache", "niveau"]

# Alles außer Buchstaben/Ziffern/Unterstrich/Bindestrich raus (dateisystemsicher).
_UNSAFE_NAME_CHARS = re.compile(r"[^0-9A-Za-zÄÖÜäöüß_-]+")


def _or_none(value):
    """`N/A` / leerer String → ``None``; sonst der Wert unverändert."""
    if value is None or value == NOT_AVAILABLE or (isinstance(value, str) and not value.strip()):
        return None
    return value


def _url_slug(profile_url: str) -> str:
    """Letztes nicht-leeres Pfadsegment einer Profil-URL (Rückfall für den Dateinamen)."""
    parts = [p for p in profile_url.rstrip("/").split("/") if p]
    return parts[-1] if parts else "profil"


def profile_filename(profile: Profile, run_date: date) -> str:
    """``<Vorname>_<Nachname>_<TTMMJJJJ>.json``; ohne verwertbaren Namen der URL-Slug.

    Bei einem 404-Profil (`profile.not_found`) steht in vorname/nachname der Marker
    PROFILE_NOT_FOUND ("404") statt eines echten Namens - der zählt hier NICHT als
    verwertbarer Name (sonst hieße die Datei "404_404_<Datum>.json"), fällt also auf
    den URL-Slug zurück, genau wie ein Profil ohne <title>-Namen."""
    raw = "_".join(
        part.strip()
        for part in (profile.vorname, profile.nachname)
        if part and part.strip() and part.strip() not in (NOT_AVAILABLE, PROFILE_NOT_FOUND)
    )
    name = _UNSAFE_NAME_CHARS.sub("", raw.replace(" ", "_")).strip("_-")
    if not name:
        name = _UNSAFE_NAME_CHARS.sub("", _url_slug(profile.profile_url))
    return f"{name}_{run_date.strftime('%d%m%Y')}.json"


def profile_to_dict(profile: Profile, run_date: date) -> dict:
    """Verschachteltes Zielschema als ``dict`` (siehe Modul-Docstring / Abschnitt 3.3.3)."""
    return {
        "meta": {
            "profil_url": profile.profile_url,
            "abgerufen_am": run_date.isoformat(),
            "werkzeug_version": __version__,
        },
        "person": {f: _or_none(getattr(profile, f)) for f in _PERSON_FIELDS},
        "berufserfahrung": [
            {f: _or_none(getattr(e, f)) for f in _EXPERIENCE_FIELDS} for e in profile.experiences
        ],
        "ausbildung": [
            {f: _or_none(getattr(e, f)) for f in _EDUCATION_FIELDS} for e in profile.educations
        ],
        "kenntnisse": list(profile.skills),
        "zertifikate": [
            {f: _or_none(getattr(c, f)) for f in _CERTIFICATION_FIELDS} for c in profile.certifications
        ],
        "sprachen": [
            {f: _or_none(getattr(s, f)) for f in _LANGUAGE_FIELDS} for s in profile.languages
        ],
    }


class JsonWriter:
    """Schreibt je Profil eine JSON-Datei in ``output_dir``.

    Kein Kontextmanager nötig (keine über den Lauf offene Datei) - je Aufruf von
    :meth:`write_profile` wird genau eine Datei geschlossen geschrieben, damit bei einem
    Abbruch mitten im Lauf die bereits erhobenen Profile vollständig vorliegen (NFA1).
    """

    def __init__(self, output_dir: Path, run_date: date | None = None):
        self.output_dir = Path(output_dir)
        self.run_date = run_date or date.today()
        self._written: set[Path] = set()

    def write_profile(self, profile: Profile) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        path = self.output_dir / profile_filename(profile, self.run_date)

        # Kollision *innerhalb desselben Laufs* (zwei verschiedene Profile, gleicher Name
        # und gleiches Datum): mit Zähler eindeutig machen. Eine Datei aus einem früheren
        # Lauf am selben Tag wird bewusst überschrieben (gleicher Tag → gleiches Ergebnis).
        if path in self._written:
            stem, suffix = path.stem, path.suffix
            n = 2
            while (cand := self.output_dir / f"{stem}_{n}{suffix}") in self._written:
                n += 1
            path = cand

        data = profile_to_dict(profile, self.run_date)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        self._written.add(path)
        logger.info("Profil als JSON geschrieben: %s", path)
        return path
