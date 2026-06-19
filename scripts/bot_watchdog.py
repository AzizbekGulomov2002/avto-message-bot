#!/usr/bin/env python3
"""Check bot heartbeat and alert superadmins if the bot stopped responding.

Cron (har 3 daqiqa):
*/3 * * * * cd /home/avto-message-bot && ./env/bin/python scripts/bot_watchdog.py >> logs/bot_watchdog.log 2>&1

Yoki systemd timer:
sudo cp deploy/systemd/avto-message-bot-watchdog.* /etc/systemd/system/
sudo systemctl enable --now avto-message-bot-watchdog.timer
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pytz

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from bot.bot_alerts import (
    TASHKENT_TZ,
    evaluate_bot_health,
    format_down_alert,
    format_recovery_alert,
    is_service_active,
    load_watchdog_state,
    notify_superadmins,
    read_runtime_heartbeat,
    restart_service,
    save_watchdog_state,
)
from bot.config import Config

# Avtomatik restartlar orasidagi minimal interval (restart-loop oldini olish).
RESTART_COOLDOWN_SECONDS = 300


def main() -> int:
    config = Config()
    if not config.BOT_TOKEN:
        print("BOT_TOKEN is not configured.")
        return 1

    heartbeat = read_runtime_heartbeat()
    service_active = is_service_active()
    healthy, reason = evaluate_bot_health(heartbeat, service_active)
    state = load_watchdog_state()
    now = datetime.now(TASHKENT_TZ).isoformat()

    if not healthy:
        if not state.get("down_alert_sent"):
            message = format_down_alert(reason, heartbeat)
            sent = notify_superadmins(config, message)
            state["down_alert_sent"] = True
            state["last_down_alert_at"] = now
            state["last_down_reason"] = reason
            save_watchdog_state(state)
            print(f"Down alert sent to {sent} superadmin(s): {reason}")
        else:
            print(f"Bot still unhealthy, alert already sent: {reason}")

        # O'z-o'zini davolash: osilib qolgan botni avtomatik restart qilamiz,
        # lekin cooldown ichida takror restart qilmaymiz (restart-loop himoyasi).
        last_restart_at = state.get("last_auto_restart_at")
        can_restart = True
        if last_restart_at:
            try:
                elapsed = (
                    datetime.now(TASHKENT_TZ)
                    - datetime.fromisoformat(last_restart_at)
                ).total_seconds()
                can_restart = elapsed >= RESTART_COOLDOWN_SECONDS
            except ValueError:
                can_restart = True

        if can_restart:
            restarted = restart_service()
            state["last_auto_restart_at"] = now
            save_watchdog_state(state)
            print(f"Auto-restart {'succeeded' if restarted else 'FAILED'}: {reason}")
        else:
            print("Auto-restart skipped (within cooldown window).")
        return 0

    if state.get("down_alert_sent"):
        sent = notify_superadmins(config, format_recovery_alert())
        state["down_alert_sent"] = False
        state["last_recovery_at"] = now
        save_watchdog_state(state)
        print(f"Recovery alert sent to {sent} superadmin(s)")
        return 0

    print("Bot is healthy.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
