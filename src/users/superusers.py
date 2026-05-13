"""Helpers for resolving Telegram superuser IDs from the users table."""
from functools import lru_cache

from django.db import connection


def ensure_users_superuser_column() -> None:
    """Ensure the users table has an is_superuser column."""
    with connection.cursor() as cursor:
        cursor.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = 'users' AND column_name = 'is_superuser'
                ) THEN
                    ALTER TABLE users ADD COLUMN is_superuser BOOLEAN NOT NULL DEFAULT FALSE;
                END IF;
            END $$;
        """)


def clear_superuser_cache() -> None:
    """Clear cached superuser IDs."""
    get_superuser_ids.cache_clear()


@lru_cache(maxsize=1)
def get_superuser_ids() -> tuple[int, ...]:
    """Return Telegram IDs allowed to approve user access."""
    ensure_users_superuser_column()
    with connection.cursor() as cursor:
        cursor.execute("SELECT id FROM users WHERE is_superuser = TRUE")
        return tuple(row[0] for row in cursor.fetchall())


def is_superuser_id(user_id: int) -> bool:
    """Return whether the Telegram user is configured as a superuser."""
    ensure_users_superuser_column()
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT is_superuser FROM users WHERE id = %s",
            [user_id],
        )
        row = cursor.fetchone()
        return bool(row and row[0])
