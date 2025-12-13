#!/usr/bin/env python3
"""Schema-safe state patcher.

Usage:
  python tools/migrate_state.py <slug> < patch.json
"""
import json
import sys
from pathlib import Path
from jsonschema import validate, ValidationError

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "schemas" / "state.schema.json"


def load_json(path: Path):
    with path.open() as f:
        return json.load(f)


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    slug = sys.argv[1]
    state_path = REPO_ROOT / "sessions" / slug / "state.json"
    if not state_path.exists():
        sys.exit(f"Missing state file: {state_path}")

    try:
        patch = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        sys.exit(f"Invalid JSON patch: {exc}")

    state = load_json(state_path)
    state.update(patch)

    schema = load_json(SCHEMA_PATH)
    try:
        validate(instance=state, schema=schema)
    except ValidationError as exc:
        sys.exit(f"Schema validation failed: {exc.message}")

    with state_path.open("w") as f:
        json.dump(state, f, indent=2)
        f.write("\n")
    print(f"State updated for {slug}")


if __name__ == "__main__":
    main()
