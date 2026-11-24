# Group Karaoke

Asynchronous group karaoke. A host picks a song, the song is split into segments, each participant records their segment (voice only) whenever they like, and a finale plays every clip in order over the backing track.

**Live:** https://mgimenesui.z1.web.core.windows.net (the first request after a quiet period can take up to a minute: see [Cold starts](#cold-starts)).

## Architecture
Two FastAPI services, each with its own Dockerfile and its own SQL Server database, and a static UI:

```text
Browser ── ui/ (Azure Storage static website)
   │
   ├── sessions   (services/sessions)   songs, sessions, participants, turns ── mgimenes-sessions-db
   └── recordings (services/recordings) clip uploads, finale playlist        ── mgimenes-recordings-db
          │
          └── calls sessions over HTTP (3 endpoints, 3 s timeout)
```

- Each service is split into `routes.py` (HTTP), `service.py` (business rules) and `repository.py` (SQL), plus `db.py` (connections, retries, migrations) and `config.py` (environment variables).
- `services/recordings/recordings/sessions_client.py` is the only place recordings calls sessions (ADR-2, ADR-6). If sessions doesn't answer, recordings answers 503 and saves nothing (ADR-10).
- Clips are stored in the recordings database as `VARBINARY(MAX)` (ADR-7).
- The UI is plain HTML/CSS/JavaScript in `ui/`, no build step. `ui/config.js` holds the two services' addresses; the CD workflow rewrites it for Azure.
- `system.yaml` describes the whole system (validated against `system.schema.json` in CI), and each service has an `openapi.yaml`. Decisions are in `ADR.md` (ADR-1 to ADR-10).

