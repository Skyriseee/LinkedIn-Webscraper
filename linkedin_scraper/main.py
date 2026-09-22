"""CLI-Einstiegspunkt: Anmelden, Scrapen, Debug-Dumps.

Die Session kommt ausschließlich aus dem persistenten Tool-Browserprofil (einmal über
Menüpunkt 1 anmelden). Der frühere Weg über die Browser-Extension ist entfallen - die
Cookie-Injektion in einen fremden Browserkontext hat in der Praxis Logouts ausgelöst.
Der Code der Extension-Bridge bleibt im Repo, wird hier aber nicht mehr aufgerufen.
"""
import random
import sys
from datetime import date
from pathlib import Path

from .logging_setup import setup_logging, setup_console_capture
from .config import (
    INPUT_DIR, OUTPUT_CSV_DIR, DEBUG_DUMP_DIR, USE_BROWSER_FOR_LAZY,
    USE_VOYAGER_FOR_LAZY, USE_BROWSER_FOR_CONTACT, BROWSER_USER_DATA_DIR,
    REQUEST_TIMEOUT_SECONDS, URL_SESSION_CHECK, SEND_REFERER_CHAIN,
    URL_PROFILE, URL_CONTACT_INFO, URL_EXPERIENCE, URL_EDUCATION,
    URL_SKILLS, URL_LANGUAGES, URL_CERTIFICATIONS, OUTPUT_JSON_DIR,
    BROWSER_RECYCLE_EVERY_PROFILES, PROFILE_RETRY_ATTEMPTS, PROFILE_NOT_FOUND,
    NOT_AVAILABLE, ensure_data_dirs,
)
from .models import Profile
from .session.session_manager import build_session, SessionError
from .io_handlers.input_reader import read_profile_urls, extract_slug
from .io_handlers.csv_writer import CsvWriter
from .io_handlers.json_writer import JsonWriter
from .rate_limiter import RateLimiter
from .fetch.fetcher import Fetcher, FetchError, ProfileNotFoundError
from .fetch.browser_fetcher import BrowserFetcher
from .fetch.voyager_client import VoyagerClient, VoyagerError
from .fetch.voyager_parser import parse_profile_view, parse_contact_info_json
from .fetch.parser_profile import parse_profile_page
from .fetch.parser_contact import parse_contact_info
from .fetch.parser_experience import parse_experience_page
from .fetch.parser_education import parse_education_page
from .fetch.parser_certifications import parse_certifications_page
from .fetch.parser_languages import parse_languages_page
from .fetch.parser_skills import parse_skills_page
from . import __version__

logger = setup_logging()

# Detailseiten, die LinkedIn erst client-seitig nachlädt und die daher über den
# Browser-Fetcher geholt werden (fetch/browser_fetcher.py).
_LAZY_URLS = (
    (URL_EDUCATION, "educations", parse_education_page),
    (URL_SKILLS, "skills", parse_skills_page),
    (URL_CERTIFICATIONS, "certifications", parse_certifications_page),
    (URL_LANGUAGES, "languages", parse_languages_page),
)


_NOT_LOGGED_IN_MSG = (
    "Im Tool-Browserprofil liegt keine gültige LinkedIn-Anmeldung.\n"
    "  → Menüpunkt 1 wählen und dort einmal manuell anmelden\n"
    "    ('Angemeldet bleiben' aktiviert lassen).\n"
    "  → Falls du dich gerade angemeldet hast: Tool einmal neu starten."
)
_RESTART_HINT = (
    "Bitte das Tool neu starten. Wenn die Anmeldung abgelaufen ist: Menüpunkt 1 "
    "(neu anmelden)."
)


