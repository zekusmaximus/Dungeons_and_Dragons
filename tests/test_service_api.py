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
    sessions = response.json()
    assert isinstance(sessions, list)
    slugs = [s["slug"] for s in sessions]
    assert "example-rogue" in slugs


def test_state_reads_existing_session(client):
    response = client.get("/sessions/example-rogue/state")
    assert response.status_code == 200
    state = response.json()
    assert state["character"] == "example-rogue"
    assert state["world"] == "default"


def test_transcript_tail(client):
    response = client.get("/sessions/example-rogue/transcript", params={"tail": 2})
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "cursor" in data
    transcript = data["items"]
    assert len(transcript) <= 2
    if transcript:
        assert transcript[-1]["text"] == "The DM will append narrated scenes here."


def test_changelog_tail(client):
    response = client.get("/sessions/example-rogue/changelog", params={"tail": 1})
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "cursor" in data
    changelog = data["items"]
    assert len(changelog) <= 1
    if changelog:
        assert "Initialized session state" in changelog[-1]["text"]


def test_world_factions(client):
    response = client.get("/sessions/example-rogue/world/factions")
    assert response.status_code == 200
    factions = response.json()
    assert isinstance(factions, dict)
    assert factions


def test_world_timeline(client):
    response = client.get("/sessions/example-rogue/world/timeline")
    assert response.status_code == 200
    timeline = response.json()
    assert isinstance(timeline, dict)


def test_world_rumors(client):
    response = client.get("/sessions/example-rogue/world/rumors")
    assert response.status_code == 200
    rumors = response.json()
    assert isinstance(rumors, dict)


def test_world_faction_clocks(client):
    response = client.get("/sessions/example-rogue/world/faction-clocks")
    assert response.status_code == 200
    clocks = response.json()
    assert isinstance(clocks, dict)


def test_quests(client):
    response = client.get("/sessions/example-rogue/quests")
    assert response.status_code == 200
    data = response.json()
    assert "quests" in data


def test_npc_memory(client):
    response = client.get("/sessions/example-rogue/npc-memory")
    assert response.status_code == 200
    data = response.json()
    assert "npc_memory" in data


def test_entropy_preview(client):
    response = client.get("/entropy", params={"limit": 2})
    assert response.status_code == 200
    entropy = response.json()["entropy"]
    assert len(entropy) == 2
    assert entropy[0]["i"] == 1


def test_get_turn(client):
    response = client.get("/sessions/example-rogue/turn")
    assert response.status_code == 200
    data = response.json()
    assert "prompt" in data
    assert "turn_number" in data
    assert "lock_status" in data


def test_lock_claim(client):
    response = client.post("/sessions/example-rogue/lock/claim", json={"owner": "testuser", "ttl": 300})
    assert response.status_code == 200
    assert response.json() == {"message": "Lock claimed"}

    # Check lock status
    response = client.get("/sessions/example-rogue/turn")
    assert response.status_code == 200
    data = response.json()
    assert data["lock_status"]["owner"] == "testuser"


def test_lock_claim_conflict(client):
    # Claim first
    client.post("/sessions/example-rogue/lock/claim", json={"owner": "user1", "ttl": 300})
    # Try to claim again
    response = client.post("/sessions/example-rogue/lock/claim", json={"owner": "user2", "ttl": 300})
    assert response.status_code == 409


def test_lock_release(client):
    client.post("/sessions/example-rogue/lock/claim", json={"owner": "testuser", "ttl": 300})
    response = client.delete("/sessions/example-rogue/lock")
    assert response.status_code == 200
    assert response.json() == {"message": "Lock released"}

    # Check unlocked
    response = client.get("/sessions/example-rogue/turn")
    assert response.status_code == 200
    data = response.json()
    assert data["lock_status"] is None


def test_preview_turn(client):
    response = client.post("/sessions/example-rogue/turn/preview", json={"response": "Test response"})
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert "diffs" in data
    assert "entropy_plan" in data


def test_commit_turn(client):
    # Preview first
    preview_resp = client.post("/sessions/example-rogue/turn/preview", json={"response": "Test response"})
    preview_id = preview_resp.json()["id"]

    response = client.post("/sessions/example-rogue/turn/commit", json={"preview_id": preview_id})
    assert response.status_code == 200
    data = response.json()
    assert "state" in data
    assert "log_indices" in data


def test_create_explore_job(client):
    response = client.post("/jobs/explore", json={"type": "explore", "params": {"slug": "example-rogue", "steps": 1, "pace": "normal"}})
    assert response.status_code == 200
    job = response.json()
    assert "id" in job
    assert job["type"] == "explore"
    assert job["status"] == "pending"


def test_get_job_progress(client):
    # Create job first
    create_resp = client.post("/jobs/explore", json={"type": "explore", "params": {"slug": "example-rogue", "steps": 1, "pace": "normal"}})
    job_id = create_resp.json()["id"]

    response = client.get(f"/jobs/{job_id}")
    assert response.status_code == 200
    progress = response.json()
    assert "status" in progress
    assert "logs" in progress
    assert "entropy_usage" in progress
    assert "diff_preview" in progress


def test_commit_job(client):
    # Create and wait for completion (in real test, might need to mock or wait)
    create_resp = client.post("/jobs/explore", json={"type": "explore", "params": {"slug": "example-rogue", "steps": 1, "pace": "normal"}})
    job_id = create_resp.json()["id"]

    # Assume job completes quickly for test
    import time
    time.sleep(2)  # Wait for job to run

    response = client.post(f"/jobs/{job_id}/commit")
    assert response.status_code == 200
    assert response.json() == {"message": "Job committed"}


def test_cancel_job(client):
    create_resp = client.post("/jobs/explore", json={"type": "explore", "params": {"slug": "example-rogue", "steps": 1, "pace": "normal"}})
    job_id = create_resp.json()["id"]

    response = client.post(f"/jobs/{job_id}/cancel")
    assert response.status_code == 200
    assert response.json() == {"message": "Job cancelled"}
