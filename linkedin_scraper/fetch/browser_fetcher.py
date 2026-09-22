"""JS-fähiger Abruf über Playwright - mit auf Kohärenz getrimmter Browser-Identität.

LinkedIn lädt Ausbildung, Kenntnisse, Sprachen, Zertifikate und das Kontakt-Overlay
erst client-seitig nach. Ein reiner HTTP-Abruf bekommt dort
nur einen leeren Mount-Punkt bzw. ein geschlossenes Dialog-Gerüst.

Warum dieser Aufbau: Bis v0.3.2 hat der Fetcher eine in sich
widersprüchliche Identität erzeugt - er übernahm den `USER_AGENT` aus der config
(macOS/Chrome 131, gedacht für die curl_cffi-Impersonation), lief real aber auf einem
gebündelten Chromium 115 unter Windows mit `navigator.webdriver = true`, in einem
fabrikneuen Ephemer-Context ohne jede gewachsene Client-State. Eine bestehende Session
dort hineinzureichen sieht für LinkedIn aus wie ein Gerätewechsel mitten in der Sitzung -
Antwort: Logout + Mail-2FA (zweimal beobachtet, 07.09. headless und 08.09. headful).

Deshalb hier:
  * KEINE geerbte HTTP-UA. Der Browser benutzt seine eigene, echte User-Agent
    (`BROWSER_USER_AGENT = None`), die per Konstruktion zu Engine und Plattform passt.
  * `channel="chrome"` - echtes installiertes Chrome statt veraltetem Bundled-Chromium.
  * `--disable-blink-features=AutomationControlled` + Init-Script gegen `navigator.webdriver`.
  * Persistenter, TOOL-eigener Profilordner: localStorage/IndexedDB/Cache/Service-Worker
    wachsen über Läufe hinweg. (Ausdrücklich NICHT das Chrome-Profil des Bedieners -
    die Reproduzierbarkeit soll breit und standardisiert bleiben.)
  * Eine Seite pro Sitzung, in der navigiert wird, statt je URL ein neuer Tab.
  * Aufwärmen über den Feed und menschenähnliches Scrollen mit gestreuten Werten.

Gleiche Schnittstelle wie `fetch.fetcher.Fetcher`: ``get_html(url) -> str``.

Voraussetzung: ``pip install playwright`` und einmalig ``playwright install chromium``
(bzw. ein installiertes Google Chrome, wenn `BROWSER_CHANNEL = "chrome"`).
"""
from __future__ import annotations

import logging
import random
import re
from datetime import datetime

from ..config import (
    DEBUG_DUMP_DIR,
    BROWSER_USER_AGENT,
    BROWSER_CHANNEL,
    BROWSER_PERSISTENT,
    BROWSER_USER_DATA_DIR,
    BROWSER_INJECT_COOKIES,
    BROWSER_LOCALE,
    BROWSER_TIMEZONE,
    BROWSER_VIEWPORT,
    BROWSER_DEVICE_SCALE_FACTOR,
    BROWSER_HEADLESS,
    BROWSER_NAV_TIMEOUT_MS,
    BROWSER_ENTRY_WAIT_MS,
    BROWSER_DIALOG_WAIT_MS,
    BROWSER_SETTLE_MS,
    BROWSER_WARMUP,
    BROWSER_WARMUP_DWELL_MIN_MS,
    BROWSER_WARMUP_DWELL_MAX_MS,
    BROWSER_SCROLL_STEPS_MIN,
    BROWSER_SCROLL_STEPS_MAX,
    BROWSER_SCROLL_STEPS_MAX_WITH_TARGET,
    BROWSER_SCROLL_PX_MIN,
    BROWSER_SCROLL_PX_MAX,
    BROWSER_SCROLL_PAUSE_MIN_MS,
    BROWSER_SCROLL_PAUSE_MAX_MS,
    BROWSER_SCROLL_BACK_PROBABILITY,
    BROWSER_SCROLL_STABILITY_CONFIRM_MS,
    BROWSER_BLOCK_ASSETS,
    URL_SESSION_CHECK,
)
from ..rate_limiter import RateLimiter
from .fetcher import FetchError, ProfileNotFoundError, ERROR_BOUNDARY_MARKER, _error_boundary_in_body

logger = logging.getLogger("linkedin_scraper")


def _save_error_boundary_dump(page, url: str) -> None:
    """Sichert die Roh-HTML im Moment, in dem ERROR_BOUNDARY_MARKER endgültig als
    Fehler gewertet wird - als echtes Artefakt für die nächste Diagnose, statt nur
    einer Fehlermeldung ohne Beleg.

    Autor-Fund 2026-09-14: im sichtbaren, headful Browserfenster erscheint die Seite
    beim Zusehen augenscheinlich korrekt geladen, obwohl dieser Check auslöst und
    das Profil als Fehler/404 gewertet wird - ohne einen echten Dump lässt sich
    nicht unterscheiden, ob der Marker-Text tatsächlich sichtbar/aktiv im DOM steht
    (echte Fehlerseite) oder nur an unsichtbarer/inaktiver Stelle vorkommt (falsches
    Positiv der reinen Substring-Prüfung). Landet bewusst im selben Ordner wie die
    regulären Debug-Dumps (`config.DEBUG_DUMP_DIR`), mit eigenem Namenspräfix, damit
    sie sich nicht mit echten Dumps vermischen."""
    slug = re.sub(r"^https?://(www\.)?linkedin\.com/", "", url)
    slug = re.sub(r"[^A-Za-z0-9]+", "_", slug).strip("_") or "unbekannt"
    pfad = DEBUG_DUMP_DIR / f"errorboundary_{slug}_{datetime.now().strftime('%H%M%S')}.html"
    try:
        DEBUG_DUMP_DIR.mkdir(parents=True, exist_ok=True)
        pfad.write_text(page.content(), encoding="utf-8")
        logger.info("Rohdaten der mutmaßlichen Fehlerseite gesichert: %s", pfad)
    except Exception as exc:
        logger.warning("Konnte Fehlerseiten-Dump nicht speichern: %s", exc)

