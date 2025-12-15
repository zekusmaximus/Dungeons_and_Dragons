from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Runtime configuration for the DM service."""

    repo_root: Path = Path(__file__).resolve().parent.parent
    sessions_dir: str = "sessions"
    dice_file: str = "dice/entropy.ndjson"
    transcript_tail: int = 50
    changelog_tail: int = 50

    class Config:
        env_prefix = "DM_SERVICE_"

    @property
    def sessions_path(self) -> Path:
        return self.repo_root / self.sessions_dir

    @property
    def dice_path(self) -> Path:
        return self.repo_root / self.dice_file


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
