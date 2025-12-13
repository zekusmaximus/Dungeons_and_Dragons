import argparse
import json
from datetime import datetime
from pathlib import Path
from shutil import copyfile


def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open() as handle:
        return json.load(handle)


def save_json(path: Path, payload: dict):
    with path.open("w") as handle:
        json.dump(payload, handle, indent=2)


def snapshot(slug: str):
    session_dir = Path("sessions") / slug
    timestamp = datetime.utcnow().isoformat().replace(":", "-")
    target = session_dir / "snapshots" / timestamp
    ensure_dir(target)

    state = load_json(session_dir / "state.json")
    character = load_json(Path("data") / "characters" / f"{slug}.json")
    quests = state.get("quests", {}) if state else {}

    save_json(target / "state.json", state)
    save_json(target / "character.json", character)
    save_json(target / "quests.json", quests)

    world = state.get("world", "default") if state else "default"
    world_dir = Path("worlds") / world
    faction_path = world_dir / "factions.json"
    timeline_path = world_dir / "timeline.json"
    faction_data = load_json(faction_path)
    timeline_data = load_json(timeline_path)
    save_json(target / "faction_standings.json", faction_data)
    save_json(target / "timeline_state.json", timeline_data)

    maps_dir = world_dir / "maps"
    if maps_dir.exists():
        maps = [p.name for p in maps_dir.glob("*.json")]
    else:
        maps = []
    save_json(target / "location_maps.json", {"maps": maps})

    source_transcript = session_dir / "transcript.md"
    if source_transcript.exists():
        copyfile(source_transcript, target / "transcript.md")

    return target


def main():
    parser = argparse.ArgumentParser(description="Create deterministic save snapshots")
    parser.add_argument("--slug", required=True)
    args = parser.parse_args()
    path = snapshot(args.slug)
    print(f"Snapshot created at {path}")


if __name__ == "__main__":
    main()
