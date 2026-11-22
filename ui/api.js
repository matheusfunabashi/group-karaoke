// Small helpers shared by every page.

// Full address of an API path: /api/sessions/... goes to the sessions service and
// /api/recordings/... (and the /media clips it serves) to the recordings service (config.js).
function serviceUrl(path) {
  const config = window.KARAOKE_CONFIG;
  const base = path.startsWith("/api/sessions") ? config.sessionsUrl : config.recordingsUrl;
  return base + path;
}

const RETRY_WAITS_MS = [3000, 6000, 10000, 15000, 20000];

// On Azure a service sleeps when nobody uses it. The first request then gets 502/503/504
// (or no answer at all) for up to a minute while it starts and its database resumes.
function isStartingUp(response) {
  return response === null || [502, 503, 504].includes(response.status);
}

// Call the JSON API; throws an Error with the server's "detail" message on failure.
// Retries while the service is starting up, telling the user what is happening.
async function api(path, options = {}) {
  const request = {
    ...options,
    headers: options.body && !(options.body instanceof FormData)
      ? { "Content-Type": "application/json" }
      : {},
  };
  let response = null;
  for (let attempt = 0; ; attempt++) {
    try {
      response = await fetch(serviceUrl(path), request);
    } catch {
      response = null; // network error: the service isn't answering yet
    }
    if (!isStartingUp(response) || attempt === RETRY_WAITS_MS.length) break;
    showError(new Error("The service is starting up after being idle, please wait..."));
    await new Promise((resolve) => setTimeout(resolve, RETRY_WAITS_MS[attempt]));
  }
  showError(null);
  if (isStartingUp(response)) {
    throw new Error("The service is still starting up. Please try again in a minute.");
  }
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(typeof body.detail === "string" ? body.detail : "Something went wrong");
  }
  return body;
}

// Create an element with text. textContent (not innerHTML) so names typed by users
// are shown as text and can never inject HTML or scripts.
function el(tag, text = "", className = "") {
  const node = document.createElement(tag);
  node.textContent = text;
  if (className) node.className = className;
  return node;
}

// Which participant this browser is in a given session (there are no accounts).
function myParticipantId(sessionId) {
  const value = localStorage.getItem(`karaoke:${sessionId}`);
  return value ? Number(value) : null;
}

function rememberParticipant(sessionId, participantId) {
  localStorage.setItem(`karaoke:${sessionId}`, String(participantId));
}

function showError(error) {
  const box = document.getElementById("error");
  if (box) box.textContent = error ? error.message : "";
}
