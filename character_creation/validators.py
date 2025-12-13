import json
from pathlib import Path
from typing import Dict, List

try:
    import jsonschema
except ImportError:  # pragma: no cover
    class _Dummy:
        @staticmethod
        def validate(instance, schema):
            return True

    jsonschema = _Dummy()


def _load_table(path: Path):
    return json.load(open(path, "r", encoding="utf-8"))


def validate_race(name: str, base_path: Path) -> Dict[str, object]:
    races = _load_table(base_path / "character_creation" / "tables" / "races.json")
    for race in races:
        if race.get("name") == name:
            required = ["name", "ability_modifiers", "size", "speed", "languages"]
            missing = [field for field in required if field not in race]
            if missing:
                raise ValueError(f"Race {name} missing fields: {missing}")
            return race
    raise ValueError(f"Unknown race: {name}")


def validate_class(name: str, base_path: Path) -> Dict[str, object]:
    classes = _load_table(base_path / "character_creation" / "tables" / "classes.json")
    for cls in classes:
        if cls.get("name") == name:
            required = ["name", "hit_die", "primary_ability", "saving_throws", "features"]
            missing = [field for field in required if field not in cls]
            if missing:
                raise ValueError(f"Class {name} missing fields: {missing}")
            return cls
    raise ValueError(f"Unknown class: {name}")


def validate_background(name: str, base_path: Path) -> Dict[str, object]:
    backgrounds = _load_table(base_path / "character_creation" / "tables" / "backgrounds.json")
    for bg in backgrounds:
        if bg.get("name") == name:
            required = ["name", "skill_proficiencies", "tool_proficiencies", "feature", "equipment"]
            missing = [field for field in required if field not in bg]
            if missing:
                raise ValueError(f"Background {name} missing fields: {missing}")
            return bg
    raise ValueError(f"Unknown background: {name}")


def validate_inventory(class_name: str, background_name: str, base_path: Path) -> List[str]:
    inventories = _load_table(base_path / "character_creation" / "tables" / "inventories.json")
    class_kits = inventories.get("class_kits", [])
    background_kits = inventories.get("background_kits", [])
    class_items = []
    background_items = []
    for kit in class_kits:
        if kit.get("class") == class_name:
            class_items = kit.get("items", [])
            break
    for kit in background_kits:
        if kit.get("background") == background_name:
            background_items = kit.get("items", [])
            break
    if not class_items:
        raise ValueError(f"No inventory kit for class {class_name}")
    if not background_items:
        raise ValueError(f"No inventory kit for background {background_name}")
    return class_items + background_items


def validate_abilities(abilities: Dict[str, int]):
    required = ["str", "dex", "con", "int", "wis", "cha"]
    missing = [a for a in required if a not in abilities]
    if missing:
        raise ValueError(f"Missing ability scores: {missing}")
    for key, value in abilities.items():
        if not isinstance(value, int):
            raise ValueError(f"Ability {key} must be int")
        if value < 1:
            raise ValueError(f"Ability {key} must be positive")
    return abilities


def validate_final_character(character: Dict[str, object], base_path: Path):
    schema = json.load(open(base_path / "schemas" / "character.schema.json", "r", encoding="utf-8"))
    jsonschema.validate(character, schema)
    return character

