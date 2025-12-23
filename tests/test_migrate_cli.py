import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from service.config import Settings
from service.storage_backends.sqlite_backend import SQLiteDatabase, SQLiteStateStore, SQLiteTextLogStore, SQLiteTurnStore
from tools import migrate_to_sqlite as migrator


def _write(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_migrate_cli_round_trip(tmp_path):
    source = tmp_path / "src"
    session_dir = source / "sessions" / "demo-session"
    session_dir.mkdir(parents=True)

    state = {
        "character": "demo-session",
        "turn": 2,
        "scene_id": "scn",
        "location": "L1",
        "hp": 9,
        "conditions": [],
        "flags": {},
        "log_index": 3,
        "level": 1,
        "xp": 0,
        "inventory": [],
        "world": "default",
    }
    _write(session_dir / "state.json", state)

    transcript = "# intro\n\nsecond line\n"
    (session_dir / "transcript.md").write_text(transcript, encoding="utf-8")
    changelog = '{"turn":1}\n{"turn":2}\n'
    (session_dir / "changelog.md").write_text(changelog, encoding="utf-8")

    _write(session_dir / "turns" / "1.json", {"turn": 1, "note": "first"})
    _write(session_dir / "turns" / "2.json", {"turn": 2, "note": "second"})

    _write(session_dir / "npc_memory.json", {"npcs": [{"id": "n1"}]})
    _write(session_dir / "saves" / "auto-test.json", {"save_id": "auto-test", "save_type": "auto", "timestamp": "2024-01-01T00:00:00Z"})

    _write(source / "data" / "characters" / "demo-session.json", {"name": "Tester", "slug": "demo-session"})

    db_path = tmp_path / "dm.sqlite"
    rc = migrator.main(["--source", str(source), "--db", str(db_path)])
    assert rc == 0

    settings = Settings(repo_root=source)
    db = SQLiteDatabase(db_path)

    loaded_state = SQLiteStateStore(db).load_state(settings, "demo-session")
    assert loaded_state["turn"] == state["turn"]
    assert loaded_state["log_index"] == state["log_index"]

    transcript_entries, _ = SQLiteTextLogStore(db).load_transcript(settings, "demo-session", tail=10, cursor=None)
    changelog_entries, _ = SQLiteTextLogStore(db).load_changelog(settings, "demo-session", tail=10, cursor=None)
    assert len(transcript_entries) == 2  # blank lines are ignored
    assert len(changelog_entries) == 2

    turn_records = SQLiteTurnStore(db).load_turn_records(settings, "demo-session", limit=5)
    assert len(turn_records) == 2
