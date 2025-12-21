import hashlib
import json
import re
import uuid
import subprocess
import tempfile
import shutil
from copy import deepcopy
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
import jsonschema

from fastapi import HTTPException, status
from pydantic import ValidationError

from .config import Settings
from .models import LockInfo, JobCreateRequest, JobStatus, SessionState, PreviewRequest, RollRequest, RollResult

_SLUG_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")
_PREVIEWS_DIRNAME = "previews"


def _canonical_hash(data: Dict) -> str:
    """Compute a deterministic hash for a JSON-serializable object."""
    payload = json.dumps(data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def validate_data(data: Dict, schema_name: str, settings: Settings) -> List[str]:
    """Validate data against JSON schema. Return list of error messages."""
    schema_path = settings.repo_root / "schemas" / f"{schema_name}.schema.json"
    if not schema_path.exists():
        return []  # No schema, no validation
    with schema_path.open() as f:
        schema = json.load(f)
    try:
        jsonschema.validate(data, schema)
        return []
    except jsonschema.ValidationError as e:
        return [e.message]
    except Exception as e:
        return [str(e)]


def _ensure_session(settings: Settings, slug: str) -> Path:
    if not _SLUG_PATTERN.match(slug):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid session slug. Use letters, numbers, hyphens, or underscores.",
        )
    session_path = settings.sessions_path / slug
    if not session_path.exists() or not session_path.is_dir():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown session '{slug}'",
        )
    return session_path


def list_sessions(settings: Settings) -> List[Dict]:
    if not settings.sessions_path.exists():
        return []
    sessions = []
    for p in sorted(settings.sessions_path.iterdir()):
        if p.is_dir() and not p.name.startswith("."):
            slug = p.name
            state_path = p / "state.json"
            world = "default"
            updated_at = p.stat().st_mtime
            has_lock = (p / "LOCK").exists()
            if state_path.exists():
                try:
                    with state_path.open() as handle:
                        state = json.load(handle)
                    world = state.get("world", "default")
                    # updated_at could be from state if has time, but for now use mtime
                except Exception:
                    pass
            sessions.append({
                "slug": slug,
                "world": world,
                "has_lock": has_lock,
                "updated_at": updated_at  # timestamp
            })
    return sessions


def create_session(settings: Settings, slug: str, template_slug: str = "example-rogue") -> str:
    if not _SLUG_PATTERN.match(slug):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid session slug. Use letters, numbers, hyphens, or underscores.",
        )
    settings.sessions_path.mkdir(parents=True, exist_ok=True)
    session_path = settings.sessions_path / slug
    if session_path.exists():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Session already exists")
    template_path = settings.sessions_path / template_slug
    if not template_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template session not found")

    shutil.copytree(template_path, session_path)
    lock_path = session_path / "LOCK"
    if lock_path.exists():
        lock_path.unlink()
    preview_dir = session_path / _PREVIEWS_DIRNAME
    if preview_dir.exists():
        shutil.rmtree(preview_dir)

    state_path = session_path / "state.json"
    state = load_state(settings, slug)
    state["character"] = slug
    state["turn"] = 0
    state["log_index"] = 0
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    transcript_path = session_path / "transcript.md"
    transcript_path.write_text(f"# Transcript: {slug}\n\nThe DM will append narrated scenes here.\n", encoding="utf-8")
    changelog_path = session_path / "changelog.md"
    changelog_path.write_text(
        json.dumps(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "turn": 0,
                "scene_id": "init",
                "summary": "Initialized session state",
                "diffs": {"hp": 0, "inventory": [], "flags": {}},
                "rolls": [],
                "rules": ["Initialization"],
            }
        ) + "\n",
        encoding="utf-8",
    )

    template_character = settings.repo_root / "data" / "characters" / f"{template_slug}.json"
    if template_character.exists():
        try:
            character_data = json.loads(template_character.read_text(encoding="utf-8"))
            save_character(settings, slug, character_data, persist_to_data=True)
        except Exception:
            pass

    return slug


def load_character(settings: Settings, slug: str) -> Dict:
    """Load a character sheet by slug. Prefer session-local copy, fall back to data/characters."""
    if not _SLUG_PATTERN.match(slug):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid character slug. Use letters, numbers, hyphens, or underscores.",
        )

    session_path = settings.sessions_path / slug
    session_character = session_path / "character.json"
    character_path = settings.repo_root / "data" / "characters" / f"{slug}.json"

    if session_character.exists():
        target = session_character
    elif character_path.exists():
        target = character_path
    else:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Character '{slug}' not found",
        )

    try:
        content = target.read_text(encoding="utf-8")
        if content.startswith('\ufeff'):
            content = content[1:]
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Invalid character data for '{slug}': {exc}",
        )


