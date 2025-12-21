from pathlib import Path
import shutil

import pytest
from fastapi.testclient import TestClient

from service.app import app, get_settings_dep
from service.config import Settings


@pytest.fixture()
def client_with_root(tmp_path_factory):
    repo_root = Path(__file__).resolve().parent.parent
    temp_root = tmp_path_factory.mktemp("repo_copy_turns")
    for name in ["sessions", "data", "worlds", "dice"]:
        shutil.copytree(repo_root / name, temp_root / name)

    def override_settings():
        return Settings(repo_root=temp_root)

    app.dependency_overrides[get_settings_dep] = override_settings
    with TestClient(app) as client:
        yield client, temp_root
    app.dependency_overrides.clear()


def _prepare_preview(client):
    preview_resp = client.post("/sessions/example-rogue/turn/preview", json={"response": "push forward"})
    assert preview_resp.status_code == 200
    return preview_resp.json()["id"]


def test_commit_and_narrate_persists_record(client_with_root):
    client, root = client_with_root
    base_state = client.get("/sessions/example-rogue/state").json()
    new_turn = base_state["turn"] + 1
    preview_id = _prepare_preview(client)
    resp = client.post("/sessions/example-rogue/turn/commit-and-narrate", json={"preview_id": preview_id})
    assert resp.status_code == 200
    record_path = root / "sessions" / "example-rogue" / "turns" / f"{new_turn}.json"
    assert record_path.exists()
    data = resp.json()
    assert data["turn_record"]["turn"] == new_turn


def test_get_turn_records_returns_recent(client_with_root):
    client, _ = client_with_root
    base_state = client.get("/sessions/example-rogue/state").json()
    new_turn = base_state["turn"] + 1
    preview_id = _prepare_preview(client)
    client.post("/sessions/example-rogue/turn/commit-and-narrate", json={"preview_id": preview_id})
    resp = client.get("/sessions/example-rogue/turns", params={"limit": 3})
    assert resp.status_code == 200
    records = resp.json()
    assert isinstance(records, list)
    assert records[0]["turn"] == new_turn


def test_dm_validation_fallback(client_with_root, monkeypatch):
    client, _ = client_with_root

    async def fake_call_llm(settings, prompt, context=None, max_tokens=None):
        return {"content": "not json", "usage": {"total_tokens": 5}}

    monkeypatch.setattr("service.narration.call_llm_api", fake_call_llm)

    preview_id = _prepare_preview(client)
    resp = client.post("/sessions/example-rogue/turn/commit-and-narrate", json={"preview_id": preview_id})
    assert resp.status_code == 200
    data = resp.json()
    dm = data["dm"]
    assert dm["choices"]
    assert data["usage"] == {"total_tokens": 5}
