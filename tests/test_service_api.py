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
