"""Helper functions for sending Telegram messages."""
import os
import requests
import logging

logger = logging.getLogger(__name__)


def send_telegram_message(user_id: int, message: str, show_menu: bool = False) -> bool:
    """Send message to user via Telegram Bot API."""
    bot_token = os.getenv("BOT_TOKEN", "")
    if not bot_token:
        logger.error("BOT_TOKEN not found in environment variables")
        return False
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": user_id,
        "text": message,
        "parse_mode": "HTML"
    }
    
    # Add inline keyboard if show_menu is True
    if show_menu:
        reply_markup = {
            "inline_keyboard": [
                [
                    {"text": "📤 Xabar yuborish", "callback_data": "action_send_message"},
                    {"text": "📋 Xabarlar jadvali", "callback_data": "action_messages_table"}
                ],
                [
                    {"text": "📹 Video qo'llanma", "callback_data": "action_video_tutorial"}
                ]
            ]
        }
        payload["reply_markup"] = reply_markup
    
    try:
        response = requests.post(url, json=payload, timeout=5)
        response.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"Error sending Telegram message to user {user_id}: {e}")
        return False

