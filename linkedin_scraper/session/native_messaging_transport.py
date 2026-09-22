"""Empfängt die Session-Cookies von der Browser-Extension via lokalem Loopback-Socket.

Ablauf: Chrome/Edge erstellt bei chrome.runtime.connectNative() den native_host_runner.py
als eigenen Prozess. Dieser reicht die Cookie-Daten per TCP an main.py weiter, das
währenddessen NATIVE_BRIDGE_PORT prüft - es wird kein Cookie lokal gespeichert.
"""
import json
import logging
import socket

from .transport_base import SessionTransport
from ..config import NATIVE_BRIDGE_HOST, NATIVE_BRIDGE_PORT

logger = logging.getLogger("linkedin_scraper")


class NativeMessagingTransport(SessionTransport):
    def receive_session_data(self, timeout: int) -> dict:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind((NATIVE_BRIDGE_HOST, NATIVE_BRIDGE_PORT))
            server.listen(1)
            server.settimeout(timeout)
            logger.info(
                "Warte auf Session von der Browser-Extension (Port %s) - "
                "jetzt im Extension-Popup auf 'Session senden' klicken.",
                NATIVE_BRIDGE_PORT,
            )
            try:
                conn, _addr = server.accept()
            except socket.timeout as exc:
                raise TimeoutError(
                    "Keine Session empfangen (Timeout). Extension installiert und Host registriert?"
                ) from exc

            with conn:
                conn.settimeout(timeout)
                chunks = []
                while True:
                    chunk = conn.recv(4096)
                    if not chunk:
                        break
                    chunks.append(chunk)

        raw = b"".join(chunks).decode("utf-8")
        return json.loads(raw)
