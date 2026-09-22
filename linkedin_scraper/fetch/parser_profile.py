"""Parst die Haupt-Profilseite /in/<slug>/: Name, Titel/Headline, Standort.

Stand 2026 (SDUI): Der Name steht immer im
`<title>Vorname Nachname | LinkedIn</title>`. Headline und Standort stehen in der
Topcard-Sektion `section[componentkey$="Topcard"]` - die ist aber Teil der
client-seitig gerenderten Seite und in einem reinen `requests.get()` NICHT
enthalten. Gegen einen hand-gespeicherten Browser-Dump (2026-09-06) verifiziert:
in der Topcard stehen als `<p>` in dieser Reihenfolge
  [0] Headline (z. B. "In Ausbildung/Studium: ...")
  [1] aktuelle Firma · Schule
  [2] Standort (z. B. "Chemnitz, Sachsen, Deutschland")
  [.] "·" / "Kontaktinformationen" / ...
Der Standort wird an ", " in Ort / Bundesland / Land zerlegt.
"""
import logging
import re

from ..models import Profile
from ..config import NOT_AVAILABLE
from .dom_utils import get_soup, clean_text

logger = logging.getLogger("linkedin_scraper")

_TITLE_SUFFIX = re.compile(r'\s*\|\s*LinkedIn\s*$')
_TOPCARD_SEL = '[componentkey$="Topcard"]'
_CONTACT_MARKERS = ("Kontaktinformationen", "Kontaktinfo")
# Stand 2026-09: die Topcard beginnt mit Zähl-Markierungen wie "· 1." / "· 2." (SDUI v2).
# Solche Zeilen sind keine Headline und werden verworfen.
_MIDDOT_NOISE_RE = re.compile(r'^[·•∙・]\s*\d*\.?$')
# LinkedIn zeigt ein optionales Pronomen-Badge ("He/Him", "She/Her", ...) als eigene
# <p>-Zeile in der Topcard. Steht sie vor der eigentlichen Headline, wurde sie bisher
# fälschlich als Headline übernommen (Autor-Fund 2026-09-13 im laufenden Testkorpus:
# 9 von 35 Profilen hatten `titel` == "He/Him"/"She/Her" statt der echten
# Berufsbezeichnung). Bewusst ein enger, exakter Treffer auf die von LinkedIn
# vorgegebene Auswahlliste - keine echte Headline lautet nur "He/Him".
_PRONOUN_RE = re.compile(
    r'^(he|she|they|ze|xe|zie)\s*/\s*(him|her|them|zir|xem|hir)\.?$', re.IGNORECASE
)


def parse_profile_page(html: str, profile_url: str) -> Profile:
    soup = get_soup(html)
    profile = Profile(profile_url=profile_url)

    vorname, nachname = _parse_name(soup)
    profile.vorname = vorname
    profile.nachname = nachname
    if not vorname and not nachname:
        logger.warning("Kein Name auf Profilseite gefunden für %s - Markup evtl. geändert", profile_url)

    card = soup.select_one(_TOPCARD_SEL)
    if card is None:
        logger.warning(
            "Topcard-Sektion nicht gefunden für %s - Headline/Standort bleiben N/A "
            "(Dump vermutlich ohne JS gerendert).", profile_url
        )

    paragraphs = _card_paragraphs(card)
    location_line = _find_location_line(paragraphs)
    profile.titel = _parse_headline(
        paragraphs, full_name=f"{vorname} {nachname}".strip(), location_line=location_line
    )
    profile.ort, profile.bundesland, profile.land = _parse_location(location_line)

    return profile


def _parse_name(soup) -> tuple[str, str]:
    title_tag = soup.find("title")
    if not title_tag:
        return "", ""
    name = _TITLE_SUFFIX.sub("", clean_text(title_tag)).strip()
    if not name:
        return "", ""
    parts = name.split()
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def _card_paragraphs(card) -> list[str]:
    """Nicht-leere <p>-Texte der Topcard, ohne reine Trennzeichen und ohne <p>,
    die in einem Link/Button stecken (Verifizieren-CTA, Kontaktezähler, „Offen für"-
    Badge). Übrig bleiben Headline, Firma·Schule, Standort, Kontaktinfo-Label ..."""
    if card is None:
        return []
    out: list[str] = []
    for p in card.find_all("p"):
        text = clean_text(p)
        if not text or _MIDDOT_NOISE_RE.match(text) or _PRONOUN_RE.match(text):
            continue
        if any(a.name in ("a", "button") for a in p.parents if a is not card):
            continue
        out.append(text)
    return out


def _find_location_line(paragraphs: list[str]) -> str:
    """Die rohe, unaufgeteilte Standort-Zeile - direkt vor dem
    "Kontaktinformationen"-Link, sonst als Fallback die erste Komma-getrennte, nicht
    durch Middot getrennte Zeile nach der Headline. Wird sowohl von `_parse_location`
    (dort weiter aufgeteilt) als auch von `_parse_headline` benutzt, damit diese Zeile
    nicht fälschlich als Headline übernommen wird, wenn eine Headline fehlt (siehe
    `_parse_headline`)."""
    for i, text in enumerate(paragraphs):
        if any(text.startswith(m) for m in _CONTACT_MARKERS) and i >= 1:
            return paragraphs[i - 1]
    for text in paragraphs[1:]:
        if ", " in text and " · " not in text:
            return text
    return ""


def _parse_headline(paragraphs: list[str], full_name: str, location_line: str) -> str:
    """Regelfall: erste <p>-Zeile der Topcard ist die Headline.

    Manche Profile haben aber gar keine Headline gesetzt - dann ist die erste Zeile
    der Topcard schon die Standort-Zeile, die sonst fälschlich als Headline
    übernommen würde (gefunden 2026-09-14 an einem Profil ohne Namen/Headline: der
    Standort landete sowohl in `titel` als auch in `ort`/`bundesland`/`land`)."""
    if paragraphs:
        first = paragraphs[0]
        if first and first != full_name and first != location_line:
            return first
    return NOT_AVAILABLE


def _parse_location(location_line: str) -> tuple[str, str, str]:
    na = (NOT_AVAILABLE, NOT_AVAILABLE, NOT_AVAILABLE)
    if not location_line:
        return na

    parts = [p.strip() for p in location_line.split(",") if p.strip()]
    if not parts:
        return na
    ort = parts[0]
    if len(parts) >= 3:
        return ort, parts[1], parts[-1]
    if len(parts) == 2:
        return ort, NOT_AVAILABLE, parts[1]
    return ort, NOT_AVAILABLE, NOT_AVAILABLE
