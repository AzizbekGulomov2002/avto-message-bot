"""User state management."""
import threading
from dataclasses import dataclass, field
from typing import Dict, Optional


@dataclass
class UserState:
    """User state for bot interaction."""
    step: str = ""
    phone: str = ""
    code: Optional[str] = None
    password: Optional[str] = None
    phone_code_hash: Optional[str] = None
    selected_groups: Dict[int, bool] = field(default_factory=dict)
    pending_message: str = ""
    groups_page: int = 1
    selected_interval_id: Optional[int] = None
    selected_duration_id: Optional[int] = None
    admin_target_id: Optional[int] = None
    admin_pending_name: str = ""
    admin_pending_phone: Optional[str] = None


class UserStateManager:
    """Manages user states."""
    
    def __init__(self):
        """Initialize state manager."""
        self._states: Dict[int, UserState] = {}
        self._lock = threading.RLock()
    
    def get_state(self, user_id: int) -> UserState:
        """Get user state, creating if not exists."""
        with self._lock:
            if user_id not in self._states:
                self._states[user_id] = UserState()
            return self._states[user_id]
    
    def set_state(self, user_id: int, state: UserState):
        """Set user state."""
        with self._lock:
            self._states[user_id] = state
    
    def delete_state(self, user_id: int):
        """Delete user state."""
        with self._lock:
            if user_id in self._states:
                del self._states[user_id]