def save_character(settings: Settings, slug: str, character_data: Dict, persist_to_data: bool = True) -> Dict:
    """Persist a character JSON to the session and optionally the shared data directory."""
    if not _SLUG_PATTERN.match(slug):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid character slug. Use letters, numbers, hyphens, or underscores.",
        )

    payload = deepcopy(character_data)
    payload["slug"] = slug

    session_path = _ensure_session(settings, slug)
    session_character = session_path / "character.json"
    session_character.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    if persist_to_data:
        characters_dir = settings.repo_root / "data" / "characters"
        characters_dir.mkdir(parents=True, exist_ok=True)
        data_character = characters_dir / f"{slug}.json"
        data_character.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    return payload

def load_state(settings: Settings, slug: str) -> Dict:
    session_path = _ensure_session(settings, slug)
    state_path = session_path / "state.json"
    if not state_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"State not found for '{slug}'"
        )
    with state_path.open(encoding='utf-8') as handle:
        content = handle.read()
    if content.startswith('\ufeff'):
        content = content[1:]
    return json.loads(content)


def _validate_state(state: Dict) -> SessionState:
    try:
        return SessionState(**state)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"State validation failed: {exc}",
        )


def save_state(settings: Settings, slug: str, state: Dict) -> SessionState:
    """Validate and persist session state."""
    session_path = _ensure_session(settings, slug)
    validated = _validate_state(state)
    state_path = session_path / "state.json"
    state_path.write_text(json.dumps(validated.model_dump(mode="json"), indent=2), encoding="utf-8")
    return validated


def load_text_entries(path: Path, count: Optional[int] = None, cursor: Optional[str] = None) -> Tuple[List[Dict], Optional[str]]:
    if not path.exists():
        return [], None
    with path.open() as handle:
        all_lines = [line.rstrip() for line in handle.readlines() if line.strip()]
    entries = [{"id": str(idx), "text": line} for idx, line in enumerate(all_lines)]
    if cursor:
        try:
            start_idx = int(cursor) + 1
        except ValueError:
            start_idx = 0
    else:
        start_idx = max(0, len(entries) - (count or len(entries)))
    end_idx = len(entries) if count is None else start_idx + count
    selected = entries[start_idx:end_idx]
    next_cursor = str(end_idx - 1) if end_idx < len(entries) else None
    return selected, next_cursor


def load_transcript(settings: Settings, slug: str, tail: Optional[int] = None, cursor: Optional[str] = None) -> Tuple[List[Dict], Optional[str]]:
    session_path = _ensure_session(settings, slug)
    transcript_path = session_path / "transcript.md"
    count = tail if tail is not None else settings.transcript_tail
    return load_text_entries(transcript_path, count, cursor)


def load_changelog(settings: Settings, slug: str, tail: Optional[int] = None, cursor: Optional[str] = None) -> Tuple[List[Dict], Optional[str]]:
    session_path = _ensure_session(settings, slug)
    changelog_path = session_path / "changelog.md"
    count = tail if tail is not None else settings.changelog_tail
    return load_text_entries(changelog_path, count, cursor)


def load_quests(settings: Settings, slug: str) -> Dict:
    state = load_state(settings, slug)
    return state.get("quests", {})


def save_quest(settings: Settings, slug: str, quest_id: str, quest_data: Dict):
    state = load_state(settings, slug)
    if "quests" not in state:
        state["quests"] = {}
    state["quests"][quest_id] = quest_data
    session_path = _ensure_session(settings, slug)
    state_path = session_path / "state.json"
    with state_path.open('w') as handle:
        json.dump(state, handle, indent=2)


def delete_quest(settings: Settings, slug: str, quest_id: str):
    state = load_state(settings, slug)
    if "quests" in state and quest_id in state["quests"]:
        del state["quests"][quest_id]
        session_path = _ensure_session(settings, slug)
        state_path = session_path / "state.json"
        with state_path.open('w') as handle:
            json.dump(state, handle, indent=2)


def load_npc_memory(settings: Settings, slug: str) -> List[Dict]:
    session_path = _ensure_session(settings, slug)
    path = session_path / "npc_memory.json"
    if not path.exists():
        return []
    with path.open() as handle:
        data = json.load(handle)
    return data.get("npcs", [])


def save_npc_memory(settings: Settings, slug: str, npcs: List[Dict]):
    session_path = _ensure_session(settings, slug)
    path = session_path / "npc_memory.json"
    data = {"npcs": npcs}
    with path.open('w') as handle:
        json.dump(data, handle, indent=2)


def resolve_world(settings: Settings, slug: str) -> Path:
    state = load_state(settings, slug)
    world_name = state.get("world", "default")
    world_path = settings.repo_root / "worlds" / world_name
    if not world_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"World '{world_name}' not found"
        )
    return world_path


def load_world_file(world_path: Path, filename: str) -> Dict:
    path = world_path / filename
    if not path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Missing world file {filename}")
    with path.open() as handle:
        data = json.load(handle)
    return data


def load_factions(settings: Settings, slug: str) -> Dict:
    world = resolve_world(settings, slug)
    data = load_world_file(world, "factions.json")
    factions = {f["id"]: f for f in data["factions"]}
    return factions


