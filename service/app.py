from typing import Optional, List, Dict
from datetime import datetime
from http import HTTPStatus
import json
import re

import uuid

from fastapi import Depends, FastAPI, Query, HTTPException
from pydantic import BaseModel

from .config import Settings, get_settings
from .llm import call_llm_api, get_effective_llm_config, persist_llm_config
from . import storage
from .models import (
    SessionSummary, PaginatedResponse,
    LockClaim, LockInfo, TurnResponse, PreviewRequest, PreviewResponse,
    FileDiff, EntropyPlan, CommitRequest, CommitResponse, SessionState,
    JobCreateRequest, JobResponse, JobProgress, JobCommitRequest,
    CommitSummary, DiffResponse, EntropyHistoryEntry
)
from .adventure_hooks import AdventureHooksService, get_adventure_hooks_service
from .auto_save import AutoSaveSystem, get_auto_save_system
from .discovery_log import DiscoveryLog, get_discovery_log, Discovery
from .mood_system import MoodSystem, get_mood_system, Mood
from .npc_relationships import NPCRelationshipService, get_npc_relationship_service
from quests.generator import generate_dynamic_quest

app = FastAPI(
    title="Deterministic DM Service",
    description="API surface for deterministic, auditable gameplay data",
)


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
    sessions_data = storage.list_sessions(settings)
    return [SessionSummary(**s) for s in sessions_data]


