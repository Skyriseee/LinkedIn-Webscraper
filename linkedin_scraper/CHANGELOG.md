# Changelog - LinkedIn Research Scraper (Python-Tool)

Nur inhaltliche Änderungen am Python-Code selbst (nicht Setup-/Umgebungsschritte wie
Registry-Registrierung oder das Anpassen von Windows-Einstellungen).

## 0.7.31
- **v0.7.30 reichte NICHT aus - Kenntnisse-Liste bei Vaibhav Grover trotz vollem
  Schrittbudget (40) diesmal nur 50 statt 98 erfasst** (Autor-Fund 2026-09-15, direkt
  nach dem Neubau/Re-Scrape mit v0.7.30). Erneut ein sauberes Präfix (kein zufälliges
  Muster), diesmal aber OHNE die in v0.7.30 neu eingeführte "Schrittbudget
  ausgeschöpft"-Warnung im Log - die Scroll-Schleife hat also über `break` regulär
  über die Stabilitätsprüfung abgebrochen, nicht durch Erschöpfen des Budgets. **Root
  Cause:** die Stabilitätsprüfung akzeptierte bisher 2 aufeinanderfolgende
  Scroll-Runden mit gleicher Trefferzahl als "fertig geladen" - bei nur der normalen,
  kurzen Scroll-Pause (max. 1,2 s pro Runde) dazwischen. LinkedIns LazyColumn lädt
  lange Listen in Batches nach; braucht ein Batch länger als diese kurze Pause, sieht
  ein Zwischenstand rein zufällig 2 Runden lang "stabil" aus, obwohl der nächste Batch
  nur noch nicht gerendert ist - die Schleife bricht dann vorzeitig ab. **Fix:** vor
  dem eigentlichen Abbruch wird die Trefferzahl jetzt einmal mit einer deutlich
  längeren Wartezeit (`BROWSER_SCROLL_STABILITY_CONFIRM_MS = 3000`, angelehnt an
  `BROWSER_ENTRY_WAIT_MS`, den an anderer Stelle bereits etablierten Richtwert für
  LinkedIns Nachlade-Dauer) gegengeprüft; hat sie sich in dieser Zeit doch noch
  erhöht, war es keine echte Stabilität und es wird weitergescrollt. **Kein
  Live-Test möglich** (kein eigener Browser-Zugriff) - Fix beruht auf der Logauswertung
  (kein Budget-Erschöpfungs-Log trotz unvollständiger Liste ⇒ vorzeitiger,
  stabilitätsbasierter Abbruch) und schließt die Lücke, die v0.7.30 noch offen ließ.
  Nächster echter Scrape von Vaibhav Grover sollte 98 Kenntnisse liefern - falls
  weiterhin nicht, deutet das auf eine noch längere oder variablere Batch-Ladezeit
  hin, die eine größere Anpassung bräuchte.

## 0.7.30
- **Lange Kenntnisse-Listen konnten durch das randomisierte Scroll-Schrittbudget
  still gekürzt werden** (Autor-Fund 2026-09-15, im Zuge des Referenzabgleichs von
  10 Profilen gegen `Referenz JSONs`: Vaibhav Grover lieferte nur 80 statt 98
  Kenntnisse - und zwar exakt als Präfix der echten Liste, um die letzten 18
  Einträge gekürzt, nicht zufällig verstreut). Ursache: `_scroll_through()`
  (`fetch/browser_fetcher.py`) würfelte die tatsächliche Schrittzahl auch bei
  gesetztem `stop_selector` (Ziel-Selektor, z. B. für Kenntnisse-Einträge) aus dem
  VOLLEN Bereich `random.randint(BROWSER_SCROLL_STEPS_MIN=6, max_steps)` - obwohl
  `max_steps` für diesen Fall extra auf 40 angehoben wird
  (`BROWSER_SCROLL_STEPS_MAX_WITH_TARGET`), konnte der gewürfelte Wert trotzdem nur
  6 betragen. Bei einer langen Liste (98 Einträge) reichen 6 Scroll-Schritte nicht,
  um alles nachzuladen - die Schleife lief dann einfach durch, OHNE dass die
  eigentlich vorgesehene Stabilitätsprüfung (2 Runden ohne Zuwachs der Trefferzahl)
  je zum Tragen kam, und OHNE jede Warnung. **Fix:** bei gesetztem `stop_selector`
  ist die Schrittzahl jetzt fest `max_steps` (40) statt gewürfelt - `max_steps` war
  ohnehin als Sicherheitsobergrenze gedacht, das eigentliche Abbruchkriterium bleibt
  die Stabilitätsprüfung. Ohne Ziel-Selektor (Aufwärm-Scroll auf dem Feed, keine
  Vollständigkeits-Erwartung) bleibt die bisherige Zufallsstreuung unverändert.
  Zusätzlich neue Warnung, falls das Schrittbudget je ausgeschöpft wird, ohne dass
  sich die Trefferzahl stabilisiert hat (`for`/`else` auf die Scroll-Schleife) -
  macht eine mögliche künftige Kürzung sichtbar statt still (DQ4). **Kein
  Live-Test gegen echtes LinkedIn möglich** (kein eigener Browser-Zugriff) - Fix
  beruht auf der eindeutigen Beweislage (sauberer Präfix-Schnitt bei Vaibhav
  Grover) und der Logik der bestehenden Stabilitätsprüfung; nächster echter Scrape
  von Vaibhav Grover sollte 98 statt 80 Kenntnisse liefern.

