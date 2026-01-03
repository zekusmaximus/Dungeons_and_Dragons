# Dungeons & Dragons Game Manual

## Introduction

This project delivers a deterministic solo D&D experience where the AI is the DM. A FastAPI backend enforces deterministic state updates and entropy-based rolls, while a React/Vite UI provides the player table, character sheet, and journaling.

Key pillars:
- Deterministic dice mechanics using `dice/entropy.ndjson`
- AI DM produces explicit `state_patch` and `dice_expressions` for each turn
- File-based campaign storage for easy backups and auditability
- SRD-only classes, spells, monsters, and rules (no homebrew)

## Install and Run

### Desktop App (Windows EXE)
Build a Windows installer with the bundled backend and UI.

Prerequisites (build machine):
- Node.js 18+
- Python 3.10+ on PATH (for packaging only)

Build steps:
1) Build the UI:
```
npm --prefix ui install
npm --prefix ui run build
```
2) Install desktop build dependencies:
```
npm --prefix desktop install
```
3) Build the Windows EXE (NSIS):
```
npm --prefix desktop run dist
```
Output: `desktop/dist/`

First run:
- The app asks for a data folder. This is where all sessions, character data, and entropy live.
- The backend seeds the folder with required assets on first run.

### Developer Mode (UI + API)
1) Install backend deps:
```
python -m venv .venv
.\.venv\Scripts\activate
pip install -r service/requirements.txt
```
2) Build the UI once:
```
npm --prefix ui install
npm --prefix ui run build
```
3) Start the combined server:
```
uvicorn service.app:app --host 0.0.0.0 --port 8000
```
4) Open `http://localhost:8000`

Optional: run the Vite dev server separately:
```
VITE_API_BASE_URL=http://localhost:8000 npm run dev --prefix ui
```

### Data Root (non-repo storage)
You can point the backend at any folder:
- `DM_SERVICE_DATA_ROOT`: data folder to store sessions and assets.
- `DM_SERVICE_SEED_ROOT`: source folder to seed assets from (defaults to the repo).

Example:
```
set DM_SERVICE_DATA_ROOT=D:\SoloDM\Data
uvicorn service.app:app --port 8000
```

## Gameplay Loop

### Character Creation
- Use the Character Wizard to roll abilities from entropy and select an SRD class.
- A character is saved under `sessions/<slug>/character.json` and `data/characters/<slug>.json`.
- Starting scene is generated after creation via `/sessions/{slug}/player/opening`.

### Turns and State Updates
- The AI DM returns JSON containing:
  - `state_patch`: updates to session state (HP, inventory, conditions, etc)
  - `dice_expressions`: rolls to consume from `dice/entropy.ndjson`
- The backend commits `state_patch` and reserves the entropy indices atomically.
- State updates applied via `state_patch` are also synced into the session character sheet so the UI reflects HP, inventory, level, spells, and abilities changes.
- The player only submits intent; the DM controls state updates.

### Rolls
- All random outcomes consume entropy.
- Player roll requests (ability checks, saves, attacks) are logged and attached to the next committed turn.

## Data Model

- Session state: `sessions/<slug>/state.json` (validated by `schemas/state.schema.json`)
- Transcript and changelog: `sessions/<slug>/transcript.md`, `sessions/<slug>/changelog.md`
- Deterministic entropy: `dice/entropy.ndjson`
- Characters: `sessions/<slug>/character.json` and `data/characters/<slug>.json`

## Configuration

Key environment variables:
- `DM_SERVICE_DATA_ROOT`: data folder for sessions and assets
- `DM_SERVICE_SEED_ROOT`: seed folder for first-run copy
- `STORAGE_BACKEND`: `file` or `sqlite`
- `SQLITE_PATH`: sqlite db path (if using sqlite)
- `DM_API_KEY`: optional API key gate for writes
- `DM_SERVICE_LLM_API_KEY`: LLM API key
- `DM_SERVICE_LLM_MODEL`: default model
- `DM_SERVICE_LLM_BASE_URL`: provider base URL

## FAQ

### Can I play offline?
Yes. All data is local. Only LLM narration requires network access.

### How do I back up my campaign?
Back up the data folder you selected. All sessions and characters live there.

### What if the UI loads but the DM is silent?
Check that the LLM key is configured via `/api/llm/config` or `DM_SERVICE_LLM_API_KEY`.

For more detail, see `README.md`, `ENGINE.md`, and `PROTOCOL.md`.