def _slugify_seed(seed: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", seed).strip("-").lower()
    return cleaned or "adventure"


@app.post("/sessions", status_code=201)
def create_session(request: NewSessionRequest, settings: Settings = Depends(get_settings_dep)) -> SessionCreateResponse:
    base = _slugify_seed(request.slug or request.hook_id or "adventure")
    candidate = base
    suffix = 1
    while True:
        try:
            created = storage.create_session(settings, candidate, request.template_slug)
            return SessionCreateResponse(slug=created)
        except HTTPException as exc:
            if exc.status_code == HTTPStatus.CONFLICT:
                candidate = f"{base}-{suffix}"
                suffix += 1
                continue
            raise


@app.get("/sessions/{slug}/state")
def session_state(slug: str, settings: Settings = Depends(get_settings_dep)) -> dict:
    return storage.load_state(settings, slug)


@app.get("/sessions/{slug}/transcript")
def session_transcript(
    slug: str,
    tail: Optional[int] = Query(None, ge=1, description="Number of entries to return"),
    cursor: Optional[str] = Query(None, description="Cursor for pagination"),
    settings: Settings = Depends(get_settings_dep),
) -> PaginatedResponse:
    items, next_cursor = storage.load_transcript(settings, slug, tail, cursor)
    return PaginatedResponse(items=items, cursor=next_cursor)


@app.get("/sessions/{slug}/changelog")
def session_changelog(
    slug: str,
    tail: Optional[int] = Query(None, ge=1, description="Number of entries to return"),
    cursor: Optional[str] = Query(None, description="Cursor for pagination"),
    settings: Settings = Depends(get_settings_dep),
) -> PaginatedResponse:
    items, next_cursor = storage.load_changelog(settings, slug, tail, cursor)
    return PaginatedResponse(items=items, cursor=next_cursor)


@app.get("/sessions/{slug}/quests")
def session_quests(slug: str, settings: Settings = Depends(get_settings_dep)) -> dict:
    return {"quests": storage.load_quests(settings, slug)}


@app.get("/sessions/{slug}/quests/{quest_id}")
def get_quest(slug: str, quest_id: str, settings: Settings = Depends(get_settings_dep)) -> dict:
    quests = storage.load_quests(settings, slug)
    if quest_id not in quests:
        raise HTTPException(status_code=404, detail="Quest not found")
    return quests[quest_id]


@app.post("/sessions/{slug}/quests")
def create_quest(slug: str, quest_data: Dict, dry_run: bool = Query(False), settings: Settings = Depends(get_settings_dep)) -> dict:
    errors = storage.validate_data(quest_data, "quest", settings)
    if errors:
        return {"errors": errors}
    if dry_run:
        return {"diff": f"Would add quest {quest_data.get('id', 'new')}", "warnings": []}
    quest_id = quest_data.get("id", str(uuid.uuid4()))
    storage.save_quest(settings, slug, quest_id, quest_data)
    return {"id": quest_id}


@app.put("/sessions/{slug}/quests/{quest_id}")
def update_quest(slug: str, quest_id: str, quest_data: Dict, dry_run: bool = Query(False), settings: Settings = Depends(get_settings_dep)) -> dict:
    errors = storage.validate_data(quest_data, "quest", settings)
    if errors:
        return {"errors": errors}
    quests = storage.load_quests(settings, slug)
    if quest_id not in quests:
        raise HTTPException(status_code=404, detail="Quest not found")
    if dry_run:
        return {"diff": f"Would update quest {quest_id}", "warnings": []}
    storage.save_quest(settings, slug, quest_id, quest_data)
    return {"message": "Updated"}


@app.delete("/sessions/{slug}/quests/{quest_id}")
def delete_quest(slug: str, quest_id: str, dry_run: bool = Query(False), settings: Settings = Depends(get_settings_dep)) -> dict:
    quests = storage.load_quests(settings, slug)
    if quest_id not in quests:
        raise HTTPException(status_code=404, detail="Quest not found")
    if dry_run:
        return {"diff": f"Would delete quest {quest_id}", "warnings": []}
    storage.delete_quest(settings, slug, quest_id)
    return {"message": "Deleted"}


@app.get("/sessions/{slug}/npc-memory")
def session_npc_memory(slug: str, settings: Settings = Depends(get_settings_dep)) -> dict:
    return {"npc_memory": storage.load_npc_memory(settings, slug)}


@app.get("/sessions/{slug}/npc-memory/{index}")
def get_npc(slug: str, index: int, settings: Settings = Depends(get_settings_dep)) -> dict:
    npcs = storage.load_npc_memory(settings, slug)
    if index < 0 or index >= len(npcs):
        raise HTTPException(status_code=404, detail="NPC not found")
    return npcs[index]


@app.post("/sessions/{slug}/npc-memory")
def create_npc(slug: str, npc_data: Dict, dry_run: bool = Query(False), settings: Settings = Depends(get_settings_dep)) -> dict:
    # Assume no schema
    if dry_run:
        return {"diff": f"Would add NPC {npc_data.get('name', 'new')}", "warnings": []}
    npcs = storage.load_npc_memory(settings, slug)
    npcs.append(npc_data)
    if not dry_run:
        storage.save_npc_memory(settings, slug, npcs)
    return {"index": len(npcs) - 1}


@app.put("/sessions/{slug}/npc-memory/{index}")
def update_npc(slug: str, index: int, npc_data: Dict, dry_run: bool = Query(False), settings: Settings = Depends(get_settings_dep)) -> dict:
    npcs = storage.load_npc_memory(settings, slug)
    if index < 0 or index >= len(npcs):
        raise HTTPException(status_code=404, detail="NPC not found")
    if dry_run:
        return {"diff": f"Would update NPC at {index}", "warnings": []}
    npcs[index] = npc_data
    storage.save_npc_memory(settings, slug, npcs)
    return {"message": "Updated"}


@app.delete("/sessions/{slug}/npc-memory/{index}")
def delete_npc(slug: str, index: int, dry_run: bool = Query(False), settings: Settings = Depends(get_settings_dep)) -> dict:
    npcs = storage.load_npc_memory(settings, slug)
    if index < 0 or index >= len(npcs):
        raise HTTPException(status_code=404, detail="NPC not found")
    if dry_run:
        return {"diff": f"Would delete NPC at {index}", "warnings": []}
    npcs.pop(index)
    storage.save_npc_memory(settings, slug, npcs)
    return {"message": "Deleted"}


@app.get("/sessions/{slug}/world/factions")
def session_factions(slug: str, settings: Settings = Depends(get_settings_dep)) -> dict:
    return storage.load_factions(settings, slug)


@app.get("/sessions/{slug}/world/factions/{faction_id}")
def get_faction(slug: str, faction_id: str, settings: Settings = Depends(get_settings_dep)) -> dict:
    factions = storage.load_factions(settings, slug)
    if faction_id not in factions:
        raise HTTPException(status_code=404, detail="Faction not found")
    return factions[faction_id]


@app.post("/sessions/{slug}/world/factions")
def create_faction(slug: str, faction_data: Dict, dry_run: bool = Query(False), settings: Settings = Depends(get_settings_dep)) -> dict:
    # Assume no schema for faction
    if dry_run:
        return {"diff": f"Would add faction {faction_data.get('id', 'new')}", "warnings": []}
    faction_id = faction_data.get("id", str(uuid.uuid4()))
    storage.save_faction(settings, slug, faction_id, faction_data)
    return {"id": faction_id}


@app.put("/sessions/{slug}/world/factions/{faction_id}")
def update_faction(slug: str, faction_id: str, faction_data: Dict, dry_run: bool = Query(False), settings: Settings = Depends(get_settings_dep)) -> dict:
    factions = storage.load_factions(settings, slug)
    if faction_id not in factions:
        raise HTTPException(status_code=404, detail="Faction not found")
    if dry_run:
        return {"diff": f"Would update faction {faction_id}", "warnings": []}
    storage.save_faction(settings, slug, faction_id, faction_data)
    return {"message": "Updated"}


@app.delete("/sessions/{slug}/world/factions/{faction_id}")
def delete_faction(slug: str, faction_id: str, dry_run: bool = Query(False), settings: Settings = Depends(get_settings_dep)) -> dict:
    factions = storage.load_factions(settings, slug)
    if faction_id not in factions:
        raise HTTPException(status_code=404, detail="Faction not found")
    if dry_run:
        return {"diff": f"Would delete faction {faction_id}", "warnings": []}
    storage.delete_faction(settings, slug, faction_id)
    return {"message": "Deleted"}


@app.get("/sessions/{slug}/world/timeline")
def session_timeline(slug: str, settings: Settings = Depends(get_settings_dep)) -> dict:
    return storage.load_timeline(settings, slug)


@app.post("/sessions/{slug}/world/timeline")
def create_timeline_event(slug: str, event_data: Dict, dry_run: bool = Query(False), settings: Settings = Depends(get_settings_dep)) -> dict:
    if dry_run:
        return {"diff": f"Would add timeline event {event_data.get('id', 'new')}", "warnings": []}
    event_id = event_data.get("id", str(uuid.uuid4()))
    storage.save_timeline_event(settings, slug, event_id, event_data)
    return {"id": event_id}


@app.put("/sessions/{slug}/world/timeline/{event_id}")
def update_timeline_event(slug: str, event_id: str, event_data: Dict, dry_run: bool = Query(False), settings: Settings = Depends(get_settings_dep)) -> dict:
    timeline = storage.load_timeline(settings, slug)
    if event_id not in timeline:
        raise HTTPException(status_code=404, detail="Event not found")
    if dry_run:
        return {"diff": f"Would update timeline event {event_id}", "warnings": []}
    storage.save_timeline_event(settings, slug, event_id, event_data)
    return {"message": "Updated"}


@app.delete("/sessions/{slug}/world/timeline/{event_id}")
def delete_timeline_event(slug: str, event_id: str, dry_run: bool = Query(False), settings: Settings = Depends(get_settings_dep)) -> dict:
    timeline = storage.load_timeline(settings, slug)
    if event_id not in timeline:
        raise HTTPException(status_code=404, detail="Event not found")
    if dry_run:
        return {"diff": f"Would delete timeline event {event_id}", "warnings": []}
    storage.delete_timeline_event(settings, slug, event_id)
    return {"message": "Deleted"}


@app.get("/sessions/{slug}/world/rumors")
def session_rumors(slug: str, settings: Settings = Depends(get_settings_dep)) -> dict:
    return storage.load_rumors(settings, slug)


@app.get("/sessions/{slug}/world/faction-clocks")
def session_faction_clocks(slug: str, settings: Settings = Depends(get_settings_dep)) -> dict:
    return storage.load_faction_clocks(settings, slug)


@app.get("/sessions/{slug}/turn")
def get_turn(slug: str, settings: Settings = Depends(get_settings_dep)) -> TurnResponse:
    prompt = storage.load_turn(settings, slug)
    state = storage.load_state(settings, slug)
    turn_number = state.get("turn", 0)
    lock_info = storage.get_lock_info(settings, slug)
    return TurnResponse(prompt=prompt, turn_number=turn_number, lock_status=lock_info)


@app.post("/sessions/{slug}/lock/claim")
def claim_lock(slug: str, claim: LockClaim, settings: Settings = Depends(get_settings_dep)):
    storage.claim_lock(settings, slug, claim.owner, claim.ttl)
    return {"message": "Lock claimed"}


@app.delete("/sessions/{slug}/lock")
def release_lock(slug: str, settings: Settings = Depends(get_settings_dep)):
    storage.release_lock(settings, slug)
    return {"message": "Lock released"}


@app.post("/sessions/{slug}/turn/preview")
def preview_turn(slug: str, request: PreviewRequest, settings: Settings = Depends(get_settings_dep)) -> PreviewResponse:
    preview_id, diffs, entropy_plan = storage.create_preview(settings, slug, request)
    file_diffs = [FileDiff(path=d["path"], changes=d["changes"]) for d in diffs]
    ep = EntropyPlan(indices=entropy_plan["indices"], usage=entropy_plan["usage"])
    return PreviewResponse(id=preview_id, diffs=file_diffs, entropy_plan=ep)


@app.post("/sessions/{slug}/turn/commit")
def commit_turn(slug: str, request: CommitRequest, settings: Settings = Depends(get_settings_dep)) -> CommitResponse:
    state, log_indices = storage.commit_preview(settings, slug, request.preview_id, request.lock_owner)
    session_state = SessionState(**state)
    return CommitResponse(state=session_state, log_indices=log_indices)


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
    return {"entropy": storage.load_entropy_preview(settings, limit)}


@app.get("/sessions/{slug}/history/commits", tags=["History"], summary="Get commit history for a session")
def session_commit_history(slug: str, settings: Settings = Depends(get_settings_dep)) -> List[CommitSummary]:
    commits_data = storage.load_commit_history(settings, slug)
    return [CommitSummary(**c) for c in commits_data]


@app.get("/sessions/{slug}/diff", tags=["History"], summary="Get diff between two commits")
def session_diff(
    slug: str,
    from_commit: str = Query(..., description="From commit ID"),
    to: str = Query(..., description="To commit ID"),
    settings: Settings = Depends(get_settings_dep),
) -> DiffResponse:
    diffs = storage.load_session_diff(settings, slug, from_commit, to)
    file_diffs = [FileDiff(path=d["path"], changes=d["changes"]) for d in diffs]
    return DiffResponse(files=file_diffs)


@app.get("/sessions/{slug}/entropy/history", tags=["Observability"], summary="Get entropy usage history for a session")
def session_entropy_history(
    slug: str,
    limit: int = Query(10, ge=1, le=100, description="Number of entries to return"),
    settings: Settings = Depends(get_settings_dep),
) -> List[EntropyHistoryEntry]:
    history_data = storage.load_entropy_history(settings, slug, limit)
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
    state = storage.load_state(settings, slug)
    character = storage.load_character(settings, slug)
    
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
def get_npc_relationships(slug: str):
    """Get all NPC relationships for a session"""
    relationship_service = get_npc_relationship_service(slug)
    relationships = relationship_service.get_all_relationships()
    
    return [NPCRelationshipResponse(**rel.to_dict()) for rel in relationships]


@app.get("/sessions/{slug}/npcs/{npc_id}/relationship", tags=["NPCs"], summary="Get relationship with specific NPC")
def get_npc_relationship(slug: str, npc_id: str):
    """Get relationship details for a specific NPC"""
    relationship_service = get_npc_relationship_service(slug)
    relationship = relationship_service.get_relationship(npc_id)
    
    if not relationship:
        raise HTTPException(status_code=404, detail="NPC relationship not found")
    
    return NPCRelationshipResponse(**relationship.to_dict())


@app.post("/sessions/{slug}/npcs/{npc_id}/relationship", tags=["NPCs"], summary="Update relationship with NPC")
def update_npc_relationship(slug: str, npc_id: str, request: RelationshipUpdateRequest):
    """Update relationship with an NPC based on interaction"""
    relationship_service = get_npc_relationship_service(slug)
    
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
async def generate_npc_dialogue(slug: str, npc_id: str, context: Dict):
    """Generate dialogue for an NPC based on current relationship"""
    relationship_service = get_npc_relationship_service(slug)
    
    dialogue = await relationship_service.generate_relationship_dialogue(npc_id, context)
    
    if not dialogue:
        raise HTTPException(status_code=404, detail="NPC not found or no dialogue available")
    
    return {"dialogue": dialogue}


@app.get("/sessions/{slug}/npcs/relationship-summary", tags=["NPCs"], summary="Get relationship summary")
def get_relationship_summary(slug: str):
    """Get a summary of all NPC relationships"""
    relationship_service = get_npc_relationship_service(slug)
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
def get_current_mood(slug: str):
    """Get the current mood and tone settings"""
    mood_system = get_mood_system(slug)
    
    return MoodResponse(
        current_mood=mood_system.get_current_mood().value,
        mood_intensity=mood_system.get_mood_intensity(),
        mood_history=mood_system.get_mood_history()
    )


@app.post("/sessions/{slug}/mood", tags=["Mood"], summary="Set mood state")
def set_mood_state(slug: str, request: MoodUpdateRequest):
    """Set the current mood and intensity"""
    mood_system = get_mood_system(slug)
    
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
def adjust_mood_state(slug: str, request: MoodAdjustRequest):
    """Adjust the current mood"""
    mood_system = get_mood_system(slug)
    
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
def get_mood_suggestions(slug: str):
    """Get suggestions for the current mood"""
    mood_system = get_mood_system(slug)
    
    return mood_system.get_mood_suggestions()


@app.post("/sessions/{slug}/mood/narrate", tags=["Mood"], summary="Generate mood-enhanced narrative")
async def generate_mood_narrative(slug: str, prompt: str, context: Dict = {}):
    """Generate narrative enhanced with current mood"""
    mood_system = get_mood_system(slug)
    
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
def get_all_discoveries(slug: str):
    """Get all discoveries for a session"""
    discovery_log = get_discovery_log(slug)
    discoveries = discovery_log.get_all_discoveries()
    
    return [DiscoveryResponse(**discovery.to_dict()) for discovery in discoveries]


@app.get("/sessions/{slug}/discoveries/recent", tags=["Discoveries"], summary="Get recent discoveries")
def get_recent_discoveries(slug: str, limit: int = Query(5, ge=1, le=20)):
    """Get most recent discoveries"""
    discovery_log = get_discovery_log(slug)
    discoveries = discovery_log.get_recent_discoveries(limit)
    
    return [DiscoveryResponse(**discovery.to_dict()) for discovery in discoveries]


@app.get("/sessions/{slug}/discoveries/important", tags=["Discoveries"], summary="Get important discoveries")
def get_important_discoveries(slug: str, min_importance: int = Query(3, ge=1, le=5)):
    """Get important discoveries"""
    discovery_log = get_discovery_log(slug)
    discoveries = discovery_log.get_important_discoveries(min_importance)
    
    return [DiscoveryResponse(**discovery.to_dict()) for discovery in discoveries]


@app.get("/sessions/{slug}/discoveries/types/{discovery_type}", tags=["Discoveries"], summary="Get discoveries by type")
def get_discoveries_by_type(slug: str, discovery_type: str):
    """Get discoveries filtered by type"""
    discovery_log = get_discovery_log(slug)
    discoveries = discovery_log.get_discoveries_by_type(discovery_type)
    
    return [DiscoveryResponse(**discovery.to_dict()) for discovery in discoveries]


@app.post("/sessions/{slug}/discoveries", tags=["Discoveries"], summary="Log a new discovery")
def log_discovery(slug: str, request: DiscoveryCreateRequest):
    """Log a new discovery"""
    discovery_log = get_discovery_log(slug)
    
    discovery = discovery_log.create_discovery(
        name=request.name,
        discovery_type=request.discovery_type,
        description=request.description,
        location=request.location,
        importance=request.importance,
        related_quest=request.related_quest,
        rewards=request.rewards
    )
    
    return DiscoveryResponse(**discovery.to_dict())


@app.get("/sessions/{slug}/discoveries/stats", tags=["Discoveries"], summary="Get discovery statistics")
def get_discovery_stats(slug: str):
    """Get statistics about discoveries"""
    discovery_log = get_discovery_log(slug)
    stats = discovery_log.get_discovery_stats()
    
    return stats


@app.post("/sessions/{slug}/discoveries/{discovery_id}/describe", tags=["Discoveries"], summary="Generate enhanced discovery description")
async def generate_discovery_description(slug: str, discovery_id: str):
    """Generate an enhanced description for a discovery using LLM"""
    discovery_log = get_discovery_log(slug)
    
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
    lock_info = storage.get_lock_info(settings, slug)
    if lock_info is None:
        raise HTTPException(status_code=HTTPStatus.CONFLICT, detail="Lock required to create or restore a save")
    if owner and lock_info.owner != owner:
        raise HTTPException(status_code=HTTPStatus.CONFLICT, detail="Lock owned by another actor")


@app.get("/sessions/{slug}/auto-save/status", tags=["AutoSave"], summary="Get auto-save status")
def get_auto_save_status(slug: str):
    """Get current auto-save status"""
    auto_save = get_auto_save_system(slug)
    status = auto_save.get_auto_save_status()
    
    return AutoSaveStatusResponse(**status)


@app.post("/sessions/{slug}/auto-save/start", tags=["AutoSave"], summary="Start auto-save")
def start_auto_save(slug: str):
    """Start the auto-save system"""
    auto_save = get_auto_save_system(slug)
    auto_save.start_auto_save()
    
    return {"message": "Auto-save started successfully"}


@app.post("/sessions/{slug}/auto-save/stop", tags=["AutoSave"], summary="Stop auto-save")
def stop_auto_save(slug: str):
    """Stop the auto-save system"""
    auto_save = get_auto_save_system(slug)
    auto_save.stop_auto_save()
    
    return {"message": "Auto-save stopped successfully"}


@app.post("/sessions/{slug}/auto-save/perform", tags=["AutoSave"], summary="Perform immediate auto-save")
def perform_auto_save(slug: str, lock_owner: Optional[str] = None, settings: Settings = Depends(get_settings_dep)):
    """Perform an immediate auto-save"""
    _require_save_lock(slug, settings, lock_owner)
    auto_save = get_auto_save_system(slug)
    success = auto_save.perform_auto_save()
    
    if success:
        return {"message": "Auto-save performed successfully"}
    else:
        raise HTTPException(status_code=500, detail="Auto-save failed")


@app.post("/sessions/{slug}/save", tags=["AutoSave"], summary="Perform manual save")
def manual_save(slug: str, request: ManualSaveRequest, settings: Settings = Depends(get_settings_dep)):
    """Perform a manual save"""
    _require_save_lock(slug, settings, request.lock_owner)
    auto_save = get_auto_save_system(slug)
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
def get_save_history(slug: str, limit: int = Query(10, ge=1, le=50)):
    """Get auto-save history"""
    auto_save = get_auto_save_system(slug)
    saves = auto_save.get_save_history(limit)
    
    return [SaveResponse(**save) for save in saves]


@app.get("/sessions/{slug}/saves/{save_id}", tags=["AutoSave"], summary="Get save information")
def get_save_info(slug: str, save_id: str):
    """Get information about a specific save"""
    auto_save = get_auto_save_system(slug)
    save_info = auto_save.get_save_info(save_id)
    
    if not save_info:
        raise HTTPException(status_code=404, detail="Save not found")
    
    return save_info


@app.post("/sessions/{slug}/saves/{save_id}/restore", tags=["AutoSave"], summary="Restore a save")
def restore_save(slug: str, save_id: str, lock_owner: Optional[str] = None, settings: Settings = Depends(get_settings_dep)):
    """Restore a save (placeholder - actual implementation would be more complex)"""
    _require_save_lock(slug, settings, lock_owner)
    auto_save = get_auto_save_system(slug)
    result = auto_save.restore_save(save_id)
    
    if result['success']:
        return {
            "message": "Save restoration initiated",
            "note": result['message']
        }
    else:
        raise HTTPException(status_code=500, detail=f"Restore failed: {result['error']}")


@app.get("/events/{slug}", tags=["Observability"], summary="SSE endpoint for real-time session updates")
def session_events(slug: str, settings: Settings = Depends(get_settings_dep)):
    """SSE endpoint is currently disabled pending deterministic event stream design."""
    raise HTTPException(status_code=HTTPStatus.NOT_IMPLEMENTED, detail="Server-sent events are not available yet.")
