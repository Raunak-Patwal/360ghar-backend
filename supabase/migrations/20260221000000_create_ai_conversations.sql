-- AI Conversations for the in-app AI agent
-- Stores conversation sessions and messages (user, assistant, tool calls)

CREATE TABLE IF NOT EXISTS ai_conversations (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(200),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_ai_conversations_user ON ai_conversations (user_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS ai_conversation_messages (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER NOT NULL REFERENCES ai_conversations(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL,  -- user, assistant, tool_call, tool_result
    content TEXT,
    tool_name VARCHAR(100),
    tool_args JSONB,
    tool_result JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_ai_messages_conv ON ai_conversation_messages (conversation_id, created_at);

-- Auto-update updated_at on conversation when messages are inserted
CREATE OR REPLACE FUNCTION update_ai_conversation_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE ai_conversations SET updated_at = now() WHERE id = NEW.conversation_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_ai_message_update_conv_ts
    AFTER INSERT ON ai_conversation_messages
    FOR EACH ROW
    EXECUTE FUNCTION update_ai_conversation_timestamp();
