from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timezone
import asyncio
from http import HTTPStatus
import json
import os
import re
from pathlib import Path

import uuid

from fastapi import Depends, FastAPI, Query, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from .config import Settings, get_settings
from .llm import call_llm_api, get_effective_llm_config, persist_llm_config
from .storage_backends.factory import get_storage_backend
from .storage_backends.interfaces import StorageBackend
from .models import (
    SessionSummary, PaginatedResponse,
    LockClaim, LockInfo, TurnResponse, PreviewRequest, PreviewResponse,
    FileDiff, EntropyPlan, CommitRequest, CommitResponse, SessionState,
    JobCreateRequest, JobResponse, JobProgress, JobCommitRequest,
    CommitSummary, DiffResponse, EntropyHistoryEntry, CommitAndNarrateResponse, DMNarration, TurnRecord,
    CharacterCreationRequest, CharacterCreationResponse, PlayerBundleResponse, PlayerTurnRequest, PlayerTurnResponse,
    OpeningSceneRequest,
    RollRequest, RollResult
)
from .narration import generate_dm_narration, generate_opening_narration
from .adventure_hooks import AdventureHooksService, get_adventure_hooks_service
from .auto_save import AutoSaveSystem, get_auto_save_system
from .discovery_log import DiscoveryLog, get_discovery_log, Discovery
from .mood_system import MoodSystem, get_mood_system, Mood
from .npc_relationships import NPCRelationshipService, get_npc_relationship_service
from quests.generator import generate_dynamic_quest

api_app = FastAPI(
    title="Deterministic DM Service",
    description="API surface for deterministic, auditable gameplay data",
)
# Legacy alias so route decorators keep working before we wrap with the UI/static host app.
app = api_app


class LLMNarrativeRequest(BaseModel):
    prompt: str
    context: Optional[Dict] = None
    scene_type: Optional[str] = None
    tone: Optional[str] = None
    max_tokens: Optional[int] = None


class LLMNarrativeResponse(BaseModel):
    narrative: str
    tokens_used: Optional[int] = None
    model: str
    usage: Optional[Dict[str, int]] = None


class LLMConfigRequest(BaseModel):
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None


class LLMConfigResponse(BaseModel):
    api_key_set: bool
    current_model: str
    base_url: str
    temperature: float
    max_tokens: int
    source: str


class NewSessionRequest(BaseModel):
    hook_id: Optional[str] = None
    template_slug: str = "example-rogue"
    slug: Optional[str] = None


class SessionCreateResponse(BaseModel):
    slug: str


def get_settings_dep() -> Settings:
    return get_settings()


def _get_backend(settings: Settings) -> StorageBackend:
    return get_storage_backend(settings)


_MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_PROTECTED_PREFIXES = (
    "/llm/config",
    "/llm/narrate",
    "/adventure-hooks/generate",
    "/quests/generate",
)


@app.middleware("http")
async def api_key_guard(request: Request, call_next):
    api_key = os.getenv("DM_API_KEY")
    if not api_key:
        return await call_next(request)

    path = request.url.path
    normalized = path[4:] if path.startswith("/api") else path
    normalized = normalized if normalized.startswith("/") else f"/{normalized}"
    method = request.method.upper()

    requires_key = method in _MUTATING_METHODS
    if any(normalized.startswith(prefix) for prefix in _PROTECTED_PREFIXES):
        requires_key = True
    if "/llm/narrate" in normalized:
        requires_key = True

    if requires_key and request.headers.get("X-API-Key") != api_key:
        return JSONResponse(status_code=HTTPStatus.UNAUTHORIZED, content={"detail": "unauthorized"})
    return await call_next(request)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/schemas/{schema_name}")
def get_schema(schema_name: str, settings: Settings = Depends(get_settings_dep)) -> dict:
    schema_path = settings.repo_root / "schemas" / f"{schema_name}.schema.json"
    if not schema_path.exists():
        raise HTTPException(status_code=404, detail="Schema not found")
    with schema_path.open() as f:
        return json.load(f)


@app.get("/sessions")
def list_sessions(settings: Settings = Depends(get_settings_dep)) -> List[SessionSummary]:
    backend = _get_backend(settings)
    sessions_data = backend.session.list_sessions(settings)
    return [SessionSummary(**s) for s in sessions_data]


