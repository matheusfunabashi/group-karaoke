// Finale page: play the backing track and start each person's clip at their part's time.

const sessionId = new URLSearchParams(window.location.search).get("id");
let finale = null;
let playing = []; // every Audio element and timer currently running, so Stop can end them

async function load() {
  finale = await api(`/api/recordings/sessions/${encodeURIComponent(sessionId)}/finale`);
  document.getElementById("back-link").href = `/session.html?id=${encodeURIComponent(sessionId)}`;
  const recorded = finale.playlist.filter((item) => item.clip_url).length;
  document.getElementById("status").textContent =
    `${recorded} of ${finale.playlist.length} parts recorded` +
    (finale.status === "complete" ? " · complete!" : " · parts not sung yet stay silent");

  const list = document.getElementById("playlist");
  list.replaceChildren();
  for (const item of finale.playlist) {
    const seconds = `${item.start_ms / 1000}s – ${item.end_ms / 1000}s`;
    const row = el("div", "", "turn");
    row.id = `item-${item.turn_id}`;
    row.append(el("div", `Part ${item.position}`), el("div", item.clip_url ? seconds : "not recorded", "muted"));
    list.append(row);
  }
}

function play() {
  stop();
  const backing = new Audio(finale.backing_track_url);
  backing.addEventListener("ended", stop);
  playing.push(backing);

  for (const item of finale.playlist) {
    if (!item.clip_url) continue;
    const clip = new Audio(item.clip_url);
    clip.preload = "auto";
    // Start each clip when the backing track reaches that part (start_ms after we press Play).
    const timer = setTimeout(() => {
      clip.play();
      document.getElementById(`item-${item.turn_id}`).style.fontWeight = "bold";
    }, item.start_ms);
    playing.push(clip, timer);
  }
  backing.play();
  document.getElementById("stop").disabled = false;
}

function stop() {
  for (const thing of playing) {
    if (thing instanceof Audio) thing.pause();
    else clearTimeout(thing);
  }
  playing = [];
  document.getElementById("stop").disabled = true;
  document.querySelectorAll("#playlist .turn").forEach((row) => (row.style.fontWeight = ""));
}

document.getElementById("play").addEventListener("click", play);
document.getElementById("stop").addEventListener("click", stop);
load().catch(showError);
