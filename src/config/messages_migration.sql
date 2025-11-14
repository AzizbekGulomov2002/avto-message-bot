-- Add message_time and duration_time columns to scheduled_messages table
ALTER TABLE scheduled_messages 
ADD COLUMN IF NOT EXISTS message_time VARCHAR(200) NULL,
ADD COLUMN IF NOT EXISTS duration_time VARCHAR(200) NULL;

-- Add comments
COMMENT ON COLUMN scheduled_messages.message_time IS 'Dynamic message time display (e.g., "5 daqiqa", "Har 10 minutda")';
COMMENT ON COLUMN scheduled_messages.duration_time IS 'Dynamic duration time display (e.g., "2025-11-08 12:55:02")';

