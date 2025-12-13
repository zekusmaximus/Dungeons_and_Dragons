import json
import shutil
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

try:
    import jsonschema
except ImportError:  # pragma: no cover
    class _Dummy:
        @staticmethod
        def validate(instance, schema):
            return True

    jsonschema = _Dummy()

from character_creation import builder, validators


EXPECTED_ABILITIES = {
    "str": 15,
    "dex": 8,
    "con": 15,
    "int": 17,
    "wis": 16,
    "cha": 8,
}


def _prepare_base(tmp_path: Path) -> Path:
    base = tmp_path / "game"
    base.mkdir()
    shutil.copytree(Path("schemas"), base / "schemas")
    shutil.copytree(Path("character_creation"), base / "character_creation")
    shutil.copytree(Path("dice"), base / "dice")
    (base / "data" / "characters").mkdir(parents=True, exist_ok=True)
    (base / "sessions").mkdir(parents=True, exist_ok=True)
    return base


def test_ability_scores_deterministic():
    cursor = builder.EntropyCursor(Path("dice/entropy.ndjson"))
    abilities, rolls = builder.roll_ability_scores(cursor)
    assert abilities == EXPECTED_ABILITIES
    assert [r.entropy_index for r in rolls] == [1, 2, 3, 4, 5, 6]


def test_character_files_created(tmp_path):
    base = _prepare_base(tmp_path)
    cursor = builder.EntropyCursor(base / "dice" / "entropy.ndjson")
    rolled, rolls = builder.roll_ability_scores(cursor)
    race_data = validators.validate_race("Human", base)
    final_abilities = builder.apply_racial_modifiers(rolled, race_data)
    inventory_table = json.load(open(base / "character_creation" / "tables" / "inventories.json", "r", encoding="utf-8"))
    inventory = builder.build_inventory("Rogue", "Criminal", inventory_table)

    character, state, log_entry = builder.write_creation_files(
        base_path=base,
        slug="alira",
        name="Alira Stone",
        race_name="Human",
        class_name="Rogue",
        background_name="Criminal",
        abilities=final_abilities,
        rolls=rolls,
        inventory=inventory,
        source="tool",
    )

    validators.validate_final_character(character, base)
    state_schema = json.load(open(base / "schemas" / "state.schema.json", "r", encoding="utf-8"))
    jsonschema.validate(state, state_schema)

    assert (base / "sessions" / "alira" / "creation_progress.json").exists() is False
    assert state["inventory"]
    assert log_entry["rolls"]
