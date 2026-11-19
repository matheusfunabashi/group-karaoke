// Small helpers shared by every page.

// Call the JSON API; throws an Error with the server's "detail" message on failure.
async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: options.body && !(options.body instanceof FormData)
      ? { "Content-Type": "application/json" }
      : {},
  });
  const body = await response.json();
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
  box.textContent = error ? error.message : "";
}
