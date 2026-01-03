# Repo-as-Game: Solo D&D-Style Adventure

This repository is a deterministic, file-backed solo D&D experience. A FastAPI backend reads/writes the same session files a human DM would use, and a React/Vite UI is served at `/` with the API mounted at `/api`. The contract for how the Dungeon Master operates is defined in `PROTOCOL.md`, and all randomness is pulled from `dice/entropy.ndjson` so play is reproducible.

New here? Start with `QUICKSTART.md`.

## Single-process quickstart (UI + API)
1. Install backend deps
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r service/requirements.txt
   ```
2. Build the UI once
   ```bash
   npm --prefix ui install
   npm --prefix ui run build
   ```
3. Run the combined server (serves UI at `/`, API at `/api`)
   ```bash
   uvicorn service.app:app --host 0.0.0.0 --port 8000
   ```

Key environment variables:
- `STORAGE_BACKEND` (`file` | `sqlite`, default sqlite)
- `SQLITE_PATH` / `DATABASE_URL` (default `dm.sqlite` in the repo root)
- `DM_API_KEY` (optional; when set, `X-API-Key` is required on mutating + LLM routes)
- `VITE_API_BASE_URL` for UI builds and the dev proxy (default `/api`)
- `DM_SERVICE_LLM_API_KEY` / `DM_SERVICE_LLM_MODEL` / `DM_SERVICE_LLM_BASE_URL` to set LLM defaults

## Dev mode (hot reload)
- Backend: `uvicorn service.app:app --reload --port 8000`
- Frontend: `VITE_API_BASE_URL=http://localhost:8000 npm run dev --prefix ui` (proxy stays on `/api`)
- Open `http://localhost:5173`

## Docker
Docker support is archived under `archive/` and not maintained. Use dev mode or the desktop build instead.

## Troubleshooting
- UI loads but API calls 404: verify the FastAPI service is running and reachable; confirm the UI build/proxy points at `/api` (or set `VITE_API_BASE_URL` for an alternate host).
- API 401 unauthorized: check whether `DM_API_KEY` is set in the environment; if so, include `X-API-Key` on all mutating routes and `/api/llm/*`.
- SQLite path/volume issues: ensure `SQLITE_PATH`/`DATABASE_URL` points to a writable location (e.g., `/data/dm.sqlite` in Docker) and that the volume is mounted with write permissions.

## Player Mode Quickstart
Player Mode is now the default landing page.
1. Run the combined server (or `docker run` above).
2. Open `http://localhost:8000` and choose **Start new adventure**. A fresh session is created from the template you enter (default `example-rogue`).
3. The Character Wizard walks through concept, abilities (standard array by default; roll/point-buy optional), proficiencies, equipment, and review. Pick a starting hook on the final step. Submitting persists the hero to `sessions/<slug>/character.json`, updates session state, and triggers the opening scene.
4. Play at the **Player Table**: free-text chat with the DM, suggestion buttons beneath the input, character sheet panel (AC/HP/stats/gear/spells), and a journal with quests, discoveries, and the latest recap.
5. Need the deterministic controls? Click the small **Advanced** link to open the existing dashboard at `/advanced`.

## Minimal auth
- When `DM_API_KEY` is unset: open dev mode, no auth required.
- When `DM_API_KEY` is set: send `X-API-Key: <value>` on all POST/PUT/PATCH/DELETE calls and on `/api/llm/*` (config + narration). Read-only routes stay open.

## Smoke test (expected to work locally)
```bash
npm --prefix ui run build
uvicorn service.app:app --host 0.0.0.0 --port 8000 &
SERVER_PID=$!
sleep 2
curl -f http://localhost:8000/api/health
curl -f -X POST http://localhost:8000/api/sessions -H "Content-Type: application/json" -d '{"slug":"demo","template_slug":"example-rogue"}'
preview_id=$(curl -sf -X POST http://localhost:8000/api/sessions/demo/turn/preview -H "Content-Type: application/json" -d '{"response":"look around","state_patch":{"location":"camp"},"transcript_entry":"peek","dice_expressions":[]}' | python - <<'PY'
import json,sys
print(json.load(sys.stdin)["id"])
PY
)
curl -f -X POST http://localhost:8000/api/sessions/demo/turn/commit -H "Content-Type: application/json" -d "{\"preview_id\":\"$preview_id\"}"
kill $SERVER_PID
```

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
