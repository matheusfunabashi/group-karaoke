// Where each service lives. These are the docker compose ports; on Azure the CD workflow
// overwrites this file with the Container Apps' addresses before uploading the UI.
window.KARAOKE_CONFIG = {
  sessionsUrl: "http://localhost:8001",
  recordingsUrl: "http://localhost:8002",
};
