import argparse
import json
from datetime import datetime
from pathlib import Path


def load_mystery(slug: str, mystery_id: str) -> Path:
    base = Path("sessions") / slug / "mysteries"
    path = base / f"{mystery_id}.json"
    if not path.exists():
        raise SystemExit(f"Mystery not found: {path}")
    return path


def resolve_clue(path: Path, clue_text: str, evidence: str, entropy_index: int | None = None):
    with path.open() as handle:
        data = json.load(handle)
    matched = None
    for clue in data.get("clues", []):
        if clue_text.strip().lower() in clue.get("text", "").lower():
            matched = clue
            break
    if not matched:
        raise SystemExit("Clue text does not match known leads.")
    if matched.get("found"):
        status = "already_found"
    else:
        matched["found"] = True
        status = "new"
    state = data.setdefault("state", {})
    log = state.setdefault("log", [])
    log.append({
        "timestamp": datetime.utcnow().isoformat(),
        "clue": matched.get("text"),
        "evidence": evidence,
        "status": status,
        "entropy_index": entropy_index
    })
    revealed = state.setdefault("revealed", [])
    if matched.get("text") not in revealed:
        revealed.append(matched.get("text"))
    with path.open("w") as handle:
        json.dump(data, handle, indent=2)
    return status


def main():
    parser = argparse.ArgumentParser(description="Resolve a clue for an active mystery")
    parser.add_argument("--slug", required=True)
    parser.add_argument("--mystery", required=True, help="Mystery id without extension")
    parser.add_argument("--clue-text", required=True, help="Snippet of the clue text to resolve")
    parser.add_argument("--evidence", required=True, help="Evidence or action taken")
    parser.add_argument("--entropy-index", type=int, default=None, help="Deterministic dice index used")
    args = parser.parse_args()

    path = load_mystery(args.slug, args.mystery)
    status = resolve_clue(path, args.clue_text, args.evidence, args.entropy_index)
    print(f"Clue resolution status: {status}")


if __name__ == "__main__":
    main()
