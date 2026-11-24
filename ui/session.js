// Session page: join, wait for the host to start, then go to the recording page (record.html).
// When the host presses Start, the song's lines are dealt to the singers in rotation
// (one line each, then the next person), so each turn is short.

const sessionId = new URLSearchParams(window.location.search).get("id");
let refreshTimer = null; // while waiting for the host, reload every few seconds to see who joined

async function load() {
  const session = await api(`/api/sessions/${encodeURIComponent(sessionId)}`);
  showError(null); // clear any old error once the latest data has loaded
  const me = myParticipantId(sessionId);
  const names = Object.fromEntries(session.participants.map((p) => [p.id, p.display_name]));
  const started = session.turns.length > 0;
  const hostId = session.participants[0].id;

  document.getElementById("song-title").textContent = session.song.title;
  document.getElementById("finale-link").href = `/finale.html?id=${encodeURIComponent(sessionId)}`;
  document.getElementById("status").textContent =
    session.status === "complete" ? "Everyone has sung!" : `Hosted by ${session.host_name}`;
  const link = document.getElementById("share-link");
  link.href = link.textContent = window.location.href;
  document.getElementById("participants").textContent =
    session.participants.map((p) => p.display_name).join(", ");

  // Before the start: people join, and only the host sees the Start button.
  document.getElementById("join-card").hidden = me !== null || started;
  document.getElementById("lobby-card").hidden = started;
  document.getElementById("lines-card").hidden = !started;
  if (!started) {
    const count = session.participants.length;
    document.getElementById("lobby-text").textContent = me === hostId
      ? `${count} singer${count === 1 ? "" : "s"} so far. Press Start when everyone has joined: ` +
        "the lines are dealt one each, in the order people joined, and nobody can join after that."
      : "Waiting for the host to start. Share the link above with anyone else who wants to sing.";
    document.getElementById("start-button").hidden = me !== hostId;
    if (!refreshTimer) refreshTimer = setInterval(() => load().catch(showError), 5000);
    return;
  }
  clearInterval(refreshTimer);
  refreshTimer = null;

  const mine = session.turns.filter((t) => t.participant_id === me && t.status === "assigned");
  const recordAll = document.getElementById("record-all");
  recordAll.hidden = mine.length === 0;
  recordAll.textContent = `Record all my lines (${mine.length})`;
  recordAll.onclick = () => (window.location.href = `/record.html?id=${encodeURIComponent(sessionId)}`);

  const list = document.getElementById("turns");
  list.replaceChildren();
  for (const turn of session.turns) {
    const row = el("div", "", "turn");
    row.id = `turn-${turn.id}`;
    const text = el("div");
    text.append(el("div", `${turn.position}. ${turn.lyrics}`, "lyrics"));
    text.append(el("div", `${names[turn.participant_id] ?? "nobody"} · ${turn.status}`, "muted"));
    row.append(text);
    list.append(row);
  }
}

async function startSession() {
  try {
    await api(`/api/sessions/${encodeURIComponent(sessionId)}/start`, {
      method: "POST",
      body: JSON.stringify({ participant_id: myParticipantId(sessionId) }),
    });
    await load();
  } catch (error) {
    showError(error);
  }
}

document.getElementById("start-button").addEventListener("click", startSession);

document.getElementById("join-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const participant = await api(`/api/sessions/${encodeURIComponent(sessionId)}/participants`, {
      method: "POST",
      body: JSON.stringify({ display_name: document.getElementById("display-name").value }),
    });
    rememberParticipant(sessionId, participant.id);
    await load();
  } catch (error) {
    showError(error);
  }
});

load().catch(showError);
