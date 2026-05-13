"""Telegram notifications for superuser and activation flows."""
import calendar
import logging
import os
from datetime import datetime

import pytz
import requests

logger = logging.getLogger(__name__)

TASHKENT_TZ = pytz.timezone('Asia/Tashkent')


def _bot_token() -> str:
    return os.getenv("BOT_TOKEN", "").strip()


def send_telegram_message(
    user_id: int,
    message: str,
    show_menu: bool = False,
    reply_markup: dict | None = None,
) -> bool:
    """Send a message to a Telegram user."""
    bot_token = _bot_token()
    if not bot_token:
        logger.error("BOT_TOKEN not found in environment variables")
        return False

    payload = {
        "chat_id": user_id,
        "text": message,
        "parse_mode": "HTML",
    }

    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    elif show_menu:
        payload["reply_markup"] = {
            "inline_keyboard": [
                [
                    {"text": "📤 Xabar yuborish", "callback_data": "action_send_message"},
                    {"text": "📋 Xabarlar jadvali", "callback_data": "action_messages_table"},
                ],
                [
                    {"text": "📹 Video qo'llanma", "callback_data": "action_video_tutorial"},
                ],
            ]
        }

    try:
        response = requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json=payload,
            timeout=10,
        )
        response.raise_for_status()
        return True
    except Exception as exc:
        logger.error("Error sending Telegram message to user %s: %s", user_id, exc)
        return False


def _shift_access_calendar_month(year: int, month: int, offset: int) -> tuple[int, int]:
    month += offset
    while month < 1:
        month += 12
        year -= 1
    while month > 12:
        month -= 12
        year += 1
    return year, month


def build_access_calendar_keyboard(target_user_id: int, year: int, month: int) -> dict:
    """Build inline calendar markup for activation approval."""
    prev_year, prev_month = _shift_access_calendar_month(year, month, -1)
    next_year, next_month = _shift_access_calendar_month(year, month, 1)
    month_name = calendar.month_name[month]

    keyboard = [[
        {"text": "◀️", "callback_data": f"access_cal_{target_user_id}_{prev_year}_{prev_month}"},
        {"text": f"{month_name} {year}", "callback_data": "access_ignore"},
        {"text": "▶️", "callback_data": f"access_cal_{target_user_id}_{next_year}_{next_month}"},
    ]]

    for week in calendar.monthcalendar(year, month):
        row = []
        for day in week:
            if day == 0:
                continue
            date_value = f"{year}-{month:02d}-{day:02d}"
            row.append({
                "text": str(day),
                "callback_data": f"access_day_{target_user_id}_{date_value}",
            })
        if row:
            keyboard.append(row)

    keyboard.append([
        {"text": "❌ Rad etish", "callback_data": f"access_reject_{target_user_id}"},
    ])
    return {"inline_keyboard": keyboard}


def build_activation_request_message(user_id: int, full_name: str | None, phone: str | None) -> str:
    """Build activation request text for superusers."""
    return (
        "🆕 Yangi foydalanuvchi aktivatsiya kutmoqda\n\n"
        f"ID: {user_id}\n"
        f"Ism: {full_name or '—'}\n"
        f"Telefon: {phone or '—'}\n\n"
        "Qaysi sanagacha aktiv qilasiz?"
    )


def notify_superuser_assigned(superuser_id: int) -> None:
    """Notify a Telegram user that they were granted superuser access."""
    send_telegram_message(
        superuser_id,
        "✅ Siz superuser qilindingiz. Endi aktivatsiya kutayotgan foydalanuvchilar haqida xabar olasiz.",
    )


def notify_pending_activation_request(superuser_id: int, pending_user) -> bool:
    """Send one pending activation request to a superuser."""
    now = datetime.now(TASHKENT_TZ)
    return send_telegram_message(
        superuser_id,
        build_activation_request_message(
            pending_user.id,
            pending_user.full_name,
            pending_user.phone,
        ),
        reply_markup=build_access_calendar_keyboard(pending_user.id, now.year, now.month),
    )


def notify_pending_activation_requests_for_superuser(superuser_id: int) -> int:
    """Send all pending activation requests to a superuser."""
    from users.models import User

    pending_users = User.objects.filter(
        auth=1,
        status=0,
        is_superuser=False,
    ).exclude(full_name__isnull=True).exclude(full_name='')

    sent_count = 0
    for pending_user in pending_users:
        if notify_pending_activation_request(superuser_id, pending_user):
            sent_count += 1
    return sent_count
