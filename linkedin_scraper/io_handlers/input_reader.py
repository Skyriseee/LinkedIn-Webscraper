"""Liest die Liste der zu scrapenden Profil-URLs aus einer CSV-Datei."""
from __future__ import annotations
import csv
import logging
import re
from pathlib import Path

logger = logging.getLogger("linkedin_scraper")

PROFILE_URL_PATTERN = re.compile(r"linkedin\.com/in/([^/?#]+)")


def read_profile_urls(csv_path: Path) -> list[str]:
    """Liest die Profil-URLs aus der ersten Spalte.

    Zeile 1 ist die Kopfzeile (`URL`) und wird immer übersprungen; Daten ab Zeile 2.
    Leere Zeilen und Zeilen ohne gültige LinkedIn-Profil-URL werden mit Warnung
    ignoriert, damit ein Tippfehler nicht den ganzen Lauf abbricht.
    """
    urls: list[str] = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)

    if not rows:
        logger.warning("%s ist leer.", csv_path)
        return urls

    header = rows[0][0].strip().lower() if rows[0] else ""
    if header != "url":
        logger.warning(
            "Kopfzeile in %s ist '%s', erwartet wurde 'URL'. Zeile 1 wird trotzdem "
            "als Kopfzeile behandelt und übersprungen.", csv_path, rows[0][0] if rows[0] else "",
        )

    for line_no, row in enumerate(rows[1:], start=2):
        if not row:
            continue
        value = row[0].strip()
        if not value:
            continue
        if not PROFILE_URL_PATTERN.search(value):
            logger.warning("Zeile %d in %s ist keine LinkedIn-Profil-URL, übersprungen: %r",
                           line_no, csv_path, value)
            continue
        urls.append(value)

    logger.info("%d Profil-URLs aus %s eingelesen (ab Zeile 2)", len(urls), csv_path)
    return urls


def extract_slug(profile_url: str) -> str:
    """Extrahiert die Profil-Kennung ('slug') aus der Haupt-URL, z.B. 'max-mustermann-123abc'."""
    match = PROFILE_URL_PATTERN.search(profile_url)
    if not match:
        raise ValueError(f"Keine gültige LinkedIn-Profil-URL: {profile_url}")
    return match.group(1)
