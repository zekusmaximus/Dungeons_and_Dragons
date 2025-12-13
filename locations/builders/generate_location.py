import argparse
import json
import random
from datetime import datetime
from pathlib import Path


TEMPLATES = {
    "dungeon_basic": Path(__file__).resolve().parent.parent / "templates" / "dungeon_basic.json",
    "cave_complex": Path(__file__).resolve().parent.parent / "templates" / "cave_complex.json",
    "haunted_ruin": Path(__file__).resolve().parent.parent / "templates" / "haunted_ruin.json",
}


def load_template(name: str) -> dict:
    template_path = TEMPLATES.get(name)
    if not template_path or not template_path.exists():
        raise SystemExit(f"Unknown template: {name}")
    with template_path.open() as handle:
        return json.load(handle)


def build_location(template_name: str, seed: int) -> dict:
    rng = random.Random(seed)
    template = load_template(template_name)
    rooms = template.get("rooms", [])
    rng.shuffle(rooms)
    hazards = list(template.get("hazards", []))
    treasures = list(template.get("treasures", []))
    rng.shuffle(hazards)
    rng.shuffle(treasures)
    map_id = f"{template_name}-{seed}" if seed else f"{template_name}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    return {
        "id": map_id,
        "template": template_name,
        "rooms": rooms,
        "hazards": hazards,
        "treasures": treasures,
        "seed": seed,
        "status": {
            "populated": False,
            "log": []
        }
    }


def save_location(world: str, location: dict) -> Path:
    base = Path("worlds") / world / "maps"
    base.mkdir(parents=True, exist_ok=True)
    path = base / f"{location['id']}.json"
    with path.open("w") as handle:
        json.dump(location, handle, indent=2)
    return path


def main():
    parser = argparse.ArgumentParser(description="Generate deterministic location map")
    parser.add_argument("--template", choices=list(TEMPLATES.keys()), required=True)
    parser.add_argument("--seed", type=int, default=0, help="Deterministic seed from entropy")
    parser.add_argument("--world", default="default")
    args = parser.parse_args()

    location = build_location(args.template, args.seed)
    path = save_location(args.world, location)
    print(f"Location saved to {path}")


if __name__ == "__main__":
    main()
