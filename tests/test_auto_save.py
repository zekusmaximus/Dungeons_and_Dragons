from pathlib import Path
import json
from service.auto_save import AutoSaveSystem


def _prep_session(tmp_path: Path, slug: str) -> Path:
    base = tmp_path / "game"
    session = base / "sessions" / slug
    session.mkdir(parents=True, exist_ok=True)
    (session / "state.json").write_text('{"hp":10}', encoding="utf-8")
    (session / "transcript.md").write_text("Turn 0\n", encoding="utf-8")
    return base


def test_manual_save_and_restore(tmp_path):
    base = _prep_session(tmp_path, "demo")
    autosave = AutoSaveSystem("demo", base_root=base)

    result = autosave.manual_save("checkpoint")
    assert result["success"]
    save_id = result["save_id"]

    save_file = base / "sessions" / "demo" / "saves" / f"{save_id}.json"
    assert save_file.exists()

    with save_file.open(encoding="utf-8") as f:
        payload = json.load(f)
    assert "state.json" in payload["data"]["files"]

    # mutate state, then restore
    state_path = base / "sessions" / "demo" / "state.json"
    state_path.write_text('{"hp":1}', encoding="utf-8")

    restore_result = autosave.restore_save(save_id)
    assert restore_result["success"]
    restored = json.loads(state_path.read_text(encoding="utf-8"))
    assert restored["hp"] == 10