## 0.7.29
- **Standort ging bei Mehrfach-Positionen innerhalb einer Firma verloren, obwohl er im
  DOM vorhanden war** (Autor-Fund 2026-09-15, an Marcel Merkel/TeamBank AG entdeckt:
  "Nürnberg" fehlte bei allen drei TeamBank-Rollen). Ursache: `_parse_multi_position_group()`
  übernahm für ALLE Rollen einer Gruppe ausnahmslos den Standort aus dem Gruppen-Header
  (`_group_header()`); hatte dieser (wie bei TeamBank AG) selbst keinen eigenen
  Standort-Absatz, ging der Standort verloren - obwohl die aktuellste Rolle
  ("Lead Cloud Computing") direkt nach ihrem eigenen Zeitraum einen eigenen
  Standort-Absatz ("Nürnberg, Bayern, Deutschland") im DOM hatte, der bisher komplett
  ignoriert wurde (jeder Absatz nach Zeitraum/Arbeitsverhältnis wurde bisher verworfen).
  **Fix:** `_parse_multi_position_group()` prüft jetzt zusätzlich den Absatz direkt nach
  dem erkannten Zeitraum jeder einzelnen Rolle auf `_looks_like_location()` und nutzt ihn
  als Standort, falls gültig; sonst bleibt der Gruppen-Header-Standort als Fallback.
  Bei der Verifizierung gegen den echten Marcel-Merkel-Dump fiel ein neuer Fehlalarm auf:
  eine Kenntnisse-Aufzählung ("Kenntnisse:Projektmanagement, User- und
  Lizenzmanagement, +7 Kenntnisse", Martin Reimann/DDV Mediengruppe, Azubi-Rolle)
  rutschte durch, weil die bestehende `_SKILL_SUFFIX_RE` nur "und +N Kenntnisse" am
  direkten Ende erkennt, nicht mitten in einer mehrteiligen Aufzählung. **Zusatz-Fix:**
  neue `_KENNTNISSE_PREFIX_RE`, die auf das stabile UI-Label "Kenntnisse:" am Anfang des
  Absatzes prüft (dasselbe Label wie in `dom_utils._NOISE_LINE_MARKERS`), zuverlässiger
  als das Suffix-Muster. Zusätzlich die Wortanzahl-Heuristik aus v0.7.28 von `> 4` auf
  `>= 4` Wörter (ohne Komma) verschärft, nachdem der komplette Korpus (584 Standort-Werte)
  keinen einzigen echten Standort mit genau 4 Wörtern ohne Komma zeigte, aber mindestens
  zwei weitere Freitext-Leaks ("Application Manager Azure Infrastructure",
  "Graduate Course Spatial Econometrics" bei Moritz Meister, noch in v0.7.27-Daten
  vorhanden) genau 4 Wörter hatten. **Verifiziert:** echter Marcel-Merkel-Dump liefert
  jetzt für "Lead Cloud Computing" korrekt "Nürnberg, Bayern, Deutschland"; alle anderen
  TeamBank- und T-Systems-Einträge unverändert (bleiben `N/A`, da LinkedIn dort tatsächlich
  keinen Standort anzeigt); Regressionstest gegen alle verfügbaren Erfahrungs-Dumps
  (David Haslacher, Martin Reimann, Marcel Merkel) ergibt keine neuen Fehlalarme; alle 133
  eindeutigen historischen Standort-Werte im Korpus erneut geprüft, die 11 abgelehnten sind
  ausnahmslos bereits bekannte oder neu bestätigte Freitext-/Kenntnisse-Leaks, 0 echte
  Standorte fälschlich verworfen.

## 0.7.28
- **Freitext-Aufgabenbeschreibung landete bei Einzelpositionen im Standort-Feld**
  (Autor-Fund 2026-09-15, an Jan Werth und Hana Ibrahim im aktuellsten Scrape
  entdeckt). Fünf echte Fälle im Korpus bestätigt: "research collaboration."
  (Hana Ibrahim), "Bayesian machine learning for modeling motor control."
  (David Haslacher), "Künstliche Intelligenz (KI) und Agenten" sowie "Mitwirkung
  an Planung, Organisation und Durchführung von Events." (Dr. David Müller),
  "Working as a journeyman of the joinery trade" (Dr. Jan Werth) - alle klar
  Fließtext statt Ortsangabe, aber unter der bestehenden 80-Zeichen-Grenze und
  ohne Kenntnisse-/Abschluss-Marker, daher von `_looks_like_location()` bisher
  nicht erkannt. **Fix:** drei zusätzliche Signale in `_looks_like_location()`
  (`fetch/parser_experience.py`) - endet mit Punkt, beginnt mit Kleinbuchstaben,
  oder mehr als vier Wörter ohne Komma; alle drei gegen den kompletten
  vorhandenen Korpus (255 echte Standort-Werte) verifiziert, bevor sie
  scharfgeschaltet wurden. Betrifft `_parse_single_position` UND
  `_group_header` (beide nutzen dieselbe Funktion). **Verifiziert:** alle 5
  bekannten Fälle liefern jetzt `False` (→ Feld wird `N/A` statt Fließtext);
  Regressionstest gegen alle 255 echten Standort-Werte im Korpus ergibt 0
  neue Fehlalarme; End-to-End-Test gegen den echten David-Haslacher-Dump
  bestätigt: der betroffene Eintrag liefert jetzt `N/A`, der echte Standort im
  Nachbareintrag bleibt unverändert korrekt.

## 0.7.27
- **ROOT CAUSE für alle "Fehlerseite"/"404"-Funde seit v0.7.19 gefunden und behoben**
  (Autor-Frage 2026-09-14: „warum werden die Daten client-seitig geladen, aber sind
  nicht abrufbar für den Bot?" - Anstoß, den frischen `errorboundary_...html`-Dump
  aus v0.7.26 tatsächlich zu öffnen statt weiter zu spekulieren). Der Dump von
  `martin-reimann-26902a26b/details/experience/` - zweifelsfrei korrekt geladen,
  enthält die echten, mehrfach verifizierten Erfahrungsdaten (Reimann Solutions,
  DDV Mediengruppe, Oli Lacke, …) - enthält den Text „Leider ist ein Fehler
  aufgetreten" trotzdem, exakt EINMAL: in einem statischen
  `<meta name="como-err" content="{&quot;title&quot;:&quot;Leider ist ein Fehler
  aufgetreten.&quot;,...}">`-Tag im `<head>`. Gegenprobe an vier weiteren,
  historischen, zweifelsfrei korrekten Dumps (Zertifikate/Sprachen Martin Reimann,
  Profil kreuter92, Kenntnisse alisia-deichhardt) bestätigt: **dieses Meta-Tag
  steht im `<head>` JEDER LinkedIn-Seite**, unabhängig vom tatsächlichen Zustand -
  eine reine Konfigurations-/Übersetzungsangabe für eine client-seitige
  Fehlerkomponente, kein Hinweis auf einen echten Fehler. Die bisherige rohe
  Substring-Suche über die komplette HTML (`ERROR_BOUNDARY_MARKER in text`/
  `in page.content()`, seit v0.7.19) matchte damit auf JEDER Seite, erfolgreich
  oder nicht - das war die eigentliche Ursache für den david-haslacher-Fund
  (v0.7.20), das komplette All-404-Debakel unter FAST_TEST_MODE (v0.7.21/22), den
  jetzigen Ausfall von Scraper UND Debug-Modul (v0.7.25) - **nicht** Delays,
  Drosselung, Rendering-Last oder eine LinkedIn-seitige Sperre, wie in den
  vorherigen Versionen vermutet.
  **Fix:** neue `fetcher._error_boundary_in_body()` prüft den Marker nur noch
  innerhalb von `soup.body` (BeautifulSoup) statt über die komplette HTML - ein
  Treffer im `<head>` zählt nicht mehr, ein tatsächlich im Seiteninhalt
  gerenderter Fehlertext (der ursprüngliche v0.7.19-Verdachtsfall) würde
  weiterhin erkannt. Ersetzt die rohe Substring-Prüfung in `fetcher.py` UND
  `browser_fetcher.py`. **Verifiziert an echten Dumps** (kein Mock): alle 5
  bekannten, zweifelsfrei korrekten Dumps liefern jetzt `False` (kein Fehler);
  ein synthetischer Fall mit dem Marker-Text tatsächlich im `<body>` liefert
  weiterhin `True`.

## 0.7.26
- **Fehlerseiten-Dump als Diagnose-Artefakt** (Autor-Fund 2026-09-14: im sichtbaren,
  headful Browserfenster erscheint die Seite beim Zusehen augenscheinlich korrekt
  geladen, obwohl `ERROR_BOUNDARY_MARKER` auslöst und das Profil als Fehler/404
  gewertet wird - das deutet eher auf ein falsches Positiv der reinen
  Substring-Prüfung als auf eine echte LinkedIn-seitige Drosselung). Neue
  `browser_fetcher._save_error_boundary_dump()` sichert die Roh-HTML im Moment,
  in dem der Marker nach dem zweiten Versuch endgültig als Fehler gewertet wird,
  unter `data/debug_dumps/errorboundary_<url-slug>_<uhrzeit>.html` - liefert beim
  nächsten Auftreten ein echtes Artefakt zur Analyse statt nur einer
  Fehlermeldung ohne Beleg. **Reine Instrumentierung, keine Änderung der
  Erkennungslogik selbst** - es wird bewusst nicht geraten, welcher Mechanismus
  dahintersteckt (Timing/Hydration, versteckte DOM-Stelle, echte Drosselung),
  solange kein echter Dump vorliegt. **Verifiziert** (gemockt): ein simulierter
  Treffer speichert die vollständige Seiten-HTML korrekt unter einem eindeutigen
  Dateinamen.

## 0.7.25
- **Logs jetzt tagesbasiert statt einer einzigen, dauerhaft wachsenden Datei**
  (Autor-Wunsch 2026-09-14, analog zu `output_results_<TTMMJJJJ>.csv`/
  `<Name>_<TTMMJJJJ>.json`): neue `config.log_file_path(run_date=None)` liefert
  `data/logs/scraper_<TTMMJJJJ>.log` - mehrere Läufe am selben Tag hängen weiterhin
  an dieselbe Datei an (`FileHandler`/`open(..., "a")` unverändert im Anhänge-Modus),
  ein neuer Kalendertag bekommt automatisch eine frische Datei. `LOG_FILE_PATH` als
  fixe Konstante entfällt, `logging_setup.py` ruft die Funktion jetzt bei jedem
  Setup auf. Die bestehende `data/logs/scraper.log` wurde nach
  `scraper_14092026.log` umbenannt statt gelöscht, damit der bisherige Verlauf
  erhalten bleibt.
- **Debug-Modul komplett auf den Stand vor v0.7.22 zurückgerollt** (Autor-Fund
  2026-09-14: nach den v0.7.22/23-Änderungen scheiterten sowohl der manuelle
  Einzelprofil- als auch der CSV-Batch-Dump an derselben LinkedIn-Fehlerseite -
  sogar am eigenen, seit Projektbeginn verlässlichen Referenzprofil, direkt beim
  allerersten Request nach vollständigem Aufwärmen und mit bereits vollen
  NFA2-Delays). Auf expliziten Wunsch **ohne** weitere Root-Cause-Analyse entfernt:
  `_run_debug_dump_csv_batch()` und die geteilte `_dump_all_pages_for_profile()`
  (v0.7.23) sind komplett raus; `run_debug_dump()` fragt wieder ausschließlich nach
  einem einzelnen, per Hand eingetippten Profil-Slug, keine CSV-Auswahl mehr an
  dieser Stelle. Menüpunkt 2 (Scraping) ist davon **nicht** betroffen -
  `_choose_input_csv()`/`data/input/` bleiben dort unverändert im Einsatz.
  **Wichtiger Hinweis:** dieses Rollback betrifft nur main.py (die
  Debug-Orchestrierung). Die Stelle, die die beobachtete Fehlerseite tatsächlich
  auswirft (`ERROR_BOUNDARY_MARKER`-Prüfung samt Retry-Logik in
  `fetch/browser_fetcher.py`, v0.7.19-v0.7.22), ist unverändert geblieben, da sie
  gemeinsam mit dem echten Scraping-Pfad genutzt wird und nicht explizit als Teil
  des "Debug Updates" benannt wurde. Es ist daher nicht auszuschließen, dass ein
  erneuter Debug-Versuch weiterhin an derselben Fehlerseite scheitert.
  **Verifiziert** (gemockt): `run_debug_dump()` fragt direkt nach der Seite ohne
  CSV-Zwischenschritt, "Alle Seiten" dumpt weiterhin alle 7 Seiten; die entfernten
  Funktionen existieren im Modul nicht mehr.

## 0.7.24
- **Logs in eigenen Ordner ausgelagert** (Autor-Wunsch 2026-09-14, analog zu
  `INPUT_DIR`/`OUTPUT_CSV_DIR`/`OUTPUT_JSON_DIR`/`DEBUG_DUMP_DIR`): neue
  `config.LOG_DIR = DATA_DIR / "logs"`, `LOG_FILE_PATH` zeigt jetzt auf
  `data/logs/scraper.log` statt direkt auf `data/scraper.log`. Reiner
  Konfigurations-/Pfadwechsel - `logging_setup.py` legt den Ordner über das
  bestehende `LOG_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)` automatisch
  an, kein weiterer Code betroffen. Die bestehende Logdatei wurde nach
  `data/logs/scraper.log` verschoben (nicht neu angelegt), damit der bisherige
  Verlauf erhalten bleibt.

## 0.7.23
- **Bestätigt per echtem Testlauf: die verkürzten Testmodus-Delays waren tatsächlich
  die Ursache des All-404-Problems (Autor-Fund 2026-09-14, Testlauf mit v0.7.22).**
  Auch die entschärften v0.7.22-Werte (Request 2-4s) lieferten weiterhin
  durchgehend "404" - schon das allererste Profil eines frischen Laufs (plain
  Profilseite, Kontakt-Overlay UND eine Detailseite) zeigte LinkedIns generische
  Fehlerseite, obwohl dasselbe Profil im normalen Browser klaglos lädt.
  **`config.FAST_TEST_MODE` komplett entfernt** statt weiter herunterzuregeln - der
  Schalter brachte in der Praxis keinen nutzbaren Zeitgewinn, nur unbrauchbare
  Testläufe (Autor: „damit können wir das wieder entfernen, da es wirklich 0,0 was
  bringt"). Alle Läufe (auch gegen `input_profiles_test34.csv`) verwenden jetzt
  unterschiedslos die vollen NFA2-Delays; `main.py` warnt daher auch nicht mehr bei
  jedem Start.
- **Debug-Dump-CSV-Batch schlug ebenfalls fehl, vermutlich aus demselben Grund.**
  Zusätzlich fiel dabei ein zweiter, unabhängiger Bug auf: `_run_debug_dump_csv_batch`
  rief nie `rate_limiter.profile_done()` auf, wodurch der interne Zähler bei 0 blieb -
  `0 % N == 0` gilt für jedes N, also löste `between_profiles()` bei JEDEM Profil die
  längste Pausenstufe aus statt der normalen Profil-Pause. Behoben: der Aufruf fehlt
  jetzt nicht mehr, Pacing entspricht damit exakt einem echten Scraping-Lauf.
  **Zusätzlich (Autor-Wunsch):** die Logik zum Holen aller sieben Detailseiten eines
  Profils lag bisher in main.py doppelt vor - einmal im manuellen
  Einzelprofil-Debug-Pfad (Slug per Hand eingetippt), einmal im CSV-Batch-Pfad. Auf
  eine gemeinsame `_dump_all_pages_for_profile()`-Funktion zusammengeführt, damit
  beide Wege garantiert denselben Ablauf durchlaufen und nicht wieder unbemerkt
  auseinanderdriften können.
- **CLI-Ausgaben (print()) werden jetzt zusätzlich in `data/scraper.log`
  mitgeschrieben, mit sofortigem Flush nach jeder Zeile** (Autor-Wunsch: Copy/Paste
  in der Windows-Konsole ist während eines Laufs gesperrt - schließt sich das
  Fenster oder stürzt der Prozess ab, war der reine Bildschirmverlauf bisher komplett
  weg, da nur `logger.info/.warning/.error` dort landete, nicht die vielen
  print()-Statusmeldungen). Neue `logging_setup.setup_console_capture()` spiegelt ab
  Programmstart `sys.stdout`/`sys.stderr` in dieselbe Logdatei wie das normale
  Logging (auch ein unbehandelter Absturz-Traceback landet damit dort).
  **Verifiziert** (gemockt): `_run_debug_dump_csv_batch` ruft `profile_done()` und
  `between_profiles()` jetzt in derselben Reihenfolge wie `run_scraping`; beide
  Debug-Pfade rufen `_dump_all_pages_for_profile()` mit identischen Argumenten auf.
  **Ohne einen weiteren echten Testlauf lässt sich nicht endgültig ausschließen, dass
  ein Teil der 404-Serie auch von einer vorübergehenden LinkedIn-seitigen Drosselung
  durch die vorangegangenen Testläufe herrührt** (Cool-down-Zeit statt reinem
  Delay-Effekt).

## 0.7.22
- **Testmodus lieferte durchgehend "404" statt echter Daten - Testmodul damit
  unbrauchbar (Autor-Fund 2026-09-14, direkt nach dem Aktivieren von v0.7.21).**
  Ursache: die stark verkürzten Delays (0.5-1.5s/Request, 3-8s/Profil) lösten
  vermutlich echte Drosselung/Timing-Probleme bei LinkedIn aus - jedes Profil zeigte
  dieselbe generische Fehlerseite (`ERROR_BOUNDARY_MARKER`), die seit v0.7.19 auf
  der Kontakt-/Profilseite als 404 gewertet wird. **Drei Gegenmaßnahmen:**
  1. `browser_fetcher.get_html()` wartet jetzt (`BROWSER_SETTLE_MS`) direkt nach der
     Navigation, BEVOR der Seitenzustand geprüft wird - gibt der SPA mehr Zeit,
     Routing/Laden abzuschließen, statt sie sofort als kaputt zu werten.
  2. Der Retry-bei-Fehlerseite aus v0.7.20 (bisher nur für Detailseiten) gilt jetzt
     für JEDE URL, auch die Kontakt-/Profilseite: Fehlerseite beim ersten Versuch →
     erneute Navigation, ERST wenn sie beim zweiten Versuch weiterhin da ist, wird
     entschieden (Kontakt-/Profilseite → `ProfileNotFoundError`, Detailseite →
     normaler `FetchError`).
  3. `config.FAST_TEST_MODE`s Delays weniger aggressiv gesenkt (Request 2-4s statt
     0.5-1.5s, Profil-Pause 5-12s statt 3-8s, restliche Pausen proportional
     angehoben) - noch immer ca. 3-5x schneller als Produktion statt 10-20x.
  **Verifiziert** (gemockt): Kontakt-Overlay UND Detailseite erholen sich beim
  Retry und liefern normalen Inhalt, wenn die Fehlerseite nur beim ersten Versuch
  auftrat; bleibt sie bestehen, kommt weiterhin `ProfileNotFoundError` auf der
  Kontakt-/Profilseite bzw. `FetchError` auf einer Detailseite; ein normaler Ablauf
  ohne Fehlerseite braucht weiterhin nur eine Navigation (kein unnötiger Overhead).
  **Hinweis:** ob damit die eigentliche Ursache (Drosselung vs. reiner
  Rendering-Zufall) behoben ist, lässt sich ohne einen echten Testlauf nicht
  abschließend sagen.
- **CSV-Eingabe in einen eigenen Ordner ausgelagert, mit interaktiver Auswahl**
  (Autor-Wunsch 2026-09-14). `data/input/` enthält jetzt alle Eingabelisten
  (`input_profiles.csv`, `input_profiles_test34.csv`, `input_profiles.example.csv`
  - aus `data/` dorthin verschoben). Neues `main._choose_input_csv()`: listet alle
  `*.csv` in `config.INPUT_DIR` nummeriert auf, der Bediener wählt eine per Ziffer.
  Menüpunkt 2 (Scraping) fragt das jetzt VOR jedem Lauf ab, statt stur
  `input_profiles.csv` zu lesen - `run_scraping()` bekommt den gewählten Pfad als
  neuen Parameter `input_csv_path` statt ihn selbst aus `config` zu lesen.
  `config.FAST_TEST_MODE` schaltet die Eingabeliste nicht mehr automatisch um
  (entfernt) - welche Liste läuft, ist jetzt unabhängig von diesem Schalter bei
  jedem Lauf eine bewusste Wahl.
- **Debug-Dump-Modul (Menüpunkt 3) kann jetzt eine ganze CSV auf einmal abarbeiten**
  statt nur einen einzeln eingetippten Profil-Slug (Autor-Wunsch 2026-09-14: alle
  Rohdaten des Testkorpus als Dump sichern, um sie systematisch gegen die
  gescrapten Ausgaben zu verifizieren, statt bei jedem neuen kleinen Bug einzeln
  nachzufragen). Neue Rückfrage am Anfang von `run_debug_dump()`: "Mehrere Profile
  aus einer CSV dumpen?" - bei Ja über denselben `_choose_input_csv()`-Dialog eine
  Liste wählen, dann werden für JEDES Profil darin ALLE sieben Seiten gespeichert
  (`_run_debug_dump_csv_batch()`), mit derselben Profil-Pause wie ein echter
  Scraping-Lauf (NFA2 gilt auch für Batch-Dumps). Bestehender Einzelprofil-Ablauf
  (Ziffern 1-9) bei "Nein" unverändert.

## 0.7.21
- **Neuer Testmodus für schnellere Regressionsläufe während der Entwicklung**
  (Autor-Wunsch 2026-09-14: ein voller ~59-Profile-Korpuslauf dauert ~3 Stunden -
  zu langsam, um jeden Fix zeitnah gegenzuprüfen). `config.FAST_TEST_MODE`
  (Default `False`) schaltet bei `True` zwei Dinge um: (1) die Eingabeliste zeigt
  auf `data/input_profiles_test34.csv` statt `input_profiles.csv` - ein neuer,
  kuratierter 34-Profile-Testkorpus, bestehend aus genau den Profilen, deren
  `kenntnisse`-Zahl beim v0.7.20-Fund verdächtig glatt bei 20 oder 30 lag (also
  wahrscheinlich vom Scroll-Abschneide-Bug betroffen waren) - damit lässt sich der
  Fix gezielt an den Fällen gegenprüfen, die ihn auch brauchen. (2) die
  Politeness-Delays (NFA2) werden drastisch verkürzt (z. B. Profil-Pause 25-75s →
  3-8s, „alle 25 Profile"-Pause 300-600s → 30-60s), aber bewusst NICHT auf 0 -
  ein Testlauf über die 34 Profile dauert damit ~10 statt ~180 Minuten. **Wichtige
  Absicherung:** `FAST_TEST_MODE` ist eine einzige, gut sichtbare Konstante in
  `config.py` mit einem expliziten Kommentar, dass sie vor jedem echten
  Erhebungslauf (voller Korpus, Server-Einsatz) wieder auf `False` stehen MUSS;
  `main.py` gibt bei jedem Start eine unübersehbare Warnung aus und hängt
  „[TESTMODUS - verkürzte Delays!]" an die Menü-Kopfzeile, solange der Schalter
  aktiv ist - damit er nicht versehentlich aktiv bleibt. **Aktuell aktiv** (für
  die laufende Bugfix-Phase) - vor dem nächsten echten Korpuslauf wieder
  deaktivieren.

## 0.7.20
- **Kritisch, zwei zusammenhängende Funde am Beispiel `david-haslacher` (48 echte
  Kenntnisse laut manuellem Abgleich, Autor-Fund 2026-09-14):**
  1. **Kenntnisse-Liste wurde bei langen Listen weiterhin abgeschnitten** (30 statt
     48 Einträge) - trotz des `_split_by_hr`-Fixes in v0.7.18. Ursache diesmal NICHT
     im DOM-Parsing, sondern beim Scrollen: `BrowserFetcher._scroll_through` brach
     bisher ab, sobald AUCH NUR EIN Treffer des Wartemarkers (`[data-component-type=
     "LazyColumn"] p`) sichtbar war - das passiert praktisch sofort, weil die ersten
     Kenntnisse ohne viel Scrollen rendern. Lange Listen laden aber weitere Einträge
     erst beim WEITEREN Scrollen nach (Pagination innerhalb der LazyColumn) - das
     alte "ein Treffer reicht"-Kriterium brach also ab, bevor der Rest nachgeladen
     war. **Fix:** `_scroll_through` scrollt jetzt weiter, solange die Trefferzahl
     noch wächst, und bricht erst ab, wenn sie über zwei aufeinanderfolgende
     Scrollschritte stabil geblieben ist; neues, höheres Schrittbudget nur für
     Detailseiten (`BROWSER_SCROLL_STEPS_MAX_WITH_TARGET = 40` statt 6-12) - das
     kleinere Aufwärm-Budget ohne Ziel bleibt unverändert.
  2. **Der eigene Debug-Dump-Versuch für dieses (echt existierende, nicht gelöschte)
     Profil brach mit der neuen v0.7.19-404-Erkennung ab** ("zeigt LinkedIns
     generische Fehlerseite ... bisher nur bei gelöschten Profilen beobachtet") -
     ein klarer **False Positive**: `/details/skills/` zeigte denselben
     Fehlertext wie zuvor nur bei `anastasiia-m-b045461b3`/`imbilalbutt`
     beobachtet, obwohl das Profil unstrittig existiert (lädt im normalen Browser
     normal). Vermutlich ein Rendering-Absturz der React-App bei umfangreichem
     Inhalt/viel Scrollen, kein 404-Mechanismus. **Fix:** die
     `ERROR_BOUNDARY_MARKER`-Prüfung unterscheidet jetzt nach URL - auf der
     Kontakt-/Profilseite (kein `"/details/"` in der URL, wo beide bislang
     bestätigten 404-Fälle auftraten) bleibt es ein `ProfileNotFoundError`; auf
     einer Detailseite wird EINMAL erneut navigiert (der Fehler kann transient
     sein) und nur, wenn er dabei bestehen bleibt, als normaler `FetchError`
     gewertet - NICHT mehr als 404. Gilt für beide Fetch-Wege (`fetcher.py`,
     `browser_fetcher.py`).
  **Verifiziert** (gemockt): `_scroll_through` stoppt bei einer konstant
  bleibenden Trefferzahl nach 3 Prüfungen, bei einer schrittweise wachsenden Liste
  (Muster 10→20→30→40→48→stabil) erst nach Erreichen von 48, und läuft bei einer
  nie stabilen Liste das volle (höhere) Schrittbudget ohne Absturz durch; ohne
  `stop_selector` bleibt das kleine 6-12-Budget unverändert. Kontakt-Overlay mit
  Fehlerseite wirft weiterhin sofort `ProfileNotFoundError`; eine Detailseite mit
  einmaliger Fehlerseite erholt sich beim Retry und liefert normalen Inhalt; bleibt
  die Fehlerseite auf einer Detailseite bestehen, kommt `FetchError` (kein
  `ProfileNotFoundError`) - sowohl im Browser- als auch im reinen HTTP-Weg.

## 0.7.19
- **Gegenprüfung des kompletten, unter v0.7.18 neu gescrapten ~59-Profile-Korpus:**
  Pronomen-Bug weg (0 Treffer), Kenntnisse jetzt Ø 16,8 statt 1 (Spanne 0-30, 0 nur
  bei plausibel echten Fällen), keine Abschluss-Leaks in `standort`, CSV ohne
  doppelte Personenzeilen trotz mehrerer Läufe am selben Tag (Anhänge-Fix aus
  v0.7.15 hält). **Neuer Fund dabei:** die beiden bekannten gelöschten Profile
  (`anastasiia-m-b045461b3`, `imbilalbutt`) zeigen jetzt `person`-Felder als `null`
  UND „Leider ist ein Fehler aufgetreten"/„Seite aktualisieren" als scheinbar echte
  Ausbildungs-/Kenntnis-/Sprachen-Einträge - statt wie erwartet `"404"` überall.
  Ursache: LinkedIn leitet bei diesen beiden nicht (mehr) sauber auf `/404/` um,
  sondern die React-App stürzt stattdessen in ihre generische Fehlerseite (vermutlich
  ausgelöst dadurch, dass seit v0.7.15 die allererste Browser-Anfrage eines Profils
  direkt die Kontakt-Overlay-URL ist statt zuerst die Profilseite). Weder der
  `/404`-Landed-URL-Check noch ein `FetchError` griffen dafür bisher. **Fix:** neue
  `fetcher.ERROR_BOUNDARY_MARKER = "Leider ist ein Fehler aufgetreten"`, geprüft
  sowohl im reinen HTTP-Weg (`fetcher.py`, gegen den Antworttext) als auch im
  Browser-Weg (`browser_fetcher.py`, gegen `page.content()`, direkt nach dem
  `/404`-Check) - ein Treffer wirft `ProfileNotFoundError` und wird damit wie eine
  saubere 404-Umleitung behandelt. Bewusst als **404-Fall** statt als generischer
  `FetchError` eingestuft, weil der Marker an exakt den beiden bereits bestätigt
  gelöschten Profilen auftrat und bei 0 der 57 echten Profile - noch keine an einem
  Debug-Dump verifizierte LinkedIn-Mechanik, aber ein enger, spezifischer
  Text-Treffer mit geringem Fehlalarm-Risiko. **Verifiziert** (gemockt, beide
  Fetch-Wege): der Marker im Antworttext/`page.content()` löst `ProfileNotFoundError`
  aus; normale Inhalte ohne den Marker bleiben unbeeinflusst. Die zwei betroffenen
  Profile brauchen noch einen weiteren Scrape-Durchlauf unter dieser Version, um
  korrekt als „404" markiert zu werden - der Rest des Korpus ist NICHT betroffen.

## 0.7.18
- **Kritischer Fund: bei FREMDEN Profilen wurde nur die erste Kenntnis statt der
  vollständigen Liste gescrapt (Autor-Fund 2026-09-14, betraf systematisch den
  gesamten 35-Profile-Testkorpus vom 13.09. - `kenntnisse` war dort praktisch
  überall `[1 Eintrag]` statt der echten Liste).** Debug-Dump eines fremden Profils
  (`alisia-deichhardt`) zeigt die Ursache: `dom_utils._split_by_hr` ging bisher davon
  aus, dass alle `<hr>`-Trenner **direkte Geschwister** der Eintrags-`<div>`s unter
  einem GEMEINSAMEN Elternknoten sind (`<div>…</div><hr><div>…</div>…` - so sind
  Ausbildung/Sprachen/Zertifikate aufgebaut). Bei den Kenntnissen fremder Profile
  steckt jedes `<hr>` stattdessen ALLEIN in einem eigenen Wrapper-`<div>`, das ein
  Geschwister der Eintrags-`<div>`s ist, nicht dessen Elternknoten - `_split_by_hr`
  fand dadurch keine Gruppen, `_split_by_row_button` fand ebenfalls keinen
  „bestätigen"-Button (den es in dieser Ansicht gar nicht mehr gibt - stattdessen
  je Kenntnis 0-2 Kontextzeilen wie „Junior Data Scientist bei Siemens" oder
  „Universität Regensburg"), und alles fiel auf `_single_entry` zurück, das die
  GESAMTE Sektion als EINEN Eintrag behandelt - nur dessen erste Zeile (die erste
  Kenntnis) wurde am Ende verwertet. **Fix:** `_split_by_hr` läuft jetzt über ALLE
  Nachfahren der Sektion in Dokumentreihenfolge (`section.descendants`) und schneidet
  bei jedem `<hr>`-Tag, unabhängig von dessen Verschachtelungstiefe - deckt damit
  beide Strukturvarianten ab. Die Sektions-Überschrift (die dadurch neu in die erste
  Gruppe rutscht) wird wie in `_single_entry` über `_SECTION_HEADINGS` entfernt.
  **Verifiziert:** `alisia-deichhardt` liefert jetzt 20 statt 1 Kenntnis (Namen
  stichprobenartig gegen den Dump geprüft); volle Regression unverändert korrekt -
  Ausbildung 4/4 und Sprachen 3/3 am eigenen Profil (kein Heading-Leak durch die neue
  Traversierung), Zertifikate 5/5 an `kreuter92`, **eigene Kenntnisse weiterhin 26/26
  identisch** (laufen jetzt über den neuen `_split_by_hr`-Pfad statt über
  `_split_by_row_button`, liefern aber exakt dieselbe Liste).

## 0.7.17
- **Die zwei offenen `kreuter92`-Verdachtsfälle aus der 0.7.16-Gegenprüfung gegen
  frische Debug-Dumps geklärt - beide sind KEIN Parser-Bug.**
  `/details/certifications/`: der Dump zeigt, dass jeder Eintrag im echten DOM
  wirklich nur zwei Zeilen hat (`"Scrum.org"`/`"Coursera"` + `"Ausgestellt: <Datum>"`)
  - es gibt keine separate Aussteller-Zeile, `aussteller: null` ist also korrekt,
  keine Verwechslung von Name/Aussteller. `/details/experience/`: der Dump zeigt den
  echten LinkedIn-Leerzustand-Text „Noch keine Informationen verfügbar" - das Profil
  hat schlicht keine Berufserfahrung hinterlegt, `[]` ist korrekt.
- **Dabei aber ein wichtiger Nebenfund: `/details/experience/` liegt bei diesem Dump
  im NEUEN SDUI-Markup vor** (`data-sdui-screen="...ProfileExperienceDetails"`,
  `LazyColumn`) - bisher gebaut wurde `parser_experience.py` ausschließlich gegen das
  ALTE SSR-Markup (`entity-collection-item-`), das die vier anderen Detailseiten
  schon länger nicht mehr verwenden. Fand `parser_experience.py` bisher 0 Einträge im
  bekannten Markup, gab es `[]` zurück **ohne jede Warnung** - nicht unterscheidbar
  von einem echt leeren Profil. Da der vorliegende Dump zufällig selbst leer ist
  (siehe oben), lässt sich noch nicht sagen, ob LinkedIn diese Umstellung
  flächendeckend ausrollt und ob sie Profile MIT echter Erfahrung betrifft - ein
  echter Fix (SDUI-Fallback-Parser) braucht dafür einen Dump eines Profils mit
  echten Erfahrungseinträgen in diesem neuen Markup. **Fix in dieser Version:** neue
  `_warn_if_unrecognized_markup()` - findet `parse_experience_page` 0 Einträge, prüft
  sie erst auf den bekannten Leerzustand-Text (dann keine Warnung, wie bisher), sonst
  auf das neue SDUI-Markup (dann eine klare Warnung „Ergebnis könnte unvollständig
  statt echt leer sein"), sonst die bisherige generische „Markup evtl. geändert".
  **Verifiziert:** kreuter92-Dump liefert weiterhin `[]` ohne Warnung; ein
  synthetisches SDUI-Markup ohne Leerzustand-Text löst die neue Warnung aus; eine
  Kontrolle mit unbekanntem/leerem HTML löst die alte generische Warnung aus; volle
  Regression gegen den echten Martin-Reimann-Erfahrungsdump weiterhin 5/5 unverändert.

## 0.7.16
- **Pronomen-Badge ("He/Him", "She/Her") wurde als Headline übernommen.** Bei der
  Gegenprüfung des am 2026-09-13 live gescrapten Testkorpus (35 Profile) fiel auf:
  9 von 35 Profilen (≈26 %) hatten `titel` gleich dem literalen Text „He/Him" bzw.
  „She/Her" statt einer echten Berufsbezeichnung. LinkedIn zeigt das optionale
  Pronomen als eigene `<p>`-Zeile in der Topcard; steht sie vor der eigentlichen
  Headline-Zeile, nahm `_parse_headline` sie ungeprüft als `paragraphs[0]`. Fix:
  neue `_PRONOUN_RE` (exakter Treffer auf die von LinkedIn vorgegebene, geschlossene
  Auswahlliste - He/Him, She/Her, They/Them u. Ä.) filtert diese Zeile in
  `_card_paragraphs` konsequent heraus, unabhängig von ihrer Position, damit
  `paragraphs[0]` wieder verlässlich die echte Headline ist. **Verifiziert:**
  synthetische Topcards mit Pronomen vor UND nach der Headline liefern jetzt beide
  die echte Headline; eine Kontrolle mit einer echten Headline, die zufällig auch
  einen Schrägstrich enthält („CEO/Founder"), wird NICHT gefiltert (kein
  False-Positive); Regression gegen die Martin-Reimann- und kreuter92-Dumps
  unverändert korrekt.

## 0.7.15
- **CSV wurde bei mehreren Läufen am selben Tag überschrieben statt erweitert.**
  `CsvWriter.__enter__` öffnete `output_results_<Datum>.csv` bisher immer mit `"w"` -
  ein zweiter Testlauf am selben Tag hat damit die Ergebnisse des ersten Laufs
  gelöscht (Autor-Fund 2026-09-13, 50 von 60 Profilen in mehreren Sitzungen
  getestet). Fix: existiert die Datei schon, wird angehängt (`"a"`) und der Header
  nicht erneut geschrieben; existiert sie noch nicht (neuer Tag), wird sie wie bisher
  frisch mit BOM + Header angelegt. Bewusst `utf-8` (ohne `-sig`) beim Anhängen, sonst
  würde jedes neue Schreib-Handle sein eigenes BOM mitten in die Datei setzen.
  **Verifiziert:** ein Testschreiben mit „w utf-8-sig" gefolgt von „a utf-8" erzeugt
  genau EIN BOM am Dateianfang, keins an der Anhängestelle.
- **Konsole blieb während des GESAMTEN Laufs für Klicks gesperrt (QuickEdit aus) -
  auch nach Abschluss, was das Kopieren von Fehlermeldungen erschwerte.**
  `_disable_console_quick_edit()` (v0.7.11) lief nur einmal beim Start und wurde nie
  zurückgesetzt. Ersetzt durch `_set_console_quick_edit(enabled: bool)`; `main()`
  schaltet QuickEdit jetzt nur noch für die Dauer des jeweils gewählten Menüpunkts aus
  und direkt danach (auch bei Fehlern, via `finally`) wieder ein - unabhängig davon,
  welches Modul lief (Autor-Wunsch 2026-09-13).
- **Reihenfolge beim Scraping-Start: das Aufwärmen der Browser-Sitzung lief mitten im
  ERSTEN Profil statt vollständig davor.** `browser_fetcher._warm_up()` wurde bisher
  lazy beim ersten Browser-Zugriff ausgelöst (typischerweise das Kontakt-Overlay) -
  zu diesem Zeitpunkt waren für das erste Profil bereits Profilseite und Erfahrung
  per HTTP abgerufen worden (Autor-Fund 2026-09-13, am Log sichtbar: „Aufgewärmt"
  erschien zwischen zwei Log-Zeilen des ersten Profils). Fix: neue öffentliche
  Methode `BrowserFetcher.warm_up_now()` (startet den Browser + wärmt sofort auf);
  `run_scraping` ruft sie VOR der Profil-Schleife auf, statt das Aufwärmen dem
  ersten `get_html()`-Aufruf zu überlassen.
- **404-Erkennung griff nicht beim tatsächlichen Scrapen - zwei bestätigt gelöschte
  Profile liefen unbemerkt durch die komplette Erhebung (alle Sektionen, alle
  Wartezeiten).** Der in v0.7.14 gebaute `ProfileNotFoundError`-Check saß nur in
  `fetch/fetcher.py` (reiner HTTP-Weg): der prüft die *nach Redirects finale URL*,
  aber LinkedIns Umleitung auf `/404/` passiert client-seitig per JS, NACHDEM die
  Seite geladen ist - ein reiner `requests`/`curl_cffi`-GET bekommt sie nie zu
  sehen, nur ein echter Browser (bestätigt am Log vom 2026-09-13: beide gelöschten
  Profile bekamen "Kein Name"/"Topcard nicht gefunden", aber keine
  `ProfileNotFoundError`, und liefen bis zum Schluss durch). Fix: `browser_fetcher.py`
  prüft jetzt zusätzlich `page.url` nach jeder Navigation auf `/404` und wirft dort
  ebenfalls `ProfileNotFoundError`. Damit das so früh wie möglich greift (Autor-Wunsch:
  „da gibt es ja nur Existiert oder existiert nicht ... spart Zeit"), ruft
  `main.py:scrape_profile` jetzt zuerst das Kontakt-Overlay ab (client-seitig
  gerendert, damit der früheste Punkt mit Browser-Zugriff) und bricht bei
  `ProfileNotFoundError` sofort mit einem 404-Profil ab, BEVOR Profilseite,
  Erfahrung oder irgendeine der vier Detailseiten abgefragt werden. Der bisherige
  Check auf der Profilseite (reiner HTTP-Weg) bleibt als zweite, schwächere
  Absicherung bestehen (ohne Browser bzw. falls LinkedIn den Redirect doch einmal
  serverseitig macht).
- **Vier identische, aber irreführende Log-Zeilen gekürzt.** „Keine
  Ausbildungs-/Kenntnis-/Zertifikats-/Sprach-Einträge im HTML" endete bisher immer
  mit „- Sektion leer oder nicht client-seitig geladen (Browser-Fetcher nötig)" -
  das klang nach einem Fehler, obwohl eine leere Sektion (z. B.
  echt keine Zertifikate) der weitaus häufigere, unauffällige Fall ist (Autor-Wunsch
  2026-09-13: „Dies reicht aus mit 'Keine XXX-Einträge im HTML', der Rest ist
  unnötig und irreführend"). Betrifft `parser_education.py`, `parser_skills.py`,
  `parser_certifications.py`, `parser_languages.py`.

## 0.7.14
- **Debug-Dump von `kreuter92` diagnostiziert `parser_profile`-Bug: fehlende Headline
  ließ den Standort doppelt einlaufen.** Der Dump zeigte ein leeres `<title></title>`
  (kein Name, echte Einschränkung dieses Profils - kein Parserfehler) UND eine Topcard
  mit genau drei Zeilen: Ort, ein bloßer Middot, „Kontaktinformationen" - also KEINE
  eigene Headline-Zeile. `_parse_headline` nahm bisher ungeprüft `paragraphs[0]` als
  Headline, was hier fälschlich die Ortszeile traf - `titel` bekam denselben Wert wie
  `ort`+`bundesland`+`land` zusammen. Fix: neue `_find_location_line()`-Hilfsfunktion
  (einmal berechnet, von `_parse_headline` UND `_parse_location` benutzt);
  `_parse_headline` übernimmt `paragraphs[0]` nur noch, wenn es weder dem Namen noch
  dieser Standort-Zeile entspricht. Dabei auch einen nie im Testkorpus ausgelösten,
  unbelegten Fallback (`<p>Name</p>...<span>Headline</span>` für alte Dumps ohne JS)
  entfernt - Regression gegen alle vorhandenen Dumps (inkl. der beiden ältesten,
  vor-SDUI-Varianten) bestätigt, dass er nie gebraucht wurde. **Verifiziert:** `titel`
  ist am echten `kreuter92`-Dump jetzt `N/A` statt der Ortszeile; `ort`/`bundesland`/
  `land` unverändert korrekt; volle Regression (Martin-Reimann-Dumps, alle Sektionen)
  weiterhin unverändert korrekt.
- **404-Erkennung: ein nicht mehr existierendes Profil bekommt jetzt `"404"` statt
  `"N/A"`.** Zwei der drei Profile aus dem letzten Fund (`anastasiia-m-b045461b3`,
  `imbilalbutt`) existieren gar nicht mehr - ihre URLs leiten auf
  `https://www.linkedin.com/404/` um. Bisher wäre das wie ein Profil mit lauter leeren
  Feldern behandelt worden (`N/A` überall) - nicht unterscheidbar von einem
  existierenden Profil, das aus Privatsphäre-Gründen nichts zeigt. Neu:
  `fetch/fetcher.py` erkennt `/404` in der (nach Redirects) finalen URL und wirft eine
  eigene `ProfileNotFoundError` (Unterklasse von `FetchError`, ein `except FetchError`
  anderswo greift also weiterhin); `main.py:scrape_profile` fängt sie beim allerersten
  Abruf der Profilseite ab, baut sofort ein `Profile` mit `not_found=True` (neues Feld
  in `models.py`) und allen Personenfeldern auf `config.PROFILE_NOT_FOUND` ("404")
  gesetzt, und überspringt Erfahrung/Kontakt/Lazy-Sektionen ganz (nichts zu holen).
  `csv_writer.py` schreibt dafür eine einzige Zeile mit „404" in jeder Spalte;
  `json_writer.py` zeigt „404" in jedem `person`-Feld und lässt die Listen `[]` (der
  Dateiname fällt dabei auf den URL-Slug zurück statt „404_404_...", da PROFILE_NOT_FOUND
  wie NOT_AVAILABLE nicht als verwertbarer Name zählt). **Verifiziert** mit einem
  gemockten HTTP-Client, der auf `/404/` umleitet: `ProfileNotFoundError` wird korrekt
  geworfen, `scrape_profile` liefert ein korrektes 404-Profil ohne Erfahrungsabruf,
  CSV-Zeile ist genau eine Zeile mit 23× „404", JSON-Dateiname nutzt den URL-Slug; ein
  normaler (nicht umgeleiteter) Abruf bleibt unverändert unbeeinflusst (kein
  False-Positive).

## 0.7.13
- **Harte `MAX_PROFILES_PER_RUN=25`-Obergrenze entfernt.** Ein Lauf brach bisher nach 25
  Profilen ab (die restlichen URLs wurden gar nicht erst verarbeitet) - bei einem
  größeren Testkorpus (Autor: knapp 60 Profile) unpraktisch. Ersetzt durch eine
  **zweite, längere Pausenstufe** im `RateLimiter`: alle `EXTRA_LONG_PAUSE_EVERY_PROFILES`
  (Default 25) Profile eine Pause von `EXTRA_LONG_PAUSE_MIN/MAX_SECONDS` (Default
  5-10 Minuten) - zusätzlich zur bestehenden „alle 6 Profile" 3-7-Minuten-Pause, hat
  Vorrang, falls beide zusammenfallen. `run_scraping` verarbeitet jetzt beliebig viele
  URLs aus der Input-CSV in einem Lauf, mit derselben konservativen Rücksichtnahme
  gegenüber LinkedIn wie zuvor (NFA2 unverändert, nur die neue Pausenstufe kommt dazu).
  Verifiziert mit einem gemockten 50-Profile-Durchlauf: Pausen bei Profil 25 und 50
  korrekt "extra lang", bei 6/12/18/24/30/48 weiterhin die bisherige "lange" Pause,
  sonst die kurze Zwischen-Profil-Pause.
- **CSV-Export jetzt in einem eigenen Ordner** (`data/output_csv/`), analog zu
  `data/output_json/` - vorher landete `output_results_<TTMMJJJJ>.csv` direkt in
  `data/`. `config.OUTPUT_CSV_DIR` zeigt jetzt auf den Unterordner; `CsvWriter` legt ihn
  bei Bedarf an (`mkdir(parents=True)`, unverändert). Bestehende CSV-Dateien aus
  früheren Läufen wurden in den neuen Ordner verschoben (nicht kopiert/dupliziert).

## 0.7.12
- **`parser_experience._looks_like_location`: ein Abschluss/Studiengang konnte noch als
  Standort durchrutschen.** Beim Gegenprüfen des ersten kompletten Testkorpus-Neulaufs
  (v0.7.10) gefunden: Marcel Merkels „Dualer Student Wirtschaftsinformatik" bei
  Deutscher Telekom bekam `standort: "Bachelor of Science - Wirtschaftsinformatik"` -
  kurz genug und ohne Jahreszahl/Kenntnisse-Suffix, um die bisherigen Filter zu
  passieren, aber klar kein Ort. Isolierter Einzelfall im ganzen Korpus (10 Profile,
  gezielt danach gesucht). Fix: neue `_DEGREE_MARKER_RE` (Bachelor/Master/Diplom/
  Studium/Ausbildung/Promotion/B.Sc./M.Sc./Ph.D., DE+EN) zusätzlich zur bisherigen
  Prüfung in `_looks_like_location`. Verifiziert: der gemeldete Fall liefert jetzt
  `N/A`; alle bisher korrekten Ortsangaben (u. a. „Sunnyvale, Kalifornien, Vereinigte
  Staaten von Amerika", „Košice, Slowakei", „Remote") bleiben unverändert erkannt;
  volle Regression gegen den echten Martin-Reimann-Dump weiterhin 5/5.

## 0.7.11
- **`browser_fetcher.py`: Kontakt-Overlay-Klick schlug bei fremden Profilen fast immer
  zweimal fehl, bevor der dritte Versuch griff** ("Klick auf die Kontaktinformationen
  (normal) fehlgeschlagen: Element is not attached to the DOM", dito "erzwungen").
  Ursache: `_open_contact_overlay` holte den Link bisher per
  `page.wait_for_selector(...)` - das liefert ein **ElementHandle**, eine EINMALIGE
  Referenz auf den zum Abrufzeitpunkt existierenden DOM-Knoten. Rendert LinkedIns SPA
  diesen Teil der Seite kurz danach neu (React ersetzt den Knoten, auch wenn er
  inhaltlich identisch aussieht), wird die alte Referenz "detached" - `.click()` UND
  `.click(force=True)` scheitern dann beide mit genau dieser Meldung, weil beide
  dieselbe veraltete Referenz benutzen; nur der dritte Versuch (`el.click()` per
  `evaluate()` auf der alten Objektreferenz) traf über Event-Bubbling noch den
  richtigen Handler. Betraf beim Testkorpus praktisch jedes fremde Profil, beim eigenen
  Testprofil nie aufgefallen (wahrscheinlich seltener/schneller geladen). **Fix:** `link`
  ist jetzt ein **Locator** (`page.locator(...)`) statt eines ElementHandles - ein
  Locator löst den Selektor bei JEDER Aktion neu auf und trifft so zuverlässig das
  aktuell existierende Element, ohne die drei Klickstrategien selbst aufzugeben (die
  bleiben für andere Fälle wie ein von einem Banner verdecktes Element). **Verifiziert**
  mit echtem headless Chrome (kein Mock): eine Testseite, die ihren Link 150ms nach dem
  Laden durch einen neuen, inhaltlich identischen Knoten ersetzt, reproduziert exakt
  "Element is not attached to the DOM" für `ElementHandle.click()` **und**
  `.click(force=True)` - der Locator-Klick auf dieselbe Seite trifft dagegen zuverlässig
  den frischen Knoten (bestätigt per `window.__clicked`-Marker im neuen Element).
- **CSV-Export: jetzt datumsversioniert, eine neue Datei je Lauf statt fortlaufendem
  Anhängen.** Bisher wurde `output_results.csv` bei jedem Lauf im Anhänge-Modus
  geöffnet (`"a"`) - über mehrere Läufe hinweg wuchs eine einzige, immer größere Datei
  an, ohne erkennbare Grenze zwischen den Läufen. Jetzt: `output_results_
  <TTMMJJJJ>.csv` (Datum = Tag des Laufs, analog zu `output_json/*.json`), im
  Schreib-Modus (`"w"`) geöffnet - jeder Lauf bekommt seine eigene, klar abgegrenzte
  Datei; innerhalb eines Laufs weiterhin zeilenweise + geflusht (Absturzsicherheit
  bleibt). `CsvWriter` nimmt jetzt einen Ordner (`OUTPUT_CSV_DIR`, vorher
  `OUTPUT_CSV_PATH`) statt eines festen Dateipfads entgegen. Verifiziert: ein
  vorhandener "alter Stand" unter demselben Dateinamen wird beim nächsten Lauf sauber
  überschrieben, nicht fortgeschrieben.
- **Windows-Konsole pausiert nicht mehr bei einem versehentlichen Klick
  (QuickEdit-Modus deaktiviert).** Windows-Konsolen pausieren per Voreinstellung den
  gesamten Prozess, sobald man mit der Maus hineinklickt/markiert - bei einem länger
  laufenden Scraping-Lauf ein echtes Risiko (ein Doppelklick pausiert den Lauf
  unbemerkt, bis jemand Enter drückt). `main()` schaltet den QuickEdit-Modus für die
  aktuelle Konsole jetzt beim Start ab (`SetConsoleMode` via `ctypes`, reine
  Bequemlichkeit, best-effort - wirkungslos und harmlos ohne echte Windows-Konsole,
  z. B. unter einer IDE). Getestet: Aufruf bricht in einer umgeleiteten/nicht-Konsolen-
  Umgebung nicht ab (no-op).

## 0.7.10
- **Fallback bei Chrome-Absturz mitten im Lauf.** Bisher: stürzte der Browser während
  eines Profils ab, fing jede weitere Lazy-Sektion den (identischen) Fehler einzeln ab
  und protokollierte ihn - das Profil wurde am Ende trotzdem geschrieben, nur mit
  lauter `N/A`-Feldern statt eines klaren "übersprungen". `BrowserFetcher` erkennt jetzt
  über eine neue `crashed`-Property (gesetzt in `_check_crashed()`, geprüft nach jedem
  Fehler in `get_html()` über `page.is_closed()`), wenn die Seite/der Browser weg ist.
  `scrape_profile` bricht das Profil dann als Ganzes ab (`_raise_if_browser_crashed`)
  statt Feld für Feld weiterzumachen. `run_scraping` fängt genau diesen Fall auf,
  startet den Browser neu (`browser_fetcher.recycle()` - die Anmeldung im persistenten
  Profil bleibt erhalten) und versucht **nur dieses eine Profil** von vorn
  (`config.PROFILE_RETRY_ATTEMPTS = 1`), statt den ganzen Lauf neu zu starten. Andere
  Fehler (Authwall/Checkpoint, ein Profil ohne freigegebene Kontaktdaten) lösen bewusst
  **keinen** Retry aus - ein Neustart würde daran nichts ändern und nur unnötige
  zusätzliche Anfragen erzeugen. Verifiziert mit gemockten Tests: (1) `crashed` wird
  korrekt gesetzt/zurückgesetzt (`_page.is_closed()` bzw. `_page is None` → `True`,
  `close()`/`recycle()` → `False`); (2) ein simulierter Absturz löst genau einen Retry
  aus (Browser-Neustart, zweiter Versuch schreibt das Profil korrekt); (3) ein
  Nicht-Absturz-Fehler (z. B. Authwall) löst **keinen** Retry aus.
- **`parser_education`/`parser_languages`/`parser_certifications`: Sektions-Überschrift
  leakte bei genau einem Eintrag ins Ergebnis.** Neuer Fund beim erneuten Prüfen der
  Testkorpus-Outputs (Screenshot-Abgleich Sebastian Brinkmann/Arne W.): bei genau einer
  Ausbildung lieferte der Parser `name: "Ausbildung"` (die Sektions-Überschrift selbst!)
  statt des Schulnamens, und `fachrichtung` bekam stattdessen den Schulnamen - der
  eigentliche Abschluss (`"Bachelor of Science - BS, Physical Geography"`) fehlte
  komplett. Ursache: `dom_utils._single_entry` (Rückfall für eine Sektion ohne `<hr>`,
  siehe v0.7.2) erfasst den **gesamten** Sektionstext inkl. der Überschrift, weil dort -
  anders als bei mehreren Einträgen (`_split_by_hr`) - kein `<hr>`-Container die
  Überschrift vom Inhalt abgrenzt. Bei Zertifikaten war das nie aufgefallen, weil deren
  Überschriften ("Bescheinigungen und Zertifikate" etc.) schon vorher in
  `_NOISE_LINE_MARKERS` standen - "Ausbildung"/"Sprachen" aber nicht. Fix: neue
  `_SECTION_HEADINGS`-Zuordnung je SDUI-Sektion, `_single_entry` entfernt eine führende
  Zeile nur bei **exaktem** Treffer (nicht als Teilstring wie `_NOISE_LINE_MARKERS`) -
  sonst hätte z. B. eine echte Fachrichtung wie „Ausbildung, IT-Systemelektroniker"
  (Martin Reimanns DDV-Mediengruppe-Eintrag) fälschlich mit verworfen werden können.
  **Verifiziert:** synthetische Nachbildung des gemeldeten Falls liefert jetzt Schule/
  Abschluss/Zeitraum korrekt; volle Regression gegen die echten Dumps unverändert
  (Ausbildung 4/4 inkl. „Ausbildung, IT-Systemelektroniker", Zertifikat 1/1, Kenntnisse
  26, Sprachen 3/3, Erfahrung 5/5, Kontakt korrekt).
- **Wichtig:** auch dieser Fix wirkt nur auf künftige Läufe - die Outputs vom 11.09.
  brauchen für Kap. 4 ohnehin schon wegen v0.7.9 einen erneuten Scraping-Lauf.

## 0.7.9
- **`parser_experience.py`: Zeitraum/Arbeitsverhältnis/Standort landeten teils in den
  falschen Feldern - gefunden beim ersten echten Testkorpus (10 fremde
  Einwilligungsprofile, Lauf vom 11.09., in der Text-Sitzung geprüft).**
  Zwei Ursachen, beide dieselbe Klasse Fehler (feste Spalten-/Absatz-Position statt
  Inhaltsprüfung):
  1. **Mehrfach-Gruppe (mehrere Rollen bei einer Firma), `_parse_multi_position_group`:**
     Code nahm `<li>`-Absatz `[1]` immer als Arbeitsverhältnis und `[2]` als
     "Zeitraum · Dauer" an. Hat eine Rolle aber **kein** eigenes
     Arbeitsverhältnis-`<p>` (recht häufig bei der jüngsten/aktuellen Position),
     rutscht der Zeitraum auf `[1]` und `[2]` wird zu Standort oder sogar einer frei
     formulierten Aufgabenbeschreibung - beides landete unbemerkt in den falschen
     Feldern. Konkret beobachtet: `arbeitsverhaeltnis: "Juni 2026–Heute · 4 Monate"`
     (ein Zeitraum!) und `zeitraum: "Nürnberg, Bayern, Deutschland"` (ein Ort!) bzw.
     `zeitraum: "Transforming IT from on-premise operations to a secure, ..."`
     (Fließtext!) in mehreren Profilen des Testkorpus.
  2. **Standort-Extraktion** (`_group_header`'s `ps[2]`, `_parse_single_position`'s
     `ps[3]`): beide nahmen den jeweiligen Absatz ungeprüft als Ortsangabe. Tatsächlich
     kann dort auch eine Kenntnisse-Zusammenfassung stehen ("Data Warehousing, SQL
     Server Integration Services (SSIS) und +3 Kenntnisse") oder eine mehrsätzige/
     stichpunktartige Aufgabenbeschreibung der Position - beides wurde bisher unbesehen
     als `standort` übernommen.
  - **Fix:** Zeitraum/Dauer werden jetzt über `looks_like_period` (Jahreszahl im Text,
    aus `dom_utils.py` - bisher ungenutzt) erkannt, unabhängig von der Absatz-Position.
    Arbeitsverhältnis wird über eine Positivliste bekannter Werte erkannt (`vollzeit`,
    `teilzeit`, `praktikum`, `werkstudium`, `freiberuflich`, `selbstständig`,
    `befristet`, `unbefristet`, + englische Entsprechungen), nicht über die Position.
    Ein Standort-Kandidat wird nur übernommen, wenn er weder wie ein Zeitraum noch wie
    ein "... und +N Kenntnisse"-Rest aussieht noch länger als 80 Zeichen ist (neue
    `_looks_like_location`-Prüfung) - sonst `NOT_AVAILABLE` statt falscher Daten (DQ4:
    lieber `N/A` als falscher Inhalt).
  - **Verifiziert:** eine synthetische Nachbildung aller drei beobachteten Muster
    (fehlendes Arbeitsverhältnis-`<p>`, Beschreibungstext statt Zeitraum, Kenntnisse-
    Rest bzw. Fließtext statt Standort) liefert jetzt in jedem Fall entweder den
    korrekten Wert oder `N/A` - nie mehr Zeitraum/Ort/Fließtext im falschen Feld.
    Regressionscheck gegen den echten, bereits verifizierten Martin-Reimann-Dump:
    weiterhin 5/5 korrekt, unverändert zu v0.7.5.
  - **Wichtig:** Die bereits erzeugten Output-Dateien (`output_results.csv`,
    `output_json/*.json` vom 11.09., 10 externe Profile) enthalten noch die
    **fehlerhaften** Werte - dieser Fix ändert nur den Parser, nicht rückwirkend
    bestehende Dateien. Ein erneuter Scraping-Lauf (Menüpunkt 2) über dieselben
    Profil-URLs erzeugt korrigierte Ausgaben.
  - Für Kap. 3.4/4: die frühere Aussage „`parser_experience` verifiziert 5/5" bezog
    sich ausschließlich auf das eigene Testprofil, das **keine** Mehrfach-Gruppe
    (mehrere Rollen bei einer Firma) enthält - der jetzt behobene Fehlerpfad war damit
    nie durch echte Daten abgedeckt. Erst der externe Testkorpus deckte ihn auf; siehe
    §6-Log als Beispiel dafür, wie wichtig ein Testkorpus jenseits des eigenen Profils
    ist (§5 Punkt 10 war genau deshalb offen geführt).

## 0.7.8
- **pkg_resources-Deprecation-Warnung beim exe-Start unterdrückt.** Seit dem
  `setuptools<81`-Workaround (0.7.6) landet `pkg_resources` mit im Bundle (ein
  automatischer PyInstaller-Paket-Runtime-Hook, `pyi_rth_pkgres`, importiert es für
  ein Paket im Abhängigkeitsbaum, das noch das alte Namespace-Package-Schema nutzt)
  und meldet dabei bei **jedem** exe-Start seine eigene Deprecation-Warnung - rein
  kosmetisch, keine Funktionsänderung, aber unschöne Konsolenausgabe. Ein Filter in
  `run.py` selbst kam zu spät (der auslösende Import passiert schon vorher, in einem
  automatischen Runtime-Hook). Fix: neuer eigener Runtime-Hook
  `build/rthook_suppress_pkg_resources.py`, über `Analysis(runtime_hooks=[...])` in
  `build/LinkedInScraper.spec` eingebunden - eigene Runtime-Hooks laufen laut
  PyInstaller (`depend/analysis.py:analyze_runtime_hooks`) nachweislich VOR den
  automatisch erkannten Paket-Hooks, der Filter ist also rechtzeitig aktiv. Verifiziert
  per Neubau + Start: Warnung verschwunden, Menü erscheint direkt; Fingerprint-Check
  (Menüpunkt 4) weiterhin fehlerfrei (alle fünf Prüfungen grün, wie zuvor).

## 0.7.7
- **Datenhoheit zwischen exe und Quellcode umgedreht.** Bisher zeigte die exe auf
  dieselbe `data/` wie der Quellcode (`linkedin_scraper/data/`) - auf Wunsch des Autors
  ist es jetzt umgekehrt: die "kanonische" Kopie (insbesondere das Browserprofil mit
  der aktiven Anmeldung) wohnt jetzt **bei** `LinkedInScraper/` (dem exe-Ausgabeordner),
  der Quellcode-Betrieb greift nur noch darauf zu. Grund: `LinkedInScraper/` soll eine
  in sich geschlossene, portable Einheit sein, die sich "zur Not" komplett auf ein
  anderes Gerät kopieren lässt - exe + Session zusammen, ohne Quellcode.
- **`LinkedInScraper/` in `app/` (exe) und `data/` (Session/Ausgabe) geteilt.** Vor der
  Umsetzung verifiziert: PyInstallers `COLLECT`-Schritt räumt sein Zielverzeichnis bei
  jedem Build vollständig leer (mit einer Marker-Datei bestätigt) - `data/` direkt neben
  der exe zu halten hätte also jeden Rebuild die Session gekostet. Deshalb jetzt
  `LinkedInScraper/app/LinkedInScraper.exe` (von PyInstaller verwaltet,
  `build/LinkedInScraper.spec`: `COLLECT(..., name="app")`, `build/build.ps1`:
  `--distpath` zeigt auf `LinkedInScraper/`) und `LinkedInScraper/data/` als
  Geschwisterordner, den kein Build je anfasst (mit Marker-Datei nach dem Umbau erneut
  bestätigt). `config.py`: `DATA_DIR` ist jetzt `_APP_ROOT/"data"`, `_APP_ROOT` bei
  `sys.frozen` aus `sys.executable.parent.parent` (liegt jetzt zwei statt eine Ebene
  unter `LinkedInScraper/`), im Quellcode-Betrieb `PROJECT_ROOT/"LinkedInScraper"` -
  beide Wege zeigen auf dieselbe, einzige `data/`. Die reale, bestehende
  `linkedin_scraper/data/` (aktives `li_at`, echte Debug-Dumps/Output) wurde per
  `robocopy /MOVE` migriert (ein einfaches `mv` scheiterte an einer
  Windows-Dateisperre) - Login und Testdaten blieben dabei erhalten.
- **Fallback für ein auf dem neuen Gerät nicht mehr startbares, mitgebrachtes Profil.**
  `BrowserFetcher` bekommt einen neuen Parameter `allow_profile_reset` (Default
  `False`); nur der explizite Anmelde-Ablauf (Menüpunkt 1, `_open_profile_for_login`)
  setzt ihn auf `True`. Schlägt dort der Profilstart fehl (z. B. weil das Profil von
  einer anderen Maschine mitgebracht wurde und dort inkompatibel ist), verschiebt die
  neue Methode `_reset_profile_and_relaunch` das bestehende Profil zeitgestempelt zur
  Seite (`browser_profile_defekt_<Datum-Zeit>`, **nie gelöscht**) und versucht es mit
  einem frischen, leeren Profil erneut - der Bediener meldet sich danach einmal neu an.
  Bewusst **nicht** im normalen Scraping-/Debug-/Fingerprint-Pfad aktiv: dort kann
  "Profil startet nicht" auch schlicht heißen, dass das Tool noch in einem zweiten
  Fenster läuft - ein stilles Zurücksetzen wäre dort das falsche Verhalten und bleibt
  ein harter Fehler wie zuvor.
- Verifiziert: (1) zwei Marker-Datei-Tests bestätigen, dass weder der erste noch ein
  erneuter Rebuild `data/` anfasst; (2) ein isolierter Test mit gemocktem
  `_launch_persistent` (1. Aufruf wirft, 2. Aufruf liefert einen Sentinel-Wert) prüft
  die Reset-Logik Ende-zu-Ende: altes Profil samt Markerdatei landet unverändert im
  Quarantäne-Ordner, ein neues leeres Profilverzeichnis entsteht, der Rückgabewert
  stammt vom zweiten, erfolgreichen Versuch; (3) die migrierten echten Daten wurden
  stichprobenartig geprüft (scraper.log, browser_profile-Größe).
- README („Kompilieren") und `build/`-Kommentare
  entsprechend aktualisiert.

## 0.7.6
- **Python-Umgebung von 3.10.0 auf 3.12.10 umgestellt** (Anlass: Wunsch nach einer
  kompilierten .exe, siehe unten). Python 3.10 erreicht Oktober 2026 End-of-Life;
  3.12 ist die aktuell voll gepflegte Version (3.13 läuft Ende des Jahres aus der
  Bugfix- in die reine Security-Phase). Zusätzlicher, konkreter Auslöser: das exakt
  gepinnte Python 3.10.0 hat einen bekannten CPython-Bug in `dis.py`
  (`IndexError: tuple index out of range` beim Scannen großer generierter Module wie
  `playwright.sync_api`, behoben ab 3.10.1) - PyInstaller kann damit unter 3.10.0
  grundsätzlich nicht bauen, unabhängig von der PyInstaller-Version selbst. Verifiziert:
  alle sieben Parser liefern unter 3.12.10 byte-identische Ergebnisse zu 3.10.0 gegen
  dieselben Debug-Dumps (Ausbildung 4, Kenntnisse 26, Sprachen 3, Zertifikat 1/1,
  Kontakt E-Mail+Geburtstag), ebenso die Fetcher-/Validator-Regressionstests aus
  v0.7.5 (Status-/Redirect-Matrix). `requirements.txt`-Kopf aktualisiert.
- **Kompilierte .exe (PyInstaller, onedir) hinzugefügt** - siehe `build/`. Neuer
  Build-Einstiegspunkt `run.py` im Projektstamm. `config.py` leitet `PROJECT_ROOT` bei
  eingefrorenem Zustand (`sys.frozen`) aus `sys.executable` statt `__file__` ab, damit
  die exe **dieselbe** `linkedin_scraper/data/` benutzt wie der Quellcode-Betrieb -
  bewusst kein eigenes zweites Browserprofil, sonst sähe LinkedIn zwei Geräte mit
  derselben Session (das Muster, das in v0.4.0 zu Logouts führte).
  `build/build.ps1` baut nach `<Projektstamm>/LinkedInScraper/LinkedInScraper.exe`
  (Geschwisterordner von `linkedin_scraper/`, nicht `build/dist/`), damit diese
  Pfadableitung stimmt. `build/LinkedInScraper.spec` bündelt Playwright (inkl.
  `node.exe`-Treiber) und curl_cffi per `collect_all` (beide bringen Binärdateien mit,
  die PyInstallers Standard-Analyse bei CFFI-/Subprocess-Paketen nicht zuverlässig
  findet); onedir statt onefile, damit diese Binärdateien nicht bei jedem Start neu in
  einen Temp-Ordner entpackt werden müssen. `build/requirements-build.txt` pinnt die
  reinen Build-Werkzeuge (PyInstaller 6.22.2, `setuptools<81` - neuere Setuptools haben
  `pkg_resources` entfernt, das PyInstallers modulegraph noch braucht) getrennt von
  `requirements.txt`. Verifiziert: exe gebaut und gestartet, Menüpunkt 4
  (Fingerprint-Check, ohne LinkedIn-Zugriff) lief vollständig durch - der gebündelte
  Playwright-Treiber startet echtes Chrome, alle fünf Prüfungen grün - und die
  Log-Zeile landete in derselben `linkedin_scraper/data/scraper.log` wie bei
  `python -m linkedin_scraper.main`.

## 0.7.5
- **`fetcher.py`: 5xx wurde nicht wiederholt, obwohl der Docstring genau das verspricht
  ("Retry/Backoff bei 429/403/5xx").** Der Code behandelte nur `403`/`429` mit Backoff;
  jeder andere Status inkl. `500`/`502`/`503` warf sofort `FetchError` ohne einen
  einzigen Versuch erneut. Bei einem vorübergehenden Serverfehler bei LinkedIn wurde das
  Profil damit sofort übersprungen statt nach kurzer Pause erneut versucht — eine echte
  Lücke gegenüber **NFA1 (Robustheit)**. Fix: `500 <= status_code < 600` fällt jetzt in
  denselben Retry-Zweig wie `403`/`429` (gleicher fester Backoff `5·2^(Versuch-1)`), nur
  mit passenderer Logmeldung ("serverseitiger Fehler" statt "Rate-Limit/Bot-Check").
  `voyager_client.py` hat dasselbe Muster, bleibt aber unverändert - der Weg ist
  abgeschaltet (`USE_VOYAGER_FOR_LAZY = False`) und nur als dokumentierter
  Negativbefund im Baum.
- **`session/validator.py`: ein harmloser Redirect wurde fälschlich als abgelaufene
  Session gemeldet.** Ein 3xx, dessen `Location` weder `login`, `authwall` noch
  `checkpoint` enthält (z. B. eine Sprach-/Regionsvariante von `/feed/`), fiel bisher
  auf `status_code == 200` durch - das ist bei jedem Redirect falsch. Fix: ein
  unauffälliges Redirect-Ziel gilt jetzt als gültige Session (`True`); nur ein Redirect
  auf einen der drei Marker gilt als abgelaufen (`False`).
- Beide Fixes mit einem Mini-Testskript gegen die Statuscode-/Redirect-Matrix verifiziert
  (503→200 retryt und gelingt; durchgehend 502 wirft erst nach `MAX_RETRIES` einen
  Fehler statt sofort; 404 bleibt sofortiger Fehler; benigner Redirect → gültige Session).
- Kein Eingriff an Parsern oder Fetch-Layer-Struktur; reine Fehlerbehandlungs-Fixes.

## 0.7.4
- **Performance: weniger lokale Rendering-Last im Browser-Weg.** Betrifft ausdrücklich
  nur die Arbeit auf dem Rechner (Download, RAM, Rendering) - die Politeness-Delays
  (NFA2) und die Zugriffsrate gegenüber LinkedIn bleiben unverändert.
  1. **`page.goto(wait_until="domcontentloaded")`** statt `"load"` - kein Warten mehr auf
     alle Sub-Ressourcen; direkt danach folgt ohnehin ein gezieltes `wait_for_selector`.
  2. **Asset-Blocker** (`config.BROWSER_BLOCK_ASSETS`, Default an): Bilder, Media und
     Web-Fonts werden per `context.route` gar nicht erst geladen. Dokument, Skripte,
     Stylesheets und XHR bleiben unberührt. Größter Hebel auf schwacher Hardware /
     langsamer Leitung. Beim manuellen Login (Menüpunkt 1) ist der Blocker aus
     (`block_assets=False`), damit die Anmeldeseite normal aussieht.
  3. **Adaptives Scrollen**: `_scroll_through` bricht ab, sobald der Wartemarker der
     LazyColumn sichtbar ist, statt das feste 6-12-Schritt-Budget zu verbrauchen
     (spart ~3-6 s je Detailseite; wirkt eher wie menschliches „aufhören, wenn man's
     sieht").
  4. **`BROWSER_ENTRY_WAIT_MS` 6000 → 4000** - die volle Wartezeit greift nur noch bei
     wirklich leeren Sektionen.
  5. **Doppelter Feed-Aufwärmer entfernt**: `run_scraping` machte einen HTTP-`get_html`
     auf den Feed *und* der Browser wärmt sich selbst über den Feed auf. Der HTTP-Teil
     (inkl. eines `rate_limiter.wait()` von 6-14 s) entfällt, wenn ein Browser-Fetcher
     dabei ist.
  6. **Speicherhygiene für lange Läufe** (`config.BROWSER_RECYCLE_EVERY_PROFILES`, Default
     25): der Browser-Kontext wird alle N Profile neu aufgesetzt, damit der RAM nicht
     anwächst. Die Anmeldung liegt im persistenten Tool-Profil und überlebt das;
     der Feed-Aufwärmer läuft danach einmalig erneut. 0 = nie.
- Nebenbei: `main()` setzt `sys.stdout/stderr` auf `errors="replace"`, damit ein
  Sonderzeichen in einer (z. B. Playwright-)Fehlermeldung auf einer cp1252-Windows-
  Konsole nicht mehr den ganzen Lauf mit `UnicodeEncodeError` abbricht.
- Kein Eingriff an Parsern, Fetch-Logik oder Ausgabe.

## 0.7.3
- **JSON-Ausgabe ergänzt (FA8: „Serialisierung nach CSV *und* JSON").** Bisher schrieb
  das Tool nur die CSV. Neu: `io_handlers/json_writer.py` schreibt **je Profil eine
  eigene Datei** `<Vorname>_<Nachname>_<TTMMJJJJ>.json` (Datum = Tag des Laufs, z. B.
  `Martin_Reimann_10092026.json`) nach `data/output_json/` (`config.OUTPUT_JSON_DIR`).
  Ohne verwertbaren Namen wird der URL-Slug genommen; zwei gleichnamige Profile im selben
  Lauf bekommen einen Zähler (`…_2.json`). Ein früherer Lauf am selben Tag wird bewusst
  überschrieben (gleicher Tag → gleiches Ergebnis, NFA5/NFA8).
- **Struktur** bildet das Zielschema aus Thesis 3.3.3 verschachtelt ab: `meta`
  (`profil_url`, `abgerufen_am`, `werkzeug_version`), `person` (die acht Kopffelder),
  dazu die Listen `berufserfahrung`, `ausbildung`, `kenntnisse`, `zertifikate`,
  `sprachen`. Fehlende Skalarfelder sind hier `null` (FA6: „`null`-Kennzeichnung
  fehlender Felder"); die CSV behält `N/A`, weil eine leere Tabellenzelle dort
  mehrdeutig wäre. Leere Kategorien sind `[]`.
- `run_scraping` schreibt CSV und JSON im selben Loop je Profil (inkrementell, damit ein
  Abbruch mitten im Lauf die bereits erhobenen Profile vollständig hinterlässt, NFA1).
- Reine Ausgabe-Erweiterung; an Fetch-/Parser-Pfad ändert sich nichts.

## 0.7.2
- **Geburtstag wird jetzt geparst.** Im Kontakt-Overlay steht er als zwei
  aufeinanderfolgende `<p>`: `<p>Geburtstag</p><p>10. Mai</p>` (Tag + Monatsname, i. d. R.
  ohne Jahr). Die bisherige Regex `Geburtstag[^0-9]{0,40}…` scheiterte an den ~100
  Zeichen gehashter CSS-Klassen zwischen den beiden Tags. `parser_contact._extract_birthday`
  liest ihn nun strukturell über das Label-`<p>` und dessen Nachbar-`<p>`
  (`birthDateOn`-JSON- und lose Textregex bleiben als Rückfall). Format `TT.MM.` bzw.
  `TT.MM.JJJJ`, falls ein Jahr angegeben ist. Verifiziert: `10.05.`
- **Einzelnes Zertifikat wird jetzt erkannt.** `dom_utils.iter_sdui_entries` konnte nur
  Sektionen mit `<hr>`-Trennern (ab 2 Einträgen) oder Zeilen-Buttons zerlegen. Bei genau
  einem Zertifikat gibt es keinen Trenner → 0 Einträge. Neuer Rückfall
  `dom_utils._single_entry`: behandelt eine Sektion ohne Trenner als einen Eintrag,
  schneidet die als „Kenntnisse:" angehängten verknüpften Skills ab und verwirft
  Sektionsüberschrift + „Nachweis anzeigen"-Button (neue Einträge in
  `_NOISE_LINE_MARKERS`). `parser_certifications` selbst unverändert - die Feldzuordnung
  (Name/Aussteller/Ausstelldatum, „Gültig bis" wird verworfen) ist damit erstmals an
  echten Daten verifiziert: `IBM Generative & Agentic AI Foundation` / `IBM` / `Aug. 2026`.
- Regressionscheck: Ausbildung 4/Kenntnisse 26/Sprachen 3 gegen den 09-10-Browserlauf
  unverändert; Legacy-Dumps (früheres Markup) weiter Kenntnisse 10/Sprachen 3.
- **Debug-Dump (Menü 3) läuft nur noch über den Browser.** Die „Quelle: 1=HTTP 2=Browser"-
  Abfrage entfällt; `_dump_single_page` nimmt fest den Browser-Fetcher, Dateiname immer
  `…_browser.html`. Der HTTP-/curl_cffi-Weg rendert die client-seitigen Sektionen nicht
  und wird für Dumps nicht mehr gebraucht — im **Scraping-Lauf** (Menü 2) holt HTTP
  weiterhin Profilkopf + Erfahrung.

## 0.7.1
- **CSV: komplett leere Kategorie wird jetzt in *allen* ihren Spalten mit `N/A`
  markiert, nicht nur in der ersten.** Vorher stand bei einem Profil ganz ohne
  Zertifikate in Zeile 1 nur `Zertifikat - Name = N/A`, `Aussteller`/`Datum` blieben
  leer (und in den Folgezeilen alles leer). Das war für DQ4 missverständlich - ein
  leeres Feld ("nicht befüllt") ist nicht dasselbe wie `N/A` ("nachweislich nicht
  vorhanden"). Neu: Zeile 1 der leeren Kategorie = `N/A` in jeder Spalte; Folgezeilen
  bleiben leer (die Markierung wird - wie Personendaten oder eine kürzere Liste -
  nicht auf jede Zeile wiederholt). `linkedin_scraper/io_handlers/csv_writer.py`.
- Verifiziert gegen den 09-10-Browserlauf: Profil/Kontakt/Erfahrung 5/Ausbildung 4/
  Kenntnisse 25/Sprachen 3/Zertifikate 0 - Parser-Ausgabe deckt sich 1:1 mit
  `output_results.csv`.

## 0.7.0
- **CLI aufgeräumt: der Login-Weg über die Browser-Extension ist raus.** Er hatte in der
  Praxis Logouts ausgelöst (Cookie-Injektion in einen fremden Browserkontext)
  und ist damit kein sinnvoller Weg mehr. Neues Menü:
    1. Bei LinkedIn anmelden (Tool-Browserprofil)   [war Punkt 5]
    2. Scraping starten
    3. Debug: Rohdaten einer Detailseite speichern
    4. Browser: Fingerprint prüfen (ohne LinkedIn-Zugriff)
    5. Beenden
- **Kein separates "Session laden" mehr.** Die Session kommt ausschließlich aus dem
  persistenten Tool-Browserprofil und wird bei Menüpunkt 2/3 **beim ersten Aufruf
  automatisch** aufgebaut (`_ensure_session` / `_open_session`). Liegt dort keine
  gültige Anmeldung, kommt eine klare Anweisung ("Menüpunkt 1 wählen … oder Tool
  neu starten") statt einer Exception.
- **Einheitliche Fehlermeldung bei Abbruch.** Scheitert ein Lauf mit `FetchError`
  (Session abgelaufen, Bot-Check, Profil gesperrt), meldet die CLI
  "Bitte das Tool neu starten. Wenn die Anmeldung abgelaufen ist: Menüpunkt 1."
- `config.SESSION_SOURCE` steht jetzt auf `"browser_profile"` (Standard). Die Werte
  `"extension"` / `"auto"` bleiben dokumentiert, werden von der CLI aber nicht mehr
  angesteuert. Die Native-Messaging-Bridge (`session/`, `browser_extension/`) bleibt als
  dokumentierter, nicht mehr benutzter Weg im Repo.
- Menüpunkt 4 nutzt einen bereits geöffneten Session-Browser mit, statt einen zweiten
  zu starten (das persistente Profil lässt nur ein Chromium gleichzeitig zu).

## 0.6.0
- **Lazy-Parser auf das neue SDUI-Markup umgestellt.** Der erste
  komplette Browser-Lauf (09-10) hat gezeigt: der Browser-Fetcher hydratisiert die
  LazyColumns jetzt zuverlässig, aber LinkedIn hat die Eintragsstruktur erneut
  gewechselt - `div[componentkey^="entity-collection-item-"]` gibt es nicht mehr, und
  Kenntnisse/Sprachen/Zertifikate haben ihr eigenes `data-testid` verloren.
  - **`dom_utils.iter_sdui_entries(html, screen_suffix)`** (neu): findet die Sektion über
    `data-sdui-screen$="Profile<Sektion>Details"` (stabiler semantischer Name, kein Hash)
    bzw. die LazyColumn, deren `componentkey` auf `<Sektion>DetailsSection` endet. Trennt
    Einträge über `<hr>`-Gruppen (Ausbildung, Sprachen, Zertifikate) bzw. über den
    "... bestätigen"-Button je Zeile (Kenntnisse). Erkennt den Leerzustand ("Noch keine
    Informationen verfügbar") und steigt bei noch vorhandenem `entity-collection-item-`
    aus, damit alte Dumps weiter über den Alt-Weg laufen.
  - `dom_utils.iter_detail_entries` bleibt als Rückfall für Dumps im früheren Markup.
  - `parser_education` / `_skills` / `_languages` / `_certifications` nutzen zuerst
    `iter_sdui_entries`, dann den Rückfall. Zeitraum/Datum werden über eine
    Jahreszahl-Erkennung (`looks_like_period`) gefunden statt über eine feste Position.
- **`parser_profile`: Headline-Fix.** Die neue Topcard beginnt mit Zähl-Markierungen
  `· 1.` / `· 2.`; `_card_paragraphs` verwarf bisher nur exakt `·` und nahm dadurch
  `· 1.` als Headline. Jetzt greift `_MIDDOT_NOISE_RE` (Mittelpunkt + optionale Zahl).
- **`browser_fetcher`: Wartemarker für Detailseiten** von `entity-collection-item-` auf
  `[data-component-type="LazyColumn"] p` umgestellt (Inhalt ist gerendert).
- **Verifiziert gegen die 09-10-Browser-Dumps:** Profil-Headline OK, Kontakt-E-Mail OK,
  Erfahrung 5/5, Ausbildung 4/4, Kenntnisse 25 (Buttons gezählt, sauberer Anfang/Ende),
  Sprachen 3/3, Zertifikate 0 (Leerzustand). Alt-Dumps über den Rückfall weiterhin
  4 / 10 / 3.

## 0.5.2
- **ERFOLG: Die Kontakt-E-Mail kommt an.** Erster Lauf mit dem echten Klick (v0.5.1)
  gegen das Testprofil: Dump 219 KB statt 151 KB, `mailto:` vorhanden,
  `parse_contact_info` liefert die Adresse. Damit ist das letzte der sechs
  client-seitig gerenderten Felder erreichbar - über den Browser-Weg, ohne Voyager
  und ohne Logout.
- **Klick abgehärtet**, weil der Kontakt-Link je nach Profil unterschiedlich erreichbar
  ist (Hinweis des Autors: "je nach Länge der Profilinhalt gibt es einen Weg zum
  Öffnen bzw. eben auch nicht"):
  - **Drei Klickstrategien** nacheinander: normal -> `force=True` (falls ein Banner oder
    Sticky-Header davorliegt) -> `el.click()` direkt im DOM. Nach jedem Versuch wird
    geprüft, ob der Dialog wirklich offen ist.
  - **Klare Unterscheidung zweier Fälle:** Topcard da, aber kein Kontakt-Link = das
    Profil gibt schlicht keine Kontaktdaten frei (Info-Log, Felder bleiben N/A, kein
    Fehler). Weder Topcard noch Link = die Seite wurde nicht geladen oder das Markup hat
    sich geändert (Warnung).
  - **Zweistufiges Warten** (`BROWSER_DIALOG_WAIT_MS`, neu): erst auf einen SICHTBAREN
    `[role="dialog"]`, dann auf ein `mailto:` darin. Bleibt das mailto aus, gilt das
    NICHT als Fehler - viele Profile geben keine E-Mail frei, der Dialog ist trotzdem
    korrekt geöffnet.
  - `_open_contact_overlay()` gibt jetzt `bool` zurück statt stillschweigend
    weiterzulaufen.

## 0.5.1
- **Kontakt-Overlay wird jetzt geklickt statt angesprungen.** Ein direkter Aufruf von
  `/overlay/contact-info/` liefert die Profilseite mit dem Popover im DOM, aber mit
  `inert=""` und Opacity 0 - also geschlossen und ohne Inhalt. Zweimal verifiziert
  (08.09., zuletzt sogar mit nativer Profil-Session). LinkedIn lädt den Inhalt erst
  beim echten Klick. `BrowserFetcher._open_contact_overlay()` sucht deshalb
  `a[href*="/overlay/contact-info/"]`, scrollt ihn in den Blick, klickt mit kurzer
  zufälliger Verzögerung und wartet auf einen SICHTBAREN `[role="dialog"]`.
- **Fix: Scrollen stürzte ab, seit `BROWSER_VIEWPORT = None` der Standard ist.**
  `_scroll_through` griff weiterhin fest auf `BROWSER_VIEWPORT["width"]` zu ->
  `'NoneType' object is not subscriptable`. Das hat das Aufwärmen abgebrochen und hätte
  **alle Lazy-Sektionen lahmgelegt**, weil ohne Scrollen die LazyColumns nicht auslösen.
  Die Fenstergröße kommt jetzt aus `page.viewport_size`, sonst aus
  `window.innerWidth/innerHeight`, sonst aus einem Standardwert.
- **Fix: doppelter Funktionsblock in `main.py` entfernt.** Ein fehlerhafter Edit hatte
  `_load_session`, `_run_fingerprint_check` und `_open_profile_for_login` ein zweites Mal
  eingefügt; Python nahm jeweils die letzte - also die ALTE Fassung von Menüpunkt 5.
  Deshalb erschien im Log noch der überholte Hinweis auf `BROWSER_INJECT_COOKIES`.
- **Klare Meldung, wenn das Tool-Profil gesperrt ist.** Ein Profilverzeichnis kann nur von
  EINEM Browser benutzt werden; läuft das Tool bereits in einem zweiten Fenster oder
  hängt ein Browser aus einem abgebrochenen Lauf, kam bisher eine kryptische
  Playwright-Meldung plus irreführender Rückfall auf das gebündelte Chromium.
- **Hinweis zum Playwright-Upgrade:** Nach dem Sprung auf 1.62 müssen die gebündelten
  Browser einmalig neu geladen werden (`python -m playwright install chromium`). Betrifft
  nur den Headless-Modus und den Rückfallpfad - im Normalbetrieb läuft über
  `BROWSER_CHANNEL = "chrome"` das installierte Google Chrome.

## 0.5.0
- **Die Anmeldung im Tool-Browserprofil macht die Extension überflüssig.** Bisher
  musste man nach dem manuellen Login (Menüpunkt 5) trotzdem über Menüpunkt 1 eine
  zweite Session aus dem Alltags-Chrome hereinreichen - das waren zwei Sitzungen von
  zwei Geräten im selben Lauf und hat den Sinn des Tool-Profils zunichte gemacht.
  Neu `SESSION_SOURCE` ("auto" | "browser_profile" | "extension", Standard "auto"):
  Menüpunkt 1 sieht zuerst im Tool-Profil nach und benutzt eine dort gefundene
  Anmeldung für **beide** Wege (HTTP und Browser). Nur wenn dort nichts liegt, wird
  die Extension gefragt.
  - `BrowserFetcher.session_cookies()` liest die LinkedIn-Cookies aus dem Tool-Profil.
  - `BrowserFetcher.inject_cookies()` für den Extension-Rückfall.
  - `session_manager.build_session(cookies, quelle)` baut und validiert den HttpClient
    unabhängig davon, woher die Cookies stammen; die Quelle steht im Log.
- **Menüpunkt 5 bestätigt jetzt das Ergebnis.** Nach dem Login wird geprüft, ob ein
  `li_at` im Profil liegt und ob es ein **Ablaufdatum** hat. Fehlt das Ablaufdatum, ist
  es ein reines Sitzungs-Cookie und die Anmeldung wäre beim nächsten Start weg - der
  Menüpunkt weist dann ausdrücklich darauf hin, "Angemeldet bleiben" zu aktivieren.
- **Nachgewiesen:** Cookies MIT Ablaufdatum überleben im persistenten Tool-Profil einen
  kompletten Browser-Neustart (getestet), Cookies OHNE nicht. Die über die Extension
  injizierten Cookies sind mangels `expires` reine Sitzungs-Cookies - sie müssen jedes
  Mal neu gesetzt werden und das Profil "besitzt" nie eine dauerhafte Session. Genau
  deshalb ist die einmalige manuelle Anmeldung der dauerhafte Weg: Tage später gilt sie
  LinkedIn gegenüber als dieselbe, bekannte Sitzung auf demselben Gerät.

## 0.4.2
- **Playwright auf 1.62.0 aktualisiert** (vorher 1.36.0 von 2023 - das war sogar älter
  als die in requirements.txt deklarierte Untergrenze `>=1.40`). Nach dem Upgrade erneut
  gegen Menüpunkt 4 geprüft: alle fünf Fingerprint-Prüfungen weiterhin grün.
- **requirements.txt gepinnt** statt Untergrenzen: `requests==2.32.3`,
  `beautifulsoup4==4.13.4`, `curl_cffi==0.16.3`, `playwright==1.62.0`. Dazu die getestete
  Umgebung dokumentiert (Windows 10 19045, Python 3.10.0, Chrome 134.0.6998.89). Für ein
  Artefakt, das Monate später nachvollziehbar sein soll, sind Untergrenzen zu unscharf
  (NFA5).
- **Wirkung der portablen Vorgaben aus 0.4.1 verifiziert:** mit `BROWSER_VIEWPORT = None`
  meldet der Browser jetzt den **echten** Bildschirm (2560x1440) statt der zuvor
  vorgetäuschten 1536x864. Ein erzwungenes Viewport hatte auch `screen` mit überschrieben -
  auf einem Rechner mit kleinerem Monitor wäre daraus ein Viewport größer als der
  Bildschirm geworden, was für sich schon ein Erkennungsmerkmal ist.

## 0.4.1
- **Eine Geräte-Identität für beide Abrufwege** (neu `fingerprint.py`). Der UA-Split aus
  0.4.0 hatte ein neues Problem erzeugt: Der HTTP-Weg meldete *macOS/Chrome 131*, der
  Browser *Windows/Chrome 134* — im selben Lauf, mit demselben `li_at`. Aus Serversicht
  ein Gerätewechsel mitten in der Sitzung, also genau das Signal, das laut §9.2 die
  Ursache ist. Jetzt wird die Identität zur Laufzeit aus der Maschine abgeleitet:
  Betriebssystem aus `platform.system()`, Chrome-Hauptversion aus der real installierten
  Chrome-Installation (Windows: `HKCU\Software\Google\Chrome\BLBeacon` — die tatsächlich
  gestartete Version; der HKLM-Uninstall-Eintrag kann abweichen). Daraus User-Agent,
  `sec-ch-ua`, `sec-ch-ua-platform` und das curl_cffi-Ziel (nächstes `chromeNNN`
  **<= Hauptversion**, nie nach oben runden). `HTTP_IDENTITY_AUTO = True` steuert das;
  bei fehlgeschlagener Erkennung greifen die festen config-Werte plus Logwarnung.
  Verifiziert: abgeleitete UA ist byte-identisch mit der, die der Browser real meldet.
- **Identitäts-Header jetzt auch im curl_cffi-Pfad gesetzt.** Bisher bewusst nicht, mit
  der Begründung „sonst passt es nicht mehr zum TLS-Fingerprint". Das gilt für die
  Version, nicht für das Betriebssystem: der TLS-/HTTP-2-Fingerprint kodiert kein OS.
  Die alte Zurückhaltung war der Grund für die macOS-UA.
- **Portable Browser-Vorgaben.** `BROWSER_TIMEZONE = None` → Systemzeitzone (ein festes
  „Europe/Berlin" widerspricht auf einer fremden Maschine der IP-Geolokalisierung),
  `BROWSER_VIEWPORT = None` → echtes Fenster statt eines festen 1536×864, das größer sein
  kann als der Bildschirm der Zielmaschine.
- **`BROWSER_INJECT_COOKIES` ist jetzt dreiwertig: `True` / `False` / `"auto"` (Standard).**
  Bei `"auto"` prüft der Fetcher, ob im Tool-Profil schon ein `li_at` liegt: wenn ja,
  wird die Injektion übersprungen (die dort nativ entstandene Anmeldung gilt), sonst
  injiziert er und weist auf Menüpunkt 5 hin. Damit schaltet sich die Injektion nach
  einer einmaligen manuellen Anmeldung von selbst ab — ohne dass der Code seine eigene
  config umschreibt. Bekannte Kante: eine *abgelaufene* Profil-Anmeldung erkennt die
  Automatik nicht (das kostete einen LinkedIn-Request); die Checkpoint-Fehlermeldungen
  weisen deshalb ausdrücklich auf Menüpunkt 5 hin.

## 0.4.0
- **Browser-Identität in sich stimmig gemacht** — Kern der Fehleranalyse. Vorher meldete der Browser gleichzeitig macOS *und* Win32,
  Chrome 131 *und* Chromium 115, dazu `navigator.webdriver = true`. Jetzt:
  - **Zwei getrennte User-Agents.** `USER_AGENT`/`SEC_CH_UA` gelten ausschließlich für
    den HTTP-Weg (curl_cffi liefert für alle Chrome-Targets macOS-UAs, dort ist das
    korrekt). Neu `BROWSER_USER_AGENT = None` → der Browser benutzt seine **eigene,
    echte** UA, die per Konstruktion zu Engine und Plattform passt. Das war die Ursache
    des Widerspruchs: `browser_fetcher` hatte den HTTP-UA unbesehen mitbenutzt.
  - `BROWSER_CHANNEL = "chrome"` — echtes installiertes Google Chrome statt des
    gebündelten Chromium (Playwright 1.36 bringt Chromium 115 von 2023 mit). Fällt
    automatisch auf Chromium zurück, wenn kein Chrome da ist, und protokolliert das.
  - `--disable-blink-features=AutomationControlled` + minimales Init-Script gegen
    `navigator.webdriver`. Bewusst nur dieser eine Patch — großflächiges Umschreiben der
    JS-Umgebung ist selbst wieder erkennbar.
  - `BROWSER_LOCALE`, `BROWSER_TIMEZONE`, `BROWSER_VIEWPORT`, `BROWSER_DEVICE_SCALE_FACTOR`
    konsistent gesetzt.
- **Persistentes Tool-Browserprofil** (`BROWSER_PERSISTENT`, `BROWSER_USER_DATA_DIR` →
  `data/browser_profile/`). localStorage, IndexedDB, Cache und Service Worker wachsen
  über Läufe hinweg, statt bei jedem Start ein fabrikneues Gerät zu simulieren. Das
  Verzeichnis gehört dem **Tool**, nicht dem Bediener — die Reproduzierbarkeit bleibt
  breit und standardisiert.
- **Neu `BROWSER_INJECT_COOKIES`.** Auf `False` setzen, wenn man sich im Tool-Profil
  einmal manuell angemeldet hat: die Session ist dann *nativ* in diesem Profil
  entstanden, und der Auslöser „fremdes Token in unbekanntem Browser" entfällt ganz.
  Menüpunkt 5 öffnet das Profil dafür.
- **Sitzung wird aufgewärmt** (`BROWSER_WARMUP`): erst den Feed laden und dort zufällig
  3–9 s verweilen, statt die Sitzung mit einer `/details/…`-Seite zu beginnen.
- **Eine Seite je Sitzung** statt eines neuen Tabs pro URL — entspricht eher einer
  echten Browsersitzung und reduziert die Zahl der Kaltstarts.
- **Menschenähnliches Scrollen.** Vorher exakt 10 Schritte à 2200 px alle 400 ms ohne
  jede Mausbewegung. Jetzt 6–12 Schritte mit gestreuten Distanzen (600–1400 px),
  gestreuten Pausen (250–1200 ms), echten `mouse.move`-Pfaden und 25 % Chance auf ein
  Stück Zurückscrollen.
- **Zwei Selbsttests ohne LinkedIn-Zugriff** (neue Menüpunkte 4 und 5):
  - `4` misst den Fingerprint auf einer neutralen HTTPS-Seite und bewertet ihn
    (webdriver, UA/Plattform-Kohärenz, „Google Chrome" in den Brands, echte GPU statt
    SwiftShader, Plugins). Damit lässt sich der Umbau prüfen, **ohne einen Account zu
    riskieren**. Gemessen wird bewusst auf `example.com`, weil `navigator.userAgentData`
    und `deviceMemory` nur im Secure Context existieren.
  - `5` öffnet das Tool-Profil sichtbar zur einmaligen manuellen Anmeldung.
- **`USE_BROWSER_FOR_LAZY` wieder auf `True`.** Der Sicherheitsdefault aus 0.3.2 ist
  hinfällig: die Ursachen sind adressiert, und der Testbetrieb läuft ohnehin auf einem
  Wegwerf-Account.
- **Korrektur zur Analyse:** Die in §9.2 als Maßnahme 6 gelistete Idee, Cookies mit
  Originalattributen (`secure`/`httpOnly`/`sameSite`) zu setzen, ist **wirkungslos** und
  wurde nicht umgesetzt. Diese Attribute sind rein client-seitig; der Server bekommt nur
  `name=value` zu sehen und kann sie gar nicht beobachten.

**Messergebnis nach dem Umbau** (Menüpunkt 4, echtes Chrome 134 auf Windows):
`webdriver: undefined` · UA und `navigator.platform` beide Windows · Brands enthalten
`Google Chrome` 134 · WebGL meldet echte Hardware (ANGLE/NVIDIA statt SwiftShader) ·
5 Plugins · `userAgentData.platform = "Windows"`. Alle fünf Prüfungen grün.

## 0.3.2
- **Headful-Test des Kontakt-Overlays: zwei Negativbefunde.**
  - *Inhaltlich:* Eine direkte Navigation auf `/overlay/contact-info/` **öffnet das
    Modal nicht.** Der Popover steht zwar im DOM, aber mit `inert=""`, `popover="manual"`
    und Opacity `0`; kein `mailto:`, keine Adresse, kein Geburtstag. LinkedIn lädt den
    Inhalt erst beim echten Klick auf „Kontaktinformationen".
  - *Betrieblich:* Der Lauf hat **erneut zum Logout geführt - diesmal headful.** Damit
    ist die Annahme widerlegt, der Headless-Modus sei die Ursache. Auslöser ist das
    Muster „separat gestartetes Chromium mit injizierten Cookies".
- **`USE_BROWSER_FOR_LAZY` als Sicherheitsdefault auf `False`.** Zweiter Account-Flag
  in zwei Tagen; ein dritter riskiert eine dauerhafte Einschränkung und damit den
  Testkorpus. Der Browser-Pfad bleibt im Code, ist aber bewusst abgeschaltet, bis der
  Extension-Weg steht. Kein Funktionsverlust gegenüber vorher: ohne Browser bleiben
  die sechs client-seitigen Felder wie bisher `N/A` (DQ4-konform).
- **Konsequenz für den Plan:** „Headful härten" ist zurückgestuft, der Extension-Weg
  (Seiten im echten Browser des Bedieners holen, Ergebnis über die bestehende
  Loopback-Bridge zurück) ist jetzt der Hauptweg.

## 0.3.1
- **Voyager-Weg verworfen (HTTP 410 Gone).** Der Live-Test gegen LinkedIn hat gezeigt,
  dass die klassischen REST-Endpunkte (`profileView`, `profileContactInfo`) abgeschaltet
  sind. Der verbleibende GraphQL-Weg braucht eine `queryId`, die mit jedem LinkedIn-
  Web-Release rotiert und aus einer individuellen Session mitgeschnitten werden müsste -
  das widerspricht der geforderten Reproduzierbarkeit (NFA5). `USE_VOYAGER_FOR_LAZY`
  steht jetzt auf `False`; `voyager_client.py` / `voyager_parser.py` bleiben als
  dokumentierter Negativbefund im Baum.
- **Zurück auf den Browser-Weg für alle client-seitig gerenderten Felder.**
  `USE_BROWSER_FOR_LAZY = True`, `BROWSER_HEADLESS = False`. Begründung: der
  `BrowserFetcher` hat nachweislich funktioniert (eigener `headless_true`-Dump →
  `parser_education` 4/4), er parst gegen strukturelle Marker statt gegen rotierende
  IDs, und er sieht nur, was ein einwilligender Mensch auch sieht.
- **Kontakt-Overlay läuft jetzt über den Browser** (neu `USE_BROWSER_FOR_CONTACT`).
  Über HTTP kam dort nur die Profil-Hülle; das Overlay wird client-seitig gerendert.
  Ohne Browser bleibt der HTTP-Weg als dokumentierter Fallback (liefert dann `N/A`).
  Profilkopf und Berufserfahrung bleiben bewusst beim schnelleren HTML-Weg (verifiziert)
  - so muss der Browser pro Profil fünf statt sieben Seiten laden.
- **`BrowserFetcher` ist jetzt seitentyp-bewusst.** Der Wartemarker wird aus der URL
  abgeleitet: `/overlay/contact-info/` → `a[href^="mailto:"], [role="dialog"]`,
  `/details/…` → `entity-collection-item-`, Hauptprofil → Topcard. Vorher lief jede
  Nicht-Listen-Seite unnötig in den vollen Timeout. Beim Kontakt-Overlay wird
  außerdem nicht gescrollt (es gibt dort keine LazyColumn).
- **Debug-Dumps tragen das Quellen-Kürzel im Dateinamen** (`…_browser.html` /
  `…_http.html`), damit ein Vergleichslauf den vorherigen Dump nicht überschreibt.

## 0.3.0
- **Voyager-API-Pfad für die sechs client-seitig nachgeladenen Felder** (E-Mail,
  Geburtstag, Ausbildung, Kenntnisse, Sprachen, Zertifikate). Läuft über dieselbe
  warme Session wie der HTML-Weg (curl_cffi), nur mit XHR-Headern.
  - `fetch/http_client.py`: `csrf-token` wird aus dem `JSESSIONID`-Cookie abgeleitet
    (Anführungszeichen entfernt). Neue Methode `get_api(url, *, referer, params)`
    setzt den vollständigen `/voyager/api`-Header-Satz (`csrf-token`,
    `x-restli-protocol-version: 2.0.0`, `x-li-lang`, `x-li-track`, `x-li-page-instance`,
    `accept: application/vnd.linkedin.normalized+json+2.1`, `Sec-Fetch-*` für einen
    same-origin-XHR).
  - `fetch/voyager_client.py` (neu): `VoyagerClient` mit Delay + Retry/Backoff,
    Methoden `profile_view(pid)` und `contact_info(pid)`. Bewusst die **klassischen
    REST-Endpunkte** `/identity/profiles/{pid}/profileView` bzw. `/profileContactInfo`
    statt GraphQL - kein rotierender `queryId`, dadurch reproduzierbar (NFA5).
  - `fetch/voyager_parser.py` (neu): mappt `educationView/skillView/languageView/
    certificationView.elements[]` bzw. `emailAddress`/`birthDateOn` defensiv auf die
    Datenmodelle. Proficiency-Enum → deutsches Label; `timePeriod` → „Apr. 2023–Okt. 2026".
  - `main.py`: Voyager füllt diese sechs Felder vorrangig; **Profilkopf und
    Berufserfahrung behalten ihren verifizierten HTML-Weg**. Fällt ein Voyager-Call
    aus, greift der bisherige HTML-/Browser-Fallback. Session-Menü baut den
    `VoyagerClient` bei `USE_VOYAGER_FOR_LAZY` (Default an); Debug-Menü hat einen
    neuen Punkt „9 = Voyager-JSON" (speichert `profileView` + `profileContactInfo`
    roh als `.json` zum Abgleich der Feldzuordnung).
  - `config.py`: `USE_VOYAGER_FOR_LAZY`, `VOYAGER_*`-URLs, `LI_CLIENT_VERSION`,
    `LI_LANG`, `LI_TIMEZONE`.
- **Noch offen:** Live-Test gegen echtes LinkedIn (nur der Autor kann das). Wenn die
  REST-Endpunkte 2026 abgeschaltet sind, meldet der Client das als `VoyagerError` und
  der Browser-Fetcher bleibt als Weg.

## 0.2.4
- **Input-CSV: feste Kopfzeile.** `read_profile_urls` behandelt Zeile 1 immer als
  Kopfzeile (`URL`) und überspringt sie; Daten ab Zeile 2. Warnt, wenn die Kopfzeile
  nicht `URL` heißt, und protokolliert (statt still zu ignorieren) jede Datenzeile,
  die keine LinkedIn-Profil-URL ist. `input_profiles.example.csv` + README angepasst.
- **Kontakt-Overlay abschließend geklärt.** Gegentest 13:37 mit `FORCE_HTTP_ENGINE = None`
  (curl_cffi), **öffentlicher** E-Mail am Zielprofil, Zugriff aus einem **anderen** Account,
  lesbarer 1-MB-Dump: `/overlay/contact-info/` liefert nur den *Link* + die SSR-Topcard,
  **null Overlay-Inhalt** (kein `emailAddress`/`websites`/`phoneNumbers`/`birthDateOn`/
  `mailto:`, weder im HTML noch im Flight-Payload). Der Overlay ist **rein client-seitig**
  gerendert → E-Mail + Geburtstag sind über requests/curl_cffi nicht erreichbar und
  gehören in denselben Fetch-Topf wie die 4 Lazy-Sektionen (Browser/Voyager).
  `parser_contact` unverändert (liefert korrekt `N/A`).

## 0.2.3
- **Kontakt-E-Mail war nie eine Regression.** Das Testprofil `martin-reimann` hat die
  E-Mail-Sichtbarkeit auf privat gestellt → LinkedIn liefert dann korrekterweise keine
  Adresse im Kontakt-Overlay aus, egal über welche Engine. Mit einem zweiten Testaccount
  und Sichtbarkeit „alle" ist die E-Mail wieder da. Nicht scrapebare Felder bleiben
  vereinbarungsgemäß `N/A` (DQ4) - `parser_contact` macht das bereits sauber (nur eine
  `WARNING`, kein Fehler). curl_cffi mit `FORCE_HTTP_ENGINE = None` hatte die ganze Zeit
  korrekt funktioniert.
- **Fix `requests`-Fallback: `Accept-Encoding` dynamisch.** Der erzwungene `requests`-Pfad
  hat `br` (Brotli) angekündigt, obwohl weder `brotli` noch `brotlicffi` installiert ist →
  urllib3 packt den Body nicht aus, `.text` ist komprimierter Datenmüll (genau das Symptom
  der „leeren"/unlesbaren erzwungenen requests-Dumps, auch schon beim `_requests`-Ausbildungs-
  Dump). `http_client._fallback_accept_encoding()` kündigt jetzt nur `gzip, deflate` an und
  ergänzt `br`/`zstd` nur, wenn ein Decoder importierbar ist. curl_cffi ist nicht betroffen
  (bringt Brotli/zstd selbst mit).

## 0.2.2
- **Erfahrung läuft über den requests-Weg (curl_cffi).** Der kalte Dump (`SEND_REFERER_CHAIN
  = False`) enthält alle 5 Positionen mit sauberer `<p>`-Struktur - nur der `/edit/forms/`-
  Link fehlt in dieser Variante (wie schon bei Kenntnissen). `parser_experience._parse_single_position`
  nimmt jetzt die `<p>` direkt aus dem Eintrag, wenn kein Edit-Link da ist → **5/5 verifiziert**
  gegen den curl_cffi-Dump. Der Referer war NICHT die Ursache (Dump mit/ohne Referer
  strukturgleich) - der alte Parser war nur zu streng.
- **Kontakt-E-Mail kommt über requests NICHT mehr.** Der `overlay/contact-info/`-Abruf
  liefert nur noch die Profil-Hülle, kein `mailto:` / keine E-Mail im Payload (am 30.08.
  über Plain-`requests` war sie noch da). Offen, ob LinkedIn das umgestellt hat oder
  curl_cffi eine andere Variante bekommt.
- **Neu `config.FORCE_HTTP_ENGINE`** (`None` / `"requests"` / `"curl_cffi"`) - erzwingt die
  Engine, um Plain-`requests` vs. curl_cffi zu isolieren (Kontakt-Regression eingrenzen).

## 0.2.1
- **Befund Live-Test v0.2.0:** Der Profil-Dump (kalt geholt, ohne Referer) enthält die
  Topcard vollständig → `parser_profile` liefert Name/Titel/Ort/Bundesland/Land korrekt.
  Der Erfahrungs- und der Kontakt-Dump wurden dagegen **mit** Referer/`Sec-Fetch-Site:
  same-origin` geholt und kamen als schlanke SPA-Hydrations-Variante: Erfahrung hat den
  Inhalt nur noch teilweise als parsebare Struktur (kein `profile_ExperienceDetailsSection`
  -testid mehr, Einzelpositionen ohne `/edit/forms/`-Link → nur 2 von 5), Kontakt-Overlay
  nur noch die Profil-Hülle ohne die E-Mail im Payload. Der Aug.-30-Plain-`requests`-Weg
  (ganz ohne `Sec-Fetch`/`Referer`) hatte jeweils das volle SSR geliefert.
- **Fix (Hypothese, Live-Test offen):** `config.SEND_REFERER_CHAIN = False` (Default) -
  jede Detailseite wird jetzt **kalt** geholt (kein Referer, `Sec-Fetch-Site: none`),
  wie ein in die Adressleiste getippter Aufruf. `main.py` und der Debug-Dump ziehen den
  Referer nur noch, wenn das Flag an ist.
- `parser_experience.py`: fällt auf die ganze Seite zurück, wenn der
  `profile_ExperienceDetailsSection`-testid fehlt (schlanke Varianten). Hilft, löst das
  Grundproblem aber nicht, solange die Seite nur die Teil-Struktur liefert.
- TLS-Fingerprint, Header, Delays, Cookie-Vollsatz bleiben - nur die Referer-Kette ist raus.

## 0.2.0
**requests-Pfad „menschlicher" gemacht (Bot-Erkennung).** Der reine `requests`-Abruf
wird an drei Stellen erkannt: TLS-Fingerprint, Header-Satz, Sec-Fetch-/Referer-Kette.

- **Neu `fetch/http_client.py` (`HttpClient`)** — nutzt `curl_cffi` mit
  `impersonate="chrome131"` (echter Chrome-TLS-/HTTP-2-Fingerprint, real existierende
  Version, in sich konsistent „Chrome auf macOS"). Fällt ohne `curl_cffi` auf `requests`
  zurück und protokolliert das. Vollständiger Chrome-Navigations-Header-Satz
  (`Accept`, `Accept-Language`, `Sec-Fetch-*`, `Upgrade-Insecure-Requests`, `Priority`).
  `get(url, referer=...)` setzt `Referer` + `Sec-Fetch-Site` (`none` beim Einstieg,
  `same-origin` beim Klick von der Profilseite). requests.Session-kompatible Fläche.
- `session_manager.py` baut jetzt einen `HttpClient` statt einer nackten
  `requests.Session`; der globale `csrf-token`-Header ist raus (Chrome sendet den nicht
  bei Navigationen). `validator.py` entkoppelt vom `requests`-Typ.
- **`rate_limiter.py` dreistufig:** pro Request 6–14 s (mit ~18 % Chance auf 4–20 s
  Aufschlag „kurz abgelenkt"), zwischen Profilen 25–75 s, alle 6 Profile 3–7 min.
  Harte Obergrenze `MAX_PROFILES_PER_RUN = 25` pro Lauf.
- `main.py`: menschliche Navigationsreihenfolge — erst die Profilseite, dann die
  Unterseiten *mit der Profil-URL als Referer*; Reihenfolge der vier Lazy-Sektionen je
  Profil zufällig; Aufwärm-Request auf den Feed vor dem ersten Profil.
- `fetch/fetcher.py`: `get_html(url, referer=...)`, erkennt Umleitung auf
  Login/Checkpoint (finale URL) und meldet „Session ungültig / Bot-Check".
- `fetch/browser_fetcher.py`: `get_html` nimmt `referer` entgegen (ignoriert, gemeinsame
  Schnittstelle).
- `config.py`: `HTTP_IMPERSONATE`, `ACCEPT_LANGUAGE`, `SEC_CH_UA*`, alle neuen Delay-/
  Pausen-Parameter, `MAX_PROFILES_PER_RUN`. Grunddelay von 4–9 s auf 6–14 s angehoben.
- `requirements.txt`: `curl_cffi>=0.7`.
- Extension 0.1.2: `popup.js` überträgt **alle** LinkedIn-Cookies statt nur vier.
- **Noch offen:** Die vier Lazy-Sektionen liefert `requests` weiterhin leer (Inhalt ist
  nicht im HTML). Dafür bleibt der Browser-Fetcher zuständig bzw. später der
  Voyager-GraphQL-Aufruf. Live-Test des neuen Fingerprints gegen LinkedIn steht aus.

## 0.1.9
- `browser_fetcher.py`: erkennt jetzt eine Umleitung auf Login/Checkpoint/Authwall und
  wirft dann eine klare `FetchError` (statt die Login-Seite als Dump zu speichern);
  `ERR_TOO_MANY_REDIRECTS`/`ERR_ABORTED` bei `page.goto` werden als „Session vermutlich
  ungültig / Bot-Check" gemeldet.
- Hintergrund (Live-Test 2026-09-07): Der headless-Lauf gegen `/details/education/` hat
  zwar die Daten geliefert (`parser_education` → 4 Einträge korrekt), aber LinkedIns
  Bot-Erkennung ausgelöst → Session serverseitig invalidiert, Nutzer ausgeloggt,
  E-Mail-2FA zur Neuanmeldung nötig. Der anschließende Lauf lief dadurch in
  `ERR_TOO_MANY_REDIRECTS` (tote Session). Ein separat gestartetes Chromium mit
  injizierten Cookies ist für LinkedIn als Automat erkennbar; der manuelle
  „Seite speichern"-Weg aus dem echten Browser war es nie. Nächster Schritt =
  Grundsatzentscheidung.

## 0.1.8
- **Neuer `fetch/browser_fetcher.py` (`BrowserFetcher`)** - JS-fähiger Abruf über
  Playwright/Chromium für die client-seitig nachgeladenen Sektionen. Gleiche
  `get_html(url) -> str`-Schnittstelle wie `Fetcher`, Chromium wird lazy beim ersten
  Abruf gestartet. Übernimmt die Session-Cookies, scrollt die Seite in Schritten
  (löst die `LazyColumn`s aus) und wartet auf `div[componentkey^="entity-collection-item-"]`
  (Timeout = leere Sektion, kein Fehler).
- `main.py`: Hybrider Ablauf. Profil/Kontakt/Erfahrung weiter über `requests`
  (`Fetcher`), Ausbildung/Kenntnisse/Sprachen/Zertifikate über den `BrowserFetcher`
  (wenn `config.USE_BROWSER_FOR_LAZY`). Einzelne fehlgeschlagene Lazy-Sektionen brechen
  das Profil nicht mehr ab. Debug-Dump-Menü fragt jetzt nach der Quelle (requests/Browser).
  „Beenden" schließt den Browser sauber (`try/finally`).
- `config.py`: `USE_BROWSER_FOR_LAZY`, `BROWSER_HEADLESS`, Timeouts/Scroll-Parameter.
- `requirements.txt`: `playwright>=1.40` (danach einmalig `playwright install chromium`).
- Smoke-Test gegen example.com OK (Start/Navigation/Scroll/Content/Close). Der Lauf
  gegen echte LinkedIn-Lazy-Sektionen mit gültiger Session steht noch aus.

## 0.1.7
- `parser_profile.py` neu auf die **Topcard-Sektion** (`section[componentkey$="Topcard"]`)
  gestützt statt auf den alten `<p>Name</p> … <span>` -Heuristik-Pfad:
  - Headline = erste `<p>`-Zeile der Topcard, die nicht in einem Link/Button steckt
    (filtert die „In 2 Minuten verifzieren"-CTA und den Kontaktezähler weg).
  - Standort = `<p>` direkt vor dem „Kontaktinformationen"-Label; wird an „, " in
    Ort / Bundesland / Land zerlegt (3 Teile → alle drei, 2 Teile → Ort + Land).
  - Fallback auf die alte Heuristik bleibt für ohne-JS-Dumps erhalten.
  - Gegen Browser-Dump (`mainpage`) und den alten Tool-Dump (`profil`) verifiziert:
    beide liefern Titel „In Ausbildung/Studium: …" und Chemnitz / Sachsen / Deutschland.
    Die Topcard ist also auch im reinen `requests`-HTML vorhanden - nur die
    Detail-Listen (education/skills/…) sind die Lazy-Teile.
- `parser_languages.py` gegen einen neuen, hydratisierten Sprachen-Dump verifiziert:
  3 Einträge (Deutsch / Muttersprache oder zweisprachig, Englisch / Verhandlungssicher,
  Französisch / Grundkenntnisse); Feldzuordnung [0] Sprache, [1] Niveau bestätigt.
- Offen bleibt nur noch `parser_certifications` (Testprofil hat keine Zertifikate).

## 0.1.6
- `dom_utils.iter_detail_entries`: Fallback ergänzt. Bisher wurden nur die `<p>` im
  „Bearbeiten"-Link (`/edit/forms/`) gelesen; bei den Kenntnissen ist dieser Link aber
  nur ein Icon ohne `<p>`, sodass die Sektion trotz vorhandener Daten leer zurückkam.
  Jetzt: `<p>` aus dem Edit-Link, und falls dort keine → alle `<p>` des Eintrags.
- Gegen hand-gespeicherte Browser-Dumps des Testprofils (2026-09-06) verifiziert:
  - `parser_education` → 4 Einträge (Schule / Fachrichtung / Zeitraum), korrekt.
  - `parser_skills` → 10 Kenntnisse (`data-testid="profile_SkillDetails_<slug>"`; erste
    `<p>`-Zeile = Name, zweite = Kontext und wird verworfen).
  - `parser_languages` / `parser_certifications` → `[]`; das Testprofil hat laut Autor
    keine Sprachen/Zertifikate, die Feldzuordnung dieser beiden bleibt daher unverifiziert.
- Docstrings der vier Parser an den verifizierten Stand angepasst (kein „UNVERIFIZIERT"
  mehr für education/skills).
- Hinweis: `parser_experience` nutzt `iter_detail_entries` nicht und ist unberührt.

## 0.1.5
- Aufräumen: `fetch/json_extractor.py` (suchte `<code id="bpr-guid-…">`-Voyager-JSON,
  das LinkedIn seit der SDUI-Umstellung nicht mehr ausliefert) und `fetch/format_utils.py`
  (`format_zeitraum()` für die alten dateRange-Objekte) entfernt — beide waren nach dem
  Umstieg auf DOM-Parsing von keinem Modul mehr importiert.
- Doku in den Modulen aktualisiert: Warntexte der
  vier blockierten Parser sagen jetzt „kommt als leere LazyColumn" statt „vermutlich
  client-seitig nachgeladen" (per Dump-Analyse bestätigt: Sektions-Hülle mit
  `data-component-type="LazyColumn"` + `data-lazy-mount-id`, aber 0 Einträge im HTML).
- `README.md` §"Wichtiger Hinweis zu den Parsern" und Architektur-Baum an die SDUI-
  Realität angepasst.
- Kein Verhaltensänderung an den Parsern selbst.

## 0.1.4
- Fix: `parser_experience.py` erfasste nur die Hälfte der Positionen - der Selektor
  suchte `componentkey^="entity-collection-item--"` (zwei Bindestriche), LinkedIn nutzt
  aber teils nur einen. Jetzt `entity-collection-item-`; gegen den Testprofil-Dump
  verifiziert (alle 5 Positionen inkl. Einzel- und Mehrfach-Firmen-Gruppe, Firma/Standort
  je Zeile korrekt).
- Fix: `parser_contact.py` und `parser_profile.py` vom toten Voyager-JSON-Weg auf
  DOM/Flight-Payload umgestellt. Kontakt: E-Mail per `mailto:`-Regex (verifiziert),
  Geburtstag bleibt N/A (nicht im Payload). Profil: Name aus `<title>`, Headline aus
  dem SSR-Karten-Header; Ort/Bundesland/Land sind über den reinen GET nicht verfügbar
  und stehen jetzt explizit auf N/A.
- `parser_education/skills/languages/certifications.py` auf DOM-Skeletons (neuer Helper
  `dom_utils.iter_detail_entries`) umgestellt und als BLOCKIERT markiert: diese Sektionen
  werden von LinkedIn client-seitig nachgeladen und sind in einem `requests.get()` nicht
  enthalten. Sie liefern jetzt `[]` mit klarer Log-Warnung statt stiller Fehlannahmen.
  Der Fetch-Layer muss dafür auf Browser oder Voyager-API umziehen.
- `json_extractor.py` wird nur noch von den blockierten Skeletons nicht mehr benutzt;
  Entfernung offen, sobald der Fetch-Weg für die Listen-Sektionen steht.

## 0.1.3
- Feature: Debug-Dump (`main.py:run_debug_dump`) umgebaut - jede Detailseite wird jetzt als
  eigene Datei `debug_dump_<seite>_<profil-slug>.html` im neuen Ordner `data/debug_dumps/`
  gespeichert (statt einer einzigen fest benannten `debug_dump.html`, die bei jedem Dump
  überschrieben wurde). Neue Option "Alle Seiten" holt alle 7 Detailseiten eines Profils
  nacheinander, ein Fehler bei einer Seite bricht die übrigen nicht ab. `config.py`:
  `DEBUG_DUMP_PATH` durch `DEBUG_DUMP_DIR` ersetzt.

## 0.1.2
- Fix: LinkedIn liefert kein eingebettetes Voyager-JSON (`bpr-guid`) mehr - `parser_experience.py`
  komplett auf DOM-basiertes Parsing umgestellt (neues `fetch/dom_utils.py`), gegen echten
  Debug-Dump verifiziert. Die übrigen Detail-Parser (Kontakt, Ausbildung, Kenntnisse,
  Zertifikate, Sprachen) sind vom selben Problem betroffen und noch offen.
- Fix: `fetcher.py` erzwingt jetzt UTF-8-Dekodierung (`requests` erriet zuvor teils Latin-1
  und verstümmelte Sonderzeichen wie Gedankenstriche in Zeiträumen).

## 0.1.1
- Fix: `native_host_runner.py` stürzte bei unvollständigen/kaputten Nachrichten mit
  Traceback ab, statt sauber abzubrechen (fehlende Längen-/JSON-Validierung ergänzt).
- Fix: `install_native_host.py` erzeugt den Wrapper jetzt mit `py -3` statt `python`,
  da `python` im PATH auf einen defekten Microsoft-Store-Alias zeigen kann.

## 0.1.0
- Erste Version: Session-Bridge (Native Messaging), Fetcher mit Retry/Backoff,
  JSON-Extraktor, Parser für Profil/Kontakt/Erfahrung/Ausbildung/Kenntnisse/
  Zertifikate/Sprachen, CSV-Writer nach ExportVorlage-Format, CLI-Menü.
