import json
import sys
import time
from pathlib import Path


REQUIRED_MONSTER_FIELDS = {
    "name",
    "size",
    "type",
    "alignment",
    "armor_class",
    "hit_points",
    "speed",
    "abilities",
    "challenge",
    "actions",
}


def _load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: invalid JSON ({exc})") from exc


def _validate_monsters(monsters_dir: Path) -> list[str]:
    errors = []
    monster_files = sorted(monsters_dir.glob("*.json"))
    if not monster_files:
        errors.append("No monster files found in data/monsters.")
        return errors
    for path in monster_files:
        try:
            payload = _load_json(path)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        missing = REQUIRED_MONSTER_FIELDS - payload.keys()
        if missing:
            errors.append(f"{path}: missing fields {sorted(missing)}")
        if not isinstance(payload.get("actions"), list) or not payload["actions"]:
            errors.append(f"{path}: actions must be a non-empty list")
    return errors


def _validate_rules(rules_dir: Path) -> list[str]:
    errors = []
    rule_files = sorted(rules_dir.glob("*.md"))
    if len(rule_files) < 3:
        errors.append("Expected at least 3 rules markdown files in data/rules.")
    for path in rule_files:
        if not path.read_text(encoding="utf-8").strip():
            errors.append(f"{path}: file is empty")
    return errors


def _index_rules(repo_root: Path) -> None:
    sys.path.insert(0, str(repo_root))
    from tools import index_rules

    cwd = Path.cwd()
    try:
        sys.chdir(repo_root)
        index_rules.main()
    finally:
        sys.chdir(cwd)


def _create_demo_session(repo_root: Path) -> str:
    sys.path.insert(0, str(repo_root))
    from service.config import get_settings
    from service.storage_backends.factory import get_storage_backend

    get_settings.cache_clear()
    settings = get_settings()
    backend = get_storage_backend(settings)
    slug = f"demo-sanity-{time.strftime('%Y%m%d-%H%M%S')}"
    return backend.session.create_session(settings, slug, "example-rogue")


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    rules_dir = repo_root / "data" / "rules"
    monsters_dir = repo_root / "data" / "monsters"

    errors = []
    errors.extend(_validate_rules(rules_dir))
    errors.extend(_validate_monsters(monsters_dir))

    if errors:
        print("Sanity check failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    _index_rules(repo_root)
    slug = _create_demo_session(repo_root)
    print("Sanity check passed.")
    print(f"Indexed rules and created demo session: {slug}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
