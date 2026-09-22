"""Gemeinsame Hilfsfunktionen für DOM-basiertes Parsing.

LinkedIn liefert Profildaten (Stand: 2026) nicht mehr über eingebettete Voyager-JSON-
Blöcke (Server-Driven UI / React-Flight). Server-gerenderte Sektionen (z. B. Erfahrung)
lassen sich weiterhin als HTML parsen - nur die Klassennamen sind gehasht/instabil.
Deshalb wird hier strukturell geparst: über stabile Attribute wie 'data-sdui-screen',
'data-component-type' und 'data-testid', Reihenfolge der Textzeilen und Trennzeichen,
nicht über CSS-Klassen.
"""
import re

from bs4 import BeautifulSoup, NavigableString

MIDDOT = "·"  # LinkedIn trennt z.B. "Firma · Teilzeit" mit diesem Zeichen

# SDUI-Screen-Namen der Detailseiten (stabil, semantisch - kein Hash). Der Wert steht
# als data-sdui-screen="com.linkedin.sdui.flagshipnav.profile.Profile<Sektion>Details".
SDUI_EDUCATION = "ProfileEducationDetails"
SDUI_SKILLS = "ProfileSkillDetails"
SDUI_LANGUAGES = "ProfileLanguageDetails"
SDUI_CERTIFICATIONS = "ProfileCertificationDetails"

# Leerzustand einer Sektion ("Noch keine Informationen verfügbar …").
_EMPTY_STATE_MARKERS = (
    "Noch keine Informationen",
    "No information available",
)

# Zeilen, an denen ein Kenntnis-Eintrag endet (Button unter jeder Kenntnis).
_ROW_END_MARKERS = ("bestätigen", "bestatigen", "endorse", "confirm skill")

# Zeilen, die innerhalb eines Eintrags nur Beiwerk sind und verworfen werden.
_NOISE_LINE_MARKERS = (
    "Kenntnisse:",
    "berufliche Erfahrung",
    "berufliche Erfahrungen",
    "Kenntnisse bestätigen",
    # Sektionsüberschriften der Detailseiten (stabile UI-Strings, kein Hash)
    "Bescheinigungen und Zertifikate",
    "Lizenzen und Zertifikate",
    "Licenses & certifications",
    "Licenses and certifications",
    # "Nachweis anzeigen"-Button unter einem Zertifikat
    "Nachweis anzeigen",
    "Show credential",
)

# Label, ab dem die verknüpften Kenntnisse eines Zertifikats folgen - dort schneiden
# wir den Eintrag ab (die Skill-Namen gehören nicht zum Zertifikat selbst).
_LINKED_SKILLS_LABELS = ("kenntnisse", "skills")

# Die Sektions-Überschrift (z.B. "Ausbildung") steht bei GENAU EINEM Eintrag (kein
# <hr>-Trenner, siehe _single_entry) mit im erfassten Text, weil dort keine <hr>-
# Container-Grenze existiert, die sie sonst aussortiert (siehe _split_by_hr). Nur als
# EXAKTER Treffer entfernen, nicht als Teilstring wie _NOISE_LINE_MARKERS - sonst würde
# z.B. eine echte Fachrichtung wie "Ausbildung, IT-Systemelektroniker" fälschlich mit
# verworfen.
_SECTION_HEADINGS = {
    SDUI_EDUCATION: ("ausbildung", "education"),
    SDUI_LANGUAGES: ("sprachen", "languages"),
    SDUI_CERTIFICATIONS: (
        "zertifikate", "lizenzen und zertifikate", "bescheinigungen und zertifikate",
        "licenses & certifications", "licenses and certifications", "certifications",
    ),
    SDUI_SKILLS: ("kenntnisse", "skills"),
}

_YEAR_RE = re.compile(r"(?:19|20)\d{2}")


def get_soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def split_by_middot(text: str) -> list[str]:
    """Teilt z.B. 'Technische Universität Chemnitz · Teilzeit' in ['...', 'Teilzeit'].
    Gibt bei fehlendem Trennzeichen eine Liste mit nur dem Originaltext zurück."""
    if not text:
        return []
    parts = [p.strip() for p in text.split(MIDDOT)]
    return [p for p in parts if p]


def clean_text(tag) -> str:
    return tag.get_text(strip=True) if tag else ""


