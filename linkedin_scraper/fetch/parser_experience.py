"""Parst /details/experience/: Firma, Stelle, Arbeitsverhältnis, Standort, Zeitraum, Dauer.

DOM-basiert (siehe dom_utils.py) - LinkedIn liefert hier kein eingebettetes Voyager-JSON
mehr, sondern serverseitig gerendertes HTML mit stabilen Struktur-Markern
('data-testid', 'componentkey'), nur CSS-Klassen sind gehasht/instabil.

Struktur (Stand 2026):
  section[data-testid^="profile_ExperienceDetailsSection_"]
    > div[componentkey^="entity-collection-item-"]      # je Eintrag (EIN Bindestrich!)
        - Einzelposition:  <a href*="/edit/forms/"> mit i.d.R. 4 <p>:
            [0] Stelle
            [1] "Firma · Arbeitsverhältnis"
            [2] "Zeitraum · Dauer"
            [3] "Standort · Arbeitsmodell" (oder eine frei formulierte Beschreibung/
                Aufzählung der Position - siehe _looks_like_location unten)
        - Mehrfach-Gruppe (mehrere Rollen bei einer Firma): enthält ein <ul>.
            Firmenname/Gesamtdauer/Standort im <a href*="/company/"|"/school/">-Header;
            je Rolle ein <li> mit [0] Stelle, dann i.d.R. [1] Arbeitsverhältnis,
            [2] "Zeitraum · Dauer" - **aber nicht zuverlässig in dieser Reihenfolge**
            (siehe unten).

Firma wird bei mehreren Positionen in derselben Firma auf jeder Positions-Zeile
wiederholt (siehe Absprache zur ExportVorlage.csv).

**Erkenntnis aus dem ersten echten Testkorpus (v0.7.9):**
Die feste Index-Annahme [1]=Arbeitsverhältnis/[2]="Zeitraum · Dauer" je `<li>` einer
Mehrfach-Gruppe gilt nur, wenn eine Rolle WIRKLICH ein separates Arbeitsverhältnis-`<p>`
hat. Fehlt es (z. B. bei der aktuellen/jüngsten Rolle recht häufig), rutscht der Zeitraum
auf Index [1] und Index [2] wird zu Standort oder gar einem frei formulierten
Beschreibungstext - beides landete vorher unbemerkt in den falschen Feldern (Zeitraum
als Arbeitsverhältnis, ein Ort oder Fließtext als Zeitraum). Ebenso kann die optionale
Freitext-Beschreibung einer Position (Aufgaben, Stichpunkte) an der Stelle auftauchen, an
der sonst der Standort steht (`_parse_single_position`s `ps[3]`, `_group_header`s `ps[2]`)
- auch das wurde vorher ungeprüft übernommen. Fix: Zeitraum/Dauer werden über
`looks_like_period` (Jahreszahl) erkannt, Arbeitsverhältnis über eine Positivliste
bekannter Werte (`_EMPLOYMENT_TYPES`) statt über die Position, und ein Standort-Kandidat
wird nur übernommen, wenn er nicht wie ein Zeitraum, eine Kenntnisse-Aufzählung oder ein
längerer Fließtext aussieht (`_looks_like_location`) - sonst `NOT_AVAILABLE` statt
falscher Daten (DQ4).

**Fund v0.7.29 (Marcel Merkel/TeamBank AG):** der
Gruppen-Header selbst hat nicht immer einen eigenen Standort-Absatz - eine einzelne
Rolle (v.a. die aktuellste) kann aber direkt nach ihrem eigenen Zeitraum einen eigenen
Standort-Absatz haben, der bis dahin für alle Rollen ungeprüft verworfen wurde. Fix:
`_parse_multi_position_group` prüft den Absatz direkt nach dem erkannten Zeitraum jeder
Rolle zusätzlich per `_looks_like_location` und nutzt ihn, falls gültig; sonst bleibt
der Gruppen-Header-Standort als Fallback.
"""
from __future__ import annotations
import logging
import re

from ..models import Experience
from ..config import NOT_AVAILABLE
from .dom_utils import get_soup, split_by_middot, clean_text, looks_like_period

logger = logging.getLogger("linkedin_scraper")

