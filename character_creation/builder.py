import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

from character_creation import validators


@dataclass
class RollResult:
    expr: str
    total: int
    entropy_index: int


class EntropyCursor:
    def __init__(self, entropy_path: Path, start_index: int = 0):
        self.entropy_path = entropy_path
        self.current = start_index
        self._cache = None

    def _load_cache(self):
        if self._cache is None:
            self._cache = {entry["i"]: entry for entry in self._iter_entropy()}

    def _iter_entropy(self):
        with self.entropy_path.open("r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                yield json.loads(line)

    def next_entry(self):
        self._load_cache()
        target = self.current + 1
        if target not in self._cache:
            raise ValueError(f"Entropy index {target} not available")
        self.current = target
        return self._cache[target]

    def map_die(self, raw: int, sides: int) -> int:
        return 1 + ((raw - 1) % sides)

    def roll_on_list(self, options: List[str], label: str) -> Tuple[str, RollResult]:
        entry = self.next_entry()
        die_val = self.map_die(entry["d20"][0], len(options))
        choice = options[die_val - 1]
        return choice, RollResult(expr=label, total=die_val, entropy_index=entry["i"])


def ability_modifier(score: int) -> int:
    return (score - 10) // 2


def roll_ability_scores(cursor: EntropyCursor, count: int = 6) -> Tuple[Dict[str, int], List[RollResult]]:
    abilities = {}
    rolls: List[RollResult] = []
    ability_order = ["str", "dex", "con", "int", "wis", "cha"]
    for idx in range(count):
        entry = cursor.next_entry()
        mapped = [cursor.map_die(val, 6) for val in entry["d20"][:4]]
        mapped.sort(reverse=True)
        total = sum(mapped[:3])
        ability_key = ability_order[idx] if idx < len(ability_order) else f"ability_{idx+1}"
        abilities[ability_key] = total
        rolls.append(RollResult(expr=f"4d6-drop-lowest:{ability_key}", total=total, entropy_index=entry["i"]))
    return abilities, rolls


def apply_racial_modifiers(abilities: Dict[str, int], race_data: Dict[str, object]) -> Dict[str, int]:
    modified = dict(abilities)
    for key, bonus in race_data.get("ability_modifiers", {}).items():
        modified[key] = modified.get(key, 0) + bonus
    return modified


def build_inventory(class_name: str, background_name: str, inventories: Dict[str, List[Dict[str, object]]]) -> List[str]:
    inventory: List[str] = []
    class_kits = inventories.get("class_kits", [])
    background_kits = inventories.get("background_kits", [])

    for kit in class_kits:
        if kit.get("class") == class_name:
            inventory.extend(kit.get("items", []))
            break
    for kit in background_kits:
        if kit.get("background") == background_name:
            inventory.extend(kit.get("items", []))
            break
    return inventory


def summarize_character(slug: str, name: str, race: str, char_class: str, background: str, abilities: Dict[str, int], inventory: List[str]) -> str:
    ability_line = ", ".join([f"{k.upper()} {v}" for k, v in abilities.items()])
    return (
        f"Character {name} ({slug}) created as a {race} {char_class} with background {background}. "
        f"Abilities: {ability_line}. Inventory items: {len(inventory)}"
    )


def write_transcript(path: Path, summary: str):
    with path.open("w", encoding="utf-8") as f:
        f.write(summary + "\n")


def write_changelog(path: Path, log_entry: Dict[str, object]):
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry) + "\n")