def save_faction(settings: Settings, slug: str, faction_id: str, faction_data: Dict):
    world = resolve_world(settings, slug)
    data = load_world_file(world, "factions.json")
    factions_dict = {f["id"]: f for f in data["factions"]}
    factions_dict[faction_id] = faction_data
    data["factions"] = list(factions_dict.values())
    factions_path = world / "factions.json"
    with factions_path.open('w') as handle:
        json.dump(data, handle, indent=2)


def delete_faction(settings: Settings, slug: str, faction_id: str):
    world = resolve_world(settings, slug)
    data = load_world_file(world, "factions.json")
    factions_dict = {f["id"]: f for f in data["factions"]}
    if faction_id in factions_dict:
        del factions_dict[faction_id]
        data["factions"] = list(factions_dict.values())
        factions_path = world / "factions.json"
        with factions_path.open('w') as handle:
            json.dump(data, handle, indent=2)


def load_timeline(settings: Settings, slug: str) -> Dict:
    world = resolve_world(settings, slug)
    data = load_world_file(world, "timeline.json")
    timeline = {e["id"]: e for e in data["events"]}
    return timeline


def save_timeline_event(settings: Settings, slug: str, event_id: str, event_data: Dict):
    world = resolve_world(settings, slug)
    data = load_world_file(world, "timeline.json")
    events_dict = {e["id"]: e for e in data["events"]}
    events_dict[event_id] = event_data
    data["events"] = list(events_dict.values())
    timeline_path = world / "timeline.json"
    with timeline_path.open('w') as handle:
        json.dump(data, handle, indent=2)


def delete_timeline_event(settings: Settings, slug: str, event_id: str):
    world = resolve_world(settings, slug)
    data = load_world_file(world, "timeline.json")
    events_dict = {e["id"]: e for e in data["events"]}
    if event_id in events_dict:
        del events_dict[event_id]
        data["events"] = list(events_dict.values())
        timeline_path = world / "timeline.json"
        with timeline_path.open('w') as handle:
            json.dump(data, handle, indent=2)


def load_rumors(settings: Settings, slug: str) -> Dict:
    world = resolve_world(settings, slug)
    data = load_world_file(world, "rumors.json")
    rumors = {r["id"]: r for r in data["rumors"]}
    return rumors


def save_rumor(settings: Settings, slug: str, rumor_id: str, rumor_data: Dict):
    world = resolve_world(settings, slug)
    data = load_world_file(world, "rumors.json")
    rumors_dict = {r["id"]: r for r in data["rumors"]}
    rumors_dict[rumor_id] = rumor_data
    data["rumors"] = list(rumors_dict.values())
    rumors_path = world / "rumors.json"
    with rumors_path.open('w') as handle:
        json.dump(data, handle, indent=2)


def delete_rumor(settings: Settings, slug: str, rumor_id: str):
    world = resolve_world(settings, slug)
    data = load_world_file(world, "rumors.json")
    rumors_dict = {r["id"]: r for r in data["rumors"]}
    if rumor_id in rumors_dict:
        del rumors_dict[rumor_id]
        data["rumors"] = list(rumors_dict.values())
        rumors_path = world / "rumors.json"
        with rumors_path.open('w') as handle:
            json.dump(data, handle, indent=2)


def load_faction_clocks(settings: Settings, slug: str) -> Dict:
    world = resolve_world(settings, slug)
    data = load_world_file(world, "faction_clocks.json")
    clocks = {p["id"]: p for p in data["projects"]}
    return clocks


def save_faction_clock(settings: Settings, slug: str, clock_id: str, clock_data: Dict):
    world = resolve_world(settings, slug)
    data = load_world_file(world, "faction_clocks.json")
    clocks_dict = {p["id"]: p for p in data["projects"]}
    clocks_dict[clock_id] = clock_data
    data["projects"] = list(clocks_dict.values())
    clocks_path = world / "faction_clocks.json"
    with clocks_path.open('w') as handle:
        json.dump(data, handle, indent=2)


def delete_faction_clock(settings: Settings, slug: str, clock_id: str):
    world = resolve_world(settings, slug)
    data = load_world_file(world, "faction_clocks.json")
    clocks_dict = {p["id"]: p for p in data["projects"]}
    if clock_id in clocks_dict:
        del clocks_dict[clock_id]
        data["projects"] = list(clocks_dict.values())
        clocks_path = world / "faction_clocks.json"
        with clocks_path.open('w') as handle:
            json.dump(data, handle, indent=2)


def load_advantages(settings: Settings, slug: str) -> Dict:
    session_path = _ensure_session(settings, slug)
    path = session_path / "advantages.json"
    if not path.exists():
        return {"active": [], "tracking_rules": ""}
    with path.open() as handle:
        return json.load(handle)


def save_advantages(settings: Settings, slug: str, advantages: Dict):
    session_path = _ensure_session(settings, slug)
    path = session_path / "advantages.json"
    with path.open('w') as handle:
        json.dump(advantages, handle, indent=2)


def load_journal_entries(settings: Settings, slug: str) -> List[Dict]:
    session_path = _ensure_session(settings, slug)
    path = session_path / "journal_entries.json"
    if not path.exists():
        return []
    with path.open() as handle:
        return json.load(handle)


