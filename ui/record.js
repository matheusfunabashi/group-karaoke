// Recording page (record.html?id=<session>): a karaoke screen. The whole song plays, so it is easy
// to keep the rhythm; the current line is shown big and fills in word by word. Only this person's
// lines that still need a recording are recorded; on everyone else's the screen says "Not your
// part". Each of my lines becomes one clip, uploaded as soon as the line ends.
//
// Timing (see karaoke.js): the backing track is decoded into memory and played on the Web Audio
// clock. The lyrics follow songMs(), the position in the song the singer is hearing right now.
// The microphone is captured on the audio thread the whole time, and each of my lines is cut out
// of it afterwards at the exact moments it was sung, so the clip lines up with the music.
//
// Above the lyrics is the karaoke room (characters.js): whoever has the line being sung stands up.

const sessionId = new URLSearchParams(window.location.search).get("id");
const sessionPage = `/session.html?id=${encodeURIComponent(sessionId)}`;
const COUNTDOWN_MS = 3000; // "your line in 3, 2, 1" before each of my lines
const CUT_MARGIN_MS = 400; // wait this long after a line ends, so its last sound has arrived

let backingBuffer = null; // the decoded backing track
let source = null; // the backing track while it plays
let songStart = 0; // audio-clock time (s) at which song position 0 would have been heard
let stream = null; // the microphone
let capture = null; // the microphone recorder on the audio thread (startCapture in karaoke.js)
let micDelayS = 0; // how late the microphone delivers sound (reported by Chrome, else 0)
let mine = []; // my lines that still need a recording
const cut = new Set(); // my lines already cut out of the capture and sent
let stopped = false;
let uploads = Promise.resolve(); // one upload at a time (see uploadClip)
let saved = 0;
let failed = 0;
let total = 0; // how many lines this person is singing on this page
let room = null; // everyone around the table; the singer of the current line stands up

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
  room = createRoom(document.getElementById("room"));
  room.setTitle(session.song.title);
  room.setPeople(session.participants, me);

  mine = session.turns.filter((t) => t.participant_id === me && t.status === "assigned");
  if (mine.length === 0) {
    showDone("Nothing to record", "You have no lines waiting for a recording in this session.");
    return;
  }
  // Every line of the song, so the singer can follow all of it and knows when their turn comes
  const lines = session.turns.map((t) => ({
    ...t, singer: names[t.participant_id] ?? "someone", isMine: mine.includes(t),
  }));
  paceLyrics(session.song, lines);
  lyricsNudge(document.getElementById("nudge"), session.song);

  const ready = document.getElementById("ready-text");
  const go = document.getElementById("go-button");
  document.getElementById("ready-card").hidden = false;
  ready.textContent = "Loading the song…";
  go.disabled = true;
  backingBuffer = await loadAudio("/" + session.song.audio_file);
  ready.textContent = `You have ${mine.length} line${mine.length === 1 ? "" : "s"} to sing. ` +
    "The whole song plays; only your lines are recorded.";
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

  // Start the whole song a moment from now
  const when = audioContext().currentTime + 0.1;
  source = playBuffer(backingBuffer, when);
  songStart = when;

  // Stop at the end of the song (and never before my last line has been cut out)
  const end = Math.max(backingBuffer.duration * 1000, mine[mine.length - 1].end_ms + CUT_MARGIN_MS);

  // Runs on every screen refresh (about 60 times a second): the song position decides which
  // line is shown and how much of it is filled in, and which of my lines are over and can be cut
  // out of the microphone capture. If the page is slow, lines are cut a little later, but always
  // at their exact times. The lyrics nudge (karaoke.js) moves only what is shown, never the cuts.
  const tick = () => {
    if (stopped) return;
    const now = songMs();
    const shown = now - lyricsOffset();
    const index = lines.findIndex((line) => shown < line.end_ms);
    const line = lines[index];
    room.setSinger(line && shown >= line.start_ms ? line.participant_id : null);
    if (line) {
      showLine(line, lines[index + 1], shown);
    } else {
      document.getElementById("cue").textContent = "End of the song";
      document.getElementById("next-line").textContent = "";
    }
    cutFinishedLines(now);
    if (now >= end) {
      finish();
    } else {
      requestAnimationFrame(tick);
    }
  };
  requestAnimationFrame(tick);
}


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

// The big line, plus what to do now and what's next. On my lines: a countdown, then "Sing now!".
// On everyone else's: "Not your part", and who is singing it.
function showLine(line, next, now) {
  renderLine(document.getElementById("current-line"), line, now, line.isMine);
  const cue = document.getElementById("cue");
  if (line.isMine) {
    const seconds = Math.ceil((line.start_ms - now) / 1000);
    cue.textContent = now >= line.start_ms ? "🎤 Sing now!"
      : line.start_ms - now <= COUNTDOWN_MS ? `Your line in ${seconds}…` : "Your line is next";
  } else {
    cue.textContent = `Not your part · ${line.singer} ${now >= line.start_ms ? "is singing" : "is next"}`;
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
