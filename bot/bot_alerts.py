"""Runtime heartbeat and superadmin alert helpers."""
from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import pytz
import requests

from bot.config import Config
from bot.storage.database import Database
from bot.storage.user_storage import UserStorage

TASHKENT_TZ = pytz.timezone("Asia/Tashkent")
DATA_DIR = Path(__file__).resolve().parent / "data"
HEARTBEAT_FILE = DATA_DIR / "runtime_heartbeat.json"
WATCHDOG_STATE_FILE = DATA_DIR / "bot_watchdog_state.json"
HEARTBEAT_STALE_SECONDS = 180
CRASH_ALERT_COOLDOWN_SECONDS = 600
SYSTEMD_SERVICE_NAME = "avto-message-bot.service"


def _ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def write_runtime_heartbeat(
    polling: bool,
    queue_size: int,
    active_cycles: int,
    workers: int,
):
    _ensure_data_dir()
    payload = {
        "updated_at": datetime.now(TASHKENT_TZ).isoformat(),
        "polling": polling,
        "queue_size": queue_size,
        "active_cycles": active_cycles,
        "workers": workers,
    }
    with open(HEARTBEAT_FILE, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def read_runtime_heartbeat() -> Optional[dict[str, Any]]:
    if not HEARTBEAT_FILE.exists():
        return None
    try:
        with open(HEARTBEAT_FILE, encoding="utf-8") as handle:
            data = json.load(handle)
            if isinstance(data, dict):
                return data
    except (OSError, json.JSONDecodeError):
        pass
    return None


def heartbeat_age_seconds(heartbeat: Optional[dict[str, Any]]) -> Optional[float]:
    if not heartbeat or not heartbeat.get("updated_at"):
        return None
    try:
        updated_at = datetime.fromisoformat(str(heartbeat["updated_at"]))
        if updated_at.tzinfo is None:
            updated_at = TASHKENT_TZ.localize(updated_at)
        return (datetime.now(TASHKENT_TZ) - updated_at.astimezone(TASHKENT_TZ)).total_seconds()
    except ValueError:
        return None


def is_service_active(service_name: str = SYSTEMD_SERVICE_NAME) -> bool:
    try:
        result = subprocess.run(
            ["systemctl", "is-active", service_name],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        return result.stdout.strip() == "active"
    except Exception:
        return False


def load_watchdog_state() -> dict[str, Any]:
    _ensure_data_dir()
    if not WATCHDOG_STATE_FILE.exists():
        return {"down_alert_sent": False}
    try:
        with open(WATCHDOG_STATE_FILE, encoding="utf-8") as handle:
            data = json.load(handle)
            if isinstance(data, dict):
                return data
    except (OSError, json.JSONDecodeError):
        pass
    return {"down_alert_sent": False}


def save_watchdog_state(state: dict[str, Any]):
    _ensure_data_dir()
    with open(WATCHDOG_STATE_FILE, "w", encoding="utf-8") as handle:
        json.dump(state, handle, ensure_ascii=False, indent=2)


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
    return response.ok


def notify_superadmins(config: Config, text: str) -> int:
    if not config.BOT_TOKEN:
        return 0

    db = Database(config)
    db.connect()
    try:
        superusers = UserStorage(db).get_superuser_ids()
    finally:
        db.close()

    sent = 0
    for superuser_id in superusers:
        if send_telegram_message(config.BOT_TOKEN, superuser_id, text):
            sent += 1
    return sent


def evaluate_bot_health(
    heartbeat: Optional[dict[str, Any]],
    service_active: bool,
    stale_after_seconds: int = HEARTBEAT_STALE_SECONDS,
) -> tuple[bool, str]:
    age = heartbeat_age_seconds(heartbeat)
    if not service_active:
        return False, "Systemd servisi active holatda emas"

    if heartbeat is None:
        return False, "Heartbeat fayli topilmadi (bot ishga tushmagan yoki qotib qolgan)"

    if age is None:
        return False, "Heartbeat vaqti o'qib bo'lmadi"

    if age > stale_after_seconds:
        return False, f"Heartbeat {int(age)} soniyadan beri yangilanmagan"

    if not heartbeat.get("polling"):
        return False, "Telegram polling ishlamayapti"

    return True, "OK"


def format_down_alert(reason: str, heartbeat: Optional[dict[str, Any]]) -> str:
    age = heartbeat_age_seconds(heartbeat)
    age_text = f"{int(age)} soniya oldin" if age is not None else "noma'lum"
    queue_size = heartbeat.get("queue_size") if heartbeat else "—"
    workers = heartbeat.get("workers") if heartbeat else "—"
    return (
        "🚨 <b>Avto Message Bot to'xtab qoldi!</b>\n\n"
        f"Sabab: {reason}\n"
        f"Oxirgi heartbeat: {age_text}\n"
        f"Queue: {queue_size}\n"
        f"Workers: {workers}\n\n"
        "Serverda tekshiring:\n"
        "<code>systemctl status avto-message-bot.service</code>"
    )


def format_recovery_alert() -> str:
    return (
        "✅ <b>Avto Message Bot qayta ishlayapti</b>\n\n"
        "Heartbeat va polling tiklandi."
    )


def format_crash_alert() -> str:
    return (
        "🚨 <b>Avto Message Bot servisi quladi</b>\n\n"
        "Systemd servisni qayta ishga tushirmoqda.\n"
        "Agar xabar takrorlansa, loglarni tekshiring:\n"
        "<code>journalctl -u avto-message-bot.service -n 100</code>"
    )


def should_send_crash_alert(state: dict[str, Any]) -> bool:
    last_sent = state.get("last_crash_alert_at")
    if not last_sent:
        return True
    try:
        sent_at = datetime.fromisoformat(str(last_sent))
        if sent_at.tzinfo is None:
            sent_at = TASHKENT_TZ.localize(sent_at)
        elapsed = (datetime.now(TASHKENT_TZ) - sent_at.astimezone(TASHKENT_TZ)).total_seconds()
        return elapsed >= CRASH_ALERT_COOLDOWN_SECONDS
    except ValueError:
        return True