def save_journal_entries(settings: Settings, slug: str, entries: List[Dict]):
    session_path = _ensure_session(settings, slug)
    path = session_path / "journal_entries.json"
    with path.open('w') as handle:
        json.dump(entries, handle, indent=2)


def load_mysteries(settings: Settings, slug: str) -> Dict:
    session_path = _ensure_session(settings, slug)
    path = session_path / "mysteries.json"
    if not path.exists():
        return {}
    with path.open() as handle:
        return json.load(handle)


def save_mystery(settings: Settings, slug: str, mystery_id: str, mystery_data: Dict):
    mysteries = load_mysteries(settings, slug)
    mysteries[mystery_id] = mystery_data
    session_path = _ensure_session(settings, slug)
    path = session_path / "mysteries.json"
    with path.open('w') as handle:
        json.dump(mysteries, handle, indent=2)


def delete_mystery(settings: Settings, slug: str, mystery_id: str):
    mysteries = load_mysteries(settings, slug)
    if mystery_id in mysteries:
        del mysteries[mystery_id]
        session_path = _ensure_session(settings, slug)
        path = session_path / "mysteries.json"
        with path.open('w') as handle:
            json.dump(mysteries, handle, indent=2)


def load_allies(settings: Settings, slug: str) -> List[Dict]:
    session_path = _ensure_session(settings, slug)
    path = session_path / "allies.json"
    if not path.exists():
        return []
    with path.open() as handle:
        return json.load(handle)


def save_allies(settings: Settings, slug: str, allies: List[Dict]):
    session_path = _ensure_session(settings, slug)
    path = session_path / "allies.json"
    with path.open('w') as handle:
        json.dump(allies, handle, indent=2)


def load_locations(settings: Settings, slug: str) -> Dict:
    session_path = _ensure_session(settings, slug)
    path = session_path / "locations.json"
    if not path.exists():
        return {}
    with path.open() as handle:
        return json.load(handle)


def save_location(settings: Settings, slug: str, location_id: str, location_data: Dict):
    locations = load_locations(settings, slug)
    locations[location_id] = location_data
    session_path = _ensure_session(settings, slug)
    path = session_path / "locations.json"
    with path.open('w') as handle:
        json.dump(locations, handle, indent=2)


def delete_location(settings: Settings, slug: str, location_id: str):
    locations = load_locations(settings, slug)
    if location_id in locations:
        del locations[location_id]
        session_path = _ensure_session(settings, slug)
        path = session_path / "locations.json"
        with path.open('w') as handle:
            json.dump(locations, handle, indent=2)


def load_entropy_preview(settings: Settings, limit: int = 5) -> List[Dict]:
    if not settings.dice_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entropy file missing")
    preview: List[Dict] = []
    with settings.dice_path.open() as handle:
        for idx, line in enumerate(handle):
            if idx >= limit:
                break
            try:
                preview.append(json.loads(line))
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to parse entropy file",
                )
    return preview


def load_turn(settings: Settings, slug: str) -> str:
    session_path = _ensure_session(settings, slug)
    turn_path = session_path / "turn.md"
    if not turn_path.exists():
        return ""
    with turn_path.open(encoding='utf-8') as handle:
        content = handle.read()
    if content.startswith('\ufeff'):
        content = content[1:]
    return content


def get_lock_info(settings: Settings, slug: str) -> Optional[LockInfo]:
    session_path = _ensure_session(settings, slug)
    lock_path = session_path / "LOCK"
    if not lock_path.exists():
        return None
    try:
        with lock_path.open() as handle:
            data = json.load(handle)
    except Exception:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Lock file unreadable")
    return LockInfo(
        owner=data["owner"],
        ttl=data["ttl"],
        claimed_at=datetime.fromisoformat(data["claimed_at"])
    )


def claim_lock(settings: Settings, slug: str, owner: str, ttl: int):
    session_path = _ensure_session(settings, slug)
    lock_path = session_path / "LOCK"
    if lock_path.exists():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Lock already claimed")
    data = {
        "owner": owner,
        "ttl": ttl,
        "claimed_at": datetime.now(timezone.utc).isoformat()
    }
    with lock_path.open('w') as handle:
        json.dump(data, handle)


def release_lock(settings: Settings, slug: str):
    session_path = _ensure_session(settings, slug)
    lock_path = session_path / "LOCK"
    if lock_path.exists():
        lock_path.unlink()


def _assert_lock_owner(session_path: Path, owner: Optional[str]):
    """Ensure lock is held by the requester (or absent)."""
    lock_path = session_path / "LOCK"
    if not lock_path.exists():
        if owner:
            # Require caller to own the lock when specifying owner
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Lock is not claimed")
        return
    try:
        data = json.loads(lock_path.read_text(encoding="utf-8"))
    except Exception:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Lock is corrupted")
    if owner and data.get("owner") != owner:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Lock owned by another actor")
    if not owner:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Session locked")


