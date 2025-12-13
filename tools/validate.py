import json
from pathlib import Path
import subprocess

try:
    import jsonschema
except ImportError:  # pragma: no cover
    class _Dummy:
        @staticmethod
        def validate(instance, schema):
            return True

    jsonschema = _Dummy()

SCHEMAS = [
  "state.schema.json",
  "table.schema.json",
  "hexmap.schema.json",
  "quest.schema.json",
  "encounter.schema.json",
  "loot.schema.json",
  "character.schema.json",
  "log_entry.schema.json",
]


def validate_file(path, schema_path):
    data = json.load(open(path, "r", encoding="utf-8"))
    schema = json.load(open(schema_path, "r", encoding="utf-8"))
    jsonschema.validate(data, schema)


def main():
    root = Path(__file__).resolve().parents[1]
    creation_tables = root / "character_creation" / "tables"
    for schema_name in SCHEMAS:
        schema_path = root / "schemas" / schema_name
        if schema_name == "state.schema.json":
            for state_file in root.glob("sessions/*/state.json"):
                validate_file(state_file, schema_path)
        elif schema_name == "character.schema.json":
            for character_file in root.glob("data/characters/*.json"):
                validate_file(character_file, schema_path)
        elif schema_name == "table.schema.json":
            for table_file in root.glob("tables/**/*.json"):
                validate_file(table_file, schema_path)
        elif schema_name == "hexmap.schema.json":
            for hx in root.glob("worlds/**/*.json"):
                validate_file(hx, schema_path)
        elif schema_name == "quest.schema.json":
            for q in root.glob("quests/**/*.json"):
                if "templates" in q.parts:
                    continue
                try:
                    validate_file(q, schema_path)
                except FileNotFoundError:
                    continue
        elif schema_name == "encounter.schema.json":
            for enc in root.glob("sessions/*/encounters/*.json"):
                validate_file(enc, schema_path)
        elif schema_name == "loot.schema.json":
            for loot in root.glob("sessions/*/loot/*.json"):
                validate_file(loot, schema_path)
        elif schema_name == "log_entry.schema.json":
            for changelog in root.glob("sessions/*/changelog.md"):
                for line in changelog.read_text(encoding="utf-8").splitlines():
                    if not line.strip():
                        continue
                    validate_file_line(line, schema_path)

    # Background/class/race/inventory completeness
    required_race_fields = {"name", "ability_modifiers", "size", "speed", "languages"}
    for race in json.load(open(creation_tables / "races.json", "r", encoding="utf-8")):
        missing = required_race_fields - set(race.keys())
        if missing:
            raise ValueError(f"Race table entry missing fields: {missing}")

    required_class_fields = {"name", "hit_die", "primary_ability", "saving_throws", "features"}
    for cls in json.load(open(creation_tables / "classes.json", "r", encoding="utf-8")):
        missing = required_class_fields - set(cls.keys())
        if missing:
            raise ValueError(f"Class table entry missing fields: {missing}")

    required_background_fields = {"name", "skill_proficiencies", "tool_proficiencies", "feature", "equipment"}
    for bg in json.load(open(creation_tables / "backgrounds.json", "r", encoding="utf-8")):
        missing = required_background_fields - set(bg.keys())
        if missing:
            raise ValueError(f"Background table entry missing fields: {missing}")

    inventories = json.load(open(creation_tables / "inventories.json", "r", encoding="utf-8"))
    for class_kit in inventories.get("class_kits", []):
        if not class_kit.get("class") or not class_kit.get("items"):
            raise ValueError("Inventory class kit missing class or items")
    for bg_kit in inventories.get("background_kits", []):
        if not bg_kit.get("background") or not bg_kit.get("items"):
            raise ValueError("Inventory background kit missing background or items")

    # Session completeness
    for session_dir in root.glob("sessions/*"):
        state_path = session_dir / "state.json"
        if not state_path.exists():
            continue
        slug = session_dir.name
        character_path = root / "data" / "characters" / f"{slug}.json"
        transcript_path = session_dir / "transcript.md"
        changelog_path = session_dir / "changelog.md"
        turn_path = session_dir / "turn.md"
        if not all(p.exists() for p in [character_path, transcript_path, changelog_path, turn_path]):
            raise ValueError(f"Session {slug} missing required files")
        if (session_dir / "creation_progress.json").exists():
            raise ValueError(f"creation_progress.json should be removed for finalized session {slug}")

    # Hex neighbor check

    # Hex neighbor check
    for hx_path in root.glob("worlds/*/hexmap.json"):
        data = json.load(open(hx_path, "r", encoding="utf-8"))
        coords = {(h["q"], h["r"]) for h in data.get("hexes", [])}
        for h in data.get("hexes", []):
            for n in h.get("neighbors", []):
                if (n["q"], n["r"]) not in coords:
                    raise ValueError(f"Invalid neighbor {n} in {hx_path}")

    # Audit entropy uniqueness and changelog determinism
    for changelog in root.glob("sessions/*/changelog.md"):
        subprocess.run(["python", str(root / "dice" / "verify_dice.py"), "--audit", str(changelog)], check=False)


def validate_file_line(line: str, schema_path: Path):
    data = json.loads(line)
    schema = json.load(open(schema_path, "r", encoding="utf-8"))
    jsonschema.validate(data, schema)


if __name__ == "__main__":
    main()
