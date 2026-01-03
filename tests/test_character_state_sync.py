def test_character_state_patch_syncs_roll_and_ui(client, session_slug):
    preview_request = {
        "response": "I take the loot and catch my breath.",
        "state_patch": {
            "hp": 7,
            "max_hp": 12,
            "level": 2,
            "xp": 300,
            "ac": 14,
            "inventory": ["Torch", "Rope"],
            "spells": ["Mage Hand"],
            "abilities": {"str": 18, "dex": 14, "con": 12, "int": 10, "wis": 10, "cha": 10},
        },
        "transcript_entry": "Player takes loot and rests.",
        "dice_expressions": [],
    }
    preview_response = client.post(
        f"/api/sessions/{session_slug}/turn/preview",
        json=preview_request,
    )
    assert preview_response.status_code == 200
    preview_id = preview_response.json()["id"]

    commit_response = client.post(
        f"/api/sessions/{session_slug}/turn/commit",
        json={"preview_id": preview_id},
    )
    assert commit_response.status_code == 200

    bundle_response = client.get(f"/api/sessions/{session_slug}/player")
    assert bundle_response.status_code == 200
    bundle = bundle_response.json()

    state = bundle["state"]
    character = bundle["character"]

    assert state["hp"] == 7
    assert state["max_hp"] == 12
    assert state["level"] == 2
    assert state["xp"] == 300
    assert state["inventory"] == ["Torch", "Rope"]
    assert state["spells"] == ["Mage Hand"]

    assert character["hp"] == 7
    assert character["max_hp"] == 12
    assert character["level"] == 2
    assert character["experience"] == 300
    assert character["inventory"] == ["Torch", "Rope"]
    assert character["spells"] == ["Mage Hand"]
    assert character["abilities"]["str"] == 18
    assert character["ac"] == 14

    roll_request = {"kind": "ability_check", "ability": "STR"}
    roll_response = client.post(f"/api/sessions/{session_slug}/roll", json=roll_request)
    assert roll_response.status_code == 200
    roll_payload = roll_response.json()
    assert roll_payload["total"] == 5
    assert "+4 (STR)" in roll_payload["breakdown"]
