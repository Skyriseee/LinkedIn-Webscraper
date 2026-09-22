"""Eine einzige Geräte-Identität für beide Abrufwege.

Warum das nötig ist: Der HTTP-Weg (curl_cffi) und der Browser-Weg
sprechen im selben Lauf mit **demselben Session-Cookie** mit LinkedIn. Geben sie sich
dabei als zwei verschiedene Geräte aus - bis v0.4.0 „macOS/Chrome 131" über HTTP und
„Windows/Chrome 134" im Browser -, ist das aus Serversicht ein Gerätewechsel mitten in
der Sitzung. Genau darauf antwortet LinkedIn mit Logout + Mail-2FA.

Deshalb wird die Identität hier **einmal aus der laufenden Maschine abgeleitet** und von
beiden Wegen benutzt:

  * Betriebssystem aus `platform.system()` - nicht geraten.
  * Chrome-Hauptversion aus der real installierten Chrome-Installation.
  * Daraus: User-Agent, `sec-ch-ua`, `sec-ch-ua-platform` und das curl_cffi-
    Impersonation-Ziel (das nächstgelegene verfügbare `chromeNNN` <= Hauptversion).

Damit ist die Konfiguration zugleich **portabel**: auf einem anderen Rechner mit einer
anderen Chrome-Version ergibt sich automatisch eine dazu passende Identität, statt einer
fest verdrahteten, die dort nicht mehr stimmt (NFA5).

Schlägt die Erkennung fehl, wird auf die festen Werte in `config.py` zurückgefallen und
das protokolliert.
"""
from __future__ import annotations

import logging
import platform
import re
import subprocess
import sys

logger = logging.getLogger("linkedin_scraper")

# In curl_cffi 0.16 verfügbare Chrome-Impersonation-Ziele. Bewusst als Liste gepflegt
# statt dynamisch ermittelt, damit das Verhalten reproduzierbar dokumentiert ist; die
# Liste wird beim Import gegen das installierte curl_cffi geprüft.
_KNOWN_CHROME_TARGETS = [
    99, 100, 101, 104, 107, 110, 116, 119, 120, 123, 124, 131, 133, 136, 142, 145, 146, 150
]
# Ziele, die in curl_cffi einen Namenszusatz tragen.
_TARGET_SUFFIX = {133: "a"}

_WINDOWS_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/{major}.0.0.0 Safari/537.36")
_MAC_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
           "(KHTML, like Gecko) Chrome/{major}.0.0.0 Safari/537.36")
_LINUX_UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
             "(KHTML, like Gecko) Chrome/{major}.0.0.0 Safari/537.36")

_cache: dict | None = None


# -- Erkennung ---------------------------------------------------------------

def _chrome_version_windows() -> str | None:
    """Liest die aktive Chrome-Version aus der Registry.

    `HKCU\\Software\\Google\\Chrome\\BLBeacon` ist die Version, die der Benutzer
    tatsächlich startet. Der Uninstall-Eintrag unter HKLM kann davon abweichen (auf der
    Entwicklungsmaschine z. B. 152 vs. real laufende 134) und ist deshalb nur Rückfall.
    """
    try:
        import winreg
    except ImportError:  # pragma: no cover - nicht Windows
        return None
    kandidaten = [
        (winreg.HKEY_CURRENT_USER, r"Software\Google\Chrome\BLBeacon", "version"),
        (winreg.HKEY_LOCAL_MACHINE,
         r"SOFTWARE\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall\Google Chrome",
         "DisplayVersion"),
        (winreg.HKEY_LOCAL_MACHINE,
         r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Google Chrome",
         "DisplayVersion"),
    ]
    for hive, pfad, name in kandidaten:
        try:
            with winreg.OpenKey(hive, pfad) as key:
                wert = winreg.QueryValueEx(key, name)[0]
                if wert:
                    return str(wert)
        except OSError:
            continue
    return None


