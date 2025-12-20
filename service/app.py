from typing import Optional, List, Dict
from datetime import datetime
import json
import httpx

import uuid

from fastapi import Depends, FastAPI, Query, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .config import Settings, get_settings
from . import storage
from .models import (
    SessionSummary, PaginatedResponse,
    LockClaim, LockInfo, TurnResponse, PreviewRequest, PreviewResponse,
    FileDiff, EntropyPlan, CommitRequest, CommitResponse, SessionState,
    JobCreateRequest, JobResponse, JobProgress, JobCommitRequest,
    CommitSummary, DiffResponse, EntropyHistoryEntry, EventType, ServerSentEvent
)

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
    tokens_used: int
    model: str


class LLMConfigRequest(BaseModel):
    api_key: str
    base_url: Optional[str] = None
    model: Optional[str] = None


class LLMConfigResponse(BaseModel):
    api_key_set: bool
    current_model: str
    base_url: str


async def call_llm_api(
    settings: Settings,
    prompt: str,
    context: Optional[Dict] = None,
    max_tokens: Optional[int] = None
) -> str:
    """Call LLM API for narrative generation"""
    if not settings.has_llm_config:
        raise HTTPException(
            status_code=400,
            detail="LLM API key not configured. Please set DM_SERVICE_LLM_API_KEY or use /llm/config endpoint."
        )
    
    max_tokens = max_tokens or settings.llm_max_tokens
    
    # Build the prompt with context
    full_prompt = prompt
    if context:
        context_str = json.dumps(context)
        full_prompt = f"Context: {context_str}\n\nPrompt: {prompt}"
    
    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": settings.llm_model,
        "messages": [{"role": "user", "content": full_prompt}],
        "temperature": settings.llm_temperature,
        "max_tokens": max_tokens
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{settings.llm_base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=30.0
            )
            response.raise_for_status()
            result = response.json()
            return result["choices"][0]["message"]["content"].strip()
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=e.response.status_code,
                detail=f"LLM API error: {e.response.text}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"LLM API call failed: {str(e)}"
            )


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
    preview_id, diffs, entropy_plan = storage.create_preview(settings, slug, request.response)
    file_diffs = [FileDiff(path=d["path"], changes=d["changes"]) for d in diffs]
    ep = EntropyPlan(indices=entropy_plan["indices"], usage=entropy_plan["usage"])
    return PreviewResponse(id=preview_id, diffs=file_diffs, entropy_plan=ep)


@app.post("/sessions/{slug}/turn/commit")
def commit_turn(slug: str, request: CommitRequest, settings: Settings = Depends(get_settings_dep)) -> CommitResponse:
    state, log_indices = storage.commit_preview(settings, slug, request.preview_id)
    session_state = SessionState(**state)
    return CommitResponse(state=session_state, log_indices=log_indices)


@app.post("/jobs/explore")
def create_explore_job(request: JobCreateRequest, settings: Settings = Depends(get_settings_dep)) -> JobResponse:
    if request.type.value != "explore":
        raise HTTPException(status_code=400, detail="Invalid job type")
    job_id = storage.create_job(settings, request)
    job = storage.get_job(settings, job_id)
    return JobResponse(**job)


@app.post("/jobs/resolve-encounter")
def create_resolve_encounter_job(request: JobCreateRequest, settings: Settings = Depends(get_settings_dep)) -> JobResponse:
    if request.type.value != "resolve-encounter":
        raise HTTPException(status_code=400, detail="Invalid job type")
    job_id = storage.create_job(settings, request)
    job = storage.get_job(settings, job_id)
    return JobResponse(**job)


@app.post("/jobs/loot")
def create_loot_job(request: JobCreateRequest, settings: Settings = Depends(get_settings_dep)) -> JobResponse:
    if request.type.value != "loot":
        raise HTTPException(status_code=400, detail="Invalid job type")
    job_id = storage.create_job(settings, request)
    job = storage.get_job(settings, job_id)
    return JobResponse(**job)


