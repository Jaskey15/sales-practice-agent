"""
Configuration management for the sales training system.
Loads environment variables and provides typed configuration.
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Twilio Configuration
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_phone_number: str

    # OpenAI API Configuration
    openai_api_key: str
    openai_model: str = "gpt-5-chat"

    # Application Configuration
    host: str = "0.0.0.0"
    port: int = 8000
    base_url: str  # Your public URL for Twilio webhooks (e.g., from ngrok)

    # Storage Configuration
    transcripts_dir: str = "data/transcripts"

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
