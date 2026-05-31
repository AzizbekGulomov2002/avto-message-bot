"""DigitalOcean payment reminder state and scheduling helpers."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import pytz

from bot.digitalocean import TASHKENT_TZ, days_until_next_payment, next_invoice_date

PAYMENT_REMINDER_DAYS = 3
STATE_FILE = Path(__file__).resolve().parent / "data" / "do_payment_reminder.json"


def _ensure_state_dir():
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)


def _load_state() -> dict[str, Any]:
    _ensure_state_dir()
    if not STATE_FILE.exists():
        return {"sent": {}}
    try:
        with open(STATE_FILE, encoding="utf-8") as handle:
            data = json.load(handle)
            if isinstance(data, dict) and "sent" in data:
                return data
    except (OSError, json.JSONDecodeError):
        pass
    return {"sent": {}}


def _save_state(state: dict[str, Any]):
    _ensure_state_dir()
    with open(STATE_FILE, "w", encoding="utf-8") as handle:
        json.dump(state, handle, ensure_ascii=False, indent=2)


def _state_key(next_payment: datetime, today: datetime) -> str:
    return (
        f"{next_payment.strftime('%Y-%m-%d')}:"
        f"{today.strftime('%Y-%m-%d')}"
    )


def reminder_already_sent(next_payment: datetime, today: datetime) -> bool:
    state = _load_state()
    return _state_key(next_payment, today) in state.get("sent", {})


def mark_reminder_sent(next_payment: datetime, today: datetime):
    state = _load_state()
    state.setdefault("sent", {})[_state_key(next_payment, today)] = datetime.now(TASHKENT_TZ).isoformat()
    _save_state(state)


def get_payment_reminder_days_left(now: Optional[datetime] = None) -> Optional[int]:
    """Return days left until payment when inside reminder window, else None."""
    now = now or datetime.now(TASHKENT_TZ)
    next_payment = next_invoice_date(now)
    days_left = days_until_next_payment(next_payment, now)
    if 0 <= days_left <= PAYMENT_REMINDER_DAYS:
        return days_left
    return None


def should_send_payment_reminder(now: Optional[datetime] = None) -> tuple[bool, Optional[int], Optional[datetime]]:
    """Check whether a reminder should be sent today."""
    now = now or datetime.now(TASHKENT_TZ)
    days_left = get_payment_reminder_days_left(now)
    if days_left is None:
        return False, None, None

    next_payment = next_invoice_date(now)
    if reminder_already_sent(next_payment, now):
        return False, days_left, next_payment

    return True, days_left, next_payment


def format_days_left_text(days_left: int) -> str:
    if days_left == 0:
        return "Bugun to'lov kuni!"
    return f"To'lov qilish sanasiga {days_left} kun qoldi!"


def format_payment_reminder_message(summary: dict[str, Any], days_left: int) -> str:
    """Reminder header plus the same billing block as /money."""
    from bot.digitalocean import format_billing_message

    header = f"⚠️ {format_days_left_text(days_left)}"
    return f"{header}\n\n{format_billing_message(summary, html=True)}"
