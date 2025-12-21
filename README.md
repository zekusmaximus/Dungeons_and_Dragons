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
- Token usage in responses mirrors provider metadata when available; no word-count proxy is used.

## Deterministic data model
- **State:** `service/models.py::SessionState` is the canonical schema. Files live under `sessions/<slug>/state.json`.
- **Turns:** `/sessions/{slug}/turn/preview` validates the current state, computes a JSON diff, and reserves entropy indices without consuming them. `/sessions/{slug}/turn/commit` re-validates against the preview hash/turn, advances `log_index` to consume the reserved entropy, appends transcript/changelog entries, and increments `turn` atomically.
- **Dice:** `dice/entropy.ndjson` supplies deterministic rolls. See `dice/README.md` for mapping rules and extension instructions.
- **Auto-save:** Snapshots land under `sessions/<slug>/saves` and `auto_save.json` via the auto-save endpoints. Snapshot creation (`/auto-save/perform`, `/save`, `/saves/{id}/restore`) requires an active session lock owner to avoid concurrent writes.

## Creating a new session manually
- Use POST `/api/sessions` (or the "New Adventure" button in the Lobby) to copy the `example-rogue` template into a fresh slug. The endpoint resets `turn`/`log_index`, rewrites transcript/changelog placeholders, and clones the template character JSON under the new slug.
- Manual option: Copy `sessions/example-rogue` to a new slug and duplicate `data/characters/example-rogue.json` to `data/characters/<slug>.json`. Reset `state.json` to turn `0`, set starting location/HP, and clear `transcript.md`/`changelog.md` except for an initialization entry.

## Disabled surfaces
- Background job endpoints (`/jobs/*`) are gated and return `501 Not Implemented` to avoid mock entropy.
- The `/events/{slug}` SSE endpoint is intentionally disabled until a deterministic stream is designed.

## Licenses and SRD Notice
Open content follows the SRD and Creative Commons terms documented in `LICENSES/`. Read `NOTICE_SRD.md` for attribution details.