def _slugify_seed(seed: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", seed).strip("-").lower()
    return cleaned or "adventure"


HOOK_OPTIONS = [
    "Classic dungeon",
    "Urban mystery",
    "Wilderness survival",
    "Political intrigue",
    "Horror",
]

_SRD_CLASSES = {
    "barbarian",
    "bard",
    "cleric",
    "druid",
    "fighter",
    "monk",
    "paladin",
    "ranger",
    "rogue",
    "sorcerer",
    "warlock",
    "wizard",
}

_ENTROPY_WINDOW_SIZE = 5

_SKILL_TO_ABILITY = {
    "athletics": "str",
    "perception": "wis",
    "survival": "wis",
    "stealth": "dex",
    "investigation": "int",
    "persuasion": "cha",
}

_ARMOR_RULES = [
    ("half plate", 15, 2),
    ("chain mail", 16, 0),
    ("chain shirt", 13, 2),
    ("scale mail", 14, 2),
    ("breastplate", 14, 2),
    ("plate", 18, 0),
    ("hide", 12, 2),
    ("studded leather", 12, None),
    ("leather", 11, None),
    ("padded", 11, None),
]

_IMPERATIVE_STARTERS = {
    "go", "move", "enter", "leave", "travel", "return", "approach", "retreat",
    "look", "search", "scan", "inspect", "investigate", "explore", "survey", "scout",
    "check", "examine", "observe", "listen", "watch", "follow", "track",
    "talk", "speak", "ask", "question", "negotiate", "persuade", "intimidate",
    "deceive", "barter", "buy", "sell", "tell", "warn", "signal", "call",
    "prepare", "plan", "ready", "rest", "heal", "help", "assist", "protect",
    "defend", "attack", "strike", "cast", "use", "draw", "open", "close",
    "take", "grab", "secure", "save", "rescue", "hide", "sneak", "climb",
    "swim", "jump", "dodge", "wait", "press", "probe", "gather", "do", "try",
}


def _decapitalize(text: str) -> str:
    for idx, char in enumerate(text):
        if char.isalpha():
            return text[:idx] + char.lower() + text[idx + 1:]
    return text


def _starts_with_imperative(text: str) -> bool:
    lowered = text.strip().lower()
    if lowered.startswith(("try to ", "try ")):
        return True
    match = re.match(r"^[\"'(\[]*([a-z]+)", lowered)
    if not match:
        return False
    return match.group(1) in _IMPERATIVE_STARTERS


def _normalize_suggestion(text: str) -> Optional[str]:
    if not text:
        return None
    cleaned = " ".join(str(text).strip().split())
    if not cleaned:
        return None
    if _starts_with_imperative(cleaned):
        return cleaned
    lowered = cleaned.lstrip().lower()
    if lowered.startswith(("a ", "an ", "the ")):
        return f"Try to do {_decapitalize(cleaned)}"
    return f"Try to {_decapitalize(cleaned)}"


def _suggestion_verb(text: str) -> str:
    match = re.match(r"^[\"'(\[]*([a-z]+)", text.strip().lower())
    return match.group(1) if match else ""


def _is_wildcard_suggestion(text: str) -> bool:
    lowered = text.strip().lower()
    return "something unexpected" in lowered or "anything unexpected" in lowered


def _build_suggestions(raw: List[str]) -> List[str]:
    normalized: List[str] = []
    seen = set()
    for item in raw:
        suggestion = _normalize_suggestion(item)
        if not suggestion:
            continue
        key = suggestion.lower()
        if key in seen:
            continue
        seen.add(key)
        normalized.append(suggestion)

    fallback = [
        "Survey the area for clues",
        "Talk to someone nearby",
        "Check your gear",
        "Press the most promising lead",
        "Do something unexpected",
    ]
    wildcard_needed = not any(_is_wildcard_suggestion(s) for s in normalized)
    if wildcard_needed:
        normalized.append(fallback[-1])

    chosen: List[str] = []
    used_verbs = set()
    extras: List[str] = []
    for suggestion in normalized:
        verb = _suggestion_verb(suggestion)
        if verb and verb in used_verbs:
            extras.append(suggestion)
            continue
        used_verbs.add(verb)
        chosen.append(suggestion)
    if len(chosen) < 4:
        for suggestion in extras:
            chosen.append(suggestion)
            if len(chosen) >= 4:
                break
    for suggestion in fallback:
        if len(chosen) >= 5:
            break
        normalized_fallback = _normalize_suggestion(suggestion)
        if not normalized_fallback:
            continue
        if normalized_fallback.lower() in {s.lower() for s in chosen}:
            continue
        chosen.append(normalized_fallback)

    if not any(_is_wildcard_suggestion(s) for s in chosen):
        if len(chosen) >= 5:
            chosen[-1] = "Do something unexpected"
        else:
            chosen.append("Do something unexpected")

    if len(chosen) < 4:
        for suggestion in fallback:
            if len(chosen) >= 4:
                break
            normalized_fallback = _normalize_suggestion(suggestion)
            if normalized_fallback and normalized_fallback.lower() not in {s.lower() for s in chosen}:
                chosen.append(normalized_fallback)

    return chosen[:5]


def _ability_modifier(score: int) -> int:
    return (score - 10) // 2


def _proficiency_bonus(level: int) -> int:
    return 2 + max(0, (level - 1) // 4)


def _class_hit_die(class_name: str) -> int:
    name = (class_name or "").strip().lower()
    if name in {"barbarian"}:
        return 12
    if name in {"fighter", "paladin", "ranger"}:
        return 10
    if name in {"rogue", "bard", "cleric", "druid", "monk", "warlock"}:
        return 8
    if name in {"wizard", "sorcerer"}:
        return 6
    return 8


def _compute_hp(level: int, hit_die: int, con_mod: int) -> int:
    if level <= 1:
        return max(1, hit_die + con_mod)
    avg_per_level = (hit_die // 2) + 1
    total = hit_die + con_mod + (level - 1) * (avg_per_level + con_mod)
    return max(1, total)


def _compute_ac(equipment: List[str], dex_mod: int) -> int:
    lower_items = [item.lower() for item in equipment]
    base_ac = 10
    max_dex = None
    for armor_name, armor_ac, armor_max_dex in _ARMOR_RULES:
        if any(armor_name in item for item in lower_items):
            base_ac = armor_ac
            max_dex = armor_max_dex
            break
    dex_bonus = dex_mod if max_dex is None else min(dex_mod, max_dex)
    shield_bonus = 2 if any("shield" in item for item in lower_items) else 0
    return max(1, base_ac + dex_bonus + shield_bonus)


def _normalize_hook_label(hook: Optional[str]) -> Optional[str]:
    if not hook:
        return None
    cleaned = hook.strip()
    if not cleaned:
        return None
    for option in HOOK_OPTIONS:
        if cleaned.lower() == option.lower():
            return option
    return cleaned


def _build_entropy_window(
    backend: StorageBackend,
    settings: Settings,
    log_index: int,
    window_size: int = _ENTROPY_WINDOW_SIZE,
) -> List[Dict[str, Any]]:
    if window_size <= 0:
        return []
    target = log_index + window_size
    backend.entropy.ensure_available(settings, target)
    window: List[Dict[str, Any]] = []
    for idx in range(log_index + 1, log_index + window_size + 1):
        entry = backend.entropy.load_entry(settings, idx)
        window.append(
            {
                "index": idx,
                "d20": entry.get("d20", []),
                "d100": entry.get("d100", []),
            }
        )
    return window


def _map_d20_to_die(value: int, size: int) -> int:
    return 1 + ((value - 1) % size)


def _roll_abilities_from_entropy(
    backend: StorageBackend,
    settings: Settings,
    slug: str,
) -> Tuple[Dict[str, int], List[int]]:
    state = backend.state.load_state(settings, slug)
    log_index = int(state.get("log_index", 0))
    ability_keys = ["str", "dex", "con", "int", "wis", "cha"]
    rolls: Dict[str, int] = {}
    indices: List[int] = []

    for key in ability_keys:
        log_index += 1
        backend.entropy.ensure_available(settings, log_index)
        entry = backend.entropy.load_entry(settings, log_index)
        d20_values = entry.get("d20") or []
        if len(d20_values) < 4:
            raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail="Entropy entry missing d20 rolls")
        d6_rolls = [_map_d20_to_die(value, 6) for value in d20_values[:4]]
        d6_rolls.sort(reverse=True)
        rolls[key] = sum(d6_rolls[:3])
        indices.append(log_index)

    state["log_index"] = log_index
    backend.state.save_state(settings, slug, state)
    return rolls, indices


@app.post("/sessions", status_code=201)
def create_session(request: NewSessionRequest, settings: Settings = Depends(get_settings_dep)) -> SessionCreateResponse:
    backend = _get_backend(settings)
    base = _slugify_seed(request.slug or request.hook_id or "adventure")
    candidate = base
    suffix = 1
    while True:
        try:
            created = backend.session.create_session(settings, candidate, request.template_slug)
            return SessionCreateResponse(slug=created)
        except HTTPException as exc:
            if exc.status_code == HTTPStatus.CONFLICT:
                candidate = f"{base}-{suffix}"
                suffix += 1
                continue
            raise


@app.get("/sessions/{slug}/state")
def session_state(slug: str, settings: Settings = Depends(get_settings_dep)) -> dict:
    backend = _get_backend(settings)
    return backend.state.load_state(settings, slug)


@app.get("/data/characters/{slug}.json")
def character_data(slug: str, settings: Settings = Depends(get_settings_dep)) -> dict:
    backend = _get_backend(settings)
    return backend.character.load_character(settings, slug)


@app.get("/sessions/{slug}/transcript")
def session_transcript(
    slug: str,
    tail: Optional[int] = Query(None, ge=1, description="Number of entries to return"),
    cursor: Optional[str] = Query(None, description="Cursor for pagination"),
    settings: Settings = Depends(get_settings_dep),
) -> PaginatedResponse:
    backend = _get_backend(settings)
    items, next_cursor = backend.text_logs.load_transcript(settings, slug, tail, cursor)
    return PaginatedResponse(items=items, cursor=next_cursor)


@app.get("/sessions/{slug}/changelog")
def session_changelog(
    slug: str,
    tail: Optional[int] = Query(None, ge=1, description="Number of entries to return"),
    cursor: Optional[str] = Query(None, description="Cursor for pagination"),
    settings: Settings = Depends(get_settings_dep),
) -> PaginatedResponse:
    backend = _get_backend(settings)
    items, next_cursor = backend.text_logs.load_changelog(settings, slug, tail, cursor)
    return PaginatedResponse(items=items, cursor=next_cursor)


@app.get("/sessions/{slug}/quests")
def session_quests(slug: str, settings: Settings = Depends(get_settings_dep)) -> dict:
    backend = _get_backend(settings)
    return {"quests": backend.state.load_quests(settings, slug)}


@app.get("/sessions/{slug}/quests/{quest_id}")
def get_quest(slug: str, quest_id: str, settings: Settings = Depends(get_settings_dep)) -> dict:
    backend = _get_backend(settings)
    quests = backend.state.load_quests(settings, slug)
    if quest_id not in quests:
        raise HTTPException(status_code=404, detail="Quest not found")
    return quests[quest_id]


@app.post("/sessions/{slug}/quests")
def create_quest(slug: str, quest_data: Dict, dry_run: bool = Query(False), settings: Settings = Depends(get_settings_dep)) -> dict:
    backend = _get_backend(settings)
    errors = backend.state.validate_data(quest_data, "quest", settings)
    if errors:
        return {"errors": errors}
    if dry_run:
        return {"diff": f"Would add quest {quest_data.get('id', 'new')}", "warnings": []}
    quest_id = quest_data.get("id", str(uuid.uuid4()))
    backend.state.save_quest(settings, slug, quest_id, quest_data)
    return {"id": quest_id}


@app.put("/sessions/{slug}/quests/{quest_id}")
def update_quest(slug: str, quest_id: str, quest_data: Dict, dry_run: bool = Query(False), settings: Settings = Depends(get_settings_dep)) -> dict:
    backend = _get_backend(settings)
    errors = backend.state.validate_data(quest_data, "quest", settings)
    if errors:
        return {"errors": errors}
    quests = backend.state.load_quests(settings, slug)
    if quest_id not in quests:
        raise HTTPException(status_code=404, detail="Quest not found")
    if dry_run:
        return {"diff": f"Would update quest {quest_id}", "warnings": []}
    backend.state.save_quest(settings, slug, quest_id, quest_data)
    return {"message": "Updated"}


@app.delete("/sessions/{slug}/quests/{quest_id}")
def delete_quest(slug: str, quest_id: str, dry_run: bool = Query(False), settings: Settings = Depends(get_settings_dep)) -> dict:
    backend = _get_backend(settings)
    quests = backend.state.load_quests(settings, slug)
    if quest_id not in quests:
        raise HTTPException(status_code=404, detail="Quest not found")
    if dry_run:
        return {"diff": f"Would delete quest {quest_id}", "warnings": []}
    backend.state.delete_quest(settings, slug, quest_id)
    return {"message": "Deleted"}


@app.get("/sessions/{slug}/npc-memory")
def session_npc_memory(slug: str, settings: Settings = Depends(get_settings_dep)) -> dict:
    backend = _get_backend(settings)
    return {"npc_memory": backend.docs.load_doc(settings, slug, "npc_memory")}


@app.get("/sessions/{slug}/npc-memory/{index}")
def get_npc(slug: str, index: int, settings: Settings = Depends(get_settings_dep)) -> dict:
    backend = _get_backend(settings)
    npcs = backend.docs.load_doc(settings, slug, "npc_memory")
    if index < 0 or index >= len(npcs):
        raise HTTPException(status_code=404, detail="NPC not found")
    return npcs[index]


@app.post("/sessions/{slug}/npc-memory")
def create_npc(slug: str, npc_data: Dict, dry_run: bool = Query(False), settings: Settings = Depends(get_settings_dep)) -> dict:
    backend = _get_backend(settings)
    # Assume no schema
    if dry_run:
        return {"diff": f"Would add NPC {npc_data.get('name', 'new')}", "warnings": []}
    npcs = backend.docs.load_doc(settings, slug, "npc_memory")
    npcs.append(npc_data)
    if not dry_run:
        backend.docs.save_doc(settings, slug, "npc_memory", npcs)
    return {"index": len(npcs) - 1}


@app.put("/sessions/{slug}/npc-memory/{index}")
def update_npc(slug: str, index: int, npc_data: Dict, dry_run: bool = Query(False), settings: Settings = Depends(get_settings_dep)) -> dict:
    backend = _get_backend(settings)
    npcs = backend.docs.load_doc(settings, slug, "npc_memory")
    if index < 0 or index >= len(npcs):
        raise HTTPException(status_code=404, detail="NPC not found")
    if dry_run:
        return {"diff": f"Would update NPC at {index}", "warnings": []}
    npcs[index] = npc_data
    backend.docs.save_doc(settings, slug, "npc_memory", npcs)
    return {"message": "Updated"}


@app.delete("/sessions/{slug}/npc-memory/{index}")
def delete_npc(slug: str, index: int, dry_run: bool = Query(False), settings: Settings = Depends(get_settings_dep)) -> dict:
    backend = _get_backend(settings)
    npcs = backend.docs.load_doc(settings, slug, "npc_memory")
    if index < 0 or index >= len(npcs):
        raise HTTPException(status_code=404, detail="NPC not found")
    if dry_run:
        return {"diff": f"Would delete NPC at {index}", "warnings": []}
    npcs.pop(index)
    backend.docs.save_doc(settings, slug, "npc_memory", npcs)
    return {"message": "Deleted"}


@app.get("/sessions/{slug}/world/factions")
def session_factions(slug: str, settings: Settings = Depends(get_settings_dep)) -> dict:
    backend = _get_backend(settings)
    return backend.world.load_factions(settings, slug)


@app.get("/sessions/{slug}/world/factions/{faction_id}")
def get_faction(slug: str, faction_id: str, settings: Settings = Depends(get_settings_dep)) -> dict:
    backend = _get_backend(settings)
    factions = backend.world.load_factions(settings, slug)
    if faction_id not in factions:
        raise HTTPException(status_code=404, detail="Faction not found")
    return factions[faction_id]


@app.post("/sessions/{slug}/world/factions")
def create_faction(slug: str, faction_data: Dict, dry_run: bool = Query(False), settings: Settings = Depends(get_settings_dep)) -> dict:
    backend = _get_backend(settings)
    # Assume no schema for faction
    if dry_run:
        return {"diff": f"Would add faction {faction_data.get('id', 'new')}", "warnings": []}
    faction_id = faction_data.get("id", str(uuid.uuid4()))
    backend.world.save_faction(settings, slug, faction_id, faction_data)
    return {"id": faction_id}


@app.put("/sessions/{slug}/world/factions/{faction_id}")
def update_faction(slug: str, faction_id: str, faction_data: Dict, dry_run: bool = Query(False), settings: Settings = Depends(get_settings_dep)) -> dict:
    backend = _get_backend(settings)
    factions = backend.world.load_factions(settings, slug)
    if faction_id not in factions:
        raise HTTPException(status_code=404, detail="Faction not found")
    if dry_run:
        return {"diff": f"Would update faction {faction_id}", "warnings": []}
    backend.world.save_faction(settings, slug, faction_id, faction_data)
    return {"message": "Updated"}


@app.delete("/sessions/{slug}/world/factions/{faction_id}")
def delete_faction(slug: str, faction_id: str, dry_run: bool = Query(False), settings: Settings = Depends(get_settings_dep)) -> dict:
    backend = _get_backend(settings)
    factions = backend.world.load_factions(settings, slug)
    if faction_id not in factions:
        raise HTTPException(status_code=404, detail="Faction not found")
    if dry_run:
        return {"diff": f"Would delete faction {faction_id}", "warnings": []}
    backend.world.delete_faction(settings, slug, faction_id)
    return {"message": "Deleted"}


@app.get("/sessions/{slug}/world/timeline")
def session_timeline(slug: str, settings: Settings = Depends(get_settings_dep)) -> dict:
    backend = _get_backend(settings)
    return backend.world.load_timeline(settings, slug)


@app.post("/sessions/{slug}/world/timeline")
def create_timeline_event(slug: str, event_data: Dict, dry_run: bool = Query(False), settings: Settings = Depends(get_settings_dep)) -> dict:
    backend = _get_backend(settings)
    if dry_run:
        return {"diff": f"Would add timeline event {event_data.get('id', 'new')}", "warnings": []}
    event_id = event_data.get("id", str(uuid.uuid4()))
    backend.world.save_timeline_event(settings, slug, event_id, event_data)
    return {"id": event_id}


@app.put("/sessions/{slug}/world/timeline/{event_id}")
def update_timeline_event(slug: str, event_id: str, event_data: Dict, dry_run: bool = Query(False), settings: Settings = Depends(get_settings_dep)) -> dict:
    backend = _get_backend(settings)
    timeline = backend.world.load_timeline(settings, slug)
    if event_id not in timeline:
        raise HTTPException(status_code=404, detail="Event not found")
    if dry_run:
        return {"diff": f"Would update timeline event {event_id}", "warnings": []}
    backend.world.save_timeline_event(settings, slug, event_id, event_data)
    return {"message": "Updated"}


@app.delete("/sessions/{slug}/world/timeline/{event_id}")
def delete_timeline_event(slug: str, event_id: str, dry_run: bool = Query(False), settings: Settings = Depends(get_settings_dep)) -> dict:
    backend = _get_backend(settings)
    timeline = backend.world.load_timeline(settings, slug)
    if event_id not in timeline:
        raise HTTPException(status_code=404, detail="Event not found")
    if dry_run:
        return {"diff": f"Would delete timeline event {event_id}", "warnings": []}
    backend.world.delete_timeline_event(settings, slug, event_id)
    return {"message": "Deleted"}


@app.get("/sessions/{slug}/world/rumors")
def session_rumors(slug: str, settings: Settings = Depends(get_settings_dep)) -> dict:
    backend = _get_backend(settings)
    return backend.world.load_rumors(settings, slug)


@app.get("/sessions/{slug}/world/faction-clocks")
def session_faction_clocks(slug: str, settings: Settings = Depends(get_settings_dep)) -> dict:
    backend = _get_backend(settings)
    return backend.world.load_faction_clocks(settings, slug)


@app.get("/sessions/{slug}/turn")
def get_turn(slug: str, settings: Settings = Depends(get_settings_dep)) -> TurnResponse:
    backend = _get_backend(settings)
    prompt = backend.turn.load_turn(settings, slug)
    state = backend.state.load_state(settings, slug)
    turn_number = state.get("turn", 0)
    lock_info = backend.session.get_lock_info(settings, slug)
    return TurnResponse(prompt=prompt, turn_number=turn_number, lock_status=lock_info)


@app.post("/sessions/{slug}/lock/claim")
def claim_lock(slug: str, claim: LockClaim, settings: Settings = Depends(get_settings_dep)):
    backend = _get_backend(settings)
    backend.session.claim_lock(settings, slug, claim.owner, claim.ttl)
    return {"message": "Lock claimed"}


@app.delete("/sessions/{slug}/lock")
def release_lock(slug: str, settings: Settings = Depends(get_settings_dep)):
    backend = _get_backend(settings)
    backend.session.release_lock(settings, slug)
    return {"message": "Lock released"}


@app.post("/sessions/{slug}/turn/preview")
def preview_turn(slug: str, request: PreviewRequest, settings: Settings = Depends(get_settings_dep)) -> PreviewResponse:
    backend = _get_backend(settings)
    preview_id, diffs, entropy_plan = backend.turn.create_preview(settings, slug, request)
    file_diffs = [FileDiff(path=d["path"], changes=d["changes"]) for d in diffs]
    ep = EntropyPlan(indices=entropy_plan["indices"], usage=entropy_plan["usage"])
    return PreviewResponse(id=preview_id, diffs=file_diffs, entropy_plan=ep)


@app.post("/sessions/{slug}/turn/commit")
def commit_turn(slug: str, request: CommitRequest, settings: Settings = Depends(get_settings_dep)) -> CommitResponse:
    backend = _get_backend(settings)
    state, log_indices = backend.turn.commit_preview(settings, slug, request.preview_id, request.lock_owner)
    session_state = SessionState(**state)
    return CommitResponse(state=session_state, log_indices=log_indices)


async def _commit_and_narrate_internal(
    settings: Settings,
    slug: str,
    request: CommitRequest,
) -> CommitAndNarrateResponse:
    backend = _get_backend(settings)
    state_before = backend.state.load_state(settings, slug)
    last_discovery_turn = backend.docs.get_last_discovery_turn(settings, slug)
    preview_data = backend.turn.load_preview_metadata(settings, slug, request.preview_id)
    state, log_indices = backend.turn.commit_preview(settings, slug, request.preview_id, request.lock_owner)
    session_state = SessionState(**state)
    diff = backend.turn.summarize_state_diff(state_before, state)
    player_intent = preview_data.get("response", "")
    include_discovery = last_discovery_turn is None or session_state.turn - last_discovery_turn > 2

    try:
        character = backend.character.load_character(settings, slug)
    except Exception:
        character = {}

    dm_output, usage = await generate_dm_narration(
        settings,
        slug,
        session_state.model_dump(mode="json"),
        state_before,
        player_intent,
        diff,
        character=character,
        include_discovery=include_discovery,
    )
    if dm_output.discovery_added:
        discovery_log = get_discovery_log(slug, settings.storage_root)
        discovery_log.create_discovery(
            name=dm_output.discovery_added.title,
            discovery_type="rumor",
            description=dm_output.discovery_added.text,
            location=session_state.location,
            importance=1,
        )
        backend.docs.record_last_discovery_turn(settings, slug, session_state.turn)
    consequence_echo = dm_output.consequence_echo or "A new consequence unfolds."
    record_payload = TurnRecord(
        turn=session_state.turn,
        player_intent=player_intent,
        diff=diff,
        consequence_echo=consequence_echo,
        dm=dm_output,
        created_at=datetime.now(timezone.utc),
    ).model_dump(mode="json")
    backend.turn.persist_turn_record(settings, slug, record_payload)

    response = CommitAndNarrateResponse(
        commit=CommitResponse(state=session_state, log_indices=log_indices),
        dm=dm_output,
        turn_record=TurnRecord(**record_payload),
        usage=usage,
    )
    return response


async def _commit_and_narrate_opening(
    settings: Settings,
    slug: str,
    request: CommitRequest,
    hook_label: Optional[str],
    character: Optional[Dict],
) -> CommitAndNarrateResponse:
    backend = _get_backend(settings)
    state_before = backend.state.load_state(settings, slug)
    last_discovery_turn = backend.docs.get_last_discovery_turn(settings, slug)
    preview_data = backend.turn.load_preview_metadata(settings, slug, request.preview_id)
    state, log_indices = backend.turn.commit_preview(settings, slug, request.preview_id, request.lock_owner)
    session_state = SessionState(**state)
    diff = backend.turn.summarize_state_diff(state_before, state)
    player_intent = preview_data.get("response", "")
    include_discovery = last_discovery_turn is None or session_state.turn - last_discovery_turn > 2

    dm_output, usage = await generate_opening_narration(
        settings,
        slug,
        session_state.model_dump(mode="json"),
        state_before,
        player_intent,
        diff,
        character,
        hook_label,
        include_discovery=include_discovery,
    )
    if dm_output.discovery_added:
        discovery_log = get_discovery_log(slug, settings.storage_root)
        discovery_log.create_discovery(
            name=dm_output.discovery_added.title,
            discovery_type="rumor",
            description=dm_output.discovery_added.text,
            location=session_state.location,
            importance=1,
        )
        backend.docs.record_last_discovery_turn(settings, slug, session_state.turn)
    consequence_echo = dm_output.consequence_echo or "A new consequence unfolds."
    record_payload = TurnRecord(
        turn=session_state.turn,
        player_intent=player_intent,
        diff=diff,
        consequence_echo=consequence_echo,
        dm=dm_output,
        created_at=datetime.now(timezone.utc),
    ).model_dump(mode="json")
    backend.turn.persist_turn_record(settings, slug, record_payload)

    response = CommitAndNarrateResponse(
        commit=CommitResponse(state=session_state, log_indices=log_indices),
        dm=dm_output,
        turn_record=TurnRecord(**record_payload),
        usage=usage,
    )
    return response


@app.post("/sessions/{slug}/turn/commit-and-narrate")
async def commit_and_narrate(
    slug: str,
    request: CommitRequest,
    settings: Settings = Depends(get_settings_dep)
) -> CommitAndNarrateResponse:
    return await _commit_and_narrate_internal(settings, slug, request)


@app.post("/sessions/{slug}/character", status_code=201)
def create_character_for_session(
    slug: str,
    request: CharacterCreationRequest,
    settings: Settings = Depends(get_settings_dep),
) -> CharacterCreationResponse:
    backend = _get_backend(settings)
    class_name = request.class_name.strip().lower()
    if class_name not in _SRD_CLASSES:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="Class must be SRD-only.")
    state = backend.state.load_state(settings, slug)
    equipment = request.equipment or []
    ability_scores = request.abilities.model_dump(by_alias=True)
    dex_mod = _ability_modifier(request.abilities.dex)
    con_mod = _ability_modifier(request.abilities.con)
    hit_die = _class_hit_die(request.class_name)
    derived_hp = _compute_hp(request.level, hit_die, con_mod)
    derived_ac = _compute_ac(equipment, dex_mod)
    prof_bonus = _proficiency_bonus(request.level)
    skills_map = {}
    for skill in request.skills or []:
        skill_key = str(skill).lower().replace(" ", "_")
        ability_key = _SKILL_TO_ABILITY.get(skill_key)
        if not ability_key:
            continue
        ability_score = ability_scores.get(ability_key)
        if ability_score is None:
            continue
        skills_map[skill_key] = _ability_modifier(ability_score) + prof_bonus
    hook_label = _normalize_hook_label(request.hook)
    character_payload = {
        "slug": slug,
        "name": request.name,
        "race": request.ancestry,
        "class": request.class_name,
        "background": request.background,
        "level": request.level,
        "hp": derived_hp,
        "ac": derived_ac,
        "abilities": ability_scores,
        "skills": skills_map,
        "proficiencies": {
          "skills": request.skills,
          "tools": request.tools,
          "languages": request.languages,
        },
        "inventory": equipment,
        "starting_equipment": equipment,
        "features": [],
        "notes": request.notes or "",
        "creation_source": "player",
        "spells": request.spells,
        "method": request.method,
    }
    saved_character = backend.character.save_character(settings, slug, character_payload, persist_to_data=True)

    state["character"] = slug
    state["hp"] = derived_hp
    state["max_hp"] = derived_hp
    state["level"] = request.level
    state["inventory"] = equipment
    state["gp"] = request.gp
    if request.starting_location:
        state["location"] = request.starting_location
    state["ac"] = derived_ac
    state["abilities"] = ability_scores
    if request.spells:
        state["spells"] = request.spells
    if hook_label:
        state["adventure_hook"] = {"label": hook_label}
    if not state.get("conditions"):
        state["conditions"] = []
    if not state.get("flags"):
        state["flags"] = {}
    updated_state = backend.state.save_state(settings, slug, state)
    return CharacterCreationResponse(character=saved_character, state=updated_state)


@app.post("/sessions/{slug}/character/roll-abilities")
def roll_character_abilities(
    slug: str,
    settings: Settings = Depends(get_settings_dep),
) -> Dict[str, Any]:
    backend = _get_backend(settings)
    rolls, indices = _roll_abilities_from_entropy(backend, settings, slug)
    return {"abilities": rolls, "entropy_indices": indices}


@app.get("/sessions/{slug}/player")
def get_player_bundle(slug: str, settings: Settings = Depends(get_settings_dep)) -> PlayerBundleResponse:
    backend = _get_backend(settings)
    state = SessionState(**backend.state.load_state(settings, slug))
    try:
        character = backend.character.load_character(settings, slug)
    except HTTPException:
        character = {}
    recaps_raw = backend.turn.load_turn_records(settings, slug, limit=3)
    recaps = [TurnRecord(**r) for r in recaps_raw]
    discovery_log = get_discovery_log(slug, settings.storage_root)
    discoveries = [d.to_dict() for d in discovery_log.get_recent_discoveries(5)]
    quests = backend.state.load_quests(settings, slug)
    raw_suggestions: List[str] = []
    if recaps and recaps[0].dm and recaps[0].dm.choices:
        raw_suggestions = [choice.text for choice in recaps[0].dm.choices if choice.text]
    if not raw_suggestions:
        raw_suggestions = [
            "Survey the area for clues",
            "Talk to someone nearby",
            "Check your gear and supplies",
            "Look for a safe path forward",
            "Take a breather and plan",
        ]
    suggestions = _build_suggestions(raw_suggestions)
    return PlayerBundleResponse(
        state=state,
        character=character,
        recaps=recaps,
        discoveries=discoveries,
        quests=quests,
        suggestions=suggestions,
    )


@app.post("/sessions/{slug}/player/opening")
async def player_opening_scene(
    slug: str,
    request: OpeningSceneRequest,
    settings: Settings = Depends(get_settings_dep),
) -> PlayerTurnResponse:
    backend = _get_backend(settings)
    owner = "player-ui"
    claimed_here = False
    lock_info = backend.session.get_lock_info(settings, slug)
    if lock_info and lock_info.owner != owner:
        raise HTTPException(status_code=HTTPStatus.CONFLICT, detail="Session is busy right now. Try again in a moment.")
    if lock_info is None:
        backend.session.claim_lock(settings, slug, owner, ttl=300)
        claimed_here = True
    try:
        state = backend.state.load_state(settings, slug)
        entropy_window = _build_entropy_window(backend, settings, state.get("log_index", 0))
        try:
            character = backend.character.load_character(settings, slug)
        except HTTPException:
            character = {}
        hook_label = _normalize_hook_label(request.hook)
        existing_hook = state.get("adventure_hook", {})
        if not hook_label:
            if isinstance(existing_hook, dict):
                hook_label = existing_hook.get("label")
        if not hook_label:
            hook_label = HOOK_OPTIONS[0]
        state_patch = {}
        if hook_label:
            existing_label = existing_hook.get("label") if isinstance(existing_hook, dict) else None
            if existing_label != hook_label:
                state_patch["adventure_hook"] = {"label": hook_label}

        include_discovery = True
        dm_output, usage = await generate_opening_narration(
            settings,
            slug,
            state,
            state,
            "Opening scene",
            [],
            character,
            hook_label,
            include_discovery=include_discovery,
            entropy_window=entropy_window,
        )
        combined_patch = dict(state_patch)
        if dm_output.state_patch:
            combined_patch.update(dm_output.state_patch)

        preview_id, _, _ = backend.turn.create_preview(
            settings,
            slug,
            PreviewRequest(
                response="Opening scene",
                state_patch=combined_patch,
                transcript_entry=f"Player: Opening scene\nDM: {dm_output.narration}",
                lock_owner=owner,
                dice_expressions=dm_output.dice_expressions,
            ),
        )
        commit_request = CommitRequest(preview_id=preview_id, lock_owner=owner)
        state_before = state
        state_after, log_indices = backend.turn.commit_preview(settings, slug, commit_request.preview_id, commit_request.lock_owner)
        session_state = SessionState(**state_after)
        diff = backend.turn.summarize_state_diff(state_before, state_after)
        if dm_output.discovery_added:
            discovery_log = get_discovery_log(slug, settings.storage_root)
            discovery_log.create_discovery(
                name=dm_output.discovery_added.title,
                discovery_type="rumor",
                description=dm_output.discovery_added.text,
                location=session_state.location,
                importance=1,
            )
            backend.docs.record_last_discovery_turn(settings, slug, session_state.turn)
        consequence_echo = dm_output.consequence_echo or "A new consequence unfolds."
        record_payload = TurnRecord(
            turn=session_state.turn,
            player_intent="Opening scene",
            diff=diff,
            consequence_echo=consequence_echo,
            dm=dm_output,
            created_at=datetime.now(timezone.utc),
        ).model_dump(mode="json")
        backend.turn.persist_turn_record(settings, slug, record_payload)
        result = CommitAndNarrateResponse(
            commit=CommitResponse(state=session_state, log_indices=log_indices),
            dm=dm_output,
            turn_record=TurnRecord(**record_payload),
            usage=usage,
        )
    finally:
        if claimed_here:
            backend.session.release_lock(settings, slug)

    raw_suggestions = [choice.text for choice in result.dm.choices if choice and getattr(choice, "text", None)] if result.dm.choices else []
    if not raw_suggestions:
        raw_suggestions = [
            "Probe the surroundings",
            "Strike up a conversation",
            "Prepare for trouble",
            "Take stock of your gear",
            "Move cautiously ahead",
        ]
    suggestions = _build_suggestions(raw_suggestions)
    return PlayerTurnResponse(
        state=result.commit.state,
        narration=result.dm,
        turn_record=result.turn_record,
        suggestions=suggestions,
        roll_request=result.dm.roll_request,
    )


@app.post("/sessions/{slug}/roll")
def player_roll(slug: str, request: RollRequest, settings: Settings = Depends(get_settings_dep)) -> RollResult:
    backend = _get_backend(settings)
    try:
        return backend.turn.perform_roll(settings, slug, request)
    except HTTPException as exc:
        if exc.status_code >= 500:
            raise exc
        raise HTTPException(status_code=exc.status_code, detail="The DM couldn't respond. Try again in a moment.") from exc
    except Exception:
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail="The DM couldn't respond. Try again in a moment.")


