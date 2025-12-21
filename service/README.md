# Deterministic DM Service

This FastAPI service surfaces the deterministic gameplay data already stored in the repository. It reads session state directly from the existing files so the current file-based workflows stay compatible.

## Quickstart

1. Install dependencies (ideally in a virtual environment):

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
- `DM_SERVICE_LLM_API_KEY` / `DM_SERVICE_LLM_MODEL` / `DM_SERVICE_LLM_BASE_URL`: defaults for LLM calls (overridable via `/llm/config`)

LLM overrides are persisted to `.dm_llm_config.json` in the repo root (git-ignored). Keys are never returned by the API.

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
- `GET /sessions/{slug}/world/faction-clocks` — world project clocks
- `GET /entropy?limit=N` — preview the first N entropy entries
- `GET/POST /llm/config` — view or persist LLM configuration (base URL, model, API key presence)
- `POST /llm/narrate` and `POST /sessions/{slug}/llm/narrate` — contract-aware LLM calls (session route injects character/state context)
- Additional endpoints cover adventure hooks, quests, NPC relationships, discoveries, and auto-save; some job/diff flows remain placeholders.

Container builds are supported via the included `Dockerfile`:

```bash
docker build -t dm-service -f service/Dockerfile .
```

## Frontend pairing

The React/Vite UI in `/ui` proxies `/api/*` to this service when you run `npm run dev`. Start this FastAPI app on port `8000` first to avoid proxy errors.
