import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, status

from .. import storage
from ..config import Settings
from ..models import PreviewRequest, RollRequest, RollResult, SessionState
from .interfaces import (
    CharacterStore,
    EntropyStore,
    GenericDocStore,
    SessionStore,
    SnapshotStore,
    StateStore,
    StorageBackend,
    TextLogStore,
    TurnStore,
    WorldStore,
)


class FileSessionStore(SessionStore):
    def list_sessions(self, settings: Settings) -> List[Dict]:
        return storage.list_sessions(settings)

    def create_session(self, settings: Settings, slug: str, template_slug: str = "example-rogue") -> str:
        return storage.create_session(settings, slug, template_slug)

    def get_lock_info(self, settings: Settings, slug: str):
        return storage.get_lock_info(settings, slug)

    def claim_lock(self, settings: Settings, slug: str, owner: str, ttl: int) -> None:
        storage.claim_lock(settings, slug, owner, ttl)

    def release_lock(self, settings: Settings, slug: str) -> None:
        storage.release_lock(settings, slug)


class FileStateStore(StateStore):
    def load_state(self, settings: Settings, slug: str) -> Dict:
        return storage.load_state(settings, slug)

    def save_state(self, settings: Settings, slug: str, state: Dict) -> SessionState:
        return storage.save_state(settings, slug, state)

    def apply_state_patch(self, settings: Settings, slug: str, patch: Dict) -> SessionState:
        state = storage.load_state(settings, slug)
        updated = storage._apply_state_patch(state, patch)
        persisted = storage.save_state(settings, slug, updated)
        updates = storage._character_updates_from_state_patch(persisted.model_dump(mode="json"), patch)
        if updates:
            try:
                character = storage.load_character(settings, slug)
                updated_character, changed = storage._apply_character_updates(character, updates)
                if changed:
                    storage.save_character(settings, slug, updated_character, persist_to_data=True)
            except HTTPException:
                pass
        return persisted

    def validate_data(self, data: Dict, schema_name: str, settings: Settings) -> List[str]:
        return storage.validate_data(data, schema_name, settings)

    def load_quests(self, settings: Settings, slug: str) -> Dict:
        return storage.load_quests(settings, slug)

    def save_quest(self, settings: Settings, slug: str, quest_id: str, quest_data: Dict) -> None:
        storage.save_quest(settings, slug, quest_id, quest_data)

    def delete_quest(self, settings: Settings, slug: str, quest_id: str) -> None:
        storage.delete_quest(settings, slug, quest_id)


class FileTurnStore(TurnStore):
    def load_turn(self, settings: Settings, slug: str) -> str:
        return storage.load_turn(settings, slug)

    def create_preview(self, settings: Settings, slug: str, request: PreviewRequest) -> Tuple[str, List[Dict], Dict]:
        return storage.create_preview(settings, slug, request)

    def commit_preview(self, settings: Settings, slug: str, preview_id: str, lock_owner: Optional[str]) -> Tuple[Dict, Dict]:
        return storage.commit_preview(settings, slug, preview_id, lock_owner)

    def load_preview_metadata(self, settings: Settings, slug: str, preview_id: str) -> Dict:
        return storage.load_preview_metadata(settings, slug, preview_id)

    def summarize_state_diff(self, before: Dict, after: Dict) -> List[str]:
        return storage.summarize_state_diff(before, after)

    def persist_turn_record(self, settings: Settings, slug: str, record: Dict) -> None:
        storage.persist_turn_record(settings, slug, record)

    def load_turn_records(self, settings: Settings, slug: str, limit: int) -> List[Dict]:
        return storage.load_turn_records(settings, slug, limit)

    def load_turn_record(self, settings: Settings, slug: str, turn: int) -> Dict:
        return storage.load_turn_record(settings, slug, turn)

    def perform_roll(self, settings: Settings, slug: str, request: RollRequest) -> RollResult:
        return storage.perform_roll(settings, slug, request)

    def load_commit_history(self, settings: Settings, slug: str) -> List[Dict]:
        return storage.load_commit_history(settings, slug)

    def load_session_diff(self, settings: Settings, slug: str, from_commit: str, to_commit: str) -> List[Dict]:
        return storage.load_session_diff(settings, slug, from_commit, to_commit)


class FileEntropyStore(EntropyStore):
    def load_entropy_preview(self, settings: Settings, limit: int) -> List[Dict]:
        return storage.load_entropy_preview(settings, limit)

    def load_entropy_history(self, settings: Settings, slug: str, limit: int) -> List[Dict]:
        return storage.load_entropy_history(settings, slug, limit)

    def ensure_available(self, settings: Settings, target_index: int) -> None:
        storage._ensure_entropy_available(settings, target_index)

    def load_entry(self, settings: Settings, index: int) -> Dict:
        return storage._load_entropy_entry(settings, index)

    def reserve_indices(self, log_index: int, count: int) -> List[int]:
        if count <= 0:
            return []
        return list(range(log_index + 1, log_index + count + 1))

    def commit_indices(self, settings: Settings, slug: str, reserved_indices: List[int]) -> int:
        state = storage.load_state(settings, slug)
        current_index = state.get("log_index", 0)
        if not reserved_indices:
            return current_index
        expected_start = current_index + 1
        if reserved_indices[0] != expected_start:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Entropy reservation mismatch",
            )
        storage._ensure_entropy_available(settings, reserved_indices[-1])
        return reserved_indices[-1]


