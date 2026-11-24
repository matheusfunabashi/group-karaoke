// Shared by the recording page and the finale: exact audio timing with the Web Audio API,
// and the big karaoke line that fills in word by word.
//
// Why Web Audio and not <audio> elements: an <audio> element can't jump to an exact time in a
// variable-bitrate MP3 (the browser estimates the position from the file size and can be off by
// a second or more), and clips started with setTimeout begin late while they download. Here every
// file is downloaded and decoded into memory first, and each one is started at an exact time on
// the same audio clock.

let context = null;

// One AudioContext for the page. Browsers create it "suspended" until the user clicks something,
// so callers resume() it inside a click handler before playing.
function audioContext() {
  if (!context) context = new AudioContext();
  return context;
}

// Download a file and decode it into an AudioBuffer (the whole sound, sample by sample).
async function loadAudio(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Couldn't load ${url} (${response.status})`);
  return audioContext().decodeAudioData(await response.arrayBuffer());
}

// Play a buffer at an exact moment on the audio clock (`when`, in seconds), from `offset` seconds
// into the sound, into `output` (the speakers unless given, e.g. a volume control). Returns the
// source so it can be stopped.
function playBuffer(buffer, when, offset = 0, output = audioContext().destination) {
  const source = audioContext().createBufferSource();
  source.buffer = buffer;
  source.connect(output);
  source.start(when, offset);
  return source;
}

// How much to boost a recorded voice so every singer comes out about equally loud and clearly
// above the backing track. The microphone is recorded raw (no automatic gain, see record.js), so
// a clip is often very quiet. The level is measured on the loudest stretches of the clip (the
// 90th percentile of 50 ms windows), so silence before and after the singing doesn't count.
// A clip with nothing sung in it isn't boosted, so its background noise stays quiet.
const VOICE_LEVEL = 0.2; // the target loudness (RMS of the loud parts) of every voice
const MAX_VOICE_BOOST = 12;
function voiceBoost(buffer) {
  const samples = buffer.getChannelData(0);
  const window = Math.round(buffer.sampleRate * 0.05);
  const levels = [];
  for (let start = 0; start + window <= samples.length; start += window) {
    let sum = 0;
    for (let i = start; i < start + window; i++) sum += samples[i] * samples[i];
    levels.push(Math.sqrt(sum / window));
  }
  if (levels.length === 0) return 1;
  levels.sort((a, b) => a - b);
  const loud = levels[Math.floor(levels.length * 0.9)];
  if (loud < 0.003) return 1; // silence: nobody sang
  return Math.min(MAX_VOICE_BOOST, Math.max(1, VOICE_LEVEL / loud));
}

// The moment on the audio clock that the listener is hearing right now. The clock itself
// (currentTime) runs ahead of the speakers by the output latency, which is small on built-in
// speakers but 0.15 to 0.3 s on Bluetooth headphones. Lyrics follow what is heard, not what is sent.
function heardTime() {
  const ctx = audioContext();
  if (ctx.getOutputTimestamp) {
    const stamp = ctx.getOutputTimestamp();
    if (stamp.contextTime > 0) return stamp.contextTime + (performance.now() - stamp.performanceTime) / 1000;
  }
  return ctx.currentTime - (ctx.outputLatency || ctx.baseLatency || 0);
}

// How far the audio clock runs ahead of what is heard (seconds): see heardTime().
function outputDelay() {
  return Math.min(0.5, Math.max(0, audioContext().currentTime - heardTime()));
}

// The microphone recorder. It runs on the audio thread (an AudioWorklet), which keeps exact
// time even when the page itself is busy or slow, and sends the sound to the page in blocks of
// 4096 samples, each stamped with the audio-clock time of its first sample. clip(from, to) then
// cuts out exactly the sound between two moments: no recorder has to be started or stopped on time.
const CAPTURE_WORKLET = `
class Capture extends AudioWorkletProcessor {
  constructor() { super(); this.block = new Float32Array(4096); this.filled = 0; this.time = 0; }
  process(inputs) {
    const input = inputs[0][0] || new Float32Array(128); // no sound yet: keep time with silence
    if (this.filled === 0) this.time = currentTime;
    this.block.set(input, this.filled);
    this.filled += input.length;
    if (this.filled === this.block.length) {
      this.port.postMessage({ time: this.time, samples: this.block });
      this.block = new Float32Array(4096);
      this.filled = 0;
    }
    return true;
  }
}
registerProcessor("capture", Capture);
`;

