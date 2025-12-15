from typing import Optional

from fastapi import Depends, FastAPI, Query

from .config import Settings, get_settings
from . import storage

app = FastAPI(
    title="Deterministic DM Service",
    description="API surface for deterministic, auditable gameplay data",
)


def get_settings_dep() -> Settings:
    return get_settings()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/sessions")
def list_sessions(settings: Settings = Depends(get_settings_dep)) -> dict:
    return {"sessions": storage.list_sessions(settings)}


@app.get("/sessions/{slug}/state")
def session_state(slug: str, settings: Settings = Depends(get_settings_dep)) -> dict:
    return storage.load_state(settings, slug)


@app.get("/sessions/{slug}/transcript")
def session_transcript(
    slug: str,
    tail: Optional[int] = Query(None, ge=1, description="Number of lines to return from the end"),
    settings: Settings = Depends(get_settings_dep),
) -> dict:
    return {"transcript": storage.load_transcript(settings, slug, tail)}


@app.get("/sessions/{slug}/changelog")
def session_changelog(
    slug: str,
    tail: Optional[int] = Query(None, ge=1, description="Number of entries to return from the end"),
    settings: Settings = Depends(get_settings_dep),
) -> dict:
    return {"changelog": storage.load_changelog(settings, slug, tail)}


@app.get("/sessions/{slug}/quests")
def session_quests(slug: str, settings: Settings = Depends(get_settings_dep)) -> dict:
    return {"quests": storage.load_quests(settings, slug)}


@app.get("/sessions/{slug}/npc-memory")
def session_npc_memory(slug: str, settings: Settings = Depends(get_settings_dep)) -> dict:
    return {"npc_memory": storage.load_npc_memory(settings, slug)}


@app.get("/sessions/{slug}/world/factions")
def session_factions(slug: str, settings: Settings = Depends(get_settings_dep)) -> dict:
    return storage.load_factions(settings, slug)


@app.get("/sessions/{slug}/world/timeline")
def session_timeline(slug: str, settings: Settings = Depends(get_settings_dep)) -> dict:
    return storage.load_timeline(settings, slug)


@app.get("/entropy")
def entropy_preview(
    limit: int = Query(5, ge=1, le=50, description="Number of entropy records to preview"),
    settings: Settings = Depends(get_settings_dep),
) -> dict:
    return {"entropy": storage.load_entropy_preview(settings, limit)}
