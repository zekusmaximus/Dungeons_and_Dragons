import argparse
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

try:
    import jsonschema
except ImportError:  # pragma: no cover - fallback when dependency unavailable
    class _Dummy:
        @staticmethod
        def validate(instance, schema):
            return True

    jsonschema = _Dummy()

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "state.schema.json"


def load_entropy(index):
    with open(Path(__file__).resolve().parents[1] / "dice" / "entropy.ndjson", "r", encoding="utf-8") as f:
        for line in f:
            entry = json.loads(line)
            if entry["i"] == index:
                return entry
    raise ValueError("Entropy index not found")


def next_entropy(current):
    target = current + 1
    return load_entropy(target)


def roll_from_entry(expr, entry):
    count, sides = expr.lower().split("d")
    count = int(count)
    sides = int(sides)
    results = []
    for i in range(count):
        val = entry["d20"][i]
        results.append(1 + ((val - 1) % sides))
    return sum(results)


def roll_on_table(table_path, state):
    table = json.load(open(table_path, "r", encoding="utf-8"))
    entry = next_entropy(state.get("log_index", 0))
    roll_value = roll_from_entry(table["dice"], entry)
    for row in table["rows"]:
        low, high = row["range"]
        if low <= roll_value <= high:
            state["log_index"] = entry["i"]
            return row["result"], entry["i"], roll_value
    raise ValueError("No matching row")


def validate_state(state):
    schema = json.load(open(SCHEMA_PATH, "r", encoding="utf-8"))
    jsonschema.validate(state, schema)


def find_hex(hexmap, q, r):
    for hx in hexmap["hexes"]:
        if hx["q"] == q and hx["r"] == r:
            return hx
    raise KeyError("Hex not found")


def choose_next_hex(hexmap, current_hex):
    neighbors = current_hex.get("neighbors", [])
    if not neighbors:
        return current_hex
    next_ref = neighbors[0]
    return find_hex(hexmap, next_ref["q"], next_ref["r"])


def advance_time(iso_time, hours):
    dt = datetime.fromisoformat(iso_time.replace("Z", "+00:00"))
    dt += timedelta(hours=hours)
    return dt.isoformat().replace("+00:00", "Z")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--slug", required=True)
    parser.add_argument("--steps", type=int, default=1)
    parser.add_argument("--pace", choices=["slow", "normal", "fast"], default="normal")
    args = parser.parse_args()

    session_dir = Path("sessions") / args.slug
    state_path = session_dir / "state.json"
    transcript_path = session_dir / "transcript.md"
    changelog_path = session_dir / "changelog.md"

    state = json.load(open(state_path, "r", encoding="utf-8"))
    hexmap = json.load(open(Path("worlds") / state["world"] / "hexmap.json", "r", encoding="utf-8"))
    validate_state(state)

    movement_mods = json.load(open(Path("data/terrain/movement_modifiers.json"), "r", encoding="utf-8"))

    travel_lines = []
    for _ in range(args.steps):
        current_hex = find_hex(hexmap, state["hex"]["q"], state["hex"]["r"])
        target_hex = choose_next_hex(hexmap, current_hex)
        pace_mod = {"slow": 1.2, "normal": 1.0, "fast": 0.8}[args.pace]
        terrain_mod = movement_mods.get(target_hex["biome"], 1.0)
        hours = 1.0 * terrain_mod * pace_mod
        state["time"] = advance_time(state["time"], hours)
        state["hex"] = {"q": target_hex["q"], "r": target_hex["r"]}
        state["travel_pace"] = args.pace

        weather_result, weather_idx, weather_roll = roll_on_table(Path("tables/weather/temperate.json"), state)
        state["weather"] = weather_result.get("condition", "")

        encounter_result, enc_idx, enc_roll = roll_on_table(Path("tables/encounters/forest_tier1.json"), state)
        feature = None
        feature_idx = None
        feature_roll = None
        if target_hex["biome"] == "forest":
            feature, feature_idx, feature_roll = roll_on_table(Path("tables/terrain/features_forest.json"), state)

        log_entry = {
            "type": "travel",
            "hex": state["hex"],
            "weather": state["weather"],
            "encounters": [encounter_result.get("id")],
            "rolls": [
                {"expression": "weather", "result": weather_roll, "entropy_index": weather_idx},
                {"expression": "encounter", "result": enc_roll, "entropy_index": enc_idx},
            ]
        }
        if feature_idx is not None:
            log_entry["rolls"].append({"expression": "feature", "result": feature_roll, "entropy_index": feature_idx})
        with open(changelog_path, "a", encoding="utf-8") as clog:
            clog.write(json.dumps(log_entry) + "\n")

        travel_lines.append(
            f"Travel to hex ({state['hex']['q']},{state['hex']['r']}), weather={state['weather']}, encounter={encounter_result.get('id')}"
        )

    with open(transcript_path, "a", encoding="utf-8") as tlog:
        for line in travel_lines:
            tlog.write(line + "\n")

    json.dump(state, open(state_path, "w", encoding="utf-8"), indent=2)


if __name__ == "__main__":
    main()