@app.post("/sessions/{slug}/player/roll")
def player_roll_legacy(slug: str, request: RollRequest, settings: Settings = Depends(get_settings_dep)) -> RollResult:
    return player_roll(slug, request, settings)


@app.post("/sessions/{slug}/player/turn")
async def player_turn(
    slug: str,
    request: PlayerTurnRequest,
    settings: Settings = Depends(get_settings_dep),
) -> PlayerTurnResponse:
    backend = _get_backend(settings)
    if request.state_patch:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="state_patch is DM-controlled.")
    owner = "player-ui"
    claimed_here = False
    lock_info = backend.session.get_lock_info(settings, slug)
    if lock_info and lock_info.owner != owner:
        raise HTTPException(status_code=HTTPStatus.CONFLICT, detail="Session is busy right now. Try again in a moment.")
    if lock_info is None:
        backend.session.claim_lock(settings, slug, owner, ttl=300)
        claimed_here = True
    try:
        state_before = backend.state.load_state(settings, slug)
        try:
            character = backend.character.load_character(settings, slug)
        except Exception:
            character = {}
        last_discovery_turn = backend.docs.get_last_discovery_turn(settings, slug)
        include_discovery = last_discovery_turn is None or (state_before.get("turn", 0) + 1) - last_discovery_turn > 2
        entropy_window = _build_entropy_window(backend, settings, state_before.get("log_index", 0))

        dm_output, usage = await generate_dm_narration(
            settings,
            slug,
            state_before,
            state_before,
            request.action,
            [],
            character=character,
            include_discovery=include_discovery,
            entropy_window=entropy_window,
        )

        preview_id, _, _ = backend.turn.create_preview(
            settings,
            slug,
            PreviewRequest(
                response=request.action,
                state_patch=dm_output.state_patch,
                transcript_entry=f"Player: {request.action}\nDM: {dm_output.narration}",
                lock_owner=owner,
                dice_expressions=dm_output.dice_expressions,
            ),
        )
        commit_request = CommitRequest(preview_id=preview_id, lock_owner=owner)
        state_after, log_indices = backend.turn.commit_preview(settings, slug, commit_request.preview_id, commit_request.lock_owner)
        session_state = SessionState(**state_after)
        diff = backend.turn.summarize_state_diff(state_before, state_after)

        if dm_output.discovery_added:
            discovery_log = get_discovery_log(slug, settings.storage_root)
            discovery_log.create_discovery(
                name=dm_output.discovery_added.title,
                discovery_type="rumor",
                description=dm_output.discovery_added.text,
                location=session_state.location,
                importance=1,
            )
            backend.docs.record_last_discovery_turn(settings, slug, session_state.turn)
        consequence_echo = dm_output.consequence_echo or "A new consequence unfolds."
        record_payload = TurnRecord(
            turn=session_state.turn,
            player_intent=request.action,
            diff=diff,
            consequence_echo=consequence_echo,
            dm=dm_output,
            created_at=datetime.now(timezone.utc),
        ).model_dump(mode="json")
        backend.turn.persist_turn_record(settings, slug, record_payload)
        result = CommitAndNarrateResponse(
            commit=CommitResponse(state=session_state, log_indices=log_indices),
            dm=dm_output,
            turn_record=TurnRecord(**record_payload),
            usage=usage,
        )
    finally:
        if claimed_here:
            backend.session.release_lock(settings, slug)

    raw_suggestions = [choice.text for choice in result.dm.choices if choice and getattr(choice, "text", None)] if result.dm.choices else []
    if not raw_suggestions:
        raw_suggestions = [
            "Probe the surroundings",
            "Strike up a conversation",
            "Prepare for trouble",
            "Take stock of your gear",
            "Move cautiously ahead",
        ]
    suggestions = _build_suggestions(raw_suggestions)
    return PlayerTurnResponse(
        state=result.commit.state,
        narration=result.dm,
        turn_record=result.turn_record,
        suggestions=suggestions,
        roll_request=result.dm.roll_request,
    )


