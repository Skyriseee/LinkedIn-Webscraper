"""Schreibt Profile im Format der ExportVorlage.csv (Mehrfach-Einträge = mehrere Zeilen)."""
from __future__ import annotations
import csv
import logging
from datetime import date
from pathlib import Path

from ..config import CSV_COLUMNS, NOT_AVAILABLE, PROFILE_NOT_FOUND
from ..models import Profile

logger = logging.getLogger("linkedin_scraper")

# (Attribut-Name am Profile-Objekt, Feldnamen je Eintrag) je Mehrfach-Kategorie,
# in exakter CSV-Spaltenreihenfolge. 'None' = einfache String-Liste (z.B. Kenntnisse).
_CATEGORY_SPECS = [
    ("experiences", ["firma", "stelle", "arbeitsverhaeltnis", "standort", "zeitraum", "dauer"]),
    ("educations", ["name", "fachrichtung", "zeitraum"]),
    ("skills", None),
    ("certifications", ["name", "aussteller", "datum"]),
    ("languages", ["sprache", "niveau"]),
]

_PERSON_FIELDS = ["vorname", "nachname", "titel", "ort", "bundesland", "land", "email", "geburtstag"]


def profile_to_rows(profile: Profile) -> list[list[str]]:
    """Baut die CSV-Zeilen einer Person: Personendaten nur Zeile 1, Kategorien
    positionsbasiert untereinander gestapelt. Eine komplett leere Kategorie wird in
    Zeile 1 in *allen* ihren Spalten mit 'N/A' markiert (DQ4: nicht scrapbare Felder
    explizit belegen); die Markierung wird nicht auf jede Folgezeile wiederholt - so
    wie auch die Personendaten oder eine nur kürzere Liste nicht wiederholt werden.

    Ein Profil, dessen URL auf die 404-Seite umgeleitet hat (`profile.not_found`),
    bekommt eine einzige Zeile mit PROFILE_NOT_FOUND ("404") in jeder Spalte - das
    unterscheidet sich bewusst von NOT_AVAILABLE ("N/A"), das eine leere Kategorie
    eines EXISTIERENDEN Profils markiert (siehe config.py)."""
    if profile.not_found:
        return [[PROFILE_NOT_FOUND] * len(CSV_COLUMNS)]

    categories = [(getattr(profile, attr), fields) for attr, fields in _CATEGORY_SPECS]
    max_rows = max([len(items) for items, _ in categories] + [1])

    rows = []
    for i in range(max_rows):
        row = [getattr(profile, f) for f in _PERSON_FIELDS] if i == 0 else [""] * len(_PERSON_FIELDS)

        for items, fields in categories:
            width = 1 if fields is None else len(fields)
            if not items:
                row += [NOT_AVAILABLE] * width if i == 0 else [""] * width
            elif i < len(items):
                entry = items[i]
                row += [entry] if fields is None else [getattr(entry, f) for f in fields]
            else:
                row += [""] * width
        rows.append(row)
    return rows


def output_csv_filename(run_date: date) -> str:
    """`output_results_<TTMMJJJJ>.csv` - Datum = Tag des Laufs, analog zu
    io_handlers/json_writer.py (dort je Profil, hier eine Datei fürs ganze CSV)."""
    return f"output_results_{run_date.strftime('%d%m%Y')}.csv"


class CsvWriter:
    """Schreibt Ergebnisse inkrementell (Zeile pro Zeile), damit bei einem Absturz
    mitten im Lauf bereits gescrapte Profile nicht verloren gehen - in eine
    datumsversionierte Datei je KALENDERTAG (`output_csv_filename`), nicht mehr eine
    einzige durchgehende Datei über alle Läufe (Stand v0.7.11).

    Mehrere Läufe am selben Tag hängen an dieselbe Datei an, statt sie zu überschreiben
    (Autor-Fund 2026-09-13: bei mehreren Test-Läufen am selben Tag hat der zweite Lauf
    die Ergebnisse des ersten sonst gelöscht). Der Header wird nur beim allerersten Lauf
    des Tages geschrieben - jeder folgende Lauf hängt seine Zeilen einfach an."""

    def __init__(self, output_dir: Path, run_date: date | None = None):
        self.output_dir = Path(output_dir)
        self.run_date = run_date or date.today()
        self.output_path = self.output_dir / output_csv_filename(self.run_date)
        self._file = None
        self._writer = None

    def __enter__(self):
        self.output_dir.mkdir(parents=True, exist_ok=True)
        # Existiert die Datei schon (ein früherer Lauf am selben Tag), wird angehängt -
        # OHNE erneuten Header und OHNE erneutes BOM (utf-8-sig würde bei jedem neuen
        # Schreib-Handle ein eigenes BOM voranstellen; mitten in der Datei wäre das ein
        # sichtbares Datenmüll-Zeichen). Neue Datei = neuer Tag = frisches BOM + Header.
        gibt_es_schon = self.output_path.exists()
        encoding = "utf-8" if gibt_es_schon else "utf-8-sig"
        self._file = open(self.output_path, "a", newline="", encoding=encoding)
        self._writer = csv.writer(self._file)
        if not gibt_es_schon:
            self._writer.writerow(CSV_COLUMNS)
        return self

    def write_profile(self, profile: Profile) -> None:
        for row in profile_to_rows(profile):
            self._writer.writerow(row)
        self._file.flush()
        logger.info("Profil geschrieben: %s", profile.profile_url)

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._file:
            self._file.close()
