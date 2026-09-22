"""Einmalig ausführen, um den Native-Messaging-Host bei Chrome/Edge zu registrieren.

Aufruf:  python -m linkedin_scraper.session.install_native_host <EXTENSION_ID>
Die EXTENSION_ID steht in chrome://extensions bzw. edge://extensions, nachdem die
Extension aus browser_extension/ als "entpackt" geladen wurde.
"""
import json
import sys
import winreg
from pathlib import Path

from ..config import NATIVE_HOST_NAME

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
WRAPPER_BAT = PROJECT_ROOT / "linkedin_scraper" / "session" / "run_native_host.bat"
MANIFEST_DIR = Path.home() / "AppData" / "Local" / "linkedin_research_scraper"
MANIFEST_PATH = MANIFEST_DIR / f"{NATIVE_HOST_NAME}.json"

# Registry-Pfade der unterstützten Chromium-Browser
BROWSER_REGISTRY_ROOTS = [
    r"Software\Google\Chrome\NativeMessagingHosts",
    r"Software\Microsoft\Edge\NativeMessagingHosts",
]


def write_wrapper_bat() -> None:
    WRAPPER_BAT.write_text(
        "@echo off\r\n"
        f'cd /d "{PROJECT_ROOT}"\r\n'
        # "py" (Python Launcher for Windows) statt "python": umgeht zuverlässig den
        # kaputten Microsoft-Store-Alias-Stub, der unter "python" im PATH stehen kann.
        "py -3 -m linkedin_scraper.session.native_host_runner\r\n",
        encoding="utf-8",
    )


def write_manifest(extension_id: str) -> None:
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {
        "name": NATIVE_HOST_NAME,
        "description": "LinkedIn Research Scraper - Session Bridge (Bachelorarbeit)",
        "path": str(WRAPPER_BAT),
        "type": "stdio",
        "allowed_origins": [f"chrome-extension://{extension_id}/"],
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def register_in_registry() -> None:
    for reg_path in BROWSER_REGISTRY_ROOTS:
        try:
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, f"{reg_path}\\{NATIVE_HOST_NAME}")
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, str(MANIFEST_PATH))
            winreg.CloseKey(key)
            print(f"Registriert: HKCU\\{reg_path}\\{NATIVE_HOST_NAME}")
        except OSError as exc:
            print(f"Übersprungen ({reg_path}): {exc}")


def main() -> None:
    if len(sys.argv) != 2:
        print("Aufruf: python -m linkedin_scraper.session.install_native_host <EXTENSION_ID>")
        sys.exit(1)

    extension_id = sys.argv[1]
    write_wrapper_bat()
    write_manifest(extension_id)
    register_in_registry()
    print(f"Native-Messaging-Host '{NATIVE_HOST_NAME}' registriert. Manifest: {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
