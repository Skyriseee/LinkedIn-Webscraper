"""Ein-Kommando-Setup: installiert Abhängigkeiten und baut LinkedInScraper.exe.

Für einen frischen Checkout gedacht (z. B. direkt nach `git clone`) - deckt alles ab,
was in der README unter "Setup"/"Kompilieren" sonst manuell in mehreren Schritten
nötig wäre. Nutzt überall `sys.executable`, arbeitet also in genau der
Python-Umgebung, aus der dieses Skript gestartet wurde (idealerweise eine vorher
aktivierte venv, siehe README).

Ablauf:
  1. Laufzeit-Abhängigkeiten installieren (requirements.txt, Versionen bewusst
     gepinnt - siehe Kopf der Datei zur Reproduzierbarkeits-Begründung).
  2. Build-Abhängigkeiten installieren (build/requirements-build.txt, nur für
     PyInstaller gebraucht).
  3. `playwright install chromium` - nur der Rückfall-Browser; im Normalbetrieb
     wird das installierte Google Chrome benutzt (config.BROWSER_CHANNEL).
  4. PyInstaller-Build ausführen - Python-Äquivalent zu build/build.ps1, damit
     dieser eine Schritt nicht an PowerShell hängt.
  5. `data/`-Ordnerstruktur im frisch gebauten `LinkedInScraper/` anlegen
     (linkedin_scraper.config.ensure_data_dirs()), damit der Ordner sofort
     nutzbar ist, ohne dass main.py dafür ein erstes Mal gestartet werden muss.

Für eine schnelle Neu-Kompilierung NACH einer Code-Änderung (Abhängigkeiten schon
installiert) reicht weiterhin `powershell -File build\build.ps1` - das überspringt
Schritte 1-3 und ist entsprechend schneller.

Aufruf: `python build.py` aus einem beliebigen Verzeichnis (der Projektstamm wird aus
dem Speicherort dieser Datei ermittelt, nicht aus dem aktuellen Arbeitsverzeichnis).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
GETESTETE_PYTHON_VERSION = (3, 12)


def _run(befehl: list[str], beschreibung: str) -> None:
    print(f"\n=== {beschreibung} ===")
    print("  $", " ".join(str(teil) for teil in befehl))
    ergebnis = subprocess.run(befehl, cwd=PROJECT_ROOT)
    if ergebnis.returncode != 0:
        print(f"\nAbgebrochen: {beschreibung} (Exit-Code {ergebnis.returncode})")
        sys.exit(ergebnis.returncode)


def _pruefe_python_version() -> None:
    if sys.version_info[:2] != GETESTETE_PYTHON_VERSION:
        aktuell = ".".join(str(t) for t in sys.version_info[:3])
        getestet = ".".join(str(t) for t in GETESTETE_PYTHON_VERSION)
        print(
            f"Hinweis: getestet ist Python {getestet} (siehe requirements.txt-Kopf, "
            f"Reproduzierbarkeit), aktuell läuft {aktuell}. Setup/Build laufen "
            "trotzdem weiter, im Fehlerfall zuerst hierauf prüfen."
        )


def main() -> None:
    _pruefe_python_version()

    _run(
        [sys.executable, "-m", "pip", "install", "-r", str(PROJECT_ROOT / "requirements.txt")],
        "Laufzeit-Abhängigkeiten installieren (requirements.txt)",
    )
    _run(
        [
            sys.executable, "-m", "pip", "install", "-r",
            str(PROJECT_ROOT / "build" / "requirements-build.txt"),
        ],
        "Build-Abhängigkeiten installieren (build/requirements-build.txt)",
    )
    _run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        "Playwright-Rückfallbrowser installieren (chromium)",
    )
    _run(
        [
            sys.executable, "-m", "PyInstaller", "--noconfirm",
            "--distpath", str(PROJECT_ROOT / "LinkedInScraper"),
            "--workpath", str(PROJECT_ROOT / "build" / "_work"),
            str(PROJECT_ROOT / "build" / "LinkedInScraper.spec"),
        ],
        "LinkedInScraper.exe bauen (PyInstaller)",
    )

    sys.path.insert(0, str(PROJECT_ROOT))
    from linkedin_scraper.config import ensure_data_dirs
    ensure_data_dirs()

    exe_pfad = PROJECT_ROOT / "LinkedInScraper" / "app" / "LinkedInScraper.exe"
    print(f"\nFertig: {exe_pfad}")
    print(
        "Vor dem ersten Scraping: die exe starten und Menüpunkt 1 (bei LinkedIn "
        "anmelden) einmal ausführen."
    )


if __name__ == "__main__":
    main()
