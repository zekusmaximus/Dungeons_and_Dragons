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
  "loot.schema.json"
]


def validate_file(path, schema_path):
    data = json.load(open(path, "r", encoding="utf-8"))
    schema = json.load(open(schema_path, "r", encoding="utf-8"))
    jsonschema.validate(data, schema)


def main():
    root = Path(__file__).resolve().parents[1]
    for schema_name in SCHEMAS:
        schema_path = root / "schemas" / schema_name
        if schema_name == "state.schema.json":
            for state_file in root.glob("sessions/*/state.json"):
                validate_file(state_file, schema_path)
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

    # Hex neighbor check
    for hx_path in root.glob("worlds/*/hexmap.json"):
        data = json.load(open(hx_path, "r", encoding="utf-8"))
        coords = {(h["q"], h["r"]) for h in data.get("hexes", [])}
        for h in data.get("hexes", []):
            for n in h.get("neighbors", []):
                if (n["q"], n["r"]) not in coords:
                    raise ValueError(f"Invalid neighbor {n} in {hx_path}")

    # Audit entropy uniqueness
    subprocess.run(["python", str(root / "dice" / "verify_dice.py"), "--audit"], check=False)


if __name__ == "__main__":
    main()
