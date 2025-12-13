import argparse
import json
from pathlib import Path
from tools.explore import next_entropy, roll_from_entry

OUTCOMES = {
    "train": "gains a skill edge",
    "craft": "creates a modest item",
    "carouse": "makes colorful contacts",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--slug", required=True)
    parser.add_argument("--activity", choices=list(OUTCOMES.keys()), required=True)
    args = parser.parse_args()

    session_dir = Path("sessions") / args.slug
    state_path = session_dir / "state.json"
    transcript_path = session_dir / "transcript.md"
    changelog_path = session_dir / "changelog.md"

    state = json.load(open(state_path, "r", encoding="utf-8"))
    entry = next_entropy(state.get("log_index", 0))
    roll_val = roll_from_entry("1d20", entry)
    state["log_index"] = entry["i"]

    cost = 10
    state["gp"] = max(0, state.get("gp", 0) - cost)

    outcome = OUTCOMES[args.activity]
    with open(transcript_path, "a", encoding="utf-8") as tlog:
        tlog.write(f"Downtime {args.activity}: {outcome} (roll {roll_val}).\n")

    with open(changelog_path, "a", encoding="utf-8") as clog:
        clog.write(
            json.dumps(
                {
                    "type": "downtime",
                    "activity": args.activity,
                    "rolls": [{"expression": args.activity, "result": roll_val, "entropy_index": entry["i"]}],
                }
            )
            + "\n"
        )

    json.dump(state, open(state_path, "w", encoding="utf-8"), indent=2)


if __name__ == "__main__":
    main()
