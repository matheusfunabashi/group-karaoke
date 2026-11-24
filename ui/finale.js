// Finale page: play the backing track with every recorded line on top of it, at the moment its
// line starts, and show the lyrics like a karaoke screen.
//
// Timing (see karaoke.js): the backing track and all clips are downloaded and decoded before Play
// is enabled, then every one is scheduled on the same Web Audio clock, so each clip starts exactly
// at its line instead of whenever a timer fires and the clip has finished downloading.
//
// Volume: microphones record voices much quieter than a mastered backing track. Each clip is
// boosted to the same loudness (voiceBoost in karaoke.js), the voices go through a compressor so
// the loud bits don't distort, and the backing track plays a little quieter, under the voices.
//
// Above the lyrics is the karaoke room (characters.js): whoever sang the line playing stands up.

const sessionId = new URLSearchParams(window.location.search).get("id");
let items = []; // the playlist, with lyrics and singer added and each clip's decoded audio
let backingBuffer = null;
const BACKING_VOLUME = 0.55;
let playing = []; // the sources currently playing, so Stop can end them
let songStart = 0; // audio-clock time (s) at which the song started
let running = false;
let room = null; // everyone around the table; the singer of the line playing stands up

async function load() {
  // The finale (from recordings) has the timing and clips; the session (from sessions) has the
  // lyrics and who sings each line.
  const [finale, session] = await Promise.all([
    api(`/api/recordings/sessions/${encodeURIComponent(sessionId)}/finale`),
    api(`/api/sessions/${encodeURIComponent(sessionId)}`),
  ]);
  document.getElementById("back-link").href = `/session.html?id=${encodeURIComponent(sessionId)}`;
  const names = Object.fromEntries(session.participants.map((p) => [p.id, p.display_name]));
  const turns = Object.fromEntries(session.turns.map((t) => [t.id, t]));
  room = createRoom(document.getElementById("room"));
  room.setTitle(session.song.title);
  room.setPeople(session.participants, myParticipantId(sessionId));
  room.setCaption("Press Play");
  paceLyrics(session.song, session.turns);
  lyricsNudge(document.getElementById("nudge"));
  items = finale.playlist.map((item) => ({
    ...item,
    id: item.turn_id,
    lyrics: turns[item.turn_id]?.lyrics ?? "",
    participant_id: turns[item.turn_id]?.participant_id,
    singer: names[turns[item.turn_id]?.participant_id] ?? "someone",
  }));

  const recorded = items.filter((item) => item.clip_url).length;
  document.getElementById("status").textContent =
    `${recorded} of ${items.length} lines recorded` +
    (finale.status === "complete" ? " · complete!" : " · lines not sung yet stay silent");
  const list = document.getElementById("playlist");
  list.replaceChildren();
  for (const item of items) {
    const row = el("div", "", "turn");
    row.id = `item-${item.turn_id}`;
    row.append(el("div", `${item.position}. ${item.singer}`), el("div", item.clip_url ? "" : "not recorded", "muted"));
    list.append(row);
  }

  // Download and decode everything before allowing Play
  const play = document.getElementById("play");
  let ready = 0;
  const progress = () => (play.textContent = `Loading clips… ${ready} of ${recorded}`);
  progress();
  backingBuffer = await loadAudio(finale.backing_track_url);
  await Promise.all(items.filter((item) => item.clip_url).map(async (item) => {
    try {
      item.buffer = await loadAudio(serviceUrl(item.clip_url)); // clips are served by the recordings service
      item.boost = voiceBoost(item.buffer);
    } catch {
      document.querySelector(`#item-${item.turn_id} .muted`).textContent = "can't be played in this browser";
    }
    ready++;
    progress();
  }));
  play.textContent = "▶ Play";
  play.disabled = false;
}

async function play() {
  stop();
  await audioContext().resume(); // allowed now: we are inside a click
  const when = audioContext().currentTime + 0.2;
  songStart = when;
  const { music, voices } = mixer();
  const backing = playBuffer(backingBuffer, when, 0, music);
  backing.onended = stop;
  playing.push(backing);
  for (const item of items) {
    if (!item.buffer) continue;
    const volume = audioContext().createGain();
    volume.gain.value = item.boost;
    volume.connect(voices);
    playing.push(playBuffer(item.buffer, when + item.start_ms / 1000, 0, volume));
  }
  running = true;
  document.getElementById("stop").disabled = false;
  requestAnimationFrame(show);
}

// Where the sounds go: the backing track through a volume control, the voices through a
// compressor that evens them out, and everything through a limiter so the mix never clips.
let mix = null;
function mixer() {
  if (mix) return mix;
  const ctx = audioContext();
  const limiter = new DynamicsCompressorNode(ctx, { threshold: -3, knee: 0, ratio: 20, attack: 0.002, release: 0.1 });
  limiter.connect(ctx.destination);
  const music = new GainNode(ctx, { gain: BACKING_VOLUME });
  music.connect(limiter);
  const voices = new DynamicsCompressorNode(ctx, { threshold: -24, knee: 12, ratio: 4, attack: 0.005, release: 0.2 });
  const makeUp = new GainNode(ctx, { gain: 1.6 }); // gives back the loudness the compressor takes off
  voices.connect(makeUp).connect(limiter);
  mix = { music, voices };
  return mix;
}

// Every screen refresh: show the line being heard now, and bold its row in the list.
function show() {
  if (!running) return;
  const now = (heardTime() - songStart) * 1000 - lyricsOffset(); // the lyrics nudge: what is shown
  const line = items.find((item) => now < item.end_ms);
  const cue = document.getElementById("cue");
  room.setSinger(line && now >= line.start_ms ? line.participant_id : null);
  if (line) {
    renderLine(document.getElementById("current-line"), line, now, Boolean(line.buffer));
    cue.textContent = now < line.start_ms ? `${line.singer} next` : `${line.singer}${line.buffer ? "" : " (not recorded)"}`;
  }
  document.querySelectorAll("#playlist .turn").forEach((row) => (row.style.fontWeight = ""));
  if (line && now >= line.start_ms) document.getElementById(`item-${line.turn_id}`).style.fontWeight = "bold";
  requestAnimationFrame(show);
}

function stop() {
  running = false;
  room?.setSinger(null);
  for (const source of playing) source.stop();
  playing = [];
  document.getElementById("stop").disabled = true;
  document.querySelectorAll("#playlist .turn").forEach((row) => (row.style.fontWeight = ""));
}

document.getElementById("play").addEventListener("click", play);
document.getElementById("stop").addEventListener("click", stop);
load().catch(showError);