def _ensure_entropy_available(settings: Settings, target_index: int):
    """Ensure entropy.ndjson has at least up to the target index."""
    if target_index <= 0:
        return
    if not settings.dice_path.exists():
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Entropy file missing")
    highest = 0
    with settings.dice_path.open(encoding="utf-8") as handle:
        for line in handle:
            try:
                data = json.loads(line)
                highest = max(highest, data.get("i", 0))
                if highest >= target_index:
                    return
            except json.JSONDecodeError:
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Entropy file corrupt")
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Not enough entropy reserved (need index {target_index}, have {highest})",
    )


def _load_entropy_entry(settings: Settings, index: int) -> Dict:
    """Load a specific entropy entry by index."""
    with settings.dice_path.open(encoding="utf-8") as handle:
        for line in handle:
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if data.get("i") == index:
                return data
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Not enough entropy for the requested roll",
    )


def _ability_score_from_payload(payload: Dict, ability: str) -> Optional[int]:
    abilities = payload.get("abilities") or {}
    if not isinstance(abilities, dict):
        return None
    lower = ability.lower()
    return (
        abilities.get(lower)
        or abilities.get(f"{lower}_")
        or abilities.get(lower.upper())
        or abilities.get(ability)
    )


def _ability_modifier(score: Optional[int]) -> int:
    if score is None:
        return 0
    return (score - 10) // 2


_SKILL_TO_ABILITY = {
    "athletics": "STR",
    "acrobatics": "DEX",
    "sleight_of_hand": "DEX",
    "stealth": "DEX",
    "arcana": "INT",
    "history": "INT",
    "investigation": "INT",
    "nature": "INT",
    "religion": "INT",
    "animal_handling": "WIS",
    "insight": "WIS",
    "medicine": "WIS",
    "perception": "WIS",
    "survival": "WIS",
    "deception": "CHA",
    "intimidation": "CHA",
    "performance": "CHA",
    "persuasion": "CHA",
}


def _normalize_skill_name(skill: str) -> str:
    return skill.strip().lower().replace(" ", "_")


def _proficiency_bonus(level: Optional[int]) -> int:
    if not level or level < 1:
        return 2
    return 2 + max(0, (level - 1) // 4)


def _is_skill_proficient(character: Dict, skill: str) -> bool:
    profs = character.get("proficiencies") or {}
    skills = profs.get("skills") if isinstance(profs, dict) else []
    if not isinstance(skills, list):
        return False
    target = _normalize_skill_name(skill)
    normalized = {_normalize_skill_name(str(item)) for item in skills if isinstance(item, str)}
    return target in normalized


def _display_label(roll_request: RollRequest) -> str:
    if roll_request.skill:
        return _normalize_skill_name(roll_request.skill).replace("_", " ").title()
    if roll_request.ability:
        return roll_request.ability
    return roll_request.kind.replace("_", " ").title()


def _append_transcript_entry(session_path: Path, text: str) -> None:
    transcript_path = session_path / "transcript.md"
    transcript_path.touch(exist_ok=True)
    with transcript_path.open("a", encoding="utf-8") as handle:
        handle.write(text.rstrip() + "\n")


def _append_roll_to_turn_record(settings: Settings, slug: str, roll_payload: Dict) -> None:
    session_path = _ensure_session(settings, slug)
    state = load_state(settings, slug)
    turn_number = state.get("turn")
    if turn_number is None:
        return
    record_path = session_path / "turns" / f"{turn_number}.json"
    if not record_path.exists():
        return
    try:
        record = json.loads(record_path.read_text(encoding="utf-8"))
    except Exception:
        return
    rolls = record.get("rolls")
    if not isinstance(rolls, list):
        rolls = []
    rolls.append(roll_payload)
    record["rolls"] = rolls
    record_path.write_text(json.dumps(record, indent=2, default=str), encoding="utf-8")


def perform_roll(settings: Settings, slug: str, roll_request: RollRequest) -> RollResult:
    state = load_state(settings, slug)
    character = {}
    try:
        character = load_character(settings, slug)
    except HTTPException:
        pass

    next_index = state.get("log_index", 0) + 1
    _ensure_entropy_available(settings, next_index)
    entropy_entry = _load_entropy_entry(settings, next_index)

    d20_values = entropy_entry.get("d20") or []
    needed = 2 if roll_request.advantage in ("advantage", "disadvantage") else 1
    if len(d20_values) < needed:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Entropy line missing dice values")

    used_rolls = d20_values[:needed]
    base_roll = max(used_rolls) if roll_request.advantage == "advantage" else min(used_rolls) if roll_request.advantage == "disadvantage" else used_rolls[0]

    modifier = 0
    ability = roll_request.ability
    if not ability and roll_request.skill:
        ability = _SKILL_TO_ABILITY.get(_normalize_skill_name(roll_request.skill))
    if not ability and roll_request.kind == "initiative":
        ability = "DEX"

    ability_score = None
    if ability:
        ability_score = _ability_score_from_payload(state, ability) or _ability_score_from_payload(character, ability)
    ability_mod = _ability_modifier(ability_score)
    modifier += ability_mod

    prof_bonus = 0
    if roll_request.skill and _is_skill_proficient(character, roll_request.skill):
        level = character.get("level") or state.get("level")
        prof_bonus = _proficiency_bonus(level)
        modifier += prof_bonus

    total = base_roll + modifier

    state["log_index"] = next_index
    save_state(settings, slug, state)

    breakdown_parts = [str(base_roll)]
    if ability:
        breakdown_parts.append(f"{ability_mod:+d} ({ability})")
    if prof_bonus:
        breakdown_parts.append(f"+{prof_bonus} (PROF)")
    breakdown = " ".join(part.replace("+-", "-") for part in breakdown_parts)

    display_label = _display_label(roll_request)
    text = f"I roll {display_label}: {breakdown} = {total}"

    roll_payload = {
        "kind": roll_request.kind,
        "ability": ability,
        "skill": roll_request.skill,
        "advantage": roll_request.advantage,
        "dc": roll_request.dc,
        "total": total,
        "d20": used_rolls,
        "breakdown": breakdown,
        "text": text,
    }
    _append_transcript_entry(_ensure_session(settings, slug), text)
    _append_roll_to_turn_record(settings, slug, roll_payload)

    return RollResult(d20=used_rolls, total=total, breakdown=breakdown, text=text)
def _apply_state_patch(state: Dict, patch: Dict) -> Dict:
    allowed_fields = set(SessionState.model_fields.keys())
    disallowed = {"turn", "log_index"}
    for key in patch.keys():
        if key in disallowed:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"'{key}' cannot be set directly")
        if key not in allowed_fields:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown state field '{key}'")
    merged = deepcopy(state)

    def _merge_dict(base: Dict, updates: Dict) -> Dict:
        updated = deepcopy(base)
        for k, v in updates.items():
            if isinstance(v, dict) and isinstance(updated.get(k), dict):
                updated[k] = _merge_dict(updated.get(k, {}), v)
            else:
                updated[k] = v
        return updated

    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_dict(merged.get(key, {}), value)
        else:
            merged[key] = value
    return merged


