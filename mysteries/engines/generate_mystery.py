import argparse
import json
import random
from datetime import datetime
from pathlib import Path


TEMPLATES = {
    "murder_minimal": Path(__file__).resolve().parent.parent / "templates" / "murder_minimal.json",
    "theft_minimal": Path(__file__).resolve().parent.parent / "templates" / "theft_minimal.json",
    "cult_activity": Path(__file__).resolve().parent.parent / "templates" / "cult_activity.json",
}


def load_template(name: str) -> dict:
    template_path = TEMPLATES.get(name)
    if not template_path or not template_path.exists():
        raise SystemExit(f"Unknown template: {name}")
    with template_path.open() as handle:
        return json.load(handle)


def deterministic_choice(seq, rng: random.Random):
    if not seq:
        return None
    return seq[rng.randrange(len(seq))]


def build_mystery(slug: str, template_name: str, seed: int) -> dict:
    rng = random.Random(seed)
    template = load_template(template_name)
    suspects = list(template.get("suspects", []))
    clues = list(template.get("clues", []))
    rng.shuffle(suspects)
    rng.shuffle(clues)
    twist = deterministic_choice(template.get("twists", []), rng)
    mystery_id = f"{template_name}-{seed}" if seed else f"{template_name}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    return {
        "id": mystery_id,
        "slug": slug,
        "template": template_name,
        "crime": template.get("crime"),
        "suspects": [{"name": s, "status": "unknown"} for s in suspects],
        "clues": [{"text": c, "found": False} for c in clues],
        "motive": deterministic_choice([
            "greed", "revenge", "duty", "desperation", "misdirection"
        ], rng),
        "twist": twist,
        "state": {
            "revealed": [],
            "entropy_seed": seed,
            "log": []
        }
    }


def save_mystery(slug: str, mystery: dict) -> Path:
    session_dir = Path("sessions") / slug / "mysteries"
    session_dir.mkdir(parents=True, exist_ok=True)
    output_path = session_dir / f"{mystery['id']}.json"
    with output_path.open("w") as handle:
        json.dump(mystery, handle, indent=2)
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Deterministic mystery generator")
    parser.add_argument("--slug", required=True, help="Session slug")
    parser.add_argument("--template", choices=list(TEMPLATES.keys()), required=True, help="Template name")
    parser.add_argument("--seed", type=int, default=0, help="Deterministic seed; map from entropy index if desired")
    args = parser.parse_args()

    mystery = build_mystery(args.slug, args.template, args.seed)
    path = save_mystery(args.slug, mystery)
    print(f"Mystery saved to {path}")


if __name__ == "__main__":
    main()
