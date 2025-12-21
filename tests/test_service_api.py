from pathlib import Path
import shutil

import pytest
from fastapi.testclient import TestClient

from service.app import app, get_settings_dep
from service.config import Settings
from service import app as app_module
from service.models import DMChoice, DMNarration, RollRequest


@pytest.fixture(scope="function")
def client(tmp_path_factory):
    # ensure service uses repository root relative to test file
    repo_root = Path(__file__).resolve().parent.parent
    temp_root = tmp_path_factory.mktemp("repo_copy")
    for name in ["sessions", "data", "worlds", "dice"]:
        shutil.copytree(repo_root / name, temp_root / name)

    def override_settings():
        return Settings(repo_root=temp_root)

    app.dependency_overrides[get_settings_dep] = override_settings
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


def test_create_session_endpoint(client):
    response = client.post("/sessions", json={"hook_id": "test-hook"})
    assert response.status_code == 201
    slug = response.json()["slug"]
    sessions = client.get("/sessions").json()
    assert slug in [s["slug"] for s in sessions]

    state = client.get(f"/sessions/{slug}/state").json()
    assert state["character"] == slug
    assert state["turn"] == 0


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
    assert response.status_code == 501
    assert "disabled" in response.json()["detail"]


def test_get_job_progress(client):
    response = client.get("/jobs/some-id")
    assert response.status_code == 501


def test_commit_job(client):
    response = client.post("/jobs/any/commit")
    assert response.status_code == 501


def test_cancel_job(client):
    response = client.post("/jobs/any/cancel")
    assert response.status_code == 501


def _character_payload():
    return {
        "name": "Player One",
        "ancestry": "Human",
        "class": "Fighter",
        "background": "Soldier",
        "level": 1,
        "hp": 11,
        "ac": 16,
        "gp": 10,
        "abilities": {"str": 15, "dex": 14, "con": 13, "int": 10, "wis": 12, "cha": 8},
        "skills": ["athletics", "perception"],
        "proficiencies": ["athletics", "perception"],
        "tools": ["smith's tools"],
        "languages": ["Common"],
        "equipment": ["Chain mail", "Shield", "Longsword"],
        "spells": [],
        "notes": "Ready for battle",
        "starting_location": "Town Gate",
        "method": "standard-array",
        "hook": "Urban mystery",
    }


def test_player_character_creation_and_bundle(client):
    new_session = client.post("/sessions", json={"slug": "player-flow"}).json()["slug"]
    response = client.post(f"/sessions/{new_session}/character", json=_character_payload())
    assert response.status_code == 201
    created = response.json()
    assert created["character"]["name"] == "Player One"
    assert created["state"]["hp"] == 11
    assert created["state"]["ac"] == 18
    assert created["state"]["abilities"]["str"] == 15

    settings = app.dependency_overrides[get_settings_dep]()
    session_character = settings.sessions_path / new_session / "character.json"
    assert session_character.exists()

    bundle = client.get(f"/sessions/{new_session}/player").json()
    assert bundle["state"]["character"] == new_session
    assert bundle["character"]["name"] == "Player One"
    assert bundle["suggestions"]


def test_opening_scene_with_hook(client):
    slug = client.post("/sessions", json={"slug": "opening-scene"}).json()["slug"]
    client.post(f"/sessions/{slug}/character", json=_character_payload())
    response = client.post(f"/sessions/{slug}/player/opening", json={"hook": "Urban mystery"})
    assert response.status_code == 200
    data = response.json()
    assert "narration" in data
    assert "What do you do?" in data["narration"]["narration"]
    assert len(data["narration"]["choices"]) >= 4
    assert data["state"]["adventure_hook"]["label"] == "Urban mystery"


def test_player_turn_endpoint(client):
    slug = client.post("/sessions", json={"slug": "player-turn"}).json()["slug"]
    client.post(f"/sessions/{slug}/character", json=_character_payload())
    response = client.post(f"/sessions/{slug}/player/turn", json={"action": "I scout the area"})
    assert response.status_code == 200
    data = response.json()
    assert "narration" in data
    assert data["state"]["turn"] >= 1


