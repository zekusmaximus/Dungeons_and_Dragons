import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, status

from .. import storage
from ..config import Settings
from ..models import LockInfo, PreviewRequest, RollRequest, RollResult, SessionState
from .interfaces import (
    CharacterStore,
    EntropyStore,
    GenericDocStore,
    SessionStore,
    SnapshotStore,
    StateStore,
    StorageBackend,
    TextLogStore,
    TurnStore,
    WorldStore,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_slug(slug: str) -> None:
    if not storage._SLUG_PATTERN.match(slug):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid session slug. Use letters, numbers, hyphens, or underscores.",
        )


def _json_dumps(payload: Any) -> str:
    return json.dumps(payload, indent=2, default=str)


def _resolve_db_path(settings: Settings) -> Path:
    raw = os.getenv("DATABASE_URL") or os.getenv("SQLITE_PATH")
    candidate = getattr(settings, "database_url", None)
    if raw is None and candidate:
        raw = candidate
    if raw:
        if raw.startswith("sqlite:///"):
            raw = raw.replace("sqlite:///", "", 1)
        elif raw.startswith("file:"):
            raw = raw[5:]
        path = Path(raw)
    else:
        root = settings.data_root or settings.repo_root
        path = root / "dm.sqlite"
    if not path.is_absolute():
        root = settings.data_root or settings.repo_root
        path = root / path
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