_EDIT_LINK = "/edit/forms/"
_ORG_LINK_MARKERS = ("/company/", "/school/")
# Leerzustand-Text, den auch die vier anderen (SDUI-)Detailseiten kennen (siehe
# dom_utils._EMPTY_STATE_MARKERS) - hier separat gehalten, weil parser_experience.py
# (noch) nicht über iter_sdui_entries läuft.
_EMPTY_STATE_MARKERS = ("Noch keine Informationen", "No information available")
# LinkedIn hat die vier anderen Detailseiten (Ausbildung/Kenntnisse/Sprachen/
# Zertifikate) 2026-09 auf SDUI (LazyColumn, data-sdui-screen) umgestellt - die
# Erfahrungsseite galt bisher als einzige Ausnahme, weiterhin SSR mit dem alten
# entity-collection-item--Markup (siehe Moduldocstring). Ein am 2026-09-13
# angeforderter Debug-Dump von kreuter92 zeigte aber genau dieses SDUI-Markup auch
# für /details/experience/ (data-sdui-screen="...ProfileExperienceDetails") - dort
# allerdings mit echtem Leerzustand-Text, sodass sich (noch) nicht klären ließ, ob
# das ein flächendeckender LinkedIn-Rollout ist. Dieser Selektor dient NUR der
# Erkennung/Warnung unten, nicht dem eigentlichen Parsen (siehe _warn_if_unrecognized).
_SDUI_EXPERIENCE_SEL = '[data-sdui-screen$="ProfileExperienceDetails"]'

# Bekannte LinkedIn-Arbeitsverhältnis-Werte (DE/EN) - Positivliste statt Positionsannahme,
# weil das <p> dafür je nach Rolle fehlen kann (siehe Moduldocstring).
_EMPLOYMENT_TYPES = {
    "vollzeit", "teilzeit", "praktikum", "werkstudium", "freiberuflich",
    "selbstständig", "ausbildung", "befristet", "unbefristet", "ehrenamt",
    "ehrenamtlich", "saisonarbeit", "full-time", "part-time", "self-employed",
    "freelance", "internship", "trainee", "apprenticeship", "contract",
    "temporary", "volunteer", "seasonal",
}

# Ein "Standort"-Kandidat, der wie eine Kenntnisse-Aufzählung endet (z.B. "... und +3
# Kenntnisse"), ist keine Ortsangabe, sondern verrutschter Skill-Text.
_SKILL_SUFFIX_RE = re.compile(r"und\s*\+?\s*\d+\s*Kenntnis", re.IGNORECASE)
# Dasselbe gilt für einen mit angehängten Abschluss/Studiengang (z.B. bei einem dualen
# Studium/Trainee-Programm steht dort manchmal "Bachelor of Science - X" statt eines
# Orts) - gefunden im Testkorpus (Marcel Merkel/Deutsche Telekom).
_DEGREE_MARKER_RE = re.compile(
    r"\b(Bachelor|Master|Diplom|Studium|Ausbildung|Promotion|B\.?Sc\.?|M\.?Sc\.?|Ph\.?D\.?)\b",
    re.IGNORECASE,
)
# Echte Ortsangaben ("München, Bayern, Deutschland", "Remote", "Metropolregion
# Nürnberg") sind kurz. Freitext-Beschreibungen/Aufzählungen einer Position sind das
# nicht - großzügig bemessen, damit lange, aber reale Städtenamen-Ketten nicht verworfen
# werden, während mehrsätzige Beschreibungen (deutlich länger) zuverlässig ausscheiden.
_LOCATION_MAX_LEN = 80

# Autor-Fund 2026-09-15: kurze, freiformulierte Aufgaben-/Projektbeschreibungen an der
# Standort-Stelle bei EINZELPOSITIONEN (_parse_single_position, ps[3]) - unter der
# 80-Zeichen-Grenze und ohne Kenntnisse-/Abschluss-Marker, daher von den obigen Prüfungen
# nicht erfasst. Fünf echte Fälle im Testkorpus gefunden, alle eindeutig kein Ortsname:
# "research collaboration." (Hana Ibrahim), "Bayesian machine learning for modeling
# motor control." (David Haslacher), "Künstliche Intelligenz (KI) und Agenten" +
# "Mitwirkung an Planung, Organisation und Durchführung von Events." (Dr. David Müller),
# "Working as a journeyman of the joinery trade" (Dr. Jan Werth). Drei zusätzliche,
# gegen den kompletten vorhandenen Korpus (255 echte Standort-Werte, 0 Fehlalarme)
# verifizierte Signale, die eine Ortsangabe nie zeigt, ein Fließtext-Satz aber häufig:
# endet mit Punkt, beginnt mit Kleinbuchstaben, oder mehr als vier Wörter ohne Komma
# (eine echte "Stadt, Region, Land"-Kette hat Kommas, ein einzelner Ortsname wenige Wörter).
_FREITEXT_ENDET_MIT_PUNKT_RE = re.compile(r"\.\s*$")