def test_player_roll_deterministic(client):
    slug = client.post("/sessions", json={"slug": "roll-deterministic"}).json()["slug"]
    response = client.post(
        f"/sessions/{slug}/roll",
        json={"kind": "ability_check", "ability": "DEX"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == data["d20"][0] + 3
    # First entropy line uses d20=12 and character dex modifier +3
    assert data["total"] == 15
    assert set(data.keys()) == {"d20", "total", "breakdown", "text"}


def test_player_roll_proficiency_applied(client):
    slug = client.post("/sessions", json={"slug": "roll-prof"}).json()["slug"]
    client.post(f"/sessions/{slug}/character", json=_character_payload())

    response = client.post(
        f"/sessions/{slug}/roll",
        json={"kind": "ability_check", "skill": "athletics"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["d20"][0] == 12
    assert "PROF" in data["breakdown"]
    assert data["total"] == 16

    response = client.post(
        f"/sessions/{slug}/roll",
        json={"kind": "ability_check", "skill": "stealth"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["d20"][0] == 7
    assert "PROF" not in data["breakdown"]
    assert data["total"] == 9


def test_player_roll_flow_smoke(monkeypatch, client):
    slug = client.post("/sessions", json={"slug": "roll-flow"}).json()["slug"]
    client.post(f"/sessions/{slug}/character", json=_character_payload())
    client.post(f"/sessions/{slug}/player/opening", json={"hook": "Urban mystery"})

    call_count = {"n": 0}

    async def fake_dm(settings, session_slug, state, before_state, player_intent, diff, include_discovery=False):
        call_count["n"] += 1
        choices = [
            DMChoice(id="A", text="Talk", intent_tag="talk", risk="low"),
            DMChoice(id="B", text="Sneak", intent_tag="sneak", risk="medium"),
            DMChoice(id="C", text="Fight", intent_tag="fight", risk="high"),
            DMChoice(id="D", text="Investigate", intent_tag="investigate", risk="medium"),
        ]
        if call_count["n"] == 1:
            dm = DMNarration(
                narration="Test scene. Roll now.",
                recap="recap",
                stakes="stakes",
                choices=choices,
                roll_request=RollRequest(kind="ability_check", ability="DEX", skill="stealth", dc=12),
            )
            return dm, None
        dm = DMNarration(
            narration="Resolution lands. What do you do?",
            recap="recap",
            stakes="stakes",
            choices=choices,
        )
        return dm, None

    monkeypatch.setattr(app_module, "generate_dm_narration", fake_dm)

    response = client.post(f"/sessions/{slug}/player/turn", json={"action": "I test"})
    assert response.status_code == 200
    data = response.json()
    assert data["roll_request"]["kind"] == "ability_check"

    roll_response = client.post(
        f"/sessions/{slug}/roll",
        json={"kind": "ability_check", "ability": "DEX", "skill": "stealth"},
    )
    assert roll_response.status_code == 200
    action_text = roll_response.json()["text"]

    response = client.post(f"/sessions/{slug}/player/turn", json={"action": action_text})
    assert response.status_code == 200
    data = response.json()
    assert data["roll_request"] is None
    assert "Resolution" in data["narration"]["narration"]


def test_player_turn_includes_roll_request(monkeypatch, client):
    slug = client.post("/sessions", json={"slug": "roll-request"}).json()["slug"]

    async def fake_dm(settings, session_slug, state, before_state, player_intent, diff, include_discovery=False):
        choices = [
            DMChoice(id="A", text="Talk", intent_tag="talk", risk="low"),
            DMChoice(id="B", text="Sneak", intent_tag="sneak", risk="medium"),
            DMChoice(id="C", text="Fight", intent_tag="fight", risk="high"),
            DMChoice(id="D", text="Investigate", intent_tag="investigate", risk="medium"),
        ]
        dm = DMNarration(
            narration="Test scene. What do you do?",
            recap="recap",
            stakes="stakes",
            choices=choices,
            roll_request=RollRequest(kind="ability_check", ability="DEX", skill="stealth", dc=12, reason="Test roll"),
        )
        return dm, None

    monkeypatch.setattr(app_module, "generate_dm_narration", fake_dm)

    response = client.post(f"/sessions/{slug}/player/turn", json={"action": "I test"})
    assert response.status_code == 200
    data = response.json()
    assert data["roll_request"]["kind"] == "ability_check"
    assert data["roll_request"]["ability"] == "DEX"