class SQLiteDatabase:
    def __init__(self, path: Path):
        self.path = path
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slug TEXT UNIQUE NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS session_state (
                session_id INTEGER PRIMARY KEY,
                state_json TEXT NOT NULL,
                turn_number INTEGER NOT NULL,
                log_index INTEGER NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS previews (
                preview_id TEXT PRIMARY KEY,
                session_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                base_turn_number INTEGER NOT NULL,
                base_log_index INTEGER NOT NULL,
                reserved_indices_json TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS text_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                stream TEXT NOT NULL CHECK(stream IN ('transcript','changelog')),
                entry_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(session_id, stream, entry_id),
                FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS turns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                turn_number INTEGER NOT NULL,
                turn_record_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(session_id, turn_number),
                FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS characters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                character_json TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(session_id),
                FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS session_docs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                doc_key TEXT NOT NULL,
                doc_json TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(session_id, doc_key),
                FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS entropy (
                entropy_index INTEGER PRIMARY KEY,
                entropy_json TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                save_id TEXT NOT NULL,
                save_type TEXT NOT NULL,
                created_at TEXT NOT NULL,
                snapshot_json TEXT NOT NULL,
                UNIQUE(session_id, save_id),
                FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS session_locks (
                session_id INTEGER PRIMARY KEY,
                owner TEXT NOT NULL,
                ttl INTEGER NOT NULL,
                claimed_at TEXT NOT NULL,
                FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
            );
            """
        )


def _fetch_session_row(db: SQLiteDatabase, slug: str) -> sqlite3.Row:
    _validate_slug(slug)
    row = db.conn.execute("SELECT * FROM sessions WHERE slug = ?", (slug,)).fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown session '{slug}'")
    return row


def _fetch_session_id(db: SQLiteDatabase, slug: str) -> int:
    return int(_fetch_session_row(db, slug)["id"])


def _fetch_state_row(db: SQLiteDatabase, session_id: int) -> sqlite3.Row:
    row = db.conn.execute(
        "SELECT state_json, turn_number, log_index FROM session_state WHERE session_id = ?", (session_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="State not found for session")
    return row


def _next_entry_id(db: SQLiteDatabase, session_id: int, stream: str) -> int:
    row = db.conn.execute(
        "SELECT MAX(entry_id) as max_id FROM text_entries WHERE session_id = ? AND stream = ?",
        (session_id, stream),
    ).fetchone()
    current = row["max_id"]
    return (int(current) + 1) if current is not None else 0


def _current_log_indices(db: SQLiteDatabase, session_id: int) -> Dict[str, int]:
    result: Dict[str, int] = {}
    for stream in ("transcript", "changelog"):
        row = db.conn.execute(
            "SELECT MAX(entry_id) as max_id FROM text_entries WHERE session_id = ? AND stream = ?",
            (session_id, stream),
        ).fetchone()
        result[stream] = int(row["max_id"]) if row and row["max_id"] is not None else -1
    return result


def _ensure_session_dir(settings: Settings, slug: str) -> Path:
    path = settings.sessions_path / slug
    path.mkdir(parents=True, exist_ok=True)
    return path


def _seed_entropy_from_file(db: SQLiteDatabase, settings: Settings, target_index: Optional[int] = None) -> int:
    if not settings.dice_path.exists():
        return 0
    highest = 0
    in_tx = db.conn.in_transaction
    with settings.dice_path.open(encoding="utf-8") as handle:
        for line in handle:
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Entropy file corrupt"
                )
            idx = data.get("i", 0)
            highest = max(highest, idx)
            db.conn.execute(
                "INSERT OR REPLACE INTO entropy (entropy_index, entropy_json) VALUES (?, ?)",
                (idx, json.dumps(data)),
            )
            if target_index is not None and highest >= target_index:
                break
    if not in_tx:
        db.conn.commit()
    return highest


def _ensure_entropy_available(db: SQLiteDatabase, settings: Settings, target_index: int) -> None:
    if target_index <= 0:
        return
    row = db.conn.execute("SELECT MAX(entropy_index) as max_idx FROM entropy").fetchone()
    highest = int(row["max_idx"]) if row and row["max_idx"] is not None else 0
    if highest >= target_index:
        return
    highest = _seed_entropy_from_file(db, settings, target_index=target_index)
    if highest >= target_index:
        return
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Not enough entropy reserved (need index {target_index}, have {highest})",
    )


def _load_entropy_entry(db: SQLiteDatabase, index: int) -> Dict:
    row = db.conn.execute("SELECT entropy_json FROM entropy WHERE entropy_index = ?", (index,)).fetchone()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Not enough entropy for the requested roll",
        )
    return json.loads(row["entropy_json"])


def _load_text_entries_db(
    db: SQLiteDatabase, session_id: int, stream: str, count: Optional[int], cursor: Optional[str]
) -> Tuple[List[Dict], Optional[str]]:
    rows = db.conn.execute(
        "SELECT entry_id, text FROM text_entries WHERE session_id = ? AND stream = ? ORDER BY entry_id ASC",
        (session_id, stream),
    ).fetchall()
    entries = [{"id": str(r["entry_id"]), "text": r["text"]} for r in rows]
    if cursor:
        try:
            start_idx = int(cursor) + 1
        except ValueError:
            start_idx = 0
    else:
        start_idx = max(0, len(entries) - (count or len(entries)))
    end_idx = len(entries) if count is None else start_idx + count
    selected = entries[start_idx:end_idx]
    next_cursor = str(end_idx - 1) if end_idx < len(entries) else None
    return selected, next_cursor


def _persist_state(
    db: SQLiteDatabase, session_id: int, state: Dict, *, update_timestamp: bool = True
) -> SessionState:
    validated = storage._validate_state(state).model_dump(mode="json")
    now = _now_iso()
    db.conn.execute(
        """
        UPDATE session_state
        SET state_json = ?, turn_number = ?, log_index = ?, updated_at = ?
        WHERE session_id = ?
        """,
        (_json_dumps(validated), validated["turn"], validated["log_index"], now, session_id),
    )
    if update_timestamp:
        db.conn.execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (now, session_id))
    return SessionState(**validated)


class SQLiteSessionStore(SessionStore):
    def __init__(self, db: SQLiteDatabase):
        self.db = db

    def list_sessions(self, settings: Settings) -> List[Dict]:
        rows = self.db.conn.execute("SELECT slug, updated_at FROM sessions").fetchall()
        sessions: List[Dict] = []
        for row in rows:
            slug = row["slug"]
            try:
                state = SQLiteStateStore(self.db).load_state(settings, slug)
                world = state.get("world", "default") or "default"
            except HTTPException:
                world = "default"
            lock_row = self.db.conn.execute(
                "SELECT 1 FROM session_locks WHERE session_id = ?", (_fetch_session_id(self.db, slug),)
            ).fetchone()
            updated_at = row["updated_at"]
            try:
                updated_at = datetime.fromisoformat(updated_at)
            except Exception:
                pass
            sessions.append(
                {
                    "slug": slug,
                    "world": world,
                    "has_lock": lock_row is not None,
                    "updated_at": updated_at,
                }
            )
        return sessions

    def create_session(self, settings: Settings, slug: str, template_slug: str = "example-rogue") -> str:
        _validate_slug(slug)
        existing = self.db.conn.execute("SELECT 1 FROM sessions WHERE slug = ?", (slug,)).fetchone()
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Session already exists")

        settings.sessions_path.mkdir(parents=True, exist_ok=True)
        template_path = settings.sessions_path / template_slug / "state.json"
        if not template_path.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template session not found")
        content = template_path.read_text(encoding="utf-8")
        if content.startswith("\ufeff"):
            content = content[1:]
        base_state = json.loads(content)
        base_state["character"] = slug
        base_state["turn"] = 0
        base_state["log_index"] = 0
        validated_state = storage._validate_state(base_state).model_dump(mode="json")

        now = _now_iso()
        with self.db.conn:
            cur = self.db.conn.execute(
                "INSERT INTO sessions (slug, created_at, updated_at) VALUES (?, ?, ?)", (slug, now, now)
            )
            session_id = int(cur.lastrowid)
            self.db.conn.execute(
                """
                INSERT INTO session_state (session_id, state_json, turn_number, log_index, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (session_id, _json_dumps(validated_state), validated_state["turn"], validated_state["log_index"], now),
            )
            transcript_lines = [
                f"# Transcript: {slug}",
                "The DM will append narrated scenes here.",
            ]
            for idx, line in enumerate(transcript_lines):
                self.db.conn.execute(
                    """
                    INSERT INTO text_entries (session_id, stream, entry_id, text, created_at)
                    VALUES (?, 'transcript', ?, ?, ?)
                    """,
                    (session_id, idx, line, now),
                )
            changelog_entry = json.dumps(
                {
                    "timestamp": now,
                    "turn": 0,
                    "scene_id": "init",
                    "summary": "Initialized session state",
                    "diffs": {"hp": 0, "inventory": [], "flags": {}},
                    "rolls": [],
                    "rules": ["Initialization"],
                }
            )
            self.db.conn.execute(
                """
                INSERT INTO text_entries (session_id, stream, entry_id, text, created_at)
                VALUES (?, 'changelog', 0, ?, ?)
                """,
                (session_id, changelog_entry, now),
            )

        template_character = settings.characters_path / f"{template_slug}.json"
        if template_character.exists():
            try:
                char_payload = json.loads(template_character.read_text(encoding="utf-8"))
                SQLiteCharacterStore(self.db).save_character(settings, slug, char_payload, persist_to_data=True)
            except Exception:
                pass

        _ensure_session_dir(settings, slug)
        return slug

    def get_lock_info(self, settings: Settings, slug: str) -> Optional[LockInfo]:
        session_id = _fetch_session_id(self.db, slug)
        row = self.db.conn.execute(
            "SELECT owner, ttl, claimed_at FROM session_locks WHERE session_id = ?", (session_id,)
        ).fetchone()
        if row is None:
            return None
        return LockInfo(owner=row["owner"], ttl=row["ttl"], claimed_at=datetime.fromisoformat(row["claimed_at"]))

    def claim_lock(self, settings: Settings, slug: str, owner: str, ttl: int) -> None:
        session_id = _fetch_session_id(self.db, slug)
        existing = self.db.conn.execute(
            "SELECT 1 FROM session_locks WHERE session_id = ?", (session_id,)
        ).fetchone()
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Lock already claimed")
        now = _now_iso()
        with self.db.conn:
            self.db.conn.execute(
                """
                INSERT INTO session_locks (session_id, owner, ttl, claimed_at)
                VALUES (?, ?, ?, ?)
                """,
                (session_id, owner, ttl, now),
            )

    def release_lock(self, settings: Settings, slug: str) -> None:
        session_id = _fetch_session_id(self.db, slug)
        with self.db.conn:
            self.db.conn.execute("DELETE FROM session_locks WHERE session_id = ?", (session_id,))


class SQLiteStateStore(StateStore):
    def __init__(self, db: SQLiteDatabase):
        self.db = db

    def load_state(self, settings: Settings, slug: str) -> Dict:
        session_id = _fetch_session_id(self.db, slug)
        row = _fetch_state_row(self.db, session_id)
        state = json.loads(row["state_json"])
        return state

    def save_state(self, settings: Settings, slug: str, state: Dict) -> SessionState:
        session_id = _fetch_session_id(self.db, slug)
        with self.db.conn:
            return _persist_state(self.db, session_id, state)

    def apply_state_patch(self, settings: Settings, slug: str, patch: Dict) -> SessionState:
        state = self.load_state(settings, slug)
        updated = storage._apply_state_patch(state, patch)
        persisted = self.save_state(settings, slug, updated)
        updates = storage._character_updates_from_state_patch(persisted.model_dump(mode="json"), patch)
        if updates:
            try:
                character_store = SQLiteCharacterStore(self.db)
                character = character_store.load_character(settings, slug)
                updated_character, changed = storage._apply_character_updates(character, updates)
                if changed:
                    character_store.save_character(settings, slug, updated_character, persist_to_data=True)
            except HTTPException:
                pass
        return persisted

    def validate_data(self, data: Dict, schema_name: str, settings: Settings) -> List[str]:
        return storage.validate_data(data, schema_name, settings)

    def load_quests(self, settings: Settings, slug: str) -> Dict:
        state = self.load_state(settings, slug)
        quests = state.get("quests") or {}
        return quests

    def save_quest(self, settings: Settings, slug: str, quest_id: str, quest_data: Dict) -> None:
        state = self.load_state(settings, slug)
        quests = state.get("quests") or {}
        quests[quest_id] = quest_data
        state["quests"] = quests
        self.save_state(settings, slug, state)

    def delete_quest(self, settings: Settings, slug: str, quest_id: str) -> None:
        state = self.load_state(settings, slug)
        quests = state.get("quests") or {}
        if quest_id in quests:
            del quests[quest_id]
        state["quests"] = quests
        self.save_state(settings, slug, state)


class SQLiteEntropyStore(EntropyStore):
    def __init__(self, db: SQLiteDatabase):
        self.db = db

    def load_entropy_preview(self, settings: Settings, limit: int) -> List[Dict]:
        if not settings.dice_path.exists():
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Entropy file missing")
        _seed_entropy_from_file(self.db, settings)
        rows = self.db.conn.execute(
            "SELECT entropy_json FROM entropy ORDER BY entropy_index ASC LIMIT ?", (limit,)
        ).fetchall()
        return [json.loads(r["entropy_json"]) for r in rows]

    def load_entropy_history(self, settings: Settings, slug: str, limit: int) -> List[Dict]:
        entropy = self.load_entropy_preview(settings, limit)
        history = []
        for entry in entropy:
            history.append(
                {
                    "timestamp": datetime.fromisoformat(entry.get("timestamp", datetime.utcnow().isoformat())),
                    "who": entry.get("who", "unknown"),
                    "what": entry.get("what", "unknown"),
                    "indices": entry.get("indices", []),
                }
            )
        return history

    def ensure_available(self, settings: Settings, target_index: int) -> None:
        _ensure_entropy_available(self.db, settings, target_index)

    def load_entry(self, settings: Settings, index: int) -> Dict:
        _ensure_entropy_available(self.db, settings, index)
        return _load_entropy_entry(self.db, index)

    def reserve_indices(self, log_index: int, count: int) -> List[int]:
        if count <= 0:
            return []
        return list(range(log_index + 1, log_index + count + 1))

    def commit_indices(self, settings: Settings, slug: str, reserved_indices: List[int]) -> int:
        state = SQLiteStateStore(self.db).load_state(settings, slug)
        current_index = state.get("log_index", 0)
        if not reserved_indices:
            return current_index
        expected_start = current_index + 1
        if reserved_indices[0] != expected_start:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Entropy reservation mismatch",
            )
        _ensure_entropy_available(self.db, settings, reserved_indices[-1])
        return reserved_indices[-1]


class SQLiteCharacterStore(CharacterStore):
    def __init__(self, db: SQLiteDatabase):
        self.db = db

    def load_character(self, settings: Settings, slug: str) -> Dict:
        _validate_slug(slug)
        try:
            session_id = _fetch_session_id(self.db, slug)
        except HTTPException:
            session_id = None
        if session_id is not None:
            row = self.db.conn.execute(
                "SELECT character_json FROM characters WHERE session_id = ?", (session_id,)
            ).fetchone()
            if row is not None:
                return json.loads(row["character_json"])

        character_path = settings.characters_path / f"{slug}.json"
        session_character = settings.sessions_path / slug / "character.json"
        if session_character.exists():
            target = session_character
        elif character_path.exists():
            target = character_path
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Character '{slug}' not found",
            )
        content = target.read_text(encoding="utf-8")
        if content.startswith("\ufeff"):
            content = content[1:]
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Invalid character data for '{slug}': {exc}",
            )

    def save_character(self, settings: Settings, slug: str, character_data: Dict, persist_to_data: bool = True) -> Dict:
        _validate_slug(slug)
        payload = dict(character_data)
        payload["slug"] = slug
        now = _now_iso()
        session_id = _fetch_session_id(self.db, slug)
        with self.db.conn:
            self.db.conn.execute(
                """
                INSERT INTO characters (session_id, character_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET character_json = excluded.character_json, updated_at = excluded.updated_at
                """,
                (session_id, _json_dumps(payload), now),
            )
        if persist_to_data:
            characters_dir = settings.characters_path
            characters_dir.mkdir(parents=True, exist_ok=True)
            data_character = characters_dir / f"{slug}.json"
            data_character.write_text(_json_dumps(payload), encoding="utf-8")
        session_dir = _ensure_session_dir(settings, slug)
        session_character = session_dir / "character.json"
        session_character.write_text(_json_dumps(payload), encoding="utf-8")
        return payload


