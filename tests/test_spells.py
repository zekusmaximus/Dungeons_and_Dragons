from pathlib import Path

from service import spells


def test_full_caster_slot_progression_bounds():
    assert spells.full_caster_slots(1) == {"1": 2}
    assert spells.full_caster_slots(5)["3"] == 2
    assert "9" in spells.full_caster_slots(20)
    # clamp
    assert spells.full_caster_slots(0) == {"1": 2}
    assert spells.full_caster_slots(30) == spells.full_caster_slots(20)


def test_reset_spell_slots_aliases_full():
    assert spells.reset_spell_slots(3) == spells.full_caster_slots(3)
    half = spells.reset_spell_slots(5, caster_type="half")
    assert half.get("2", 0) > 0
    third = spells.reset_spell_slots(7, caster_type="third")
    assert third.get("2", 0) >= 0


def test_spell_index_lookup(tmp_path):
    spells_path = tmp_path / "spells.json"
    spells_path.write_text(
        '[{"name":"Fire Bolt","level":0},{"name":"Cure Wounds","level":1}]',
        encoding="utf-8",
    )
    index = spells.spell_index_by_name(spells_path)
    assert "Fire Bolt" in index
    assert index["Cure Wounds"]["level"] == 1
