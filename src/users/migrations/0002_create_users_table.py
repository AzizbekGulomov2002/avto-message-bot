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
                    active_until TIMESTAMPTZ
                );
            """,
            reverse_sql="-- Cannot reverse table creation for managed=False model",
        ),
    ]

