# LinkedIn Research Scraper

Wissenschaftliches Projekt (Bachelorarbeit): quelloffenes, nachvollziehbares Scraping-Tool
für LinkedIn-Profile von Freiwilligen, die der Erhebung und Verarbeitung ihrer Profildaten
für das Forschungsvorhaben ausdrücklich zugestimmt haben. Rechtsgrundlage ist diese
informierte Einwilligung (Art. 6 Abs. 1 lit. a DSGVO), nicht die öffentliche Zugänglichkeit
eines Profils. Ziel ist eine transparente Alternative zu Black-Box-Tools (z. B. PhantomBuster),
die sich im rechtlichen/ethischen Rahmen dieser Studie bewegt.

## Architektur

```
linkedin-research-scraper/
├── linkedin_scraper/          # Python-Tool
│   ├── main.py                 # CLI-Menü (Einstiegspunkt)
│   ├── config.py                # Pfade, URLs, Delays, CSV-Spalten, OUTPUT_JSON_DIR
│   ├── models.py                 # Profile/Experience/Education/... Dataclasses
│   ├── fingerprint.py            # leitet EINE Geräteidentität (OS + installierte
│   │                             #   Chrome-Version) ab, für HTTP- und Browser-Weg
│   ├── rate_limiter.py           # zufällige, dreistufige Delays (NFA2)
│   ├── logging_setup.py          # Konsole + Datei-Logging
│   ├── io_handlers/
│   │   ├── input_reader.py        # liest Profil-URLs aus CSV (Kopfzeile "URL", ab Zeile 2)
│   │   ├── csv_writer.py          # eine Ergebnis-CSV (ExportVorlage-Format)
│   │   └── json_writer.py         # je Profil eine <Vorname>_<Nachname>_<TTMMJJJJ>.json
│   ├── fetch/
│   │   ├── http_client.py        # Chrome-TLS-Fingerprint (curl_cffi) + Header/Referer
│   │   ├── fetcher.py             # HTTP GET inkl. Retry/Backoff
│   │   ├── browser_fetcher.py    # Playwright + echtes Chrome: DER Weg für die
│   │   │                          #   client-seitig gerenderten Felder
│   │   ├── dom_utils.py           # DOM-Helfer (get_soup, iter_sdui_entries, ...)
│   │   ├── parser_*.py            # ein Parser je Detailseite (DOM-basiert)
│   │   └── voyager_*.py          # verworfener API-Weg (HTTP 410), bleibt als Negativbefund
│   ├── session/                  # Native-Messaging-Bridge Extension <-> Python.
│   │   │                          #   NICHT mehr im Ablauf (siehe unten), bleibt als
│   │   │                          #   dokumentierter, verworfener Weg im Baum.
│   │   ├── session_manager.py     # baut den HTTP-Client aus einem Cookie-Satz
│   │   └── validator.py           # prüft Login-Status
├── run.py                       # Build-Einstiegspunkt für PyInstaller (siehe unten) -
│                                  #   für den normalen Betrieb weiter `python -m
│                                  #   linkedin_scraper.main` benutzen
├── build.py                     # Ein-Kommando-Setup+Build für einen frischen
│                                  #   Checkout (siehe „Kompilieren")
├── build/                       # PyInstaller-Spezifikation + schnelles Rebuild-Skript
├── LinkedInScraper/             # NICHT Teil des Repos. Die "kanonische" Einheit aus
│   ├── app/                      #   exe + aktiver Session - siehe „Kompilieren". app/
│   └── data/                      #   wird bei jedem Build neu geschrieben, data/ (Input-
│                                  #   CSV, Output-CSV/JSON, Logs, Browser-Profil mit der
│                                  #   Anmeldung) NIE - das ist die Stelle, die bei Bedarf
│                                  #   auf ein anderes Gerät umzieht.
└── browser_extension/          # Chrome/Edge Extension (MV3) — vestigial, s. u.
```

## Authentifizierung: manuelle Anmeldung in einem tool-eigenen Browserprofil

Der Login erfolgt **manuell durch den Bediener im echten Browser**. Das Tool automatisiert
keinen Login und verarbeitet kein Passwort.

Konkret meldet man sich **einmal** über Menüpunkt 1 in einem *tool-eigenen, persistenten*
Chrome-Profil an (`LinkedInScraper/data/browser_profile/`, „Angemeldet bleiben" aktiv
lassen). LinkedIn mintet das Session-Cookie (`li_at`) damit in genau dem Browser, der es
später benutzt — es gibt keinen Gerätewechsel mitten in der Sitzung. Die Anmeldung
überlebt Neustarts; Menüpunkt 2/3 bauen die Session danach automatisch aus diesem Profil.
Lässt sich das Profil auf dieser Maschine nicht öffnen (z. B. weil es von einem anderen
Gerät mitgebracht wurde, siehe „Kompilieren"), legt Menüpunkt 1 automatisch ein frisches
Profil für diese Maschine an — das alte wird dabei nur zeitgestempelt zur Seite gelegt,
nie gelöscht.

> **Warum nicht die Browser-Extension?** Frühere Versionen reichten die Cookies aus dem
> Alltags-Browser per Native Messaging weiter. Das Injizieren einer bestehenden Session in
> einen frisch gestarteten, automatisierten Browser hat bei LinkedIn wiederholt einen
> Logout + Mail-2FA ausgelöst (Gerät/Sitzung inkonsistent). Der Weg wurde in v0.7.0
> entfernt; `browser_extension/` und `session/` bleiben nur als dokumentierter
> Negativbefund im Baum.

## Setup

1. Abhängigkeiten installieren (Python 3.12, am besten in einer eigenen venv):
   ```bash
   py -3.12 -m venv .venv && .venv\Scripts\activate    # optional, empfohlen
   pip install -r requirements.txt
   playwright install chromium   # nur Rückfall; im Normalbetrieb wird über
                                 # BROWSER_CHANNEL = "chrome" das installierte
                                 # Google Chrome benutzt
   ```
2. Profil-URLs der Freiwilligen in einer CSV in `LinkedInScraper/data/input/` eintragen
   (Vorlage: `data/input/input_profiles.example.csv`; der Ordner entsteht beim ersten
   Start, siehe „Kompilieren"). Zeile 1 ist die Kopfzeile `URL` und wird übersprungen;
   ab Zeile 2 eine Profil-URL pro Zeile. Beliebig viele CSVs können dort nebeneinander
   liegen (z. B. eine kleine Testliste neben der vollen Korpusliste) - beim Start von
   Menüpunkt 2 oder dem CSV-Batch-Modus von Menüpunkt 3 wird nummeriert ausgewählt,
   welche davon verwendet wird.
3. Tool starten:
   ```bash
   python -m linkedin_scraper.main
   ```
   Menü:
   ```
   1. Bei LinkedIn anmelden (Tool-Browserprofil)   ← einmalig; Fenster öffnet sich,
                                                     manuell einloggen, dann Enter
   2. Scraping starten (fragt zuerst, welche CSV aus data/input/ verwendet wird)
   3. Debug: Rohdaten einer Detailseite speichern (nur Browser) - einzelnes Profil
      oder, auf Wunsch, alle Seiten für alle Profile einer CSV auf einmal
   4. Browser: Fingerprint prüfen (ohne LinkedIn-Zugriff)
   5. Beenden
   ```
4. Einmal Menüpunkt 1, dann Menüpunkt 2. Kommt es zu einem Fehler (abgelaufene Session,
   Bot-Check), meldet die CLI „Bitte das Tool neu starten. Wenn die Anmeldung abgelaufen
   ist: Menüpunkt 1."

## Ausgabe

- `LinkedInScraper/data/output_csv/output_results_<TTMMJJJJ>.csv` — **eine Datei je
  Kalendertag** (Datum des Laufs im Namen). Mehrere Läufe am selben Tag hängen an
  dieselbe Datei an, statt sie zu überschreiben; ein neuer Tag bekommt eine frische
  Datei mit Header. Feste Spaltenreihenfolge (ExportVorlage-Format). Mehrfach-
  Kategorien (mehrere Stationen usw.) werden positionsbezogen über mehrere Zeilen
  gestapelt. Fehlende Felder: `N/A`.
- `LinkedInScraper/data/output_json/` — **je Profil eine Datei**
  `<Vorname>_<Nachname>_<TTMMJJJJ>.json` mit dem Datum des Laufs (z. B.
  `Martin_Reimann_10092026.json`). Verschachteltes Zielschema (`meta` / `person` +
  Listen `berufserfahrung` / `ausbildung` / `kenntnisse` / `zertifikate` / `sprachen`).
  Fehlende Skalarfelder: `null`.
- **Profil existiert nicht mehr** (URL leitet auf LinkedIns 404-Seite um): CSV-Zeile
  bzw. JSON-`person`-Felder zeigen `404` statt `N/A`/`null` — unterscheidbar von einem
  Profil, das existiert, aber Felder aus Privatsphäre-Gründen nicht zeigt.

## Kompilieren (.exe)

Für den Alltagsgebrauch lässt sich das Tool zu einer eigenständigen `.exe` bauen, statt
jedes Mal `python -m linkedin_scraper.main` in einer aktivierten venv aufzurufen.

**Frischer Checkout (empfohlen):** ein einziger Befehl aus dem Projektstamm erledigt
Abhängigkeiten (Laufzeit + Build), `playwright install chromium` und den eigentlichen
Build in einem Rutsch:

```bash
python build.py
```

**Schnelle Neu-Kompilierung** nach einer Code-Änderung (Abhängigkeiten schon
installiert, deutlich schneller als `build.py`, da Schritte 1-3 übersprungen werden):

```powershell
powershell -File build\build.ps1
```

Beide Wege liefern dasselbe Ergebnis: `LinkedInScraper\app\LinkedInScraper.exe` — dort
per Doppelklick starten.
`LinkedInScraper\` ist bewusst in zwei Unterordner geteilt:

- **`app\`** — die eigentliche exe + alle Binärdateien. Wird bei **jedem** `build.ps1`-
  Lauf komplett neu geschrieben (PyInstaller räumt sein Zielverzeichnis leer).
- **`data\`** — Input-CSV, Output-CSV/JSON, Logs und vor allem das **Browserprofil mit
  der aktiven Anmeldung**. Wird von `build.ps1` nie angefasst und ist damit die
  eigentliche „kanonische" Kopie: Der Quellcode-Betrieb (`python -m
  linkedin_scraper.main`) benutzt **dieselbe** `LinkedInScraper\data\`, nicht eine
  eigene zweite Kopie unter `linkedin_scraper\` — die Anmeldung „gehört" also der exe,
  der Rohcode greift nur darauf zu. Zwei getrennte Browserprofile mit je eigenem Login
  sähen LinkedIn gegenüber wie zwei Geräte mit derselben Sitzung aus — genau das
  Muster, das früher Logouts ausgelöst hat.

**Umzug auf ein anderes Gerät ("zur Not"):** weil `LinkedInScraper\` die exe **und**
die Session in einer in sich geschlossenen Einheit hält, reicht es, den ganzen Ordner
dorthin zu kopieren — kein Quellcode nötig, kein erneutes `pip install`. Läuft das
mitgebrachte Browserprofil auf dem neuen Gerät aus irgendeinem Grund nicht an (andere
Chrome-Version, defektes Profilschema o. ä.), fängt **Menüpunkt 1** das automatisch ab:
das nicht startbare Profil wird zeitgestempelt zur Seite gelegt (`browser_profile_
defekt_<Datum-Zeit>`, nichts wird gelöscht) und durch ein frisches ersetzt — einmal neu
anmelden, fertig. Dieser Automatismus greift **nur** über Menüpunkt 1; beim Scraping
selbst bleibt ein nicht startbares Profil weiterhin ein harter Fehler (sonst könnte ein
Profil, das nur gerade in einem zweiten Fenster offen ist, versehentlich zurückgesetzt
werden).

Es ist eine **onedir**-Anwendung (ein Ordner voller Dateien, keine einzelne
Riesen-`.exe`): Playwright bringt seinen eigenen Treiber (`node.exe` + Treiber-Paket)
mit, curl_cffi ein gebündeltes `libcurl` — beides sind Binärdateien, die bei „onefile"
bei jedem Start neu in einen Temp-Ordner entpackt werden müssten. Nach Code-Änderungen
`build\build.ps1` erneut ausführen, um `app\` zu aktualisieren — `data\` bleibt dabei
unangetastet. Details/Hintergründe zu den PyInstaller-Stolpersteinen (u. a. ein
CPython-3.10.0-Bug, der den Wechsel auf Python 3.12 nötig gemacht hat) stehen im
CHANGELOG (0.7.6/0.7.7).

## Wichtiger Hinweis zu den Parsern

LinkedIn liefert die Profilseiten seit 2026 als **Server-Driven UI** (React-Flight); es
gibt **kein eingebettetes Voyager-JSON** mehr. `fetch/parser_*.py` parsen das **DOM**
gegen stabile, semantische Marker (`data-sdui-screen`, `componentkey`-Präfixe,
`data-testid`), nicht gegen die gehashten CSS-Klassen. Stand:

- **Profilkopf** (Name, Headline, Ort/Bundesland/Land) steht in der server-gerenderten
  Topcard → `parser_profile.py`, läuft über den schnellen HTTP-Weg (curl_cffi).
- **Berufserfahrung** wird ebenfalls serverseitig gerendert → `parser_experience.py`,
  HTTP-Weg, gegen einen echten eingeloggten Dump verifiziert (5/5).
- **E-Mail, Geburtstag, Ausbildung, Kenntnisse, Sprachen, Zertifikate** kommen als leere
  `LazyColumn` bzw. als client-seitig gerendertes Overlay und stehen im reinen HTML nicht
  drin. Das Tool holt sie über den **Browser-Pfad** (`fetch/browser_fetcher.py`,
  Playwright + echtes Chrome, `USE_BROWSER_FOR_LAZY = True`, `BROWSER_HEADLESS = False`).
  Das Kontakt-Overlay wird dabei **angeklickt**, nicht als URL angesprungen (sonst bleibt
  der Popover `inert`). Alle sechs Felder sind gegen echte Daten verifiziert.
- **SDUI v2** (Markup-Stand seit ~09/2026): Einträge sind `<hr>`-getrennte `<div>`-Gruppen
  bzw. Button-begrenzte Zeilen; ein trennerloser Einzeleintrag (z. B. genau ein
  Zertifikat) wird gesondert behandelt. Alles in `dom_utils.iter_sdui_entries`.
- **Verworfen: der Voyager-API-Weg.** Die klassischen REST-Endpunkte antworten seit 2026
  mit **HTTP 410**; der verbleibende GraphQL-Weg bräuchte eine `queryId`, die mit jedem
  LinkedIn-Release rotiert — das widerspricht der Reproduzierbarkeit. `fetch/voyager_*.py`
  bleibt als dokumentierter Negativbefund, `USE_VOYAGER_FOR_LAZY = False`.

Für neue Dumps den Debug-Menüpunkt 3 nutzen (Quelle ist immer der Browser).

## Rechtlicher/Ethischer Rahmen

- Nur Profile von Freiwilligen mit vorliegender Einwilligungserklärung. Rechtsgrundlage ist
  die informierte Einwilligung (Art. 6 Abs. 1 lit. a DSGVO), nicht die öffentliche
  Zugänglichkeit eines Profils.
- Datensparsame Verarbeitung; Pseudonymisierung/Anonymisierung und Löschung der erhobenen
  Daten nach Projektende.
- Zentrale Ausführung durch das Forschungsteam, kein automatisierter Passwort-Login.
- Rate-Limiting standardmäßig aktiv und bewusst konservativ (`config.py`, NFA2). Die
  Verzögerungen sind kein Performance-Fehler, sondern Teil des Rücksichtnahme-Konzepts.
- Dieses Projekt bewegt sich nach eigener Einschätzung von Autor und Betreuer in einem
  rechtlichen Graubereich (LinkedIn-ToS) — das ist Teil der Forschungsfrage, nicht deren
  Ergebnis vorweggenommen.

## Lizenz

[MIT](LICENSE) — der Quellcode darf frei verwendet, verändert und weiterverbreitet
werden. Das erlaubt ausdrücklich NICHT, LinkedIns Nutzungsbedingungen zu umgehen oder
Profile ohne informierte Einwilligung zu scrapen — siehe „Rechtlicher/Ethischer
Rahmen" oben.