def scrape_profile(fetcher: Fetcher, browser_fetcher, profile_url: str, voyager_client=None):
    slug = extract_slug(profile_url)
    prof_url = URL_PROFILE.format(slug=slug)
    # Referer nur, wenn bewusst aktiviert - sonst kommt die Detailseite als schlanke
    # SPA-Variante (siehe config.SEND_REFERER_CHAIN).
    ref = prof_url if SEND_REFERER_CHAIN else None

    # Kontakt-Overlay zuerst abrufen, VOR Profilseite/Erfahrung: das Overlay wird
    # client-seitig gerendert und ist damit der früheste
    # Punkt im Ablauf, an dem eine Umleitung auf LinkedIns 404-Seite sichtbar wird -
    # die passiert per JS und ist einem reinen HTTP-GET (fetch/fetcher.py) unsichtbar.
    # Existiert das Profil nicht mehr, bricht hier sofort ab, statt zuerst Profilseite,
    # Erfahrung UND alle vier Detailseiten sinnlos abzufragen (Autor-Wunsch 2026-09-13:
    # „da gibt es ja nur Existiert oder existiert nicht ... spart Zeit").
    #
    # Ohne Browser bleibt der HTTP-Weg als dokumentierter Fallback (liefert dann in der
    # Regel N/A) - und ohne Browser lässt sich ein gelöschtes
    # Profil über diesen frühen Abruf ohnehin nicht erkennen (die Umleitung ist ja
    # gerade nur im Browser sichtbar); dafür bleibt fetcher.get_html(prof_url) unten als
    # zweite, wenn auch schwächere Absicherung.
    contact_src = browser_fetcher if (browser_fetcher is not None and USE_BROWSER_FOR_CONTACT) else fetcher
    email, geburtstag = NOT_AVAILABLE, NOT_AVAILABLE
    try:
        contact = parse_contact_info(
            contact_src.get_html(URL_CONTACT_INFO.format(slug=slug), referer=ref)
        )
        email, geburtstag = contact["email"], contact["geburtstag"]
    except ProfileNotFoundError as exc:
        logger.warning("Profil existiert nicht (mehr): %s (%s)", profile_url, exc)
        return _not_found_profile(profile_url)
    except FetchError as exc:
        logger.error("Kontakt-Overlay übersprungen (%s): %s", slug, exc)
        _raise_if_browser_crashed(browser_fetcher, contact_src, profile_url, exc)

    try:
        profile_html = fetcher.get_html(prof_url)
    except ProfileNotFoundError as exc:
        logger.warning("Profil existiert nicht (mehr): %s (%s)", profile_url, exc)
        return _not_found_profile(profile_url)

    profile = parse_profile_page(profile_html, profile_url)
    profile.email, profile.geburtstag = email, geburtstag

    profile.experiences = parse_experience_page(
        fetcher.get_html(URL_EXPERIENCE.format(slug=slug), referer=ref)
    )

    # Vier client-seitig nachgeladene Listen-Felder: bevorzugt über die Voyager-API
    # (ein profileView-Call deckt Ausbildung/Kenntnisse/Sprachen/Zertifikate ab, dazu
    # profileContactInfo für E-Mail/Geburtstag - überschreibt dann die oben schon
    # gesetzten Werte). `covered` = die Sektionen, die Voyager tatsächlich geliefert
    # hat und die daher nicht noch einmal über HTML geholt werden müssen. In der Praxis
    # ungenutzt (USE_VOYAGER_FOR_LAZY=False, siehe config.py „Verworfener Weg").
    covered = _fill_from_voyager(voyager_client, slug, profile) if voyager_client else set()

    # Übrige Listen-Sektionen über den Browser-Fetcher (falls aktiv) bzw. requests
    # (liefert dann []). Reihenfolge je Profil zufällig, damit das Zugriffsmuster
    # nicht immer gleich ist.
    lazy_fetcher = browser_fetcher or fetcher
    remaining = [t for t in _LAZY_URLS if t[1] not in covered]
    random.shuffle(remaining)
    for url_template, attr, parse_fn in remaining:
        url = url_template.format(slug=slug)
        try:
            setattr(profile, attr, parse_fn(lazy_fetcher.get_html(url, referer=ref)))
        except ProfileNotFoundError as exc:
            logger.warning("Profil existiert nicht (mehr): %s (%s)", profile_url, exc)
            return _not_found_profile(profile_url)
        except FetchError as exc:
            logger.error("Lazy-Sektion übersprungen (%s): %s", url, exc)
            _raise_if_browser_crashed(browser_fetcher, lazy_fetcher, profile_url, exc)

    return profile


def _not_found_profile(profile_url: str) -> Profile:
    """Profil-Objekt für eine URL, die auf LinkedIns 404-Seite umgeleitet hat (Profil
    existiert nicht mehr). Alle Personenfelder werden auf PROFILE_NOT_FOUND ("404")
    gesetzt statt auf NOT_AVAILABLE ("N/A") - so lässt sich in CSV/JSON unterscheiden
    "Profil gibt es nicht mehr" von "Profil existiert, Felder aber leer" (Autor-Wunsch
    2026-09-14). Kategorie-Listen (Erfahrung, Ausbildung, ...) bleiben leer - es gibt
    nichts zu holen, und ein leeres Profil mit `not_found=True` sagt bereits alles."""
    profile = Profile(profile_url=profile_url, not_found=True)
    for feld in ("vorname", "nachname", "titel", "ort", "bundesland", "land", "email", "geburtstag"):
        setattr(profile, feld, PROFILE_NOT_FOUND)
    return profile


