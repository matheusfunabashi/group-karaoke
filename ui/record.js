// Recording page: a karaoke screen. The backing track plays, the current line is shown big and
// fills in word by word, and the microphone records only during this person's lines. Each of
// their lines becomes one clip, uploaded as soon as the line ends.
//
// record.html?id=<session>            all of my lines that still need a recording
// record.html?id=<session>&turn=<id>  just that one line (to sing it again)
//
// Timing (see karaoke.js): the backing track is decoded into memory and played on the Web Audio
// clock. The lyrics follow songMs(), the position in the song the singer is hearing right now.
// The microphone is captured on the audio thread the whole time, and each of my lines is cut out
// of it afterwards at the exact moments it was sung, so the clip lines up with the music.

const params = new URLSearchParams(window.location.search);
const sessionId = params.get("id");
const onlyTurn = params.get("turn") ? Number(params.get("turn")) : null;
const sessionPage = `/session.html?id=${encodeURIComponent(sessionId)}`;
const LEAD_IN_MS = 3000; // start the music a little before the first line, to find the beat
const COUNTDOWN_MS = 3000; // "your line in 3, 2, 1" before each of my lines

let backingBuffer = null; // the decoded backing track
let source = null; // the backing track while it plays
let songStart = 0; // audio-clock time (s) at which song position 0 would have been heard
let stream = null; // the microphone
let capture = null; // the microphone recorder on the audio thread (startCapture in karaoke.js)
let micDelayS = 0; // how late the microphone delivers sound (reported by Chrome, else 0)
let mine = []; // my lines on this page
const cut = new Set(); // my lines already cut out of the capture and sent
let stopped = false;
let uploads = Promise.resolve(); // one upload at a time (see uploadClip)
let saved = 0;
let failed = 0;
let total = 0; // how many lines this person is singing on this page

// Position in the song, in ms, that the singer is hearing now.
function songMs() {
  return (heardTime() - songStart) * 1000;
}

async function load() {
  const session = await api(`/api/sessions/${encodeURIComponent(sessionId)}`);
  const me = myParticipantId(sessionId);
  const names = Object.fromEntries(session.participants.map((p) => [p.id, p.display_name]));
  document.getElementById("song-title").textContent = session.song.title;
  document.getElementById("back-link").href = sessionPage;

  mine = session.turns.filter(
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

  const ready = document.getElementById("ready-text");
  const go = document.getElementById("go-button");
  document.getElementById("ready-card").hidden = false;
  ready.textContent = "Loading the song…";
  go.disabled = true;
  backingBuffer = await loadAudio("/" + session.song.audio_file);
  ready.textContent = mine.length === 1
    ? "You have 1 line to sing."
    : `You have ${mine.length} lines to sing. The song plays from just before your first one.`;
  go.disabled = false;
  go.onclick = () => sing(lines);
}

async function sing(lines) {
  showError(null);
  total = mine.length;
  await audioContext().resume(); // allowed now: we are inside a click
  try {
    // Echo cancellation and noise suppression are off so the voice is recorded as sung (with
    // headphones there is no echo to remove), and they add delay.
    stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: false, noiseSuppression: false, autoGainControl: false },
    });
  } catch {
    showError(new Error("Microphone access is needed to record your lines"));
    return;
  }
  micDelayS = stream.getAudioTracks()[0].getSettings().latency || 0;
  capture = await startCapture(stream);
  document.getElementById("ready-card").hidden = true;
  document.getElementById("stage").hidden = false;

  // Start the backing track a moment from now, from just before my first line
  const offsetS = Math.max(0, mine[0].start_ms - LEAD_IN_MS) / 1000;
  const when = audioContext().currentTime + 0.1;
  source = playBuffer(backingBuffer, when, offsetS);
  songStart = when - offsetS;

  const end = mine[mine.length - 1].end_ms;

  // Runs on every screen refresh (about 60 times a second): the song position decides which
  // line is shown and how much of it is filled in, and which of my lines are over and can be cut
  // out of the microphone capture. If the page is slow, lines are cut a little later, but always
  // at their exact times.
  const tick = () => {
    if (stopped) return;
    const now = songMs();
    const index = lines.findIndex((line) => now < line.end_ms);
    const line = lines[index];
    if (line) showLine(line, lines[index + 1], now);
    cutFinishedLines(now);
    if (now >= end + CUT_MARGIN_MS) {
      finish();
    } else {
      requestAnimationFrame(tick);
    }
  };
  requestAnimationFrame(tick);
}

const CUT_MARGIN_MS = 400; // wait this long after a line ends, so its last sound has arrived

// Cut out every one of my lines that is over, and upload it.
function cutFinishedLines(now) {
  for (const line of mine) {
    if (cut.has(line.id) || now < line.end_ms + CUT_MARGIN_MS) continue;
    cut.add(line.id);
    // Song position p was heard at audio-clock time songStart + p. The singer's voice for it
    // reached the capture later, by the output delay (the headphones) plus the microphone's delay.
    const delay = outputDelay() + micDelayS;
    const from = songStart + line.start_ms / 1000 + delay;
    const to = songStart + line.end_ms / 1000 + delay;
    uploadClip(line.id, capture.clip(from, to));
    capture.forget(to);
  }
}

// The big line, plus what to do now ("Sing now!", a countdown, or who is singing) and what's next.
function showLine(line, next, now) {
  renderLine(document.getElementById("current-line"), line, now, line.isMine);
  const cue = document.getElementById("cue");
  if (now < line.start_ms) {
    const seconds = Math.ceil((line.start_ms - now) / 1000);
    cue.textContent = line.isMine && line.start_ms - now <= COUNTDOWN_MS
      ? `Your line in ${seconds}…`
      : `${line.isMine ? "You" : line.singer} next`;
  } else {
    cue.textContent = line.isMine ? "🎤 Sing now!" : `${line.singer} is singing`;
  }
  document.getElementById("next-line").textContent = next ? `${next.isMine ? "You" : next.singer}: ${next.lyrics}` : "";
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
  if (capture) {
    cutFinishedLines(songMs()); // lines that are over but not cut yet; a line cut short is not saved
    capture.stop();
  }
  if (source) source.stop();
  if (stream) stream.getTracks().forEach((track) => track.stop()); // turn the microphone off
  document.getElementById("stage").hidden = true;
  showDone("Saving your lines…", "");
  await uploads;
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
