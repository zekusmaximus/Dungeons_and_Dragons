# Dungeons & Dragons Game Manual

## Introduction

This project delivers a deterministic, file-backed solo D&D experience. A FastAPI backend reads and writes the same session files a human DM would touch, and a React/Vite UI consumes the API via a `/api` proxy. Dice entropy is pre-generated, gameplay contracts live in `PROTOCOL.md`, and every turn is auditable in the repo.

Key pillars:
- Deterministic dice mechanics using `dice/entropy.ndjson`
- File-based campaign storage for easy backups and versioning
- Web UI for browsing sessions and driving turns
- Modular backend that can be extended with additional tools

## Getting Started

### Prerequisites
- Python 3.8+ for the backend service
- Node.js and npm for the frontend UI
- Git for version control (optional but recommended)

### Installation
1. Clone or download the project repository.
2. Navigate to the project root directory.
3. Install backend dependencies (virtual environment recommended):
   ```
   pip install -r service/requirements.txt
   ```
4. Install frontend dependencies:
   ```
   cd ui
   npm install
   cd ..
   ```

### Running the Application
1. Start the backend service from the project root directory (port `8000`):
   ```
   uvicorn service.app:app --reload --port 8000
   ```
2. In a separate terminal, start the frontend UI (proxies `/api` to the backend):
   ```
   cd ui
   npm run dev
   ```
3. Open your web browser and navigate to `http://localhost:5173` (or the port shown by Vite).

### Creating Your First Session
1. Launch the UI to see the Lobby component.
2. Select the shipped **example-rogue** session to begin play. The "New Adventure" button now POSTs `/api/sessions` to clone the template into a fresh slug and refreshes the session list automatically.
3. Manual alternative: copy `sessions/example-rogue` to a new slug, duplicate `data/characters/example-rogue.json` to `data/characters/<slug>.json`, reset `state.json` to turn `0`, and clear `transcript.md`/`changelog.md` except for initialization text.
4. Configure your LLM key from the Narrative Dashboard → Settings → LLM Configuration, or set the `DM_SERVICE_LLM_API_KEY` environment variable before starting the backend. The POST `/api/llm/config` endpoint persists overrides to `.dm_llm_config.json` and never echoes your key.

## Gameplay Mechanics

### Character Data
- Characters live in `data/characters/<slug>.json`.
- Session state follows `service/models.py::SessionState` and is stored in `sessions/<slug>/state.json`.

### Dice
- Deterministic dice rolls come from `dice/entropy.ndjson`.
- Use `dice/README.md` and `dice/verify_dice.py` to inspect or extend the pool.

### Exploration & Narrative
- The UI surfaces the current scene from `turn.md` and state information from `state.json`.
- `/sessions/{slug}/llm/narrate` injects session and character context into the LLM call.

### Turn Preview & Commit
- `/sessions/{slug}/turn/preview` validates the current state, computes a diff, and reserves deterministic entropy indices without advancing `log_index`.
- `/sessions/{slug}/turn/commit` re-checks the preview base hash/turn, consumes the reserved indices, appends transcript/changelog entries, and increments `turn` atomically. Stale previews return `409 Conflict`.

### Downtime & Jobs
- Jobs endpoints (explore/loot/downtime/etc.) are gated with `501 Not Implemented`; run the CLI tools manually under a session lock if needed.

## UI Components

### Lobby
Lists existing campaigns. The "New Adventure" button clones the template session via POST `/api/sessions` and opens it immediately.

### Narrative Dashboard
Shows current scene text, quick actions, transcript/changelog panels, and links to map and character views.

### Turn Console
Manages lock claim/release and preview/commit calls to the backend turn endpoints.

### LLM Configuration
Available from the Narrative Dashboard settings modal. Persists base URL/model and key presence to `.dm_llm_config.json` (git-ignored) and never returns the key in responses.

## Advanced Features

### File-Based Storage
- Sessions live under `sessions/`, characters under `data/characters/`, and supporting data under `worlds/` and `data/`.
- Version control is encouraged for auditing and backup.

### Snapshots and Journaling
- Auto-save endpoints write snapshots beneath `sessions/<slug>/saves` and `auto_save.json`.
- `transcript.md` and `changelog.md` remain the audit trail for turns.

### API and Extensibility
- FastAPI endpoints are defined in `service/app.py`; extend or gate features there.
- Docker builds are available via `service/Dockerfile`.

## FAQs

### How do I roll dice?
Dice rolls are deterministic and pulled from `dice/entropy.ndjson`; the next unused entry is consumed for each roll.

### Can I play offline?
Yes. All data is local; only the LLM endpoint requires internet access.

### How do I back up my campaign?
Copy the repo or use Git. Key gameplay files live under `sessions/<slug>/` and `data/characters/`.

### What if an API call fails?
Check the FastAPI logs. Verify that the backend is running on port `8000` and the UI proxy is targeting `/api`. Ensure session files exist and follow the expected schema.

For more detail, see `README.md`, `service/README.md`, `ENGINE.md`, and `PROTOCOL.md`.
