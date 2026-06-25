# CLAUDE.md

Guidance for AI assistants (and humans) working in this repository. Read this
first, then `PROTOCOL.md` if you will be acting as the Dungeon Master.

## What this project is

A **deterministic, file-backed solo D&D experience** where an AI plays the
Dungeon Master. A FastAPI backend enforces deterministic state updates and
entropy-based dice rolls; a React/Vite UI serves the player table, character
wizard, and journal. The repo *is* the game: session state, transcripts, and
campaign data all live as files (or in SQLite) that a human or AI DM reads and
writes the same way.

Two layers coexist:
- **Service layer** (`service/`, `ui/`) — the FastAPI + React app that most
  development targets. Runs as a single process: UI at `/`, API at `/api`.
- **Tooling/contract layer** (`tools/`, `PROTOCOL.md`, `PROMPTS/`, top-level
  game-content dirs) — CLI procedures and the rules an AI DM must follow when
  mutating a session directly.

Core principles, in priority order:
1. **Determinism** — all randomness comes from `dice/entropy.ndjson`, consumed
   in order and recorded by index. Never use `random`/`Math.random()`. Play
   must be reproducible.
2. **SRD-only content** — classes, spells, monsters, rules are SRD/Creative
   Commons only. No homebrew, no trademarked IP. See `LICENSES/`.
3. **Auditability** — every state change is logged to `changelog.md` with the
   entropy indices it consumed; the DM controls state, the player submits intent.

## Repository layout

| Path | Purpose |
| --- | --- |
| `service/` | FastAPI backend. `app.py` holds all routes; `models.py` is the canonical Pydantic schema; `storage.py` + `storage_backends/` abstract file vs sqlite. |
| `ui/` | React 19 + Vite + TypeScript frontend. `src/pages/` (PlayerStart, CharacterWizard, PlayerTable), `src/components/`, `src/App.tsx` (hand-rolled path router). |
| `desktop/` | Electron wrapper that bundles backend + UI into a Windows EXE (NSIS). |
| `tools/` | Deterministic CLI procedures (explore, loot, downtime, encounters, rules index/search, validation, migrations). |
| `schemas/` | JSON Schemas for state, character, quest, encounter, loot, hexmap, table, log entries. |
| `PROMPTS/` | DM contracts and style guides. `dm_v3_contract.md` is the current system prompt source. |
| `data/` | SRD content + seed assets: `characters/`, `monsters/`, `rules/`, `spells/`, `terrain/`. |
| `dice/` | `entropy.ndjson` (the deterministic roll source), `verify_dice.py`, mapping rules in `README.md`. |
| `sessions/<slug>/` | Per-session state: `state.json`, `transcript.md`, `changelog.md`, `turn.md`, `journal.md`, `character.json`, `LOCK`, `saves/`, `snapshots/`. |
| `worlds/<world>/` | World content: `factions.json`, `faction_clocks.json`, `timeline.json`, `rumors.json`, `hexmap.json`, `maps/`, `npcs/`. |
| `tests/` | Pytest suite (parametrized over both storage backends). |
| Game-content dirs | `combat/`, `mysteries/`, `locations/`, `factions/`, `quests/`, `narrative/`, `exploration/`, `downtime/`, `party/`, `meta/`, `rumors/`, `timeline/`, `rules_index/` — JSON data + engine scripts used by v3 procedures. |
| `archive/` | Unmaintained Docker support; do not rely on it. |
| `dm.sqlite` | Default committed SQLite DB (sqlite is the default backend). |

Key docs: `README.md` (run instructions), `QUICKSTART.md`, `INSTRUCTION_MANUAL.md`
(game manual + desktop build), `ENGINE.md` (v2 procedure engine), `MIGRATION.md`
(file→sqlite), `PROTOCOL.md` (DM operating contract).

## Development workflows

### Run the app (combined server — UI at `/`, API at `/api`)
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r service/requirements.txt
npm --prefix ui install
npm --prefix ui run build           # build UI once; required for `/` to serve
uvicorn service.app:app --host 0.0.0.0 --port 8000
```
The exported ASGI `app` mounts the API under `/api` and serves the built UI
(`ui/dist`) at `/`, with an SPA fallback for client-side routes.

### Dev mode (hot reload)
- Backend: `uvicorn service.app:app --reload --port 8000`
- Frontend: `VITE_API_BASE_URL=http://localhost:8000 npm run dev --prefix ui`
  then open `http://localhost:5173` (Vite proxies `/api`).

### Tests
```bash
pytest -q                              # backend; conftest parametrizes file + sqlite backends
npm --prefix ui test                   # UI unit tests (jest + Testing Library)
npm --prefix ui run test:e2e           # Playwright e2e
python tools/sanity_check.py           # indexes rules, checks monsters, creates a demo session
```
When you change backend behavior, run `pytest -q` — the `repo_root` fixture runs
each test against **both** the `file` and `sqlite` backends, so storage-specific
regressions are caught.

### Build artifacts
- UI: `npm --prefix ui run build` (`tsc && vite build`).
- Desktop EXE: `npm --prefix desktop install && npm --prefix desktop run dist`.

## The turn lifecycle (most important backend flow)

State changes are **two-phase** to keep entropy consumption atomic and
auditable. When working on turn/state code, preserve this contract:

1. `POST /api/sessions/{slug}/turn/preview` — validates current state, computes a
   JSON diff, and *reserves* entropy indices without consuming them. Returns a
   preview id + entropy plan.
2. `POST /api/sessions/{slug}/turn/commit` — re-validates against the preview
   hash/turn, advances `log_index` to *consume* the reserved entropy, appends
   transcript/changelog entries, and increments `turn` atomically.

