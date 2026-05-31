"""DigitalOcean billing API helpers."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

import pytz
import requests

DO_API_BASE = "https://api.digitalocean.com/v2"
TASHKENT_TZ = pytz.timezone("Asia/Tashkent")
REQUEST_TIMEOUT_SECONDS = 20


class DigitalOceanAPIError(Exception):
    """Raised when the DigitalOcean API returns an error."""


def _do_get(token: str, path: str) -> dict[str, Any]:
    response = requests.get(
        f"{DO_API_BASE}{path}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    if response.status_code == 401:
        raise DigitalOceanAPIError("DigitalOcean token noto'g'ri yoki muddati tugagan.")
    if not response.ok:
        raise DigitalOceanAPIError(
            f"DigitalOcean API xatosi ({response.status_code}): {response.text[:200]}"
        )
    return response.json()


def _format_usd(value: Optional[str]) -> str:
    if value is None or value == "":
        return "—"
    try:
        amount = float(value)
    except (TypeError, ValueError):
        return f"${value}"
    return f"${amount:,.2f}"


def next_invoice_date(now: Optional[datetime] = None) -> datetime:
    """DigitalOcean invoices are issued on the 1st of each month."""
    now = now or datetime.now(TASHKENT_TZ)
    if now.month == 12:
        return now.replace(year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    return now.replace(month=now.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)


def days_until_next_payment(next_payment: datetime, now: Optional[datetime] = None) -> int:
    now = now or datetime.now(TASHKENT_TZ)
    return (next_payment.date() - now.date()).days


def _parse_generated_at(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(TASHKENT_TZ)
    except ValueError:
        return None


def fetch_billing_summary(token: str) -> dict[str, Any]:
    """Fetch balance from DigitalOcean."""
    balance = _do_get(token, "/customers/my/balance")

    generated_at = _parse_generated_at(balance.get("generated_at"))
    reference_time = generated_at or datetime.now(TASHKENT_TZ)
    next_payment_at = next_invoice_date(reference_time)

    return {
        "month_to_date_balance": balance.get("month_to_date_balance"),
        "generated_at": generated_at,
        "next_payment_at": next_payment_at,
    }


def _format_days_left_text(days_left: int, html: bool = True) -> str:
    if days_left == 0:
        text = "Bugun"
    else:
        text = f"{days_left} kun"
    if html:
        return f"<b>{text}</b>"
    return text


def format_billing_message(summary: dict[str, Any], html: bool = True) -> str:
    """Format billing data for Telegram."""
    generated_at = summary.get("generated_at")
    generated_text = generated_at.strftime("%Y-%m-%d %H:%M") if generated_at else "—"
    next_payment_at = summary.get("next_payment_at")
    next_payment_text = next_payment_at.strftime("%Y-%m-%d") if next_payment_at else "—"
    balance_text = _format_usd(summary.get("month_to_date_balance"))

    if html:
        balance_text = f"<b>{balance_text}</b>"
        next_payment_text = f"<b>{next_payment_text}</b>"

    lines = [
        "💰 DigitalOcean balansi",
        "",
        f"Hozirgi jami balans: {balance_text}",
        f"Keyingi to'lov sanasi: {next_payment_text}",
    ]

    if next_payment_at:
        days_left = days_until_next_payment(next_payment_at, datetime.now(TASHKENT_TZ))
        lines.append(f"Qoldi: {_format_days_left_text(days_left, html=html)}")

    lines.extend([
        "",
        f"Yangilangan: {generated_text} (Toshkent)",
    ])
    return "\n".join(lines)
