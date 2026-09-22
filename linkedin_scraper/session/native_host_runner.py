"""Wird von Chrome/Edge als Native-Messaging-Host gestartet (siehe install_native_host.py).

Liest EINE Nachricht der Extension (Native-Messaging-Protokoll: 4-Byte-Längenpräfix,
Little-Endian, + UTF-8-JSON), reicht sie an das laufende main.py (Loopback-Socket)
weiter und meldet das Ergebnis an die Extension zurück.

Wird über den generierten run_native_host.bat-Wrapper als
'python -m linkedin_scraper.session.native_host_runner' aus dem Projekt-Root gestartet.
"""
from __future__ import annotations
import json
import socket
import struct
import sys

from linkedin_scraper.config import NATIVE_BRIDGE_HOST, NATIVE_BRIDGE_PORT


def read_message() -> dict | None:
    raw_length = sys.stdin.buffer.read(4)
    if not raw_length or len(raw_length) < 4:
        return None
    length = struct.unpack("<I", raw_length)[0]
    data = sys.stdin.buffer.read(length)
    if len(data) < length:
        return None  # Verbindung abgebrochen, bevor die Nachricht vollständig war
    try:
        return json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None  # kaputte/unerwartete Daten - sauber abbrechen statt abzustürzen


def send_message(message: dict) -> None:
    data = json.dumps(message).encode("utf-8")
    sys.stdout.buffer.write(struct.pack("<I", len(data)))
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()


def main() -> None:
    message = read_message()
    if message is None:
        return

    try:
        with socket.create_connection((NATIVE_BRIDGE_HOST, NATIVE_BRIDGE_PORT), timeout=5) as sock:
            sock.sendall(json.dumps(message).encode("utf-8"))
        send_message({"ok": True})
    except OSError as exc:
        send_message({
            "ok": False,
            "error": f"Python-Tool nicht erreichbar ({exc}). Läuft main.py mit 'Session laden'?",
        })
    except Exception as exc:  # nie unbehandelt abstürzen - Chrome sonst ohne Antwort
        send_message({"ok": False, "error": f"Unerwarteter Fehler im Native Host: {exc}"})


if __name__ == "__main__":
    main()
