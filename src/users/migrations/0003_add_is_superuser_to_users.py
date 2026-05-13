# Add is_superuser column to users table
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0002_create_users_table'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'users' AND column_name = 'is_superuser'
                    ) THEN
                        ALTER TABLE users ADD COLUMN is_superuser BOOLEAN NOT NULL DEFAULT FALSE;
                    END IF;
                END $$;

                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_name = 'admins'
                    ) THEN
                        UPDATE users
                        SET is_superuser = TRUE
                        WHERE id IN (SELECT id FROM admins);
                    END IF;
                END $$;
            """,
            reverse_sql="""
                ALTER TABLE users DROP COLUMN IF EXISTS is_superuser;
            """,
        ),
    ]