# Fund 2026-09-15 (Martin Reimann/DDV Mediengruppe, Azubi-Rolle innerhalb einer
# Mehrfach-Gruppe): die o.g. _SKILL_SUFFIX_RE erwartet "und +N Kenntnisse" unmittelbar
# am Ende, greift aber nicht bei "Kenntnisse:Vorname, X und Y, +N Kenntnisse" (das "und"
# steht dort mitten in einer Aufzählung, nicht direkt vor der Zahl). Die Kenntnisse-Zeile
# beginnt aber IMMER mit dem stabilen UI-Label "Kenntnisse:" (siehe dom_utils.py
# _NOISE_LINE_MARKERS, wo dasselbe Label bereits als Rauschen behandelt wird) - das ist
# ein verlässlicheres Signal als das Suffix-Muster.
_KENNTNISSE_PREFIX_RE = re.compile(r"^\s*Kenntnisse\s*:", re.IGNORECASE)


def _looks_like_location(text: str) -> bool:
    """True für echte Ortsangaben, False für Zeiträume, Kenntnisse-Reste oder Fließtext
    (Aufgabenbeschreibung/Aufzählung), die versehentlich an der Standort-Stelle stehen
    könnten (siehe Moduldocstring)."""
    if not text:
        return False
    if looks_like_period(text):
        return False
    if _SKILL_SUFFIX_RE.search(text):
        return False
    if _KENNTNISSE_PREFIX_RE.search(text):
        return False
    if _DEGREE_MARKER_RE.search(text):
        return False
    if len(text) > _LOCATION_MAX_LEN:
        return False
    if _FREITEXT_ENDET_MIT_PUNKT_RE.search(text):
        return False
    if text[0].islower():
        return False
    if "," not in text and len(text.split()) >= 4:
        return False
    return True


def parse_experience_page(html: str) -> list[Experience]:
    soup = get_soup(html)
    # Bevorzugt die benannte Sektion; in schlankeren SSR-Varianten fehlt dieser
    # data-testid, dann über die ganze Seite gehen (auf /details/experience/ sind alle
    # entity-collection-item- Einträge Berufserfahrung).
    section = soup.select_one('[data-testid^="profile_ExperienceDetailsSection_"]')
    scope = section if section is not None else soup

    items = scope.select('div[componentkey^="entity-collection-item-"]')
    experiences: list[Experience] = []
    for item in items:
        position_list = item.find("ul")
        if position_list is not None:
            experiences.extend(_parse_multi_position_group(item, position_list))
        else:
            exp = _parse_single_position(item)
            if exp:
                experiences.append(exp)

    if not items and not experiences:
        _warn_if_unrecognized_markup(soup)
    return experiences


def _warn_if_unrecognized_markup(soup) -> None:
    """0 Einträge über das bekannte SSR-Markup gefunden - meist eine echte leere
    Sektion (Leerzustand-Text im DOM). Steht dort STATTDESSEN das neue SDUI-Markup
    (das die vier anderen Detailseiten schon länger benutzen, siehe dom_utils.py),
    OHNE den Leerzustand-Text, ist unklar, ob wirklich keine Erfahrung vorliegt oder
    ob LinkedIn die Seite umgestellt hat und `parse_experience_page` sie deshalb
    nicht mehr lesen kann (Fund am kreuter92-Dump vom 2026-09-13 - dort zufällig
    beides zugleich: neues Markup UND ein echter Leerzustand). Ohne diese Warnung
    wäre ein „nichts gefunden" nicht von einem stillen Datenverlust zu unterscheiden
    (DQ4) - lieber einmal zu oft warnen."""
    full_text = soup.get_text(" ", strip=True)
    if any(m in full_text for m in _EMPTY_STATE_MARKERS):
        return
    if soup.select_one(_SDUI_EXPERIENCE_SEL) is not None:
        logger.warning(
            "Erfahrungsseite liegt im neuen SDUI-Markup vor (parser_experience.py "
            "kennt bisher nur das alte SSR-Markup) und zeigt keinen Leerzustand-Text "
            "- das Ergebnis [] koennte unvollstaendig statt echt leer sein. Fuer einen "
            "Fix wird ein Debug-Dump eines Profils MIT echter Berufserfahrung in "
            "diesem Markup benoetigt."
        )
    else:
        logger.warning(
            "Keine Erfahrungs-Eintraege im HTML - weder bekanntes Markup noch "
            "Leerzustand-Text gefunden, Markup moeglicherweise geaendert."
        )


