import argparse
import json
from pathlib import Path
from datetime import datetime

from tools.explore import next_entropy, roll_from_entry


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--slug", required=True)
    parser.add_argument("--monster", required=True)
    args = parser.parse_args()

    session_dir = Path("sessions") / args.slug
    state_path = session_dir / "state.json"
    transcript_path = session_dir / "transcript.md"
    changelog_path = session_dir / "changelog.md"

    state = json.load(open(state_path, "r", encoding="utf-8"))
    monster = json.load(open(args.monster, "r", encoding="utf-8"))

    entry = next_entropy(state.get("log_index", 0))
    initiative_player = roll_from_entry("1d20", entry)
    initiative_monster = roll_from_entry("1d20", entry)
    state["log_index"] = entry["i"]

    entry2 = next_entropy(state.get("log_index", 0))
    attack_roll = roll_from_entry("1d20", entry2) + 5
    damage = roll_from_entry("1d6", entry2) + 3
    state["log_index"] = entry2["i"]

    monster_ac = monster.get("armor_class", 10)
    hit = attack_roll >= monster_ac
    monster_hp = monster.get("hit_points", 1)
    monster_hp = monster_hp - damage if hit else monster_hp

    encounter_log = {
        "stamp": datetime.utcnow().isoformat() + "Z",
        "rounds": [
            {
                "order": ["player", monster.get("name", "monster")],
                "actions": [
                    {
                        "actor": "player",
                        "attack_roll": attack_roll,
                        "damage": damage,
                        "hit": hit,
                        "target": monster.get("name", "monster"),
                    }
                ],
            }
        ],
        "outcome": "hit" if hit else "miss",
        "rolls": [
            {"expression": "initiative", "result": initiative_player, "entropy_index": entry["i"]},
            {"expression": "initiative_monster", "result": initiative_monster, "entropy_index": entry["i"]},
            {"expression": "attack", "result": attack_roll, "entropy_index": entry2["i"]},
            {"expression": "damage", "result": damage, "entropy_index": entry2["i"]},
        ],
    }

    encounters_dir = session_dir / "encounters"
    encounters_dir.mkdir(exist_ok=True)
    encounter_path = encounters_dir / f"{encounter_log['stamp'].replace(':','-')}\.json"
    json.dump(encounter_log, open(encounter_path, "w", encoding="utf-8"), indent=2)

    with open(transcript_path, "a", encoding="utf-8") as tlog:
        tlog.write(
            f"Encounter with {monster.get('name','foe')}: attack {attack_roll} vs AC {monster_ac}, damage {damage if hit else 0}.\n"
        )

    with open(changelog_path, "a", encoding="utf-8") as clog:
        clog.write(json.dumps({"type": "encounter", "rolls": encounter_log["rolls"]}) + "\n")

    json.dump(state, open(state_path, "w", encoding="utf-8"), indent=2)


if __name__ == "__main__":
    main()
