# Deterministic DM Service

This FastAPI service surfaces the deterministic gameplay data already stored in the repository. It reads session state directly from the existing files so the current file-based workflows stay compatible.

## Quickstart

1. Install dependencies:

```bash
pip install -r service/requirements.txt
```

2. Run the service:

```bash
uvicorn service.app:app --reload --port 8000
```

The service defaults to using the repository root for data. Override paths with environment variables:

- `DM_SERVICE_REPO_ROOT`: root directory containing sessions, dice, and worlds (defaults to repo root)
- `DM_SERVICE_SESSIONS_DIR`: relative path to sessions folder (default: `sessions`)
- `DM_SERVICE_DICE_FILE`: relative path to entropy file (default: `dice/entropy.ndjson`)
- `DM_SERVICE_TRANSCRIPT_TAIL`: default number of transcript lines to return
- `DM_SERVICE_CHANGELOG_TAIL`: default number of changelog entries to return

## API surface

- `GET /health` — service status
- `GET /sessions` — list available session slugs
- `GET /sessions/{slug}/state` — full state JSON
- `GET /sessions/{slug}/transcript?tail=N` — last N lines from transcript
- `GET /sessions/{slug}/changelog?tail=N` — last N changelog entries
- `GET /sessions/{slug}/quests` — quests pulled from state
- `GET /sessions/{slug}/npc-memory` — NPC impressions for the session
- `GET /sessions/{slug}/world/factions` — faction standings for the session world
- `GET /sessions/{slug}/world/timeline` — world timeline entries
- `GET /entropy?limit=N` — preview the first N entropy entries

Container builds are supported via the included `Dockerfile`:

```bash
docker build -t dm-service -f service/Dockerfile .
```
