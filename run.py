"""Build-Einstiegspunkt für PyInstaller (siehe build/).

Für den normalen Quellcode-Betrieb weiterhin `python -m linkedin_scraper.main`
benutzen - dieses Skript existiert nur, damit PyInstaller einen Datei-Pfad als
Analyse-Startpunkt hat (siehe build/LinkedInScraper.spec).

Die pkg_resources-Deprecation-Warnung beim exe-Start wird NICHT hier unterdrückt -
das wäre zu spät (die Warnung feuert schon während eines automatischen PyInstaller-
Runtime-Hooks, bevor dieses Skript überhaupt läuft). Siehe stattdessen
build/rthook_suppress_pkg_resources.py.
"""
from linkedin_scraper.main import main

if __name__ == "__main__":
    main()