@app.post("/jobs/explore")
def create_explore_job(request: JobCreateRequest, settings: Settings = Depends(get_settings_dep)) -> JobResponse:
    raise HTTPException(status_code=501, detail="Job automation is disabled. Run the CLI tools directly under a session lock.")


@app.post("/jobs/resolve-encounter")
def create_resolve_encounter_job(request: JobCreateRequest, settings: Settings = Depends(get_settings_dep)) -> JobResponse:
    raise HTTPException(status_code=501, detail="Job automation is disabled. Run the CLI tools directly under a session lock.")


@app.post("/jobs/loot")
def create_loot_job(request: JobCreateRequest, settings: Settings = Depends(get_settings_dep)) -> JobResponse:
    raise HTTPException(status_code=501, detail="Job automation is disabled. Run the CLI tools directly under a session lock.")


@app.post("/jobs/downtime")
def create_downtime_job(request: JobCreateRequest, settings: Settings = Depends(get_settings_dep)) -> JobResponse:
    raise HTTPException(status_code=501, detail="Job automation is disabled. Run the CLI tools directly under a session lock.")


@app.post("/jobs/quest/init")
def create_quest_init_job(request: JobCreateRequest, settings: Settings = Depends(get_settings_dep)) -> JobResponse:
    raise HTTPException(status_code=501, detail="Job automation is disabled. Run the CLI tools directly under a session lock.")


