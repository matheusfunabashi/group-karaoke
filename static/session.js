// Session page: join, see every part of the song, and claim one.

const sessionId = new URLSearchParams(window.location.search).get("id");

async function load() {
  const session = await api(`/api/sessions/${encodeURIComponent(sessionId)}`);
  showError(null); // clear any old error once the latest data has loaded
  const me = myParticipantId(sessionId);
  const names = Object.fromEntries(session.participants.map((p) => [p.id, p.display_name]));

  document.getElementById("song-title").textContent = session.song.title;
  document.getElementById("status").textContent =
    session.status === "complete" ? "Everyone has sung!" : `Hosted by ${session.host_name}`;
  const link = document.getElementById("share-link");
  link.href = link.textContent = window.location.href;

  document.getElementById("join-card").hidden = me !== null;
  document.getElementById("participants").textContent =
    session.participants.map((p) => p.display_name).join(", ");

  const list = document.getElementById("turns");
  list.replaceChildren();
  for (const turn of session.turns) {
    const row = el("div", "", "turn");
    const text = el("div");
    text.append(el("div", `${turn.position}. ${turn.lyrics}`, "lyrics"));
    const who = turn.participant_id ? names[turn.participant_id] : "nobody yet";
    text.append(el("div", `${who} · ${turn.status}`, "muted"));
    row.append(text);

    if (turn.status === "pending" && me !== null) {
      const claim = el("button", "Sing this");
      claim.addEventListener("click", () => claimTurn(turn.id, me));
      row.append(claim);
    }
    list.append(row);
  }
}

async function claimTurn(turnId, participantId) {
  try {
    await api(`/api/sessions/${encodeURIComponent(sessionId)}/turns/${turnId}/claim`, {
      method: "POST",
      body: JSON.stringify({ participant_id: participantId }),
    });
    await load();
  } catch (error) {
    showError(error);
  }
}

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
