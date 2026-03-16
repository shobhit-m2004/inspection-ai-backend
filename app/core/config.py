from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    app_name: str = 'SOP vs Log Gap Detection API'
    api_prefix: str = '/api'

    backend_host: str = '0.0.0.0'
    backend_port: int = 8000

    database_url: str = 'postgresql+psycopg://postgres:postgres@localhost:5432/sop_gap'

    openai_api_key: str | None = None
    openai_model: str = 'gpt-4.1-mini'

    allowed_origins: str = 'http://localhost:5173'

    storage_root: Path = Path('storage')

    @property
    def uploads_dir(self) -> Path:
        return self.storage_root / 'uploads'

    @property
    def cors_origins(self) -> list[str]:
        return [item.strip() for item in self.allowed_origins.split(',') if item.strip()]


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    return settings
