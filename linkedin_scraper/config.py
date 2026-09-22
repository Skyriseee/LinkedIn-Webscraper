"""Zentrale Konfiguration: Pfade, URLs, Delays, CSV-Spalten."""
import sys
from datetime import date
from pathlib import Path

# --- Projektpfade ---
# Seit v0.7.7 wohnt die "kanonische" data/ (insbesondere das Browserprofil mit der
# aktiven Anmeldung) BEIM exe-Ausgabeordner, nicht bei linkedin_scraper/ - Absicht:
# `LinkedInScraper/` (exe + data/ + Session) ist eine in sich geschlossene, portable
# Einheit, die sich im Notfall komplett auf ein anderes Gerät kopieren lässt. Der
# Quellcode-Betrieb zeigt auf DIESELBE Stelle statt eine zweite Kopie zu führen - sonst
# gäbe es wieder zwei Geräte mit potenziell derselben Session.
#
# Layout: <Projektstamm>/LinkedInScraper/app/LinkedInScraper.exe (von PyInstaller
# verwaltet, siehe build/) + <Projektstamm>/LinkedInScraper/data/ (NICHT von
# PyInstaller verwaltet - ein Rebuild räumt den "app"-Unterordner leer, "data" bleibt
# unberührt, siehe build/LinkedInScraper.spec). sys.executable liegt also zwei Ebenen
# unter LinkedInScraper/, daher .parent.parent.
if getattr(sys, "frozen", False):
    _APP_ROOT = Path(sys.executable).resolve().parent.parent
else:
    _PROJECT_ROOT = Path(__file__).resolve().parent.parent
    _APP_ROOT = _PROJECT_ROOT / "LinkedInScraper"
DATA_DIR = _APP_ROOT / "data"
# NEU v0.7.22: alle Eingabelisten liegen in einem eigenen Ordner statt als einzelne,
# fest verdrahtete Datei - main.py lässt den Bediener bei jedem Lauf (Scraping UND
# Debug-Dump) aus den dort liegenden *.csv nummeriert auswählen (Autor-Wunsch
# 2026-09-14), statt immer stur `input_profiles.csv` zu lesen. `INPUT_CSV_PATH` bleibt
# als dokumentierter Standardname/Fallback bestehen (z. B. für README-Beispiele).
INPUT_DIR = DATA_DIR / "input"
INPUT_CSV_PATH = INPUT_DIR / "input_profiles.csv"

# Eine CSV je Lauf: output_results_<TTMMJJJJ>.csv (siehe io_handlers/csv_writer.py) -
# kein fortlaufendes Anhängen an eine feste Datei mehr (Stand v0.7.11). Seit v0.7.13 in
# einem eigenen Ordner, analog zu OUTPUT_JSON_DIR.
OUTPUT_CSV_DIR = DATA_DIR / "output_csv"
# Je Profil eine JSON-Datei <Vorname>_<Nachname>_<TTMMJJJJ>.json (siehe io_handlers/json_writer.py)
OUTPUT_JSON_DIR = DATA_DIR / "output_json"
# NEU v0.7.24: eigener Ordner statt einer einzelnen Datei direkt in data/ (Autor-Wunsch
# 2026-09-14), analog zu INPUT_DIR/OUTPUT_CSV_DIR/OUTPUT_JSON_DIR/DEBUG_DUMP_DIR.
LOG_DIR = DATA_DIR / "logs"


def log_file_path(run_date: date | None = None) -> Path:
    """`scraper_<TTMMJJJJ>.log` - ein File je Tag, analog zu `output_results_<TTMMJJJJ>.
    csv`/`<Name>_<TTMMJJJJ>.json` (siehe io_handlers/csv_writer.py, json_writer.py).
    NEU v0.7.25 (Autor-Wunsch 2026-09-14): vorher eine einzige, über die gesamte
    Projektlaufzeit fortlaufend wachsende `scraper.log`. `logging.FileHandler` und
    `logging_setup.setup_console_capture()` öffnen diese Datei im Anhänge-Modus
    ("a") - mehrere Läufe am selben Tag landen also in derselben Datei, ein neuer
    Tag bekommt automatisch eine frische."""
    return LOG_DIR / f"scraper_{(run_date or date.today()).strftime('%d%m%Y')}.log"
