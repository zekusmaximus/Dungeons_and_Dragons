from __future__ import annotations

from typing import Any, Dict, List, Optional


DiffHighlights = Dict[str, List[str]]


def _stringify_sequence(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(v) for v in value]
    return []


def _stringify_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def summarize_diff(diff: List[str], before_state: Dict[str, Any], after_state: Dict[str, Any]) -> DiffHighlights:
    """Reduce a raw diff list into categorized highlights.

    The reducer focuses on player-facing state changes so downstream consumers
    can construct consequence echoes without guessing at intent.
    """

    highlights: DiffHighlights = {
        "hp": [],
        "location": [],
        "inventory_added": [],
        "inventory_removed": [],
        "quests": [],
        "clocks": [],
        "relationships": [],
        "other": [],
    }

    before_hp = before_state.get("hp")
    after_hp = after_state.get("hp")
    if isinstance(before_hp, (int, float)) and isinstance(after_hp, (int, float)) and before_hp != after_hp:
        delta = after_hp - before_hp
        sign = "+" if delta >= 0 else ""
        highlights["hp"].append(f"HP {before_hp} -> {after_hp} ({sign}{delta})")

    before_location = before_state.get("location")
    after_location = after_state.get("location")
    if before_location != after_location:
        highlights["location"].append(
            f"Location shifts from {before_location or 'unknown'} to {after_location or 'unknown'}"
        )

    before_inventory = set(_stringify_sequence(before_state.get("inventory")))
    after_inventory = set(_stringify_sequence(after_state.get("inventory")))
    added_items = sorted(after_inventory - before_inventory)
    removed_items = sorted(before_inventory - after_inventory)
    if added_items:
        highlights["inventory_added"].append(f"Picked up: {', '.join(added_items)}")
    if removed_items:
        highlights["inventory_removed"].append(f"Lost: {', '.join(removed_items)}")

    before_quests = _stringify_dict(before_state.get("quests"))
    after_quests = _stringify_dict(after_state.get("quests"))
    quest_ids = set(before_quests.keys()) | set(after_quests.keys())
    for quest_id in sorted(quest_ids):
        if before_quests.get(quest_id) != after_quests.get(quest_id):
            before_status = _stringify_dict(before_quests.get(quest_id)).get("status", "updated")
            after_status = _stringify_dict(after_quests.get(quest_id)).get("status", "updated")
            highlights["quests"].append(f"Quest '{quest_id}' {before_status} -> {after_status}")

    before_flags = _stringify_dict(before_state.get("flags"))
    after_flags = _stringify_dict(after_state.get("flags"))
    before_clocks = _stringify_dict(before_flags.get("clocks"))
    after_clocks = _stringify_dict(after_flags.get("clocks"))
    clock_keys = set(before_clocks.keys()) | set(after_clocks.keys())
    for clock in sorted(clock_keys):
        if before_clocks.get(clock) != after_clocks.get(clock):
            before_val = before_clocks.get(clock, "?")
            after_val = after_clocks.get(clock, "?")
            highlights["clocks"].append(f"Clock '{clock}' {before_val} -> {after_val}")

    before_relationships = _stringify_dict(before_flags.get("relationships"))
    after_relationships = _stringify_dict(after_flags.get("relationships"))
    rel_keys = set(before_relationships.keys()) | set(after_relationships.keys())
    for rel in sorted(rel_keys):
        if before_relationships.get(rel) != after_relationships.get(rel):
            before_status = before_relationships.get(rel, "?")
            after_status = after_relationships.get(rel, "?")
            highlights["relationships"].append(f"Relationship with {rel}: {before_status} -> {after_status}")

    tracked_categories = {
        "hp": "hp",
        "location": "location",
        "inventory": "inventory_added",
        "quest": "quests",
        "clock": "clocks",
        "relationship": "relationships",
    }
    for entry in diff:
        lower_entry = entry.lower()
        matched = False
        for keyword, bucket in tracked_categories.items():
            if keyword in lower_entry:
                highlights[bucket].append(entry)
                matched = True
                break
        if not matched:
            highlights["other"].append(entry)

    return highlights


def derive_consequence_echo(
    provided_echo: Optional[str],
    highlights: DiffHighlights,
    narration: Optional[str],
    diff: List[str],
) -> str:
    """Construct a consequence echo anchored in recent state changes."""

    if provided_echo and provided_echo.strip():
        return provided_echo.strip()

    segments: List[str] = []
    for key in ("hp", "location"):
        if highlights.get(key):
            segments.append(highlights[key][0])

    inventory_bits = []
    if highlights.get("inventory_added"):
        inventory_bits.append(highlights["inventory_added"][0])
    if highlights.get("inventory_removed"):
        inventory_bits.append(highlights["inventory_removed"][0])
    if inventory_bits:
        segments.append("; ".join(inventory_bits))

    for key in ("quests", "clocks", "relationships"):
        if highlights.get(key):
            segments.append(highlights[key][0])

    if not segments and diff:
        segments.append(diff[0])

    if not segments and narration:
        leading = narration.split(".")[0].strip()
        if leading:
            segments.append(leading)

    return "; ".join(segments) or "A new consequence unfolds."
