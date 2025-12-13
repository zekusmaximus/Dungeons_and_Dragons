import argparse
import json
import random
from pathlib import Path

MONSTER_TABLE = {
    "dungeon_basic": ["goblin sentry", "animated armor", "skeletal guard"],
    "cave_complex": ["giant bat", "ooze", "bog lurker"],
    "haunted_ruin": ["restless spirit", "shadow", "possessed acolyte"],
}

TRAP_TABLE = {
    "dungeon_basic": ["tripwire darts", "falling net"],
    "cave_complex": ["unstable ledge", "spore burst"],
    "haunted_ruin": ["ghostly chill", "echoing bells that alert spirits"],
}


def load_map(world: str, map_id: str) -> Path:
    path = Path("worlds") / world / "maps" / f"{map_id}.json"
    if not path.exists():
        raise SystemExit(f"Location not found: {path}")
    return path


def populate(world: str, map_id: str, seed: int) -> Path:
    path = load_map(world, map_id)
    with path.open() as handle:
        data = json.load(handle)

    template = data.get("template")
    rng = random.Random(seed or data.get("seed", 0))
    monsters = MONSTER_TABLE.get(template, [])
    traps = TRAP_TABLE.get(template, [])

    for room in data.get("rooms", []):
        room_monster = monsters[rng.randrange(len(monsters))] if monsters else None
        room_trap = traps[rng.randrange(len(traps))] if traps else None
        room["inhabitants"] = [room_monster] if room_monster else []
        room["traps"] = [room_trap] if room_trap else []
        room.setdefault("dressing", []).append(f"seed-{seed}-detail")

    status = data.setdefault("status", {})
    status["populated"] = True
    status.setdefault("log", []).append({
        "seed": seed,
        "note": "Rooms populated deterministically",
        "traps_used": traps,
        "monsters_used": monsters
    })

    with path.open("w") as handle:
        json.dump(data, handle, indent=2)
    return path


def main():
    parser = argparse.ArgumentParser(description="Populate a generated location with deterministic encounters")
    parser.add_argument("--world", default="default")
    parser.add_argument("--map-id", required=True)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    path = populate(args.world, args.map_id, args.seed)
    print(f"Populated map saved to {path}")


if __name__ == "__main__":
    main()