# Debug-Dumps landen hier als debug_dump_<seite>_<slug>.html (siehe main.py:run_debug_dump)
DEBUG_DUMP_DIR = DATA_DIR / "debug_dumps"


def ensure_data_dirs() -> None:
    """Legt `data/` und alle bekannten Unterordner an, falls sie fehlen.

    `data/` liegt außerhalb des Quellcodes (siehe oben) und wird deshalb NICHT
    versioniert - bei einem frischen Checkout existiert der Ordner also nicht.
    Die meisten Unterordner legen sich beim ersten Schreibzugriff ohnehin selbst
    an (`mkdir(parents=True, exist_ok=True)` u. a. in csv_writer.py,
    json_writer.py, logging_setup.py), aber `INPUT_DIR` wird nur gelesen, nie
    beschrieben - ohne diesen Aufruf müsste ihn ein Bediener nach dem Klonen
    erst von Hand anlegen, bevor er dort eine CSV ablegen kann. Wird deshalb
    einmal ganz am Anfang von `main()` aufgerufen."""
    for ordner in (INPUT_DIR, OUTPUT_CSV_DIR, OUTPUT_JSON_DIR, LOG_DIR, DEBUG_DUMP_DIR):
        ordner.mkdir(parents=True, exist_ok=True)

# --- LinkedIn URLs ({slug} = Profil-Kennung aus der Profil-URL, z.B. "max-mustermann-123abc") ---
BASE_URL = "https://www.linkedin.com"
URL_PROFILE = BASE_URL + "/in/{slug}/"
URL_CONTACT_INFO = BASE_URL + "/in/{slug}/overlay/contact-info/"
URL_EXPERIENCE = BASE_URL + "/in/{slug}/details/experience/"
URL_EDUCATION = BASE_URL + "/in/{slug}/details/education/"
URL_SKILLS = BASE_URL + "/in/{slug}/details/skills/"
URL_LANGUAGES = BASE_URL + "/in/{slug}/details/languages/"
URL_CERTIFICATIONS = BASE_URL + "/in/{slug}/details/certifications/"

# Testseite zur Session-Validierung (nur mit gültigem Login ohne Redirect erreichbar)
URL_SESSION_CHECK = BASE_URL + "/feed/"

# --- Rate Limiting / menschenähnliche Taktung ---
# Grunddelay zwischen zwei einzelnen Requests (Lesezeit auf einer Seite).
DELAY_MIN_SECONDS = 6.0
DELAY_MAX_SECONDS = 14.0
# Mit dieser Wahrscheinlichkeit kommt ein längerer "kurz abgelenkt"-Aufschlag dazu.
DISTRACTION_PROBABILITY = 0.18
DISTRACTION_EXTRA_MIN_SECONDS = 4.0
DISTRACTION_EXTRA_MAX_SECONDS = 20.0
# Pause zwischen zwei Profilen (ein Mensch klickt nicht sofort das nächste Profil an).
PROFILE_PAUSE_MIN_SECONDS = 25.0
PROFILE_PAUSE_MAX_SECONDS = 75.0
# Nach je N Profilen eine längere Pause (Kaffee/Meeting).
LONG_PAUSE_EVERY_PROFILES = 6
LONG_PAUSE_MIN_SECONDS = 180.0
LONG_PAUSE_MAX_SECONDS = 420.0
# Nach je M Profilen eine NOCH längere Pause (zusätzlich zur "alle N Profile"-Pause
# oben, hat Vorrang wenn beide zusammenfallen). Ersetzt seit v0.7.13 die frühere harte
# Obergrenze MAX_PROFILES_PER_RUN=25, die einen Lauf nach 25 Profilen einfach
# abgeschnitten hat - der Autor wollte stattdessen größere Korpora in einem Lauf
# durchlaufen können, mit einer langen Pause statt eines harten Endes.
EXTRA_LONG_PAUSE_EVERY_PROFILES = 25
EXTRA_LONG_PAUSE_MIN_SECONDS = 300.0
EXTRA_LONG_PAUSE_MAX_SECONDS = 600.0

