from __future__ import annotations

from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from enum import Enum


class Abilities(BaseModel):
    str_: int = Field(alias="str")
    dex: int
    con: int
    int_: int = Field(alias="int")
    wis: int
    cha: int


class Proficiencies(BaseModel):
    skills: List[str]
    tools: List[str]
    languages: List[str]


class Character(BaseModel):
    slug: str
    name: str
    race: str
    class_: str = Field(alias="class")
    background: str
    level: int = Field(ge=1)
    hp: int = Field(ge=0)
    ac: int = Field(ge=1)
    abilities: Abilities
    skills: Dict[str, int]
    inventory: List[str]
    starting_equipment: List[str]
    features: List[str]
    proficiencies: Proficiencies
    notes: str
    creation_source: str  # "dm" or "tool"

    model_config = ConfigDict(populate_by_name=True)


class Hex(BaseModel):
    q: int
    r: int


class SessionState(BaseModel):
    character: str
    turn: int = Field(ge=0)
    scene_id: str
    location: str
    hp: int = Field(ge=0)
    conditions: List[str]
    flags: Dict[str, Any]
    log_index: int = Field(ge=0)
    level: int = Field(ge=1)
    xp: int = Field(ge=0)
    inventory: List[str]
    conditions_detail: Optional[List[str]] = None
    world: Optional[str] = None
    hex: Optional[Hex] = None
    time: Optional[datetime] = None
    weather: Optional[str] = None
    travel_pace: Optional[str] = None
    exhaustion: Optional[int] = Field(None, ge=0)
    quests: Optional[Dict[str, Any]] = None
    gp: Optional[int] = Field(None, ge=0)


# Add more models as needed from other schemas
# For now, these are key ones for the existing endpoints


class SessionSummary(BaseModel):
    slug: str
    world: str
    has_lock: bool
    updated_at: datetime


class TranscriptEntry(BaseModel):
    id: str
    text: str


class ChangelogEntry(BaseModel):
    id: str
    text: str


class PaginatedResponse(BaseModel):
    items: List[Dict[str, Any]]
    cursor: Optional[str] = None


class ErrorEnvelope(BaseModel):
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None


class LockClaim(BaseModel):
    owner: str
    ttl: int = Field(ge=1, description="Time to live in seconds")


class LockInfo(BaseModel):
    owner: str
    ttl: int
    claimed_at: datetime


class TurnResponse(BaseModel):
    prompt: str
    turn_number: int
    lock_status: Optional[LockInfo] = None


class PreviewRequest(BaseModel):
    response: str = Field(description="Proposed turn response text", default="")
    state_patch: Dict[str, Any] = Field(default_factory=dict, description="Partial update to session state")
    transcript_entry: Optional[str] = Field(
        default=None, description="Optional transcript line to append on commit"
    )
    changelog_entry: Optional[str] = Field(
        default=None, description="Optional changelog entry to append on commit"
    )
    dice_expressions: List[str] = Field(
        default_factory=list, description="Dice expressions that will consume entropy on commit"
    )
    lock_owner: Optional[str] = Field(
        default=None, description="Owner that must hold the session lock for this preview"
    )


class FileDiff(BaseModel):
    path: str
    changes: str  # diff summary


class EntropyPlan(BaseModel):
    indices: List[int]
    usage: str  # description


class PreviewResponse(BaseModel):
    id: str
    diffs: List[FileDiff]
    entropy_plan: EntropyPlan


class CommitRequest(BaseModel):
    preview_id: str
    lock_owner: Optional[str] = Field(default=None, description="Owner expected to hold the session lock")


class CommitResponse(BaseModel):
    state: SessionState
    log_indices: Dict[str, int]


class JobType(str, Enum):
    EXPLORE = "explore"
    RESOLVE_ENCOUNTER = "resolve-encounter"
    LOOT = "loot"
    DOWNTIME = "downtime"
    QUEST_INIT = "quest-init"


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobCreateRequest(BaseModel):
    type: JobType
    params: Dict[str, Any] = Field(default_factory=dict)


class JobProgress(BaseModel):
    status: JobStatus
    logs: List[str] = Field(default_factory=list)
    entropy_usage: List[int] = Field(default_factory=list)
    diff_preview: List[FileDiff] = Field(default_factory=list)
    error: Optional[str] = None


class JobResponse(BaseModel):
    id: str
    type: JobType
    status: JobStatus
    created_at: datetime
    params: Dict[str, Any]


class JobCommitRequest(BaseModel):
    pass  # No body needed, just POST to commit


class CommitSummary(BaseModel):
    id: str
    tags: List[str]
    entropy_indices: List[int]
    timestamp: datetime
    description: str


class DiffResponse(BaseModel):
    files: List[FileDiff]


class EntropyHistoryEntry(BaseModel):
    timestamp: datetime
    who: str  # e.g., "player", "dm", "tool"
    what: str  # description of action
    indices: List[int]


class EventType(str, Enum):
    TRANSCRIPT_UPDATE = "transcript_update"
    LOCK_CLAIMED = "lock_claimed"
    LOCK_RELEASED = "lock_released"
    JOB_UPDATE = "job_update"


class ServerSentEvent(BaseModel):
    type: EventType
    data: Dict[str, Any]
    timestamp: datetime


class DMChoice(BaseModel):
    id: str
    text: str
    intent_tag: Literal["talk", "sneak", "fight", "magic", "investigate", "travel", "other"]
    risk: Literal["low", "medium", "high"]


class DiscoveryItem(BaseModel):
    title: str
    text: str


class DMNarration(BaseModel):
    narration: str
    recap: str
    stakes: str
    choices: List[DMChoice] = Field(min_length=2, max_length=4)
    discovery_added: Optional[DiscoveryItem] = None
    consequence_echo: Optional[str] = None
    choices_fallback: bool = False


class TurnRecord(BaseModel):
    turn: int
    player_intent: str
    diff: List[str]
    consequence_echo: str
    dm: DMNarration
    created_at: datetime


class CommitAndNarrateResponse(BaseModel):
    commit: CommitResponse
    dm: DMNarration
    turn_record: TurnRecord
    usage: Optional[Dict[str, int]] = None
