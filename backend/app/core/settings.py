"""Archimedes platform settings — SOPS-aware configuration loader."""
import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = os.getenv("DATABASE_URL", "postgresql://archimedes:archimedes@localhost:5432/archimedes")
    minio_endpoint: str = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    minio_access_key: str = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
    minio_secret_key: str = os.getenv("MINIO_SECRET_KEY", "minioadmin")
    langfuse_public_key: str = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    langfuse_secret_key: str = os.getenv("LANGFUSE_SECRET_KEY", "")
    litellm_base_url: str = os.getenv("LITELLM_BASE_URL", "http://localhost:4000")
    environment: str = os.getenv("ENVIRONMENT", "development")

    class Config:
        env_file = None  # No .env loading — SOPS-decrypted env vars only


def get_settings() -> Settings:
    return Settings()