def looks_like_period(text: str) -> bool:
    """True für Zeilen wie 'Apr. 2023–Okt. 2026' oder '2018–2021'."""
    return bool(text and _YEAR_RE.search(text))


# --------------------------------------------------------------------------
#  SDUI-Detailseiten (Ausbildung / Kenntnisse / Sprachen / Zertifikate)
# --------------------------------------------------------------------------

def _sdui_section(soup: BeautifulSoup, screen_suffix: str):
    """Die LazyColumn der gewünschten Detailseite.

    Anker in dieser Reihenfolge (vom Speziellsten zum Allgemeinsten):
      1. `[data-sdui-screen$="Profile<Sektion>Details"]` → darin die LazyColumn
      2. eine LazyColumn, deren `componentkey` auf `<Sektion>DetailsSection` endet
      3. die einzige/erste LazyColumn der Seite
    Punkt 3 trägt, weil ein Detail-Dump nur die eine Sektion enthält.
    """
    host = soup.select_one(f'[data-sdui-screen$="{screen_suffix}"]')
    if host is not None:
        lc = host.select_one('[data-component-type="LazyColumn"]')
        if lc is not None:
            return lc
        return host

    section_name = screen_suffix.replace("Profile", "").replace("Details", "")
    for lc in soup.select('[data-component-type="LazyColumn"]'):
        if section_name and section_name in (lc.get("componentkey") or ""):
            return lc

    return soup.select_one('[data-component-type="LazyColumn"]')


def _split_by_hr(section, screen_suffix: str | None = None) -> list[list[str]]:
    """Einträge = Textstücke zwischen `<hr>`-Trennern innerhalb der Sektion, in
    Dokumentreihenfolge - unabhängig davon, wie tief ein `<hr>` verschachtelt ist.

    Bis v0.7.17 wurde dafür angenommen, dass alle `<hr>` direkte Geschwister der
    Eintrags-`<div>`s unter EINEM gemeinsamen Elternknoten sind (`<div>…</div><hr>
    <div>…</div>…`) - das gilt für Ausbildung/Sprachen/Zertifikate. Bei den
    Kenntnissen FREMDER Profile steckt jedes `<hr>` stattdessen allein in einem
    eigenen Wrapper-`<div>`, das ein GESCHWISTER der Eintrags-`<div>`s ist statt
    dessen Elternknoten (Autor-Fund 2026-09-14, Debug-Dump `alisia-deichhardt`: von
    20 echten Kenntnissen wurde nur 1 erkannt, weil die alte, positionsstarre Version
    das nicht fand und auf den `_single_entry`-Rückfall zurückfiel, der die GANZE
    Sektion als einen Eintrag behandelt). Läuft daher über ALLE Nachfahren der
    Sektion in Dokumentreihenfolge und schneidet bei jedem `<hr>`-Tag, egal auf
    welcher Verschachtelungstiefe er sitzt - das deckt beide Strukturvarianten ab.

    Wie schon in `_single_entry`: die Sektions-Überschrift (z. B. „Ausbildung") steht
    VOR dem ersten `<hr>` und landet dadurch in der ersten Gruppe mit - wird hier
    genauso über `_SECTION_HEADINGS` (exakter Treffer) wieder entfernt.
    """
    if not section.find_all("hr"):
        return []

    groups: list[list[str]] = []
    current: list[str] = []
    for node in section.descendants:
        if getattr(node, "name", None) == "hr":
            if current:
                groups.append(current)
                current = []
        elif isinstance(node, NavigableString):
            parent_name = getattr(node.parent, "name", None)
            if parent_name in ("script", "style"):
                continue
            chunk = node.strip()
            if chunk and chunk not in current:
                current.append(chunk)
    if current:
        groups.append(current)

    headings = _SECTION_HEADINGS.get(screen_suffix, ())
    if groups and headings:
        while groups[0] and groups[0][0].rstrip(":").strip().lower() in headings:
            groups[0] = groups[0][1:]

    entries: list[list[str]] = []
    for group in groups:
        lines = _drop_noise(group)
        if lines:
            entries.append(lines)
    return entries


