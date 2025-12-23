import os

from ..config import Settings
from .file_backend import build_file_backend
from .interfaces import StorageBackend
from .sqlite_backend import _resolve_db_path, build_sqlite_backend

_BACKEND_CACHE: dict[str, StorageBackend] = {}


def _cache_key(backend_name: str, settings: Settings) -> str:
    if backend_name == "sqlite":
        db_path = _resolve_db_path(settings)
        return f"{backend_name}:{db_path}"
    return backend_name


def get_storage_backend(settings: Settings) -> StorageBackend:
    backend_name = os.getenv("STORAGE_BACKEND", "file").lower()
    key = _cache_key(backend_name, settings)
    backend = _BACKEND_CACHE.get(key)
    if backend is not None:
        return backend
    if backend_name == "file":
        backend = build_file_backend()
    elif backend_name == "sqlite":
        backend = build_sqlite_backend(settings, db_path=_resolve_db_path(settings))
    else:
        raise ValueError(f"Unsupported storage backend: {backend_name}")
    _BACKEND_CACHE[key] = backend
    return backend
