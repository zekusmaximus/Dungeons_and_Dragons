import json
import uuid
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import jsonschema

from fastapi import HTTPException, status

from .config import Settings
from .models import LockInfo, JobCreateRequest, JobStatus


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


def load_state(settings: Settings, slug: str) -> Dict:
    session_path = _ensure_session(settings, slug)
    state_path = session_path / "state.json"
    if not state_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"State not found for '{slug}'"
        )
    with state_path.open() as handle:
        return json.load(handle)


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
        return json.load(handle)


def load_factions(settings: Settings, slug: str) -> Dict:
    world = resolve_world(settings, slug)
    return load_world_file(world, "factions.json")


def save_faction(settings: Settings, slug: str, faction_id: str, faction_data: Dict):
    world = resolve_world(settings, slug)
    factions = load_world_file(world, "factions.json")
    factions[faction_id] = faction_data
    factions_path = world / "factions.json"
    with factions_path.open('w') as handle:
        json.dump(factions, handle, indent=2)


def delete_faction(settings: Settings, slug: str, faction_id: str):
    world = resolve_world(settings, slug)
    factions = load_world_file(world, "factions.json")
    if faction_id in factions:
        del factions[faction_id]
        factions_path = world / "factions.json"
        with factions_path.open('w') as handle:
            json.dump(factions, handle, indent=2)


def load_timeline(settings: Settings, slug: str) -> Dict:
    world = resolve_world(settings, slug)
    return load_world_file(world, "timeline.json")


def save_timeline_event(settings: Settings, slug: str, event_id: str, event_data: Dict):
    world = resolve_world(settings, slug)
    timeline = load_world_file(world, "timeline.json")
    timeline[event_id] = event_data
    timeline_path = world / "timeline.json"
    with timeline_path.open('w') as handle:
        json.dump(timeline, handle, indent=2)


def delete_timeline_event(settings: Settings, slug: str, event_id: str):
    world = resolve_world(settings, slug)
    timeline = load_world_file(world, "timeline.json")
    if event_id in timeline:
        del timeline[event_id]
        timeline_path = world / "timeline.json"
        with timeline_path.open('w') as handle:
            json.dump(timeline, handle, indent=2)


def load_rumors(settings: Settings, slug: str) -> Dict:
    world = resolve_world(settings, slug)
    return load_world_file(world, "rumors.json")


def save_rumor(settings: Settings, slug: str, rumor_id: str, rumor_data: Dict):
    world = resolve_world(settings, slug)
    rumors = load_world_file(world, "rumors.json")
    rumors[rumor_id] = rumor_data
    rumors_path = world / "rumors.json"
    with rumors_path.open('w') as handle:
        json.dump(rumors, handle, indent=2)


def delete_rumor(settings: Settings, slug: str, rumor_id: str):
    world = resolve_world(settings, slug)
    rumors = load_world_file(world, "rumors.json")
    if rumor_id in rumors:
        del rumors[rumor_id]
        rumors_path = world / "rumors.json"
        with rumors_path.open('w') as handle:
            json.dump(rumors, handle, indent=2)


def load_faction_clocks(settings: Settings, slug: str) -> Dict:
    world = resolve_world(settings, slug)
    return load_world_file(world, "faction_clocks.json")


def save_faction_clock(settings: Settings, slug: str, clock_id: str, clock_data: Dict):
    world = resolve_world(settings, slug)
    clocks = load_world_file(world, "faction_clocks.json")
    clocks[clock_id] = clock_data
    clocks_path = world / "faction_clocks.json"
    with clocks_path.open('w') as handle:
        json.dump(clocks, handle, indent=2)


def delete_faction_clock(settings: Settings, slug: str, clock_id: str):
    world = resolve_world(settings, slug)
    clocks = load_world_file(world, "faction_clocks.json")
    if clock_id in clocks:
        del clocks[clock_id]
        clocks_path = world / "faction_clocks.json"
        with clocks_path.open('w') as handle:
            json.dump(clocks, handle, indent=2)


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
    with turn_path.open() as handle:
        return handle.read()


def get_lock_info(settings: Settings, slug: str) -> Optional[LockInfo]:
    session_path = _ensure_session(settings, slug)
    lock_path = session_path / "LOCK"
    if not lock_path.exists():
        return None
    with lock_path.open() as handle:
        data = json.load(handle)
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
        "claimed_at": datetime.utcnow().isoformat()
    }
    with lock_path.open('w') as handle:
        json.dump(data, handle)


def release_lock(settings: Settings, slug: str):
    session_path = _ensure_session(settings, slug)
    lock_path = session_path / "LOCK"
    if lock_path.exists():
        lock_path.unlink()


# Placeholder for preview and commit logic
# In a real implementation, this would process the response and compute changes
def create_preview(settings: Settings, slug: str, response: str) -> Tuple[str, List[Dict], Dict]:
    # Generate a preview id
    preview_id = f"preview_{datetime.utcnow().timestamp()}"
    # Placeholder diffs: assume response is added to transcript
    diffs = [{"path": "transcript.md", "changes": f"Add: {response[:50]}..."}]
    # Placeholder entropy plan
    entropy_plan = {"indices": [], "usage": "No dice rolls in this turn"}
    return preview_id, diffs, entropy_plan


def commit_preview(settings: Settings, slug: str, preview_id: str) -> Tuple[Dict, Dict]:
    # Placeholder: update state turn number, add to transcript and changelog
    state = load_state(settings, slug)
    state["turn"] += 1
    # Save state
    session_path = _ensure_session(settings, slug)
    state_path = session_path / "state.json"
    with state_path.open('w') as handle:
        json.dump(state, handle)
    # Append to transcript (placeholder)
    transcript_path = session_path / "transcript.md"
    with transcript_path.open('a') as handle:
        handle.write(f"\nTurn {state['turn']}: Committed preview {preview_id}\n")
    # Append to changelog
    changelog_path = session_path / "changelog.md"
    with changelog_path.open('a') as handle:
        handle.write(f"\nCommitted turn {state['turn']}\n")
    # Log indices
    log_indices = {"transcript": 0, "changelog": 0}  # placeholder
    return state, log_indices


# Job management
_jobs: Dict[str, Dict] = {}  # In-memory job store, in production use persistent storage
_executor = ThreadPoolExecutor(max_workers=4)


def create_job(settings: Settings, request: JobCreateRequest) -> str:
    job_id = str(uuid.uuid4())
    job = {
        "id": job_id,
        "type": request.type.value,
        "status": JobStatus.PENDING.value,
        "created_at": datetime.utcnow().isoformat(),
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
    # Start job asynchronously
    _executor.submit(run_job, settings, job_id, request)
    return job_id


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
    if job["status"] != JobStatus.COMPLETED.value:
        raise HTTPException(status_code=400, detail="Job not completed")
    # In dry-run, we didn't modify original files, so apply diffs here
    # Placeholder: assume diffs are applied
    job["status"] = JobStatus.COMPLETED.value  # Already completed


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
