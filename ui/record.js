// Recording page: a karaoke screen. The backing track plays, the current line is shown big and
// fills in from left to right over its duration, and the microphone records only during this
// person's lines. Each of their lines becomes one clip, uploaded as soon as the line ends.
//
// record.html?id=<session>            all of my lines that still need a recording
// record.html?id=<session>&turn=<id>  just that one line (to redo it)

const params = new URLSearchParams(window.location.search);
const sessionId = params.get("id");
const onlyTurn = params.get("turn") ? Number(params.get("turn")) : null;
const sessionPage = `/session.html?id=${encodeURIComponent(sessionId)}`;
const LEAD_IN_MS = 3000; // start the music a little before the first line, to find the beat
const COUNTDOWN_MS = 3000; // "your line in 3, 2, 1" before each of my lines

let backing = null; // the <audio> playing the backing track
let stream = null; // the microphone
let recorder = null; // the MediaRecorder of the line being sung right now, if any
let stopped = false;
let uploads = Promise.resolve(); // one upload at a time (see uploadClip)
const recorderStops = []; // resolves when each line's recorder has handed over its clip
let saved = 0;
let failed = 0;
let total = 0; // how many lines this person is singing on this page

async function load() {
  const session = await api(`/api/sessions/${encodeURIComponent(sessionId)}`);
  const me = myParticipantId(sessionId);
  const names = Object.fromEntries(session.participants.map((p) => [p.id, p.display_name]));
  document.getElementById("song-title").textContent = session.song.title;
  document.getElementById("back-link").href = sessionPage;

  const mine = session.turns.filter(
    (t) => t.participant_id === me && t.status === "assigned" && (onlyTurn === null || t.id === onlyTurn),
  );
  if (mine.length === 0) {
    showDone("Nothing to record", "You have no lines waiting for a recording in this session.");
    return;
  }
  // Everything that plays between my first and last line, including other people's lines,
  // so I can follow the song and know when my next line comes.
  const from = mine[0].start_ms;
  const to = mine[mine.length - 1].end_ms;
  const lines = session.turns
    .filter((t) => t.end_ms > from && t.start_ms < to)
    .map((t) => ({ ...t, singer: names[t.participant_id] ?? "someone", isMine: mine.includes(t) }));

  document.getElementById("ready-text").textContent = mine.length === 1
    ? "You have 1 line to sing."
    : `You have ${mine.length} lines to sing. The song plays from just before your first one.`;
  document.getElementById("ready-card").hidden = false;
  document.getElementById("go-button").onclick = () => sing(session, lines, mine);
}

async function sing(session, lines, mine) {
  showError(null);
  total = mine.length;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch {
    showError(new Error("Microphone access is needed to record your lines"));
    return;
  }
  document.getElementById("ready-card").hidden = true;
  document.getElementById("stage").hidden = false;

  backing = new Audio("/" + session.song.audio_file);
  backing.currentTime = Math.max(0, mine[0].start_ms - LEAD_IN_MS) / 1000;
  try {
    await backing.play();
  } catch {
    stream.getTracks().forEach((track) => track.stop());
    document.getElementById("stage").hidden = true;
    document.getElementById("ready-card").hidden = false;
    showError(new Error("The backing track couldn't start playing. Press Start singing again."));
    return;
  }

  const end = mine[mine.length - 1].end_ms;
  const recorded = new Set();
  let chunks = [];

  // Runs on every screen refresh (about 60 times a second): the backing track's position
  // decides which line is shown, how much of it is filled in, and when to record.
  const tick = () => {
    if (stopped) return;
    const now = backing.currentTime * 1000;
    const index = lines.findIndex((line) => now < line.end_ms);
    const line = lines[index];
    showLine(line, lines[index + 1], now, mine);

    // Start recording when one of my lines begins, stop when it ends
    if (line && line.isMine && now >= line.start_ms && !recorder && !recorded.has(line.id)) {
      chunks = [];
      recorder = new MediaRecorder(stream);
      recorder.addEventListener("dataavailable", (event) => chunks.push(event.data));
      recorder.start();
      recorder.turn = line;
    }
    if (recorder && now >= recorder.turn.end_ms) {
      const finished = recorder;
      const finishedChunks = chunks;
      recorded.add(finished.turn.id);
      recorder = null;
      // A recorder hands over its audio a moment after stop(), so remember when that happens:
      // finish() waits for it, otherwise the last line could be missed.
      recorderStops.push(new Promise((resolve) => finished.addEventListener("stop", () => {
        // finished.mimeType is e.g. "audio/webm;codecs=opus" (Chrome) or "audio/mp4" (Safari)
        uploadClip(finished.turn.id, new Blob(finishedChunks, { type: finished.mimeType }));
        resolve();
      })));
      finished.stop();
    }

    if (now >= end || backing.ended) {
      finish();
    } else {
      requestAnimationFrame(tick);
    }
  };
  requestAnimationFrame(tick);
}

