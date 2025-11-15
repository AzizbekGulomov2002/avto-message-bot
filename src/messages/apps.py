"""Messages app configuration."""
from django.apps import AppConfig
from django.db import connection


class MessagesConfig(AppConfig):
    """Messages app config."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'messages'
    label = 'bot_messages'
    
    def ready(self):
        """Ensure required tables exist on startup."""
        self._ensure_tables_exist()
    
    def _ensure_tables_exist(self):
        """Ensure schedule_intervals and duration_options tables exist."""
        try:
            with connection.cursor() as cursor:
                # Check and create schedule_intervals table
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'schedule_intervals'
                    );
                """)
                exists = cursor.fetchone()[0]
                
                if not exists:
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS schedule_intervals (
                            id SERIAL PRIMARY KEY,
                            time DOUBLE PRECISION NOT NULL,
                            time_type VARCHAR(20) NOT NULL DEFAULT 'minut',
                            display_order INTEGER NOT NULL DEFAULT 0,
                            is_active BOOLEAN NOT NULL DEFAULT TRUE,
                            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                        );
                    """)
                
                # Check and create duration_options table
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'duration_options'
                    );
                """)
                exists = cursor.fetchone()[0]
                
                if not exists:
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS duration_options (
                            id SERIAL PRIMARY KEY,
                            time DOUBLE PRECISION NOT NULL,
                            time_type VARCHAR(20) NOT NULL DEFAULT 'soat',
                            display_order INTEGER NOT NULL DEFAULT 0,
                            is_active BOOLEAN NOT NULL DEFAULT TRUE,
                            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                        );
                    """)
                
                connection.commit()
        except Exception as e:
            # Log error but don't crash the app
            print(f"Warning: Could not ensure messages tables exist: {e}")