def _raise_if_browser_crashed(browser_fetcher, used_fetcher, profile_url: str, exc: Exception) -> None:
    """Bricht das GANZE Profil ab, sobald der Browser abgestürzt ist, statt für jede
    weitere Sektion denselben Fehler einzeln zu bekommen und am Ende ein Profil mit
    lauter N/A-Feldern zu schreiben.
    `run_scraping` fängt das auf, startet den Browser neu und versucht das Profil von
    vorn (config.PROFILE_RETRY_ATTEMPTS)."""
    if browser_fetcher is not None and used_fetcher is browser_fetcher and browser_fetcher.crashed:
        raise FetchError(
            f"Browser-Sitzung abgestürzt beim Abruf von {profile_url} - Profil wird "
            f"(falls Versuche übrig sind) von vorn versucht. ({exc})"
        ) from exc


def _fill_from_voyager(voyager_client, slug: str, profile) -> set[str]:
    """Füllt E-Mail/Geburtstag + die vier Listen-Sektionen aus der Voyager-API.
    Gibt die Namen der abgedeckten Bereiche zurück (`educations`, `skills`,
    `languages`, `certifications`, `contact`), damit sie nicht noch einmal über
    HTML/Browser geholt werden."""
    covered: set[str] = set()
    try:
        pv = voyager_client.profile_view(slug)
    except VoyagerError as exc:
        logger.warning("Voyager profileView fehlgeschlagen für %s: %s - HTML-Fallback aktiv.", slug, exc)
    else:
        parsed = parse_profile_view(pv)
        for attr in ("educations", "skills", "languages", "certifications"):
            setattr(profile, attr, parsed[attr])
            covered.add(attr)

    try:
        ci = voyager_client.contact_info(slug)
    except VoyagerError as exc:
        logger.warning("Voyager profileContactInfo fehlgeschlagen für %s: %s - HTML-Fallback aktiv.", slug, exc)
    else:
        parsed_ci = parse_contact_info_json(ci)
        profile.email = parsed_ci["email"]
        profile.geburtstag = parsed_ci["geburtstag"]
        covered.add("contact")

    return covered


def _choose_input_csv() -> Path | None:
    """Listet alle *.csv in config.INPUT_DIR nummeriert auf und lässt den Bediener
    eine davon auswählen (Autor-Wunsch 2026-09-14: statt immer stur dieselbe feste
    Datei zu lesen, z. B. um gezielt gegen eine kleine Testliste statt den vollen
    Korpus zu laufen). Gibt `None` zurück, wenn keine CSV gefunden wurde oder die
    Auswahl ungültig/abgebrochen ist - der Aufrufer muss das behandeln."""
    kandidaten = sorted(INPUT_DIR.glob("*.csv"))
    if not kandidaten:
        print(f"Keine CSV-Dateien in {INPUT_DIR} gefunden.")
        return None
    print(f"Verfügbare Eingabelisten ({INPUT_DIR}):")
    for i, pfad in enumerate(kandidaten, start=1):
        print(f"  {i}. {pfad.name}")
    auswahl = input(f"Welche Liste? (1-{len(kandidaten)}): ").strip()
    try:
        index = int(auswahl)
        if not (1 <= index <= len(kandidaten)):
            raise ValueError
    except ValueError:
        print("Ungültige Auswahl.")
        return None
    return kandidaten[index - 1]


