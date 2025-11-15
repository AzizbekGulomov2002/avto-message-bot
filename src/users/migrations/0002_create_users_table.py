# Migration to ensure users table exists
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0001_initial'),
    ]

    operations = [
        # Create users table if it doesn't exist
        migrations.RunSQL(
            sql="""
                CREATE TABLE IF NOT EXISTS users (
                    id BIGINT NOT NULL PRIMARY KEY,
                    auth INTEGER DEFAULT 0,
                    status INTEGER DEFAULT 0,
                    full_name VARCHAR(200),
                    phone VARCHAR(20),
                    active_until TIMESTAMPTZ
                );
                
                -- Add phone column if it doesn't exist
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name = 'users' AND column_name = 'phone'
                    ) THEN
                        ALTER TABLE users ADD COLUMN phone VARCHAR(20);
                    END IF;
                END $$;
            """,
            reverse_sql="-- Cannot reverse table creation for managed=False model",
        ),
    ]