def _assert_lock_owner(db: SQLiteDatabase, slug: str, owner: Optional[str]) -> None:
    session_id = _fetch_session_id(db, slug)
    row = db.conn.execute(
        "SELECT owner FROM session_locks WHERE session_id = ?", (session_id,)
    ).fetchone()
    if row is None:
        if owner:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Lock is not claimed")
        return
    if owner and row["owner"] != owner:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Lock owned by another actor")
    if not owner:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Session locked")


class SQLiteTurnStore(TurnStore):
    def __init__(self, db: SQLiteDatabase):
        self.db = db

    def load_turn(self, settings: Settings, slug: str) -> str:
        session_id = _fetch_session_id(self.db, slug)
        row = self.db.conn.execute(
            "SELECT doc_json FROM session_docs WHERE session_id = ? AND doc_key = ?", (session_id, "turn.md")
        ).fetchone()
        if row is None:
            return ""
        try:
            return json.loads(row["doc_json"])
        except Exception:
            return ""

    def create_preview(self, settings: Settings, slug: str, request: PreviewRequest) -> Tuple[str, List[Dict], Dict]:
        _assert_lock_owner(self.db, slug, request.lock_owner)
        state_store = SQLiteStateStore(self.db)
        current_state = storage._validate_state(state_store.load_state(settings, slug))
        base_state_dict = current_state.model_dump(mode="json")
        state_hash = storage._canonical_hash(base_state_dict)

        proposed_state_dict = storage._apply_state_patch(base_state_dict, request.state_patch or {})
        storage._validate_state(proposed_state_dict)

        dice_count = len(request.dice_expressions or [])
        next_index = current_state.log_index + 1
        reserved_indices = list(range(next_index, next_index + dice_count))
        if reserved_indices:
            _ensure_entropy_available(self.db, settings, reserved_indices[-1])
            entropy_usage = f"Reserve {dice_count} entries starting at {reserved_indices[0]}"
        else:
            entropy_usage = "No dice reserved"

        diffs: List[Dict] = []
        state_changes = storage.summarize_state_diff(base_state_dict, proposed_state_dict)
        if state_changes:
            diffs.append({"path": "state.json", "changes": "; ".join(state_changes)})
        if request.transcript_entry or request.response:
            diffs.append({"path": "transcript.md", "changes": "Append 1 entry"})
        if request.changelog_entry:
            diffs.append({"path": "changelog.md", "changes": "Append changelog entry"})

        preview_id = str(uuid.uuid4())
        payload = {
            "id": preview_id,
            "slug": slug,
            "created_at": _now_iso(),
            "base_turn": current_state.turn,
            "base_hash": state_hash,
            "state_patch": request.state_patch or {},
            "transcript_entry": request.transcript_entry or request.response,
            "response": request.response,
            "changelog_entry": request.changelog_entry,
            "dice_expressions": request.dice_expressions or [],
            "reserved_indices": reserved_indices,
        }
        with self.db.conn:
            self.db.conn.execute(
                """
                INSERT INTO previews (
                    preview_id, session_id, created_at, base_turn_number, base_log_index, reserved_indices_json, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    preview_id,
                    _fetch_session_id(self.db, slug),
                    payload["created_at"],
                    current_state.turn,
                    current_state.log_index,
                    json.dumps(reserved_indices),
                    _json_dumps(payload),
                ),
            )
        entropy_plan = {"indices": reserved_indices, "usage": entropy_usage}
        return preview_id, diffs, entropy_plan

    def commit_preview(
        self, settings: Settings, slug: str, preview_id: str, lock_owner: Optional[str]
    ) -> Tuple[Dict, Dict]:
        _assert_lock_owner(self.db, slug, lock_owner)
        session_id = _fetch_session_id(self.db, slug)
        preview_row = self.db.conn.execute(
            "SELECT payload_json FROM previews WHERE preview_id = ? AND session_id = ?",
            (preview_id, session_id),
        ).fetchone()
        if preview_row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Preview not found or expired")
        preview_data = json.loads(preview_row["payload_json"])
        if preview_data.get("slug") != slug:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Preview slug mismatch")

        current_state = storage._validate_state(SQLiteStateStore(self.db).load_state(settings, slug))
        current_hash = storage._canonical_hash(current_state.model_dump(mode="json"))
        if (
            current_state.turn != preview_data.get("base_turn")
            or current_hash != preview_data.get("base_hash")
        ):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="State changed; preview is stale")

        proposed_state = storage._apply_state_patch(
            current_state.model_dump(mode="json"), preview_data.get("state_patch", {})
        )
        new_log_index = current_state.log_index
        reserved_indices: List[int] = preview_data.get("reserved_indices", [])
        if reserved_indices:
            expected_start = current_state.log_index + 1
            if reserved_indices[0] != expected_start:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Entropy reservation mismatch")
            _ensure_entropy_available(self.db, settings, reserved_indices[-1])
            new_log_index = reserved_indices[-1]

        proposed_state["turn"] = current_state.turn + 1
        proposed_state["log_index"] = new_log_index
        validated_state = storage._validate_state(proposed_state).model_dump(mode="json")

        transcript_entry = preview_data.get("transcript_entry") or preview_data.get("response")
        changelog_entry = preview_data.get("changelog_entry")

        with self.db.conn:
            _persist_state(self.db, session_id, validated_state, update_timestamp=True)
            updates = storage._character_updates_from_state_patch(
                validated_state, preview_data.get("state_patch", {}) or {}
            )
            if updates:
                try:
                    character_store = SQLiteCharacterStore(self.db)
                    character = character_store.load_character(settings, slug)
                    updated_character, changed = storage._apply_character_updates(character, updates)
                    if changed:
                        character_store.save_character(settings, slug, updated_character, persist_to_data=True)
                except HTTPException:
                    pass
            now = _now_iso()
            if transcript_entry:
                entry_id = _next_entry_id(self.db, session_id, "transcript")
                self.db.conn.execute(
                    """
                    INSERT INTO text_entries (session_id, stream, entry_id, text, created_at)
                    VALUES (?, 'transcript', ?, ?, ?)
                    """,
                    (session_id, entry_id, str(transcript_entry).rstrip(), now),
                )
            if changelog_entry:
                entry_id = _next_entry_id(self.db, session_id, "changelog")
                self.db.conn.execute(
                    """
                    INSERT INTO text_entries (session_id, stream, entry_id, text, created_at)
                    VALUES (?, 'changelog', ?, ?, ?)
                    """,
                    (session_id, entry_id, str(changelog_entry).rstrip(), now),
                )
            self.db.conn.execute("DELETE FROM previews WHERE preview_id = ?", (preview_id,))

        return validated_state, _current_log_indices(self.db, session_id)

    def load_preview_metadata(self, settings: Settings, slug: str, preview_id: str) -> Dict:
        session_id = _fetch_session_id(self.db, slug)
        row = self.db.conn.execute(
            "SELECT payload_json FROM previews WHERE preview_id = ? AND session_id = ?",
            (preview_id, session_id),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Preview not found or expired")
        data = json.loads(row["payload_json"])
        if data.get("slug") != slug:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Preview slug mismatch")
        return data

    def summarize_state_diff(self, before: Dict, after: Dict) -> List[str]:
        return storage.summarize_state_diff(before, after)

    def persist_turn_record(self, settings: Settings, slug: str, record: Dict) -> None:
        session_id = _fetch_session_id(self.db, slug)
        turn_number = record.get("turn")
        if turn_number is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Turn number required for record")
        now = _now_iso()
        state_store = SQLiteStateStore(self.db)
        state = state_store.load_state(settings, slug)
        pending_rolls, updated_state = storage._extract_pending_rolls(state, turn_number)
        if pending_rolls:
            existing_rolls = record.get("rolls")
            if not isinstance(existing_rolls, list):
                existing_rolls = []
            record["rolls"] = existing_rolls + pending_rolls
            state_store.save_state(settings, slug, updated_state)
        with self.db.conn:
            self.db.conn.execute(
                """
                INSERT INTO turns (session_id, turn_number, turn_record_json, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(session_id, turn_number) DO UPDATE
                SET turn_record_json = excluded.turn_record_json, created_at = excluded.created_at
                """,
                (session_id, turn_number, _json_dumps(record), now),
            )

    def load_turn_records(self, settings: Settings, slug: str, limit: int) -> List[Dict]:
        session_id = _fetch_session_id(self.db, slug)
        rows = self.db.conn.execute(
            """
            SELECT turn_record_json FROM turns
            WHERE session_id = ?
            ORDER BY turn_number DESC
            LIMIT ?
            """,
            (session_id, limit),
        ).fetchall()
        records: List[Dict] = []
        for row in rows:
            try:
                records.append(json.loads(row["turn_record_json"]))
            except Exception:
                continue
        return records

    def load_turn_record(self, settings: Settings, slug: str, turn: int) -> Dict:
        session_id = _fetch_session_id(self.db, slug)
        row = self.db.conn.execute(
            "SELECT turn_record_json FROM turns WHERE session_id = ? AND turn_number = ?",
            (session_id, turn),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Turn record not found")
        return json.loads(row["turn_record_json"])

    def perform_roll(self, settings: Settings, slug: str, roll_request: RollRequest) -> RollResult:
        character = {}
        try:
            character = SQLiteCharacterStore(self.db).load_character(settings, slug)
        except HTTPException:
            pass

        state_store = SQLiteStateStore(self.db)
        session_id = _fetch_session_id(self.db, slug)
        with self.db.conn:
            state = state_store.load_state(settings, slug)
            next_index = state.get("log_index", 0) + 1
            _ensure_entropy_available(self.db, settings, next_index)
            entropy_entry = _load_entropy_entry(self.db, next_index)

            d20_values = entropy_entry.get("d20") or []
            needed = 2 if roll_request.advantage in ("advantage", "disadvantage") else 1
            if len(d20_values) < needed:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Entropy line missing dice values"
                )

            used_rolls = d20_values[:needed]
            if roll_request.advantage == "advantage":
                base_roll = max(used_rolls)
            elif roll_request.advantage == "disadvantage":
                base_roll = min(used_rolls)
            else:
                base_roll = used_rolls[0]

            modifier = 0
            ability = roll_request.ability
            if not ability and roll_request.skill:
                ability = storage._SKILL_TO_ABILITY.get(storage._normalize_skill_name(roll_request.skill))
            if not ability and roll_request.kind == "initiative":
                ability = "DEX"

            ability_score = None
            if ability:
                ability_score = (
                    storage._ability_score_from_payload(state, ability)
                    or storage._ability_score_from_payload(character, ability)
                )
            ability_mod = storage._ability_modifier(ability_score)
            modifier += ability_mod

            prof_bonus = 0
            if roll_request.skill and storage._is_skill_proficient(character, roll_request.skill):
                level = character.get("level") or state.get("level")
                prof_bonus = storage._proficiency_bonus(level)
                modifier += prof_bonus

            total = base_roll + modifier

            state["log_index"] = next_index
            roll_payload = {
                "kind": roll_request.kind,
                "ability": ability,
                "skill": roll_request.skill,
                "advantage": roll_request.advantage,
                "dc": roll_request.dc,
                "total": total,
                "d20": used_rolls,
                "breakdown": None,
                "text": None,
            }

            breakdown_parts = [str(base_roll)]
            if ability:
                breakdown_parts.append(f"{ability_mod:+d} ({ability})")
            if prof_bonus:
                breakdown_parts.append(f"+{prof_bonus} (PROF)")
            breakdown = " ".join(part.replace("+-", "-") for part in breakdown_parts)

            display_label = storage._display_label(roll_request)
            text = f"I roll {display_label}: {breakdown} = {total}"
            roll_payload["breakdown"] = breakdown
            roll_payload["text"] = text

            state["log_index"] = next_index
            target_turn = (state.get("turn") or 0) + 1
            state = storage._queue_pending_roll(state, target_turn, roll_payload)
            _persist_state(self.db, session_id, state, update_timestamp=True)
            entry_id = _next_entry_id(self.db, session_id, "transcript")
            self.db.conn.execute(
                """
                INSERT INTO text_entries (session_id, stream, entry_id, text, created_at)
                VALUES (?, 'transcript', ?, ?, ?)
                """,
                (session_id, entry_id, text.rstrip(), _now_iso()),
            )

        return RollResult(d20=used_rolls, total=total, breakdown=breakdown, text=text)

    def load_commit_history(self, settings: Settings, slug: str) -> List[Dict]:
        session_id = _fetch_session_id(self.db, slug)
        rows = self.db.conn.execute(
            "SELECT entry_id, text FROM text_entries WHERE session_id = ? AND stream = 'changelog' ORDER BY entry_id ASC",
            (session_id,),
        ).fetchall()
        commits = []
        for row in rows:
            commits.append(
                {
                    "id": str(row["entry_id"]),
                    "tags": [],
                    "entropy_indices": [],
                    "timestamp": datetime.utcnow(),
                    "description": row["text"],
                }
            )
        return commits

    def load_session_diff(self, settings: Settings, slug: str, from_commit: str, to_commit: str) -> List[Dict]:
        return [{"path": "state.json", "changes": f"Diff from {from_commit} to {to_commit}"}]


class SQLiteTextLogStore(TextLogStore):
    def __init__(self, db: SQLiteDatabase):
        self.db = db

    def load_transcript(
        self, settings: Settings, slug: str, tail: Optional[int] = None, cursor: Optional[str] = None
    ) -> Tuple[List[Dict], Optional[str]]:
        session_id = _fetch_session_id(self.db, slug)
        count = tail if tail is not None else settings.transcript_tail
        return _load_text_entries_db(self.db, session_id, "transcript", count, cursor)

    def load_changelog(
        self, settings: Settings, slug: str, tail: Optional[int] = None, cursor: Optional[str] = None
    ) -> Tuple[List[Dict], Optional[str]]:
        session_id = _fetch_session_id(self.db, slug)
        count = tail if tail is not None else settings.changelog_tail
        return _load_text_entries_db(self.db, session_id, "changelog", count, cursor)


class SQLiteGenericDocStore(GenericDocStore):
    def __init__(self, db: SQLiteDatabase):
        self.db = db

    def load_doc(self, settings: Settings, slug: str, name: str) -> Any:
        session_id = _fetch_session_id(self.db, slug)
        row = self.db.conn.execute(
            "SELECT doc_json FROM session_docs WHERE session_id = ? AND doc_key = ?", (session_id, name)
        ).fetchone()
        if row is None:
            return [] if name == "npc_memory" else {}
        try:
            return json.loads(row["doc_json"])
        except Exception:
            return [] if name == "npc_memory" else {}

    def save_doc(self, settings: Settings, slug: str, name: str, payload: Any) -> None:
        session_id = _fetch_session_id(self.db, slug)
        now = _now_iso()
        with self.db.conn:
            self.db.conn.execute(
                """
                INSERT INTO session_docs (session_id, doc_key, doc_json, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(session_id, doc_key) DO UPDATE
                SET doc_json = excluded.doc_json, updated_at = excluded.updated_at
                """,
                (session_id, name, _json_dumps(payload), now),
            )

    def record_last_discovery_turn(self, settings: Settings, slug: str, turn: int) -> None:
        payload = {"turn": turn, "recorded_at": _now_iso()}
        self.save_doc(settings, slug, "last_discovery", payload)

    def get_last_discovery_turn(self, settings: Settings, slug: str) -> Optional[int]:
        data = self.load_doc(settings, slug, "last_discovery")
        if not isinstance(data, dict):
            return None
        turn = data.get("turn")
        try:
            return int(turn) if turn is not None else None
        except Exception:
            return None


class SQLiteSnapshotStore(SnapshotStore):
    def __init__(self, db: SQLiteDatabase):
        self.db = db

    def create_save(self, settings: Settings, slug: str, save_name: str, save_type: str) -> Dict:
        session_id = _fetch_session_id(self.db, slug)
        timestamp = _now_iso()
        save_id = f"{save_name}-{timestamp}"
        payload = {
            "save_id": save_id,
            "session_slug": slug,
            "timestamp": timestamp,
            "save_type": save_type,
            "data": {},
        }
        with self.db.conn:
            self.db.conn.execute(
                """
                INSERT INTO snapshots (session_id, save_id, save_type, created_at, snapshot_json)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(session_id, save_id) DO UPDATE
                SET snapshot_json = excluded.snapshot_json, created_at = excluded.created_at, save_type = excluded.save_type
                """,
                (session_id, save_id, save_type, timestamp, _json_dumps(payload)),
            )
        return payload

    def list_saves(self, settings: Settings, slug: str, limit: int) -> List[Dict]:
        session_id = _fetch_session_id(self.db, slug)
        rows = self.db.conn.execute(
            """
            SELECT snapshot_json FROM snapshots
            WHERE session_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (session_id, limit),
        ).fetchall()
        saves: List[Dict] = []
        for row in rows:
            try:
                saves.append(json.loads(row["snapshot_json"]))
            except Exception:
                continue
        return saves

    def get_save(self, settings: Settings, slug: str, save_id: str) -> Optional[Dict]:
        session_id = _fetch_session_id(self.db, slug)
        row = self.db.conn.execute(
            "SELECT snapshot_json FROM snapshots WHERE session_id = ? AND save_id = ?", (session_id, save_id)
        ).fetchone()
        if row is None:
            return None
        try:
            return json.loads(row["snapshot_json"])
        except Exception:
            return None

    def restore_save(self, settings: Settings, slug: str, save_id: str) -> Dict:
        data = self.get_save(settings, slug, save_id)
        if data is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Save not found")
        return {"message": "Restore not implemented", "save": data}


class SQLiteWorldStore(WorldStore):
    def __init__(self, db: SQLiteDatabase):
        self.db = db

    def _resolve_world(self, settings: Settings, slug: str) -> Path:
        state = SQLiteStateStore(self.db).load_state(settings, slug)
        world_name = state.get("world", "default")
        world_path = settings.worlds_path / world_name
        if not world_path.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"World '{world_name}' not found")
        return world_path

    def _load_world_file(self, world_path: Path, filename: str) -> Dict:
        path = world_path / filename
        if not path.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Missing world file {filename}")
        with path.open() as handle:
            return json.load(handle)

    def load_factions(self, settings: Settings, slug: str) -> Dict:
        world = self._resolve_world(settings, slug)
        data = self._load_world_file(world, "factions.json")
        return {f["id"]: f for f in data["factions"]}

    def save_faction(self, settings: Settings, slug: str, faction_id: str, faction_data: Dict) -> None:
        world = self._resolve_world(settings, slug)
        data = self._load_world_file(world, "factions.json")
        factions_dict = {f["id"]: f for f in data["factions"]}
        factions_dict[faction_id] = faction_data
        data["factions"] = list(factions_dict.values())
        with (world / "factions.json").open("w") as handle:
            json.dump(data, handle, indent=2)

    def delete_faction(self, settings: Settings, slug: str, faction_id: str) -> None:
        world = self._resolve_world(settings, slug)
        data = self._load_world_file(world, "factions.json")
        factions_dict = {f["id"]: f for f in data["factions"]}
        if faction_id in factions_dict:
            del factions_dict[faction_id]
            data["factions"] = list(factions_dict.values())
            with (world / "factions.json").open("w") as handle:
                json.dump(data, handle, indent=2)

    def load_timeline(self, settings: Settings, slug: str) -> Dict:
        world = self._resolve_world(settings, slug)
        data = self._load_world_file(world, "timeline.json")
        return {e["id"]: e for e in data["events"]}

    def save_timeline_event(self, settings: Settings, slug: str, event_id: str, event_data: Dict) -> None:
        world = self._resolve_world(settings, slug)
        data = self._load_world_file(world, "timeline.json")
        events_dict = {e["id"]: e for e in data["events"]}
        events_dict[event_id] = event_data
        data["events"] = list(events_dict.values())
        with (world / "timeline.json").open("w") as handle:
            json.dump(data, handle, indent=2)

    def delete_timeline_event(self, settings: Settings, slug: str, event_id: str) -> None:
        world = self._resolve_world(settings, slug)
        data = self._load_world_file(world, "timeline.json")
        events_dict = {e["id"]: e for e in data["events"]}
        if event_id in events_dict:
            del events_dict[event_id]
            data["events"] = list(events_dict.values())
            with (world / "timeline.json").open("w") as handle:
                json.dump(data, handle, indent=2)

    def load_rumors(self, settings: Settings, slug: str) -> Dict:
        world = self._resolve_world(settings, slug)
        data = self._load_world_file(world, "rumors.json")
        return {r["id"]: r for r in data["rumors"]}

    def load_faction_clocks(self, settings: Settings, slug: str) -> Dict:
        world = self._resolve_world(settings, slug)
        data = self._load_world_file(world, "faction_clocks.json")
        return data


def build_sqlite_backend(settings: Settings, db_path: Optional[Path] = None) -> StorageBackend:
    path = db_path or _resolve_db_path(settings)
    db = SQLiteDatabase(path)
    _seed_entropy_from_file(db, settings)
    return StorageBackend(
        session=SQLiteSessionStore(db),
        state=SQLiteStateStore(db),
        turn=SQLiteTurnStore(db),
        entropy=SQLiteEntropyStore(db),
        character=SQLiteCharacterStore(db),
        text_logs=SQLiteTextLogStore(db),
        docs=SQLiteGenericDocStore(db),
        snapshots=SQLiteSnapshotStore(db),
        world=SQLiteWorldStore(db),
    )


__all__ = ["build_sqlite_backend", "_resolve_db_path"]
