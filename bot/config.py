"""Configuration management for the bot."""
import logging
import os
import re
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / '.env')

BOT_TOKEN_PATTERN = re.compile(r"^\d+:[A-Za-z0-9_-]+$")


def normalize_bot_token(raw_token: str) -> str:
    """Normalize BOT_TOKEN and fix common duplicate-id mistakes."""
    token = (raw_token or "").strip()
    if not token:
        return ""

    parts = token.split(":")
    if len(parts) == 3 and parts[0].isdigit() and parts[0] == parts[1] and parts[2]:
        fixed = f"{parts[0]}:{parts[2]}"
        logger.warning(
            "BOT_TOKEN contained duplicate bot id; auto-corrected to %s:***",
            parts[0],
        )
        return fixed

    return token


class Config:
    """Bot configuration loaded from environment variables."""
    
    # Telegram Bot Configuration
    BOT_TOKEN: str = normalize_bot_token(os.getenv("BOT_TOKEN", ""))
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
    VIDEO_TUTORIAL_FILE_ID: str = (os.getenv("VIDEO_TUTORIAL_FILE_ID", "") or "").strip()
    LOADING_STICKER_FILE_ID: str = (os.getenv("LOADING_STICKER_FILE_ID", "") or "").strip()
    
    # DigitalOcean billing (superadmin /money command)
    DO_TOKEN: str = (os.getenv("DO_TOKEN", "") or "").strip()

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
            logger.error("BOT_TOKEN is missing in .env")
            return False
        if not BOT_TOKEN_PATTERN.fullmatch(self.BOT_TOKEN):
            logger.error(
                "BOT_TOKEN format is invalid. Expected format from @BotFather: "
                "123456789:AAHxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
            )
            return False
        if not self.APP_HASH:
            logger.error("APP_HASH is missing in .env")
            return False
        return True

