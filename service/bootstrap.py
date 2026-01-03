from __future__ import annotations

import shutil
from pathlib import Path
from typing import Iterable, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .config import Settings


_SEED_DIRS = [
    "PROMPTS",
    "schemas",
    "data",
    "dice",
    "sessions",
    "worlds",
    "rules_index",
    "tables",
    "quests",
    "exploration",
    "combat",
    "downtime",
    "factions",
    "locations",
    "mysteries",
    "narrative",
    "npcs",
    "party",
    "rumors",
    "timeline",
    "character_creation",
]

_SEED_FILES = [
    "ENGINE.md",
    "PROTOCOL.md",
    "INSTRUCTION_MANUAL.md",
]


def _copy_item(src: Path, dest: Path) -> None:
    if src.is_dir():
        for child in src.rglob("*"):
            if child.is_dir():
                continue
            rel = child.relative_to(src)
            target = dest / rel
            if target.exists():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(child, target)
    else:
        if dest.exists():
            return
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)


def ensure_data_root(settings: "Settings") -> None:
    data_root = settings.data_root
    if data_root is None:
        return
    seed_root = settings.seed_root or settings.repo_root
    if data_root.resolve() == seed_root.resolve():
        return
    data_root.mkdir(parents=True, exist_ok=True)

    for rel in _SEED_DIRS:
        src = seed_root / rel
        if not src.exists():
            continue
        dest = data_root / rel
        _copy_item(src, dest)

    for rel in _SEED_FILES:
        src = seed_root / rel
        if not src.exists():
            continue
        dest = data_root / rel
        if dest.exists():
            continue
        _copy_item(src, dest)