def summarize_state_diff(before: Dict, after: Dict) -> List[str]:
    changes: List[str] = []
    keys = set(before.keys()) | set(after.keys())
    for key in sorted(keys):
        if before.get(key) != after.get(key):
            changes.append(f"{key}: {before.get(key)} -> {after.get(key)}")
    return changes


def persist_turn_record(
    settings: Settings,
    slug: str,
    record: Dict,
):
    session_path = _ensure_session(settings, slug)
    turns_dir = session_path / "turns"
    turns_dir.mkdir(exist_ok=True)
    turn_number = record.get("turn")
    if turn_number is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Turn number required for record")
    record_path = turns_dir / f"{turn_number}.json"
    with record_path.open("w", encoding="utf-8") as handle:
        json.dump(record, handle, indent=2, default=str)


def record_last_discovery_turn(settings: Settings, slug: str, turn: int):
    session_path = _ensure_session(settings, slug)
    path = session_path / "last_discovery.json"
    payload = {"turn": turn, "recorded_at": datetime.now(timezone.utc).isoformat()}
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def get_last_discovery_turn(settings: Settings, slug: str) -> Optional[int]:
    session_path = _ensure_session(settings, slug)
    path = session_path / "last_discovery.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        turn = data.get("turn")
        return int(turn) if turn is not None else None
    except Exception:
        return None


def load_turn_records(settings: Settings, slug: str, limit: int) -> List[Dict]:
    session_path = _ensure_session(settings, slug)
    turns_dir = session_path / "turns"
    if not turns_dir.exists():
        return []
    records: List[Dict] = []
    def _turn_key(p: Path) -> int:
        try:
            return int(p.stem)
        except ValueError:
            return -1

    for path in sorted(turns_dir.glob("*.json"), key=_turn_key, reverse=True):
        try:
            with path.open(encoding="utf-8") as handle:
                records.append(json.load(handle))
        except Exception:
            continue
        if len(records) >= limit:
            break
    return records


def load_turn_record(settings: Settings, slug: str, turn: int) -> Dict:
    session_path = _ensure_session(settings, slug)
    record_path = session_path / "turns" / f"{turn}.json"
    if not record_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Turn record not found")
    with record_path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _preview_path(session_path: Path, preview_id: str) -> Path:
    preview_dir = session_path / _PREVIEWS_DIRNAME
    preview_dir.mkdir(exist_ok=True)
    return preview_dir / f"{preview_id}.json"


def load_preview_metadata(settings: Settings, slug: str, preview_id: str) -> Dict:
    session_path = _ensure_session(settings, slug)
    preview_file = _preview_path(session_path, preview_id)
    if not preview_file.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Preview not found or expired")
    data = json.loads(preview_file.read_text(encoding="utf-8"))
    if data.get("slug") != slug:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Preview slug mismatch")
    return data


