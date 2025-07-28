"""
Application configuration using Pydantic Settings.
Manages environment variables and application settings.
"""

import secrets
from functools import lru_cache
from typing import List, Optional

from pydantic import Field, validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Application Configuration
    SECRET_KEY: str = Field(default_factory=lambda: secrets.token_urlsafe(32))
    ENVIRONMENT: str = Field(default="development")
    DEBUG: bool = Field(default=True)
    LOG_LEVEL: str = Field(default="INFO")
    
    # Server Configuration
    HOST: str = Field(default="0.0.0.0")
    PORT: int = Field(default=8000)
    WORKERS: int = Field(default=1)
    RELOAD: bool = Field(default=True)
    ACCESS_LOG: bool = Field(default=True)
    
    # Database Configuration
    DATABASE_URL: str = Field(default="sqlite:///./computer_use.db")
    DATABASE_URL_ASYNC: Optional[str] = Field(default=None)
    
    # Anthropic API Configuration
    ANTHROPIC_API_KEY: str = Field(...)
    
    # VNC Configuration
    VNC_HOST: str = Field(default="localhost")
    VNC_PORT: int = Field(default=5900)
    VNC_PASSWORD: Optional[str] = Field(default=None)
    
    # WebSocket Configuration
    WS_HEARTBEAT_INTERVAL: int = Field(default=30)
    WS_MAX_CONNECTIONS: int = Field(default=100)
    
    # CORS Configuration
    ALLOWED_ORIGINS: List[str] = Field(default=["http://localhost:3000", "http://localhost:8080"])
    ALLOWED_METHODS: List[str] = Field(default=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
    ALLOWED_HEADERS: List[str] = Field(default=["*"])
    
    # File Upload Configuration
    MAX_FILE_SIZE: int = Field(default=10485760)  # 10MB
    UPLOAD_DIRECTORY: str = Field(default="./uploads")
    
    # Computer Use Configuration
    COMPUTER_USE_ENABLED: bool = Field(default=True)
    SCREENSHOT_DELAY: float = Field(default=1.0)
    MAX_TOOL_CALLS: int = Field(default=50)
    
    # Session Configuration
    SESSION_TIMEOUT: int = Field(default=3600)  # 1 hour
    MAX_SESSIONS_PER_USER: int = Field(default=10)
    
    # Redis Configuration (optional)
    REDIS_URL: Optional[str] = Field(default=None)
    
    @validator("ALLOWED_ORIGINS", pre=True)
    def parse_cors_origins(cls, v):
        """Parse CORS origins from string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v
    
    @validator("ALLOWED_METHODS", pre=True)
    def parse_cors_methods(cls, v):
        """Parse CORS methods from string or list."""
        if isinstance(v, str):
            return [method.strip() for method in v.split(",")]
        return v
    
    @validator("ALLOWED_HEADERS", pre=True)
    def parse_cors_headers(cls, v):
        """Parse CORS headers from string or list."""
        if isinstance(v, str):
            return [header.strip() for header in v.split(",")]
        return v
    
    @validator("DATABASE_URL_ASYNC", always=True)
    def set_async_database_url(cls, v, values):
        """Set async database URL if not provided."""
        if v is None:
            database_url = values.get("DATABASE_URL", "")
            if database_url.startswith("postgresql://"):
                return database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
            elif database_url.startswith("sqlite:///"):
                return database_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
        return v
    
    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.ENVIRONMENT.lower() == "development"
    
    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.ENVIRONMENT.lower() == "production"
    
    @property
    def is_testing(self) -> bool:
        """Check if running in testing environment."""
        return self.ENVIRONMENT.lower() == "testing"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()