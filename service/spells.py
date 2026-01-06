import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, List

FULL_CASTER_SLOTS = {
    1: {"1": 2},
    2: {"1": 3},
    3: {"1": 4, "2": 2},
    4: {"1": 4, "2": 3},
    5: {"1": 4, "2": 3, "3": 2},
    6: {"1": 4, "2": 3, "3": 3},
    7: {"1": 4, "2": 3, "3": 3, "4": 1},
    8: {"1": 4, "2": 3, "3": 3, "4": 2},
    9: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 1},
    10: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 2},
    11: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 2, "6": 1},
    12: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 2, "6": 1},
    13: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 2, "6": 1, "7": 1},
    14: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 2, "6": 1, "7": 1},
    15: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 2, "6": 1, "7": 1, "8": 1},
    16: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 2, "6": 1, "7": 1, "8": 1},
    17: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 2, "6": 1, "7": 1, "8": 1, "9": 1},
    18: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 2, "6": 1, "7": 1, "8": 1, "9": 1},
    19: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 2, "6": 2, "7": 1, "8": 1, "9": 1},
    20: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 2, "6": 2, "7": 1, "8": 1, "9": 1},
}

HALF_CASTER_SLOTS = {
    1: {"1": 0},
    2: {"1": 2},
    3: {"1": 3},
    4: {"1": 3},
    5: {"1": 4, "2": 2},
    6: {"1": 4, "2": 2},
    7: {"1": 4, "2": 3},
    8: {"1": 4, "2": 3},
    9: {"1": 4, "2": 3, "3": 2},
    10: {"1": 4, "2": 3, "3": 2},
    11: {"1": 4, "2": 3, "3": 3},
    12: {"1": 4, "2": 3, "3": 3},
    13: {"1": 4, "2": 3, "3": 3, "4": 1},
    14: {"1": 4, "2": 3, "3": 3, "4": 1},
    15: {"1": 4, "2": 3, "3": 3, "4": 2},
    16: {"1": 4, "2": 3, "3": 3, "4": 2},
    17: {"1": 4, "2": 3, "3": 3, "4": 3},
    18: {"1": 4, "2": 3, "3": 3, "4": 3},
    19: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 1},
    20: {"1": 4, "2": 3, "3": 3, "4": 3, "5": 1},
}

THIRD_CASTER_SLOTS = {
    1: {"1": 0},
    2: {"1": 0},
    3: {"1": 2},
    4: {"1": 3},
    5: {"1": 3},
    6: {"1": 3, "2": 0},
    7: {"1": 4, "2": 2},
    8: {"1": 4, "2": 2},
    9: {"1": 4, "2": 2, "3": 0},
    10: {"1": 4, "2": 3},
    11: {"1": 4, "2": 3},
    12: {"1": 4, "2": 3, "3": 2},
    13: {"1": 4, "2": 3, "3": 2},
    14: {"1": 4, "2": 3, "3": 2},
    15: {"1": 4, "2": 3, "3": 2, "4": 0},
    16: {"1": 4, "2": 3, "3": 3},
    17: {"1": 4, "2": 3, "3": 3},
    18: {"1": 4, "2": 3, "3": 3, "4": 1},
    19: {"1": 4, "2": 3, "3": 3, "4": 2},
    20: {"1": 4, "2": 3, "3": 3, "4": 2},
}


_FALLBACK_SPELLS = [
    {"name": "Fire Bolt", "level": 0, "school": "Evocation", "range": "120 feet", "casting_time": "1 action", "duration": "Instantaneous", "components": ["V", "S"], "description": "Ranged spell attack for 1d10 fire damage; scales with level."},
    {"name": "Cure Wounds", "level": 1, "school": "Evocation", "range": "Touch", "casting_time": "1 action", "duration": "Instantaneous", "components": ["V", "S"], "description": "Touch heals 1d8 + spellcasting modifier; +1d8 per slot above 1st."},
]


@lru_cache(maxsize=1)
def load_spells(spells_path: Path) -> List[Dict]:
    if not spells_path.exists():
        return list(_FALLBACK_SPELLS)
    with spells_path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    validated = []
    for entry in data:
        name = entry.get("name")
        level = entry.get("level")
        casting_time = entry.get("casting_time")
        if not name or level is None or casting_time is None:
            continue
        validated.append(entry)
    return validated


def spell_index_by_name(spells_path: Path) -> Dict[str, Dict]:
    return {entry["name"]: entry for entry in load_spells(spells_path)}


def full_caster_slots(level: int) -> Dict[str, int]:
    """Return per-level slot counts for full casters (wizard/cleric/etc.)."""
    level = max(1, min(level, 20))
    return dict(FULL_CASTER_SLOTS.get(level, {}))


def _slot_table(caster_type: str):
    mapping = {
        "full": FULL_CASTER_SLOTS,
        "half": HALF_CASTER_SLOTS,
        "third": THIRD_CASTER_SLOTS,
    }
    return mapping.get(caster_type, FULL_CASTER_SLOTS)


def reset_spell_slots(level: int, caster_type: str = "full") -> Dict[str, int]:
    """Reset spell slots after a long rest for the given caster profile."""
    caster_type = (caster_type or "full").lower()
    table = _slot_table(caster_type)
    level = max(1, min(level, 20))
    slots = table.get(level, {}) or {}
    return {k: v for k, v in slots.items() if v > 0}