@app.post("/jobs/downtime")
def create_downtime_job(request: JobCreateRequest, settings: Settings = Depends(get_settings_dep)) -> JobResponse:
    if request.type.value != "downtime":
        raise HTTPException(status_code=400, detail="Invalid job type")
    job_id = storage.create_job(settings, request)
    job = storage.get_job(settings, job_id)
    return JobResponse(**job)


@app.post("/jobs/quest/init")
def create_quest_init_job(request: JobCreateRequest, settings: Settings = Depends(get_settings_dep)) -> JobResponse:
    if request.type.value != "quest-init":
        raise HTTPException(status_code=400, detail="Invalid job type")
    job_id = storage.create_job(settings, request)
    job = storage.get_job(settings, job_id)
    return JobResponse(**job)


@app.get("/jobs/{job_id}")
def get_job_progress(job_id: str, settings: Settings = Depends(get_settings_dep)) -> JobProgress:
    progress = storage.get_job_progress(settings, job_id)
    return JobProgress(**progress)


@app.post("/jobs/{job_id}/commit")
def commit_job(job_id: str, request: JobCommitRequest, settings: Settings = Depends(get_settings_dep)):
    storage.commit_job(settings, job_id)
    return {"message": "Job committed"}


@app.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str, settings: Settings = Depends(get_settings_dep)):
    storage.cancel_job(settings, job_id)
    return {"message": "Job cancelled"}


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
    return LLMConfigResponse(
        api_key_set=settings.has_llm_config,
        current_model=settings.llm_model,
        base_url=settings.llm_base_url
    )


@app.post("/llm/config", tags=["LLM"], summary="Configure LLM API settings")
def configure_llm(
    config: LLMConfigRequest,
    settings: Settings = Depends(get_settings_dep)
) -> LLMConfigResponse:
    # In a real implementation, you would persist this configuration
    # For now, we'll just return the current config
    return LLMConfigResponse(
        api_key_set=settings.has_llm_config,
        current_model=config.model or settings.llm_model,
        base_url=config.base_url or settings.llm_base_url
    )


@app.post("/llm/narrate", tags=["LLM"], summary="Generate narrative text using LLM")
async def generate_narrative(
    request: LLMNarrativeRequest,
    settings: Settings = Depends(get_settings_dep)
) -> LLMNarrativeResponse:
    narrative = await call_llm_api(
        settings,
        request.prompt,
        request.context,
        request.max_tokens
    )
    return LLMNarrativeResponse(
        narrative=narrative,
        tokens_used=len(narrative.split()),  # Simple word count as proxy
        model=settings.llm_model
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
    
    narrative = await call_llm_api(
        settings,
        request.prompt,
        context,
        request.max_tokens
    )
    
    return LLMNarrativeResponse(
        narrative=narrative,
        tokens_used=len(narrative.split()),
        model=settings.llm_model
    )


@app.get("/events/{slug}", tags=["Observability"], summary="SSE endpoint for real-time session updates")
def session_events(slug: str, settings: Settings = Depends(get_settings_dep)):
    """SSE endpoint for real-time updates."""
    def event_generator():
        import asyncio
        # Placeholder: yield mock events every few seconds
        count = 0
        while True:
            if count % 10 == 0:
                event = ServerSentEvent(
                    type=EventType.TRANSCRIPT_UPDATE,
                    data={"tail": ["New transcript line"]},
                    timestamp=datetime.utcnow()
                )
                yield f"data: {event.json()}\n\n"
            elif count % 20 == 0:
                event = ServerSentEvent(
                    type=EventType.LOCK_CLAIMED,
                    data={"owner": "user"},
                    timestamp=datetime.utcnow()
                )
                yield f"data: {event.json()}\n\n"
            count += 1
            asyncio.sleep(1)  # Wait 1 second
    return StreamingResponse(event_generator(), media_type="text/event-stream")
