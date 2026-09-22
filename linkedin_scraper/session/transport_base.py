"""Abstrakte Schnittstelle für die Übergabe der Browser-Session ans Python-Tool.
"""
from abc import ABC, abstractmethod


class SessionTransport(ABC):
    @abstractmethod
    def receive_session_data(self, timeout: int) -> dict:
        """Blockiert, bis die Extension Cookie-Daten liefert. Gibt {'cookies': {...}} zurück."""
        raise NotImplementedError