def create_preview(settings: Settings, slug: str, request: PreviewRequest) -> Tuple[str, List[Dict], Dict]:
    session_path = _ensure_session(settings, slug)
    _assert_lock_owner(session_path, request.lock_owner)
    current_state = _validate_state(load_state(settings, slug))
    base_state_dict = current_state.model_dump(mode="json")
    state_hash = _canonical_hash(base_state_dict)

    proposed_state_dict = _apply_state_patch(base_state_dict, request.state_patch or {})
    _validate_state(proposed_state_dict)

    dice_count = len(request.dice_expressions or [])
    next_index = current_state.log_index + 1
    reserved_indices = list(range(next_index, next_index + dice_count))
    if reserved_indices:
        _ensure_entropy_available(settings, reserved_indices[-1])
        entropy_usage = f"Reserve {dice_count} entries starting at {reserved_indices[0]}"
    else:
        entropy_usage = "No dice reserved"

    diffs: List[Dict] = []
    state_changes = summarize_state_diff(base_state_dict, proposed_state_dict)
    if state_changes:
        diffs.append({"path": "state.json", "changes": "; ".join(state_changes)})
    if request.transcript_entry or request.response:
        diffs.append({"path": "transcript.md", "changes": "Append 1 entry"})
    if request.changelog_entry:
        diffs.append({"path": "changelog.md", "changes": "Append changelog entry"})

    preview_id = str(uuid.uuid4())
    preview_metadata = {
        "id": preview_id,
        "slug": slug,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "base_turn": current_state.turn,
        "base_hash": state_hash,
        "state_patch": request.state_patch or {},
        "transcript_entry": request.transcript_entry or request.response,
        "response": request.response,
        "changelog_entry": request.changelog_entry,
        "dice_expressions": request.dice_expressions or [],
        "reserved_indices": reserved_indices,
    }
    _preview_path(session_path, preview_id).write_text(json.dumps(preview_metadata, indent=2), encoding="utf-8")
    entropy_plan = {"indices": reserved_indices, "usage": entropy_usage}
    return preview_id, diffs, entropy_plan


def commit_preview(settings: Settings, slug: str, preview_id: str, lock_owner: Optional[str]) -> Tuple[Dict, Dict]:
    session_path = _ensure_session(settings, slug)
    _assert_lock_owner(session_path, lock_owner)
    preview_file = _preview_path(session_path, preview_id)
    if not preview_file.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Preview not found or expired")
    preview_data = load_preview_metadata(settings, slug, preview_id)

    current_state = _validate_state(load_state(settings, slug))
    current_hash = _canonical_hash(current_state.model_dump(mode="json"))
    if current_state.turn != preview_data.get("base_turn") or current_hash != preview_data.get("base_hash"):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="State changed; preview is stale")

    proposed_state = _apply_state_patch(current_state.model_dump(mode="json"), preview_data.get("state_patch", {}))
    new_log_index = current_state.log_index
    reserved_indices: List[int] = preview_data.get("reserved_indices", [])
    if reserved_indices:
        expected_start = current_state.log_index + 1
        if reserved_indices[0] != expected_start:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Entropy reservation mismatch")
        _ensure_entropy_available(settings, reserved_indices[-1])
        new_log_index = reserved_indices[-1]

    proposed_state["turn"] = current_state.turn + 1
    proposed_state["log_index"] = new_log_index
    proposed_state = _validate_state(proposed_state).model_dump(mode="json")

    # Persist state
    state_path = session_path / "state.json"
    state_path.write_text(json.dumps(proposed_state, indent=2), encoding="utf-8")

    transcript_path = session_path / "transcript.md"
    changelog_path = session_path / "changelog.md"
    transcript_path.touch(exist_ok=True)
    changelog_path.touch(exist_ok=True)
    transcript_entry = preview_data.get("transcript_entry") or preview_data.get("response")
    if transcript_entry:
        with transcript_path.open("a", encoding="utf-8") as handle:
            handle.write(transcript_entry.rstrip() + "\n")
    if preview_data.get("changelog_entry"):
        with changelog_path.open("a", encoding="utf-8") as handle:
            handle.write(str(preview_data["changelog_entry"]).rstrip() + "\n")

    log_indices = {
        "transcript": sum(1 for _ in transcript_path.open(encoding="utf-8")) - 1,
        "changelog": sum(1 for _ in changelog_path.open(encoding="utf-8")) - 1,
    }

    try:
        preview_file.unlink()
    except Exception:
        pass

    return proposed_state, log_indices


# Job management
_jobs: Dict[str, Dict] = {}  # In-memory job store, in production use persistent storage
_executor = ThreadPoolExecutor(max_workers=4)


def create_job(settings: Settings, request: JobCreateRequest) -> Dict:
    job_id = str(uuid.uuid4())
    job = {
        "id": job_id,
        "type": request.type.value,
        "status": JobStatus.PENDING.value,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "params": request.params,
        "progress": {
            "status": JobStatus.PENDING.value,
            "logs": [],
            "entropy_usage": [],
            "diff_preview": [],
            "error": None
        }
    }
    _jobs[job_id] = job
    return deepcopy(job)


