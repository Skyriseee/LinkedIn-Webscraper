"""Zentrales Logging: Konsole + Datei, für Nachvollziehbarkeit/Replizierbarkeit."""
import logging
import sys
from datetime import datetime
from .config import log_file_path


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger("linkedin_scraper")
    logger.setLevel(level)
    if logger.handlers:
        return logger  # bereits initialisiert

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    logger.addHandler(console)

    path = log_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    # mode="a" (Default): mehrere Läufe am selben Tag hängen an dieselbe Datei an
    # statt sie zu überschreiben - ein neuer Tag bekommt über log_file_path()
    # automatisch einen neuen Dateinamen (siehe config.py).
    file_handler = logging.FileHandler(path, encoding="utf-8")
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    return logger


class _TeeStream:
    """Spiegelt jede Ausgabe zusätzlich in die Tages-Logdatei (config.log_file_path()),
    mit sofortigem Flush nach jedem Schreibzugriff.

    Grund (Autor-Fund 2026-09-14): während eines laufenden Menüpunkts ist Copy/Paste
    in der Windows-Konsole gesperrt (siehe main._set_console_quick_edit), und wird die
    Konsole geschlossen oder stürzt der Prozess ab, ist der print()-basierte Verlauf
    (Fortschritt, Fehlermeldungen, Debug-Dump-Bestätigungen) sonst komplett weg - nur
    `logger.info/.warning/.error` landete bisher in der Logdatei, die zahlreichen
    print()-Statusmeldungen dagegen ausschließlich auf dem Bildschirm. Schreibt
    bewusst in dieselbe Datei wie das normale Logging, damit nicht zwei Dateien
    gegeneinander abgeglichen werden müssen; da alles hier strikt sequenziell aus
    einem einzigen Prozess/Thread kommt, bleibt die Reihenfolge beim Lesen intakt.
    """

    def __init__(self, original, log_file):
        self._original = original
        self._log_file = log_file

    def write(self, text):
        self._original.write(text)
        try:
            self._log_file.write(text)
            self._log_file.flush()
        except Exception:
            pass  # das Mitschreiben darf die eigentliche Ausgabe nie verhindern
        return len(text)

    def flush(self):
        self._original.flush()
        try:
            self._log_file.flush()
        except Exception:
            pass

    def __getattr__(self, name):
        return getattr(self._original, name)


def setup_console_capture() -> None:
    """Spiegelt ab hier ALLES, was auf stdout/stderr geschrieben wird (also auch die
    vielen print()-Statusmeldungen und ein unbehandelter Absturz-Traceback, nicht nur
    logger-Aufrufe), zusätzlich in die Tages-Logdatei (config.log_file_path()). Von
    main.main() ganz am Anfang aufgerufen (Autor-Wunsch 2026-09-14: „auch wenn die
    CLI geschlossen wird oder abbricht, der Log bis dahin gespeichert wird" - Copy/
    Paste aus der Konsole ist während eines Laufs gesperrt, ein Mitschnitt auf der
    Platte ist daher die einzige verlässliche Quelle danach)."""
    path = log_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    log_file = open(path, "a", encoding="utf-8", errors="replace")
    log_file.write(f"\n===== CLI-Mitschnitt gestartet: {datetime.now().isoformat(timespec='seconds')} =====\n")
    log_file.flush()
    sys.stdout = _TeeStream(sys.stdout, log_file)
    sys.stderr = _TeeStream(sys.stderr, log_file)