def run_scraping(fetcher: Fetcher, browser_fetcher, voyager_client=None,
                  input_csv_path: Path | None = None) -> None:
    urls = read_profile_urls(input_csv_path)
    if not urls:
        print(f"Keine Profil-URLs in {input_csv_path} gefunden.")
        return

    # Kein hartes Abschneiden nach N Profilen mehr (bis v0.7.12: MAX_PROFILES_PER_RUN =
    # 25) - stattdessen legt der RateLimiter alle EXTRA_LONG_PAUSE_EVERY_PROFILES eine
    # deutlich längere Pause ein (siehe rate_limiter.py), damit auch größere Korpora in
    # einem Lauf durchlaufen, ohne die Politeness gegenüber LinkedIn zu verletzen.

    # Aufwärm-Request wie ein Mensch, der aus seinem Feed heraus zu browsen beginnt -
    # bewusst HIER, VOR der Profil-Schleife, abgeschlossen. Bis v0.7.14 lief das
    # Aufwärmen des Browsers lazy beim ERSTEN Browser-Zugriff (z. B. Kontakt-Overlay)
    # - das passierte mitten im ersten Profil, nachdem für dieses Profil bereits
    # Profilseite und Erfahrung per HTTP abgerufen worden waren (Autor-Fund
    # 2026-09-13: reihenfolgetechnisch falsch). `warm_up_now()` startet den Browser
    # und wärmt ihn sofort auf, sodass die Sitzung vollständig steht, bevor überhaupt
    # ein Profil angefasst wird. Mit browser_fetcher=None (Browser-Weg deaktiviert)
    # bleibt der einfache HTTP-Feed-Abruf als Ersatz.
    if browser_fetcher is not None:
        browser_fetcher.warm_up_now()
    else:
        try:
            fetcher.get_html(URL_SESSION_CHECK)
        except FetchError as exc:
            logger.warning("Aufwärm-Request auf den Feed fehlgeschlagen: %s", exc)

    run_date = date.today()
    json_writer = JsonWriter(OUTPUT_JSON_DIR, run_date=run_date)
    with CsvWriter(OUTPUT_CSV_DIR, run_date=run_date) as writer:
        for i, url in enumerate(urls, start=1):
            print(f"[{i}/{len(urls)}] Scrape {url}")
            profile = None
            for versuch in range(1, PROFILE_RETRY_ATTEMPTS + 2):
                try:
                    profile = scrape_profile(fetcher, browser_fetcher, url, voyager_client)
                    break
                except FetchError as exc:
                    # Nur bei einem erkannten Browser-Absturz erneut versuchen (siehe
                    # BrowserFetcher.crashed) - ein Retry hilft nicht gegen andere
                    # Fehler wie Authwall/Checkpoint (Session ungültig) oder ein Profil,
                    # das schlicht keine Kontaktdaten freigibt; da bleibt es wie zuvor
                    # bei einem einzigen Versuch.
                    ist_absturz = browser_fetcher is not None and browser_fetcher.crashed
                    if not ist_absturz or versuch > PROFILE_RETRY_ATTEMPTS:
                        logger.error("Übersprungen (%s): %s", url, exc)
                        break
                    # Browser neu starten (Anmeldung im persistenten Profil bleibt,
                    # siehe recycle()) und GENAU DIESES Profil von vorn versuchen,
                    # statt den ganzen Lauf neu zu starten oder ein nur teilweise
                    # erhobenes Profil zu schreiben.
                    print(f"  Browser abgestürzt - {url} wird nach Neustart erneut "
                          f"versucht ({versuch}/{PROFILE_RETRY_ATTEMPTS}): {exc}")
                    browser_fetcher.recycle()

            if profile is not None:
                writer.write_profile(profile)
                json_writer.write_profile(profile)

            fetcher.rate_limiter.profile_done()

            # Speicherhygiene: den Browser-Kontext alle N Profile neu aufsetzen, damit
            # der RAM-Verbrauch über lange Läufe nicht anwächst (relevant auf schwacher
            # Hardware). Die Anmeldung im persistenten Tool-Profil überlebt das.
            if (browser_fetcher is not None and BROWSER_RECYCLE_EVERY_PROFILES
                    and i < len(urls) and i % BROWSER_RECYCLE_EVERY_PROFILES == 0):
                browser_fetcher.recycle()

            if i < len(urls):
                fetcher.rate_limiter.between_profiles()

    print(f"Fertig.\n  CSV : {writer.output_path}\n  JSON: {OUTPUT_JSON_DIR} (eine Datei je Profil)")


# (Auswahl-Ziffer, Anzeigename, URL-Template, Dateiname-Kürzel)
DEBUG_PAGE_TYPES = [
    ("1", "Profil", URL_PROFILE, "profil"),
    ("2", "Kontakt", URL_CONTACT_INFO, "kontakt"),
    ("3", "Erfahrung", URL_EXPERIENCE, "erfahrung"),
    ("4", "Ausbildung", URL_EDUCATION, "ausbildung"),
    ("5", "Kenntnisse", URL_SKILLS, "kenntnisse"),
    ("6", "Sprachen", URL_LANGUAGES, "sprachen"),
    ("7", "Zertifikate", URL_CERTIFICATIONS, "zertifikate"),
]
DEBUG_ALL_CHOICE = "8"


