"""Users app configuration."""
from django.apps import AppConfig
from django.db import connection


class UsersConfig(AppConfig):
    """Users app config."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'users'
    
    def ready(self):
        """Import signals and models when app is ready."""
        import users.payments  # Register UserPayment admin
        
        # Ensure users table exists on startup
        self._ensure_users_table()
    
    def _ensure_users_table(self):
        """Ensure users table exists in database."""
        try:
            with connection.cursor() as cursor:
                # Check if users table exists
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'users'
                    );
                """)
                exists = cursor.fetchone()[0]
                
                if not exists:
                    # Create users table if it doesn't exist
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS users (
                            id BIGINT NOT NULL PRIMARY KEY,
                            auth INTEGER DEFAULT 0,
                            status INTEGER DEFAULT 0,
                            full_name VARCHAR(200),
                            active_until TIMESTAMPTZ
                        );
                    """)
                    connection.commit()
        except Exception as e:
            # Log error but don't crash the app
            print(f"Warning: Could not ensure users table exists: {e}")

