# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller-Spezifikation für den LinkedIn Research Scraper.

Baut eine ONEDIR-Anwendung (kein onefile): Playwright (node.exe + Treiber-Paket) und
curl_cffi bringen eigene Binärdateien mit, die bei onefile bei JEDEM Start neu in
einen Temp-Ordner entpackt würden. onedir startet dagegen sofort, die Binärdateien
liegen dauerhaft im Ausgabeordner.

WICHTIG (seit v0.7.7): Der COLLECT-Name ist bewusst "app", nicht "LinkedInScraper".
Zusammen mit --distpath (siehe build/build.ps1) landet die exe unter
LinkedInScraper/app/LinkedInScraper.exe - EINE Ebene unter dem eigentlichen
LinkedInScraper/-Ordner, der daneben noch ein data/ trägt (das Browserprofil mit der
aktiven Anmeldung, siehe linkedin_scraper/config.py). Ein Rebuild räumt NUR
LinkedInScraper/app/ leer und neu auf (PyInstaller löscht den COLLECT-Zielordner beim
Neubau vollständig - getestet 2026-09-11) - data/ als Geschwisterordner bleibt davon
unberührt. Läge data/ direkt in LinkedInScraper/, würde jeder Rebuild die Session
löschen.

NICHT direkt mit `pyinstaller build/LinkedInScraper.spec` aufrufen - dann landet die
App unter build/dist/ und findet ihr data/ nicht mehr am erwarteten Ort. Immer über
build/build.ps1 bauen.
"""
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

PROJECT_ROOT = Path(SPECPATH).resolve().parent

datas = []
binaries = []
hiddenimports = []
# collect_all statt nur collect_data_files: beide Pakete bringen Binärdateien mit
# (Playwright: node.exe + Treiber-Paket; curl_cffi: gebündeltes libcurl), die
# PyInstallers automatische Analyse bei CFFI-/Subprocess-basierten Paketen zuverlässig
# nur über diesen Weg findet.
for pkg in ("playwright", "curl_cffi"):
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(pkg)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

a = Analysis(
    [str(PROJECT_ROOT / "run.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    # Läuft vor den automatisch erkannten Paket-Runtime-Hooks (siehe die Datei selbst) -
    # unterdrückt die kosmetische pkg_resources-Deprecation-Warnung beim exe-Start.
    runtime_hooks=[str(PROJECT_ROOT / "build" / "rthook_suppress_pkg_resources.py")],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="LinkedInScraper",
    console=True,
    icon=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="app",
)