def _split_by_row_button(section) -> list[list[str]]:
    """Einträge, die jeweils mit einem Button („Kenntnisse bestätigen") enden.

    Das ist die Struktur der Kenntnisse-Seite: pro Kenntnis eine Namenszeile, eine
    Kontextzeile („… bei <Firma>") und darunter der Bestätigen-Button.
    """
    lines = [t.strip() for t in section.stripped_strings if t.strip()]
    entries: list[list[str]] = []
    current: list[str] = []
    saw_marker = False
    for line in lines:
        if any(m in line.lower() for m in _ROW_END_MARKERS):
            saw_marker = True
            if current:
                entries.append(_drop_noise(current))
                current = []
            continue
        current.append(line)
    # Ohne einen einzigen Button-Marker ist das nicht die Kenntnisse-Struktur - dann
    # lieber `[]` zurückgeben, damit der Aufrufer auf den Alt-Weg zurückfallen kann,
    # statt den ganzen Textblock als einen (falschen) Eintrag auszugeben.
    if not saw_marker:
        return []
    if current and not entries:
        entries.append(_drop_noise(current))
    return [e for e in entries if e]


def _drop_noise(lines: list[str]) -> list[str]:
    return [ln for ln in lines if not any(m in ln for m in _NOISE_LINE_MARKERS)]


def iter_sdui_entries(html: str, screen_suffix: str) -> list[list[str]]:
    """Textzeilen je Eintrag einer SDUI-Detailseite.

    `screen_suffix` ist einer der `SDUI_*`-Namen oben. Rückgabe: Liste von Einträgen,
    jeder Eintrag eine Liste seiner sichtbaren Textzeilen in DOM-Reihenfolge. `[]`,
    wenn die Sektion fehlt, leer ist oder client-seitig (noch) nicht geladen wurde.
    """
    soup = get_soup(html)
    section = _sdui_section(soup, screen_suffix)
    if section is None:
        return []

    # Enthält die Sektion noch `entity-collection-item-`, ist es das frühere Markup -
    # dann hier aussteigen, damit der Aufrufer `iter_detail_entries` nutzt.
    if section.select_one('[componentkey^="entity-collection-item-"]'):
        return []

    full_text = section.get_text(" ", strip=True)
    if any(m in full_text for m in _EMPTY_STATE_MARKERS):
        return []

    entries = _split_by_hr(section, screen_suffix)
    if entries:
        return entries
    entries = _split_by_row_button(section)
    if entries:
        return entries
    return _single_entry(section, screen_suffix)


def _single_entry(section, screen_suffix: str | None = None) -> list[list[str]]:
    """Rückfall für eine Sektion mit genau einem Eintrag: kein `<hr>` (der kommt erst
    ab dem zweiten Eintrag) und kein Zeilen-Button. Trifft z. B. auf ein einzelnes
    Zertifikat oder eine einzelne Ausbildung zu. Die ganze Sektion wird zu einem
    Eintrag; die Sektions-Überschrift (z.B. "Ausbildung") wird zuerst entfernt (siehe
    _SECTION_HEADINGS), danach alles ab dem „Kenntnisse:"-Label (verknüpfte Skills).
    """
    raw = [t.strip() for t in section.stripped_strings if t.strip()]
    headings = _SECTION_HEADINGS.get(screen_suffix, ())
    while raw and raw[0].rstrip(":").strip().lower() in headings:
        raw = raw[1:]
    for cut, line in enumerate(raw):
        if line.rstrip(":").strip().lower() in _LINKED_SKILLS_LABELS:
            raw = raw[:cut]
            break
    lines: list[str] = []
    for line in _drop_noise(raw):
        if line not in lines:
            lines.append(line)
    return [lines] if len(lines) >= 2 else []


def iter_detail_entries(html: str, section_testid_prefix: str) -> list[list[str]]:
    """Alt-Weg für Dumps im früheren SDUI-Markup (`entity-collection-item-`).

    Wird von den Parsern nur noch als Rückfall benutzt; der reguläre Weg ist
    `iter_sdui_entries`. Gibt `[]` zurück, wenn die Sektion oder die Einträge fehlen.
    """
    soup = get_soup(html)
    section = soup.select_one(f'[data-testid^="{section_testid_prefix}"]')
    if section is None:
        return []

    entries: list[list[str]] = []
    for item in section.select('div[componentkey^="entity-collection-item-"]'):
        detail_link = item.find("a", href=lambda h: h and "/edit/forms/" in h)
        lines: list[str] = []
        if detail_link is not None:
            lines = [ln for ln in (clean_text(p) for p in detail_link.find_all("p")) if ln]
        if not lines:
            lines = [ln for ln in (clean_text(p) for p in item.find_all("p")) if ln]
        if lines:
            entries.append(lines)
    return entries
