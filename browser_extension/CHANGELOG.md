# Changelog - LinkedIn Research Scraper Extension

Nur inhaltliche Änderungen an der Extension selbst (nicht am Python-Tool oder an
Setup-/Umgebungsschritten wie Registry-Registrierung oder Python-Interpreter-Fixes).

> **Hinweis (Stand Python-Tool v0.7.0):** Die Extension ist **nicht mehr Teil des
> Ablaufs.** Der Login läuft jetzt über eine einmalige manuelle Anmeldung in einem
> tool-eigenen Browserprofil; die Cookie-Übergabe per Native Messaging hat in der Praxis
> Logouts ausgelöst. Extension + `session/` bleiben nur als
> dokumentierter, verworfener Weg erhalten und werden nicht mehr weiterentwickelt.

## 0.1.2
- `popup.js` überträgt jetzt **alle** LinkedIn-Cookies (`linkedin.com` + `www.linkedin.com`),
  nicht nur `li_at`/`JSESSIONID`/`bcookie`/`bscookie`. Damit hat der HTTP-Client im
  Python-Tool denselben Cookie-Satz wie der echte Browser (u. a. `lidc`, `li_rm`,
  `li_gc`, `liap`, `lang`, `UserMatchHistory`), was die Session für LinkedIns
  Bot-Erkennung weniger auffällig macht. `li_at` bleibt Pflicht.

## 0.1.1
- Fix: Erfolgsmeldung ("Session erfolgreich uebertragen.") wurde direkt danach vom
  erwarteten `onDisconnect`-Event überschrieben, weil der Native Host sich nach der
  Antwort bewusst beendet. `popup.js` ignoriert den Disconnect jetzt, wenn zuvor
  bereits eine Antwort empfangen wurde.

## 0.1.0
- Erste Version: liest `li_at`/`JSESSIONID`/`bcookie`/`bscookie` und überträgt sie
  per Native Messaging an den lokalen Python-Host.
