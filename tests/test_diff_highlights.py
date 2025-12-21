from service.diff_highlights import summarize_diff, derive_consequence_echo


def test_summarize_diff_returns_categories():
    before = {
        "hp": 10,
        "location": "camp",
        "inventory": ["rope"],
        "quests": {"rescue": {"status": "open"}},
        "flags": {"clocks": {"threat": 1}, "relationships": {"ally": "warm"}},
    }
    after = {
        "hp": 7,
        "location": "caves",
        "inventory": ["rope", "gem"],
        "quests": {"rescue": {"status": "complete"}},
        "flags": {"clocks": {"threat": 2}, "relationships": {"ally": "strained"}},
    }
    diff = ["hp: 10 -> 7", "location: camp -> caves", "inventory gained gem"]

    highlights = summarize_diff(diff, before, after)

    assert highlights["hp"][0].startswith("HP 10 -> 7")
    assert any("Location shifts" in item for item in highlights["location"])
    assert any("Picked up" in item for item in highlights["inventory_added"])
    assert highlights["quests"]
    assert highlights["clocks"]
    assert highlights["relationships"]
    assert "inventory gained gem" in highlights["inventory_added"]


def test_consequence_echo_uses_highlights():
    highlights = {
        "hp": ["HP 5 -> 3 (-2)"],
        "location": ["Location shifts from road to keep"],
        "inventory_added": [],
        "inventory_removed": [],
        "quests": [],
        "clocks": [],
        "relationships": [],
        "other": [],
    }
    echo = derive_consequence_echo("", highlights, "Narration sentence.", ["hp changed"])
    assert "HP 5 -> 3" in echo