def _dump_single_page(browser_fetcher, url_template: str, page_slug: str,
                      profile_slug: str) -> None:
    """Holt eine Detailseite über den Browser und speichert sie als
    debug_dump_<seite>_<profil-slug>_browser.html.

    Nur noch der Browser-Weg: der HTTP-Weg (curl_cffi) rendert die client-seitigen
    Sektionen nicht (Kontakt-Overlay, Ausbildung, Kenntnisse, Sprachen, Zertifikate)
    und wird für Debug-Dumps nicht mehr gebraucht. Das `_browser`-Kürzel bleibt im
    Dateinamen, damit alte HTTP-Vergleichsdumps nicht überschrieben werden."""
    referer = URL_PROFILE.format(slug=profile_slug) if (SEND_REFERER_CHAIN and page_slug != "profil") else None
    html = browser_fetcher.get_html(url_template.format(slug=profile_slug), referer=referer)
    DEBUG_DUMP_DIR.mkdir(parents=True, exist_ok=True)
    path = DEBUG_DUMP_DIR / f"debug_dump_{page_slug}_{profile_slug}_browser.html"
    path.write_text(html, encoding="utf-8")
    print(f"Rohdaten gespeichert: {path}")


DEBUG_VOYAGER_CHOICE = "9"


def _dump_voyager_json(voyager_client: VoyagerClient, profile_slug: str) -> None:
    """Speichert die Roh-JSON von profileView + profileContactInfo, damit die
    Feldzuordnung in voyager_parser.py gegen das echte Profil geprüft werden kann."""
    import json
    DEBUG_DUMP_DIR.mkdir(parents=True, exist_ok=True)
    for name, getter in (("profileview", voyager_client.profile_view),
                         ("contactinfo", voyager_client.contact_info)):
        try:
            data = getter(profile_slug)
        except VoyagerError as exc:
            print(f"  {name}: FEHLER - {exc}")
            continue
        path = DEBUG_DUMP_DIR / f"debug_voyager_{name}_{profile_slug}.json"
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  {name}: {path}")


def run_debug_dump(fetcher: Fetcher, browser_fetcher, voyager_client=None) -> None:
    """Speichert die Rohdaten einer oder aller Detailseiten zur manuellen Inspektion der
    DOM-Struktur (data-testid / componentkey).

    Seiten-Dumps laufen nur noch über den Browser (der HTTP-Weg rendert die
    client-seitigen Sektionen nicht). `fetcher` wird nur für den Voyager-JSON-Zweig
    (Menüziffer 9) gehalten, der ohnehin toter, dokumentierter Negativbefund ist.

    NEU v0.7.25: der CSV-Batch-Weg (v0.7.22/23 - eine ganze Eingabeliste auf einmal
    dumpen) ist wieder entfernt (Autor-Wunsch 2026-09-14: „das Debug Update komplett
    zurück rollen" - Einzel- UND Batch-Dump scheiterten nach den v0.7.22/23-Änderungen
    an derselben LinkedIn-Fehlerseite, sogar am eigenen, seit Projektbeginn
    verlässlichen Referenzprofil). Dieses Modul fragt wieder ausschließlich nach
    einem einzelnen, per Hand eingetippten Profil-Slug, wie vor v0.7.22 - keine
    CSV-Auswahl mehr an dieser Stelle (Menüpunkt 2/Scraping ist davon nicht
    betroffen, `_choose_input_csv()` bleibt dort unverändert im Einsatz)."""
    _ = fetcher
    optionen = "  ".join(f"{ziffer}={name}" for ziffer, name, _, _ in DEBUG_PAGE_TYPES)
    voyager_hint = f"  {DEBUG_VOYAGER_CHOICE}=Voyager-JSON" if voyager_client is not None else ""
    print(f"Welche Seite? {optionen}  {DEBUG_ALL_CHOICE}=Alle Seiten{voyager_hint}")
    choice = input("Auswahl: ").strip()

    if choice == DEBUG_VOYAGER_CHOICE and voyager_client is not None:
        profile_slug = input("Profil-Slug (z.B. max-mustermann-123abc): ").strip()
        print("Hole Voyager-JSON...")
        _dump_voyager_json(voyager_client, profile_slug)
        return

    if choice != DEBUG_ALL_CHOICE and choice not in {c for c, _, _, _ in DEBUG_PAGE_TYPES}:
        print("Ungültige Auswahl.")
        return

    if browser_fetcher is None:
        print("Kein Browser verfügbar - Debug-Dumps laufen nur noch über den Browser.")
        return

    profile_slug = input("Profil-Slug (z.B. max-mustermann-123abc): ").strip()

    if choice == DEBUG_ALL_CHOICE:
        for _, name, url_template, page_slug in DEBUG_PAGE_TYPES:
            print(f"Hole {name}...")
            try:
                _dump_single_page(browser_fetcher, url_template, page_slug, profile_slug)
            except FetchError as exc:
                logger.error("Übersprungen (%s): %s", name, exc)
        print("Alle Seiten fertig.")
        return

    _, _, url_template, page_slug = next(pt for pt in DEBUG_PAGE_TYPES if pt[0] == choice)
    _dump_single_page(browser_fetcher, url_template, page_slug, profile_slug)