Player-facing flow wraps this: `POST /api/sessions/{slug}/player/turn` takes
plain player intent, calls the LLM DM (which returns a `state_patch` +
`dice_expressions` per `PROMPTS/dm_v3_contract.md`), applies the patch through
preview/commit, syncs it into the character sheet, and returns narration +
suggestions. The player submits **intent only**; the DM owns all state mutation.

`service/models.py::SessionState` is the canonical state schema (mirrored by
`schemas/state.schema.json`). `Character`, `DMNarration`, `TurnRecord`, and
`RollRequest` are the other load-bearing models.

## Deterministic dice — non-negotiable

- `dice/entropy.ndjson` is NDJSON: `{"i":1234,"d20":[...],"d100":[...],"bytes":"..."}`.
- Consume the next unused line; pop from `d20`/`d100`. For die size `X`, map a
  d20 value `n` as `1 + ((n - 1) % X)`.
- **Never reuse an index.** Record every consumed `i` in `changelog.md` (and the
  commit message when committing as the DM).
- If entropy is exhausted: `python dice/verify_dice.py --extend N`.
- See `PROTOCOL.md` "Deterministic Dice Rules" and `dice/README.md` for details.

## Acting as the DM directly (file/CLI mode)

If you mutate a session *without* going through the service, follow `PROTOCOL.md`
exactly. Summary:
- **Scope allowlist** — only touch `sessions/<slug>/*`, `data/characters/<slug>.json`,
  `data/monsters/*`, `data/rules/*`, `PROMPTS/*`, `schemas/*`, `dice/*`.
- **Locking** — check/claim `sessions/<slug>/LOCK` before writing; release it after.
- **Per-turn outputs** — update `state.json`, append narration to `transcript.md`,
  append a one-line JSON entry to `changelog.md` (per `schemas/log_entry.schema.json`),
  rewrite `turn.md` with the next branch prompt.
- **Validate** with `tools/validate.py`; on schema error, revert the offending edit
  and write a diagnostic to `turn.md`.
- v2 procedures (explore/quest/encounter/loot/downtime/rules) and v3 procedures
  (factions, rumors, timeline, mysteries, locations, combat stances, journaling,
  snapshots) each have their own CLI entry point and commit tag — see PROTOCOL
  "v2/v3 Procedures". Character creation, level-up, and rest each have a documented
  mode in `PROTOCOL.md` that requires explicit player choices (never auto-pick).

### Commit message format (DM turns)
```
dm(<slug>): <scene summary>; rolls=[<expr>=<result>@<entropy_index> ...]; hp:-3 goblin arrow; loc=Gate-01
```
Procedure commits use bracket tags, e.g. `[travel:hex]`, `[quest:init]`,
`[encounter:resolve]`, `[faction:update]`, `[scene:frame]`, `[character:create]`,
`[level-up]`, `[rest:long]`. Full tag list in `PROTOCOL.md`.

## Configuration & environment

| Variable | Purpose |
| --- | --- |
| `STORAGE_BACKEND` | `file` or `sqlite` (factory default `file`; README notes sqlite as the product default). |
| `SQLITE_PATH` / `DATABASE_URL` | SQLite location (default `dm.sqlite` in repo root). |
| `DM_API_KEY` | When set, `X-API-Key` header is required on all mutating routes and `/api/llm/*`. Read-only routes stay open. |
| `DM_SERVICE_DATA_ROOT` | Store sessions/assets outside the repo (desktop use). |
| `DM_SERVICE_SEED_ROOT` | Seed source for first-run copy. |
| `DM_SERVICE_LLM_API_KEY` / `_MODEL` / `_BASE_URL` | LLM defaults; overridable via `POST /api/llm/config` (persisted to git-ignored `.dm_llm_config.json`). |
| `VITE_API_BASE_URL` | UI build/dev API base (default `/api`). |

Config is centralized in `service/config.py::Settings` (env prefix
`DM_SERVICE_`). LLM provider calls go to `{base_url}/chat/completions` with a
system prompt derived from `PROMPTS/dm_v3_contract.md`. The API never echoes the
LLM key — only whether one is configured.

## Conventions & gotchas

- **API path prefix:** routes are declared in `service/app.py` without `/api`
  (e.g. `@app.get("/sessions")`), then mounted under `/api`. The auth middleware
  strips a leading `/api` before matching protected prefixes.
- **Pydantic aliases:** reserved words use trailing-underscore fields with
  aliases (`class_`/`class`, `str_`/`str`, `int_`/`int`). Use `populate_by_name`.
- **Storage abstraction:** never read/write session files directly from route
  handlers — go through the `StorageBackend` interface
  (`service/storage_backends/`) so both backends stay in sync. New persistence
  must work for file *and* sqlite, and `tools/migrate_to_sqlite.py` should know
  how to ingest it.
- **Disabled surfaces:** `/api/jobs/*` return `501` (no mock entropy) and
  `/api/events/{slug}` SSE is intentionally off until a deterministic stream
  exists. Don't wire these up casually.
- **Frontend routing** is a hand-rolled `pathname` parser in `App.tsx`
  (`/`, `/character/<slug>`, `/play/<slug>`, `/advanced`) — there is no router
  library. Player Mode is the default landing page; `/advanced` exposes the
  deterministic dashboard.
- **Inventory edits** write full arrays, never partial diffs (PROTOCOL rule).
- `.dm_llm_config.json`, `.env`, and `__pycache__` are git-ignored.

## Git workflow

- Active feature branch: `claude/claude-md-docs-wna1cy`. Develop and push there;
  do not push to `main` without explicit permission.
- Do **not** open a pull request unless explicitly asked.
- Push with `git push -u origin <branch>`; retry network failures with
  exponential backoff.