async function startCapture(stream) {
  const ctx = audioContext();
  const module = URL.createObjectURL(new Blob([CAPTURE_WORKLET], { type: "application/javascript" }));
  await ctx.audioWorklet.addModule(module);
  const node = new AudioWorkletNode(ctx, "capture", {
    channelCount: 1, channelCountMode: "explicit", numberOfOutputs: 1, outputChannelCount: [1],
  });
  // The node must be connected to the speakers to run, through a volume of 0 so the singer
  // doesn't hear their own microphone.
  const silent = ctx.createGain();
  silent.gain.value = 0;
  ctx.createMediaStreamSource(stream).connect(node).connect(silent).connect(ctx.destination);
  let blocks = [];
  node.port.onmessage = (event) => blocks.push(event.data);

  return {
    // The microphone sound between two audio-clock times (seconds), as a WAV file.
    clip(from, to) {
      const rate = ctx.sampleRate;
      const out = new Float32Array(Math.max(0, Math.round((to - from) * rate)));
      for (const { time, samples } of blocks) {
        const offset = Math.round((time - from) * rate); // where this block lands in the clip
        for (let i = Math.max(0, -offset); i < samples.length && offset + i < out.length; i++) {
          out[offset + i] = samples[i];
        }
      }
      return wavFile(out, rate);
    },
    // Drop sound from before `time`, so memory doesn't grow during a long song.
    forget(time) {
      blocks = blocks.filter((block) => block.time + block.samples.length / ctx.sampleRate >= time);
    },
    stop() {
      node.port.onmessage = null;
      node.disconnect();
    },
  };
}

