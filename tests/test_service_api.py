from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from service.app import app
from service.config import Settings, get_settings


@pytest.fixture(scope="module")
def client():
    # ensure service uses repository root relative to test file
    repo_root = Path(__file__).resolve().parent.parent

    def override_settings():
        return Settings(repo_root=repo_root)

    app.dependency_overrides[get_settings] = override_settings
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_list_sessions(client):
    response = client.get("/sessions")
    assert response.status_code == 200
    payload = response.json()
    assert "example-rogue" in payload["sessions"]


def test_state_reads_existing_session(client):
    response = client.get("/sessions/example-rogue/state")
    assert response.status_code == 200
    state = response.json()
    assert state["character"] == "example-rogue"
    assert state["world"] == "default"


def test_transcript_tail(client):
    response = client.get("/sessions/example-rogue/transcript", params={"tail": 2})
    assert response.status_code == 200
    transcript = response.json()["transcript"]
    assert transcript[-1] == "The DM will append narrated scenes here."


def test_changelog_tail(client):
    response = client.get("/sessions/example-rogue/changelog", params={"tail": 1})
    assert response.status_code == 200
    changelog = response.json()["changelog"]
    assert changelog
    assert "Initialized session state" in changelog[-1]


def test_world_factions(client):
    response = client.get("/sessions/example-rogue/world/factions")
    assert response.status_code == 200
    factions = response.json()
    assert isinstance(factions, dict)
    assert factions


def test_entropy_preview(client):
    response = client.get("/entropy", params={"limit": 2})
    assert response.status_code == 200
    entropy = response.json()["entropy"]
    assert len(entropy) == 2
    assert entropy[0]["i"] == 1