# NACHTRAG 2026-09-14: ein testweise eingeführter FAST_TEST_MODE-Schalter (v0.7.21,
# verkürzte diese Delays für Regressionsläufe während der Entwicklung) wurde in
# v0.7.23 wieder VOLLSTÄNDIG entfernt - der Live-Testlauf hat bestätigt, dass schon
# die entschärften v0.7.22-Werte (Request 2-4s statt 6-14s) beim 34-Profile-Testkorpus
# durchgehend zu LinkedIns generischer Fehlerseite statt echtem Inhalt führten
# (ERROR_BOUNDARY_MARKER in fetch/fetcher.py). Der Schalter brachte damit in der
# Praxis keinen nutzbaren Zeitgewinn, nur unbrauchbare Testläufe. Die Werte oben gelten jetzt
# unterschiedslos für jeden Lauf, auch gegen den kleinen Testkorpus
# (`input_profiles_test34.csv`).

MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 5.0  # Sekunden, verdoppelt sich je Retry-Versuch (fixe Staffel)

# Stürzt der Browser mitten in einem Profil ab (main.py:run_scraping erkennt das über
# BrowserFetcher.crashed), wird der Browser neu gestartet und GENAU DIESES Profil von
# vorn versucht - so oft wie hier angegeben, bevor es endgültig übersprungen wird. Kein
# Resume über mehrere Läufe hinweg (das würde einen Änderungsabgleich mit bereits
# gespeicherten Daten brauchen) - nur ein Schutz
# gegen einen Absturz mitten im laufenden Lauf, ohne den ganzen Lauf neu zu starten und
# ohne ein Profil mit unvollständigen (halb abgestürzten) Daten zu schreiben.
PROFILE_RETRY_ATTEMPTS = 1

# --- HTTP ---
# curl_cffi bildet den TLS-/HTTP-2-Fingerprint eines echten Chrome nach. Fest auf eine
# REAL existierende Chrome-Version gepinnt (nicht "chrome" = jeweils Neuestes, driftet
# und kann eine synthetische Zukunftsversion sein). curl_cffi 0.16 liefert für alle
# Chrome-Targets eine macOS-UA - der Fingerprint ist also in sich konsistent "Chrome auf
# macOS". USER_AGENT/SEC_CH_UA unten sind nur der requests-Fallback und ziehen mit.
# Referer-/Sec-Fetch-Kette bei den Unterseiten (erst Profilseite, dann "Klick" mit
# Referer). Nachtest 2026-09-08: Dump mit/ohne Referer ist strukturgleich - die Kette
# ändert am gelieferten HTML nichts. Default trotzdem aus: ein kalter Aufruf ("URL in
# die Adressleiste getippt") ist die einfachere, gut nachvollziehbare Variante.
SEND_REFERER_CHAIN = False

# Erzwingt die HTTP-Engine: None = automatisch (curl_cffi, wenn installiert - der
# empfohlene Normalbetrieb), "requests" = bewusst der alte Weg (nur zum Vergleich/
# Isolieren; ohne installiertes brotli/zstandard NICHT für echte Dumps geeignet),
# "curl_cffi" = Pflicht. Für normale Läufe auf None lassen.
FORCE_HTTP_ENGINE = None

