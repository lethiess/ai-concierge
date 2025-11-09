"""Configuration management for AI Concierge using Pydantic."""

import logging

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Config(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # OpenAI Configuration
    openai_api_key: str = Field(..., description="OpenAI API key")

    # Twilio Configuration
    twilio_account_sid: str | None = Field(None, description="Twilio account SID")
    twilio_auth_token: str | None = Field(None, description="Twilio auth token")
    twilio_phone_number: str | None = Field(None, description="Twilio phone number")

    # Server Configuration
    server_host: str = Field(default="0.0.0.0", description="Server host")
    server_port: int = Field(default=8080, description="Server port")
    server_url: str = Field(
        default="http://localhost:8080",
        description="Server URL for CLI to connect to API",
    )
    public_domain: str | None = Field(
        None, description="Public domain for Twilio webhooks (e.g., abc123.ngrok.io)"
    )

    # Demo Restaurant Configuration
    demo_restaurant_phone: str = Field(
        default="+1234567890", description="Demo restaurant phone number"
    )
    demo_restaurant_name: str = Field(
        default="Demo Restaurant", description="Demo restaurant name"
    )

    # Logging Configuration
    log_level: str = Field(default="INFO", description="Logging level")

    # Agent Configuration
    agent_model: str = Field(default="gpt-4o", description="OpenAI model for agents")
    agent_temperature: float = Field(
        default=0.7, description="Temperature for agent responses"
    )
    realtime_model: str = Field(
        default="gpt-4o-realtime-preview-2024-10-01",
        description="OpenAI Realtime model",
    )
    realtime_voice: str = Field(
        default="alloy",
        description="Voice for realtime agent (alloy, echo, fable, onyx, nova, shimmer)",
    )

    def has_twilio_config(self) -> bool:
        """Check if Twilio is properly configured."""
        return bool(
            self.twilio_account_sid
            and self.twilio_auth_token
            and self.twilio_phone_number
        )

    def model_post_init(self, __context) -> None:
        """Validate configuration after initialization."""
        if not self.twilio_account_sid:
            logger.warning("TWILIO_ACCOUNT_SID not set - Twilio features disabled")

        if not self.twilio_auth_token:
            logger.warning("TWILIO_AUTH_TOKEN not set - Twilio features disabled")

        if not self.twilio_phone_number:
            logger.warning("TWILIO_PHONE_NUMBER not set - Twilio features disabled")


# Global config instance
config: Config | None = None


def get_config() -> Config:
    """Get or create the global configuration instance."""
    global config
    if config is None:
        config = Config()
    return config


def setup_logging(cfg: Config | None = None) -> None:
    """Configure logging for the application."""
    if cfg is None:
        cfg = get_config()

    log_level = getattr(logging, cfg.log_level.upper(), logging.INFO)

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Reduce noise from external libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("twilio").setLevel(logging.WARNING)
