#!/bin/bash
# Database setup script - Create users table and run migrations

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Default values
DB_NAME=${POSTGRES_DB:-taxi}
DB_USER=${POSTGRES_USER:-taxi}
DB_PASSWORD=${POSTGRES_PASSWORD:-taxi}
DB_HOST=${POSTGRES_HOST:-localhost}
DB_PORT=${POSTGRES_PORT:-5432}

echo "Setting up database: $DB_NAME on $DB_HOST:$DB_PORT"

# Create users table if it doesn't exist
echo "Creating users table..."
PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME <<EOF
CREATE TABLE IF NOT EXISTS users (
    id BIGINT NOT NULL PRIMARY KEY,
    auth INTEGER DEFAULT 0,
    status INTEGER DEFAULT 0,
    full_name VARCHAR(200),
    active_until TIMESTAMPTZ
);
EOF

if [ $? -eq 0 ]; then
    echo "✅ Users table created/verified successfully!"
else
    echo "❌ Failed to create users table. Please check the error above."
    exit 1
fi

# Run Django migrations
echo "Running Django migrations..."
cd src/config
python3 manage.py migrate

if [ $? -eq 0 ]; then
    echo "✅ Database setup completed successfully!"
else
    echo "❌ Migration failed. Please check the error above."
    exit 1
fi