# True = User-Agent, sec-ch-ua und das curl_cffi-Impersonation-Ziel werden zur Laufzeit
# aus der WIRKLICH installierten Chrome-Version und dem laufenden Betriebssystem
# abgeleitet (fingerprint.py). Damit geben HTTP-Weg und Browser-Weg dieselbe Identität
# an - beide sprechen ja mit demselben Session-Cookie mit LinkedIn - und die Konfig
# bleibt auf einer anderen Maschine gültig (NFA5).
# False = die festen Werte unten benutzen (nur für Vergleichsmessungen).
HTTP_IDENTITY_AUTO = True

# Rückfallwerte, falls die Erkennung scheitert (kein Chrome gefunden). Sie beschreiben
# bewusst macOS/Chrome 131, weil curl_cffi für alle Chrome-Targets macOS-UAs liefert -
# in dem Fall ist die Identität wenigstens in sich stimmig.
HTTP_IMPERSONATE = "chrome131"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
SEC_CH_UA = '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"'
# WICHTIG: USER_AGENT/SEC_CH_UA gelten NUR für den HTTP-Weg (curl_cffi-Fallback bzw.
# requests). Der Browser darf sie NICHT benutzen - curl_cffi liefert für alle
# Chrome-Targets macOS-UAs, während der Browser real auf Windows läuft. Genau diese
# Vermischung war der Fehler bis v0.3.2. Der Browser hat
# seine eigene Einstellung: BROWSER_USER_AGENT.
SEC_CH_UA_PLATFORM = '"macOS"'
ACCEPT_LANGUAGE = "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7"
REQUEST_TIMEOUT_SECONDS = 20

# --- Voyager-API: VERWORFENER WEG (Stand 2026-09-08) ---------------------------
#     Idee war, die sechs client-seitig nachgeladenen Felder (E-Mail, Geburtstag,
#     Ausbildung, Kenntnisse, Sprachen, Zertifikate) per XHR aus derselben warmen
#     Session zu holen. Ergebnis des Live-Tests: die klassischen REST-Endpunkte
#     antworten mit **HTTP 410 Gone** - LinkedIn hat sie abgeschaltet.
#     Der verbleibende GraphQL-Weg braucht eine `queryId`, die mit jedem LinkedIn-
#     Web-Release rotiert und aus einer individuellen Session mitgeschnitten werden
#     müsste. Das widerspricht der geforderten Reproduzierbarkeit (NFA5), deshalb
#     bewusst NICHT weiterverfolgt. Code bleibt als dokumentierter Negativbefund
#     liegen (fetch/voyager_client.py, fetch/voyager_parser.py).
#     Zum Reaktivieren nur für Vergleichszwecke: Flag auf True setzen.
USE_VOYAGER_FOR_LAZY = False
VOYAGER_API_BASE = BASE_URL + "/voyager/api"
# {pid} = public identifier aus der Profil-URL (der Teil hinter /in/).
VOYAGER_PROFILE_VIEW = VOYAGER_API_BASE + "/identity/profiles/{pid}/profileView"
VOYAGER_CONTACT_INFO = VOYAGER_API_BASE + "/identity/profiles/{pid}/profileContactInfo"
LI_CLIENT_VERSION = "1.13.36389"
LI_LANG = "de_DE"
LI_TIMEZONE = "Europe/Berlin"