# Eine hydratisierte SDUI-Detailseite hat innerhalb der LazyColumn Textknoten (mind. die
# Sektionsüberschrift, sonst der Leerzustand-Hinweis). Das alte Markup
# `div[componentkey^="entity-collection-item-"]` gibt es seit 2026-09 nicht mehr.
# Auf einen <p> in der LazyColumn zu warten heißt "Inhalt ist da".
_ENTRY_SELECTOR = '[data-component-type="LazyColumn"] p'
# Das Kontakt-Overlay ist kein Listen-Screen: dort zeigt der gerenderte Dialog bzw. der
# mailto-Link an, dass fertig geladen wurde. Die Hauptprofilseite erkennt man an der Topcard.
_CONTACT_SELECTOR = 'a[href^="mailto:"], [role="dialog"]'
_TOPCARD_SELECTOR = '[componentkey$="Topcard"]'
# Das Kontakt-Overlay lässt sich NICHT per URL öffnen: ein direkter Aufruf von
# /overlay/contact-info/ liefert die Profilseite mit dem Popover im DOM, aber inert und
# unsichtbar (zweimal verifiziert, 08.09.). LinkedIn lädt den Inhalt erst beim echten
# Klick auf "Kontaktinformationen". Deshalb wird die Profilseite geladen und geklickt.
_CONTACT_LINK_SELECTOR = 'a[href*="/overlay/contact-info/"]'
_COOKIE_DOMAIN = ".linkedin.com"

# Zielt LinkedIn beim Aufruf auf eine dieser URLs, ist die Session tot oder ein
# Bot-Check ausgelöst - dann NICHT die Login-/Checkpoint-Seite als Dump speichern.
_BLOCKED_URL_MARKERS = ("/checkpoint/", "/authwall", "/uas/login", "/login")
_REDIRECT_ERROR_HINTS = ("ERR_TOO_MANY_REDIRECTS", "ERR_ABORTED", "ERR_HTTP_RESPONSE_CODE_FAILURE")

# Chrome setzt navigator.webdriver, sobald es automatisiert startet. Der Schalter
# --disable-blink-features=AutomationControlled entfernt das in aktuellen Versionen
# bereits; das Init-Script ist die Absicherung für ältere Builds. Bewusst minimal
# gehalten - großflächiges Patchen der JS-Umgebung ist selbst wieder erkennbar.
_STEALTH_INIT = "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"

_LAUNCH_ARGS = [
    "--disable-blink-features=AutomationControlled",
]

# Ressourcentypen, die für das reine DOM-Parsen nichts beitragen und deshalb (wenn
# BROWSER_BLOCK_ASSETS aktiv ist) gar nicht erst geladen werden. Dokument, Skripte,
# Stylesheets, XHR/fetch und WebSockets bleiben bewusst unberührt.
_BLOCKED_RESOURCE_TYPES = {"image", "media", "font"}


def _route_block_assets(route) -> None:
    """Playwright-Route-Handler: Bilder/Media/Fonts abbrechen, alles andere durchlassen."""
    try:
        if route.request.resource_type in _BLOCKED_RESOURCE_TYPES:
            route.abort()
            return
    except Exception:  # pragma: no cover - je nach Playwright-Version/Timing
        pass
    try:
        route.continue_()
    except Exception:  # pragma: no cover
        pass


def _wait_selector_for(url: str) -> str:
    """Wartemarker passend zum Seitentyp - sonst läuft jede Nicht-Listen-Seite
    unnötig in den vollen Timeout (siehe BROWSER_ENTRY_WAIT_MS)."""
    if "/overlay/contact-info" in url:
        return _CONTACT_SELECTOR
    if "/details/" in url:
        return _ENTRY_SELECTOR
    return _TOPCARD_SELECTOR