@app.get("/jobs/{job_id}")
def get_job_progress(job_id: str, settings: Settings = Depends(get_settings_dep)) -> JobProgress:
    raise HTTPException(status_code=501, detail="Job automation is disabled.")


@app.post("/jobs/{job_id}/commit")
def commit_job(job_id: str, settings: Settings = Depends(get_settings_dep)):
    raise HTTPException(status_code=501, detail="Job automation is disabled.")


@app.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str, settings: Settings = Depends(get_settings_dep)):
    raise HTTPException(status_code=501, detail="Job automation is disabled.")


@app.get("/entropy")
def entropy_preview(
    limit: int = Query(5, ge=1, le=50, description="Number of entropy records to preview"),
    settings: Settings = Depends(get_settings_dep),
) -> dict:
    backend = _get_backend(settings)
    return {"entropy": backend.entropy.load_entropy_preview(settings, limit)}


@app.get("/sessions/{slug}/history/commits", tags=["History"], summary="Get commit history for a session")
def session_commit_history(slug: str, settings: Settings = Depends(get_settings_dep)) -> List[CommitSummary]:
    backend = _get_backend(settings)
    commits_data = backend.turn.load_commit_history(settings, slug)
    return [CommitSummary(**c) for c in commits_data]


@app.get("/sessions/{slug}/diff", tags=["History"], summary="Get diff between two commits")
def session_diff(
    slug: str,
    from_commit: str = Query(..., description="From commit ID"),
    to: str = Query(..., description="To commit ID"),
    settings: Settings = Depends(get_settings_dep),
    ) -> DiffResponse:
        backend = _get_backend(settings)
        diffs = backend.turn.load_session_diff(settings, slug, from_commit, to)
        file_diffs = [FileDiff(path=d["path"], changes=d["changes"]) for d in diffs]
        return DiffResponse(files=file_diffs)


@app.get("/sessions/{slug}/turns")
def list_turn_records(slug: str, limit: int = Query(3, ge=1, le=25), settings: Settings = Depends(get_settings_dep)) -> List[TurnRecord]:
    backend = _get_backend(settings)
    records = backend.turn.load_turn_records(settings, slug, limit)
    return [TurnRecord(**r) for r in records]


@app.get("/sessions/{slug}/turns/{turn}")
def get_turn_record(slug: str, turn: int, settings: Settings = Depends(get_settings_dep)) -> TurnRecord:
    backend = _get_backend(settings)
    record = backend.turn.load_turn_record(settings, slug, turn)
    return TurnRecord(**record)


