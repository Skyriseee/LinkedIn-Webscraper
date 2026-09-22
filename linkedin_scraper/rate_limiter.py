"""Menschenähnliche Verzögerungen zwischen Requests (Bot-Erkennung / Politeness, NFA2).

Kein festes Intervall: Grunddelay ist zufällig, mit gelegentlichem längerem Aufschlag
("kurz abgelenkt"), plus eine deutlich längere Pause zwischen Profilen und alle N
Profile eine noch längere. Jeder Wert wird frisch gezogen - keine Wiederholung.
"""
import random
import time
import logging

from .config import (
    DELAY_MIN_SECONDS, DELAY_MAX_SECONDS,
    DISTRACTION_PROBABILITY, DISTRACTION_EXTRA_MIN_SECONDS, DISTRACTION_EXTRA_MAX_SECONDS,
    PROFILE_PAUSE_MIN_SECONDS, PROFILE_PAUSE_MAX_SECONDS,
    LONG_PAUSE_EVERY_PROFILES, LONG_PAUSE_MIN_SECONDS, LONG_PAUSE_MAX_SECONDS,
    EXTRA_LONG_PAUSE_EVERY_PROFILES, EXTRA_LONG_PAUSE_MIN_SECONDS, EXTRA_LONG_PAUSE_MAX_SECONDS,
)

logger = logging.getLogger("linkedin_scraper")


class RateLimiter:
    """Delay-Strategie mit vier Ebenen: pro Request, pro Profil, alle N Profile,
    alle M Profile noch länger (seit v0.7.13, ersetzt die frühere harte
    MAX_PROFILES_PER_RUN-Obergrenze)."""

    def __init__(self, min_delay: float = DELAY_MIN_SECONDS, max_delay: float = DELAY_MAX_SECONDS):
        self.min_delay = min_delay
        self.max_delay = max_delay
        self._profiles_done = 0

    def wait(self) -> None:
        """Vor jedem einzelnen Request - simuliert die Lesezeit auf einer Seite."""
        delay = random.uniform(self.min_delay, self.max_delay)
        if random.random() < DISTRACTION_PROBABILITY:
            delay += random.uniform(DISTRACTION_EXTRA_MIN_SECONDS, DISTRACTION_EXTRA_MAX_SECONDS)
        logger.debug("Warte %.1fs vor nächstem Request", delay)
        time.sleep(delay)

    def profile_done(self) -> None:
        """Nach einem vollständig verarbeiteten Profil aufrufen (zählt für die lange Pause)."""
        self._profiles_done += 1

    def between_profiles(self) -> None:
        """Pause bevor das nächste Profil angefasst wird."""
        if (EXTRA_LONG_PAUSE_EVERY_PROFILES
                and self._profiles_done % EXTRA_LONG_PAUSE_EVERY_PROFILES == 0):
            pause = random.uniform(EXTRA_LONG_PAUSE_MIN_SECONDS, EXTRA_LONG_PAUSE_MAX_SECONDS)
            logger.info("Extra lange Pause nach %d Profilen: %.0fs", self._profiles_done, pause)
        elif LONG_PAUSE_EVERY_PROFILES and self._profiles_done % LONG_PAUSE_EVERY_PROFILES == 0:
            pause = random.uniform(LONG_PAUSE_MIN_SECONDS, LONG_PAUSE_MAX_SECONDS)
            logger.info("Längere Pause nach %d Profilen: %.0fs", self._profiles_done, pause)
        else:
            pause = random.uniform(PROFILE_PAUSE_MIN_SECONDS, PROFILE_PAUSE_MAX_SECONDS)
            logger.info("Pause vor nächstem Profil: %.0fs", pause)
        time.sleep(pause)
