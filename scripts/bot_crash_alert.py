#!/usr/bin/env python3
"""Send alert when systemd reports avto-message-bot.service failure.

Used by OnFailure= in the systemd unit.
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
    format_crash_alert,
    load_watchdog_state,
    notify_superadmins,
    save_watchdog_state,
    should_send_crash_alert,
)
from bot.config import Config


def main() -> int:
    config = Config()
    if not config.BOT_TOKEN:
        print("BOT_TOKEN is not configured.")
        return 1

    state = load_watchdog_state()
    if not should_send_crash_alert(state):
        print("Crash alert skipped due to cooldown.")
        return 0

    sent = notify_superadmins(config, format_crash_alert())
    state["down_alert_sent"] = True
    state["last_crash_alert_at"] = datetime.now(TASHKENT_TZ).isoformat()
    save_watchdog_state(state)
    print(f"Crash alert sent to {sent} superadmin(s)")
    return 0 if sent else 1


if __name__ == "__main__":
    raise SystemExit(main())
