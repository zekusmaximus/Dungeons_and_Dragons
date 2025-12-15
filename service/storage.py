import json
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import HTTPException, status

from .config import Settings


def _ensure_session(settings: Settings, slug: str) -> Path:
    session_path = settings.sessions_path / slug
    if not session_path.exists() or not session_path.is_dir():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown session '{slug}'",
        )
    return session_path


def list_sessions(settings: Settings) -> List[str]:
    if not settings.sessions_path.exists():
        return []
    return sorted(
        [p.name for p in settings.sessions_path.iterdir() if p.is_dir() and not p.name.startswith(".")]
    )


def load_state(settings: Settings, slug: str) -> Dict:
    session_path = _ensure_session(settings, slug)
    state_path = session_path / "state.json"
    if not state_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"State not found for '{slug}'"
        )
    with state_path.open() as handle:
        return json.load(handle)


def tail_text_lines(path: Path, count: int) -> List[str]:
    if not path.exists():
        return []
    with path.open() as handle:
        lines = [line.rstrip() for line in handle.readlines() if line.strip()]
    return lines[-count:]


def load_transcript(settings: Settings, slug: str, tail: Optional[int] = None) -> List[str]:
    session_path = _ensure_session(settings, slug)
    transcript_path = session_path / "transcript.md"
    count = tail if tail is not None else settings.transcript_tail
    return tail_text_lines(transcript_path, count)


def load_changelog(settings: Settings, slug: str, tail: Optional[int] = None) -> List[str]:
    session_path = _ensure_session(settings, slug)
    changelog_path = session_path / "changelog.md"
    count = tail if tail is not None else settings.changelog_tail
    return tail_text_lines(changelog_path, count)


def load_quests(settings: Settings, slug: str) -> Dict:
    state = load_state(settings, slug)
    return state.get("quests", {})


def load_npc_memory(settings: Settings, slug: str) -> List[Dict]:
    session_path = _ensure_session(settings, slug)
    path = session_path / "npc_memory.json"
    if not path.exists():
        return []
    with path.open() as handle:
        data = json.load(handle)
    return data.get("npcs", [])


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
        return json.load(handle)


def load_factions(settings: Settings, slug: str) -> Dict:
    world = resolve_world(settings, slug)
    return load_world_file(world, "factions.json")


def load_timeline(settings: Settings, slug: str) -> Dict:
    world = resolve_world(settings, slug)
    return load_world_file(world, "timeline.json")


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