// Samples (-1..1) as a 16-bit mono WAV file.
function wavFile(samples, rate) {
  const view = new DataView(new ArrayBuffer(44 + samples.length * 2));
  const text = (at, s) => [...s].forEach((c, i) => view.setUint8(at + i, c.charCodeAt(0)));
  text(0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  text(8, "WAVE");
  text(12, "fmt ");
  view.setUint32(16, 16, true); // size of this header part
  view.setUint16(20, 1, true); // PCM
  view.setUint16(22, 1, true); // mono
  view.setUint32(24, rate, true);
  view.setUint32(28, rate * 2, true); // bytes per second
  view.setUint16(32, 2, true); // bytes per sample
  view.setUint16(34, 16, true); // bits per sample
  text(36, "data");
  view.setUint32(40, samples.length * 2, true);
  samples.forEach((s, i) => view.setInt16(44 + i * 2, Math.max(-1, Math.min(1, s)) * 0x7fff, true));
  return new Blob([view.buffer], { type: "audio/wav" });
}

// Roughly how many syllables a word has: its groups of vowels, minus a silent "e" at the end and
// the "-es"/"-ed" endings that aren't sung as their own syllable. A sung syllable is usually one
// note, so filling word by word in syllables follows the rhythm much better than in letters
// ("through" is one note, not seven letters' worth). Songs are timed per line only (there is no
// word timing for them), so this is an estimate. "/" between merged lines takes no time.
function syllables(word) {
  const w = word.toLowerCase().replace(/[^a-z]/g, "");
  if (!w) return 0;
  let count = (w.match(/[aeiouy]+/g) ?? []).length;
  if (count > 1 && /[^aeiouy]e$/.test(w) && !/[^aeiouy]le$/.test(w)) count--; // silent e: "smile", not "table"
  if (count > 1 && /[^sxzcg]es$/.test(w) && !/[cs]hes$/.test(w)) count--; // "phones", not "places"
  if (count > 1 && /[^td]ed$/.test(w)) count--; // "played", not "wanted"
  if (/[aeiouy]ing$/.test(w)) count++; // "going", "trying": the vowel before -ing is its own syllable
  return Math.max(1, count);
}

// How fast the words fill in, in syllables per ms. A song timed from its real recording (Payphone:
// LRCLIB timestamps) only knows where each line starts, so a line lasts until the next one starts,
// through any pause or held note after it. Filling evenly up to that point trailed the singing by
// up to 2.6 s, so such songs fill at their usual singing pace (1.25 x the median syllables per
// second of their lines) and the line then stays full until the next. The traditional songs'
// melodies were made to spread evenly over each line, so they fill over the whole line (null).
let fillPace = null;
function paceLyrics(song, lines) {
  if (song.artist === "Traditional") return;
  const rates = lines
    .map((line) => line.lyrics.split(" ").reduce((sum, word) => sum + syllables(word), 0) / (line.end_ms - line.start_ms))
    .sort((a, b) => a - b);
  fillPace = rates[Math.floor(rates.length / 2)] * 1.25;
}

// A nudge for the lyrics, in ms (positive: show them later), kept in this browser for each song,
// for headphones whose delay the browser misjudges. A song whose times are corrected is a new song
// in the database (see seed_catalog), so its nudge starts again from 0. It only moves what is
// shown: recordings are always cut at the music's times.
let offsetKey = null;
function lyricsOffset() {
  try {
    return Number(localStorage.getItem(offsetKey)) || 0;
  } catch {
    return 0; // storage blocked: no nudge
  }
}

// "Lyrics timing: ◀ earlier  +0.2 s  later ▶" buttons inside `container`, for `song`.
function lyricsNudge(container, song) {
  offsetKey = `karaoke:lyrics-offset-ms:${song.id}`;
  const label = el("span", "", "nudge-value");
  const show = () => (label.textContent = `${lyricsOffset() >= 0 ? "+" : ""}${(lyricsOffset() / 1000).toFixed(1)} s`);
  const button = (text, step) => {
    const b = el("button", text, "secondary nudge-button");
    b.type = "button";
    b.addEventListener("click", () => {
      try {
        localStorage.setItem(OFFSET_KEY, String(Math.max(-2000, Math.min(2000, lyricsOffset() + step))));
      } catch {
        // storage blocked: the nudge can't be kept
      }
      show();
    });
    return b;
  };
  container.classList.add("nudge");
  container.replaceChildren(el("span", "Lyrics timing:"), button("◀ earlier", -100), label, button("later ▶", 100));
  show();
}

// Show `line` in `element` as one <span> per word, each word filled (CSS reads --fill) up to how
// far the song is into the line, in reading order. Songs are timed per line, not per word, so each
// word gets a share of the line's time in proportion to its syllables (see syllables), at the
// song's pace (see paceLyrics).
function renderLine(element, line, nowMs, isMine) {
  if (element.dataset.turn !== String(line.id)) {
    element.dataset.turn = line.id;
    element.replaceChildren(...line.lyrics.split(" ").map((word) => {
      const span = el("span", word);
      span.dataset.beats = syllables(word);
      return span;
    }));
  }
  element.classList.toggle("mine", isMine);
  const words = [...element.children];
  const beats = words.reduce((sum, word) => sum + Number(word.dataset.beats), 0);
  const lineMs = line.end_ms - line.start_ms;
  const fillMs = fillPace ? Math.min(lineMs, beats / fillPace) : lineMs;
  const progress = Math.min(1, Math.max(0, (nowMs - line.start_ms) / fillMs));
  let reached = progress * beats;
  for (const word of words) {
    const share = Number(word.dataset.beats);
    const filled = share ? reached / share : reached > 0 ? 1 : 0; // "/" lights up with the word before it
    word.style.setProperty("--fill", `${Math.min(1, Math.max(0, filled)) * 100}%`);
    reached -= share;
  }
}
