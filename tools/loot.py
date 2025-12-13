import argparse
import json
from pathlib import Path
from tools.explore import roll_on_table


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--slug", required=True)
    args = parser.parse_args()

    session_dir = Path("sessions") / args.slug
    state_path = session_dir / "state.json"
    transcript_path = session_dir / "transcript.md"
    changelog_path = session_dir / "changelog.md"
    loot_dir = session_dir / "loot"
    loot_dir.mkdir(exist_ok=True)

    state = json.load(open(state_path, "r", encoding="utf-8"))
    loot_result, idx, roll_val = roll_on_table(Path("tables/treasure/hoard_tier1.json"), state)
    state["gp"] = state.get("gp", 0) + loot_result.get("gp", 0)
    inventory = state.get("flags", {}).get("inventory", [])
    inventory.extend(loot_result.get("items", []))
    state.setdefault("flags", {})["inventory"] = inventory

    loot_entry = {
        "id": f"loot-{idx}",
        "items": loot_result.get("items", []),
        "gp": loot_result.get("gp", 0),
    }
    loot_path = loot_dir / f"{loot_entry['id']}.json"
    json.dump(loot_entry, open(loot_path, "w", encoding="utf-8"), indent=2)

    with open(transcript_path, "a", encoding="utf-8") as tlog:
        tlog.write(f"Loot gathered: +{loot_entry['gp']} gp, items={', '.join(loot_entry['items'])}.\n")

    with open(changelog_path, "a", encoding="utf-8") as clog:
        clog.write(json.dumps({"type": "loot", "rolls": [{"expression": "loot", "result": roll_val, "entropy_index": idx}]}) + "\n")

    json.dump(state, open(state_path, "w", encoding="utf-8"), indent=2)


if __name__ == "__main__":
    main()
