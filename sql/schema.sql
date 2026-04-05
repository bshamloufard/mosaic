-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================
-- USERS: Keyed by phone number (how Linq identifies senders)
-- ============================================================
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phone_number TEXT UNIQUE NOT NULL,          -- E.164 format: +14155551234
    display_name TEXT,                          -- User's preferred name
    timezone TEXT DEFAULT 'America/Los_Angeles',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    onboarding_complete BOOLEAN DEFAULT FALSE
);

-- ============================================================
-- LINKED_ACCOUNTS: Google OAuth tokens (encrypted at rest by Supabase)
-- ============================================================
CREATE TABLE linked_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    provider TEXT NOT NULL DEFAULT 'google',     -- Always 'google' for now
    email TEXT NOT NULL,                         -- Google account email
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    token_expiry TIMESTAMPTZ NOT NULL,
    scopes TEXT[] NOT NULL,                      -- Array of granted scopes
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, provider)
);

-- ============================================================
-- CONVERSATIONS: One active conversation per user
-- ============================================================
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    linq_chat_id TEXT,                           -- Linq's chat ID
    summary TEXT,                                -- Rolling summary of older messages
    summary_token_count INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id)
);

-- ============================================================
-- MESSAGES: Full message history for conversation context
-- ============================================================
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    token_count INT,                             -- Estimated tokens for this message
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_messages_conversation_created
    ON messages(conversation_id, created_at DESC);

-- ============================================================
-- PENDING_ACTIONS: Human-in-the-loop confirmation queue
-- ============================================================
CREATE TABLE pending_actions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    action_type TEXT NOT NULL,
    -- Types: 'create_event', 'update_event', 'delete_event',
    --        'send_email', 'send_availability', 'create_event_series'
    action_payload JSONB NOT NULL,               -- Full details of proposed action
    options JSONB,                               -- Array of options if presenting choices
    status TEXT DEFAULT 'pending'
        CHECK (status IN ('pending', 'confirmed', 'cancelled', 'expired', 'executed')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ DEFAULT NOW() + INTERVAL '2 hours'
);

CREATE INDEX idx_pending_actions_conversation_status
    ON pending_actions(conversation_id, status)
    WHERE status = 'pending';

-- ============================================================
-- CONTACTS_CACHE: Cached Google Contacts for fast name resolution
-- ============================================================
CREATE TABLE contacts_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    display_name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    source TEXT DEFAULT 'google_contacts',       -- 'google_contacts', 'manual', 'email_history'
    last_synced_at TIMESTAMPTZ DEFAULT NOW(),
    interaction_count INT DEFAULT 0,             -- Tracks how often this contact is referenced
    UNIQUE(user_id, email)                       -- Required for upsert on_conflict
);

CREATE INDEX idx_contacts_cache_user_name
    ON contacts_cache(user_id, display_name);

CREATE INDEX idx_contacts_cache_user_email
    ON contacts_cache(user_id, email);

-- ============================================================
-- USER_PREFERENCES: Scheduling preferences
-- ============================================================
CREATE TABLE user_preferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    working_hours_start TIME DEFAULT '09:00',
    working_hours_end TIME DEFAULT '17:00',
    preferred_meeting_duration INT DEFAULT 30,    -- minutes
    buffer_between_meetings INT DEFAULT 15,       -- minutes
    preferred_gym_times TEXT[] DEFAULT ARRAY['06:00-08:00', '17:00-20:00'],
    weekend_available BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id)
);

-- ============================================================
-- POLLS: Multi-party availability polls
-- ============================================================
CREATE TABLE polls (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,                          -- e.g., "Pickleball this weekend"
    proposed_times JSONB NOT NULL,                -- Array of {start, end, label}
    participants JSONB NOT NULL,                  -- Array of {name, email, status}
    status TEXT DEFAULT 'open'
        CHECK (status IN ('open', 'closed', 'expired', 'booked')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ DEFAULT NOW() + INTERVAL '48 hours'
);

-- ============================================================
-- POLL_RESPONSES: Individual responses to polls
-- ============================================================
CREATE TABLE poll_responses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    poll_id UUID REFERENCES polls(id) ON DELETE CASCADE,
    respondent_email TEXT NOT NULL,
    respondent_name TEXT,
    selected_times JSONB NOT NULL,               -- Array of indices they selected
    message TEXT,                                 -- Optional free-text note
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(poll_id, respondent_email)
);

-- ============================================================
-- PROCESSED_WEBHOOKS: Idempotency tracking
-- ============================================================
CREATE TABLE processed_webhooks (
    message_id TEXT PRIMARY KEY,
    processed_at TIMESTAMPTZ DEFAULT NOW()
);

-- Auto-cleanup old webhook IDs (older than 24 hours)
-- Run this as a Supabase cron job or periodic task
-- DELETE FROM processed_webhooks WHERE processed_at < NOW() - INTERVAL '24 hours';
