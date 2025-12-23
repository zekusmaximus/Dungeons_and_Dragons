def test_roll_flow_increments_log_index(client, session_slug):
    state_before = client.get(f"/api/sessions/{session_slug}/state").json()
    log_index_before = state_before["log_index"]

    roll_request = {"type": "ability_check", "ability": "STR"}
    roll_response = client.post(f"/api/sessions/{session_slug}/roll", json=roll_request)
    assert roll_response.status_code == 200
    roll_payload = roll_response.json()
    for key in ("d20", "total", "breakdown", "text"):
        assert key in roll_payload

    state_after = client.get(f"/api/sessions/{session_slug}/state").json()
    assert state_after["log_index"] == log_index_before + 1