## API
| Service | Method | Path | What it does |
|---|---|---|---|
| both | GET | `/health` | Service, version (git SHA) and database status with its migration version; 503 if the database is unreachable |
| sessions | GET | `/api/sessions/songs` | List the song catalog |
| sessions | POST | `/api/sessions` | Create a session (`song_id`, `host_name`, optional `avatar` 1-6: the host's character) |
| sessions | GET | `/api/sessions/{id}` | Session with song, participants and turns |
| sessions | POST | `/api/sessions/{id}/participants` | Join (`display_name`, optional `avatar` 1-6; without one, a character nobody has yet) |
| sessions | POST | `/api/sessions/{id}/start` | Host only (`participant_id`): deal the song's lines to the singers in rotation |
| sessions | GET | `/api/sessions/turns/{turn_id}/open` | *For recordings:* is this turn waiting for a clip? |
| sessions | POST | `/api/sessions/turns/{turn_id}/recorded` | *For recordings:* mark the turn recorded |
| sessions | GET | `/api/sessions/{id}/timeline` | *For recordings:* the turns' timing for the finale |
| recordings | POST | `/api/recordings` | Upload a clip (multipart: `turn_id`, `clip`; wav/webm/ogg/mp4 audio, max 5 MB) |
| recordings | GET | `/api/recordings/{id}/audio` | Play a clip |
| recordings | GET | `/api/recordings/sessions/{id}/finale` | Backing track URL and the playlist of clips |

The full contracts are in `services/sessions/openapi.yaml` and `services/recordings/openapi.yaml`.

## Run locally with docker compose
Requires Docker. Create `.env` from the example and put your own passwords in it (`.env` is git-ignored and must never be committed):

```bash
cp .env.example .env
docker compose up --build
```

- UI: http://localhost:8080, sessions: http://localhost:8001, recordings: http://localhost:8002 (`/docs` on each service shows its API).
- `db` is SQL Server 2022. `db-init` runs `db/init.sql` once: it creates one database per service and one contained user each, with only `db_ddladmin`, `db_datareader` and `db_datawriter`, the same as on Azure.
- Each service applies its migrations when it starts, then (sessions) loads the song catalog from `services/sessions/sessions/seed.json` if the `songs` table is empty.
- `docker compose down -v` deletes the local database.

## Configuration
All settings are environment variables (also listed in `system.yaml`).

| Variable | Service | Default | Purpose |
|---|---|---|---|
| `PORT` | both | `8000` | HTTP port (always binds to `0.0.0.0`) |
| `DATABASE_URL` | both | none (required, secret) | `mssql+pymssql://user:password@host:1433/database`, plus `?encryption=require` on Azure |
| `CORS_ORIGINS` | both | `http://localhost:8080` | Comma-separated browser origins allowed to call the API (the UI's address) |
| `APP_VERSION` | both | `dev` | Version shown by `/health`; CD sets it to the git commit SHA |
| `SESSIONS_URL` | recordings | `http://localhost:8001` | Base URL of the sessions service |

## Database migrations
Each service has versioned SQL files in `services/<service>/migrations/` (ADR-8). At startup, `db.migrate` applies every file not yet listed in the `schema_migrations` table, oldest first, each in its own transaction.

| Service | Migration | What it does |
|---|---|---|
| sessions | `V001__create_sessions_tables.sql` | `songs`, `song_segments`, `sessions`, `participants`, `turns` |
| sessions | `V002__deal_lines_to_players.sql` | `songs.retired` and `turns.segment_count`, on tables already holding data: one line per turn, dealt in rotation |
| sessions | `V003__choose_a_character.sql` | `participants.avatar` (1-6, with a CHECK constraint) on a table already holding data; people who joined before get characters in turn |
| recordings | `V001__create_recordings_table.sql` | `recordings` (clip details; the clip itself was on disk) |
| recordings | `V002__store_clip_audio_in_database.sql` | `ALTER TABLE recordings ADD audio VARBINARY(MAX) NULL` on a table that already held data |

**Evidence that V002 altered a table holding data on Azure:** `docs/evidence/v002-migration-on-azure.txt`, made with `infra/show-migration-evidence.sh`. Recording 1 was saved on Azure at 17:24 under V001; V002 ran at 17:32 when its commit was deployed; recording 1 is still there with `audio = NULL`, and recording 2, saved after V002, has its audio in the row. The Container App's log shows `Applied migration V002__store_clip_audio_in_database` at the same time.

## Tests and coverage
The tests run against a real SQL Server (ADR-4): each run creates a temporary database and drops it at the end. Point `TEST_DATABASE_URL` at a server where the tests may create databases, for example a throwaway container:

```bash
export TEST_SA_PASSWORD="Aa1$(openssl rand -hex 12)"
docker run -d --name karaoke-test-mssql -e ACCEPT_EULA=Y -e MSSQL_SA_PASSWORD="$TEST_SA_PASSWORD" -p 14333:1433 mcr.microsoft.com/mssql/server:2022-latest
export TEST_DATABASE_URL="mssql+pymssql://sa:${TEST_SA_PASSWORD}@localhost:14333/master"

cd services/sessions && pip install -r requirements-dev.txt && pytest --cov=sessions --cov=app
cd ../recordings && pip install -r requirements-dev.txt && pytest --cov=recordings --cov=app
```

Result in CI (2026-11-22): **sessions 34 tests, 99% coverage; recordings 54 tests, 99% coverage**. CI fails if either service drops below 70%. The browser JavaScript in `ui/` is not covered by these tests (ADR-4).

## CI/CD
- `.github/workflows/ci.yml` runs on every branch push and pull request: `ruff` lint, validation of `system.yaml` (against `system.schema.json`) and both OpenAPI documents, the tests of each service against a throwaway SQL Server with coverage of at least 70%, and a Docker build of each image.
- `.github/workflows/cd.yml` runs on every push to `main`: it calls `ci.yml` (which then pushes `ghcr.io/matheusfunabashi/group-karaoke-<service>:<git SHA>`, built with `provenance: false`), signs in to Azure with OIDC, sets each service's `DATABASE_URL` as a Container Apps secret, points each Container App at the new image, writes `ui/config.js`, uploads `ui/` to the `$web` container, and retries `/health` on both services until they report the new SHA with the database ok (ADR-9).

## Azure setup (done once)
Everything lives in the resource group `rg-mgimenes` in the Azure for Students subscription, region `germanywestcentral`. After this setup, only the pipeline changes anything. The commands below are Bash; no password appears in them.

**1. Subscription and region.** Activate Azure for Students, select it, and check which regions the policy allows:
```bash
az login
az account set --subscription "Azure for Students"
az policy assignment list --query "[?displayName=='Allowed resource deployment regions'].parameters"
```

**2. Providers and resource group.**
```bash
for p in Microsoft.App Microsoft.OperationalInsights Microsoft.Sql Microsoft.Storage Microsoft.ManagedIdentity; do
  az provider register -n $p
done
az group create -n rg-mgimenes -l germanywestcentral
```
(`rg-mgimenes` already existed from a class exercise on 2026-11-12, created in `francecentral`; its old storage account was deleted so that only this system's resources are in it. A resource group's own location is only where its metadata is kept: every resource in it is in `germanywestcentral`.)

**3. The UI: a Storage static website.**
```bash
az storage account create -n mgimenesui -g rg-mgimenes -l germanywestcentral \
  --kind StorageV2 --sku Standard_LRS --min-tls-version TLS1_2 --allow-blob-public-access false
az storage blob service-properties update --account-name mgimenesui --auth-mode login \
  --static-website --index-document index.html --404-document index.html
az storage account show -n mgimenesui --query primaryEndpoints.web -o tsv   # the public URL
```

**4. SQL server, two serverless databases and their users.** `infra/setup-sql.sh` does all of it:
```bash
bash infra/setup-sql.sh
```
It creates the server `mgimenes-sql` (with a random admin password that is never printed or saved), the firewall rule that allows Azure services, and `mgimenes-sessions-db` and `mgimenes-recordings-db` (General Purpose, serverless, Gen5, 0.5–1 vCore, locally redundant backups, free offer with `--use-free-limit true --free-limit-exhaustion-behavior AutoPause`). It then opens the firewall to this machine's IP, creates one contained user per database (`sessions_user`, `recordings_user`) with `db_ddladmin`, `db_datareader` and `db_datawriter`, checks that each one can log in, stores each password straight into a GitHub secret (`SESSIONS_DB_PASSWORD`, `RECORDINGS_DB_PASSWORD`), and closes the firewall again.

**5. Container Apps.** The environment also creates the Log Analytics workspace for the containers' logs. The apps start from the placeholder image; the first deploy replaces it and sets `DATABASE_URL` (as the secret `database-url`, read with `secretref:`), `APP_VERSION` and `CORS_ORIGINS`.
```bash
az containerapp env create -n mgimenes-env -g rg-mgimenes -l germanywestcentral
DOMAIN=$(az containerapp env show -n mgimenes-env -g rg-mgimenes --query properties.defaultDomain -o tsv)
UI=https://mgimenesui.z1.web.core.windows.net
for svc in sessions recordings; do
  EXTRA=""
  [ $svc = recordings ] && EXTRA="SESSIONS_URL=https://mgimenes-sessions.$DOMAIN"
  az containerapp create -n mgimenes-$svc -g rg-mgimenes --environment mgimenes-env \
    --image mcr.microsoft.com/k8se/quickstart:latest --ingress external --target-port 8000 \
    --min-replicas 0 --max-replicas 1 --cpu 0.25 --memory 0.5Gi \
    --env-vars PORT=8000 CORS_ORIGINS=$UI $EXTRA
done
```
CORS is handled by the services themselves (`CORS_ORIGINS`), not by the Container Apps ingress.

**6. The pipeline's identity.** A user-assigned managed identity with Contributor on this resource group only, trusted by GitHub Actions on `main` (both subject formats):
```bash
az identity create -n mgimenes-github -g rg-mgimenes -l germanywestcentral
PRINCIPAL=$(az identity show -n mgimenes-github -g rg-mgimenes --query principalId -o tsv)
az role assignment create --assignee-object-id "$PRINCIPAL" --assignee-principal-type ServicePrincipal \
  --role Contributor --scope "$(az group show -n rg-mgimenes --query id -o tsv)"
OWNER_ID=$(gh api repos/matheusfunabashi/group-karaoke --jq .owner.id)
REPO_ID=$(gh api repos/matheusfunabashi/group-karaoke --jq .id)
az identity federated-credential create --identity-name mgimenes-github -g rg-mgimenes -n github-main \
  --issuer https://token.actions.githubusercontent.com --audiences api://AzureADTokenExchange \
  --subject "repo:matheusfunabashi/group-karaoke:ref:refs/heads/main"
az identity federated-credential create --identity-name mgimenes-github -g rg-mgimenes -n github-main-ids \
  --issuer https://token.actions.githubusercontent.com --audiences api://AzureADTokenExchange \
  --subject "repo:matheusfunabashi@${OWNER_ID}/group-karaoke@${REPO_ID}:ref:refs/heads/main"
```

**7. GitHub secrets and variables.** The identity's IDs are piped straight from Azure into GitHub; the database passwords were set by `infra/setup-sql.sh` in step 4.
```bash
az identity show -n mgimenes-github -g rg-mgimenes --query clientId -o tsv | gh secret set AZURE_CLIENT_ID
az account show --query tenantId -o tsv | gh secret set AZURE_TENANT_ID
az account show --query id -o tsv | gh secret set AZURE_SUBSCRIPTION_ID
gh variable set PREFIX --body mgimenes
gh variable set RESOURCE_GROUP --body rg-mgimenes
gh variable set UI_STORAGE --body mgimenesui
```

**8. First deploy.** Push to `main`. The GHCR packages `group-karaoke-sessions` and `group-karaoke-recordings` must be public so Azure can pull them (GitHub → Packages → Package settings → Change visibility).

**9. Read access for the professors.**
```bash
for p in amartini@faculty.ie.edu bserra@faculty.ie.edu; do
  az role assignment create --assignee "$p" --role Reader --scope "$(az group show -n rg-mgimenes --query id -o tsv)"
done
```

## Cold starts
The Container Apps scale to zero and the databases pause after an hour without use, so the first request after a quiet period starts a container and wakes its database. That takes up to about a minute, and meanwhile Azure may answer 503. The services connect with retries and backoff, and the UI retries for about a minute while showing "The service is starting up after being idle, please wait..." (ADR-10).

## How to use it
1. Open the UI, pick a song, type your name, choose one of the six pixel-art characters and press **Create**.
2. Copy the **Invite people** link and send it to friends; they open it and **Join** with a name and
   a character (it starts on one nobody has picked yet; two people may pick the same one). The
   session page shows the karaoke room, with everyone who has joined sitting around the table.
3. When everyone has joined, the host presses **Start**. The song's lines are dealt one each, in
   the order people joined (host, second person, third, ... then the host again), so everyone sings
   the same number of short turns. If the lines don't divide evenly, a few neighbouring lines are
   merged into one turn. Nobody can join after the start.
4. Each person presses **Record all my lines**, which opens the karaoke screen (`record.html`).
   Wear headphones and press **Start singing**: the whole song plays, the current line is shown big
   and fills in word by word as the music goes through it, with a countdown and "Sing now!" on your
   lines and "Not your part" on everyone else's. Above the lyrics, whoever has the current line
   stands up in the room with the mic. If the lyrics feel early or late on your headphones, the
   **Lyrics timing** buttons move them by 0.1 s (saved in this browser for that song; the recording itself is
   always cut at the music's times). Only your lines are recorded, each one cut out at
   exactly its start and end. When the song is over, **Done** takes you back. Lines that failed to
   save can be sung again with the same button, which records only the lines still missing.
5. Open **Listen to the finale** at any time; lines not sung yet stay silent. In the room, whoever
   sang the line playing stands up. Every voice is brought up to the same loudness, on top of a
   slightly quieter backing track, so quiet microphones are still heard clearly.

Recording uses the Web Audio API (an `AudioWorklet` captures the microphone) and saves each line as a
WAV file (Chrome, Firefox, Safari and Edge). Browsers only allow microphone access on `localhost` or HTTPS.

The six characters and the room are original pixel art, drawn in code on a `<canvas>` by
`ui/characters.js` (no image files): each one is the same 16 x 18 pixel body with its own hair,
outfit and colours.

Two songs are traditional, public-domain melodies whose backing tracks in `ui/audio/` are
simple synthesized melodies made for this project. *Payphone* (Maroon 5) is copyrighted and is
included only as a non-commercial class demo; it is not licensed for any other use. Its line timings
come from LRCLIB (lrclib.net), a public database of synced lyrics: only the timestamps were taken and
matched in order to the lines in `seed.json`, then shifted by +2.78 s because `ui/audio/payphone.mp3`
is an instrumental remake that starts later than the original: +1.68 s to its first beat (same
110 BPM tempo, measured with ffmpeg), plus 1.1 s (about two beats) measured by ear on the live site.
LRCLIB has no word timing for it, so each word fills in for a share of its line in proportion to
its syllables (a sung syllable is usually one note).
