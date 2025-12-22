def test_preview_commit_flow(client, session_slug):
    state_before = client.get(f"/sessions/{session_slug}/state").json()
    log_index_before = state_before["log_index"]
    turn_before = state_before["turn"]

    preview_request = {
        "response": "I look around.",
        "state_patch": {"location": "The Test Camp"},
        "transcript_entry": "Player looks around.",
        "changelog_entry": "Moved to The Test Camp.",
        "dice_expressions": ["1d20", "1d20"],
    }
    preview_response = client.post(
        f"/sessions/{session_slug}/turn/preview",
        json=preview_request,
    )
    assert preview_response.status_code == 200
    preview_payload = preview_response.json()
    assert "id" in preview_payload
    assert "entropy_plan" in preview_payload
    assert preview_payload["entropy_plan"]["indices"] == [log_index_before + 1, log_index_before + 2]

    commit_response = client.post(
        f"/sessions/{session_slug}/turn/commit",
        json={"preview_id": preview_payload["id"]},
    )
    assert commit_response.status_code == 200
    commit_payload = commit_response.json()
    assert commit_payload["state"]["turn"] == turn_before + 1
    assert commit_payload["state"]["log_index"] == log_index_before + 2

    transcript_response = client.get(
        f"/sessions/{session_slug}/transcript",
        params={"tail": 1},
    )
    assert transcript_response.status_code == 200
    transcript_payload = transcript_response.json()
    assert "items" in transcript_payload
    assert "cursor" in transcript_payload
    assert transcript_payload["items"][-1]["text"] == preview_request["transcript_entry"]

    changelog_response = client.get(
        f"/sessions/{session_slug}/changelog",
        params={"tail": 1},
    )
    assert changelog_response.status_code == 200
    changelog_payload = changelog_response.json()
    assert "items" in changelog_payload
    assert "cursor" in changelog_payload
    assert changelog_payload["items"][-1]["text"] == preview_request["changelog_entry"]
