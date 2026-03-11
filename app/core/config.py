import os
import sys
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    
    # Application
    APP_NAME: str = "Pharma SOP Compliance Analyzer"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = Field(default="development", description="Environment: development, staging, production")
    DEBUG: bool = Field(default=False, description="Enable debug mode")
    
    # Database
    DATABASE_URL: str = Field(
        default="postgresql+psycopg2://postgres:postgres@localhost:5432/pharma",
        description="PostgreSQL connection URL"
    )
    SQLALCHEMY_ECHO: bool = Field(default=False, description="Enable SQLAlchemy SQL echo")
    DB_POOL_SIZE: int = Field(default=10, description="Database connection pool size")
    DB_MAX_OVERFLOW: int = Field(default=20, description="Database max overflow connections")
    DB_POOL_TIMEOUT: int = Field(default=30, description="Database pool timeout in seconds")
    DB_POOL_RECYCLE: int = Field(default=1800, description="Database pool recycle time in seconds")
    
    # JWT Authentication
    JWT_SECRET: str = Field(default="dev-secret-change-in-production", description="JWT secret key")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRES_MIN: int = Field(default=720, description="JWT token expiration in minutes")
    
    # Gemini API
    GEMINI_API_KEY: str = Field(default="", description="Google Gemini API key")
    GEMINI_EMBED_MODEL: str = Field(default="text-embedding-004", description="Gemini embedding model")
    EMBEDDING_DIM: int = Field(default=768, description="Embedding vector dimension")
    
    # FAISS
    FAISS_DIR: str = Field(default="./app/data", description="FAISS index storage directory")
    
    # CORS
    CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:5173", "http://localhost:3000"],
        description="Allowed CORS origins"
    )
    
    # Rate Limiting
    RATE_LIMIT_PER_MIN: int = Field(default=60, description="API rate limit per minute")
    
    # Security
    SECRET_KEY: str = Field(default_factory=lambda: os.getenv("SECRET_KEY", "dev-secret-key-change-in-production"))
    
    # Logging
    LOG_LEVEL: str = Field(default="INFO", description="Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL")
    LOG_FORMAT: str = Field(default="json", description="Log format: json, console")
    
    # Monitoring
    ENABLE_METRICS: bool = Field(default=True, description="Enable Prometheus metrics")
    
    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"
    
    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"


def get_settings() -> Settings:
    """Get application settings singleton."""
    if not hasattr(get_settings, "_settings"):
        get_settings._settings = Settings()
    return get_settings._settings
