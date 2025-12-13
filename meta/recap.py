import argparse
import json
from pathlib import Path
from typing import List


def tail_lines(path: Path, count: int) -> List[str]:
    if not path.exists():
        return []
    with path.open() as handle:
        lines = [line.strip() for line in handle.readlines() if line.strip()]
    return lines[-count:]


def load_changelog(slug: str) -> List[str]:
    path = Path("sessions") / slug / "changelog.md"
    return tail_lines(path, 50)


def extract_faction_updates(changelog_lines: List[str]) -> List[str]:
    return [line for line in changelog_lines if "[faction:update]" in line]


def load_state(slug: str) -> dict:
    path = Path("sessions") / slug / "state.json"
    if not path.exists():
        return {}
    with path.open() as handle:
        return json.load(handle)


def load_npc_memory(slug: str) -> List[str]:
    path = Path("sessions") / slug / "npc_memory.json"
    if not path.exists():
        return []
    with path.open() as handle:
        data = json.load(handle)
    return [f"{entry.get('name')}: {entry.get('impression')}" for entry in data.get("npcs", [])]


def main():
    parser = argparse.ArgumentParser(description="Generate a quick recap for a session")
    parser.add_argument("--slug", required=True)
    args = parser.parse_args()

    transcript_lines = tail_lines(Path("sessions") / args.slug / "transcript.md", 5)
    faction_updates = extract_faction_updates(load_changelog(args.slug))[-5:]
    state = load_state(args.slug)
    quests = state.get("quests", {}) if state else {}
    npc_notes = load_npc_memory(args.slug)

    recap = {
        "recent_scenes": transcript_lines,
        "last_faction_updates": faction_updates,
        "active_quests": quests,
        "npc_relationships": npc_notes
    }
    print(json.dumps(recap, indent=2))


if __name__ == "__main__":
    main()
