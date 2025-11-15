"""Configuration management for the bot."""
import os
from typing import Optional
from dotenv import load_dotenv

# Load .env file
load_dotenv()


class Config:
    """Bot configuration loaded from environment variables."""
    
    # Telegram Bot Configuration
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    APP_ID: int = int(os.getenv("APP_ID", "0"))
    APP_HASH: str = os.getenv("APP_HASH", "")
    
    # Database Configuration
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", "5432"))
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "godb")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "0208")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "tgbot")
    POSTGRES_SSLMODE: str = os.getenv("POSTGRES_SSLMODE", "disable")
    
    # Video Tutorial
    VIDEO_TUTORIAL_PATH: str = os.getenv("VIDEO_TUTORIAL_PATH", "video.mp4")
    VIDEO_TUTORIAL_FILE_ID: str = os.getenv("VIDEO_TUTORIAL_FILE_ID", "")
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "debug")
    
    @property
    def database_url(self) -> str:
        """Get PostgreSQL connection URL."""
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@"
            f"{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )
    
    def validate(self) -> bool:
        """Validate that required configuration is present."""
        if not self.BOT_TOKEN:
            return False
        if not self.APP_HASH:
            return False
        return True

