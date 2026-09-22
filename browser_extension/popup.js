// Liest ALLE LinkedIn-Cookies und sendet sie per Native Messaging an den lokal
// registrierten Host (siehe linkedin_scraper/session/install_native_host.py).
// Vollständiger Cookie-Satz, damit die Session im Python-Tool für LinkedIn wie ein
// normaler Browser aussieht (li_at allein reicht technisch, wirkt aber "dünn").
const NATIVE_HOST_NAME = "com.reimann.linkedin_research_scraper";

const statusEl = document.getElementById("status");

document.getElementById("sendBtn").addEventListener("click", async () => {
  statusEl.textContent = "Lese Cookies...";

  // Beide Schreibweisen abdecken (.linkedin.com und host-only www.linkedin.com).
  const all = [
    ...(await chrome.cookies.getAll({ domain: "linkedin.com" })),
    ...(await chrome.cookies.getAll({ domain: "www.linkedin.com" })),
  ];
  const relevant = {};
  for (const c of all) {
    // Letzter Treffer gewinnt; unkritisch, Werte sind für denselben Namen identisch.
    relevant[c.name] = c.value;
  }

  if (!relevant["li_at"]) {
    statusEl.textContent = "Kein li_at-Cookie gefunden - bist du bei LinkedIn eingeloggt?";
    return;
  }

  statusEl.textContent = `Lese Cookies... (${Object.keys(relevant).length} gefunden)`;

  statusEl.textContent = "Sende an lokales Python-Tool...";
  const port = chrome.runtime.connectNative(NATIVE_HOST_NAME);

  // Der Host-Prozess verarbeitet genau eine Nachricht und beendet sich danach bewusst
  // (siehe native_host_runner.py) - onDisconnect feuert also auch im Erfolgsfall.
  // Dieses Flag verhindert, dass der erwartete "Native host has exited"-Disconnect
  // eine bereits erhaltene Erfolgsmeldung ueberschreibt.
  let responseReceived = false;

  port.onMessage.addListener((msg) => {
    responseReceived = true;
    statusEl.textContent = msg.ok ? "Session erfolgreich uebertragen." : `Fehler: ${msg.error}`;
  });
  port.onDisconnect.addListener(() => {
    if (!responseReceived && chrome.runtime.lastError) {
      statusEl.textContent = `Verbindung fehlgeschlagen: ${chrome.runtime.lastError.message}`;
    }
  });

  port.postMessage({ type: "session_cookies", cookies: relevant, timestamp: Date.now() });
});
