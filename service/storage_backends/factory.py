import os

from ..config import Settings
from .file_backend import build_file_backend
from .interfaces import StorageBackend

_BACKEND_CACHE: dict[str, StorageBackend] = {}


def get_storage_backend(settings: Settings) -> StorageBackend:
    backend_name = os.getenv("STORAGE_BACKEND", "file").lower()
    backend = _BACKEND_CACHE.get(backend_name)
    if backend is not None:
        return backend
    if backend_name == "file":
        backend = build_file_backend()
    else:
        raise ValueError(f"Unsupported storage backend: {backend_name}")
    _BACKEND_CACHE[backend_name] = backend
    return backend
