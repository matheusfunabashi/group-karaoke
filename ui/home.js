// Home page: choose a song and create a session.

async function loadSongs() {
  const songs = await api("/api/sessions/songs");
  const select = document.getElementById("song");
  for (const song of songs) {
    const option = el("option", `${song.title} (${song.artist})`);
    option.value = song.id;
    select.append(option);
  }
}

document.getElementById("create-form").addEventListener("submit", async (event) => {
  event.preventDefault(); // stop the browser from reloading the page
  try {
    const session = await api("/api/sessions", {
      method: "POST",
      body: JSON.stringify({
        song_id: Number(document.getElementById("song").value),
        host_name: document.getElementById("host-name").value,
      }),
    });
    // The host is the first participant: remember it so this browser can claim turns.
    rememberParticipant(session.id, session.participants[0].id);
    window.location.href = `/session.html?id=${encodeURIComponent(session.id)}`;
  } catch (error) {
    showError(error);
  }
});

loadSongs().catch(showError);