def _open_session(rate_limiter):
    """Baut Fetcher + BrowserFetcher (+ optional VoyagerClient) aus der im
    Tool-Browserprofil gespeicherten Anmeldung.

    Wirft `SessionError` mit klarer Handlungsanweisung, wenn dort keine gültige
    Anmeldung liegt. Gibt `(fetcher, browser_fetcher, voyager_client|None)` zurück.
    """
    if not USE_BROWSER_FOR_LAZY:
        raise SessionError(
            "USE_BROWSER_FOR_LAZY steht in config.py auf False - dann gibt es kein "
            "Tool-Browserprofil, aus dem die Session kommen könnte. Bitte auf True setzen."
        )

    browser_fetcher = BrowserFetcher({}, rate_limiter)
    try:
        cookies = browser_fetcher.session_cookies()
    except Exception as exc:
        browser_fetcher.close()
        raise SessionError(f"Tool-Browserprofil nicht lesbar: {exc}\n{_RESTART_HINT}") from exc

    if not cookies.get("li_at"):
        browser_fetcher.close()
        raise SessionError(_NOT_LOGGED_IN_MSG)

    try:
        session = build_session(cookies, "Tool-Browserprofil")
    except SessionError:
        browser_fetcher.close()
        raise

    fetcher = Fetcher(session, rate_limiter)
    voyager_client = None
    if USE_VOYAGER_FOR_LAZY:
        voyager_client = VoyagerClient(session, rate_limiter)
        print("Voyager-API aktiv für E-Mail/Geburtstag/Ausbildung/Kenntnisse/Sprachen/Zertifikate.")
    print("Session aus dem Tool-Browserprofil geladen und geprüft.")
    return fetcher, browser_fetcher, voyager_client


def _run_fingerprint_check(existing_bf=None) -> None:
    """Zeigt die Merkmale, an denen Automatisierung typischerweise auffällt.

    Bewusst OHNE LinkedIn-Zugriff: der Umbau lässt sich damit prüfen, ohne einen
    Account zu riskieren. Gemessen wird auf example.com,
    weil navigator.userAgentData und deviceMemory nur im Secure Context existieren -
    auf about:blank kämen sie fälschlich als null zurück.

    Läuft schon eine Session, wird deren Browser mitbenutzt (das persistente Profil
    kann nur EIN Chromium gleichzeitig öffnen).
    """
    import json
    bf = existing_bf or BrowserFetcher({})
    try:
        bf._ensure_browser()
        bf._page.goto("https://example.com", wait_until="domcontentloaded")
        fp = bf.fingerprint()
    except FetchError as exc:
        print(f"Fehler: {exc}")
        return
    finally:
        if existing_bf is None:
            bf.close()

    print(json.dumps(fp, indent=2, ensure_ascii=False))
    print()
    print("Bewertung:")
    checks = [
        ("navigator.webdriver ist nicht gesetzt", fp.get("webdriver") in (None, False)),
        ("UA nennt Windows, platform passt dazu",
         ("Windows" in (fp.get("userAgent") or "")) == (fp.get("platform") == "Win32")),
        ("Brands enthalten 'Google Chrome' (echtes Chrome, kein Bare-Chromium)",
         any("Google Chrome" in (b or {}).get("brand", "") for b in (fp.get("brands") or []))),
        ("WebGL meldet echte Hardware (kein SwiftShader)",
         "swiftshader" not in (fp.get("webglRenderer") or "").lower()),
        ("Plugins vorhanden", (fp.get("pluginCount") or 0) > 0),
    ]
    for text, ok in checks:
        print(f"  [{'OK ' if ok else '!! '}] {text}")