class FileCharacterStore(CharacterStore):
    def load_character(self, settings: Settings, slug: str) -> Dict:
        return storage.load_character(settings, slug)

    def save_character(self, settings: Settings, slug: str, character_data: Dict, persist_to_data: bool = True) -> Dict:
        return storage.save_character(settings, slug, character_data, persist_to_data=persist_to_data)


class FileTextLogStore(TextLogStore):
    def load_transcript(
        self,
        settings: Settings,
        slug: str,
        tail: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> Tuple[List[Dict], Optional[str]]:
        return storage.load_transcript(settings, slug, tail, cursor)

    def load_changelog(
        self,
        settings: Settings,
        slug: str,
        tail: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> Tuple[List[Dict], Optional[str]]:
        return storage.load_changelog(settings, slug, tail, cursor)


class FileGenericDocStore(GenericDocStore):
    def load_doc(self, settings: Settings, slug: str, name: str) -> Any:
        if name == "npc_memory":
            return storage.load_npc_memory(settings, slug)
        session_path = storage._ensure_session(settings, slug)
        path = session_path / f"{name}.json"
        if not path.exists():
            return {}
        with path.open() as handle:
            return json.load(handle)

    def save_doc(self, settings: Settings, slug: str, name: str, payload: Any) -> None:
        if name == "npc_memory":
            storage.save_npc_memory(settings, slug, payload)
            return
        session_path = storage._ensure_session(settings, slug)
        path = session_path / f"{name}.json"
        with path.open("w") as handle:
            json.dump(payload, handle, indent=2)

    def record_last_discovery_turn(self, settings: Settings, slug: str, turn: int) -> None:
        storage.record_last_discovery_turn(settings, slug, turn)

    def get_last_discovery_turn(self, settings: Settings, slug: str) -> Optional[int]:
        return storage.get_last_discovery_turn(settings, slug)


class FileSnapshotStore(SnapshotStore):
    def _saves_dir(self, settings: Settings, slug: str) -> Path:
        session_path = storage._ensure_session(settings, slug)
        saves_dir = session_path / "saves"
        saves_dir.mkdir(exist_ok=True)
        return saves_dir

    def create_save(self, settings: Settings, slug: str, save_name: str, save_type: str) -> Dict:
        timestamp = datetime.now(timezone.utc).isoformat()
        save_id = f"{save_name}-{timestamp}"
        payload = {
            "save_id": save_id,
            "session_slug": slug,
            "timestamp": timestamp,
            "save_type": save_type,
            "data": {},
        }
        save_path = self._saves_dir(settings, slug) / f"{save_id}.json"
        save_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload

    def list_saves(self, settings: Settings, slug: str, limit: int) -> List[Dict]:
        saves_dir = self._saves_dir(settings, slug)
        items: List[Dict] = []
        for path in sorted(saves_dir.glob("*.json"), reverse=True):
            try:
                items.append(json.loads(path.read_text(encoding="utf-8")))
            except Exception:
                continue
            if len(items) >= limit:
                break
        return items

    def get_save(self, settings: Settings, slug: str, save_id: str) -> Optional[Dict]:
        saves_dir = self._saves_dir(settings, slug)
        path = saves_dir / f"{save_id}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def restore_save(self, settings: Settings, slug: str, save_id: str) -> Dict:
        data = self.get_save(settings, slug, save_id)
        if data is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Save not found")
        return {"message": "Restore not implemented", "save": data}


class FileWorldStore(WorldStore):
    def load_factions(self, settings: Settings, slug: str) -> Dict:
        return storage.load_factions(settings, slug)

    def save_faction(self, settings: Settings, slug: str, faction_id: str, faction_data: Dict) -> None:
        storage.save_faction(settings, slug, faction_id, faction_data)

    def delete_faction(self, settings: Settings, slug: str, faction_id: str) -> None:
        storage.delete_faction(settings, slug, faction_id)

    def load_timeline(self, settings: Settings, slug: str) -> Dict:
        return storage.load_timeline(settings, slug)

    def save_timeline_event(self, settings: Settings, slug: str, event_id: str, event_data: Dict) -> None:
        storage.save_timeline_event(settings, slug, event_id, event_data)

    def delete_timeline_event(self, settings: Settings, slug: str, event_id: str) -> None:
        storage.delete_timeline_event(settings, slug, event_id)

    def load_rumors(self, settings: Settings, slug: str) -> Dict:
        return storage.load_rumors(settings, slug)

    def load_faction_clocks(self, settings: Settings, slug: str) -> Dict:
        return storage.load_faction_clocks(settings, slug)


def build_file_backend() -> StorageBackend:
    return StorageBackend(
        session=FileSessionStore(),
        state=FileStateStore(),
        turn=FileTurnStore(),
        entropy=FileEntropyStore(),
        character=FileCharacterStore(),
        text_logs=FileTextLogStore(),
        docs=FileGenericDocStore(),
        snapshots=FileSnapshotStore(),
        world=FileWorldStore(),
    )
