#!/bin/bash
# Script to run the schedule intervals migration

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Default values
DB_NAME=${POSTGRES_DB:-tgbot}
DB_USER=${POSTGRES_USER:-godb}
DB_PASSWORD=${POSTGRES_PASSWORD:-0208}
DB_HOST=${POSTGRES_HOST:-localhost}
DB_PORT=${POSTGRES_PORT:-5432}

echo "Running migration for schedule_intervals and duration_options tables..."
echo "Database: $DB_NAME on $DB_HOST:$DB_PORT"

# Run the migration
PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -f src/config/schedule_intervals_migration.sql

if [ $? -eq 0 ]; then
    echo "✅ Migration completed successfully!"
else
    echo "❌ Migration failed. Please check the error above."
    exit 1
fi