def _open_profile_for_login() -> None:
    """Öffnet das Tool-Browserprofil sichtbar zur einmaligen manuellen Anmeldung.

    Das ist der einzige Login-Weg: die Anmeldung entsteht NATIV in diesem Profil,
    LinkedIn kennt das Gerät, und die Cookies haben ein Ablaufdatum - sie überleben
    Neustarts und gelten Tage später weiter als dieselbe, bekannte Sitzung.
    Danach genügen die Menüpunkte 2/3.
    """
    # block_assets=False: der Bediener soll die Anmeldeseite normal gerendert sehen.
    # allow_profile_reset=True: NUR hier, im expliziten Anmelde-Ablauf, darf ein nicht
    # startbares Profil (z.B. von einer anderen Maschine mitgebracht) automatisch zur
    # Seite gelegt und durch ein frisches ersetzt werden (siehe browser_fetcher.py
    # _reset_profile_and_relaunch).
    bf = BrowserFetcher({}, headless=False, block_assets=False, allow_profile_reset=True)
    cookies: dict[str, str] = {}
    dauerhaft = False
    try:
        bf.open_for_manual_login()
        print("Browser ist offen. Jetzt dort bei LinkedIn anmelden.")
        print("Wichtig: 'Angemeldet bleiben' aktiviert lassen - sonst gilt die Anmeldung")
        print("nur bis zum Schliessen des Browsers.")
        input("Wenn die Anmeldung steht: Enter drücken. ")
        cookies = bf.session_cookies()
        try:
            roh = bf._context.cookies("https://www.linkedin.com/")
            dauerhaft = any(
                c.get("name") == "li_at" and (c.get("expires") or -1) > 0 for c in roh
            )
        except Exception:
            dauerhaft = False
    except FetchError as exc:
        print(f"Fehler: {exc}")
    finally:
        bf.close()

    print()
    if not cookies.get("li_at"):
        print("Es liegt KEINE Anmeldung im Tool-Profil (kein li_at gefunden).")
        print("Bitte Menüpunkt 5 wiederholen und die Anmeldung wirklich abschliessen.")
        return

    print(f"Anmeldung gespeichert ({len(cookies)} Cookies) unter:")
    print(f"  {BROWSER_USER_DATA_DIR}")
    if dauerhaft:
        print("Das li_at-Cookie hat ein Ablaufdatum - die Anmeldung überlebt Neustarts.")
    else:
        print("ACHTUNG: Das li_at-Cookie ist ein reines Sitzungs-Cookie und verschwindet")
        print("beim Schliessen des Browsers. Bitte erneut anmelden und dabei")
        print("'Angemeldet bleiben' aktiviert lassen.")
    print("Die Menüpunkte 2 und 3 benutzen ab jetzt diese Anmeldung.")


def _ensure_session(state: dict) -> bool:
    """Stellt sicher, dass in `state` eine Session liegt. Baut sie beim ersten Mal aus
    dem Tool-Browserprofil. Gibt True zurück, wenn danach eine Session da ist."""
    if state.get("fetcher") is not None:
        return True
    try:
        state["rate_limiter"] = state.get("rate_limiter") or RateLimiter()
        fetcher, browser_fetcher, voyager_client = _open_session(state["rate_limiter"])
    except (SessionError, TimeoutError) as exc:
        print(f"\n{exc}")
        return False
    state.update(fetcher=fetcher, browser_fetcher=browser_fetcher, voyager_client=voyager_client)
    return True


def _set_console_quick_edit(enabled: bool) -> None:
    """Windows-Konsolen pausieren per Voreinstellung den GANZEN Prozess, sobald man mit
    der Maus hineinklickt/markiert ("QuickEdit"-Modus) - erst Enter/Escape setzt den
    Lauf fort. Bei einem länger laufenden Scraping-Lauf ist ein versehentlicher Klick
    genau das Risiko, das vermieden werden soll (Autor-Wunsch 2026-09-13).

    `main()` schaltet QuickEdit für die Dauer JEDES Menüpunkts aus und direkt danach
    wieder ein (`enabled=True`) - sonst lässt sich z. B. eine Fehlermeldung nach
    Abschluss eines Laufs nicht mehr per Maus markieren/kopieren (zweiter Autor-Wunsch
    2026-09-13: „nach Abschluss des Moduls, egal welchen, wieder freigegeben").

    Rein kosmetisch/bequemlichkeitshalber - schlägt best-effort fehl, wenn keine echte
    Windows-Konsole vorliegt (z. B. unter einer IDE oder bei umgeleitetem stdin) oder
    unter einem anderen Betriebssystem, und darf den Ablauf nie verhindern.
    """
    if sys.platform != "win32":
        return
    try:
        import ctypes

        STD_INPUT_HANDLE = -10
        ENABLE_QUICK_EDIT_MODE = 0x0040
        ENABLE_EXTENDED_FLAGS = 0x0080

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(STD_INPUT_HANDLE)
        mode = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return  # keine echte Konsole - nichts zu tun
        if enabled:
            neuer_modus = mode.value | ENABLE_QUICK_EDIT_MODE | ENABLE_EXTENDED_FLAGS
        else:
            neuer_modus = (mode.value & ~ENABLE_QUICK_EDIT_MODE) | ENABLE_EXTENDED_FLAGS
        kernel32.SetConsoleMode(handle, neuer_modus)
    except Exception:
        pass