def _parse_single_position(item) -> Experience | None:
    # Die 4 <p>-Felder stehen im Detail-Link (.../edit/forms/<id>/, „eigenes Profil"-
    # Ansicht) oder - in der schlankeren Variante ohne Edit-Link - direkt im Eintrag.
    detail_link = item.find("a", href=lambda h: h and _EDIT_LINK in h)
    source = detail_link if detail_link is not None else item
    ps = source.find_all("p")
    if len(ps) < 3:
        return None

    titel = clean_text(ps[0])
    firma_teil = split_by_middot(clean_text(ps[1]))
    zeitraum_teil = split_by_middot(clean_text(ps[2]))
    standort_kandidat = split_by_middot(clean_text(ps[3]))[0] if len(ps) > 3 else ""

    return Experience(
        firma=firma_teil[0] if firma_teil else NOT_AVAILABLE,
        stelle=titel or NOT_AVAILABLE,
        arbeitsverhaeltnis=firma_teil[1] if len(firma_teil) > 1 else NOT_AVAILABLE,
        # ps[3] ist nicht immer der Standort - manche Positionen haben stattdessen (oder
        # zusätzlich) eine frei formulierte Beschreibung an dieser Stelle stehen (siehe
        # Moduldocstring). Nur übernehmen, wenn es wirklich wie eine Ortsangabe aussieht.
        standort=standort_kandidat if _looks_like_location(standort_kandidat) else NOT_AVAILABLE,
        zeitraum=zeitraum_teil[0] if zeitraum_teil else NOT_AVAILABLE,
        dauer=zeitraum_teil[1] if len(zeitraum_teil) > 1 else NOT_AVAILABLE,
    )


def _parse_multi_position_group(item, position_list) -> list[Experience]:
    firma, gruppen_standort = _group_header(item)

    experiences: list[Experience] = []
    for li in position_list.find_all("li", recursive=False):
        ps = li.find_all("p")
        if len(ps) < 2:
            continue
        stelle = clean_text(ps[0]) or NOT_AVAILABLE

        # Arbeitsverhältnis und Zeitraum·Dauer stehen NICHT zuverlässig an festen
        # Indizes - fehlt einer Rolle das Arbeitsverhältnis-<p> (recht häufig, v.a. bei
        # der aktuellen Position), rutscht sonst der Zeitraum in dessen Feld und ein
        # Ort/Freitext in das Zeitraum-Feld (siehe Moduldocstring). Deshalb inhaltlich
        # klassifizieren statt positionsbasiert zu lesen.
        arbeitsverhaeltnis = NOT_AVAILABLE
        zeitraum = NOT_AVAILABLE
        dauer = NOT_AVAILABLE
        standort_kandidat = ""
        for idx, p in enumerate(ps[1:], start=1):
            text = clean_text(p)
            if not text:
                continue
            if looks_like_period(text):
                zeitraum_teil = split_by_middot(text)
                zeitraum = zeitraum_teil[0] if zeitraum_teil else NOT_AVAILABLE
                dauer = zeitraum_teil[1] if len(zeitraum_teil) > 1 else NOT_AVAILABLE
                # Fund 2026-09-15 (Marcel Merkel/TeamBank AG): der Gruppen-Header hat
                # nicht immer einen eigenen Standort-Absatz (siehe _group_header), eine
                # einzelne Rolle - v.a. die aktuellste - aber schon, direkt nach ihrem
                # eigenen Zeitraum. Nur dieser eine, positionsgebundene Kandidat wird
                # geprüft (nicht der ganze Rest von ps[1:]), damit eine anschließende
                # Freitext-Beschreibung nicht versehentlich als Standort durchrutscht.
                if idx + 1 < len(ps):
                    standort_kandidat = clean_text(ps[idx + 1])
                continue
            if arbeitsverhaeltnis == NOT_AVAILABLE and text.strip().lower() in _EMPLOYMENT_TYPES:
                arbeitsverhaeltnis = text
            # alles andere (z.B. eine frei formulierte Aufgabenbeschreibung) wird
            # verworfen, statt es in ein falsches Feld zu zwingen (DQ4).

        standort = (
            standort_kandidat if _looks_like_location(standort_kandidat) else gruppen_standort
        )

        experiences.append(Experience(
            firma=firma,
            stelle=stelle,
            arbeitsverhaeltnis=arbeitsverhaeltnis,
            standort=standort,
            zeitraum=zeitraum,
            dauer=dauer,
        ))
    return experiences


def _group_header(item) -> tuple[str, str]:
    """Firmenname + Standort aus dem Gruppen-Header (erster /company/- bzw. /school/-Link
    mit <p>-Inhalt). Header-<p>: [0] Firma, [1] Gesamtdauer, i.d.R. [2] "Standort ·
    Arbeitsmodell" - dort kann aber auch eine Kenntnisse-Zusammenfassung ("... und +3
    Kenntnisse") oder anderer Text stehen, siehe `_looks_like_location`."""
    for link in item.find_all("a", href=lambda h: h and any(m in h for m in _ORG_LINK_MARKERS)):
        ps = link.find_all("p")
        if not ps:
            continue
        firma = clean_text(ps[0]) or NOT_AVAILABLE
        standort_teil = split_by_middot(clean_text(ps[2])) if len(ps) > 2 else []
        standort_kandidat = standort_teil[0] if standort_teil else ""
        standort = standort_kandidat if _looks_like_location(standort_kandidat) else NOT_AVAILABLE
        return firma, standort
    return NOT_AVAILABLE, NOT_AVAILABLE