# --- Browser-Fetcher (Playwright/Chromium): der Weg für alle client-seitig
#     gerenderten Felder. Ausbildung/Kenntnisse/Sprachen/Zertifikate kommen als leere
#     LazyColumn, das Kontakt-Overlay (E-Mail/Geburtstag) wird ebenfalls erst im
#     Browser gerendert - beides braucht echtes JS. Profilkopf und Berufserfahrung
#     bleiben beim schnelleren HTML-Weg (verifiziert), damit der Browser so wenige
#     Seiten wie möglich laden muss. Braucht `playwright` + einmalig
#     `playwright install chromium`. Bei False bleiben diese Felder leer.
# Stand v0.4.0: Der Browser-Weg ist wieder aktiv. Die Identitäts-Widersprüche, die
# am 07.09. (headless) und 08.09. (headful) zum Logout geführt haben, sind behoben -
# echtes Chrome statt Bundled-Chromium, eigene statt geerbter UA, kein
# navigator.webdriver, persistentes Tool-Profil.
# Selbsttest ohne LinkedIn-Zugriff: Menüpunkt 4 (Fingerprint prüfen).
USE_BROWSER_FOR_LAZY = True
# Kontakt-Overlay über den Browser holen statt über HTTP (HTTP liefert dort nur die
# Profil-Hülle). Greift nur, wenn USE_BROWSER_FOR_LAZY aktiv ist.
USE_BROWSER_FOR_CONTACT = True
# headless=True hat am 2026-09-07 die Bot-Erkennung ausgelöst (Logout + Mail-2FA).
# Bitte auf False lassen.
BROWSER_HEADLESS = False
BROWSER_NAV_TIMEOUT_MS = 30000
# Obergrenze, wie lange nach dem Scrollen auf den Wartemarker der LazyColumn gewartet
# wird. Kein fester Wert - Inhalt, der hydratisiert, ist danach schnell da; die volle
# Zeit greift nur bei wirklich leeren Sektionen. Ab v0.7.4 von 6000 auf 4000 gesenkt.
BROWSER_ENTRY_WAIT_MS = 4000
# Kontakt-Overlay: wie lange nach dem Klick auf sichtbaren Dialog UND Inhalt gewartet
# wird. Das Overlay lädt seinen Inhalt erst nach dem Öffnen nach.
BROWSER_DIALOG_WAIT_MS = 8000
BROWSER_SETTLE_MS = 800

# --- Browser-Identität: muss in sich stimmig sein -----------------------------
# None = die ECHTE User-Agent des gestarteten Browsers verwenden (empfohlen). Nur auf
# einen String setzen, wenn man bewusst etwas anderes vorgeben will - dann aber darauf
# achten, dass Betriebssystem UND Hauptversion zur real laufenden Engine passen.
BROWSER_USER_AGENT = None
# "chrome" = echtes installiertes Google Chrome statt des gebündelten Chromium.
# Wichtig, weil das gebündelte Chromium (Playwright 1.36 -> Chromium 115) veraltet ist
# und andere Brands/Codecs/Plugins hat. None = gebündeltes Chromium.
BROWSER_CHANNEL = "chrome"
# Persistentes, TOOL-eigenes Profilverzeichnis (nicht das Chrome-Profil des Bedieners).
# Damit wachsen localStorage/IndexedDB/Cache/Service-Worker ueber Läufe hinweg, statt
# bei jedem Start ein fabrikneues Gerät zu simulieren.
BROWSER_PERSISTENT = True
BROWSER_USER_DATA_DIR = DATA_DIR / "browser_profile"
# Cookies aus der Extension in den Browser injizieren. Auf False setzen, wenn man sich
# im Tool-Profil EINMAL manuell angemeldet hat - dann ist die Session nativ in diesem
# Profil entstanden und es gibt gar keine Injektions-Anomalie mehr (stärkste Variante).
# "auto" = injizieren, wenn im Tool-Profil noch keine LinkedIn-Anmeldung liegt, sonst
# die vorhandene (nativ dort entstandene) Session benutzen. Das ist der empfohlene
# Wert: nach einer einmaligen manuellen Anmeldung (Menüpunkt 5) schaltet sich die
# Injektion von selbst ab, ohne dass hier etwas umgestellt werden muss.
# True = immer injizieren, False = nie.
BROWSER_INJECT_COOKIES = "auto"