def write_character_file(path: Path, character: Dict[str, object]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(character, f, indent=2)


def write_state_file(path: Path, state: Dict[str, object]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def write_turn_prompt(path: Path, prompt: str):
    with path.open("w", encoding="utf-8") as f:
        f.write(prompt.strip() + "\n")


def write_creation_files(
    base_path: Path,
    slug: str,
    name: str,
    race_name: str,
    class_name: str,
    background_name: str,
    abilities: Dict[str, int],
    rolls: List[RollResult],
    inventory: List[str],
    source: str,
):
    character_schema_root = base_path / "schemas"
    sessions_dir = base_path / "sessions" / slug
    sessions_dir.mkdir(parents=True, exist_ok=True)

    race_data = validators.validate_race(race_name, base_path)
    class_data = validators.validate_class(class_name, base_path)
    background_data = validators.validate_background(background_name, base_path)

    proficiencies = {
        "skills": list({*background_data.get("skill_proficiencies", [])}),
        "tools": list({*background_data.get("tool_proficiencies", [])}),
        "languages": race_data.get("languages", []),
    }

    features = []
    features.extend(race_data.get("traits", []))
    features.extend(class_data.get("features", []))
    features.append(background_data.get("feature", ""))
    features = [f for f in features if f]

    starting_equipment = inventory + background_data.get("equipment", [])

    skills = {}
    proficiency_bonus = 2
    skill_to_ability = {
        "acrobatics": "dex",
        "animal handling": "wis",
        "arcana": "int",
        "athletics": "str",
        "deception": "cha",
        "history": "int",
        "insight": "wis",
        "intimidation": "cha",
        "investigation": "int",
        "medicine": "wis",
        "nature": "int",
        "perception": "wis",
        "performance": "cha",
        "persuasion": "cha",
        "religion": "int",
        "sleight of hand": "dex",
        "stealth": "dex",
        "survival": "wis",
    }
    for skill in proficiencies["skills"]:
        ability = skill_to_ability.get(skill, "dex")
        skills[skill] = ability_modifier(abilities.get(ability, 10)) + proficiency_bonus

    character = {
        "slug": slug,
        "name": name,
        "race": race_name,
        "class": class_name,
        "background": background_name,
        "level": 1,
        "hp": class_data.get("hit_die", 6) + ability_modifier(abilities.get("con", 10)),
        "max_hp": class_data.get("hit_die", 6) + ability_modifier(abilities.get("con", 10)),
        "ac": 10 + max(ability_modifier(abilities.get("dex", 10)), 0),
        "abilities": abilities,
        "skills": skills,
        "inventory": starting_equipment,
        "features": features,
        "proficiencies": proficiencies,
        "starting_equipment": starting_equipment,
        "notes": "",
        "creation_source": source,
    }

    validators.validate_final_character(character, base_path)

    write_character_file(base_path / "data" / "characters" / f"{slug}.json", character)

    transcript_summary = summarize_character(slug, name, race_name, class_name, background_name, abilities, starting_equipment)
    write_transcript(sessions_dir / "transcript.md", transcript_summary)

    turn_prompt = "You stand ready for adventure. What is your first move?"
    write_turn_prompt(sessions_dir / "turn.md", turn_prompt)

    state = {
        "character": slug,
        "level": 1,
        "xp": 0,
        "turn": 0,
        "scene_id": "creation-complete",
        "location": "start",
        "hp": character["hp"],
        "conditions": [],
        "flags": {},
        "inventory": starting_equipment,
        "log_index": rolls[-1].entropy_index if rolls else 0,
    }
    write_state_file(sessions_dir / "state.json", state)

    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "turn": 0,
        "scene_id": "creation-complete",
        "summary": f"{name} created as a {race_name} {class_name} ({background_name})",
        "diffs": {"inventory": starting_equipment},
        "rolls": [r.__dict__ for r in rolls],
    }
    write_changelog(sessions_dir / "changelog.md", log_entry)

    progress_path = sessions_dir / "creation_progress.json"
    if progress_path.exists():
        progress_path.unlink()

    return character, state, log_entry


def load_tables(base_path: Path):
    tables_dir = base_path / "character_creation" / "tables"
    return {
        "races": json.load(open(tables_dir / "races.json", "r", encoding="utf-8")),
        "classes": json.load(open(tables_dir / "classes.json", "r", encoding="utf-8")),
        "backgrounds": json.load(open(tables_dir / "backgrounds.json", "r", encoding="utf-8")),
        "inventories": json.load(open(tables_dir / "inventories.json", "r", encoding="utf-8")),
        "names": json.load(open(tables_dir / "names_human.json", "r", encoding="utf-8")),
    }


def auto_name(cursor: EntropyCursor, names: List[str]) -> Tuple[str, RollResult]:
    return cursor.roll_on_list(names, "name")

