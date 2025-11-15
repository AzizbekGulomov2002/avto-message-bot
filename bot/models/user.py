"""User models."""
from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass
class User:
    """User model."""
    id: int
    auth: int = 0
    status: int = 0
    full_name: Optional[str] = None
    active_until: Optional[datetime] = None


@dataclass
class UserGroup:
    """User group model."""
    id: str
    user_id: int
    user_name: Optional[str] = None
    name: Optional[str] = None