@app.get("/sessions/{slug}/entropy/history", tags=["Observability"], summary="Get entropy usage history for a session")
def session_entropy_history(
    slug: str,
    limit: int = Query(10, ge=1, le=100, description="Number of entries to return"),
    settings: Settings = Depends(get_settings_dep),
) -> List[EntropyHistoryEntry]:
    backend = _get_backend(settings)
    history_data = backend.entropy.load_entropy_history(settings, slug, limit)
    return [EntropyHistoryEntry(**h) for h in history_data]


@app.get("/llm/config", tags=["LLM"], summary="Get current LLM configuration")
def get_llm_config(settings: Settings = Depends(get_settings_dep)) -> LLMConfigResponse:
    effective = get_effective_llm_config(settings)
    return LLMConfigResponse(
        api_key_set=effective.api_key is not None and len(effective.api_key) > 0,
        current_model=effective.model,
        base_url=effective.base_url,
        temperature=effective.temperature,
        max_tokens=effective.max_tokens,
        source=effective.source,
    )


@app.post("/llm/config", tags=["LLM"], summary="Configure LLM API settings")
def configure_llm(
    config: LLMConfigRequest,
    settings: Settings = Depends(get_settings_dep)
) -> LLMConfigResponse:
    effective = persist_llm_config(
        settings,
        {
            "api_key": config.api_key,
            "base_url": config.base_url,
            "model": config.model,
        },
    )
    return LLMConfigResponse(
        api_key_set=effective.api_key is not None and len(effective.api_key) > 0,
        current_model=effective.model,
        base_url=effective.base_url,
        temperature=effective.temperature,
        max_tokens=effective.max_tokens,
        source=effective.source,
    )


@app.post("/llm/narrate", tags=["LLM"], summary="Generate narrative text using LLM")
async def generate_narrative(
    request: LLMNarrativeRequest,
    settings: Settings = Depends(get_settings_dep)
) -> LLMNarrativeResponse:
    effective = get_effective_llm_config(settings)
    result = await call_llm_api(
        settings,
        request.prompt,
        request.context,
        request.max_tokens
    )
    usage = result.get("usage")
    return LLMNarrativeResponse(
        narrative=result["content"],
        tokens_used=usage.get("total_tokens") if usage else None,
        usage=usage,
        model=effective.model
    )


@app.post("/sessions/{slug}/llm/narrate", tags=["LLM"], summary="Generate scene narrative with context")
async def generate_scene_narrative(
    slug: str,
    request: LLMNarrativeRequest,
    settings: Settings = Depends(get_settings_dep)
) -> LLMNarrativeResponse:
    # Load session context
    backend = _get_backend(settings)
    state = backend.state.load_state(settings, slug)
    character = backend.character.load_character(settings, slug)
    
    # Build context from session
    context = {
        "character": character,
        "current_state": state,
        "scene_type": request.scene_type,
        "tone": request.tone
    }
    
    # Combine with any additional context from request
    if request.context:
        context.update(request.context)
    
    effective = get_effective_llm_config(settings)
    result = await call_llm_api(
        settings,
        request.prompt,
        context,
        request.max_tokens
    )
    usage = result.get("usage")
    
    return LLMNarrativeResponse(
        narrative=result["content"],
        tokens_used=usage.get("total_tokens") if usage else None,
        usage=usage,
        model=effective.model
    )


# Adventure Hooks Endpoints
class AdventureHookResponse(BaseModel):
    hook_id: str
    title: str
    description: str
    hook_type: str
    location: str
    difficulty: str
    rewards: List[str]
    starting_scene: str


@app.get("/adventure-hooks", tags=["Adventure"], summary="Get all available adventure hooks")
def get_adventure_hooks():
    """Get all available adventure hooks for starting a new session"""
    hooks_service = get_adventure_hooks_service()
    hooks = hooks_service.get_available_hooks()
    return [AdventureHookResponse(**hook.to_dict()) for hook in hooks]


@app.get("/adventure-hooks/recommended", tags=["Adventure"], summary="Get recommended adventure hooks")
def get_recommended_hooks(
    character_class: Optional[str] = Query(None, description="Character class for recommendations"),
    character_level: int = Query(1, ge=1, le=20, description="Character level")
):
    """Get adventure hooks recommended for a specific character"""
    hooks_service = get_adventure_hooks_service()
    hooks = hooks_service.get_recommended_hooks(character_class, character_level)
    return [AdventureHookResponse(**hook.to_dict()) for hook in hooks]


@app.get("/adventure-hooks/{hook_id}", tags=["Adventure"], summary="Get a specific adventure hook")
def get_adventure_hook(hook_id: str):
    """Get details for a specific adventure hook"""
    hooks_service = get_adventure_hooks_service()
    hook = hooks_service.get_hook_by_id(hook_id)
    
    if not hook:
        raise HTTPException(status_code=404, detail="Adventure hook not found")
    
    return AdventureHookResponse(**hook.to_dict())


@app.post("/adventure-hooks/generate", tags=["Adventure"], summary="Generate a custom adventure hook")
async def generate_custom_hook(
    character_context: Dict,
    settings: Settings = Depends(get_settings_dep)
):
    """Generate a custom adventure hook using LLM based on character context"""
    hooks_service = get_adventure_hooks_service()
    
    try:
        hook = await hooks_service.generate_llm_enhanced_hook(character_context)
        return AdventureHookResponse(**hook.to_dict())
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate custom hook: {str(e)}"
        )


# Dynamic Quest Generation Endpoints
class QuestResponse(BaseModel):
    id: str
    name: str
    description: str
    objectives: List[str]
    rewards: List[str]
    difficulty: str
    starting_scene: str
    quest_type: str
    character_name: Optional[str] = None
    character_class: Optional[str] = None
    character_level: Optional[int] = None
    starting_location: Optional[str] = None


@app.post("/quests/generate", tags=["Quests"], summary="Generate a dynamic quest")
def generate_dynamic_quest_endpoint(
    character_context: Dict,
    session_context: Dict,
    use_llm: bool = Query(False, description="Use LLM for enhanced quest generation")
):
    """Generate a dynamic quest based on character and session context"""
    try:
        quest = generate_dynamic_quest(character_context, session_context, use_llm)
        return QuestResponse(**quest)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate quest: {str(e)}"
        )


@app.get("/quests/types", tags=["Quests"], summary="Get available quest types")
def get_quest_types():
    """Get information about different quest types"""
    return {
        "quest_types": {
            "combat": "Focused on fighting and defeating enemies",
            "stealth": "Requires sneaking, hiding, and subtle approaches",
            "arcane": "Involves magic, puzzles, and mystical challenges",
            "divine": "Centered around healing, blessings, and holy missions",
            "exploration": "Focused on discovering new places and mapping unknown areas",
            "social": "Involves interaction, diplomacy, and social challenges",
            "training": "Personal growth and skill development quests",
            "nature": "Connected to the natural world and its balance"
        }
    }


# NPC Relationship Endpoints
class NPCRelationshipResponse(BaseModel):
    npc_id: str
    name: str
    relationship_status: str
    attitude: str
    relationship_level: int
    trust: int
    liking: int
    fear: int
    last_interaction: Optional[str] = None


class RelationshipUpdateRequest(BaseModel):
    interaction_type: str
    success: bool
    context: Dict


@app.get("/sessions/{slug}/npcs/relationships", tags=["NPCs"], summary="Get all NPC relationships")
def get_npc_relationships(slug: str, settings: Settings = Depends(get_settings_dep)):
    """Get all NPC relationships for a session"""
    relationship_service = get_npc_relationship_service(slug, base_root=settings.storage_root)
    relationships = relationship_service.get_all_relationships()
    
    return [NPCRelationshipResponse(**rel.to_dict()) for rel in relationships]


@app.get("/sessions/{slug}/npcs/{npc_id}/relationship", tags=["NPCs"], summary="Get relationship with specific NPC")
def get_npc_relationship(slug: str, npc_id: str, settings: Settings = Depends(get_settings_dep)):
    """Get relationship details for a specific NPC"""
    relationship_service = get_npc_relationship_service(slug, base_root=settings.storage_root)
    relationship = relationship_service.get_relationship(npc_id)
    
    if not relationship:
        raise HTTPException(status_code=404, detail="NPC relationship not found")
    
    return NPCRelationshipResponse(**relationship.to_dict())


@app.post("/sessions/{slug}/npcs/{npc_id}/relationship", tags=["NPCs"], summary="Update relationship with NPC")
def update_npc_relationship(
    slug: str,
    npc_id: str,
    request: RelationshipUpdateRequest,
    settings: Settings = Depends(get_settings_dep),
):
    """Update relationship with an NPC based on interaction"""
    relationship_service = get_npc_relationship_service(slug, base_root=settings.storage_root)
    
    # Get NPC name from context or use ID
    npc_name = request.context.get('npc_name', npc_id)
    
    changes = relationship_service.update_relationship(
        npc_id,
        npc_name,
        request.interaction_type,
        request.success,
        request.context
    )
    
    return {
        "message": "Relationship updated successfully",
        "changes": changes
    }


@app.post("/sessions/{slug}/npcs/{npc_id}/dialogue", tags=["NPCs"], summary="Generate NPC dialogue")
async def generate_npc_dialogue(
    slug: str,
    npc_id: str,
    context: Dict,
    settings: Settings = Depends(get_settings_dep),
):
    """Generate dialogue for an NPC based on current relationship"""
    relationship_service = get_npc_relationship_service(slug, base_root=settings.storage_root)
    
    dialogue = await relationship_service.generate_relationship_dialogue(npc_id, context)
    
    if not dialogue:
        raise HTTPException(status_code=404, detail="NPC not found or no dialogue available")
    
    return {"dialogue": dialogue}