// The big line fills in word by word, in reading order, over the line's duration, so the singer
// can see how far into the line the music is (and a line that wraps onto two rows fills the
// first row before the second). Each word is its own <span> with its own fill (CSS reads
// --fill). My lines are pink, other people's are white.
function showLine(line, next, now, mine) {
  const cue = document.getElementById("cue");
  const current = document.getElementById("current-line");
  const nextLine = document.getElementById("next-line");
  if (!line) return;

  if (current.dataset.turn !== String(line.id)) {  // a new line: one span per word
    current.dataset.turn = line.id;
    current.replaceChildren(...line.lyrics.split(" ").map((word) => el("span", word)));
    current.classList.toggle("mine", line.isMine);
  }
  // How many letters of the line the music has reached, then fill each word up to there
  const words = [...current.children];
  const letters = words.reduce((sum, word) => sum + word.textContent.length, 0);
  const progress = Math.min(1, Math.max(0, (now - line.start_ms) / (line.end_ms - line.start_ms)));
  let reached = progress * letters;
  for (const word of words) {
    const length = word.textContent.length;
    word.style.setProperty("--fill", `${Math.min(1, Math.max(0, reached / length)) * 100}%`);
    reached -= length;
  }

  if (now < line.start_ms) {
    const seconds = Math.ceil((line.start_ms - now) / 1000);
    cue.textContent = line.isMine && line.start_ms - now <= COUNTDOWN_MS
      ? `Your line in ${seconds}…`
      : `${line.isMine ? "You" : line.singer} next`;
  } else {
    cue.textContent = line.isMine ? "🎤 Sing now!" : `${line.singer} is singing`;
  }
  nextLine.textContent = next ? `${next.isMine ? "You" : next.singer}: ${next.lyrics}` : "";
  const done = mine.filter((t) => t.end_ms <= now).length;
  document.getElementById("progress").textContent = `${done} of ${mine.length} of your lines sung`;
}

// Clips go up one after another, never two at once: each upload makes the sessions service
// update a turn and check whether the session is complete, and doing that for two turns at the
// same moment could make the database stop one of them.
function uploadClip(turnId, clip) {
  uploads = uploads.then(async () => {
    const form = new FormData();
    form.append("turn_id", turnId);
    form.append("clip", clip, `turn-${turnId}`);
    try {
      await api("/api/recordings", { method: "POST", body: form });
      saved++;
    } catch (error) {
      failed++;
      showError(error);
    }
  });
}

async function finish() {
  if (stopped) return;
  stopped = true;
  if (recorder && recorder.state === "recording") recorder.stop(); // a line cut short is not saved
  backing.pause();
  stream.getTracks().forEach((track) => track.stop()); // turn the microphone off
  document.getElementById("stage").hidden = true;
  showDone("Saving your lines…", "");
  await Promise.all(recorderStops); // every finished line has been queued for upload...
  await uploads; // ...and every upload is done
  showDone(
    failed === 0 && saved === total ? "All your lines are saved!" : `${saved} of ${total} lines saved`,
    saved < total ? "Lines that weren't saved can be sung again from the session page." : "Listen to the finale once everyone has sung.",
  );
}

function showDone(title, text) {
  document.getElementById("done-card").hidden = false;
  document.getElementById("done-title").textContent = title;
  document.getElementById("done-text").textContent = text;
}

document.getElementById("stop-button").addEventListener("click", finish);
document.getElementById("done-button").addEventListener("click", () => (window.location.href = sessionPage));

load().catch(showError);
