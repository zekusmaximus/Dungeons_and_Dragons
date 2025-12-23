#!/usr/bin/env python
"""Import file-backed sessions into the SQLite backend."""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import re

from fastapi import HTTPException, status
from pydantic import ValidationError

from service.config import Settings
from service.models import SessionState
from service.storage_backends.sqlite_backend import (
    SQLiteDatabase,
    SQLiteGenericDocStore,
    SQLiteSnapshotStore,
    SQLiteStateStore,
    SQLiteTextLogStore,
    SQLiteTurnStore,
    _json_dumps,
    _fetch_session_id,
    _seed_entropy_from_file,
)


DOC_FILES = {
    "npc_memory": "npc_memory.json",
    "npc_relationships": "npc_relationships.json",
    "mood_state": "mood_state.json",
    "discovery_log": "discovery_log.json",
    "last_discovery": "last_discovery.json",
    "auto_save": "auto_save.json",
}

_SLUG_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


@dataclass
class SessionPaths:
    slug: str
    session_dir: Path
    state_path: Path
    transcript_path: Path
    changelog_path: Path
    turns_dir: Path
    saves_dir: Path
    previews_dir: Path
    character_candidates: List[Path]
    docs: Dict[str, Path]


@dataclass
class ImportResult:
    slug: str
    imported: bool
    skipped: bool = False
    reason: Optional[str] = None
    transcript_count: int = 0
    changelog_count: int = 0
    turn_count: int = 0


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_state(state: Dict) -> SessionState:
    try:
        return SessionState(**state)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"State validation failed: {exc}",
        )