# Woher die Session kommt:
#   "browser_profile" = ausschließlich das Tool-Browserprofil (Menüpunkt 1 zum
#                       Anmelden). Empfohlen und Standard.
#   "extension"       = ausschließlich die Browser-Extension. VERALTET - der Weg hat in
#                       der Praxis Logouts ausgelöst (Cookie-Injektion in einen fremden
#                       Browserkontext). Nicht mehr im Menü.
#   "auto"            = erst Profil, sonst Extension. Nur noch als Notausgang.
# Hintergrund: eine im Tool-Profil manuell entstandene Anmeldung ist von LinkedIn als
# Gerät bekannt und überlebt Neustarts (die Cookies haben ein Ablaufdatum). Über die
# Extension injizierte Cookies sind dagegen reine SITZUNGS-Cookies - sie verschwinden
# beim Schließen des Browsers und müssen jedes Mal neu gesetzt werden.
SESSION_SOURCE = "browser_profile"
# None = die Vorgabe des Systems bzw. des Browserfensters übernehmen. Das ist die
# portable Einstellung: ein fest gesetztes "Europe/Berlin" auf einem Rechner in einer
# anderen Zeitzone erzeugt einen Widerspruch zur IP-Geolokalisierung, und ein fest
# gesetztes Viewport kann größer sein als der Bildschirm des Zielrechners.
BROWSER_LOCALE = "de-DE"
BROWSER_TIMEZONE = None
BROWSER_VIEWPORT = None
BROWSER_DEVICE_SCALE_FACTOR = None

# --- Aufwärmen ("Altern") der Browser-Sitzung ---------------------------------
# Vor dem ersten Profilabruf den Feed laden und kurz darin verweilen, damit die Sitzung
# nicht mit einem Detailseiten-Aufruf beginnt. Hilft nur sekundär - die Geräte-
# Kohärenz oben ist der wichtigere Hebel.
BROWSER_WARMUP = True
BROWSER_WARMUP_DWELL_MIN_MS = 3000
BROWSER_WARMUP_DWELL_MAX_MS = 9000

# --- Scrollen: menschenähnlich statt exakt gleichförmig -----------------------
BROWSER_SCROLL_STEPS_MIN = 6
BROWSER_SCROLL_STEPS_MAX = 12
# Obergrenze NUR, wenn ein Wartemarker angegeben ist (Detailseite) - lange Listen wie
# Kenntnisse laden weitere Einträge erst beim WEITEREN Scrollen nach (LazyColumn-
# Pagination); das feste 6-12-Budget oben reicht dafür nicht (Autor-Fund 2026-09-14:
# 48 echte Kenntnisse, aber nur die ersten ~30 wurden erfasst, weil bisher schon beim
# ERSTEN sichtbaren Eintrag abgebrochen wurde). Ohne Ziel (Aufwärmen auf dem Feed)
# bleibt es beim kleineren Budget oben.
BROWSER_SCROLL_STEPS_MAX_WITH_TARGET = 40
BROWSER_SCROLL_PX_MIN = 600
BROWSER_SCROLL_PX_MAX = 1400
BROWSER_SCROLL_PAUSE_MIN_MS = 250
BROWSER_SCROLL_PAUSE_MAX_MS = 1200
# Wahrscheinlichkeit, zwischendurch ein Stück zurückzuscrollen (wie beim Überfliegen).
BROWSER_SCROLL_BACK_PROBABILITY = 0.25
# Autor-Fund 2026-09-15 (Vaibhav Grover, Referenzabgleich nach dem Fix oben): selbst mit
# vollem Schrittbudget (40) wurden nur 50 von 98 Kenntnissen erfasst, und zwar wieder als
# sauberes Präfix - die Stabilitätsprüfung (2 Scroll-Runden ohne Zuwachs, s.u.) brach
# also VORZEITIG ab, nicht das Budget war zu knapp. LinkedIns LazyColumn lädt lange
# Listen in Batches nach; dauert ein Batch länger als die normale Scroll-Pause
# (BROWSER_SCROLL_PAUSE_*_MS, max. 1,2s), sieht ein Zwischenstand 2 Runden lang
# fälschlich "stabil" aus, obwohl der nächste Batch nur noch nicht gerendert ist.
# Deshalb wird ein Kandidat für "stabil" jetzt einmal mit dieser deutlich längeren Wartezeit
# gegengeprüft (angelehnt an BROWSER_ENTRY_WAIT_MS, das an anderer Stelle als Richtwert
# dafür dient, wie lange LinkedIn zum Nachladen braucht), bevor er wirklich zählt.
BROWSER_SCROLL_STABILITY_CONFIRM_MS = 3000

