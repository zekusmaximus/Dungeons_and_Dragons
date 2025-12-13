#!/usr/bin/env python3
"""Verify and extend deterministic entropy.

Usage:
  python dice/verify_dice.py --check
  python dice/verify_dice.py --extend N
  python dice/verify_dice.py --audit sessions/<slug>/changelog.md
"""
import argparse
import json
import random
from datetime import datetime
from pathlib import Path

REPO_SEED = 20240301
ENTROPY_PATH = Path(__file__).resolve().parent / "entropy.ndjson"


def read_lines(path: Path):
    with path.open() as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError as exc:
                raise SystemExit(f"Invalid JSON at line {line_no}: {exc}")
            yield line_no, data


def validate_entropy(path: Path):
    last_i = 0
    for line_no, data in read_lines(path):
        if not isinstance(data, dict):
            raise SystemExit(f"Line {line_no} is not an object")
        if set(data.keys()) != {"i", "d20", "d100", "bytes"}:
            raise SystemExit(f"Line {line_no} has wrong keys: {data.keys()}")
        if data["i"] != last_i + 1:
            raise SystemExit(f"Line {line_no} has non-monotonic i: {data['i']}")
        last_i = data["i"]
        for key in ("d20", "d100"):
            arr = data[key]
            if not isinstance(arr, list) or not all(isinstance(n, int) for n in arr):
                raise SystemExit(f"Line {line_no} {key} is not a list of ints")
        if not isinstance(data["bytes"], str):
            raise SystemExit(f"Line {line_no} bytes must be a string")
    print(f"Validated {last_i} entropy lines")
    return last_i


def extend_entropy(path: Path, count: int):
    last_i = validate_entropy(path)
    random.seed(REPO_SEED + last_i)
    with path.open("a") as f:
        for offset in range(1, count + 1):
            i = last_i + offset
            d20 = [random.randint(1, 20) for _ in range(10)]
            d100 = [random.randint(1, 100) for _ in range(5)]
            byte_val = random.getrandbits(32).to_bytes(4, "big").hex()
            obj = {"i": i, "d20": d20, "d100": d100, "bytes": byte_val}
            f.write(json.dumps(obj, separators=(",", ":")) + "\n")
    print(f"Appended {count} lines; new total {last_i + count}")


def audit_changelog(changelog: Path):
    _, max_i = None, validate_entropy(ENTROPY_PATH)
    used = set()
    with changelog.open() as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError as exc:
                raise SystemExit(f"Changelog {changelog} line {line_no} invalid JSON: {exc}")
            for roll in entry.get("rolls", []):
                idx = roll.get("entropy_index")
                if idx is None:
                    raise SystemExit(f"Missing entropy_index at changelog line {line_no}")
                if idx in used:
                    raise SystemExit(f"Entropy index {idx} reused (line {line_no})")
                if not isinstance(idx, int) or idx < 1 or idx > max_i:
                    raise SystemExit(f"Entropy index {idx} out of range (line {line_no})")
                used.add(idx)
    print(f"Audit passed: {len(used)} unique entropy indices referenced")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate entropy file")
    parser.add_argument("--extend", type=int, help="append N new lines deterministically")
    parser.add_argument("--audit", type=str, help="audit changelog for entropy usage")
    args = parser.parse_args()

    if not any([args.check, args.extend, args.audit]):
        parser.print_help()
        return

    if args.check:
        validate_entropy(ENTROPY_PATH)
    if args.extend:
        extend_entropy(ENTROPY_PATH, args.extend)
    if args.audit:
        audit_changelog(Path(args.audit))


if __name__ == "__main__":
    main()
