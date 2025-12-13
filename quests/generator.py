import argparse
import json
from pathlib import Path
from tools.explore import next_entropy, roll_from_entry


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--slug", required=True)
    parser.add_argument("--template", required=True)
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    session_dir = root / "sessions" / args.slug
    transcript_path = session_dir / "transcript.md"
    changelog_path = session_dir / "changelog.md"

    template = json.load(open(root / "quests" / "templates" / f"{args.template}.json", "r", encoding="utf-8"))
    entry = next_entropy(json.load(open(session_dir / "state.json"))["log_index"])
    state_path = session_dir / "state.json"
    state = json.load(open(state_path))
    state["log_index"] = entry["i"]

    world = json.load(open(root / "worlds" / state["world"] / "hexmap.json", "r", encoding="utf-8"))
    quest_nodes = []
    for node in template["nodes"]:
        for hx in world["hexes"]:
            if hx["biome"] == node["biome"]:
                quest_nodes.append({"id": node["id"], "hex": {"q": hx["q"], "r": hx["r"]}, "biome": node["biome"], "description": node.get("description", "")})
                break

    quest_id = f"quest-{entry['i']}"
    quest = {
        "id": quest_id,
        "name": template["name"],
        "status": "active",
        "objectives": template["objectives"],
        "nodes": quest_nodes,
    }
    quests_dir = session_dir / "quests"
    quests_dir.mkdir(exist_ok=True)
    json.dump(quest, open(quests_dir / f"{quest_id}.json", "w", encoding="utf-8"), indent=2)
    state.setdefault("quests", {})[quest_id] = {"status": "active"}
    json.dump(state, open(state_path, "w", encoding="utf-8"), indent=2)

    with open(transcript_path, "a", encoding="utf-8") as tlog:
        tlog.write(
            " ".join(
                [
                    "A patron seeks aid recovering a relic from a forest ruin.",
                    "Leads point toward an overgrown shrine and a pursuit across nearby hills.",
                    "The prize could sway local druidic circles.",
                    "Rumors mention competing hunters and ancient wards.",
                    "Speed and discretion are rewarded."
                ]
            )
            + "\n"
        )

    with open(changelog_path, "a", encoding="utf-8") as clog:
        clog.write(
            json.dumps(
                {
                    "type": "quest_init",
                    "template": template["id"],
                    "nodes": [n["id"] for n in quest_nodes],
                    "entropy_index": entry["i"],
                }
            )
            + "\n"
        )


if __name__ == "__main__":
    main()
