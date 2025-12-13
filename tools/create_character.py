#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from character_creation import builder, validators


def parse_args():
    parser = argparse.ArgumentParser(description="Deterministic character creator")
    parser.add_argument("--slug", required=True)
    parser.add_argument("--race", required=True)
    parser.add_argument("--class", dest="char_class", required=True)
    parser.add_argument("--background", required=True)
    parser.add_argument("--abilities", default="auto", help="'auto' or comma-separated scores")
    parser.add_argument("--name", required=False, help="Character name; if omitted and abilities is auto, name is rolled")
    parser.add_argument("--start-inventory", default="auto", help="'auto' to use tables")
    return parser.parse_args()


def parse_manual_abilities(arg: str):
    parts = [p.strip() for p in arg.split(",") if p.strip()]
    if len(parts) != 6:
        raise ValueError("Manual abilities must include six comma-separated scores")
    scores = {k: int(v) for k, v in zip(["str", "dex", "con", "int", "wis", "cha"], parts)}
    validators.validate_abilities(scores)
    return scores, []


def main():
    args = parse_args()
    base_path = Path(__file__).resolve().parents[1]

    entropy_path = base_path / "dice" / "entropy.ndjson"
    cursor = builder.EntropyCursor(entropy_path)

    if args.abilities.lower() == "auto":
        rolled, roll_results = builder.roll_ability_scores(cursor)
    else:
        rolled, roll_results = parse_manual_abilities(args.abilities)

    race_data = validators.validate_race(args.race, base_path)
    class_data = validators.validate_class(args.char_class, base_path)
    background_data = validators.validate_background(args.background, base_path)

    final_abilities = builder.apply_racial_modifiers(rolled, race_data)
    validators.validate_abilities(final_abilities)

    inventories = json.load(open(base_path / "character_creation" / "tables" / "inventories.json", "r", encoding="utf-8"))
    if args.start_inventory.lower() == "auto":
        inventory_items = builder.build_inventory(args.char_class, args.background, inventories)
    else:
        inventory_items = [item.strip() for item in args.start_inventory.split(",") if item.strip()]
    validators.validate_inventory(args.char_class, args.background, base_path)

    if args.name:
        final_name = args.name
        name_roll = []
    else:
        names = json.load(open(base_path / "character_creation" / "tables" / "names_human.json", "r", encoding="utf-8"))
        final_name, name_roll_result = builder.auto_name(cursor, names)
        name_roll = [name_roll_result]

    roll_results.extend(name_roll)

    character, state, log_entry = builder.write_creation_files(
        base_path,
        args.slug,
        final_name,
        args.race,
        args.char_class,
        args.background,
        final_abilities,
        roll_results,
        inventory_items,
        source="tool",
    )

    print(json.dumps({
        "character": character,
        "state": state,
        "changelog": log_entry,
    }, indent=2))


if __name__ == "__main__":
    main()
