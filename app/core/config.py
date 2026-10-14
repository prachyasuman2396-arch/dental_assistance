import os
from typing import List, Union
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    APP_NAME: str = "AI Student Study & Research Assistant"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    PORT: int = 8000
    HOST: str = "0.0.0.0"
    CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, str):
            import json
            try:
                return json.loads(v)
            except Exception:
                return [v]
        return v

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgrespassword@localhost:5432/dental_agent_db"
    DATABASE_SYNC_URL: str = "postgresql+psycopg://postgres:postgrespassword@localhost:5432/dental_agent_db"

    # Security
    JWT_SECRET_KEY: str = "default-insecure-secret-key-change-in-production-12345"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

    # LLM Providers
    DEFAULT_LLM_PROVIDER: str = "groq"
    ENABLE_GEMINI: bool = True

    # Groq Settings
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "qwen/qwen3.8-27b"
    GROQ_FAST_MODEL: str = "qwen/qwen3.8-27b"
    GROQ_MAX_RETRIES: int = 3
    GROQ_TIMEOUT_SECONDS: float = 30.0

    # Gemini Settings
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-3.5-flash"
    GEMINI_FLASH_MODEL: str = "gemini-3.5-flash-lite"
    GEMINI_MAX_RETRIES: int = 3
    GEMINI_TIMEOUT_SECONDS: float = 60.0

    # Embedding Settings
    EMBEDDING_PROVIDER: str = "fastembed"
    EMBEDDING_MODEL_NAME: str = "BAAI/bge-small-en-v1.5"
    EMBEDDING_DIMENSION: int = 384

    # Document RAG Settings
    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 150
    MAX_UPLOAD_SIZE_MB: int = 25
    UPLOAD_STORAGE_DIR: str = "./uploads"

    # Scholarly & Web Research
    NCBI_API_KEY: str = ""
    EUROPE_PMC_BASE_URL: str = "https://www.ebi.ac.uk/europepmc/webservices/rest"
    CROSSREF_BASE_URL: str = "https://api.crossref.org"
    TAVILY_API_KEY: str = ""
    RESEARCH_MAX_RESULTS: int = 5


settings = Settings()
