from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol, Tuple

from ..config import Settings
from ..models import LockInfo, PreviewRequest, RollRequest, RollResult, SessionState


class SessionStore(Protocol):
    def list_sessions(self, settings: Settings) -> List[Dict]:
        ...

    def create_session(self, settings: Settings, slug: str, template_slug: str = "example-rogue") -> str:
        ...

    def get_lock_info(self, settings: Settings, slug: str) -> Optional[LockInfo]:
        ...

    def claim_lock(self, settings: Settings, slug: str, owner: str, ttl: int) -> None:
        ...

    def release_lock(self, settings: Settings, slug: str) -> None:
        ...


class StateStore(Protocol):
    def load_state(self, settings: Settings, slug: str) -> Dict:
        ...

    def save_state(self, settings: Settings, slug: str, state: Dict) -> SessionState:
        ...

    def apply_state_patch(self, settings: Settings, slug: str, patch: Dict) -> SessionState:
        ...

    def validate_data(self, data: Dict, schema_name: str, settings: Settings) -> List[str]:
        ...

    def load_quests(self, settings: Settings, slug: str) -> Dict:
        ...

    def save_quest(self, settings: Settings, slug: str, quest_id: str, quest_data: Dict) -> None:
        ...

    def delete_quest(self, settings: Settings, slug: str, quest_id: str) -> None:
        ...


class TurnStore(Protocol):
    def load_turn(self, settings: Settings, slug: str) -> str:
        ...

    def create_preview(self, settings: Settings, slug: str, request: PreviewRequest) -> Tuple[str, List[Dict], Dict]:
        ...

    def commit_preview(self, settings: Settings, slug: str, preview_id: str, lock_owner: Optional[str]) -> Tuple[Dict, Dict]:
        ...

    def load_preview_metadata(self, settings: Settings, slug: str, preview_id: str) -> Dict:
        ...

    def summarize_state_diff(self, before: Dict, after: Dict) -> List[str]:
        ...

    def persist_turn_record(self, settings: Settings, slug: str, record: Dict) -> None:
        ...

    def load_turn_records(self, settings: Settings, slug: str, limit: int) -> List[Dict]:
        ...

    def load_turn_record(self, settings: Settings, slug: str, turn: int) -> Dict:
        ...

    def perform_roll(self, settings: Settings, slug: str, request: RollRequest) -> RollResult:
        ...

    def load_commit_history(self, settings: Settings, slug: str) -> List[Dict]:
        ...

    def load_session_diff(self, settings: Settings, slug: str, from_commit: str, to_commit: str) -> List[Dict]:
        ...


class EntropyStore(Protocol):
    def load_entropy_preview(self, settings: Settings, limit: int) -> List[Dict]:
        ...

    def load_entropy_history(self, settings: Settings, slug: str, limit: int) -> List[Dict]:
        ...

    def ensure_available(self, settings: Settings, target_index: int) -> None:
        ...

    def load_entry(self, settings: Settings, index: int) -> Dict:
        ...

    def reserve_indices(self, log_index: int, count: int) -> List[int]:
        ...

    def commit_indices(self, settings: Settings, slug: str, reserved_indices: List[int]) -> int:
        ...


class CharacterStore(Protocol):
    def load_character(self, settings: Settings, slug: str) -> Dict:
        ...

    def save_character(self, settings: Settings, slug: str, character_data: Dict, persist_to_data: bool = True) -> Dict:
        ...


class TextLogStore(Protocol):
    def load_transcript(
        self,
        settings: Settings,
        slug: str,
        tail: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> Tuple[List[Dict], Optional[str]]:
        ...

    def load_changelog(
        self,
        settings: Settings,
        slug: str,
        tail: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> Tuple[List[Dict], Optional[str]]:
        ...


class GenericDocStore(Protocol):
    def load_doc(self, settings: Settings, slug: str, name: str) -> Any:
        ...

    def save_doc(self, settings: Settings, slug: str, name: str, payload: Any) -> None:
        ...

    def record_last_discovery_turn(self, settings: Settings, slug: str, turn: int) -> None:
        ...

    def get_last_discovery_turn(self, settings: Settings, slug: str) -> Optional[int]:
        ...


class SnapshotStore(Protocol):
    def create_save(self, settings: Settings, slug: str, save_name: str, save_type: str) -> Dict:
        ...

    def list_saves(self, settings: Settings, slug: str, limit: int) -> List[Dict]:
        ...

    def get_save(self, settings: Settings, slug: str, save_id: str) -> Optional[Dict]:
        ...

    def restore_save(self, settings: Settings, slug: str, save_id: str) -> Dict:
        ...


class WorldStore(Protocol):
    def load_factions(self, settings: Settings, slug: str) -> Dict:
        ...

    def save_faction(self, settings: Settings, slug: str, faction_id: str, faction_data: Dict) -> None:
        ...

    def delete_faction(self, settings: Settings, slug: str, faction_id: str) -> None:
        ...

    def load_timeline(self, settings: Settings, slug: str) -> Dict:
        ...

    def save_timeline_event(self, settings: Settings, slug: str, event_id: str, event_data: Dict) -> None:
        ...

    def delete_timeline_event(self, settings: Settings, slug: str, event_id: str) -> None:
        ...

    def load_rumors(self, settings: Settings, slug: str) -> Dict:
        ...

    def load_faction_clocks(self, settings: Settings, slug: str) -> Dict:
        ...


@dataclass(frozen=True)
class StorageBackend:
    session: SessionStore
    state: StateStore
    turn: TurnStore
    entropy: EntropyStore
    character: CharacterStore
    text_logs: TextLogStore
    docs: GenericDocStore
    snapshots: SnapshotStore
    world: WorldStore
