from pathlib import Path
import shutil

import pytest
from fastapi.testclient import TestClient

from service.app import app, get_settings_dep
from service.config import Settings


@pytest.fixture
def client(tmp_path):
    repo_root = Path(__file__).resolve().parent.parent
    temp_root = tmp_path / "repo_copy"
    for name in ["sessions", "data", "worlds", "dice"]:
        shutil.copytree(repo_root / name, temp_root / name)

    def override_settings():
        return Settings(repo_root=temp_root)

    app.dependency_overrides[get_settings_dep] = override_settings
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_slug_validation_blocks_traversal(client: TestClient):
    response = client.get("/sessions/%2e%2e/state")
    assert response.status_code == 400


def test_preview_reserves_entropy_without_consuming(client: TestClient):
    base_state = client.get("/sessions/example-rogue/state").json()
    preview = client.post(
        "/sessions/example-rogue/turn/preview",
        json={
            "response": "Step forward carefully.",
            "state_patch": {"flags": {"scouted": True}},
            "transcript_entry": "The rogue scouts ahead.",
            "dice_expressions": ["1d20", "1d6"],
        },
    )
    assert preview.status_code == 200
    data = preview.json()
    assert data["entropy_plan"]["indices"] == [base_state["log_index"] + 1, base_state["log_index"] + 2]

    state_after = client.get("/sessions/example-rogue/state").json()
    assert state_after["log_index"] == base_state["log_index"]


def test_commit_consumes_entropy_and_advances_turn(client: TestClient):
    base_state = client.get("/sessions/example-rogue/state").json()
    preview = client.post(
        "/sessions/example-rogue/turn/preview",
        json={
            "response": "A careful strike.",
            "state_patch": {"hp": base_state["hp"] - 1},
            "dice_expressions": ["1d20"],
            "changelog_entry": "Took a small hit while scouting.",
        },
    )
    assert preview.status_code == 200
    preview_id = preview.json()["id"]

    commit = client.post(
        "/sessions/example-rogue/turn/commit",
        json={"preview_id": preview_id},
    )
    assert commit.status_code == 200
    committed_state = commit.json()["state"]
    assert committed_state["turn"] == base_state["turn"] + 1
    assert committed_state["log_index"] == base_state["log_index"] + 1
    assert committed_state["hp"] == base_state["hp"] - 1


def test_commit_rejects_stale_preview(client: TestClient):
    preview_one = client.post(
        "/sessions/example-rogue/turn/preview",
        json={"response": "First preview.", "state_patch": {"flags": {"preview": 1}}},
    )
    assert preview_one.status_code == 200
    preview_one_id = preview_one.json()["id"]

    preview_two = client.post(
        "/sessions/example-rogue/turn/preview",
        json={"response": "Second preview.", "state_patch": {"flags": {"preview": 2}}},
    )
    assert preview_two.status_code == 200
    preview_two_id = preview_two.json()["id"]

    commit_latest = client.post(
        "/sessions/example-rogue/turn/commit", json={"preview_id": preview_two_id}
    )
    assert commit_latest.status_code == 200

    stale_commit = client.post(
        "/sessions/example-rogue/turn/commit", json={"preview_id": preview_one_id}
    )
    assert stale_commit.status_code == 409


def test_invalid_patch_fails_validation(client: TestClient):
    response = client.post(
        "/sessions/example-rogue/turn/preview",
        json={"response": "Bad hp", "state_patch": {"hp": -5}},
    )
    assert response.status_code == 400
