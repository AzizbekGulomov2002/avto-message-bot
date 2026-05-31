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


def _next_invoice_date(now: Optional[datetime] = None) -> datetime:
    """DigitalOcean invoices are issued on the 1st of each month."""
    now = now or datetime.now(TASHKENT_TZ)
    if now.month == 12:
        return now.replace(year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    return now.replace(month=now.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)


def _parse_generated_at(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(TASHKENT_TZ)
    except ValueError:
        return None


def fetch_billing_summary(token: str) -> dict[str, Any]:
    """Fetch balance and invoice preview from DigitalOcean."""
    balance = _do_get(token, "/customers/my/balance")
    invoices = _do_get(token, "/customers/my/invoices?per_page=1")

    generated_at = _parse_generated_at(balance.get("generated_at"))
    invoice_preview = invoices.get("invoice_preview") or {}
    next_payment_at = _next_invoice_date(generated_at or datetime.now(TASHKENT_TZ))

    return {
        "account_balance": balance.get("account_balance"),
        "month_to_date_balance": balance.get("month_to_date_balance"),
        "month_to_date_usage": balance.get("month_to_date_usage"),
        "generated_at": generated_at,
        "invoice_preview_amount": invoice_preview.get("amount"),
        "invoice_period": invoice_preview.get("invoice_period"),
        "next_payment_at": next_payment_at,
    }


def format_billing_message(summary: dict[str, Any]) -> str:
    """Format billing data for Telegram."""
    generated_at = summary.get("generated_at")
    generated_text = generated_at.strftime("%Y-%m-%d %H:%M") if generated_at else "—"
    next_payment_at = summary.get("next_payment_at")
    next_payment_text = next_payment_at.strftime("%Y-%m-%d") if next_payment_at else "—"
    invoice_period = summary.get("invoice_period") or "—"

    lines = [
        "💰 DigitalOcean balansi",
        "",
        f"Hisob balansi: {_format_usd(summary.get('account_balance'))}",
        f"Shu oy sarfi: {_format_usd(summary.get('month_to_date_usage'))}",
        f"Joriy jami balans: {_format_usd(summary.get('month_to_date_balance'))}",
        "",
        f"Keyingi to'lov sanasi: {next_payment_text}",
        f"Invoice preview: {_format_usd(summary.get('invoice_preview_amount'))}",
        f"Invoice davri: {invoice_period}",
        "",
        f"Yangilangan: {generated_text} (Toshkent)",
    ]
    return "\n".join(lines)