# --- Performance / lokale Rendering-Last (ändert NICHT die Politeness-Delays) --
# Diese Schalter senken nur die Arbeit, die lokal auf dem Rechner anfällt (Download,
# RAM, Rendering). Die Zugriffsrate gegenüber LinkedIn bleibt unverändert unter dem
# NFA2-Grenzwert.
#
# Assets (Bilder, Media, Web-Fonts) im Browser-Weg gar nicht erst laden - die Parser
# brauchen nur Text/DOM. Dokument, Skripte, Stylesheets und XHR bleiben unberührt.
# Spürbar v. a. auf schwacher Hardware und langsamer Leitung.
BROWSER_BLOCK_ASSETS = True
# Alle N verarbeiteten Profile den Browser-Kontext neu aufsetzen, damit der
# Speicherverbrauch über lange Läufe nicht anwächst. Die Anmeldung im persistenten
# Tool-Profil überlebt das. 0 = nie neu aufsetzen.
BROWSER_RECYCLE_EVERY_PROFILES = 25

# --- Native-Messaging-Bridge (Extension <-> Python, siehe session/) ---
NATIVE_HOST_NAME = "com.reimann.linkedin_research_scraper"
NATIVE_BRIDGE_HOST = "127.0.0.1"
NATIVE_BRIDGE_PORT = 17872
SESSION_TRANSPORT_TIMEOUT_SECONDS = 120

REQUIRED_COOKIES = ["li_at"]
# Nur informativ. Die Extension schickt inzwischen ALLE .linkedin.com-Cookies (popup.js),
# damit die Session für LinkedIn wie ein normaler Browser aussieht (u. a. lidc, li_rm,
# li_gc, liap, lang, bcookie, bscookie, JSESSIONID, UserMatchHistory, AnalyticsSyncHistory).
OPTIONAL_COOKIES = ["JSESSIONID", "bcookie", "bscookie", "lidc", "li_rm", "li_gc", "liap", "lang"]

# --- CSV-Ausgabe: Spaltenreihenfolge exakt gemäß ExportVorlage.csv ---
CSV_COLUMNS = [
    "Vorname", "Nachname", "Titel", "Ort", "Bundesland", "Land", "E-Mail", "Geburtstag",
    "Erfahrung - Firma", "Erfahrung - Stelle", "Erfahrung - Arbeitsverhältnis",
    "Erfahrung - Standort", "Erfahrung - Zeitraum", "Erfahrung - Dauer",
    "Ausbildung - Name", "Ausbildung - Fachrichtung", "Ausbildung - Zeitraum",
    "Kenntnisse",
    "Zertifikat - Name", "Zertifikat - Aussteller", "Zertifikat - Datum",
    "Sprachen", "Sprachenniveau",
]

NOT_AVAILABLE = "N/A"
# Für ein Profil, dessen URL auf LinkedIns 404-Seite umleitet (Profil existiert nicht
# mehr/wurde gelöscht) - bewusst ein anderer Marker als NOT_AVAILABLE, damit sich "Profil
# gibt es nicht mehr" von "Profil existiert, Felder aber aus Privatsphäre-Gründen leer"
# unterscheiden lässt (Autor-Wunsch 2026-09-14). Siehe fetch/fetcher.py
# ProfileNotFoundError, main.py:_not_found_profile.
PROFILE_NOT_FOUND = "404"
