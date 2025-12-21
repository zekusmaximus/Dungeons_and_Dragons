# Repo-as-Game: Solo D&D-Style Adventure

This repository is a deterministic, file-backed solo D&D experience. A FastAPI backend reads/writes the same session files a human DM would use, and a React/Vite UI surfaces them with a `/api` proxy. The contract for how the Dungeon Master operates is defined in `PROTOCOL.md`, and all randomness is pulled from `dice/entropy.ndjson` so play is reproducible.

## First playable session (clone → play)

1. **Create a virtualenv and install the service**
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r service/requirements.txt
   ```
2. **Run the FastAPI backend (port 8000)**
   ```bash
   uvicorn service.app:app --reload --port 8000
   ```
   Optional env vars:
   - `DM_SERVICE_LLM_API_KEY` / `DM_SERVICE_LLM_MODEL` / `DM_SERVICE_LLM_BASE_URL` to set defaults.
3. **Start the UI (port 5173, proxied to `/api`)**
   ```bash
   cd ui
   npm install
   npm run dev
   ```
4. **Play using the shipped session**
   - Open `http://localhost:5173`.
   - Pick **example-rogue** in the Lobby.
   - Open **Settings → LLM Configuration** to POST `/api/llm/config` with your API key if you did not set an env var. Keys are stored locally in `.dm_llm_config.json` (git-ignored).
   - The UI reads `turn.md` and `state.json` from `sessions/example-rogue` and will use `/api/llm/narrate` for story beats once a key is present.

## LLM configuration
- Backend defaults are read from environment variables; POST `/api/llm/config` persists overrides to `.dm_llm_config.json` in the repo root (not committed).
- The UI never echoes your key; it only reports whether one is configured and which base URL/model are active.
- Provider calls are sent to `{base_url}/chat/completions` with a system prompt derived from `PROMPTS/dm_v3_contract.md` plus the current session context.

## Deterministic data model
- **State:** `service/models.py::SessionState` is the canonical schema. Files live under `sessions/<slug>/state.json`.
- **Dice:** `dice/entropy.ndjson` supplies deterministic rolls. See `dice/README.md` for mapping rules and extension instructions.
- **Auto-save:** Snapshots land under `sessions/<slug>/saves` and `auto_save.json` via the auto-save endpoints.

## Creating a new session manually
Copy `sessions/example-rogue` to a new slug and duplicate `data/characters/example-rogue.json` to `data/characters/<slug>.json`. Reset `state.json` to turn `0`, set starting location/HP, and clear `transcript.md`/`changelog.md` except for an initialization entry.

## Licenses and SRD Notice
Open content follows the SRD and Creative Commons terms documented in `LICENSES/`. Read `NOTICE_SRD.md` for attribution details.
