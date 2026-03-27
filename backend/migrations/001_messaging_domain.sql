-- Additive schema for messaging / WhatsApp (run manually if not using SQLAlchemy create_all).
-- TODO: Align with Alembic if you introduce migrations later.

CREATE TYPE conversationtype AS ENUM ('direct', 'group', 'workflow_linked');
CREATE TYPE conversationstatus AS ENUM ('open', 'archived', 'closed');
CREATE TYPE participanttype AS ENUM ('user', 'agent', 'system', 'external');
CREATE TYPE messagesendertype AS ENUM ('user', 'agent', 'system', 'external');
CREATE TYPE messagedirection AS ENUM ('inbound', 'outbound', 'internal');
CREATE TYPE messagechannel AS ENUM ('web', 'whatsapp', 'system');
CREATE TYPE messageprovider AS ENUM ('twilio', 'meta', 'none');
CREATE TYPE deliverystatus AS ENUM ('queued', 'sent', 'delivered', 'read', 'failed');
CREATE TYPE channelkind AS ENUM ('whatsapp');

CREATE TABLE conversations (
    id SERIAL PRIMARY KEY,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
    type conversationtype NOT NULL,
    title VARCHAR(512),
    status conversationstatus NOT NULL,
    linked_workflow_run_id INTEGER REFERENCES workflow_runs(id),
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL
);
CREATE INDEX ix_conversations_workspace_id ON conversations(workspace_id);

CREATE TABLE conversation_participants (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id),
    participant_type participanttype NOT NULL,
    participant_id INTEGER,
    external_address VARCHAR(512),
    role VARCHAR(128)
);
CREATE INDEX ix_conversation_participants_conversation_id ON conversation_participants(conversation_id);

CREATE TABLE messages (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id),
    sender_type messagesendertype NOT NULL,
    sender_id INTEGER,
    external_sender_address VARCHAR(512),
    body_text TEXT NOT NULL,
    body_structured JSON,
    direction messagedirection NOT NULL,
    channel messagechannel NOT NULL,
    provider messageprovider NOT NULL,
    provider_message_id VARCHAR(255),
    reply_to_message_id INTEGER REFERENCES messages(id),
    delivery_status deliverystatus,
    created_at TIMESTAMP NOT NULL,
    CONSTRAINT uq_message_provider_msg_id UNIQUE (provider, provider_message_id)
);
CREATE INDEX ix_messages_conversation_id ON messages(conversation_id);

CREATE TABLE channel_bindings (
    id SERIAL PRIMARY KEY,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
    channel channelkind NOT NULL,
    provider messageprovider NOT NULL,
    external_user_address VARCHAR(512) NOT NULL,
    conversation_id INTEGER NOT NULL REFERENCES conversations(id),
    agent_id INTEGER REFERENCES agents(id),
    metadata JSON NOT NULL DEFAULT '{}',
    last_inbound_at TIMESTAMP,
    last_outbound_at TIMESTAMP,
    CONSTRAINT uq_channel_binding_workspace_provider_address UNIQUE (workspace_id, provider, external_user_address)
);
CREATE INDEX ix_channel_bindings_workspace_id ON channel_bindings(workspace_id);

CREATE TABLE status_callback_dedupe (
    id SERIAL PRIMARY KEY,
    provider messageprovider NOT NULL,
    dedupe_key VARCHAR(512) NOT NULL UNIQUE,
    created_at TIMESTAMP NOT NULL
);
CREATE INDEX ix_status_callback_dedupe_provider ON status_callback_dedupe(provider);
