# Baut LinkedInScraper.exe (onedir) aus dem Quellcode. Ausgabe landet in
# <Projektstamm>\LinkedInScraper\app\LinkedInScraper.exe - NICHT unter build\dist\ und
# NICHT direkt in LinkedInScraper\ (siehe LinkedInScraper.spec: der Rebuild räumt sein
# Zielverzeichnis komplett leer, und LinkedInScraper\data\ - das Browserprofil mit der
# aktiven Anmeldung - darf davon nie betroffen sein).
#
# Aufruf: aus einem beliebigen Verzeichnis  ->  powershell -File build\build.ps1
# Nach jeder Code-Änderung erneut ausführen, um die exe zu aktualisieren. data\ bleibt
# dabei unangetastet.

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot

py -3 -m PyInstaller --noconfirm `
    --distpath "$ProjectRoot\LinkedInScraper" `
    --workpath "$ProjectRoot\build\_work" `
    "$ProjectRoot\build\LinkedInScraper.spec"

Write-Host ""
Write-Host "Fertig: $ProjectRoot\LinkedInScraper\app\LinkedInScraper.exe"
