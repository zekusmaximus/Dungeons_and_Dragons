def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert "status" in payload


def test_session_create_and_state(client, session_slug):
    response = client.get(f"/api/sessions/{session_slug}/state")
    assert response.status_code == 200
    payload = response.json()
    assert "turn" in payload
    assert "log_index" in payload
    assert "world" in payload
    assert isinstance(payload["turn"], int)
    assert isinstance(payload["log_index"], int)
    assert payload["turn"] == 0
    assert payload["log_index"] == 0


def test_player_bundle_shape(client, session_slug):
    response = client.get(f"/api/sessions/{session_slug}/player")
    assert response.status_code == 200
    payload = response.json()
    for key in ("state", "character", "recaps", "discoveries", "quests", "suggestions"):
        assert key in payload


def test_events_stream_initial_update(client, session_slug):
    with client.stream(
        "GET",
        f"/api/events/{session_slug}",
        params={"transcript_cursor": -1, "changelog_cursor": -1},
    ) as stream:
        data_line = None
        for line in stream.iter_lines():
            if not line:
                continue
            text = line.decode() if isinstance(line, (bytes, bytearray)) else str(line)
            if text.startswith("data:"):
                data_line = text
                break
        assert data_line is not None
        assert data_line.startswith("data:")


def test_rest_endpoints_reset_hp_and_slots(client, session_slug):
    # claim lock
    lock_resp = client.post(f"/api/sessions/{session_slug}/lock/claim", json={"owner": "tester", "ttl": 300})
    assert lock_resp.status_code == 200

    # set low hp and empty slots via preview/commit
    preview = client.post(
        f"/api/sessions/{session_slug}/turn/preview",
        json={
            "response": "testing rest",
            "state_patch": {"hp": 1, "max_hp": 10, "spell_slots": {"1": 0}},
            "transcript_entry": "setup",
            "dice_expressions": [],
            "lock_owner": "tester",
        },
    )
    assert preview.status_code == 200
    preview_id = preview.json()["id"]
    commit = client.post(f"/api/sessions/{session_slug}/turn/commit", json={"preview_id": preview_id, "lock_owner": "tester"})
    assert commit.status_code == 200

    rest_resp = client.post(f"/api/sessions/{session_slug}/rest/long", json={"lock_owner": "tester"})
    assert rest_resp.status_code == 200
    state = rest_resp.json()["state"]
    assert state["hp"] == 10
    assert state["spell_slots"]["1"] >= 2


def test_spells_endpoint_filters(client):
    resp = client.get("/api/spells", params={"name": "fire"})
    assert resp.status_code == 200
    payload = resp.json()
    assert "spells" in payload
    assert any("fire" in spell["name"].lower() for spell in payload["spells"])
