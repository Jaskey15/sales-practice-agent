"""
Configuration management for the sales training system.
Loads environment variables and provides typed configuration.
"""
from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Twilio Configuration
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_phone_number: str

    # OpenRouter API Configuration
    openrouter_api_key: str
    openrouter_model: str = "google/gemini-2.5-flash"
    openrouter_http_referer: Optional[str] = None
    openrouter_x_title: Optional[str] = None

    # Application Configuration
    host: str = "0.0.0.0"
    port: int = 8000
    base_url: str  # Your public URL for Twilio webhooks (e.g., from ngrok)

    # ConversationRelay / ElevenLabs Configuration
    conversation_relay_voice_id: str = "OYTbf65OHHFELVut7v2H"
    conversation_relay_text_normalization: Optional[str] = "on"
    conversation_relay_language: str = "en-US"

    # Storage Configuration
    transcripts_dir: str = "data/calls"

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