def run_job(settings: Settings, job_id: str, request: JobCreateRequest):
    job = _jobs[job_id]
    job["status"] = JobStatus.RUNNING.value
    job["progress"]["status"] = JobStatus.RUNNING.value

    try:
        # Create temp directory for dry-run
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            # Copy session files to temp
            session_slug = request.params.get("slug")
            if not session_slug:
                raise ValueError("Missing slug in params")
            session_path = settings.sessions_path / session_slug
            temp_session = temp_path / session_slug
            shutil.copytree(session_path, temp_session)

            # Run tool in dry-run mode (simulate)
            if request.type.value == "quest-init":
                tool_script = Path(__file__).parent.parent / "quests" / "generator.py"
            else:
                tool_name = request.type.value.replace("-", "_")
                tool_script = Path(__file__).parent.parent / "tools" / f"{tool_name}.py"

            cmd = ["python", str(tool_script), "--slug", session_slug]
            # Add params
            for k, v in request.params.items():
                if k != "slug":
                    cmd.extend([f"--{k}", str(v)])

            # Change to temp dir
            result = subprocess.run(cmd, cwd=temp_path, capture_output=True, text=True)

            job["progress"]["logs"].append(f"Command: {' '.join(cmd)}")
            if result.stdout:
                job["progress"]["logs"].extend(result.stdout.strip().split('\n'))
            if result.stderr:
                job["progress"]["logs"].extend(result.stderr.strip().split('\n'))

            if result.returncode != 0:
                raise Exception(f"Tool failed: {result.stderr}")

            # Compute diffs
            diffs = []
            for file_path in temp_session.rglob("*"):
                if file_path.is_file():
                    rel_path = file_path.relative_to(temp_session)
                    orig_path = session_path / rel_path
                    if orig_path.exists():
                        with open(orig_path) as f:
                            orig_content = f.read()
                        with open(file_path) as f:
                            new_content = f.read()
                        if orig_content != new_content:
                            diffs.append({
                                "path": str(rel_path),
                                "changes": f"Modified {rel_path}"
                            })
                    else:
                        diffs.append({
                            "path": str(rel_path),
                            "changes": f"Created {rel_path}"
                        })

            job["progress"]["diff_preview"] = diffs
            # Placeholder entropy usage
            job["progress"]["entropy_usage"] = [1, 2, 3]  # Would track actual entropy used

        job["status"] = JobStatus.COMPLETED.value
        job["progress"]["status"] = JobStatus.COMPLETED.value

    except Exception as e:
        job["status"] = JobStatus.FAILED.value
        job["progress"]["status"] = JobStatus.FAILED.value
        job["progress"]["error"] = str(e)


def get_job(settings: Settings, job_id: str) -> Dict:
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return _jobs[job_id]


def get_job_progress(settings: Settings, job_id: str) -> Dict:
    job = get_job(settings, job_id)
    return job["progress"]


def commit_job(settings: Settings, job_id: str):
    job = get_job(settings, job_id)
    job["status"] = JobStatus.COMPLETED.value
    job["progress"]["status"] = JobStatus.COMPLETED.value


def cancel_job(settings: Settings, job_id: str):
    job = get_job(settings, job_id)
    if job["status"] == JobStatus.RUNNING.value:
        job["status"] = JobStatus.CANCELLED.value
        job["progress"]["status"] = JobStatus.CANCELLED.value


def load_commit_history(settings: Settings, slug: str) -> List[Dict]:
    """Load commit history from changelog, assuming each line is a commit."""
    session_path = _ensure_session(settings, slug)
    changelog_path = session_path / "changelog.md"
    if not changelog_path.exists():
        return []
    commits = []
    with changelog_path.open() as handle:
        for idx, line in enumerate(handle):
            line = line.strip()
            if line:
                # Placeholder: parse tags, entropy from line or assume
                commits.append({
                    "id": str(idx),
                    "tags": [],  # Placeholder
                    "entropy_indices": [],  # Placeholder
                    "timestamp": datetime.utcnow(),  # Placeholder
                    "description": line
                })
    return commits


def load_session_diff(settings: Settings, slug: str, from_commit: str, to_commit: str) -> List[Dict]:
    """Compute diff between commits. Placeholder: return empty or mock."""
    # In real impl, use git diff or file comparison
    # For now, return mock diff
    return [{"path": "state.json", "changes": f"Diff from {from_commit} to {to_commit}"}]


def load_entropy_history(settings: Settings, slug: str, limit: int) -> List[Dict]:
    """Load entropy history for session. Placeholder: load from global entropy file."""
    # Placeholder: load recent entropy, assume all for session
    entropy = load_entropy_preview(settings, limit)
    history = []
    for entry in entropy:
        history.append({
            "timestamp": datetime.fromisoformat(entry.get("timestamp", datetime.utcnow().isoformat())),
            "who": entry.get("who", "unknown"),
            "what": entry.get("what", "unknown"),
            "indices": entry.get("indices", [])
        })
    return history