def _chrome_version_command() -> str | None:
    """Fragt Chrome auf der Kommandozeile (macOS/Linux, und Windows als Rückfall)."""
    kandidaten = [
        "google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    ]
    for exe in kandidaten:
        try:
            out = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=8)
        except (OSError, subprocess.SubprocessError):
            continue
        treffer = re.search(r"(\d+)\.(\d+)\.(\d+)", out.stdout or "")
        if treffer:
            return treffer.group(0)
    return None


def detect_chrome_version() -> str | None:
    """Volle Versionsnummer des installierten Chrome, z. B. '134.0.6998.89'."""
    if sys.platform.startswith("win"):
        return _chrome_version_windows() or _chrome_version_command()
    return _chrome_version_command()


def detect_chrome_major() -> int | None:
    version = detect_chrome_version()
    if not version:
        return None
    try:
        return int(version.split(".")[0])
    except (ValueError, IndexError):
        return None


# -- Ableitungen -------------------------------------------------------------

def impersonate_target(major: int) -> str:
    """Nächstgelegenes verfügbares curl_cffi-Ziel <= `major`.

    Bewusst nie nach oben runden: ein Ziel, das neuer ist als das installierte Chrome,
    würde einen Fingerprint erzeugen, den es auf dieser Maschine gar nicht geben kann.
    """
    passende = [t for t in _KNOWN_CHROME_TARGETS if t <= major]
    ziel = max(passende) if passende else min(_KNOWN_CHROME_TARGETS)
    return f"chrome{ziel}{_TARGET_SUFFIX.get(ziel, '')}"


def _platform_ua_template() -> tuple[str, str]:
    """(UA-Vorlage, sec-ch-ua-platform) passend zum laufenden Betriebssystem."""
    system = platform.system()
    if system == "Windows":
        return _WINDOWS_UA, '"Windows"'
    if system == "Darwin":
        return _MAC_UA, '"macOS"'
    return _LINUX_UA, '"Linux"'


def sec_ch_ua(major: int) -> str:
    """Client-Hints-Brands wie sie echtes Chrome sendet (Reihenfolge wie im Browser)."""
    return f'"Chromium";v="{major}", "Not:A-Brand";v="24", "Google Chrome";v="{major}"'


def identity() -> dict:
    """Die abgeleitete Identität - einmal ermittelt, dann zwischengespeichert.

    Rückgabe: dict mit `chrome_version`, `major`, `user_agent`, `sec_ch_ua`,
    `sec_ch_ua_platform`, `impersonate`, `detected` (bool).
    """
    global _cache
    if _cache is not None:
        return _cache

    version = detect_chrome_version()
    major = None
    if version:
        try:
            major = int(version.split(".")[0])
        except (ValueError, IndexError):
            major = None

    if major is None:
        from .config import USER_AGENT, SEC_CH_UA, SEC_CH_UA_PLATFORM, HTTP_IMPERSONATE
        logger.warning(
            "Chrome-Version nicht erkannt - falle auf die festen Werte aus config.py "
            "zurück (%s). Auf einer fremden Maschine kann das unstimmig sein.",
            HTTP_IMPERSONATE,
        )
        _cache = {
            "chrome_version": None, "major": None, "user_agent": USER_AGENT,
            "sec_ch_ua": SEC_CH_UA, "sec_ch_ua_platform": SEC_CH_UA_PLATFORM,
            "impersonate": HTTP_IMPERSONATE, "detected": False,
        }
        return _cache

    ua_vorlage, plattform = _platform_ua_template()
    _cache = {
        "chrome_version": version,
        "major": major,
        "user_agent": ua_vorlage.format(major=major),
        "sec_ch_ua": sec_ch_ua(major),
        "sec_ch_ua_platform": plattform,
        "impersonate": impersonate_target(major),
        "detected": True,
    }
    logger.info(
        "Geräte-Identität abgeleitet: Chrome %s auf %s -> impersonate=%s",
        version, platform.system(), _cache["impersonate"],
    )
    return _cache


def reset_cache() -> None:
    """Nur für Tests/Diagnose."""
    global _cache
    _cache = None
