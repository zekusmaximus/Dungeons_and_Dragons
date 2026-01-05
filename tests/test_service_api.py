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
