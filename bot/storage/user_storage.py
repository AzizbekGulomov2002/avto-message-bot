"""User storage operations."""
from typing import Optional, List
from datetime import datetime
from bot.storage.database import Database
from bot.models.user import User, UserGroup


class UserStorage:
    """User storage operations."""
    
    def __init__(self, db: Database):
        """Initialize user storage."""
        self.db = db
    
    def insert_user(self, user_id: int) -> bool:
        """Insert a new user."""
        try:
            self.db.execute_query(
                "INSERT INTO users (id) VALUES (%s) ON CONFLICT (id) DO NOTHING",
                (user_id,)
            )
            return True
        except Exception as e:
            print(f"Error inserting user: {e}")
            return False
    
    def update_auth_status(self, user_id: int) -> bool:
        """Update user authentication status."""
        try:
            self.db.execute_query(
                "UPDATE users SET auth = 1 WHERE id = %s",
                (user_id,)
            )
            return True
        except Exception as e:
            print(f"Error updating auth status: {e}")
            return False
    
    def get_user(self, user_id: int) -> Optional[User]:
        """Get user by ID."""
        try:
            result = self.db.execute_query(
                "SELECT id, auth, status, full_name, phone, active_until FROM users WHERE id = %s",
                (user_id,),
                fetch_one=True
            )
            if result:
                return User(
                    id=result['id'],
                    auth=result['auth'],
                    status=result['status'],
                    full_name=result.get('full_name'),
                    phone=result.get('phone'),
                    active_until=result.get('active_until')
                )
            return None
        except Exception as e:
            print(f"Error getting user: {e}")
            return None
    
    def upsert_user_with_details(self, user_id: int, full_name: str, active_until: Optional[datetime] = None) -> bool:
        """Upsert user with details."""
        try:
            self.insert_user(user_id)
            if active_until:
                self.db.execute_query(
                    "UPDATE users SET full_name = %s, active_until = %s, status = 1 WHERE id = %s",
                    (full_name, active_until, user_id)
                )
            else:
                self.db.execute_query(
                    "UPDATE users SET full_name = %s, status = 1 WHERE id = %s",
                    (full_name, user_id)
                )
            return True
        except Exception as e:
            print(f"Error upserting user: {e}")
            return False
    
    def update_user_full_name(self, user_id: int, full_name: str) -> bool:
        """Update user full name."""
        try:
            self.db.execute_query(
                "UPDATE users SET full_name = %s WHERE id = %s",
                (full_name, user_id)
            )
            return True
        except Exception as e:
            print(f"Error updating full name: {e}")
            return False
    
    def update_user_phone(self, user_id: int, phone: str) -> bool:
        """Update user phone number."""
        try:
            self.db.execute_query(
                "UPDATE users SET phone = %s WHERE id = %s",
                (phone, user_id)
            )
            return True
        except Exception as e:
            print(f"Error updating phone: {e}")
            return False
    
    def update_user_active_until(self, user_id: int, active_until: Optional[datetime]) -> bool:
        """Update user active until date."""
        try:
            if active_until:
                self.db.execute_query(
                    "UPDATE users SET active_until = %s WHERE id = %s",
                    (active_until, user_id)
                )
            else:
                self.db.execute_query(
                    "UPDATE users SET active_until = NULL WHERE id = %s",
                    (user_id,)
                )
            return True
        except Exception as e:
            print(f"Error updating active until: {e}")
            return False
    
    def set_user_status(self, user_id: int, status: int) -> bool:
        """Set user status."""
        try:
            self.db.execute_query(
                "UPDATE users SET status = %s WHERE id = %s",
                (status, user_id)
            )
            return True
        except Exception as e:
            print(f"Error setting user status: {e}")
            return False
    
    def list_users_paged(self, limit: int, offset: int) -> List[dict]:
        """List users with pagination."""
        try:
            results = self.db.execute_query(
                "SELECT id, full_name, status, active_until FROM users WHERE status = 1 ORDER BY id ASC LIMIT %s OFFSET %s",
                (limit, offset),
                fetch_all=True
            )
            return [dict(row) for row in results] if results else []
        except Exception as e:
            print(f"Error listing users: {e}")
            return []
    
    def count_users(self) -> int:
        """Count active users."""
        try:
            result = self.db.execute_query(
                "SELECT COUNT(*) as count FROM users WHERE status = 1",
                fetch_one=True
            )
            return result['count'] if result else 0
        except Exception as e:
            print(f"Error counting users: {e}")
            return 0
    
    def count_users_by_query(self, query: str) -> int:
        """Count users matching query."""
        try:
            like = f"%{query}%"
            result = self.db.execute_query(
                "SELECT COUNT(*) as count FROM users WHERE CAST(id AS TEXT) ILIKE %s OR full_name ILIKE %s",
                (like, like),
                fetch_one=True
            )
            return result['count'] if result else 0
        except Exception as e:
            print(f"Error counting users by query: {e}")
            return 0
    
    def list_users_by_query(self, query: str, limit: int, offset: int) -> List[dict]:
        """List users matching query."""
        try:
            like = f"%{query}%"
            results = self.db.execute_query(
                "SELECT id, full_name, status, active_until FROM users WHERE CAST(id AS TEXT) ILIKE %s OR full_name ILIKE %s ORDER BY id DESC LIMIT %s OFFSET %s",
                (like, like, limit, offset),
                fetch_all=True
            )
            return [dict(row) for row in results] if results else []
        except Exception as e:
            print(f"Error listing users by query: {e}")
            return []
    
    def deactivate_expired_users(self) -> int:
        """Deactivate expired users."""
        try:
            count = self.db.execute_query(
                "UPDATE users SET status = 0 WHERE status = 1 AND active_until IS NOT NULL AND active_until < NOW()"
            )
            return count
        except Exception as e:
            print(f"Error deactivating expired users: {e}")
            return 0
    
    def list_users_to_deactivate(self) -> List[int]:
        """List user IDs to deactivate."""
        try:
            results = self.db.execute_query(
                "SELECT id FROM users WHERE status = 1 AND active_until IS NOT NULL AND active_until < NOW()",
                fetch_all=True
            )
            return [row['id'] for row in results] if results else []
        except Exception as e:
            print(f"Error listing users to deactivate: {e}")
            return []
    
    def deactivate_user(self, user_id: int) -> bool:
        """Deactivate a user."""
        try:
            self.db.execute_query(
                "UPDATE users SET status = 0, auth = 0 WHERE id = %s",
                (user_id,)
            )
            return True
        except Exception as e:
            print(f"Error deactivating user: {e}")
            return False
    
    def reset_auth_status(self, user_id: int) -> bool:
        """Reset user authentication status."""
        try:
            self.db.execute_query(
                "UPDATE users SET auth = 0 WHERE id = %s",
                (user_id,)
            )
            return True
        except Exception as e:
            print(f"Error resetting auth status: {e}")
            return False
    
    def set_user_auth(self, user_id: int, auth: int) -> bool:
        """Set user authentication status."""
        try:
            self.db.execute_query(
                "UPDATE users SET auth = %s WHERE id = %s",
                (auth, user_id)
            )
            return True
        except Exception as e:
            print(f"Error setting auth status: {e}")
            return False
    
    def get_superuser_ids(self) -> list[int]:
        """Get Telegram IDs that can approve user access."""
        try:
            results = self.db.execute_query(
                "SELECT id FROM users WHERE is_superuser = TRUE",
                fetch_all=True,
            ) or []
            return [row["id"] for row in results]
        except Exception as e:
            print(f"Error loading superuser ids: {e}")
            return []

    def is_admin(self, user_id: int) -> bool:
        """Check if user is admin."""
        return user_id in self.get_superuser_ids()

    def activate_user_until(self, user_id: int, active_until: datetime) -> bool:
        """Activate user until the given datetime."""
        try:
            self.db.execute_query(
                "UPDATE users SET status = 1, active_until = %s WHERE id = %s",
                (active_until, user_id)
            )
            return True
        except Exception as e:
            print(f"Error activating user: {e}")
            return False