def main() -> None:
    # data/ liegt außerhalb des Quellcodes und wird nicht versioniert - bei einem
    # frischen Checkout existiert der Ordner noch nicht. Muss vor allem anderen
    # (auch vor setup_console_capture(), die bereits in data/logs/ schreibt) stehen.
    ensure_data_dirs()

    # Auf einer Windows-Konsole (cp1252) kann ein Sonderzeichen in einer Fehlermeldung
    # sonst den ganzen Lauf mit UnicodeEncodeError abbrechen - lieber ersetzen als crashen.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except Exception:
            pass

    # Ab hier landet ALLES, was auf der Konsole erscheint (print() UND ein
    # unbehandelter Absturz-Traceback), zusätzlich in der Tages-Logdatei unter
    # data/logs/ (config.log_file_path()) - Copy/Paste aus der Konsole ist während
    # eines laufenden Menüpunkts gesperrt (_set_console_quick_edit), und schließt
    # sich das Fenster oder stürzt der Prozess ab, wäre der reine Bildschirminhalt
    # sonst komplett verloren.
    setup_console_capture()

    state: dict = {"fetcher": None, "browser_fetcher": None, "voyager_client": None,
                   "rate_limiter": None}

    try:
        while True:
            print(f"\n--- LinkedIn Research Scraper (v{__version__}) ---")
            angemeldet = "  (angemeldet)" if state["fetcher"] else ""
            print("1. Bei LinkedIn anmelden (Tool-Browserprofil)")
            print("2. Scraping starten" + angemeldet)
            print("3. Debug: Rohdaten einer Detailseite speichern" + angemeldet)
            print("4. Browser: Fingerprint prüfen (ohne LinkedIn-Zugriff)")
            print("5. Beenden")
            choice = input("Auswahl: ").strip()

            # QuickEdit nur WÄHREND des gewählten Moduls aus - direkt danach (jeder
            # Ausgang aus diesem Block, auch bei Fehler) wieder frei, damit sich z. B.
            # eine Fehlermeldung nach Abschluss per Maus markieren/kopieren lässt
            # (Autor-Wunsch 2026-09-13).
            if choice in ("1", "2", "3", "4"):
                _set_console_quick_edit(False)
            try:
                if choice == "1":
                    if state["browser_fetcher"] is not None:
                        print("Es läuft bereits eine Session (das Tool-Profil ist geöffnet).\n"
                              "Zum Neu-Anmelden bitte das Tool beenden (5) und neu starten.")
                        continue
                    _open_profile_for_login()

                elif choice == "2":
                    if not _ensure_session(state):
                        continue
                    input_csv_path = _choose_input_csv()
                    if input_csv_path is None:
                        continue
                    try:
                        run_scraping(state["fetcher"], state["browser_fetcher"],
                                     state["voyager_client"], input_csv_path)
                    except FetchError as exc:
                        print(f"\nScraping abgebrochen: {exc}\n{_RESTART_HINT}")

                elif choice == "3":
                    if not _ensure_session(state):
                        continue
                    try:
                        run_debug_dump(state["fetcher"], state["browser_fetcher"],
                                       state["voyager_client"])
                    except FetchError as exc:
                        print(f"\nDump abgebrochen: {exc}\n{_RESTART_HINT}")

                elif choice == "4":
                    _run_fingerprint_check(state["browser_fetcher"])

                elif choice == "5":
                    break

                else:
                    print("Ungültige Auswahl.")
            finally:
                if choice in ("1", "2", "3", "4"):
                    _set_console_quick_edit(True)
    finally:
        if state.get("browser_fetcher") is not None:
            state["browser_fetcher"].close()


if __name__ == "__main__":
    main()