@app.get("/sessions/{slug}/npcs/relationship-summary", tags=["NPCs"], summary="Get relationship summary")
def get_relationship_summary(slug: str, settings: Settings = Depends(get_settings_dep)):
    """Get a summary of all NPC relationships"""
    relationship_service = get_npc_relationship_service(slug, base_root=settings.storage_root)
    relationships = relationship_service.get_all_relationships()
    
    summary = {
        "total_npcs": len(relationships),
        "relationships_by_status": {},
        "average_relationship_level": 0,
        "most_trusted_npc": None,
        "most_liked_npc": None
    }
    
    if relationships:
        status_counts = {}
        total_level = 0
        
        for rel in relationships:
            status = rel.get_relationship_status()
            status_counts[status] = status_counts.get(status, 0) + 1
            total_level += rel.relationship_level
        
        summary["relationships_by_status"] = status_counts
        summary["average_relationship_level"] = total_level / len(relationships)
        
        # Find most trusted and liked NPCs
        most_trusted = max(relationships, key=lambda r: r.trust)
        most_liked = max(relationships, key=lambda r: r.liking)
        
        summary["most_trusted_npc"] = {
            "npc_id": most_trusted.npc_id,
            "name": most_trusted.name,
            "trust": most_trusted.trust
        }
        
        summary["most_liked_npc"] = {
            "npc_id": most_liked.npc_id,
            "name": most_liked.name,
            "liking": most_liked.liking
        }
    
    return summary


# Mood/Tone System Endpoints
class MoodResponse(BaseModel):
    current_mood: str
    mood_intensity: float
    mood_history: List[Dict]


class MoodUpdateRequest(BaseModel):
    mood: str
    intensity: float = 1.0
    reason: str = "Unknown"


class MoodAdjustRequest(BaseModel):
    mood_change: str
    intensity_change: float = 0.0
    reason: str = "Unknown"


@app.get("/sessions/{slug}/mood", tags=["Mood"], summary="Get current mood state")
def get_current_mood(slug: str, settings: Settings = Depends(get_settings_dep)):
    """Get the current mood and tone settings"""
    mood_system = get_mood_system(slug, base_root=settings.storage_root)
    
    return MoodResponse(
        current_mood=mood_system.get_current_mood().value,
        mood_intensity=mood_system.get_mood_intensity(),
        mood_history=mood_system.get_mood_history()
    )


@app.post("/sessions/{slug}/mood", tags=["Mood"], summary="Set mood state")
def set_mood_state(slug: str, request: MoodUpdateRequest, settings: Settings = Depends(get_settings_dep)):
    """Set the current mood and intensity"""
    mood_system = get_mood_system(slug, base_root=settings.storage_root)
    
    try:
        mood = Mood(request.mood)
        result = mood_system.set_mood(mood, request.intensity, request.reason)
        
        return {
            "message": "Mood updated successfully",
            "changes": result
        }
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid mood: {request.mood}")


@app.patch("/sessions/{slug}/mood", tags=["Mood"], summary="Adjust mood state")
def adjust_mood_state(slug: str, request: MoodAdjustRequest, settings: Settings = Depends(get_settings_dep)):
    """Adjust the current mood"""
    mood_system = get_mood_system(slug, base_root=settings.storage_root)
    
    try:
        mood_change = Mood(request.mood_change)
        result = mood_system.adjust_mood(mood_change, request.intensity_change, request.reason)
        
        return {
            "message": "Mood adjusted successfully",
            "changes": result
        }
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid mood change: {request.mood_change}")


@app.get("/sessions/{slug}/mood/suggestions", tags=["Mood"], summary="Get mood suggestions")
def get_mood_suggestions(slug: str, settings: Settings = Depends(get_settings_dep)):
    """Get suggestions for the current mood"""
    mood_system = get_mood_system(slug, base_root=settings.storage_root)
    
    return mood_system.get_mood_suggestions()


@app.post("/sessions/{slug}/mood/narrate", tags=["Mood"], summary="Generate mood-enhanced narrative")
async def generate_mood_narrative(
    slug: str,
    prompt: str,
    context: Dict = {},
    settings: Settings = Depends(get_settings_dep),
):
    """Generate narrative enhanced with current mood"""
    mood_system = get_mood_system(slug, base_root=settings.storage_root)
    
    narrative = await mood_system.generate_mood_enhanced_narrative(prompt, context)
    
    return {
        "narrative": narrative,
        "mood": mood_system.get_current_mood().value,
        "intensity": mood_system.get_mood_intensity()
    }


@app.get("/mood/types", tags=["Mood"], summary="Get available mood types")
def get_mood_types():
    """Get information about different mood types"""
    return {
        "mood_types": {
            "neutral": "Standard, balanced narrative tone",
            "joyful": "Upbeat, happy, and positive tone",
            "excited": "Energetic, thrilling, and dynamic tone",
            "tense": "Anxious, suspenseful, and uncertain tone",
            "dangerous": "Perilous, threatening, and urgent tone",
            "mysterious": "Enigmatic, cryptic, and intriguing tone",
            "peaceful": "Calm, serene, and relaxing tone",
            "sad": "Melancholic, mournful, and somber tone",
            "horrific": "Terrifying, gruesome, and disturbing tone",
            "epic": "Heroic, grand, and monumental tone"
        }
    }


# Discovery Log Endpoints
class DiscoveryResponse(BaseModel):
    discovery_id: str
    name: str
    discovery_type: str
    description: str
    location: str
    discovered_at: str
    importance: int
    related_quest: Optional[str] = None
    rewards: List[str] = []


class DiscoveryCreateRequest(BaseModel):
    name: str
    discovery_type: str
    description: str
    location: str
    importance: int = 1
    related_quest: Optional[str] = None
    rewards: List[str] = []


@app.get("/sessions/{slug}/discoveries", tags=["Discoveries"], summary="Get all discoveries")
def get_all_discoveries(slug: str, settings: Settings = Depends(get_settings_dep)):
    """Get all discoveries for a session"""
    discovery_log = get_discovery_log(slug, settings.storage_root)
    discoveries = discovery_log.get_all_discoveries()
    
    return [DiscoveryResponse(**discovery.to_dict()) for discovery in discoveries]


@app.get("/sessions/{slug}/discoveries/recent", tags=["Discoveries"], summary="Get recent discoveries")
def get_recent_discoveries(slug: str, limit: int = Query(5, ge=1, le=20), settings: Settings = Depends(get_settings_dep)):
    """Get most recent discoveries"""
    discovery_log = get_discovery_log(slug, settings.storage_root)
    discoveries = discovery_log.get_recent_discoveries(limit)
    
    return [DiscoveryResponse(**discovery.to_dict()) for discovery in discoveries]


@app.get("/sessions/{slug}/discoveries/important", tags=["Discoveries"], summary="Get important discoveries")
def get_important_discoveries(slug: str, min_importance: int = Query(3, ge=1, le=5), settings: Settings = Depends(get_settings_dep)):
    """Get important discoveries"""
    discovery_log = get_discovery_log(slug, settings.storage_root)
    discoveries = discovery_log.get_important_discoveries(min_importance)
    
    return [DiscoveryResponse(**discovery.to_dict()) for discovery in discoveries]


@app.get("/sessions/{slug}/discoveries/types/{discovery_type}", tags=["Discoveries"], summary="Get discoveries by type")
def get_discoveries_by_type(slug: str, discovery_type: str, settings: Settings = Depends(get_settings_dep)):
    """Get discoveries filtered by type"""
    discovery_log = get_discovery_log(slug, settings.storage_root)
    discoveries = discovery_log.get_discoveries_by_type(discovery_type)
    
    return [DiscoveryResponse(**discovery.to_dict()) for discovery in discoveries]


@app.post("/sessions/{slug}/discoveries", tags=["Discoveries"], summary="Log a new discovery")
def log_discovery(slug: str, request: DiscoveryCreateRequest, settings: Settings = Depends(get_settings_dep)):
    """Log a new discovery"""
    discovery_log = get_discovery_log(slug, settings.storage_root)
    backend = _get_backend(settings)
    state = backend.state.load_state(settings, slug)
    
    discovery = discovery_log.create_discovery(
        name=request.name,
        discovery_type=request.discovery_type,
        description=request.description,
        location=request.location,
        importance=request.importance,
        related_quest=request.related_quest,
        rewards=request.rewards
    )
    backend.docs.record_last_discovery_turn(settings, slug, state.get("turn", 0))
    return DiscoveryResponse(**discovery.to_dict())


@app.get("/sessions/{slug}/discoveries/stats", tags=["Discoveries"], summary="Get discovery statistics")
def get_discovery_stats(slug: str, settings: Settings = Depends(get_settings_dep)):
    """Get statistics about discoveries"""
    discovery_log = get_discovery_log(slug, settings.storage_root)
    stats = discovery_log.get_discovery_stats()
    
    return stats


@app.post("/sessions/{slug}/discoveries/{discovery_id}/describe", tags=["Discoveries"], summary="Generate enhanced discovery description")
async def generate_discovery_description(slug: str, discovery_id: str, settings: Settings = Depends(get_settings_dep)):
    """Generate an enhanced description for a discovery using LLM"""
    discovery_log = get_discovery_log(slug, settings.storage_root)
    
    # Find the discovery
    discovery = None
    for disc in discovery_log.get_all_discoveries():
        if disc.discovery_id == discovery_id:
            discovery = disc
            break
    
    if not discovery:
        raise HTTPException(status_code=404, detail="Discovery not found")
    
    enhanced_description = await discovery_log.generate_discovery_description(discovery)
    
    return {
        "discovery_id": discovery_id,
        "original_description": discovery.description,
        "enhanced_description": enhanced_description
    }


