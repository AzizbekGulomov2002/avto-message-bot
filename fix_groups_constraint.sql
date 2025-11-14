-- Fix groups table foreign key constraint to allow CASCADE delete
-- This will allow deleting users even if they have groups

-- Drop existing constraint
ALTER TABLE groups DROP CONSTRAINT IF EXISTS groups_user_id_fkey;

-- Add new constraint with ON DELETE CASCADE
ALTER TABLE groups 
ADD CONSTRAINT groups_user_id_fkey 
FOREIGN KEY (user_id) 
REFERENCES users(id) 
ON DELETE CASCADE;

-- Fix messages table foreign key constraint to allow CASCADE delete
-- This will allow deleting users even if they have messages

-- Drop existing constraint
ALTER TABLE messages DROP CONSTRAINT IF EXISTS messages_user_id_fkey;

-- Add new constraint with ON DELETE CASCADE
ALTER TABLE messages 
ADD CONSTRAINT messages_user_id_fkey 
FOREIGN KEY (user_id) 
REFERENCES users(id) 
ON DELETE CASCADE;

