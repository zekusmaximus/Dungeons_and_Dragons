# Migrating file-backed sessions into SQLite

This repository now supports a SQLite storage backend. Use `tools.migrate_to_sqlite` to ingest existing on-disk sessions and dice entropy into a standalone SQLite database.

## Usage

Primary (module) invocation:
```
python -m tools.migrate_to_sqlite --source <path_to_repo_or_export> --db <sqlite_path_or_url>
```

Script invocation (also supported):
```
python tools/migrate_to_sqlite.py --source <path_to_repo_or_export> --db <sqlite_path_or_url>
```

Required arguments:
- `--source`: Path containing `sessions/`, `data/characters/`, and optional `dice/entropy.ndjson`.
- `--db`: SQLite destination file, or URL like `sqlite:///dm.sqlite`.

Common flags:
- `--overwrite`: Replace an existing session in the DB (deletes the slug and re-imports).
- `--slugs slug1,slug2`: Only import specific slugs (defaults to all directories in `sessions/`).
- `--dry-run`: Show which sessions would be imported without writing to the database.
- `--include-previews`: Also import `sessions/<slug>/previews/*.json` (normally skipped).

## Examples

Import everything from the current repo into a local DB:
```
python -m tools.migrate_to_sqlite --source . --db dm.sqlite
```

Import a specific session, overwriting any existing copy:
```
python -m tools.migrate_to_sqlite --source . --db dm.sqlite --slugs hook-002 --overwrite
```

Dry-run to see what would happen:
```
python -m tools.migrate_to_sqlite --source /exports/dm --db sqlite:///dm.sqlite --dry-run
```

Include previews (rarely needed):
```
python -m tools.migrate_to_sqlite --source . --db dm.sqlite --include-previews
```

## What gets imported

- `sessions/<slug>/state.json` → `sessions` + `session_state` tables (turn/log preserved).
- `character.json` (or `data/characters/<slug>.json` fallback) → `characters` table.
- `transcript.md` and `changelog.md` → `text_entries` (same entry ordering as file backend).
- `turns/*.json` → `turns` table keyed by filename turn number.
- Session docs (`npc_memory`, `npc_relationships`, `mood_state`, `discovery_log`, `last_discovery`, `auto_save`) → `session_docs`.
- `saves/*.json` (and legacy `snapshots/`) → `snapshots` table (`save_id` from filename, `save_type` auto/manual by prefix).
- `dice/entropy.ndjson` (if present) → `entropy` table (seeded once).
- `previews/*.json` are ignored unless `--include-previews` is set.

## Idempotency and verification

- Without `--overwrite`, existing slugs in SQLite are skipped.
- With `--overwrite`, the slug and all dependent rows are deleted, then re-imported.
- After each import the script re-reads data through the SQLite backend and checks:
  - slug exists,
  - `state.turn` and `state.log_index` are present,
  - turn count matches the number of turn files,
  - transcript and changelog entry counts match file lines (blank lines are ignored, consistent with the API).

The script prints per-slug results and a final summary. Use the `--dry-run` flag first if you want a preview of the work to be done.
