from functools import lru_cache
from pathlib import Path
from typing import Optional

try:  # pragma: no cover - fallback when dependency unavailable
    from pydantic_settings import BaseSettings
except ImportError:  # pragma: no cover
    from pydantic import BaseModel as BaseSettings


class Settings(BaseSettings):
    """Runtime configuration for the DM service."""

    repo_root: Path = Path(__file__).resolve().parent.parent
    sessions_dir: str = "sessions"
    data_dir: str = "data"
    worlds_dir: str = "worlds"
    dice_file: str = "dice/entropy.ndjson"
    transcript_tail: int = 50
    changelog_tail: int = 50
    
    # LLM Configuration
    llm_api_key: Optional[str] = None
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o"
    llm_temperature: float = 0.7
    llm_max_tokens: int = 500

    class Config:
        env_prefix = "DM_SERVICE_"

    @property
    def sessions_path(self) -> Path:
        return self.repo_root / self.sessions_dir

    @property
    def data_path(self) -> Path:
        return self.repo_root / self.data_dir

    @property
    def characters_path(self) -> Path:
        return self.data_path / "characters"

    @property
    def worlds_path(self) -> Path:
        return self.repo_root / self.worlds_dir

    @property
    def dice_path(self) -> Path:
        return self.repo_root / self.dice_file

    @property
    def has_llm_config(self) -> bool:
        return self.llm_api_key is not None and len(self.llm_api_key) > 0


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
