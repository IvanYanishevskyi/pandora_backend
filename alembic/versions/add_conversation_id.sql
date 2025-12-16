-- Migration: Add conversation_id to messages and favorite_questions tables
-- Date: 2025-12-11
-- Purpose: Correlate question-answer pairs with a unique ID

-- Add conversation_id to messages table
ALTER TABLE messages 
ADD COLUMN conversation_id VARCHAR(36) NULL AFTER sql_dialect,
ADD INDEX idx_messages_conversation_id (conversation_id);

-- Add conversation_id to favorite_questions table  
ALTER TABLE favorite_questions
ADD COLUMN conversation_id VARCHAR(36) NULL AFTER last_used_at,
ADD INDEX idx_favorites_conversation_id (conversation_id);

-- Optional: Create a helper function comment
-- conversation_id should be a UUID (generated client-side or server-side)
-- Example: '550e8400-e29b-41d4-a716-446655440000'
-- 
-- Usage:
-- 1. When user asks a question, generate UUID: conv_id = uuid4()
-- 2. Store user message with conversation_id = conv_id
-- 3. Store bot/assistant message with same conversation_id = conv_id
-- 4. When adding to favorites, use the same conversation_id
--
-- This allows:
-- - Finding the answer for a question: SELECT * FROM messages WHERE conversation_id = 'xxx' AND role = 'bot'
-- - Finding related favorites: SELECT * FROM favorite_questions WHERE conversation_id = 'xxx'
-- - Updating favorites by conversation_id instead of individual IDs