@app.get("/discoveries/types", tags=["Discoveries"], summary="Get available discovery types")
def get_discovery_types():
    """Get information about different discovery types"""
    return {
        "discovery_types": {
            "location": "Discovery of new places and areas",
            "creature": "Discovery of new creatures or beings",
            "artifact": "Discovery of magical or historical artifacts",
            "lore": "Discovery of ancient knowledge or secrets",
            "resource": "Discovery of valuable resources or materials",
            "phenomenon": "Discovery of strange or magical phenomena",
            "civilization": "Discovery of lost civilizations or cultures",
            "achievement": "Significant player achievements and milestones"
        }
    }


# Auto-Save System Endpoints
class SaveResponse(BaseModel):
    save_id: str
    session_slug: str
    timestamp: str
    save_type: str
    saved_files: List[str]


class AutoSaveStatusResponse(BaseModel):
    running: bool
    save_interval: int
    last_save_time: float
    save_count: int
    next_save_in: float


class ManualSaveRequest(BaseModel):
    save_name: str = "manual"
    lock_owner: Optional[str] = None


def _require_save_lock(slug: str, settings: Settings, owner: Optional[str]):
    backend = _get_backend(settings)
    lock_info = backend.session.get_lock_info(settings, slug)
    if lock_info is None:
        raise HTTPException(status_code=HTTPStatus.CONFLICT, detail="Lock required to create or restore a save")
    if owner and lock_info.owner != owner:
        raise HTTPException(status_code=HTTPStatus.CONFLICT, detail="Lock owned by another actor")


@app.get("/sessions/{slug}/auto-save/status", tags=["AutoSave"], summary="Get auto-save status")
def get_auto_save_status(slug: str):
    """Get current auto-save status"""
    auto_save = get_auto_save_system(slug, base_root=settings.storage_root)
    status = auto_save.get_auto_save_status()
    
    return AutoSaveStatusResponse(**status)


@app.post("/sessions/{slug}/auto-save/start", tags=["AutoSave"], summary="Start auto-save")
def start_auto_save(slug: str):
    """Start the auto-save system"""
    auto_save = get_auto_save_system(slug, base_root=settings.storage_root)
    auto_save.start_auto_save()
    
    return {"message": "Auto-save started successfully"}


@app.post("/sessions/{slug}/auto-save/stop", tags=["AutoSave"], summary="Stop auto-save")
def stop_auto_save(slug: str):
    """Stop the auto-save system"""
    auto_save = get_auto_save_system(slug, base_root=settings.storage_root)
    auto_save.stop_auto_save()
    
    return {"message": "Auto-save stopped successfully"}


@app.post("/sessions/{slug}/auto-save/perform", tags=["AutoSave"], summary="Perform immediate auto-save")
def perform_auto_save(slug: str, lock_owner: Optional[str] = None, settings: Settings = Depends(get_settings_dep)):
    """Perform an immediate auto-save"""
    _require_save_lock(slug, settings, lock_owner)
    auto_save = get_auto_save_system(slug, base_root=settings.storage_root)
    success = auto_save.perform_auto_save()
    
    if success:
        return {"message": "Auto-save performed successfully"}
    else:
        raise HTTPException(status_code=500, detail="Auto-save failed")


@app.post("/sessions/{slug}/save", tags=["AutoSave"], summary="Perform manual save")
def manual_save(slug: str, request: ManualSaveRequest, settings: Settings = Depends(get_settings_dep)):
    """Perform a manual save"""
    _require_save_lock(slug, settings, request.lock_owner)
    auto_save = get_auto_save_system(slug, base_root=settings.storage_root)
    result = auto_save.manual_save(request.save_name)
    
    if result['success']:
        return {
            "message": "Manual save performed successfully",
            "save_id": result['save_id'],
            "timestamp": result['timestamp']
        }
    else:
        raise HTTPException(status_code=500, detail=f"Manual save failed: {result['error']}")


@app.get("/sessions/{slug}/saves", tags=["AutoSave"], summary="Get save history")
def get_save_history(slug: str, limit: int = Query(10, ge=1, le=50), settings: Settings = Depends(get_settings_dep)):
    """Get auto-save history"""
    auto_save = get_auto_save_system(slug, base_root=settings.storage_root)
    saves = auto_save.get_save_history(limit)
    
    return [SaveResponse(**save) for save in saves]


@app.get("/sessions/{slug}/saves/{save_id}", tags=["AutoSave"], summary="Get save information")
def get_save_info(slug: str, save_id: str):
    """Get information about a specific save"""
    auto_save = get_auto_save_system(slug, base_root=settings.storage_root)
    save_info = auto_save.get_save_info(save_id)
    
    if not save_info:
        raise HTTPException(status_code=404, detail="Save not found")
    
    return save_info


@app.post("/sessions/{slug}/saves/{save_id}/restore", tags=["AutoSave"], summary="Restore a save")
def restore_save(slug: str, save_id: str, lock_owner: Optional[str] = None, settings: Settings = Depends(get_settings_dep)):
    """Restore a save (placeholder - actual implementation would be more complex)"""
    _require_save_lock(slug, settings, lock_owner)
    auto_save = get_auto_save_system(slug, base_root=settings.storage_root)
    result = auto_save.restore_save(save_id)
    
    if result['success']:
        return {
            "message": "Save restoration initiated",
            "note": result['message']
        }
    else:
        raise HTTPException(status_code=500, detail=f"Restore failed: {result['error']}")


def _tail_file_lines(path: Path, cursor: int) -> Tuple[List[str], int]:
    if not path.exists():
        return [], cursor
    with path.open(encoding="utf-8") as handle:
        lines = handle.read().splitlines()
    if cursor < -1:
        cursor = -1
    start = cursor + 1
    if start >= len(lines):
        return [], len(lines) - 1
    return lines[start:], len(lines) - 1


def _sse_event(event: str, payload: Dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n"


@app.get("/events/{slug}", tags=["Observability"], summary="SSE endpoint for real-time session updates")
async def session_events(
    slug: str,
    request: Request,
    transcript_cursor: Optional[str] = Query(None, description="Last seen transcript cursor"),
    changelog_cursor: Optional[str] = Query(None, description="Last seen changelog cursor"),
    settings: Settings = Depends(get_settings_dep),
):
    """Server-sent events that stream new transcript and changelog lines deterministically."""
    backend = _get_backend(settings)

    def _normalize_cursor(token: Optional[str]) -> Optional[str]:
        if token in (None, "", "None"):
            return None
        try:
            return str(int(token))
        except Exception:
            return None

    transcript_cursor_token = _normalize_cursor(transcript_cursor)
    changelog_cursor_token = _normalize_cursor(changelog_cursor)

    async def event_stream():
        nonlocal transcript_cursor_token, changelog_cursor_token
        poll_interval = 1.0
        idle_cycles = 0
        max_idle_cycles = 60  # ~60s idle timeout

        def _load_updates():
            nonlocal transcript_cursor_token, changelog_cursor_token
            updates: Dict[str, Any] = {}

            transcript_entries, _next_t_cursor = backend.text_logs.load_transcript(
                settings, slug, cursor=transcript_cursor_token
            )
            changelog_entries, _next_c_cursor = backend.text_logs.load_changelog(
                settings, slug, cursor=changelog_cursor_token
            )

            if transcript_entries:
                transcript_cursor_token = transcript_entries[-1]["id"]
                updates["transcript"] = {
                    "cursor": transcript_cursor_token,
                    "lines": [entry["text"] for entry in transcript_entries],
                }
            if changelog_entries:
                changelog_cursor_token = changelog_entries[-1]["id"]
                updates["changelog"] = {
                    "cursor": changelog_cursor_token,
                    "lines": [entry["text"] for entry in changelog_entries],
                }
            return updates

        initial_updates = _load_updates()
        if initial_updates:
            yield _sse_event("update", initial_updates)

        while True:
            if await request.is_disconnected():
                break

            updates = _load_updates()
            if updates:
                idle_cycles = 0
                yield _sse_event("update", updates)
            else:
                idle_cycles += 1
                yield ": keep-alive\n\n"

            if idle_cycles >= max_idle_cycles:
                break

            await asyncio.sleep(poll_interval)

        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _build_main_app() -> FastAPI:
    """Wrap the API app with static file serving and the /api mount point."""
    main_app = FastAPI(
        title="Deterministic DM Service",
        description="API surface for deterministic, auditable gameplay data",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    main_app.mount("/api", api_app)

    dist_path = Path(__file__).resolve().parent.parent / "ui" / "dist"
    static_files = StaticFiles(directory=dist_path, html=True, check_dir=dist_path.exists())
    main_app.mount("/", static_files, name="ui")

    @main_app.get("/health")
    def root_health() -> dict:
        return {"status": "ok"}

    @main_app.exception_handler(StarletteHTTPException)
    async def spa_fallback(request: Request, exc: StarletteHTTPException):
        if (
            exc.status_code == HTTPStatus.NOT_FOUND
            and not request.url.path.startswith("/api")
            and "." not in request.url.path.split("/")[-1]
        ):
            index_path = dist_path / "index.html"
            if index_path.exists():
                return FileResponse(index_path)
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    main_app.state.api_app = api_app
    return main_app


# The app exported for ASGI servers mounts the API under /api and serves the built UI at /.
app = _build_main_app()





