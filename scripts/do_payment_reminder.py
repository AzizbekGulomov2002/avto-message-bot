#!/usr/bin/env python3
"""Cron-friendly DigitalOcean payment reminder for superadmins.

Example crontab (daily at 09:00 Tashkent ≈ 04:00 UTC in winter):
0 4 * * * cd /home/avto-message-bot && ./env/bin/python scripts/do_payment_reminder.py >> logs/do_reminder.log 2>&1
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pytz
import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from bot.config import Config
from bot.digitalocean import DigitalOceanAPIError, fetch_billing_summary
from bot.do_payment_reminder import (
    format_payment_reminder_message,
    mark_reminder_sent,
    should_send_payment_reminder,
)
from bot.storage.database import Database
from bot.storage.user_storage import UserStorage


def send_telegram_message(bot_token: str, chat_id: int, text: str) -> bool:
    response = requests.post(
        f"https://api.telegram.org/bot{bot_token}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
        },
        timeout=20,
    )
    if not response.ok:
        print(f"Failed to notify {chat_id}: {response.text[:200]}")
        return False
    return True


def main() -> int:
    config = Config()
    if not config.DO_TOKEN:
        print("DO_TOKEN is not configured.")
        return 1
    if not config.BOT_TOKEN:
        print("BOT_TOKEN is not configured.")
        return 1

    should_send, days_left, next_payment = should_send_payment_reminder()
    if not should_send or days_left is None or next_payment is None:
        print("No payment reminder needed today.")
        return 0

    try:
        summary = fetch_billing_summary(config.DO_TOKEN)
    except DigitalOceanAPIError as error:
        print(f"DigitalOcean API error: {error}")
        return 1

    message = format_payment_reminder_message(summary, days_left)
    db = Database(config)
    db.connect()
    user_storage = UserStorage(db)

    try:
        superusers = user_storage.get_superuser_ids()
        if not superusers:
            print("No superusers configured.")
            return 1

        sent_any = False
        for superuser_id in superusers:
            if send_telegram_message(config.BOT_TOKEN, superuser_id, message):
                sent_any = True
                print(f"Reminder sent to superuser {superuser_id}")

        if sent_any:
            mark_reminder_sent(next_payment, datetime.now(pytz.timezone("Asia/Tashkent")))
            return 0

        print("Failed to notify any superuser.")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
