#!/usr/bin/env python3
"""Validate characters, monsters, and session state against schemas."""
import json
import sys
from pathlib import Path
from jsonschema import validate, ValidationError

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = {
  "character": REPO_ROOT / "schemas" / "character.schema.json",
  "state": REPO_ROOT / "schemas" / "state.schema.json",
  "log": REPO_ROOT / "schemas" / "log_entry.schema.json",
}


def load_json(path: Path):
    with path.open() as f:
        return json.load(f)


def validate_file(path: Path, schema_path: Path):
    try:
        validate(instance=load_json(path), schema=load_json(schema_path))
        return True, None
    except ValidationError as exc:
        return False, exc.message


def main():
    errors = []
    # Characters
    char_schema = SCHEMAS["character"]
    for char_file in (REPO_ROOT / "data" / "characters").glob("*.json"):
        ok, msg = validate_file(char_file, char_schema)
        if not ok:
            errors.append(f"Character {char_file.name}: {msg}")
    # States
    state_schema = SCHEMAS["state"]
    for state_file in REPO_ROOT.glob("sessions/*/state.json"):
        ok, msg = validate_file(state_file, state_schema)
        if not ok:
            errors.append(f"State {state_file}: {msg}")
    # Logs
    log_schema = SCHEMAS["log"]
    for log_file in REPO_ROOT.glob("sessions/*/changelog.md"):
        with log_file.open() as f:
            for line_no, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError as exc:
                    errors.append(f"Log {log_file} line {line_no}: invalid JSON ({exc})")
                    continue
                ok, msg = validate_file(log_file.parent / f"_tmp_log_{line_no}.json", log_schema) if False else (True, None)
                try:
                    validate(instance=entry, schema=load_json(log_schema))
                except ValidationError as exc:
                    errors.append(f"Log {log_file} line {line_no}: {exc.message}")
    if errors:
        print("VALIDATION FAILED:")
        for err in errors:
            print(f" - {err}")
        sys.exit(1)
    print("All files validate cleanly.")


if __name__ == "__main__":
    main()