def _normalize_db_path(raw: str, base: Path) -> Path:
    candidate = raw
    if raw.startswith("sqlite:///"):
        candidate = raw.replace("sqlite:///", "", 1)
    elif raw.startswith("file:"):
        candidate = raw[5:]
    path = Path(candidate)
    if not path.is_absolute():
        path = (base / path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _load_json(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    try:
        content = path.read_text(encoding="utf-8")
        if content.startswith("\ufeff"):
            content = content[1:]
        return json.loads(content)
    except Exception as exc:  # pragma: no cover - defensive logging
        print(f"[WARN] Failed to parse {path}: {exc}", file=sys.stderr)
        return None


def _text_lines(path: Path) -> List[str]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as handle:
        return [line.rstrip() for line in handle.readlines() if line.strip()]


def _find_session_paths(source_root: Path, slug: str) -> SessionPaths:
    session_dir = source_root / "sessions" / slug
    data_dir = source_root / "data"
    paths = SessionPaths(
        slug=slug,
        session_dir=session_dir,
        state_path=session_dir / "state.json",
        transcript_path=session_dir / "transcript.md",
        changelog_path=session_dir / "changelog.md",
        turns_dir=session_dir / "turns",
        saves_dir=session_dir / "saves",
        previews_dir=session_dir / "previews",
        character_candidates=[
            session_dir / "character.json",
            data_dir / "characters" / f"{slug}.json",
        ],
        docs={key: session_dir / filename for key, filename in DOC_FILES.items()},
    )
    # Some historical data used snapshots/ instead of saves/
    snapshots_dir = session_dir / "snapshots"
    if not paths.saves_dir.exists() and snapshots_dir.exists():
        paths.saves_dir = snapshots_dir
    return paths


def _iter_turn_files(turns_dir: Path) -> Iterable[Tuple[int, Path]]:
    if not turns_dir.exists():
        return []
    for path in sorted(turns_dir.glob("*.json")):
        try:
            turn_number = int(path.stem)
        except ValueError:
            continue
        yield turn_number, path


def _iter_save_files(saves_dir: Path) -> Iterable[Path]:
    if not saves_dir.exists():
        return []
    return sorted(p for p in saves_dir.glob("*.json") if p.is_file())


def _derive_save_type(save_id: str) -> str:
    return "auto" if save_id.lower().startswith("auto") else "manual"


def _import_docs(db: SQLiteDatabase, session_id: int, docs: Dict[str, Path]) -> None:
    now = _now_iso()
    for doc_key, path in docs.items():
        data = _load_json(path)
        if data is None:
            continue
        payload = data.get("npcs", data) if doc_key == "npc_memory" else data
        db.conn.execute(
            """
            INSERT INTO session_docs (session_id, doc_key, doc_json, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(session_id, doc_key) DO UPDATE
            SET doc_json = excluded.doc_json, updated_at = excluded.updated_at
            """,
            (session_id, doc_key, _json_dumps(payload), now),
        )


def _import_text_entries(db: SQLiteDatabase, session_id: int, stream: str, path: Path) -> int:
    lines = _text_lines(path)
    if not lines:
        return 0
    now = _now_iso()
    for idx, line in enumerate(lines):
        db.conn.execute(
            """
            INSERT INTO text_entries (session_id, stream, entry_id, text, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(session_id, stream, entry_id) DO UPDATE
            SET text = excluded.text, created_at = excluded.created_at
            """,
            (session_id, stream, idx, line, now),
        )
    return len(lines)


def _import_turns(db: SQLiteDatabase, session_id: int, turns_dir: Path) -> int:
    count = 0
    now = _now_iso()
    for turn_number, path in _iter_turn_files(turns_dir):
        payload = _load_json(path)
        if payload is None:
            continue
        db.conn.execute(
            """
            INSERT INTO turns (session_id, turn_number, turn_record_json, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(session_id, turn_number) DO UPDATE
            SET turn_record_json = excluded.turn_record_json, created_at = excluded.created_at
            """,
            (session_id, turn_number, _json_dumps(payload), now),
        )
        count += 1
    return count


def _import_saves(db: SQLiteDatabase, session_id: int, saves_dir: Path) -> int:
    count = 0
    now = _now_iso()
    for path in _iter_save_files(saves_dir):
        payload = _load_json(path) or {}
        save_id = payload.get("save_id") or path.stem
        save_type = payload.get("save_type") or _derive_save_type(save_id)
        created_at = payload.get("timestamp") or now
        db.conn.execute(
            """
            INSERT INTO snapshots (session_id, save_id, save_type, created_at, snapshot_json)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(session_id, save_id) DO UPDATE
            SET snapshot_json = excluded.snapshot_json, created_at = excluded.created_at, save_type = excluded.save_type
            """,
            (session_id, save_id, save_type, created_at, _json_dumps(payload)),
        )
        count += 1
    return count


def _import_character(db: SQLiteDatabase, session_id: int, candidates: Sequence[Path], slug: str) -> None:
    now = _now_iso()
    for path in candidates:
        data = _load_json(path)
        if data is None:
            continue
        data["slug"] = slug
        db.conn.execute(
            """
            INSERT INTO characters (session_id, character_json, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET character_json = excluded.character_json, updated_at = excluded.updated_at
            """,
            (session_id, _json_dumps(data), now),
        )
        return


def _import_previews(db: SQLiteDatabase, session_id: int, previews_dir: Path, state_log_index: int) -> int:
    if not previews_dir.exists():
        return 0
    count = 0
    for path in sorted(previews_dir.glob("*.json")):
        payload = _load_json(path)
        if not payload:
            continue
        preview_id = payload.get("id") or path.stem
        created_at = payload.get("created_at") or _now_iso()
        reserved_indices = payload.get("reserved_indices") or []
        base_log_index = payload.get("base_log_index")
        if base_log_index is None:
            base_log_index = reserved_indices[0] - 1 if reserved_indices else state_log_index
        base_turn = payload.get("base_turn") or payload.get("base_turn_number") or 0
        db.conn.execute(
            """
            INSERT OR REPLACE INTO previews (
                preview_id, session_id, created_at, base_turn_number, base_log_index, reserved_indices_json, payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                preview_id,
                session_id,
                created_at,
                int(base_turn),
                int(base_log_index),
                json.dumps(reserved_indices),
                _json_dumps(payload),
            ),
        )
        count += 1
    return count


def import_session(
    db: SQLiteDatabase,
    settings: Settings,
    paths: SessionPaths,
    overwrite: bool,
    include_previews: bool,
) -> ImportResult:
    if not _SLUG_PATTERN.match(paths.slug):
        return ImportResult(slug=paths.slug, imported=False, reason="invalid slug")
    if not paths.state_path.exists():
        return ImportResult(slug=paths.slug, imported=False, reason="missing state.json")

    existing = db.conn.execute("SELECT id FROM sessions WHERE slug = ?", (paths.slug,)).fetchone()
    if existing:
        if not overwrite:
            return ImportResult(slug=paths.slug, imported=False, skipped=True, reason="already in database")
        with db.conn:
            db.conn.execute("DELETE FROM sessions WHERE slug = ?", (paths.slug,))

    state_data = _load_json(paths.state_path)
    if state_data is None:
        return ImportResult(slug=paths.slug, imported=False, reason="state unreadable")
    validated_state = _validate_state(state_data).model_dump(mode="json")

    transcript_lines = _text_lines(paths.transcript_path)
    changelog_lines = _text_lines(paths.changelog_path)
    turn_files = list(_iter_turn_files(paths.turns_dir))

    now = _now_iso()
    with db.conn:
        cur = db.conn.execute(
            "INSERT INTO sessions (slug, created_at, updated_at) VALUES (?, ?, ?)",
            (paths.slug, now, now),
        )
        session_id = int(cur.lastrowid)
        db.conn.execute(
            """
            INSERT INTO session_state (session_id, state_json, turn_number, log_index, updated_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                session_id,
                _json_dumps(validated_state),
                int(validated_state["turn"]),
                int(validated_state["log_index"]),
                now,
            ),
        )
        _import_character(db, session_id, paths.character_candidates, paths.slug)
        _import_docs(db, session_id, paths.docs)
        transcript_count = _import_text_entries(db, session_id, "transcript", paths.transcript_path)
        changelog_count = _import_text_entries(db, session_id, "changelog", paths.changelog_path)
        turn_count = _import_turns(db, session_id, paths.turns_dir)
        _import_saves(db, session_id, paths.saves_dir)
        if include_previews:
            _import_previews(db, session_id, paths.previews_dir, validated_state["log_index"])

    return ImportResult(
        slug=paths.slug,
        imported=True,
        transcript_count=transcript_count if transcript_lines else 0,
        changelog_count=changelog_count if changelog_lines else 0,
        turn_count=turn_count if turn_files else 0,
    )


def verify_session(
    db: SQLiteDatabase,
    settings: Settings,
    slug: str,
    expected_turns: int,
    expected_transcript: int,
    expected_changelog: int,
) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    try:
        _fetch_session_id(db, slug)
    except Exception:
        errors.append("slug missing after import")
        return False, errors

    state = SQLiteStateStore(db).load_state(settings, slug)
    if state.get("turn") is None or state.get("log_index") is None:
        errors.append("state missing turn/log_index")

    turn_records = SQLiteTurnStore(db).load_turn_records(settings, slug, limit=max(1, expected_turns))
    if expected_turns and len(turn_records) != expected_turns:
        errors.append(f"turn record count mismatch (expected {expected_turns}, got {len(turn_records)})")

    if expected_transcript:
        transcript, _ = SQLiteTextLogStore(db).load_transcript(
            settings, slug, tail=expected_transcript, cursor=None
        )
        if len(transcript) != expected_transcript:
            errors.append(f"transcript count mismatch (expected {expected_transcript}, got {len(transcript)})")

    if expected_changelog:
        changelog, _ = SQLiteTextLogStore(db).load_changelog(
            settings, slug, tail=expected_changelog, cursor=None
        )
        if len(changelog) != expected_changelog:
            errors.append(f"changelog count mismatch (expected {expected_changelog}, got {len(changelog)})")

    # Minimal doc existence smoke test when available
    _ = SQLiteGenericDocStore(db).get_last_discovery_turn(settings, slug)  # noqa: F841
    _ = SQLiteSnapshotStore(db).list_saves(settings, slug, limit=10)  # noqa: F841

    return len(errors) == 0, errors


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate file-backed sessions into SQLite.")
    parser.add_argument("--source", required=True, help="Path to the repository/session root containing sessions/")
    parser.add_argument("--db", required=True, help="SQLite path or sqlite:/// URL")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite sessions that already exist in SQLite")
    parser.add_argument("--include-previews", action="store_true", help="Include previews/ directory contents")
    parser.add_argument("--slugs", help="Comma-separated list of slugs to import (defaults to all found)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen without writing to SQLite")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    source_root = Path(args.source).resolve()
    settings = Settings(repo_root=source_root)

    if not source_root.exists():
        print(f"[ERROR] Source path {source_root} does not exist", file=sys.stderr)
        return 1

    db_path = _normalize_db_path(args.db, source_root)
    print(f"[INFO] Target SQLite DB: {db_path}")
    print(f"[INFO] Source repo: {source_root}")

    sessions_root = source_root / "sessions"
    if not sessions_root.exists():
        print(f"[ERROR] No sessions/ directory under {source_root}", file=sys.stderr)
        return 1

    session_dirs = [p for p in sessions_root.iterdir() if p.is_dir()]
    if args.slugs:
        selected = {slug.strip() for slug in args.slugs.split(",") if slug.strip()}
        session_dirs = [p for p in session_dirs if p.name in selected]
    slugs = sorted(p.name for p in session_dirs)
    if not slugs:
        print("[WARN] No sessions found to import")
        return 0

    if args.dry_run:
        print(f"[DRY-RUN] Would import {len(slugs)} session(s): {', '.join(slugs)}")
        return 0

    db = SQLiteDatabase(db_path)
    entropy_seeded = _seed_entropy_from_file(db, settings)
    print(f"[INFO] Entropy seeded up to index {entropy_seeded}")

    imported = 0
    skipped = 0
    failed = 0
    for slug in slugs:
        paths = _find_session_paths(source_root, slug)
        result = import_session(db, settings, paths, args.overwrite, args.include_previews)
        if result.skipped:
            skipped += 1
            print(f"[SKIP] {slug}: {result.reason}")
            continue
        if not result.imported:
            failed += 1
            print(f"[FAIL] {slug}: {result.reason or 'unknown error'}")
            continue

        ok, errors = verify_session(
            db,
            settings,
            slug,
            expected_turns=result.turn_count,
            expected_transcript=result.transcript_count,
            expected_changelog=result.changelog_count,
        )
        status = "OK" if ok else "VERIFY-FAIL"
        if ok:
            imported += 1
            print(
                f"[{status}] {slug}: turns={result.turn_count}, transcript={result.transcript_count}, changelog={result.changelog_count}"
            )
        else:
            failed += 1
            print(f"[{status}] {slug}: {'; '.join(errors)}")

    print(f"[SUMMARY] imported={imported}, skipped={skipped}, failed={failed}, total={len(slugs)}")
    return 0 if failed == 0 else 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
