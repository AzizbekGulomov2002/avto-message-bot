"""International phone number normalization (E.164)."""
import re
from typing import Optional

# ITU E.164: up to 15 digits after country code
E164_MIN_DIGITS = 7
E164_MAX_DIGITS = 15

PHONE_FORMAT_ERROR = (
    "❌ Telefon raqam noto'g'ri formatda.\n\n"
    "Xalqaro formatda kiriting: + va davlat kodi bilan "
    "(masalan: +998901234567, +79001234567, +14155552671)."
)


def normalize_phone(raw: str) -> Optional[str]:
    """
    Normalize user input to E.164 (+<country><subscriber>).
    Returns None if the number is invalid.
    """
    if not raw or not str(raw).strip():
        return None

    phone = re.sub(r"[\s\-().]", "", str(raw).strip())
    if phone.startswith("00"):
        phone = "+" + phone[2:]
    elif not phone.startswith("+"):
        phone = "+" + phone.lstrip("0")

    if not phone.startswith("+"):
        return None

    digits = phone[1:]
    if not digits.isdigit():
        return None
    if digits[0] == "0":
        return None
    if not (E164_MIN_DIGITS <= len(digits) <= E164_MAX_DIGITS):
        return None

    return f"+{digits}"
