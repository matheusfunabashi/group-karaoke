// Session page: join, wait for the host to start, then record your lines.
// When the host presses Start, the song's lines are dealt to the singers in rotation
// (one line each, then the next person), so each turn is short.

const sessionId = new URLSearchParams(window.location.search).get("id");
let backingTrackUrl = null;
let refreshTimer = null; // while waiting for the host, reload every few seconds to see who joined

async function load() {
  const session = await api(`/api/sessions/${encodeURIComponent(sessionId)}`);
  showError(null); // clear any old error once the latest data has loaded
  const me = myParticipantId(sessionId);
  const names = Object.fromEntries(session.participants.map((p) => [p.id, p.display_name]));
  const started = session.turns.length > 0;
  const hostId = session.participants[0].id;

  backingTrackUrl = "/" + session.song.audio_file;
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
  recordAll.onclick = () => recordLines(mine, recordAll);

  const list = document.getElementById("turns");
  list.replaceChildren();
  for (const turn of session.turns) {
    const row = el("div", "", "turn");
    row.id = `turn-${turn.id}`;
    const text = el("div");
    text.append(el("div", `${turn.position}. ${turn.lyrics}`, "lyrics"));
    text.append(el("div", `${names[turn.participant_id] ?? "nobody"} · ${turn.status}`, "muted"));
    row.append(text);
    // One Record button per line too, to redo a single line that went wrong
    if (turn.status === "assigned" && turn.participant_id === me) {
      const record = el("button", "Record");
      record.addEventListener("click", () => recordLines([turn], record));
      row.append(record);
    }
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

// Wait until the backing track reaches `ms` milliseconds into the song.
function untilTrackReaches(backing, ms) {
  return new Promise((resolve) => {
    const check = () => (backing.currentTime * 1000 >= ms || backing.ended ? resolve() : setTimeout(check, 20));
    check();
  });
}

// Record one clip per line in a single pass: the backing track plays from the first of these
// lines, and the microphone is recorded only during each line (other people's lines play in
// between). Each clip is uploaded as soon as its line ends.
async function recordLines(turns, button) {
  showError(null);
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch {
    showError(new Error("Microphone access is needed to record your lines"));
    return;
  }

  const nowSinging = document.getElementById("now-singing");
  const backing = new Audio(backingTrackUrl);
  backing.currentTime = turns[0].start_ms / 1000;
  button.disabled = true;
  button.textContent = "Recording…";
  await backing.play();

  // Clips are uploaded one after another (never two at once), in the background while the next
  // line is sung: parallel uploads would make the sessions database update turns at the same time.
  let uploads = Promise.resolve();
  for (const turn of turns) {
    nowSinging.textContent = `Get ready: ${turn.lyrics}`;
    await untilTrackReaches(backing, turn.start_ms);
    nowSinging.textContent = `🎤 Sing now: ${turn.lyrics}`;
    document.getElementById(`turn-${turn.id}`)?.classList.add("singing");

    const recorder = new MediaRecorder(stream);
    const chunks = [];
    recorder.addEventListener("dataavailable", (event) => chunks.push(event.data));
    const stopped = new Promise((resolve) => recorder.addEventListener("stop", resolve));
    recorder.start();
    await untilTrackReaches(backing, turn.end_ms);
    recorder.stop();
    await stopped;
    document.getElementById(`turn-${turn.id}`)?.classList.remove("singing");
    // recorder.mimeType is e.g. "audio/webm;codecs=opus" (Chrome) or "audio/mp4" (Safari).
    const clip = new Blob(chunks, { type: recorder.mimeType });
    uploads = uploads.then(() => uploadClip(turn.id, clip));
  }

  backing.pause();
  stream.getTracks().forEach((track) => track.stop()); // turn the microphone off
  nowSinging.textContent = "Saving your lines…";
  await uploads;
  nowSinging.textContent = "";
  await load();
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
