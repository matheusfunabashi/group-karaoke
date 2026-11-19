// Session page: join, see every part of the song, and claim one.

const sessionId = new URLSearchParams(window.location.search).get("id");
let backingTrackUrl = null;

async function load() {
  const session = await api(`/api/sessions/${encodeURIComponent(sessionId)}`);
  showError(null); // clear any old error once the latest data has loaded
  const me = myParticipantId(sessionId);
  const names = Object.fromEntries(session.participants.map((p) => [p.id, p.display_name]));

  backingTrackUrl = "/" + session.song.audio_file;
  document.getElementById("song-title").textContent = session.song.title;
  document.getElementById("finale-link").href = `/finale.html?id=${encodeURIComponent(sessionId)}`;
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
    if (turn.status === "assigned" && turn.participant_id === me) {
      const record = el("button", "Record");
      record.addEventListener("click", () => recordTurn(turn, record));
      row.append(record);
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

// Record this browser's microphone for exactly one part, while the backing track
// plays that part of the song, then upload the clip.
async function recordTurn(turn, button) {
  showError(null);
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch {
    showError(new Error("Microphone access is needed to record your part"));
    return;
  }

  const recorder = new MediaRecorder(stream);
  const chunks = [];
  recorder.addEventListener("dataavailable", (event) => chunks.push(event.data));

  const backing = new Audio(backingTrackUrl);
  backing.currentTime = turn.start_ms / 1000;
  const lengthMs = turn.end_ms - turn.start_ms;

  button.disabled = true;
  button.textContent = "Recording…";
  recorder.start();
  await backing.play();

  setTimeout(() => {
    backing.pause();
    recorder.stop();
  }, lengthMs);

  recorder.addEventListener("stop", async () => {
    stream.getTracks().forEach((track) => track.stop()); // turn the microphone off
    // recorder.mimeType is e.g. "audio/webm;codecs=opus" (Chrome) or "audio/mp4" (Safari).
    const clip = new Blob(chunks, { type: recorder.mimeType });
    await uploadClip(turn.id, clip);
  });
}

async function uploadClip(turnId, clip) {
  const form = new FormData();
  form.append("turn_id", turnId);
  form.append("clip", clip, `turn-${turnId}`);
  try {
    await api("/api/recordings", { method: "POST", body: form });
  } catch (error) {
    showError(error);
  }
  await load();
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
