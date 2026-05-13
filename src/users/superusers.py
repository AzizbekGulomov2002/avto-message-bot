"""Helpers for resolving Telegram superuser IDs."""
import os
from functools import lru_cache

from django.db import connection


def _parse_env_superuser_ids() -> list[int]:
    superuser_ids: list[int] = []
    for value in os.getenv("SUPERUSER_IDS", "").split(","):
        value = value.strip()
        if value.isdigit():
            superuser_ids.append(int(value))
    return superuser_ids


def _fetch_admin_table_ids() -> list[int]:
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'admins'
                );
            """)
            if not cursor.fetchone()[0]:
                return []

            cursor.execute("SELECT id FROM admins")
            return [row[0] for row in cursor.fetchall()]
    except Exception:
        return []


@lru_cache(maxsize=1)
def get_superuser_ids() -> tuple[int, ...]:
    """Return Telegram IDs allowed to approve user access."""
    env_ids = _parse_env_superuser_ids()
    if env_ids:
        return tuple(sorted(set(env_ids)))
    return tuple(sorted(set(_fetch_admin_table_ids())))


def is_superuser_id(user_id: int) -> bool:
    """Return whether the Telegram user is configured as a superuser."""
    return user_id in get_superuser_ids()