class BrowserFetcher:
    """Holt eine URL über einen echten Browser und gibt das gerenderte HTML zurück.

    Der Browser wird erst beim ersten `get_html`-Aufruf gestartet (lazy), damit der
    Import dieses Moduls auch ohne installiertes Playwright funktioniert.
    """

    def __init__(
        self,
        cookies: dict[str, str],
        rate_limiter: RateLimiter | None = None,
        headless: bool | None = None,
        block_assets: bool | None = None,
        allow_profile_reset: bool = False,
    ):
        self._cookies = dict(cookies)
        self.rate_limiter = rate_limiter or RateLimiter()
        self._headless = BROWSER_HEADLESS if headless is None else headless
        # Beim manuellen Login (Menüpunkt 1) bewusst False übergeben, damit der
        # Bediener eine normal gerenderte Seite sieht.
        self._block_assets = BROWSER_BLOCK_ASSETS if block_assets is None else block_assets
        # Nur der explizite Login-Weg (Menüpunkt 1) setzt das - siehe
        # _reset_profile_and_relaunch. Beim Scraping/Debug-Dump/Fingerprint-Check bleibt
        # ein nicht startbares Profil bewusst ein harter Fehler statt eines stillen
        # Zurücksetzens (dort könnte "startet nicht" auch einfach heißen, dass das Tool
        # noch in einem zweiten Fenster läuft - siehe Fehlermeldung unten).
        self._allow_profile_reset = allow_profile_reset
        self._pw = None
        self._browser = None
        self._context = None
        self._page = None
        self._warmed_up = False
        # True, sobald get_html() feststellt, dass die Seite/der Browser weg ist (Chrome
        # abgestürzt oder manuell geschlossen) - siehe _check_crashed(). Der Aufrufer
        # (main.py:scrape_profile) bricht ein Profil dann als Ganzes ab, statt für jede
        # weitere Sektion einzeln denselben Fehler zu bekommen und am Ende ein Profil
        # mit lauter N/A-Feldern zu schreiben.
        self._crashed = False

    @property
    def crashed(self) -> bool:
        return self._crashed

    # -- Lebenszyklus -------------------------------------------------------

    def _context_options(self) -> dict:
        """Kontext-Einstellungen, die zueinander passen müssen."""
        # None-Werte bewusst NICHT setzen: dann gilt die Vorgabe des Systems bzw. des
        # Browserfensters. Ein fest verdrahtetes "Europe/Berlin" wäre auf einem Rechner
        # in einer anderen Zeitzone ein Widerspruch zur IP-Geolokalisierung, und ein
        # festes Viewport kann größer sein als der Bildschirm der Zielmaschine.
        opts: dict = {}
        if BROWSER_LOCALE:
            opts["locale"] = BROWSER_LOCALE
        if BROWSER_TIMEZONE:
            opts["timezone_id"] = BROWSER_TIMEZONE
        if BROWSER_VIEWPORT:
            opts["viewport"] = dict(BROWSER_VIEWPORT)
        else:
            opts["no_viewport"] = True
        if BROWSER_DEVICE_SCALE_FACTOR:
            opts["device_scale_factor"] = BROWSER_DEVICE_SCALE_FACTOR
        # Nur setzen, wenn bewusst gewünscht - sonst die echte UA des Browsers behalten.
        if BROWSER_USER_AGENT:
            opts["user_agent"] = BROWSER_USER_AGENT
        return opts

    def _ensure_browser(self) -> None:
        if self._context is not None:
            return
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:  # pragma: no cover - abhängig von der Umgebung
            raise FetchError(
                "Playwright ist nicht installiert. Bitte `pip install playwright` und "
                "einmalig `playwright install chromium` ausführen - oder in config.py "
                "USE_BROWSER_FOR_LAZY = False setzen."
            ) from exc

        self._pw = sync_playwright().start()
        opts = self._context_options()

        if BROWSER_PERSISTENT:
            BROWSER_USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
            try:
                self._context = self._launch_persistent(str(BROWSER_USER_DATA_DIR), opts)
            except Exception as exc:
                if self._allow_profile_reset:
                    self._context = self._reset_profile_and_relaunch(opts, exc)
                else:
                    # Ein Profilverzeichnis kann immer nur von EINEM Browser benutzt
                    # werden. Typischer Fall: das Tool läuft bereits in einem anderen
                    # Fenster, oder ein Browser aus einem abgebrochenen Lauf hängt noch.
                    raise FetchError(
                        f"Das Tool-Browserprofil ({BROWSER_USER_DATA_DIR}) lässt sich "
                        f"nicht öffnen. Meist läuft das Tool noch in einem zweiten "
                        f"Fenster oder ein Browser aus einem abgebrochenen Lauf hängt "
                        f"noch - diese schließen und erneut versuchen. Falls das Profil "
                        f"von einer anderen Maschine mitgebracht wurde und dort "
                        f"grundsätzlich nicht mehr startet: Menüpunkt 1 (Anmelden) "
                        f"benutzen - der legt in diesem Fall automatisch ein frisches "
                        f"Profil für diese Maschine an. ({exc})"
                    ) from exc
        else:
            self._browser = self._launch_browser()
            self._context = self._browser.new_context(**opts)

        self._context.set_default_navigation_timeout(BROWSER_NAV_TIMEOUT_MS)
        self._context.add_init_script(_STEALTH_INIT)

        if self._block_assets:
            try:
                self._context.route("**/*", _route_block_assets)
                logger.info("Asset-Blocker aktiv: Bilder/Media/Fonts werden nicht geladen.")
            except Exception as exc:  # pragma: no cover
                logger.warning("Asset-Blocker konnte nicht gesetzt werden: %s", exc)

        if self._should_inject_cookies():
            self._context.add_cookies(
                [
                    {"name": name, "value": value, "domain": _COOKIE_DOMAIN, "path": "/"}
                    for name, value in self._cookies.items()
                ]
            )
            logger.info("%d Cookies in den Browser-Context übernommen.", len(self._cookies))
        else:
            logger.info(
                "Keine Cookie-Injektion (BROWSER_INJECT_COOKIES=%r) - es zählt die im "
                "Tool-Profil gespeicherte Anmeldung.", BROWSER_INJECT_COOKIES,
            )

        pages = getattr(self._context, "pages", None)
        self._page = pages[0] if pages else self._context.new_page()
        logger.info(
            "Browser-Fetcher gestartet (headless=%s, channel=%s, persistent=%s).",
            self._headless, BROWSER_CHANNEL or "bundled-chromium", BROWSER_PERSISTENT,
        )
        self._log_identity()

    def session_cookies(self) -> dict[str, str]:
        """Die LinkedIn-Cookies aus dem Tool-Profil als {name: wert}.

        Damit kann der HTTP-Weg dieselbe Session benutzen, die im Tool-Profil nativ
        entstanden ist - dann sprechen beide Wege mit **einer** Sitzung von **einem**
        Gerät, und die Browser-Extension wird gar nicht mehr gebraucht.
        """
        self._ensure_browser()
        try:
            roh = self._context.cookies("https://www.linkedin.com/")
        except Exception as exc:  # pragma: no cover
            logger.warning("Cookies konnten nicht aus dem Tool-Profil gelesen werden: %s", exc)
            return {}
        return {c["name"]: c["value"] for c in roh if c.get("name") and c.get("value")}

    def inject_cookies(self, cookies: dict[str, str]) -> None:
        """Nachträglich Cookies in den laufenden Kontext geben (Extension-Rückfall).

        Achtung: ohne `expires` sind das SITZUNGS-Cookies - sie verschwinden, sobald der
        Browser geschlossen wird. Genau deshalb ist die einmalige manuelle Anmeldung im
        Tool-Profil der dauerhafte Weg (Menüpunkt 5).
        """
        if not cookies:
            return
        self._cookies = dict(cookies)
        self._ensure_browser()
        self._context.add_cookies(
            [
                {"name": name, "value": value, "domain": _COOKIE_DOMAIN, "path": "/"}
                for name, value in cookies.items()
            ]
        )
        logger.info("%d Cookies nachträglich in den Browser-Context gegeben.", len(cookies))

    def _profile_has_session(self) -> bool:
        """Liegt im Tool-Profil bereits eine LinkedIn-Anmeldung?"""
        try:
            vorhandene = self._context.cookies("https://www.linkedin.com/")
        except Exception:  # pragma: no cover - je nach Playwright-Version
            return False
        return any(c.get("name") == "li_at" and c.get("value") for c in vorhandene)

    def _should_inject_cookies(self) -> bool:
        """Entscheidet über die Cookie-Injektion - inklusive Automatik.

        "auto" ist der empfohlene Wert: hat sich der Bediener im Tool-Profil einmal
        manuell angemeldet, ist die Session dort NATIV entstanden und LinkedIn kennt
        das Gerät. Dann wäre ein Hineinreichen fremder Cookies genau die Anomalie,
        die wir vermeiden wollen - die Automatik lässt es dann weg, ohne dass in der
        config etwas umgestellt werden muss.
        """
        if BROWSER_INJECT_COOKIES is False:
            return False
        if not self._cookies:
            return False
        if BROWSER_INJECT_COOKIES is True:
            return True
        # "auto"
        if self._profile_has_session():
            logger.info(
                "Tool-Profil ist bereits bei LinkedIn angemeldet - Cookie-Injektion "
                "wird übersprungen (BROWSER_INJECT_COOKIES='auto')."
            )
            return False
        logger.info(
            "Tool-Profil hat noch keine LinkedIn-Anmeldung - Cookies werden injiziert "
            "(BROWSER_INJECT_COOKIES='auto'). Tipp: einmal über Menüpunkt 5 manuell "
            "anmelden, dann entfällt die Injektion dauerhaft."
        )
        return True

    def _launch_persistent(self, user_data_dir: str, opts: dict):
        try:
            return self._pw.chromium.launch_persistent_context(
                user_data_dir,
                headless=self._headless,
                channel=BROWSER_CHANNEL,
                args=_LAUNCH_ARGS,
                **opts,
            )
        except Exception as exc:
            if not BROWSER_CHANNEL:
                raise
            logger.warning(
                "Chrome-Kanal '%s' nicht startbar (%s) - weiche auf das gebündelte "
                "Chromium aus. Für einen stimmigen Fingerprint bitte Google Chrome "
                "installieren.", BROWSER_CHANNEL, exc,
            )
            return self._pw.chromium.launch_persistent_context(
                user_data_dir, headless=self._headless, args=_LAUNCH_ARGS, **opts
            )

    def _reset_profile_and_relaunch(self, opts: dict, first_exc: Exception):
        """Letzter Ausweg, NUR über Menüpunkt 1 (allow_profile_reset=True) erreichbar.

        Szenario: das Browserprofil wurde von einer anderen Maschine mitgebracht (siehe
        README „Kompilieren" - LinkedInScraper/ ist als Ganzes portabel) und lässt sich
        auf dieser Maschine grundsätzlich nicht starten (andere Chrome-Version, defektes
        Profilschema o.ä.). Statt endlos mit derselben Fehlermeldung zu scheitern: das
        nicht startbare Profil NICHT löschen, sondern zeitgestempelt zur Seite legen
        (jederzeit von Hand rückgängig zu machen) und mit einem frischen, leeren Profil
        für DIESE Maschine neu versuchen - der Bediener meldet sich danach einmal neu an
        (normaler Menüpunkt-1-Ablauf, siehe _open_profile_for_login).
        """
        quarantine = BROWSER_USER_DATA_DIR.with_name(
            f"{BROWSER_USER_DATA_DIR.name}_defekt_{datetime.now():%Y%m%d-%H%M%S}"
        )
        n = 2
        while quarantine.exists():
            quarantine = BROWSER_USER_DATA_DIR.with_name(
                f"{BROWSER_USER_DATA_DIR.name}_defekt_{datetime.now():%Y%m%d-%H%M%S}_{n}"
            )
            n += 1

        try:
            BROWSER_USER_DATA_DIR.rename(quarantine)
        except Exception as rename_exc:
            raise FetchError(
                f"Das Tool-Browserprofil ({BROWSER_USER_DATA_DIR}) lässt sich nicht "
                f"öffnen ({first_exc}) und auch nicht zur Seite legen ({rename_exc}). "
                f"Meist läuft das Tool noch in einem zweiten Fenster - dieses schließen "
                f"und erneut versuchen."
            ) from rename_exc

        logger.warning(
            "Bestehendes Browserprofil liess sich nicht oeffnen (%s) - vermutlich von "
            "einer anderen Maschine mitgebracht und hier nicht kompatibel. NICHT "
            "geloescht, sondern verschoben nach %s. Lege ein frisches, leeres Profil "
            "fuer diese Maschine an.", first_exc, quarantine,
        )
        print(f"\nDas mitgebrachte Browserprofil ({BROWSER_USER_DATA_DIR.name}) läuft auf "
              f"diesem Gerät nicht an.")
        print(f"Es wurde zur Sicherheit umbenannt/verschoben nach:\n  {quarantine}")
        print("Es wird jetzt ein neues, leeres Profil für DIESES Gerät angelegt - bitte "
              "gleich im sich öffnenden Fenster neu bei LinkedIn anmelden.\n")

        BROWSER_USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
        try:
            return self._launch_persistent(str(BROWSER_USER_DATA_DIR), opts)
        except Exception as exc2:
            raise FetchError(
                f"Auch das frisch angelegte Profil ({BROWSER_USER_DATA_DIR}) lässt sich "
                f"nicht öffnen: {exc2}"
            ) from exc2

    def _launch_browser(self):
        try:
            return self._pw.chromium.launch(
                headless=self._headless, channel=BROWSER_CHANNEL, args=_LAUNCH_ARGS
            )
        except Exception as exc:
            if not BROWSER_CHANNEL:
                raise
            logger.warning(
                "Chrome-Kanal '%s' nicht startbar (%s) - weiche auf das gebündelte "
                "Chromium aus.", BROWSER_CHANNEL, exc,
            )
            return self._pw.chromium.launch(headless=self._headless, args=_LAUNCH_ARGS)

    def _log_identity(self) -> None:
        """Protokolliert die tatsächliche Identität - macht Widersprüche sofort sichtbar."""
        try:
            ident = self._page.evaluate(
                "() => ({ua: navigator.userAgent, platform: navigator.platform,"
                " webdriver: navigator.webdriver, lang: navigator.language,"
                " tz: Intl.DateTimeFormat().resolvedOptions().timeZone})"
            )
            logger.info(
                "Browser-Identität: UA=%s | platform=%s | webdriver=%s | lang=%s | tz=%s",
                ident.get("ua"), ident.get("platform"), ident.get("webdriver"),
                ident.get("lang"), ident.get("tz"),
            )
        except Exception as exc:  # pragma: no cover - reine Diagnose
            logger.debug("Identitäts-Check nicht möglich: %s", exc)

    def fingerprint(self) -> dict:
        """Sammelt die Merkmale, an denen Automatisierung typischerweise auffällt.

        Gedacht für einen Selbsttest OHNE LinkedIn-Zugriff (Debug-Menü): so lässt sich
        der Umbau prüfen, ohne einen Account zu riskieren.
        """
        self._ensure_browser()
        return self._page.evaluate(
            """() => {
                let vendor = null, renderer = null;
                try {
                    const c = document.createElement('canvas');
                    const gl = c.getContext('webgl') || c.getContext('experimental-webgl');
                    const dbg = gl && gl.getExtension('WEBGL_debug_renderer_info');
                    if (dbg) {
                        vendor = gl.getParameter(dbg.UNMASKED_VENDOR_WEBGL);
                        renderer = gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL);
                    }
                } catch (e) { /* WebGL nicht verfuegbar */ }
                return {
                    userAgent: navigator.userAgent,
                    platform: navigator.platform,
                    webdriver: navigator.webdriver,
                    languages: navigator.languages,
                    hardwareConcurrency: navigator.hardwareConcurrency,
                    deviceMemory: navigator.deviceMemory,
                    pluginCount: navigator.plugins.length,
                    mimeTypeCount: navigator.mimeTypes.length,
                    brands: navigator.userAgentData ? navigator.userAgentData.brands : null,
                    uaPlatform: navigator.userAgentData ? navigator.userAgentData.platform : null,
                    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
                    screen: [screen.width, screen.height],
                    viewport: [innerWidth, innerHeight],
                    devicePixelRatio: devicePixelRatio,
                    webglVendor: vendor,
                    webglRenderer: renderer,
                    hasChromeObject: typeof window.chrome !== 'undefined',
                    pdfViewerEnabled: navigator.pdfViewerEnabled,
                };
            }"""
        )

    def open_for_manual_login(self, url: str = URL_SESSION_CHECK) -> None:
        """Öffnet das Tool-Profil sichtbar, damit sich der Bediener EINMAL manuell anmeldet.

        Danach kann `BROWSER_INJECT_COOKIES = False` gesetzt werden: die Session ist dann
        nativ in diesem Profil entstanden, und der Anomalie-Auslöser „fremdes Token in
        unbekanntem Browser" entfällt vollständig.
        """
        self._ensure_browser()
        self._page.goto(url, wait_until="domcontentloaded")

    def close(self) -> None:
        for obj in (self._context, self._browser):
            if obj is not None:
                try:
                    obj.close()
                except Exception:  # pragma: no cover - best effort
                    pass
        if self._pw is not None:
            try:
                self._pw.stop()
            except Exception:  # pragma: no cover
                pass
        self._context = self._browser = self._pw = self._page = None
        self._warmed_up = False
        self._crashed = False

    def recycle(self) -> None:
        """Kontext/Seite/Playwright schließen, sodass der nächste `get_html` einen
        frischen Kontext aufsetzt.

        Gegen den langsam wachsenden Speicherverbrauch einer Seite, die über sehr
        viele Profile hinweg wiederverwendet wird - relevant auf schwacher Hardware.
        Die Anmeldung liegt im persistenten Tool-Profil auf der Platte und wird beim
        Neustart wieder eingelesen; die Sitzung überlebt das Recyceln also. Der
        Feed-Aufwärmer läuft danach einmalig erneut.
        """
        logger.info("Browser-Kontext wird neu aufgesetzt (Speicherhygiene).")
        self.close()

    def __enter__(self) -> "BrowserFetcher":
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

    # -- Abruf ------------------------------------------------------------

    def _warm_up(self) -> None:
        """Erst den Feed laden und kurz verweilen, statt mit einer Detailseite zu starten.

        Sekundäre Maßnahme: die Geräte-Kohärenz ist der wichtigere Hebel. Aber eine
        Sitzung, die mit `/details/education/` beginnt, ist für sich schon auffällig.
        """
        if self._warmed_up or not BROWSER_WARMUP:
            self._warmed_up = True
            return
        self._warmed_up = True  # auch bei Fehlschlag nicht erneut versuchen
        try:
            self._page.goto(URL_SESSION_CHECK, wait_until="domcontentloaded")
            self._scroll_through(self._page)
            self._page.wait_for_timeout(
                random.randint(BROWSER_WARMUP_DWELL_MIN_MS, BROWSER_WARMUP_DWELL_MAX_MS)
            )
            logger.info("Browser-Sitzung über den Feed aufgewärmt.")
        except Exception as exc:
            logger.warning("Aufwärmen des Browsers fehlgeschlagen (nicht kritisch): %s", exc)

    def warm_up_now(self) -> None:
        """Startet den Browser (falls nötig) und wärmt ihn SOFORT über den Feed auf,
        statt das lazy erst beim ersten `get_html()`-Aufruf für eine Detailseite
        passieren zu lassen.

        `run_scraping` ruft das jetzt VOR der Profil-Schleife auf: bisher lief das
        Aufwärmen mitten im ERSTEN Profil (ausgelöst vom ersten Browser-Zugriff dort,
        z. B. das Kontakt-Overlay), nachdem für dieses Profil bereits Profilseite und
        Erfahrung per HTTP abgerufen worden waren - reihenfolgetechnisch falsch (Autor-
        Fund 2026-09-13). So steht die aufgewärmte Sitzung vollständig, bevor überhaupt
        ein Profil angefasst wird.
        """
        self._ensure_browser()
        self._warm_up()

    def get_html(self, url: str, referer: str | None = None,
                 wait_selector: str | None = None) -> str:
        # `referer` wird von der gemeinsamen Fetcher-Schnittstelle mitgegeben, im
        # Browser aber nicht gebraucht (er setzt seinen Referer selbst).
        _ = referer
        selector = wait_selector or _wait_selector_for(url)
        self._ensure_browser()
        self._warm_up()
        self.rate_limiter.wait()

        # Bewusst dieselbe Seite wiederverwenden und darin navigieren, statt je URL
        # einen neuen Tab zu öffnen - das entspricht eher einer echten Sitzung.
        page = self._page
        try:
            for versuch in (1, 2):
                try:
                    # domcontentloaded statt load: auf das komplette load-Event (alle
                    # Sub-Ressourcen) zu warten bringt nichts - direkt danach folgt ein
                    # gezieltes wait_for_selector.
                    page.goto(url, wait_until="domcontentloaded")
                except Exception as exc:
                    if any(h in str(exc) for h in _REDIRECT_ERROR_HINTS):
                        raise FetchError(
                            f"Weiterleitungsschleife/Abbruch bei {url}. Meist ist die Session "
                            f"ungültig (Bot-Check ausgelöst, ausgeloggt). Wenn im Tool-Profil "
                            f"eine abgelaufene Anmeldung liegt: Menüpunkt 5 (Profil öffnen) und "
                            f"dort neu anmelden - bei BROWSER_INJECT_COOKIES='auto' wird eine "
                            f"vorhandene Profil-Anmeldung nicht durch frische Cookies ersetzt. "
                            f"({exc})"
                        ) from exc
                    raise

                # Kurze Nachlauf-Pause, bevor der Seitenzustand geprüft wird - gibt der
                # SPA etwas mehr Zeit, ihr Routing/Laden abzuschließen, statt sie direkt
                # nach "domcontentloaded" als kaputt zu werten (Autor-Fund 2026-09-14:
                # unter dem stark beschleunigten Testmodus zeigte JEDES Profil sofort
                # die Fehlerseite unten - ein Hinweis, dass zumindest ein Teil davon
                # Timing-/Drosselungs-bedingt statt ein echtes 404 war).
                page.wait_for_timeout(BROWSER_SETTLE_MS)

                landed = page.url
                # Diese Umleitung passiert client-seitig per JS, nachdem die SPA geprüft hat,
                # ob es das Profil noch gibt - ein reiner HTTP-GET (fetch/fetcher.py) bekommt
                # sie NIE zu sehen, nur der Browser. Deshalb ist das hier die einzige
                # zuverlässige Stelle, an der ein gelöschtes/nicht mehr existierendes Profil
                # erkannt wird (Autor-Fund 2026-09-13: zwei bestätigt gelöschte Profile liefen
                # über den reinen HTTP-Weg unbemerkt komplett durch die Erhebung).
                if "/404" in landed:
                    raise ProfileNotFoundError(
                        f"{url} existiert nicht (mehr) - umgeleitet auf {landed}."
                    )
                if any(m in landed for m in _BLOCKED_URL_MARKERS):
                    raise FetchError(
                        f"LinkedIn hat {url} auf {landed} umgeleitet (Login/Checkpoint) - "
                        f"Session ungültig oder Bot-Erkennung ausgelöst. Kein Dump gespeichert. "
                        f"Liegt im Tool-Profil eine abgelaufene Anmeldung, hilft Menüpunkt 5 "
                        f"(Profil öffnen und dort neu anmelden)."
                    )

                if _error_boundary_in_body(page.content()):
                    # Dieser Text ist auf KEINER URL ein hundertprozentig verlässliches
                    # 404-Signal - ein inhaltsreiches, echt existierendes Profil kann
                    # hier ebenso landen (Autor-Fund 2026-09-14: david-haslacher, 48
                    # echte Kenntnisse - /details/skills/ zeigte denselben Fehlertext,
                    # obwohl das Profil unstrittig existiert), UND unter stark
                    # verkürzten Delays (Testmodus) zeigte JEDES Profil diesen Text,
                    # auch auf der Kontakt-/Profilseite - vermutlich Drosselung/
                    # Timing statt Löschung. Deshalb JETZT auf jeder URL erst ein
                    # zweiter Versuch (neue Navigation), bevor überhaupt entschieden
                    # wird. Bleibt der Fehler bestehen, gilt weiterhin: auf der
                    # Kontakt-/Profilseite (kein "/details/" in der URL) als 404, auf
                    # einer Detailseite als normaler FetchError - weil DORT (Kontakt-/
                    # Profilseite) beide bislang bestätigten echten 404-Fälle auftraten.
                    if versuch == 1:
                        logger.info(
                            "Fehlerseite auf %s - könnte transient sein (Rendering/"
                            "Drosselung). Navigiere erneut.", url,
                        )
                        continue
                    # NEU v0.7.26: Rohdaten sichern, BEVOR aufgegeben wird - liefert
                    # beim nächsten Auftreten ein echtes Artefakt statt nur einer
                    # Fehlermeldung ohne Beleg (siehe _save_error_boundary_dump).
                    _save_error_boundary_dump(page, url)
                    if "/details/" in url:
                        raise FetchError(
                            f"{url} zeigt weiterhin LinkedIns generische Fehlerseite "
                            f"nach einem erneuten Versuch - vermutlich ein "
                            f"Rendering-/Drosselungsproblem, kein Hinweis auf ein "
                            f"gelöschtes Profil."
                        )
                    raise ProfileNotFoundError(
                        f"{url} zeigt weiterhin LinkedIns generische Fehlerseite nach "
                        f"einem erneuten Versuch (\"{ERROR_BOUNDARY_MARKER}\")."
                    )
                break

            # Kontakt-Overlay: Popover anklicken statt die URL anzuspringen.
            if "/overlay/contact-info" in url:
                self._open_contact_overlay(page)
                page.wait_for_timeout(BROWSER_SETTLE_MS)
                return page.content()

            # Scrollen löst die LazyColumns aus - und wird abgebrochen, sobald der
            # Wartemarker sichtbar ist (kein fixes Schrittbudget verbrauchen).
            self._scroll_through(page, stop_selector=selector)
            try:
                page.wait_for_selector(selector, timeout=BROWSER_ENTRY_WAIT_MS)
            except Exception:
                # Marker nicht da: entweder leere Sektion (0 Einträge, z. B. keine
                # Zertifikate / E-Mail nicht freigegeben) oder Markup geändert. Der
                # Parser gibt dann [] bzw. N/A zurück und protokolliert das.
                logger.info("Wartemarker %r nicht gefunden auf %s.", selector, url)
            page.wait_for_timeout(BROWSER_SETTLE_MS)
            return page.content()
        except FetchError:
            self._check_crashed()
            raise
        except Exception as exc:
            self._check_crashed()
            raise FetchError(f"Browser-Abruf fehlgeschlagen für {url}: {exc}") from exc

    def _check_crashed(self) -> None:
        """Setzt `crashed`, wenn die Seite/der Browser weg ist (Chrome abgestürzt oder
        manuell geschlossen). `main.py:scrape_profile` bricht ein Profil dann als Ganzes
        ab und lässt `run_scraping` den Browser neu starten und das Profil von vorn
        versuchen, statt für jede weitere Sektion denselben Fehler zu bekommen und am
        Ende ein Profil mit lauter N/A-Feldern zu schreiben."""
        try:
            if self._page is None or self._page.is_closed():
                self._crashed = True
        except Exception:  # pragma: no cover - wenn nicht mal die Prüfung geht, gilt
            self._crashed = True  # der Browser sicherheitshalber als abgestürzt.

    def _open_contact_overlay(self, page) -> bool:
        """Öffnet das Kontakt-Overlay durch einen echten Klick. Gibt zurück, ob es klappte.

        Eine Navigation auf `/overlay/contact-info/` rendert nur die Profilseite mit
        geschlossenem Popover (`inert`); LinkedIn lädt den Inhalt erst beim Klick auf
        "Kontaktinformationen" (dreimal verifiziert am 08.09.).

        Robust gehalten, weil der Link je nach Profil unterschiedlich erreichbar ist:
        nicht jedes Profil gibt Kontaktdaten frei, und der Klick kann von Overlays
        (Banner, Sticky-Header) abgefangen werden. Deshalb drei Klickstrategien und eine
        klare Unterscheidung zwischen "Profil teilt nichts" und "Seite nicht geladen".

        `link` ist bewusst ein **Locator**, kein `page.wait_for_selector(...)`-
        ElementHandle: Ein ElementHandle ist eine EINMALIGE Referenz auf den zum
        Abrufzeitpunkt existierenden DOM-Knoten. Rendert LinkedIns SPA diesen Teil der
        Seite kurz danach neu (React ersetzt den Knoten, auch wenn er inhaltlich
        identisch aussieht), wird die alte Referenz "detached" - `.click()` UND
        `.click(force=True)` scheitern dann beide mit "Element is not attached to the
        DOM", weil beide dieselbe veraltete Referenz benutzen; erst der DOM-Klick auf
        die (zufällig noch gültige) alte Objektreferenz trifft über Event-Bubbling noch
        den richtigen Handler. Ein Locator löst den Selektor dagegen bei JEDER Aktion
        neu auf und trifft so zuverlässig das aktuell existierende Element (betraf beim Testkorpus praktisch jedes fremde
        Profil, beim eigenen Testprofil nie aufgefallen).
        """
        # Ist die Seite überhaupt da? Ohne Topcard stimmt etwas Grundsätzliches nicht.
        topcard_da = True
        try:
            page.wait_for_selector(_TOPCARD_SELECTOR, timeout=BROWSER_ENTRY_WAIT_MS)
        except Exception:
            topcard_da = False

        link = page.locator(_CONTACT_LINK_SELECTOR).first
        try:
            link.wait_for(state="attached", timeout=BROWSER_ENTRY_WAIT_MS)
        except Exception:
            link = None

        if link is None:
            if topcard_da:
                logger.info(
                    "Profilseite geladen, aber kein Link auf die Kontaktinformationen - "
                    "dieses Profil gibt keine Kontaktdaten frei. E-Mail/Geburtstag "
                    "bleiben N/A."
                )
            else:
                logger.warning(
                    "Weder Topcard noch Kontakt-Link gefunden - die Seite wurde nicht "
                    "richtig geladen oder das Markup hat sich geändert."
                )
            return False

        try:
            link.scroll_into_view_if_needed(timeout=BROWSER_ENTRY_WAIT_MS)
        except Exception:
            pass
        page.wait_for_timeout(random.randint(300, 900))

        # Drei Strategien: normal -> erzwungen (falls ein Overlay davor liegt) ->
        # direkt im DOM (falls Playwright die Stelle für unklickbar hält).
        for versuch, aktion in (
            ("normal", lambda: link.click(timeout=BROWSER_ENTRY_WAIT_MS)),
            ("erzwungen", lambda: link.click(timeout=BROWSER_ENTRY_WAIT_MS, force=True)),
            ("per DOM", lambda: link.evaluate("el => el.click()")),
        ):
            try:
                aktion()
            except Exception as exc:
                logger.info("Klick auf die Kontaktinformationen (%s) fehlgeschlagen: %s",
                            versuch, exc)
                continue
            if self._contact_dialog_ready(page):
                logger.info("Kontakt-Overlay geöffnet (Klick %s).", versuch)
                return True

        logger.warning(
            "Kontakt-Overlay ließ sich nicht öffnen - der Dump enthält dann nur die "
            "Profilseite, E-Mail/Geburtstag bleiben N/A."
        )
        return False

    def _contact_dialog_ready(self, page) -> bool:
        """Wartet auf einen sichtbaren Dialog und darin auf geladenen Inhalt."""
        try:
            page.wait_for_selector('[role="dialog"]', state="visible",
                                   timeout=BROWSER_DIALOG_WAIT_MS)
        except Exception:
            return False
        # Der Dialog erscheint zuerst leer und füllt sich nach. Auf ein mailto warten,
        # aber ein Ausbleiben NICHT als Fehler werten - viele Profile geben keine
        # E-Mail frei, der Dialog ist dann trotzdem korrekt geöffnet.
        try:
            page.wait_for_selector('[role="dialog"] a[href^="mailto:"]',
                                   timeout=BROWSER_DIALOG_WAIT_MS)
        except Exception:
            page.wait_for_timeout(BROWSER_SETTLE_MS)
        return True

    def _scroll_through(self, page, stop_selector: str | None = None) -> None:
        """Scrollt mit gestreuten Distanzen und Pausen nach unten und wieder hoch.

        Vorher waren es exakt 10 Schritte a 2200 px alle 400 ms, ohne jede
        Mausbewegung - ein Muster, das sich trivial von menschlichem Scrollen
        unterscheiden lässt.

        `stop_selector`: solange sich die Anzahl der Treffer noch erhöht, wird
        weitergescrollt (lange Listen wie Kenntnisse laden weitere Einträge erst beim
        WEITEREN Scrollen nach - LazyColumn-Pagination). Ein einzelner Treffer allein reicht NICHT mehr als
        Abbruchkriterium: erst wenn die Trefferzahl über mehrere aufeinanderfolgende
        Scrollschritte NICHT mehr gewachsen ist, gilt der Inhalt als vollständig
        geladen, und es wird nach einer kurzen Nachlauf-Pause abgebrochen. Ohne den
        Parameter wird das volle (kleinere) Schrittbudget gescrollt (z. B. beim
        Aufwärmen auf dem Feed, wo es kein Ziel gibt).
        """
        # Fenstergröße vom echten Fenster nehmen. BROWSER_VIEWPORT darf None sein
        # (portabler Standard, siehe config) - dann kennt nur die Seite ihre Maße.
        groesse = page.viewport_size
        if not groesse:
            try:
                w, h = page.evaluate("() => [window.innerWidth, window.innerHeight]")
                groesse = {"width": w, "height": h}
            except Exception:
                groesse = {}
        width = groesse.get("width") or 1280
        height = groesse.get("height") or 800
        max_steps = BROWSER_SCROLL_STEPS_MAX_WITH_TARGET if stop_selector else BROWSER_SCROLL_STEPS_MAX
        # Fund 2026-09-15 (Vaibhav Grover, Referenzabgleich): mit `stop_selector` ist
        # `max_steps` NUR eine Sicherheitsobergrenze - das eigentliche Abbruchkriterium
        # ist die Stabilitätsprüfung unten. Wurde `steps` trotzdem aus dem vollen
        # Bereich [BROWSER_SCROLL_STEPS_MIN, max_steps] gewürfelt, konnte ein
        # niedriger Treffer (z. B. 6) die Schleife beenden, bevor eine lange Liste
        # (hier 98 Kenntnisse) überhaupt vollständig nachgeladen war - die
        # Stabilitätsprüfung kam so nie zum Zug. Sauber am Referenzabgleich belegt:
        # die gescrapte Liste war exakt ein Präfix der echten, um die letzten 18
        # Einträge gekürzt. Ohne Ziel-Selektor (Aufwärm-Scroll auf dem Feed) bleibt
        # die Zufallsstreuung wie bisher, dort gibt es keine Vollständigkeits-Erwartung.
        steps = max_steps if stop_selector else random.randint(BROWSER_SCROLL_STEPS_MIN, max_steps)
        letzte_anzahl = 0
        stabile_runden = 0
        for step_i in range(steps):
            try:
                page.mouse.move(
                    random.randint(int(width * 0.2), int(width * 0.8)),
                    random.randint(int(height * 0.2), int(height * 0.8)),
                    steps=random.randint(3, 12),
                )
            except Exception:  # pragma: no cover - Mausbewegung ist nur Beiwerk
                pass
            page.mouse.wheel(0, random.randint(BROWSER_SCROLL_PX_MIN, BROWSER_SCROLL_PX_MAX))
            page.wait_for_timeout(
                random.randint(BROWSER_SCROLL_PAUSE_MIN_MS, BROWSER_SCROLL_PAUSE_MAX_MS)
            )
            if random.random() < BROWSER_SCROLL_BACK_PROBABILITY:
                page.mouse.wheel(0, -random.randint(200, 700))
                page.wait_for_timeout(
                    random.randint(BROWSER_SCROLL_PAUSE_MIN_MS, BROWSER_SCROLL_PAUSE_MAX_MS)
                )
            # Trefferzahl noch am Wachsen? Dann weiterscrollen - erst zwei Runden ohne
            # Zuwachs gelten als "fertig geladen".
            if stop_selector and step_i >= 1:
                try:
                    anzahl = len(page.query_selector_all(stop_selector))
                except Exception:  # pragma: no cover
                    anzahl = 0
                if anzahl > 0:
                    stabile_runden = stabile_runden + 1 if anzahl == letzte_anzahl else 0
                    letzte_anzahl = anzahl
                    if stabile_runden >= 2:
                        # Fund 2026-09-15 (Vaibhav Grover): ein "stabiler" Zwischenstand mit
                        # nur der normalen, kurzen Scroll-Pause reicht nicht als Beleg - ein
                        # noch ladender LazyColumn-Batch kann 2 Runden lang zufällig
                        # gleich aussehen. Vor dem Abbruch deshalb einmal deutlich länger
                        # warten und die Trefferzahl gegenprüfen; hat sie sich doch noch
                        # erhöht, war es keine echte Stabilität - weiterscrollen.
                        page.wait_for_timeout(BROWSER_SCROLL_STABILITY_CONFIRM_MS)
                        try:
                            bestaetigt = len(page.query_selector_all(stop_selector))
                        except Exception:  # pragma: no cover
                            bestaetigt = anzahl
                        if bestaetigt == anzahl:
                            break
                        stabile_runden = 0
                        letzte_anzahl = bestaetigt
        else:
            # Schleife lief bis zum Ende durch (kein `break`) - bei einem Ziel-Selektor
            # heißt das: die Trefferzahl hat sich innerhalb des Schrittbudgets nie
            # stabilisiert, die Liste ist möglicherweise unvollständig geladen (siehe
            # Fund oben). Lieber einmal zu oft warnen als eine stille Kürzung (DQ4).
            if stop_selector:
                logger.warning(
                    "Scroll-Schrittbudget (%d) ausgeschöpft, ohne dass sich die "
                    "Trefferzahl für %r stabilisiert hat (zuletzt %d Treffer) - die "
                    "Liste könnte unvollständig geladen worden sein.",
                    steps, stop_selector, letzte_anzahl,
                )
        page.mouse.wheel(0, -1_000_000)
        page.wait_for_timeout(
            random.randint(BROWSER_SCROLL_PAUSE_MIN_MS, BROWSER_SCROLL_PAUSE_MAX_MS)
        )
