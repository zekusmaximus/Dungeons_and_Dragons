import json
from pathlib import Path

import pytest


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _seed_entropy(path: Path, count: int = 10) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for idx in range(1, count + 1):
        lines.append(json.dumps({"i": idx, "d20": [idx, idx + 1]}))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


@pytest.fixture(params=["file", "sqlite"])
def repo_root(tmp_path, monkeypatch, request):
    sessions_dir = tmp_path / "sessions"
    data_dir = tmp_path / "data"
    worlds_dir = tmp_path / "worlds"
    dice_path = tmp_path / "dice" / "entropy.ndjson"

    template_slug = "example-rogue"
    template_dir = sessions_dir / template_slug
    template_state = {
        "character": template_slug,
        "turn": 0,
        "scene_id": "init",
        "location": "Test Location",
        "hp": 10,
        "conditions": [],
        "flags": {},
        "log_index": 0,
        "level": 1,
        "xp": 0,
        "inventory": [],
        "world": "default",
    }
    _write_json(template_dir / "state.json", template_state)

    template_character = {
        "slug": template_slug,
        "name": "Test Hero",
        "race": "Human",
        "class": "Rogue",
        "background": "Urchin",
        "level": 1,
        "hp": 10,
        "ac": 12,
        "abilities": {"str": 10, "dex": 14, "con": 10, "int": 10, "wis": 10, "cha": 10},
        "skills": {},
        "inventory": [],
        "starting_equipment": [],
        "features": [],
        "proficiencies": {"skills": [], "tools": [], "languages": []},
        "notes": "",
        "creation_source": "dm",
    }
    _write_json(data_dir / "characters" / f"{template_slug}.json", template_character)

    worlds_dir.mkdir(parents=True, exist_ok=True)
    (worlds_dir / "default").mkdir(parents=True, exist_ok=True)
    _seed_entropy(dice_path)

    backend_name = request.param
    db_path = tmp_path / "dm.sqlite"

    monkeypatch.setenv("DM_SERVICE_REPO_ROOT", str(tmp_path))
    monkeypatch.setenv("DM_SERVICE_SESSIONS_DIR", "sessions")
    monkeypatch.setenv("DM_SERVICE_DATA_DIR", "data")
    monkeypatch.setenv("DM_SERVICE_WORLDS_DIR", "worlds")
    monkeypatch.setenv("DM_SERVICE_DICE_FILE", "dice/entropy.ndjson")
    monkeypatch.setenv("STORAGE_BACKEND", backend_name)
    if backend_name == "sqlite":
        monkeypatch.setenv("DATABASE_URL", str(db_path))
    else:
        monkeypatch.delenv("DATABASE_URL", raising=False)

    from service.config import get_settings

    get_settings.cache_clear()
    return tmp_path


@pytest.fixture()
def client(repo_root):
    from fastapi.testclient import TestClient
    from service.app import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def session_slug(client):
    payload = {"slug": "test-session", "template_slug": "example-rogue"}
    response = client.post("/sessions", json=payload)
    assert response.status_code == 201
    return response.json()["slug"]
