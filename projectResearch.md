# PLAN.md — iMessage AI Scheduling Secretary ("ScheduleGPT")

> **This document is the complete implementation blueprint.** An LLM reading this file should be able to build the entire application without asking any clarifying questions. Every design decision has been made. Every API endpoint is specified. Every file path is defined.

---

## TABLE OF CONTENTS

1. [Project Overview](#1-project-overview)
2. [Architecture Diagram](#2-architecture-diagram)
3. [Technology Stack (Final Decisions)](#3-technology-stack)
4. [Repository Structure](#4-repository-structure)
5. [Environment Variables](#5-environment-variables)
6. [Database Schema (Supabase PostgreSQL)](#6-database-schema)
7. [Google OAuth2 Setup & Token Management](#7-google-oauth2)
8. [Google People API — Contact Resolution](#8-contact-resolution)
9. [Google Calendar API — All Operations](#9-google-calendar-api)
10. [Gmail API — Email Operations](#10-gmail-api)
11. [Linq iMessage API — Full Integration](#11-linq-imessage-api)
12. [The Agent Brain — Claude Tool-Calling Loop](#12-agent-brain)
13. [Tool Definitions (All 9 Tools)](#13-tool-definitions)
14. [System Prompt (Complete)](#14-system-prompt)
15. [Smart Time Engine](#15-smart-time-engine)
16. [Conversation Memory Management](#16-conversation-memory)
17. [Async Webhook Processing](#17-async-processing)
18. [Multi-Party Scheduling Flow](#18-multi-party-scheduling)
19. [Workout/Itinerary Plan Generation](#19-structured-content)
20. [Onboarding Flow (New User)](#20-onboarding-flow)
21. [Simple Web Dashboard (Google OAuth + Polling Page)](#21-web-dashboard)
22. [Deployment to Railway](#22-deployment)
23. [Open Source Configuration](#23-open-source)
24. [Testing Strategy](#24-testing)
25. [File-by-File Implementation Guide](#25-file-by-file)

---

## 1. PROJECT OVERVIEW <a name="1-project-overview"></a>

**What it is:** A 24/7 AI scheduling secretary you control entirely via iMessage. You text it natural language commands and it manages your Google Calendar, sends emails on your behalf, coordinates with other people, and creates structured plans (gym routines, meal plans, itineraries) — all without you ever opening a browser.

**Open source model:** The entire codebase is open source. Users bring their own:
- Linq API key (for iMessage — free sandbox available)
- Google Cloud project (for Calendar, Gmail, Contacts — free tier)
- Anthropic API key (for Claude — $5 free credits on signup)

Everything else (Railway deployment, Supabase database) is either free-tier or under $10/month.

**Core user flows:**
1. **Reschedule:** "My 2pm got cancelled, move it to Thursday" → checks Thursday availability → confirms → updates event
2. **Group schedule:** "Schedule pickleball with Bharat, Tej, and Adil this weekend" → resolves contacts → checks all calendars (or emails for availability) → finds best time → creates event with invites
3. **Structured plans:** "Create me a 5-day gym plan" → reads calendar → finds 5 open slots → generates workout descriptions → creates 5 events
4. **Email coordination:** "Find a time to meet with sarah@company.com next week" → checks your calendar → sends email with your available times → reads their reply → books the meeting
5. **Modify/Delete:** "Cancel my gym session tomorrow" or "Move Friday's meeting to 4pm" → executes with confirmation

---

## 2. ARCHITECTURE DIAGRAM <a name="2-architecture-diagram"></a>

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────────────────┐
│  User's     │────▶│   Linq API       │────▶│  FastAPI Server (Railway)   │
│  iMessage   │◀────│  (webhook POST)  │◀────│                             │
│  App        │     └──────────────────┘     │  POST /webhook/linq         │
└─────────────┘                              │    ├─ verify HMAC signature │
                                             │    ├─ deduplicate message   │
                                             │    ├─ send typing indicator │
                                             │    └─ background_task:      │
                                             │         process_message()   │
                                             │                             │
                                             │  process_message():         │
                                             │    1. Load user from DB     │
                                             │    2. Load conversation     │
                                             │    3. Assemble context      │
                                             │    4. Run agent loop        │
                                             │    5. Send reply via Linq   │
                                             │    6. Save to DB            │
                                             └──────────┬──────────────────┘
                                                        │
                              ┌──────────────────────────┼──────────────────┐
                              │                          │                  │
                     ┌────────▼────────┐    ┌────────────▼───┐   ┌─────────▼──────┐
                     │  Claude API     │    │  Google APIs   │   │  Supabase      │
                     │  (Sonnet 4.5)   │    │  - Calendar    │   │  - PostgreSQL  │
                     │                 │    │  - Gmail       │   │  - users       │
                     │  Tool-calling   │    │  - People      │   │  - messages    │
                     │  agent loop     │    │  (OAuth2)      │   │  - pending_    │
                     │  (max 15 iter)  │    │                │   │    actions     │
                     └─────────────────┘    └────────────────┘   └────────────────┘

                                             ┌────────────────────────────────┐
                                             │  Web Routes (same FastAPI)     │
                                             │  GET  /auth/google            │
                                             │  GET  /auth/google/callback   │
                                             │  GET  /poll/{poll_id}         │
                                             │  POST /poll/{poll_id}/respond │
                                             └────────────────────────────────┘
```

---

## 3. TECHNOLOGY STACK <a name="3-technology-stack"></a>

| Component | Choice | Version | Why (non-negotiable) |
|-----------|--------|---------|---------------------|
| Language | **Python** | 3.11+ | Best AI/Google SDK ecosystem |
| Framework | **FastAPI** | 0.115+ | Async, Pydantic, BackgroundTasks |
| LLM | **Claude Sonnet 4.5** | `claude-sonnet-4-5-20241022` | Best tool-calling accuracy, prompt caching |
| LLM (routing) | **Claude Haiku 4.5** | `claude-haiku-4-5-20241022` | Fast intent classification ($0.25/$1.25 per M tokens) |
| iMessage | **Linq Partner API V3** | `api.linqapp.com/api/partner/v3` | Free sandbox, webhook-driven, iMessage native |
| Calendar | **Google Calendar API** | v3 | FreeBusy, events, invites |
| Email | **Gmail API** | v1 | Send/read on behalf of user |
| Contacts | **Google People API** | v1 | Resolve names → emails from user's Google Contacts |
| Database | **Supabase** | Free tier | PostgreSQL, built-in auth helpers |
| Deployment | **Railway** | Hobby ($5/mo) | Always-on, no timeouts, Docker support |
| HTTP Client | **httpx** | 0.27+ | Async HTTP for Linq API calls |
| Google SDK | **google-api-python-client** | 2.x | Official Google API client |
| Google Auth | **google-auth-oauthlib** | 1.x | OAuth2 flow |
| Anthropic SDK | **anthropic** | 0.39+ | Official Claude Python SDK |
| DB Client | **supabase-py** | 2.x | Supabase Python client |
| Env | **python-dotenv** | 1.x | Environment variable management |

### Python Dependencies (requirements.txt)

```
fastapi==0.115.6
uvicorn[standard]==0.34.0
httpx==0.27.2
anthropic==0.39.0
google-api-python-client==2.154.0
google-auth-oauthlib==1.2.1
google-auth-httplib2==0.2.0
supabase==2.10.0
python-dotenv==1.0.1
pydantic==2.10.3
pydantic-settings==2.7.1
python-dateutil==2.9.0
pytz==2024.2
jinja2==3.1.4
python-multipart==0.0.18
```

---

## 4. REPOSITORY STRUCTURE <a name="4-repository-structure"></a>

```
schedulegpt/
├── README.md                    # Open source readme with setup instructions
├── plan.md                      # This file
├── requirements.txt             # Python dependencies
├── Dockerfile                   # For Railway deployment
├── railway.toml                 # Railway config
├── .env.example                 # Template for environment variables
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI app, routes, startup
│   ├── config.py                # Settings loaded from env vars
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── loop.py              # The core agent tool-calling loop
│   │   ├── system_prompt.py     # System prompt template
│   │   ├── tools.py             # All 9 tool definitions (JSON schema)
│   │   ├── tool_executor.py     # Maps tool names → functions, executes
│   │   └── intent_router.py     # Haiku-based intent classification (optional optimization)
│   ├── services/
│   │   ├── __init__.py
│   │   ├── linq.py              # Linq API client (send, typing, reactions)
│   │   ├── calendar_service.py  # Google Calendar (CRUD, FreeBusy)
│   │   ├── gmail_service.py     # Gmail (send, read, draft)
│   │   ├── contacts_service.py  # Google People API (search contacts)
│   │   ├── google_auth.py       # OAuth2 flow, token refresh
│   │   └── smart_time.py        # Activity-aware time slot filtering
│   ├── db/
│   │   ├── __init__.py
│   │   ├── client.py            # Supabase client singleton
│   │   ├── users.py             # User CRUD operations
│   │   ├── messages.py          # Message history storage
│   │   ├── conversations.py     # Conversation management
│   │   ├── pending_actions.py   # Pending action CRUD
│   │   └── contacts_cache.py    # Local contacts cache
│   ├── webhooks/
│   │   ├── __init__.py
│   │   ├── linq_webhook.py      # Linq webhook handler + signature verification
│   │   └── gmail_webhook.py     # Gmail push notification handler (optional)
│   ├── web/
│   │   ├── __init__.py
│   │   ├── auth_routes.py       # Google OAuth routes
│   │   ├── poll_routes.py       # Availability polling page routes
│   │   └── templates/
│   │       ├── poll.html         # Jinja2 template for availability poll
│   │       ├── poll_thanks.html  # Thank you page after responding
│   │       └── auth_success.html # OAuth success page
│   └── utils/
│       ├── __init__.py
│       ├── time_utils.py        # Timezone handling, slot formatting
│       └── crypto.py            # HMAC verification for webhooks
├── sql/
│   └── schema.sql               # Complete database schema
└── tests/
    ├── test_agent_loop.py
    ├── test_calendar_service.py
    ├── test_smart_time.py
    └── test_linq_webhook.py
```

---

## 5. ENVIRONMENT VARIABLES <a name="5-environment-variables"></a>

Create `.env.example` with these exact variables. Users copy to `.env` and fill in their own values:

```bash
# === Linq API (iMessage) ===
LINQ_API_TOKEN=your_linq_api_token_here
LINQ_PHONE_NUMBER=+1XXXXXXXXXX          # Your Linq phone number (E.164 format)
LINQ_WEBHOOK_SECRET=your_webhook_signing_secret
LINQ_BASE_URL=https://api.linqapp.com/api/partner/v3

# === Anthropic (Claude LLM) ===
ANTHROPIC_API_KEY=sk-ant-xxxxx

# === Google OAuth2 ===
GOOGLE_CLIENT_ID=xxxxx.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-xxxxx
GOOGLE_REDIRECT_URI=https://your-app.up.railway.app/auth/google/callback

# === Supabase ===
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_SERVICE_KEY=eyJxxxxx                # Service role key (server-side only)

# === App Config ===
APP_BASE_URL=https://your-app.up.railway.app  # Public URL of your Railway deployment
DEFAULT_TIMEZONE=America/Los_Angeles
```

`app/config.py`:

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Linq
    linq_api_token: str
    linq_phone_number: str
    linq_webhook_secret: str
    linq_base_url: str = "https://api.linqapp.com/api/partner/v3"

    # Anthropic
    anthropic_api_key: str

    # Google
    google_client_id: str
    google_client_secret: str
    google_redirect_uri: str

    # Supabase
    supabase_url: str
    supabase_service_key: str

    # App
    app_base_url: str
    default_timezone: str = "America/Los_Angeles"

    class Config:
        env_file = ".env"

settings = Settings()
```

---

## 6. DATABASE SCHEMA <a name="6-database-schema"></a>

File: `sql/schema.sql` — Run this in Supabase SQL Editor.

```sql
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
```

---

## 7. GOOGLE OAUTH2 SETUP & TOKEN MANAGEMENT <a name="7-google-oauth2"></a>

### Google Cloud Console Setup (Manual — document in README)

1. Go to https://console.cloud.google.com → Create new project "ScheduleGPT"
2. Enable these APIs:
   - Google Calendar API
   - Gmail API
   - People API
3. Create OAuth 2.0 credentials:
   - Application type: **Web application**
   - Authorized redirect URI: `https://your-app.up.railway.app/auth/google/callback`
4. Download client ID and secret → put in `.env`
5. Configure OAuth consent screen:
   - Scopes to request:
     - `https://www.googleapis.com/auth/calendar` (read/write calendar)
     - `https://www.googleapis.com/auth/gmail.send` (send emails)
     - `https://www.googleapis.com/auth/gmail.readonly` (read email replies)
     - `https://www.googleapis.com/auth/contacts.readonly` (read contacts for name resolution)
     - `https://www.googleapis.com/auth/contacts.other.readonly` (read "Other contacts" too)
   - App is in "Testing" mode (up to 100 test users, no verification needed for hackathon)

### OAuth Flow Implementation

File: `app/services/google_auth.py`

```python
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from datetime import datetime, timezone
from app.config import settings
from app.db.client import supabase

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/contacts.readonly",
    "https://www.googleapis.com/auth/contacts.other.readonly",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
]

def create_auth_flow() -> Flow:
    """Create OAuth2 flow for Google sign-in."""
    flow = Flow.from_client_config(
        client_config={
            "web": {
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uris": [settings.google_redirect_uri],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=SCOPES,
    )
    flow.redirect_uri = settings.google_redirect_uri
    return flow

def get_auth_url(user_phone: str) -> str:
    """Generate Google OAuth URL. Pass user_phone as state parameter."""
    flow = create_auth_flow()
    auth_url, _ = flow.authorization_url(
        access_type="offline",      # CRITICAL: ensures refresh_token is returned
        prompt="consent",           # CRITICAL: forces consent to always get refresh_token
        include_granted_scopes="true",
        state=user_phone,           # We'll use this to link back to the user
    )
    return auth_url

async def exchange_code(code: str, user_phone: str) -> dict:
    """Exchange authorization code for tokens and store them."""
    flow = create_auth_flow()
    flow.fetch_token(code=code)
    creds = flow.credentials

    # Get user's email from the ID token
    from google.oauth2 import id_token
    from google.auth.transport import requests as google_requests
    id_info = id_token.verify_oauth2_token(
        creds.id_token,
        google_requests.Request(),
        settings.google_client_id,
    )
    email = id_info["email"]

    # Upsert the linked account
    data = {
        "email": email,
        "access_token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_expiry": creds.expiry.isoformat() if creds.expiry else None,
        "scopes": list(creds.scopes) if creds.scopes else SCOPES,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    # Find or create user by phone
    user_result = supabase.table("users").select("id").eq("phone_number", user_phone).execute()
    if user_result.data:
        user_id = user_result.data[0]["id"]
    else:
        result = supabase.table("users").insert({"phone_number": user_phone}).execute()
        user_id = result.data[0]["id"]

    # Upsert linked account
    supabase.table("linked_accounts").upsert(
        {**data, "user_id": user_id, "provider": "google"},
        on_conflict="user_id,provider"
    ).execute()

    return {"email": email, "user_id": user_id}

async def get_google_credentials(user_id: str) -> Credentials | None:
    """Load and refresh Google credentials for a user."""
    try:
        result = supabase.table("linked_accounts")\
            .select("*")\
            .eq("user_id", user_id)\
            .eq("provider", "google")\
            .maybe_single()\
            .execute()
    except Exception:
        return None

    if not result or not result.data:
        return None

    account = result.data
    creds = Credentials(
        token=account["access_token"],
        refresh_token=account["refresh_token"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        scopes=account["scopes"],
    )

    # Refresh if expired
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        # Update stored tokens
        supabase.table("linked_accounts").update({
            "access_token": creds.token,
            "token_expiry": creds.expiry.isoformat() if creds.expiry else None,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", account["id"]).execute()

    return creds
```

---

## 8. CONTACT RESOLUTION — Google People API <a name="8-contact-resolution"></a>

**The Problem:** When a user says "schedule lunch with Bharat," the agent needs to resolve "Bharat" to an email address (e.g., `bharat.mekala@gmail.com`). 

**The Solution:** Use Google People API's `searchContacts` endpoint which searches across the user's Google Contacts by name prefix match. This covers:
- People they've emailed (Google auto-adds to "Other Contacts")
- People in their phone contacts (if synced to Google)
- Manually added contacts

**Implementation:** `app/services/contacts_service.py`

```python
from googleapiclient.discovery import build
from app.services.google_auth import get_google_credentials
from app.db.client import supabase

async def search_contacts(user_id: str, query: str, max_results: int = 5) -> list[dict]:
    """
    Search user's Google Contacts by name.
    Returns list of {name, email, phone, source}.
    
    IMPORTANT: Google People API requires a warmup request with empty query
    before the first real search. We do this once per user session and cache.
    """
    # 1. Check local cache first (faster, works offline)
    cache_results = supabase.table("contacts_cache")\
        .select("display_name, email, phone")\
        .eq("user_id", user_id)\
        .ilike("display_name", f"%{query}%")\
        .limit(max_results)\
        .execute()

    if cache_results.data and len(cache_results.data) > 0:
        return cache_results.data

    # 2. Fall back to Google People API live search
    creds = await get_google_credentials(user_id)
    if not creds:
        return []

    service = build("people", "v1", credentials=creds)

    # Warmup request (needed once per session — the cache handles subsequent calls)
    try:
        service.people().searchContacts(
            query="",
            readMask="names,emailAddresses,phoneNumbers"
        ).execute()
    except Exception:
        pass  # Warmup can fail silently

    # Actual search
    try:
        results = service.people().searchContacts(
            query=query,
            pageSize=max_results,
            readMask="names,emailAddresses,phoneNumbers"
        ).execute()
    except Exception as e:
        # Also search "Other Contacts" (people they've emailed)
        try:
            results = service.otherContacts().search(
                query=query,
                pageSize=max_results,
                readMask="names,emailAddresses,phoneNumbers"
            ).execute()
        except Exception:
            return []

    contacts = []
    for person in results.get("results", []):
        p = person.get("person", {})
        name = ""
        email = ""
        phone = ""

        names = p.get("names", [])
        if names:
            name = names[0].get("displayName", "")

        emails = p.get("emailAddresses", [])
        if emails:
            email = emails[0].get("value", "")

        phones = p.get("phoneNumbers", [])
        if phones:
            phone = phones[0].get("value", "")

        if name or email:
            contacts.append({"display_name": name, "email": email, "phone": phone})

            # Cache for future lookups
            supabase.table("contacts_cache").upsert(
                {
                    "user_id": user_id,
                    "display_name": name,
                    "email": email,
                    "phone": phone,
                    "source": "google_contacts",
                },
                on_conflict="user_id,email"
            ).execute()

    return contacts

async def sync_contacts_to_cache(user_id: str) -> int:
    """
    Full sync of user's Google Contacts to local cache.
    Call this once during onboarding.
    Returns number of contacts synced.
    """
    creds = await get_google_credentials(user_id)
    if not creds:
        return 0

    service = build("people", "v1", credentials=creds)
    count = 0
    page_token = None

    while True:
        results = service.people().connections().list(
            resourceName="people/me",
            pageSize=100,
            personFields="names,emailAddresses,phoneNumbers",
            pageToken=page_token,
        ).execute()

        for person in results.get("connections", []):
            name = ""
            email = ""
            phone = ""

            names = person.get("names", [])
            if names:
                name = names[0].get("displayName", "")

            emails = person.get("emailAddresses", [])
            if emails:
                email = emails[0].get("value", "")

            phones = person.get("phoneNumbers", [])
            if phones:
                phone = phones[0].get("value", "")

            if email:  # Only cache contacts with emails (useful for scheduling)
                supabase.table("contacts_cache").upsert(
                    {
                        "user_id": user_id,
                        "display_name": name,
                        "email": email,
                        "phone": phone,
                        "source": "google_contacts",
                    },
                    on_conflict="user_id,email"
                ).execute()
                count += 1

        page_token = results.get("nextPageToken")
        if not page_token:
            break

    return count
```

**How it works in practice:**
1. User says "schedule pickleball with Bharat"
2. Agent calls `resolve_contact` tool with query "Bharat"
3. Tool searches local cache first (instant), then Google People API if cache miss
4. Returns: `[{name: "Bharat Mekala", email: "bharat@gmail.com"}]`
5. If multiple matches, agent presents options: "I found 2 Bharats — Bharat Mekala (bharat@gmail.com) or Bharat Singh (bsingh@company.com). Which one?"
6. If no match, agent asks: "I couldn't find Bharat in your contacts. What's their email?"

---

## 9. GOOGLE CALENDAR API — ALL OPERATIONS <a name="9-google-calendar-api"></a>

File: `app/services/calendar_service.py`

```python
from googleapiclient.discovery import build
from datetime import datetime, timedelta
from app.services.google_auth import get_google_credentials
import pytz

async def get_calendar_service(user_id: str):
    creds = await get_google_credentials(user_id)
    if not creds:
        raise ValueError("No Google credentials found. User needs to connect Google account.")
    return build("calendar", "v3", credentials=creds)

# ─── LIST EVENTS ─────────────────────────────────────────────
async def list_events(
    user_id: str,
    time_min: str,     # ISO 8601 datetime
    time_max: str,     # ISO 8601 datetime
    max_results: int = 20,
) -> list[dict]:
    """List events in a time range. Returns simplified event objects."""
    service = await get_calendar_service(user_id)
    result = service.events().list(
        calendarId="primary",
        timeMin=time_min,
        timeMax=time_max,
        maxResults=max_results,
        singleEvents=True,           # Expand recurring events
        orderBy="startTime",
    ).execute()

    events = []
    for event in result.get("items", []):
        events.append({
            "id": event["id"],
            "summary": event.get("summary", "(No title)"),
            "start": event["start"].get("dateTime", event["start"].get("date")),
            "end": event["end"].get("dateTime", event["end"].get("date")),
            "location": event.get("location", ""),
            "description": event.get("description", ""),
            "attendees": [
                {"email": a["email"], "status": a.get("responseStatus", "needsAction")}
                for a in event.get("attendees", [])
            ],
        })
    return events

# ─── CHECK FREE/BUSY ────────────────────────────────────────
async def check_freebusy(
    user_id: str,
    calendars: list[str],   # List of email addresses to check
    time_min: str,           # ISO 8601
    time_max: str,           # ISO 8601
) -> dict:
    """
    Check free/busy status for one or more calendars.
    Returns dict of {email: [{start, end}, ...]} for busy periods.
    
    CRITICAL: An empty busy array with errors means "couldn't check" NOT "free".
    """
    service = await get_calendar_service(user_id)

    body = {
        "timeMin": time_min,
        "timeMax": time_max,
        "timeZone": "UTC",
        "items": [{"id": cal} for cal in calendars],
    }

    result = service.freebusy().query(body=body).execute()

    freebusy_data = {}
    for email in calendars:
        cal_data = result["calendars"].get(email, {})
        errors = cal_data.get("errors", [])
        busy = cal_data.get("busy", [])

        if errors:
            # Could not access this calendar
            freebusy_data[email] = {
                "accessible": False,
                "busy": [],
                "error": errors[0].get("reason", "unknown"),
            }
        else:
            freebusy_data[email] = {
                "accessible": True,
                "busy": busy,
            }

    return freebusy_data

# ─── CREATE EVENT ────────────────────────────────────────────
async def create_event(
    user_id: str,
    summary: str,
    start_time: str,          # ISO 8601 datetime
    end_time: str,            # ISO 8601 datetime
    description: str = "",
    location: str = "",
    attendees: list[str] = None,  # List of email addresses
    send_updates: str = "all",    # "all", "externalOnly", "none"
    add_meet_link: bool = False,
) -> dict:
    """Create a calendar event with optional attendees and Google Meet link."""
    service = await get_calendar_service(user_id)

    event_body = {
        "summary": summary,
        "start": {"dateTime": start_time, "timeZone": "UTC"},
        "end": {"dateTime": end_time, "timeZone": "UTC"},
        "description": description,
        "location": location,
    }

    if attendees:
        event_body["attendees"] = [{"email": e} for e in attendees]

    if add_meet_link:
        event_body["conferenceData"] = {
            "createRequest": {
                "requestId": f"meet-{datetime.now().timestamp()}",
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        }

    result = service.events().insert(
        calendarId="primary",
        body=event_body,
        sendUpdates=send_updates,
        conferenceDataVersion=1 if add_meet_link else 0,
    ).execute()

    return {
        "id": result["id"],
        "summary": result.get("summary"),
        "start": result["start"].get("dateTime"),
        "end": result["end"].get("dateTime"),
        "html_link": result.get("htmlLink"),
        "meet_link": result.get("hangoutLink", ""),
    }

# ─── UPDATE EVENT ────────────────────────────────────────────
async def update_event(
    user_id: str,
    event_id: str,
    updates: dict,            # Partial update: {summary, start, end, description, location}
    send_updates: str = "all",
) -> dict:
    """Update an existing calendar event."""
    service = await get_calendar_service(user_id)

    # Fetch current event first
    event = service.events().get(calendarId="primary", eventId=event_id).execute()

    # Apply updates
    if "summary" in updates:
        event["summary"] = updates["summary"]
    if "start_time" in updates:
        event["start"] = {"dateTime": updates["start_time"], "timeZone": "UTC"}
    if "end_time" in updates:
        event["end"] = {"dateTime": updates["end_time"], "timeZone": "UTC"}
    if "description" in updates:
        event["description"] = updates["description"]
    if "location" in updates:
        event["location"] = updates["location"]

    result = service.events().update(
        calendarId="primary",
        eventId=event_id,
        body=event,
        sendUpdates=send_updates,
    ).execute()

    return {
        "id": result["id"],
        "summary": result.get("summary"),
        "start": result["start"].get("dateTime"),
        "end": result["end"].get("dateTime"),
    }

# ─── DELETE EVENT ────────────────────────────────────────────
async def delete_event(
    user_id: str,
    event_id: str,
    send_updates: str = "all",
) -> bool:
    """Delete a calendar event."""
    service = await get_calendar_service(user_id)
    service.events().delete(
        calendarId="primary",
        eventId=event_id,
        sendUpdates=send_updates,
    ).execute()
    return True

# ─── FIND AVAILABLE SLOTS ───────────────────────────────────
async def find_available_slots(
    user_id: str,
    date_start: str,          # ISO date: 2025-01-15
    date_end: str,            # ISO date: 2025-01-17
    duration_minutes: int,
    earliest_hour: int = 8,   # Don't suggest before 8am
    latest_hour: int = 21,    # Don't suggest after 9pm
    timezone: str = None,     # Will be loaded from user preferences if None
) -> list[dict]:
    """
    Find available time slots in user's calendar.
    Returns list of {start, end, label} for free periods.
    """
    # Load user's timezone from DB if not provided
    if not timezone:
        from app.db.users import get_user
        user = await get_user(user_id)
        timezone = user.get("timezone", "America/Los_Angeles")

    tz = pytz.timezone(timezone)
    start_dt = tz.localize(datetime.strptime(date_start, "%Y-%m-%d").replace(hour=0, minute=0))
    end_dt = tz.localize(datetime.strptime(date_end, "%Y-%m-%d").replace(hour=23, minute=59))

    # Get the user's primary calendar email for FreeBusy lookup
    from app.services.google_auth import get_google_credentials
    creds = await get_google_credentials(user_id)
    # The primary calendar ID is the user's email — get it from linked_accounts
    from app.db.client import supabase as sb
    account = sb.table("linked_accounts").select("email").eq("user_id", user_id).eq("provider", "google").execute()
    user_email = account.data[0]["email"] if account.data else "primary"

    # Get busy periods
    freebusy = await check_freebusy(
        user_id,
        calendars=[user_email],
        time_min=start_dt.isoformat(),
        time_max=end_dt.isoformat(),
    )

    # FreeBusy result is keyed by the actual email, not "primary"
    cal_data = freebusy.get(user_email, {})
    busy_periods = cal_data.get("busy", []) if isinstance(cal_data, dict) else []

    # Generate candidate slots in 30-min increments
    slots = []
    current = start_dt.replace(hour=earliest_hour, minute=0)

    while current < end_dt:
        # Skip to next day's earliest_hour if past latest_hour
        if current.hour >= latest_hour:
            current = (current + timedelta(days=1)).replace(hour=earliest_hour, minute=0)
            continue

        slot_end = current + timedelta(minutes=duration_minutes)

        # Check if slot overlaps with any busy period
        is_free = True
        for busy in busy_periods:
            busy_start = datetime.fromisoformat(busy["start"].replace("Z", "+00:00")).astimezone(tz)
            busy_end = datetime.fromisoformat(busy["end"].replace("Z", "+00:00")).astimezone(tz)

            if current < busy_end and slot_end > busy_start:
                is_free = False
                break

        if is_free and slot_end.hour <= latest_hour:
            slots.append({
                "start": current.isoformat(),
                "end": slot_end.isoformat(),
                "label": current.strftime("%A %b %d, %I:%M %p"),
            })

        current += timedelta(minutes=30)

    return slots
```

---

## 10. GMAIL API — EMAIL OPERATIONS <a name="10-gmail-api"></a>

File: `app/services/gmail_service.py`

```python
from googleapiclient.discovery import build
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import base64
from app.services.google_auth import get_google_credentials
from app.config import settings

async def get_gmail_service(user_id: str):
    creds = await get_google_credentials(user_id)
    if not creds:
        raise ValueError("No Google credentials found.")
    return build("gmail", "v1", credentials=creds)

async def send_email(
    user_id: str,
    to: str,
    subject: str,
    body_html: str,
    reply_to_message_id: str = None,
) -> dict:
    """Send an email on behalf of the user via Gmail API."""
    service = await get_gmail_service(user_id)

    message = MIMEMultipart("alternative")
    message["to"] = to
    message["subject"] = subject

    if reply_to_message_id:
        message["In-Reply-To"] = reply_to_message_id
        message["References"] = reply_to_message_id

    message.attach(MIMEText(body_html, "html"))

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    result = service.users().messages().send(
        userId="me",
        body={"raw": raw},
    ).execute()

    return {"message_id": result["id"], "thread_id": result.get("threadId")}

async def send_availability_email(
    user_id: str,
    to_email: str,
    to_name: str,
    user_name: str,
    event_title: str,
    poll_id: str,
    proposed_times: list[dict],
) -> dict:
    """
    Send an availability poll email with a link to the web-based poll page.
    """
    poll_url = f"{settings.app_base_url}/poll/{poll_id}"

    # Build the time options as HTML list
    time_list = ""
    for i, t in enumerate(proposed_times):
        time_list += f"<li>{t['label']}</li>"

    html = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto;">
        <h2>📅 {user_name} wants to schedule: {event_title}</h2>
        <p>Hi {to_name},</p>
        <p>{user_name} would like to find a time for <strong>{event_title}</strong>. Here are some proposed times:</p>
        <ol>{time_list}</ol>
        <p>
            <a href="{poll_url}" 
               style="display: inline-block; padding: 12px 24px; background-color: #007AFF; color: white; text-decoration: none; border-radius: 8px; font-weight: 600;">
                Pick your available times
            </a>
        </p>
        <p style="color: #666; font-size: 14px;">Or just reply to this email with your preferred time and I'll handle the rest!</p>
        <p style="color: #999; font-size: 12px;">Sent by ScheduleGPT on behalf of {user_name}</p>
    </div>
    """

    return await send_email(
        user_id=user_id,
        to=to_email,
        subject=f"📅 Finding a time for: {event_title}",
        body_html=html,
    )

async def check_for_replies(
    user_id: str,
    thread_id: str,
    since_message_id: str = None,
) -> list[dict]:
    """Check for new replies in an email thread."""
    service = await get_gmail_service(user_id)

    thread = service.users().threads().get(
        userId="me",
        id=thread_id,
        format="full",
    ).execute()

    replies = []
    found_since = since_message_id is None

    for msg in thread.get("messages", []):
        if not found_since:
            if msg["id"] == since_message_id:
                found_since = True
            continue

        # Extract the plain text body
        payload = msg.get("payload", {})
        body = ""

        if payload.get("mimeType") == "text/plain":
            body = base64.urlsafe_b64decode(payload["body"]["data"]).decode()
        else:
            for part in payload.get("parts", []):
                if part.get("mimeType") == "text/plain":
                    body = base64.urlsafe_b64decode(part["body"]["data"]).decode()
                    break

        # Get sender
        headers = {h["name"]: h["value"] for h in payload.get("headers", [])}

        replies.append({
            "message_id": msg["id"],
            "from": headers.get("From", ""),
            "date": headers.get("Date", ""),
            "body": body,
        })

    return replies
```

---

## 11. LINQ iMESSAGE API — FULL INTEGRATION <a name="11-linq-imessage-api"></a>

File: `app/services/linq.py`

**Base URL:** `https://api.linqapp.com/api/partner/v3`
**Auth:** Bearer token in `Authorization` header
**Webhook signing:** HMAC-SHA256 with `X-Linq-Signature` header and `X-Linq-Timestamp` header

```python
import httpx
from app.config import settings

class LinqClient:
    """Client for Linq Partner API V3 (iMessage, RCS, SMS)."""

    def __init__(self):
        self.base_url = settings.linq_base_url
        self.headers = {
            "Authorization": f"Bearer {settings.linq_api_token}",
            "Content-Type": "application/json",
        }
        self.phone_number = settings.linq_phone_number

    async def create_chat(
        self,
        to_phone: str,
        message: str,
        preferred_service: str = "iMessage",
        effect: dict = None,
    ) -> dict:
        """
        Create a new chat and send the first message.
        preferred_service: "iMessage", "RCS", or "SMS"
        effect: {"type": "screen", "name": "confetti"} for screen effects
        """
        payload = {
            "to": to_phone,
            "from": self.phone_number,
            "body": message,
        }
        if preferred_service:
            payload["service"] = preferred_service
        if effect:
            payload["effect"] = effect

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/chats",
                headers=self.headers,
                json=payload,
                timeout=30.0,
            )
            resp.raise_for_status()
            return resp.json()

    async def send_message(
        self,
        chat_id: str,
        text: str,
        effect: dict = None,
        reply_to_message_id: str = None,
        media_url: str = None,
    ) -> dict:
        """Send a message to an existing chat."""
        payload = {"body": text}
        if effect:
            payload["effect"] = effect
        if reply_to_message_id:
            payload["replyTo"] = reply_to_message_id
        if media_url:
            payload["mediaUrl"] = media_url

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/chats/{chat_id}/messages",
                headers=self.headers,
                json=payload,
                timeout=30.0,
            )
            resp.raise_for_status()
            return resp.json()

    async def send_typing_indicator(self, chat_id: str) -> None:
        """Show typing bubble in the user's iMessage."""
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{self.base_url}/chats/{chat_id}/typing",
                headers=self.headers,
                timeout=10.0,
            )

    async def send_reaction(self, chat_id: str, message_id: str, reaction: str) -> None:
        """
        Send a tapback reaction.
        reaction: "love", "like", "dislike", "laugh", "emphasize", "question"
        """
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{self.base_url}/chats/{chat_id}/messages/{message_id}/reactions",
                headers=self.headers,
                json={"type": reaction},
                timeout=10.0,
            )

    async def register_webhook(self, target_url: str) -> dict:
        """Register a webhook URL to receive incoming messages."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/webhook-subscriptions",
                headers=self.headers,
                json={
                    "target_url": target_url,
                    "subscribed_events": [
                        "message.received",
                        "message.delivered",
                        "reaction.added",
                    ],
                },
                timeout=30.0,
            )
            resp.raise_for_status()
            return resp.json()

# Singleton
linq_client = LinqClient()
```

File: `app/webhooks/linq_webhook.py`

```python
import hmac
import hashlib
import time
from fastapi import Request, HTTPException
from app.config import settings
from app.db.client import supabase

def verify_linq_signature(request_body: bytes, timestamp: str, signature: str) -> bool:
    """
    Verify Linq webhook HMAC-SHA256 signature.
    Reject if timestamp is older than 5 minutes (replay protection).
    """
    # Replay protection
    try:
        ts = int(timestamp)
        if abs(time.time() - ts) > 300:  # 5 minute window
            return False
    except (ValueError, TypeError):
        return False

    # HMAC verification
    expected = hmac.new(
        settings.linq_webhook_secret.encode(),
        request_body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(f"sha256={expected}", signature)

async def is_duplicate_webhook(message_id: str) -> bool:
    """Check if we've already processed this webhook (idempotency)."""
    result = supabase.table("processed_webhooks")\
        .select("message_id")\
        .eq("message_id", message_id)\
        .execute()
    return len(result.data) > 0

async def mark_webhook_processed(message_id: str) -> None:
    """Mark a webhook as processed."""
    supabase.table("processed_webhooks").insert(
        {"message_id": message_id}
    ).execute()

def parse_linq_webhook(payload: dict) -> dict:
    """
    Parse a Linq webhook payload into a normalized message object.
    
    DEFENSIVE PARSING: Linq's payload structure can vary between sandbox
    and production, and across API versions. This parser handles known variants:
    
    Variant A (CareSupport/production docs):
    {"event_type": "message.created", "data": {"chat_id": "...", "message": {"id": "...", "parts": [{"type": "text", "value": "..."}], "from": "+1..."}}}
    
    Variant B (sandbox/webhook style):
    {"event_type": "message.received", "data": {"chatId": "...", "messageId": "...", "text": "...", "from": "+1...", "service": "iMessage"}}
    
    Variant C (flat body style seen in some integrations):
    {"type": "message", "chatId": "...", "body": "...", "from": "+1..."}
    """
    event_type = payload.get("event_type", payload.get("type", ""))
    data = payload.get("data", {})
    message = data.get("message", {})

    # Extract chat_id (handle both camelCase and snake_case)
    chat_id = (
        data.get("chat_id")
        or data.get("chatId")
        or payload.get("chatId")
        or ""
    )

    # Extract message_id
    message_id = (
        message.get("id")
        or data.get("messageId")
        or data.get("message_id")
        or payload.get("messageId")
        or ""
    )

    # Extract text — try multiple known locations
    text = ""
    # Variant A: parts array
    parts = message.get("parts", [])
    for part in parts:
        if part.get("type") == "text":
            text = part.get("value", "")
            break
    # Variant B: direct text field
    if not text:
        text = data.get("text", "")
    # Variant C: body field
    if not text:
        text = message.get("body", data.get("body", payload.get("body", "")))

    # Extract sender phone
    from_phone = (
        message.get("from")
        or data.get("from")
        or payload.get("from")
        or ""
    )

    # Extract service type
    service = (
        message.get("service")
        or data.get("service")
        or payload.get("service")
        or "unknown"
    )

    return {
        "event_type": event_type,
        "chat_id": chat_id,
        "message_id": message_id,
        "from_phone": from_phone,
        "text": text,
        "service": service,
    }
```

---

## 12. THE AGENT BRAIN — CLAUDE TOOL-CALLING LOOP <a name="12-agent-brain"></a>

File: `app/agent/loop.py`

This is the core of the entire application. It implements a ReAct (Reasoning + Acting) loop where Claude reasons about the user's request, calls tools to gather information or take actions, and iterates until it has a final response.

```python
import anthropic
from app.config import settings
from app.agent.tools import TOOL_DEFINITIONS
from app.agent.tool_executor import execute_tool
from app.agent.system_prompt import build_system_prompt
from app.db.messages import save_message, get_recent_messages
from app.db.conversations import get_or_create_conversation, update_summary
from app.db.pending_actions import get_pending_actions
import json
import logging

logger = logging.getLogger(__name__)

client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

async def run_agent(
    user_id: str,
    user_message: str,
    chat_id: str,
) -> str:
    """
    Run the agent loop for a single user message.
    Returns the final text response to send back via iMessage.
    """
    # 1. Get or create conversation
    conversation = await get_or_create_conversation(user_id, chat_id)
    conversation_id = conversation["id"]

    # 2. Load conversation context BEFORE saving new message
    #    (so the new message isn't doubled in context)
    recent_messages = await get_recent_messages(conversation_id, limit=10)
    summary = conversation.get("summary", "")

    # 3. Save the incoming user message
    await save_message(conversation_id, "user", user_message)

    # 4. Check for pending actions (user might be confirming/rejecting)
    pending = await get_pending_actions(conversation_id)

    # 5. Build the messages array for Claude
    messages = []

    # Add summary of older conversation if exists
    if summary:
        messages.append({
            "role": "user",
            "content": f"[CONVERSATION SUMMARY FROM EARLIER]: {summary}"
        })
        messages.append({
            "role": "assistant",
            "content": "I remember our earlier conversation. How can I help?"
        })

    # Add recent messages (these are BEFORE the current message)
    for msg in recent_messages:
        messages.append({"role": msg["role"], "content": msg["content"]})

    # Add the current user message (not yet in DB when we loaded recent_messages)
    messages.append({"role": "user", "content": user_message})

    # 6. Build system prompt with user context
    system_prompt = await build_system_prompt(user_id, pending)

    # 7. Run the agent loop
    max_iterations = 15
    final_response = ""

    for iteration in range(max_iterations):
        try:
            response = client.messages.create(
                model="claude-sonnet-4-5-20241022",
                max_tokens=4096,
                system=system_prompt,
                tools=TOOL_DEFINITIONS,
                messages=messages,
            )
        except anthropic.APIError as e:
            logger.error(f"Claude API error: {e}")
            return "Sorry, I'm having trouble thinking right now. Try again in a moment!"

        # Process the response
        if response.stop_reason == "end_turn":
            # Claude is done — extract the text response
            for block in response.content:
                if block.type == "text":
                    final_response += block.text
            break

        elif response.stop_reason == "tool_use":
            # Claude wants to call tools
            # Add assistant's response to messages
            messages.append({"role": "assistant", "content": response.content})

            # Execute each tool call
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    logger.info(f"Tool call [{iteration}]: {block.name}({json.dumps(block.input)[:200]})")
                    try:
                        result = await execute_tool(
                            tool_name=block.name,
                            tool_input=block.input,
                            user_id=user_id,
                            conversation_id=conversation_id,
                        )
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result) if isinstance(result, (dict, list)) else str(result),
                        })
                    except Exception as e:
                        logger.error(f"Tool execution error: {block.name}: {e}")
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps({"error": str(e)}),
                            "is_error": True,
                        })

            # Add tool results to messages
            messages.append({"role": "user", "content": tool_results})

        else:
            # Unexpected stop reason
            logger.warning(f"Unexpected stop_reason: {response.stop_reason}")
            break

    if not final_response:
        final_response = "I processed your request but something went wrong generating a response. Could you try again?"

    # 8. Save the assistant's response
    await save_message(conversation_id, "assistant", final_response)

    # 9. Check if conversation is getting long — summarize older messages
    message_count = len(recent_messages)
    if message_count >= 10:
        await summarize_and_trim(conversation_id)

    return final_response

async def summarize_and_trim(conversation_id: str):
    """
    Summarize the oldest messages in the conversation and delete them.
    Keep the 10 most recent messages intact.
    """
    all_messages = await get_recent_messages(conversation_id, limit=30)

    if len(all_messages) <= 10:
        return

    # Messages are in chronological order (oldest first).
    # Keep the LAST 10 (most recent), summarize everything before that.
    old_messages = all_messages[:-10]  # Everything except the 10 most recent
    old_text = "\n".join([f"{m['role']}: {m['content']}" for m in old_messages])

    # Use Haiku for fast summarization
    summary_response = client.messages.create(
        model="claude-haiku-4-5-20241022",
        max_tokens=500,
        messages=[{
            "role": "user",
            "content": f"Summarize this conversation history concisely, preserving key decisions, scheduled events, and user preferences:\n\n{old_text}"
        }],
    )

    summary = summary_response.content[0].text
    await update_summary(conversation_id, summary)

    # Delete old messages from DB (keep only the 10 most recent)
    from app.db.messages import delete_old_messages
    await delete_old_messages(conversation_id, keep_recent=10)
```

---

## 13. TOOL DEFINITIONS (ALL 9 TOOLS) <a name="13-tool-definitions"></a>

File: `app/agent/tools.py`

These are the JSON schema definitions passed to Claude's `tools` parameter. The descriptions are CRITICAL for agent accuracy — they tell Claude WHEN and HOW to use each tool.

```python
TOOL_DEFINITIONS = [
    # ─── 1. RESOLVE CONTACT ─────────────────────────────────
    {
        "name": "resolve_contact",
        "description": (
            "Search the user's Google Contacts to find a person's email address by name. "
            "Use this BEFORE any scheduling operation that involves other people. "
            "The search is prefix-based: 'Bha' will match 'Bharat Mekala'. "
            "If multiple matches are found, present ALL options to the user and ask which one they mean. "
            "If no match is found, ask the user for the person's email address directly."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The person's name or partial name to search for. E.g., 'Bharat' or 'Sarah Johnson'"
                }
            },
            "required": ["query"]
        }
    },

    # ─── 2. LIST CALENDAR EVENTS ─────────────────────────────
    {
        "name": "list_calendar_events",
        "description": (
            "List the user's calendar events within a date range. "
            "Use this to show the user their schedule, check what's coming up, "
            "or understand their current commitments before suggesting new times. "
            "Always call this BEFORE creating or modifying events to understand current schedule context."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "date_start": {
                    "type": "string",
                    "description": "Start date in YYYY-MM-DD format. E.g., '2025-01-15'"
                },
                "date_end": {
                    "type": "string",
                    "description": "End date in YYYY-MM-DD format. E.g., '2025-01-17'"
                }
            },
            "required": ["date_start", "date_end"]
        }
    },

    # ─── 3. CHECK AVAILABILITY ───────────────────────────────
    {
        "name": "check_availability",
        "description": (
            "Check free/busy status for one or more people's Google Calendars. "
            "Pass email addresses of people to check. This uses the Google FreeBusy API. "
            "IMPORTANT: If a calendar is not accessible (the person hasn't shared it), "
            "the result will show accessible=false. In that case, tell the user you can't "
            "see that person's calendar and offer to send an availability poll email instead. "
            "An empty busy list with accessible=true means the person IS free. "
            "An empty busy list with accessible=false means you COULDN'T CHECK."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "emails": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of email addresses to check availability for"
                },
                "date_start": {
                    "type": "string",
                    "description": "Start date in YYYY-MM-DD format"
                },
                "date_end": {
                    "type": "string",
                    "description": "End date in YYYY-MM-DD format"
                }
            },
            "required": ["emails", "date_start", "date_end"]
        }
    },

    # ─── 4. FIND OPEN SLOTS ─────────────────────────────────
    {
        "name": "find_open_slots",
        "description": (
            "Find available time slots in the user's OWN calendar within a date range. "
            "Use this when you need to suggest times for new events. "
            "You can filter by earliest/latest acceptable hours (e.g., 9-17 for work hours, "
            "6-8 or 17-20 for gym, 10-17 for outdoor activities). "
            "Returns a list of available slots with human-readable labels."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "date_start": {
                    "type": "string",
                    "description": "Start date in YYYY-MM-DD format"
                },
                "date_end": {
                    "type": "string",
                    "description": "End date in YYYY-MM-DD format"
                },
                "duration_minutes": {
                    "type": "integer",
                    "description": "How long the event should be, in minutes",
                    "minimum": 15,
                    "maximum": 480
                },
                "earliest_hour": {
                    "type": "integer",
                    "description": "Earliest acceptable start hour (0-23). E.g., 9 for 9am.",
                    "minimum": 0,
                    "maximum": 23,
                    "default": 8
                },
                "latest_hour": {
                    "type": "integer",
                    "description": "Latest acceptable start hour (0-23). E.g., 17 for 5pm.",
                    "minimum": 0,
                    "maximum": 23,
                    "default": 21
                }
            },
            "required": ["date_start", "date_end", "duration_minutes"]
        }
    },

    # ─── 5. CREATE CALENDAR EVENT ────────────────────────────
    {
        "name": "create_calendar_event",
        "description": (
            "Create a new event on the user's Google Calendar. "
            "CRITICAL: NEVER call this without first confirming with the user. "
            "Always present the event details and ask 'Should I go ahead?' BEFORE calling this tool. "
            "Wait for the user to say 'yes', 'confirm', 'go ahead', etc. "
            "Only call this tool AFTER the user has explicitly confirmed."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "Event title. E.g., 'Pickleball with Bharat, Tej, and Adil'"
                },
                "start_time": {
                    "type": "string",
                    "description": "Start time in ISO 8601 format with timezone. E.g., '2025-01-15T14:00:00-08:00'"
                },
                "end_time": {
                    "type": "string",
                    "description": "End time in ISO 8601 format with timezone. E.g., '2025-01-15T15:30:00-08:00'"
                },
                "description": {
                    "type": "string",
                    "description": "Event description. Can include HTML: <b>, <br>, <ul>, <li>, <a>. Use this for workout details, meeting agendas, etc.",
                    "default": ""
                },
                "location": {
                    "type": "string",
                    "description": "Event location. E.g., 'Mission Bay Courts, SF'",
                    "default": ""
                },
                "attendees": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of attendee email addresses. Google Calendar will send invite emails automatically.",
                    "default": []
                },
                "add_meet_link": {
                    "type": "boolean",
                    "description": "Whether to add a Google Meet video call link",
                    "default": False
                }
            },
            "required": ["summary", "start_time", "end_time"]
        }
    },

    # ─── 6. UPDATE CALENDAR EVENT ────────────────────────────
    {
        "name": "update_calendar_event",
        "description": (
            "Update an existing calendar event. Use this when the user wants to reschedule, "
            "rename, or change details of an event. You need the event_id which you can get "
            "from list_calendar_events. ALWAYS confirm changes with the user before executing."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "event_id": {
                    "type": "string",
                    "description": "The Google Calendar event ID (from list_calendar_events)"
                },
                "summary": {"type": "string", "description": "New event title (optional)"},
                "start_time": {"type": "string", "description": "New start time in ISO 8601 (optional)"},
                "end_time": {"type": "string", "description": "New end time in ISO 8601 (optional)"},
                "description": {"type": "string", "description": "New description (optional)"},
                "location": {"type": "string", "description": "New location (optional)"}
            },
            "required": ["event_id"]
        }
    },

    # ─── 7. DELETE CALENDAR EVENT ────────────────────────────
    {
        "name": "delete_calendar_event",
        "description": (
            "Delete/cancel a calendar event. ALWAYS confirm with the user first. "
            "This will also notify attendees that the event has been cancelled."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "event_id": {
                    "type": "string",
                    "description": "The Google Calendar event ID to delete"
                }
            },
            "required": ["event_id"]
        }
    },

    # ─── 8. SEND EMAIL ───────────────────────────────────────
    {
        "name": "send_email",
        "description": (
            "Send an email on behalf of the user via Gmail. Use this for: "
            "1) Sending availability polls to people whose calendars you can't access. "
            "2) Sending meeting confirmations or updates. "
            "3) Any email coordination the user requests. "
            "ALWAYS confirm the email content with the user before sending. "
            "The email is sent FROM the user's Gmail account."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {
                    "type": "string",
                    "description": "Recipient email address"
                },
                "subject": {
                    "type": "string",
                    "description": "Email subject line"
                },
                "body": {
                    "type": "string",
                    "description": "Email body in plain text (will be converted to HTML)"
                }
            },
            "required": ["to", "subject", "body"]
        }
    },

    # ─── 9. SEND AVAILABILITY POLL ───────────────────────────
    {
        "name": "send_availability_poll",
        "description": (
            "Send an availability poll to one or more people when you can't access their calendars. "
            "This creates a web-based poll page and sends an email with a link to it. "
            "Use this when check_availability returns accessible=false for someone. "
            "The poll lets recipients pick from proposed times or suggest alternatives."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "event_title": {
                    "type": "string",
                    "description": "What the event is. E.g., 'Pickleball'"
                },
                "participants": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "email": {"type": "string"}
                        },
                        "required": ["name", "email"]
                    },
                    "description": "List of people to send the poll to"
                },
                "proposed_times": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "start": {"type": "string", "description": "ISO 8601 datetime"},
                            "end": {"type": "string", "description": "ISO 8601 datetime"},
                            "label": {"type": "string", "description": "Human-readable label"}
                        },
                        "required": ["start", "end", "label"]
                    },
                    "description": "Proposed time slots for the poll"
                }
            },
            "required": ["event_title", "participants", "proposed_times"]
        }
    },
]
```

---

## 14. SYSTEM PROMPT <a name="14-system-prompt"></a>

File: `app/agent/system_prompt.py`

```python
from datetime import datetime
import pytz
from app.db.users import get_user
from app.db.pending_actions import get_pending_actions

async def build_system_prompt(user_id: str, pending_actions: list) -> str:
    user = await get_user(user_id)
    tz = pytz.timezone(user.get("timezone", "America/Los_Angeles"))
    now = datetime.now(tz)

    pending_section = ""
    if pending_actions:
        pending_section = "\n\nPENDING ACTIONS AWAITING USER CONFIRMATION:\n"
        for action in pending_actions:
            pending_section += f"- [{action['action_type']}] {action['action_payload'].get('summary', 'Unknown')} (ID: {action['id']})\n"
        pending_section += "\nIf the user says 'yes', 'confirm', 'go ahead', 'option 1/2/3', etc., execute the corresponding pending action. If they say 'no', 'cancel', 'never mind', cancel it.\n"

    return f"""You are ScheduleGPT, a personal scheduling assistant that communicates via iMessage. You manage the user's Google Calendar, send emails on their behalf, and coordinate schedules with other people.

CURRENT CONTEXT:
- Current time: {now.strftime("%A, %B %d, %Y at %I:%M %p %Z")}
- User's timezone: {user.get("timezone", "America/Los_Angeles")}
- User's name: {user.get("display_name", "there")}
{pending_section}

CORE RULES — FOLLOW THESE EXACTLY:

1. ALWAYS CHECK BEFORE ACTING
   - ALWAYS call list_calendar_events or find_open_slots BEFORE creating events
   - ALWAYS call check_availability BEFORE scheduling with other people
   - ALWAYS call resolve_contact to get email addresses before scheduling with someone by name
   - NEVER assume someone's email — always look it up

2. ALWAYS CONFIRM BEFORE EXECUTING
   - Before creating, updating, or deleting events: present the details and ask "Should I go ahead?"
   - Before sending emails: show a summary and ask for confirmation
   - Present 2-3 time options when suggesting slots, never just pick one
   - Exception: if the user gives an explicit, complete instruction ("create a meeting at 3pm tomorrow called Standup"), you may confirm inline: "I'll create 'Standup' for tomorrow 3-3:30pm. Confirm?"

3. SMART TIME AWARENESS
   - Outdoor activities (pickleball, tennis, hiking, running): only suggest daylight hours (8am-6pm), prefer weekends
   - Gym/workout: prefer early morning (6-8am) or evening (5-8pm)
   - Work meetings: 9am-5pm on weekdays only
   - Social events (dinner, drinks, hangouts): 6-10pm
   - Never suggest times before 7am or after 10pm unless the user explicitly asks
   - Add 15-minute buffer between back-to-back events
   - Consider travel time for events with locations

4. CONTACT RESOLUTION
   - When the user mentions a person by name, ALWAYS use resolve_contact first
   - If multiple matches found: "I found 2 matches for 'Bharat': 1) Bharat Mekala (bharat@gmail.com) 2) Bharat Singh (bsingh@co.com). Which one?"
   - If no match found: "I couldn't find [name] in your contacts. What's their email?"
   - Never fabricate or guess email addresses

5. MULTI-PARTY SCHEDULING
   - Step 1: resolve_contact for each person
   - Step 2: check_availability for all emails
   - Step 3a: If ALL calendars accessible → find mutual free times → present options
   - Step 3b: If ANY calendar NOT accessible → for accessible ones, find mutual free times. For inaccessible ones, use send_availability_poll to send a poll
   - Step 4: Present options to user
   - Step 5: On confirmation → create_calendar_event with all attendees

6. WORKOUT/PLAN GENERATION
   - When asked to create a gym plan, meal plan, or any multi-day structured plan:
   - First call find_open_slots to find available times matching the activity type
   - Generate detailed, specific workout descriptions (exercises, sets, reps, rest periods)
   - Create each event with a rich HTML description
   - Ask for confirmation before creating the series

7. EMAIL COORDINATION
   - When sending availability to someone, use send_availability_poll (creates a poll page)
   - The poll creates a web page where they can pick times
   - Also mention in the email they can just reply with their preferred time
   - Monitor for poll responses and email replies

8. COMMUNICATION STYLE
   - Be concise — this is iMessage, not email. Keep messages short.
   - Use emoji sparingly but naturally: ✅ for confirmations, 📅 for calendar stuff, ⏰ for time
   - When presenting options, use numbered lists
   - Don't repeat back everything — be conversational
   - If something goes wrong, explain briefly and offer alternatives
   - Never mention tool names, API errors, or technical details to the user

9. ERROR HANDLING
   - If Google auth is missing: "You'll need to connect your Google account first! Here's the link: [auth_url]"
   - If a tool fails: retry once silently. If it fails again, tell the user something went wrong and suggest trying again
   - If you can't find calendar events the user mentioned: "I couldn't find that event. Can you give me the exact name or date?"
"""
```

---

## 15. SMART TIME ENGINE <a name="15-smart-time-engine"></a>

File: `app/services/smart_time.py`

```python
from dataclasses import dataclass

@dataclass
class ActivityTimeProfile:
    """Defines when an activity is appropriate to schedule."""
    earliest_hour: int
    latest_hour: int
    preferred_duration_minutes: int
    prefer_weekends: bool
    category: str  # "outdoor", "fitness", "social", "work", "flexible"

# Default profiles — the LLM can override these with explicit user preferences
ACTIVITY_PROFILES = {
    # Outdoor sports
    "pickleball": ActivityTimeProfile(9, 17, 90, True, "outdoor"),
    "tennis": ActivityTimeProfile(8, 18, 90, True, "outdoor"),
    "golf": ActivityTimeProfile(7, 16, 240, True, "outdoor"),
    "hiking": ActivityTimeProfile(7, 15, 180, True, "outdoor"),
    "running": ActivityTimeProfile(6, 19, 60, False, "outdoor"),
    "soccer": ActivityTimeProfile(9, 18, 90, True, "outdoor"),
    "basketball": ActivityTimeProfile(9, 21, 90, True, "outdoor"),
    
    # Fitness
    "gym": ActivityTimeProfile(5, 21, 60, False, "fitness"),
    "workout": ActivityTimeProfile(5, 21, 60, False, "fitness"),
    "yoga": ActivityTimeProfile(6, 20, 60, False, "fitness"),
    "crossfit": ActivityTimeProfile(5, 19, 60, False, "fitness"),
    "swimming": ActivityTimeProfile(6, 20, 60, False, "fitness"),
    
    # Social
    "dinner": ActivityTimeProfile(18, 21, 120, False, "social"),
    "lunch": ActivityTimeProfile(11, 14, 90, False, "social"),
    "brunch": ActivityTimeProfile(9, 13, 120, True, "social"),
    "coffee": ActivityTimeProfile(8, 17, 60, False, "social"),
    "drinks": ActivityTimeProfile(17, 22, 120, False, "social"),
    "happy hour": ActivityTimeProfile(16, 19, 120, False, "social"),
    "party": ActivityTimeProfile(18, 23, 180, True, "social"),
    "hangout": ActivityTimeProfile(10, 22, 120, True, "social"),
    
    # Work
    "meeting": ActivityTimeProfile(9, 17, 30, False, "work"),
    "standup": ActivityTimeProfile(9, 11, 15, False, "work"),
    "1:1": ActivityTimeProfile(9, 17, 30, False, "work"),
    "interview": ActivityTimeProfile(9, 17, 60, False, "work"),
    "review": ActivityTimeProfile(9, 17, 60, False, "work"),
    
    # Flexible
    "study": ActivityTimeProfile(8, 22, 120, False, "flexible"),
    "errands": ActivityTimeProfile(9, 18, 60, False, "flexible"),
    "appointment": ActivityTimeProfile(8, 18, 60, False, "flexible"),
}

def get_activity_profile(activity_name: str) -> ActivityTimeProfile:
    """
    Get time constraints for an activity.
    Fuzzy matches against the ACTIVITY_PROFILES dictionary.
    Falls back to a general "flexible" profile if no match.
    """
    activity_lower = activity_name.lower().strip()

    # Direct match
    if activity_lower in ACTIVITY_PROFILES:
        return ACTIVITY_PROFILES[activity_lower]

    # Partial match (e.g., "play pickleball" → "pickleball")
    for key, profile in ACTIVITY_PROFILES.items():
        if key in activity_lower or activity_lower in key:
            return profile

    # Default: flexible profile
    return ActivityTimeProfile(8, 21, 60, False, "flexible")

def rank_time_slots(slots: list[dict], profile: ActivityTimeProfile) -> list[dict]:
    """
    Rank available time slots based on activity profile preferences.
    Prioritizes: preferred times > weekends (if applicable) > sooner dates.
    Returns the top 3 slots.
    """
    from datetime import datetime

    def score_slot(slot):
        start = datetime.fromisoformat(slot["start"])
        hour = start.hour
        is_weekend = start.weekday() >= 5

        score = 0

        # Prefer middle of the acceptable range
        mid_hour = (profile.earliest_hour + profile.latest_hour) / 2
        hour_distance = abs(hour - mid_hour)
        score -= hour_distance * 2  # Penalize distance from ideal time

        # Prefer weekends for weekend-preferred activities
        if profile.prefer_weekends and is_weekend:
            score += 10

        # Prefer sooner dates (slight preference)
        days_from_now = (start - datetime.now(start.tzinfo)).days
        score -= days_from_now * 0.5

        return score

    ranked = sorted(slots, key=score_slot, reverse=True)
    return ranked[:3]
```

---

## 16. CONVERSATION MEMORY MANAGEMENT <a name="16-conversation-memory"></a>

File: `app/db/messages.py`

```python
from app.db.client import supabase
from datetime import datetime, timezone

async def save_message(conversation_id: str, role: str, content: str) -> dict:
    """Save a message to the database."""
    # Rough token estimate: 1 token ≈ 4 characters
    token_count = len(content) // 4

    result = supabase.table("messages").insert({
        "conversation_id": conversation_id,
        "role": role,
        "content": content,
        "token_count": token_count,
    }).execute()

    return result.data[0]

async def get_recent_messages(conversation_id: str, limit: int = 10) -> list[dict]:
    """Get the most recent messages for a conversation, ordered chronologically."""
    result = supabase.table("messages")\
        .select("role, content, created_at")\
        .eq("conversation_id", conversation_id)\
        .order("created_at", desc=True)\
        .limit(limit)\
        .execute()

    # Reverse so they're in chronological order
    return list(reversed(result.data))

async def get_total_token_count(conversation_id: str) -> int:
    """Get total estimated tokens for all messages in a conversation."""
    result = supabase.table("messages")\
        .select("token_count")\
        .eq("conversation_id", conversation_id)\
        .execute()

    return sum(m.get("token_count", 0) for m in result.data)

async def delete_old_messages(conversation_id: str, keep_recent: int = 10) -> int:
    """Delete messages older than the N most recent."""
    recent = supabase.table("messages")\
        .select("id")\
        .eq("conversation_id", conversation_id)\
        .order("created_at", desc=True)\
        .limit(keep_recent)\
        .execute()

    recent_ids = [m["id"] for m in recent.data]

    if recent_ids:
        supabase.table("messages")\
            .delete()\
            .eq("conversation_id", conversation_id)\
            .not_.in_("id", recent_ids)\
            .execute()

    return len(recent_ids)
```

---

## 17. ASYNC WEBHOOK PROCESSING <a name="17-async-processing"></a>

File: `app/main.py`

```python
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import logging

from app.config import settings
from app.services.linq import linq_client
from app.webhooks.linq_webhook import (
    verify_linq_signature, is_duplicate_webhook,
    mark_webhook_processed, parse_linq_webhook,
)
from app.agent.loop import run_agent
from app.db.users import get_or_create_user
from app.db.client import supabase
from app.web.auth_routes import auth_router
from app.web.poll_routes import poll_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: register Linq webhook
    try:
        webhook_url = f"{settings.app_base_url}/webhook/linq"
        await linq_client.register_webhook(webhook_url)
        logger.info(f"Linq webhook registered: {webhook_url}")
    except Exception as e:
        logger.warning(f"Could not register Linq webhook (may already exist): {e}")
    yield
    # Shutdown: nothing to clean up

app = FastAPI(title="ScheduleGPT", lifespan=lifespan)

# Mount web routes
app.include_router(auth_router, prefix="/auth")
app.include_router(poll_router, prefix="/poll")

# Health check
@app.get("/health")
async def health():
    return {"status": "ok", "service": "schedulegpt"}

# ─── LINQ WEBHOOK ENDPOINT ───────────────────────────────────
@app.post("/webhook/linq")
async def linq_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Receive incoming iMessage via Linq webhook.
    CRITICAL: Return 200 within 2 seconds, process async.
    """
    body = await request.body()
    timestamp = request.headers.get("X-Linq-Timestamp", "")
    signature = request.headers.get("X-Linq-Signature", "")

    # Verify HMAC signature
    if not verify_linq_signature(body, timestamp, signature):
        logger.warning("Invalid Linq webhook signature")
        return JSONResponse({"error": "invalid signature"}, status_code=401)

    payload = await request.json()
    parsed = parse_linq_webhook(payload)

    # Only process inbound text messages
    # Handle both "message.received" and "message.created" (Linq uses both)
    # Also handle "message" (flat variant seen in some integrations)
    valid_events = ("message.received", "message.created", "message")
    if parsed["event_type"] not in valid_events:
        return {"status": "ignored"}

    if not parsed["text"]:
        return {"status": "no text"}

    # Idempotency check
    if await is_duplicate_webhook(parsed["message_id"]):
        return {"status": "duplicate"}

    await mark_webhook_processed(parsed["message_id"])

    # Send typing indicator immediately
    if parsed["chat_id"]:
        background_tasks.add_task(linq_client.send_typing_indicator, parsed["chat_id"])

    # Process message in background
    background_tasks.add_task(
        process_incoming_message,
        parsed["from_phone"],
        parsed["text"],
        parsed["chat_id"],
    )

    return {"status": "accepted"}

async def process_incoming_message(phone: str, text: str, chat_id: str):
    """
    Process an incoming iMessage asynchronously.
    This runs AFTER the webhook has returned 200.
    """
    try:
        # Get or create user
        user = await get_or_create_user(phone)
        user_id = user["id"]

        # Check if user has completed onboarding (Google account linked)
        if not user.get("onboarding_complete"):
            await handle_onboarding(user, chat_id, text)
            return

        # Run the agent
        response = await run_agent(
            user_id=user_id,
            user_message=text,
            chat_id=chat_id,
        )

        # Send reply via Linq
        # Split long messages (iMessage has ~20K char limit but shorter is better)
        if len(response) > 1500:
            chunks = split_message(response, max_length=1500)
            for chunk in chunks:
                await linq_client.send_message(chat_id, chunk)
        else:
            await linq_client.send_message(chat_id, response)

    except Exception as e:
        logger.error(f"Error processing message from {phone}: {e}", exc_info=True)
        try:
            await linq_client.send_message(
                chat_id,
                "Sorry, something went wrong on my end 😅 Try again in a moment!"
            )
        except Exception:
            pass

async def handle_onboarding(user: dict, chat_id: str, text: str):
    """Handle the onboarding flow for new users."""
    from app.services.google_auth import get_auth_url

    auth_url = get_auth_url(user["phone_number"])

    welcome_msg = (
        f"Hey! 👋 I'm ScheduleGPT — your personal scheduling assistant.\n\n"
        f"To get started, I need to connect to your Google Calendar and Gmail. "
        f"Tap the link below to sign in:\n\n{auth_url}\n\n"
        f"Once connected, just text me things like:\n"
        f"• \"What's on my calendar today?\"\n"
        f"• \"Schedule lunch with Sarah next week\"\n"
        f"• \"Create a 5-day gym plan\""
    )
    await linq_client.send_message(chat_id, welcome_msg)

def split_message(text: str, max_length: int = 1500) -> list[str]:
    """Split a long message into chunks at paragraph boundaries."""
    if len(text) <= max_length:
        return [text]

    chunks = []
    current = ""

    for paragraph in text.split("\n\n"):
        if len(current) + len(paragraph) + 2 > max_length:
            if current:
                chunks.append(current.strip())
            current = paragraph
        else:
            current += "\n\n" + paragraph if current else paragraph

    if current:
        chunks.append(current.strip())

    return chunks

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

---

## 18. MULTI-PARTY SCHEDULING FLOW <a name="18-multi-party-scheduling"></a>

The agent handles this automatically via the system prompt rules, but here's the exact flow for the tool executor:

File: `app/agent/tool_executor.py`

```python
import json
from app.services import calendar_service, gmail_service, contacts_service
from app.services.smart_time import get_activity_profile, rank_time_slots
from app.db.pending_actions import create_pending_action
from app.db.client import supabase
import uuid

async def execute_tool(tool_name: str, tool_input: dict, user_id: str, conversation_id: str) -> dict:
    """Route tool calls to their implementations."""

    if tool_name == "resolve_contact":
        contacts = await contacts_service.search_contacts(user_id, tool_input["query"])
        if not contacts:
            return {"found": False, "message": f"No contacts found matching '{tool_input['query']}'"}
        return {"found": True, "contacts": contacts}

    elif tool_name == "list_calendar_events":
        from datetime import datetime
        import pytz
        from app.db.users import get_user
        user = await get_user(user_id)
        user_tz = user.get("timezone", "America/Los_Angeles")
        tz = pytz.timezone(user_tz)
        start = tz.localize(datetime.strptime(tool_input["date_start"], "%Y-%m-%d"))
        end = tz.localize(datetime.strptime(tool_input["date_end"], "%Y-%m-%d").replace(hour=23, minute=59))
        events = await calendar_service.list_events(user_id, start.isoformat(), end.isoformat())
        return {"events": events, "count": len(events)}

    elif tool_name == "check_availability":
        from datetime import datetime
        import pytz
        from app.db.users import get_user
        user = await get_user(user_id)
        user_tz = user.get("timezone", "America/Los_Angeles")
        tz = pytz.timezone(user_tz)
        start = tz.localize(datetime.strptime(tool_input["date_start"], "%Y-%m-%d"))
        end = tz.localize(datetime.strptime(tool_input["date_end"], "%Y-%m-%d").replace(hour=23, minute=59))
        result = await calendar_service.check_freebusy(
            user_id, tool_input["emails"], start.isoformat(), end.isoformat()
        )
        return result

    elif tool_name == "find_open_slots":
        slots = await calendar_service.find_available_slots(
            user_id,
            tool_input["date_start"],
            tool_input["date_end"],
            tool_input["duration_minutes"],
            tool_input.get("earliest_hour", 8),
            tool_input.get("latest_hour", 21),
        )
        # Optionally rank by activity profile (if context available)
        return {"available_slots": slots[:10], "total_found": len(slots)}

    elif tool_name == "create_calendar_event":
        result = await calendar_service.create_event(
            user_id,
            summary=tool_input["summary"],
            start_time=tool_input["start_time"],
            end_time=tool_input["end_time"],
            description=tool_input.get("description", ""),
            location=tool_input.get("location", ""),
            attendees=tool_input.get("attendees", []),
            add_meet_link=tool_input.get("add_meet_link", False),
        )
        return {"success": True, "event": result}

    elif tool_name == "update_calendar_event":
        updates = {}
        for key in ["summary", "start_time", "end_time", "description", "location"]:
            if key in tool_input and tool_input[key]:
                updates[key] = tool_input[key]
        result = await calendar_service.update_event(user_id, tool_input["event_id"], updates)
        return {"success": True, "event": result}

    elif tool_name == "delete_calendar_event":
        await calendar_service.delete_event(user_id, tool_input["event_id"])
        return {"success": True, "message": "Event deleted and attendees notified."}

    elif tool_name == "send_email":
        result = await gmail_service.send_email(
            user_id,
            to=tool_input["to"],
            subject=tool_input["subject"],
            body_html=f"<p>{tool_input['body']}</p>",
        )
        return {"success": True, "message_id": result["message_id"]}

    elif tool_name == "send_availability_poll":
        # Create poll in database
        poll_id = str(uuid.uuid4())
        from app.db.users import get_user
        user = await get_user(user_id)

        supabase.table("polls").insert({
            "id": poll_id,
            "user_id": user_id,
            "title": tool_input["event_title"],
            "proposed_times": tool_input["proposed_times"],
            "participants": tool_input["participants"],
            "status": "open",
        }).execute()

        # Send email to each participant
        results = []
        for participant in tool_input["participants"]:
            email_result = await gmail_service.send_availability_email(
                user_id=user_id,
                to_email=participant["email"],
                to_name=participant["name"],
                user_name=user.get("display_name", "Someone"),
                event_title=tool_input["event_title"],
                poll_id=poll_id,
                proposed_times=tool_input["proposed_times"],
            )
            results.append({
                "name": participant["name"],
                "email": participant["email"],
                "sent": True,
            })

        return {
            "success": True,
            "poll_id": poll_id,
            "emails_sent": results,
            "poll_url": f"https://your-app.up.railway.app/poll/{poll_id}",
        }

    else:
        return {"error": f"Unknown tool: {tool_name}"}
```

---

## 19. WORKOUT/ITINERARY PLAN GENERATION <a name="19-structured-content"></a>

The agent handles this naturally through the system prompt. When the user says "create a 5-day gym plan," Claude will:

1. Call `find_open_slots` with `earliest_hour=5, latest_hour=21, duration_minutes=60` across the next 7 days
2. Pick 5 slots that match gym preferences (early morning or evening)
3. Generate workout descriptions with exercises, sets, reps
4. Present the plan to the user for confirmation
5. On confirmation, call `create_calendar_event` 5 times with HTML descriptions

Example HTML description Claude would generate for an event:

```html
<b>💪 Day 1: Push (Chest, Shoulders, Triceps)</b><br><br>
<b>Warm-up (5 min):</b> Light cardio + arm circles<br><br>
<b>Main Workout:</b><br>
<ul>
  <li>Bench Press: 4 sets × 8-10 reps</li>
  <li>Overhead Press: 3 sets × 10 reps</li>
  <li>Incline Dumbbell Press: 3 sets × 12 reps</li>
  <li>Lateral Raises: 3 sets × 15 reps</li>
  <li>Tricep Pushdowns: 3 sets × 12 reps</li>
  <li>Dips: 2 sets × max reps</li>
</ul>
<b>Cool-down:</b> Stretch chest and shoulders (5 min)
```

---

## 20. ONBOARDING FLOW <a name="20-onboarding-flow"></a>

1. User texts the Linq phone number for the first time
2. System creates a user record with their phone number
3. System sends welcome message with Google OAuth link
4. User taps link → Google consent screen → authorizes Calendar + Gmail + Contacts
5. OAuth callback stores tokens in `linked_accounts`
6. System syncs contacts to `contacts_cache` (background)
7. System sends confirmation: "You're all set! 🎉 Your Google Calendar and Gmail are connected. What can I help you schedule?"
8. System marks `onboarding_complete = TRUE`

File: `app/web/auth_routes.py`

```python
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from app.services.google_auth import create_auth_flow, exchange_code
from app.services.contacts_service import sync_contacts_to_cache
from app.services.linq import linq_client
from app.db.users import update_user
from app.db.client import supabase
import logging

logger = logging.getLogger(__name__)

auth_router = APIRouter()

@auth_router.get("/google")
async def google_auth_start(phone: str):
    """Start the Google OAuth flow. Called when user taps the auth link."""
    from app.services.google_auth import get_auth_url
    auth_url = get_auth_url(phone)
    from fastapi.responses import RedirectResponse
    return RedirectResponse(auth_url)

@auth_router.get("/google/callback")
async def google_auth_callback(request: Request):
    """Handle the OAuth callback from Google."""
    code = request.query_params.get("code")
    state = request.query_params.get("state")  # This is the user's phone number

    if not code or not state:
        return HTMLResponse("<h1>Error: Missing authorization code</h1>", status_code=400)

    try:
        result = await exchange_code(code, state)
        user_id = result["user_id"]
        email = result["email"]

        # Mark onboarding complete
        await update_user(user_id, {
            "onboarding_complete": True,
            "display_name": email.split("@")[0],  # Default display name from email
        })

        # Sync contacts in background (don't block the response)
        import asyncio
        asyncio.create_task(sync_contacts_to_cache(user_id))

        # Notify user via iMessage that auth is complete
        user_data = supabase.table("users").select("phone_number").eq("id", user_id).execute()
        conv_data = supabase.table("conversations").select("linq_chat_id").eq("user_id", user_id).execute()

        if conv_data.data and conv_data.data[0].get("linq_chat_id"):
            # User already has a chat — send confirmation to existing chat
            await linq_client.send_message(
                conv_data.data[0]["linq_chat_id"],
                f"You're all set! 🎉 I've connected your Google account ({email}). Your Calendar, Gmail, and Contacts are now linked.\n\nTry saying: \"What's on my calendar today?\"",
            )
        elif user_data.data:
            # No existing chat — create a new one to the user's phone
            try:
                chat_result = await linq_client.create_chat(
                    to_phone=user_data.data[0]["phone_number"],
                    message=f"You're all set! 🎉 I've connected your Google account ({email}). Your Calendar, Gmail, and Contacts are now linked.\n\nTry saying: \"What's on my calendar today?\"",
                )
                # Save the new chat_id for future messages
                from app.db.conversations import get_or_create_conversation
                await get_or_create_conversation(user_id, chat_result.get("chatId", chat_result.get("chat_id", "")))
            except Exception as e:
                logger.warning(f"Could not send auth confirmation via iMessage: {e}")

        return HTMLResponse("""
        <html>
        <body style="font-family: -apple-system, sans-serif; display: flex; justify-content: center; align-items: center; min-height: 100vh; background: #f5f5f7;">
            <div style="text-align: center; padding: 40px;">
                <h1 style="font-size: 48px;">🎉</h1>
                <h2>You're connected!</h2>
                <p>Go back to iMessage and start scheduling.</p>
                <p style="color: #666;">You can close this tab.</p>
            </div>
        </body>
        </html>
        """)

    except Exception as e:
        return HTMLResponse(f"<h1>Error connecting Google: {str(e)}</h1>", status_code=500)
```

---

## 21. AVAILABILITY POLL PAGE <a name="21-web-dashboard"></a>

File: `app/web/poll_routes.py`

```python
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from app.db.client import supabase

poll_router = APIRouter()

@poll_router.get("/{poll_id}")
async def view_poll(poll_id: str):
    """Render the availability poll page."""
    poll_result = supabase.table("polls").select("*").eq("id", poll_id).execute()

    if not poll_result.data:
        return HTMLResponse("<h1>Poll not found</h1>", status_code=404)

    p = poll_result.data[0]
    times_html = ""
    for i, t in enumerate(p["proposed_times"]):
        times_html += f"""
        <label style="display: block; padding: 12px; margin: 8px 0; background: #f5f5f7; border-radius: 8px; cursor: pointer;">
            <input type="checkbox" name="times" value="{i}" style="margin-right: 8px;">
            {t['label']}
        </label>
        """

    return HTMLResponse(f"""
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Pick a time — {p['title']}</title>
    </head>
    <body style="font-family: -apple-system, sans-serif; max-width: 500px; margin: 0 auto; padding: 20px;">
        <h2>📅 {p['title']}</h2>
        <p>Select all times that work for you:</p>
        <form method="POST" action="/poll/{poll_id}/respond">
            {times_html}
            <input type="email" name="email" placeholder="Your email" required
                   style="width: 100%; padding: 12px; margin: 16px 0; border: 1px solid #ddd; border-radius: 8px; font-size: 16px;">
            <input type="text" name="name" placeholder="Your name" required
                   style="width: 100%; padding: 12px; margin: 0 0 16px; border: 1px solid #ddd; border-radius: 8px; font-size: 16px;">
            <textarea name="message" placeholder="Any notes? (optional)"
                      style="width: 100%; padding: 12px; margin: 0 0 16px; border: 1px solid #ddd; border-radius: 8px; font-size: 16px; min-height: 60px;"></textarea>
            <button type="submit"
                    style="width: 100%; padding: 14px; background: #007AFF; color: white; border: none; border-radius: 8px; font-size: 16px; font-weight: 600; cursor: pointer;">
                Submit
            </button>
        </form>
    </body>
    </html>
    """)

@poll_router.post("/{poll_id}/respond")
async def submit_poll_response(poll_id: str, request: Request):
    """Handle a poll response submission."""
    form = await request.form()
    email = form.get("email", "")
    name = form.get("name", "")
    message = form.get("message", "")

    # Starlette's FormData: use .multi_items() to get all values for "times" checkboxes
    selected = [v for k, v in form.multi_items() if k == "times"]

    # Save response
    supabase.table("poll_responses").upsert({
        "poll_id": poll_id,
        "respondent_email": email,
        "respondent_name": name,
        "selected_times": [int(s) for s in selected],
        "message": message,
    }, on_conflict="poll_id,respondent_email").execute()

    # Check if all participants have responded
    poll_result = supabase.table("polls").select("*").eq("id", poll_id).execute()
    if not poll_result.data:
        return HTMLResponse("<h1>Poll not found</h1>", status_code=404)
    poll_data = poll_result.data[0]
    responses = supabase.table("poll_responses").select("*").eq("poll_id", poll_id).execute()

    total_participants = len(poll_data["participants"])
    total_responses = len(responses.data)

    # If all responded, notify the organizer via iMessage
    if total_responses >= total_participants:
        # Find the consensus time(s)
        from collections import Counter
        all_selections = []
        for r in responses.data:
            all_selections.extend(r["selected_times"])

        counter = Counter(all_selections)
        best_time_idx = counter.most_common(1)[0][0] if counter else 0
        best_time = poll_data["proposed_times"][best_time_idx]

        # Notify organizer
        from app.services.linq import linq_client
        conv_result = supabase.table("conversations").select("linq_chat_id").eq("user_id", poll_data["user_id"]).execute()

        if conv_result.data and conv_result.data[0].get("linq_chat_id"):
            names = [r["respondent_name"] for r in responses.data]
            await linq_client.send_message(
                conv_result.data[0]["linq_chat_id"],
                f"📊 Everyone responded to your \"{poll_data['title']}\" poll!\n\n"
                f"Best time: {best_time['label']}\n"
                f"All {', '.join(names)} are available then.\n\n"
                f"Should I create the event and send invites?"
            )

    return HTMLResponse("""
    <html>
    <body style="font-family: -apple-system, sans-serif; display: flex; justify-content: center; align-items: center; min-height: 100vh;">
        <div style="text-align: center;">
            <h1>✅</h1>
            <h2>Thanks! Your response has been recorded.</h2>
            <p style="color: #666;">You can close this tab.</p>
        </div>
    </body>
    </html>
    """)
```

---

## 22. DEPLOYMENT TO RAILWAY <a name="22-deployment"></a>

File: `Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

File: `railway.toml`

```toml
[build]
builder = "dockerfile"
dockerfilePath = "Dockerfile"

[deploy]
startCommand = "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"
healthcheckPath = "/health"
healthcheckTimeout = 300
restartPolicyType = "always"
```

### Deployment Steps:

1. Create a Railway account at https://railway.app
2. Install Railway CLI: `npm i -g @railway/cli`
3. `railway login`
4. `railway init` (in the project root)
5. Set all environment variables: `railway variables set LINQ_API_TOKEN=xxx ...`
6. `railway up` — deploys the Docker container
7. Get your public URL: `railway domain` → something like `schedulegpt-production.up.railway.app`
8. Update `.env` with the public URL for `APP_BASE_URL` and `GOOGLE_REDIRECT_URI`
9. Update Google Cloud Console with the redirect URI
10. Redeploy: `railway up`

---

## 23. OPEN SOURCE CONFIGURATION <a name="23-open-source"></a>

File: `README.md` (template)

```markdown
# ScheduleGPT 📅🤖

An AI scheduling secretary you control entirely via iMessage. Text it to manage your calendar, coordinate with friends, create workout plans, and more.

## Quick Start

### Prerequisites
- Python 3.11+
- A [Linq](https://dashboard.linqapp.com/sandbox-signup/) account (free sandbox)
- A [Google Cloud](https://console.cloud.google.com) project
- An [Anthropic](https://console.anthropic.com) API key
- A [Supabase](https://supabase.com) project (free tier)
- A [Railway](https://railway.app) account ($5/mo hobby)

### Setup

1. **Clone and install:**
   ```bash
   git clone https://github.com/yourname/schedulegpt.git
   cd schedulegpt
   pip install -r requirements.txt
   ```

2. **Configure environment:** Copy `.env.example` to `.env` and fill in your API keys.

3. **Set up Supabase:** Run `sql/schema.sql` in your Supabase SQL Editor.

4. **Set up Google Cloud:**
   - Enable Calendar API, Gmail API, People API
   - Create OAuth 2.0 credentials (Web application)
   - Add redirect URI: `https://your-app.up.railway.app/auth/google/callback`

5. **Deploy to Railway:**
   ```bash
   railway login
   railway init
   railway variables set LINQ_API_TOKEN=xxx ANTHROPIC_API_KEY=xxx ...
   railway up
   ```

6. **Register Linq webhook:** The app auto-registers on startup, or manually:
   ```bash
   linq webhooks create --url https://your-app.up.railway.app/webhook/linq
   ```

7. **Text your Linq phone number** — the bot will guide you through Google sign-in!

## Architecture
[See plan.md for complete technical details]

## License
MIT
```

---

## 24. TESTING STRATEGY <a name="24-testing"></a>

For the hackathon, focus on integration tests that verify the end-to-end flow:

```python
# tests/test_agent_loop.py
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_simple_schedule_request():
    """Test that 'what's on my calendar today' calls list_calendar_events."""
    with patch("app.agent.tool_executor.execute_tool") as mock_exec:
        mock_exec.return_value = {"events": [], "count": 0}
        # ... run agent and verify tool was called

@pytest.mark.asyncio
async def test_contact_resolution():
    """Test that mentioning a name triggers resolve_contact."""
    # ...

@pytest.mark.asyncio
async def test_webhook_signature_validation():
    """Test HMAC signature verification."""
    from app.webhooks.linq_webhook import verify_linq_signature
    # Valid signature
    assert verify_linq_signature(b"test", "9999999999", "sha256=...")
    # Invalid signature
    assert not verify_linq_signature(b"test", "9999999999", "sha256=wrong")
```

### Manual Testing Checklist (Demo Prep):
- [ ] Text the number → receive onboarding message with Google link
- [ ] Complete Google OAuth → receive confirmation
- [ ] "What's on my calendar today?" → lists events
- [ ] "Schedule pickleball with [name] this weekend" → full multi-party flow
- [ ] "Create a 5-day gym plan" → 5 events created with workout descriptions
- [ ] "Cancel my gym session tomorrow" → deletes event
- [ ] "Move my 3pm to 4pm" → reschedules event
- [ ] Availability poll page works on mobile
- [ ] Error cases: unknown contact, no free time, network error

---

## 25. FILE-BY-FILE IMPLEMENTATION GUIDE <a name="25-file-by-file"></a>

**Build order** — implement files in this exact sequence to avoid dependency issues:

| Order | File | Dependencies | Notes |
|-------|------|-------------|-------|
| 1 | `requirements.txt` | None | Install with `pip install -r requirements.txt` |
| 2 | `app/config.py` | None | Load environment variables |
| 3 | `app/db/client.py` | config | Initialize Supabase client |
| 4 | `sql/schema.sql` | None | Run in Supabase SQL Editor |
| 5 | `app/db/users.py` | db/client | User CRUD |
| 6 | `app/db/messages.py` | db/client | Message history |
| 7 | `app/db/conversations.py` | db/client | Conversation management |
| 8 | `app/db/pending_actions.py` | db/client | Pending action CRUD |
| 9 | `app/db/contacts_cache.py` | db/client | Contact cache CRUD |
| 10 | `app/utils/crypto.py` | None | HMAC helpers |
| 11 | `app/utils/time_utils.py` | None | Timezone/formatting helpers |
| 12 | `app/services/google_auth.py` | config, db | OAuth2 flow |
| 13 | `app/services/calendar_service.py` | google_auth | Calendar API wrapper |
| 14 | `app/services/gmail_service.py` | google_auth, config | Gmail API wrapper |
| 15 | `app/services/contacts_service.py` | google_auth, db | People API + cache |
| 16 | `app/services/linq.py` | config | Linq API client |
| 17 | `app/services/smart_time.py` | None | Activity time profiles |
| 18 | `app/webhooks/linq_webhook.py` | config, db, crypto | Webhook verification |
| 19 | `app/agent/tools.py` | None | Tool JSON schemas |
| 20 | `app/agent/system_prompt.py` | db | System prompt builder |
| 21 | `app/agent/tool_executor.py` | all services | Tool routing |
| 22 | `app/agent/loop.py` | tools, tool_executor, system_prompt, db | Agent brain |
| 23 | `app/web/auth_routes.py` | google_auth, linq, db | OAuth routes |
| 24 | `app/web/poll_routes.py` | db, linq | Poll page |
| 25 | `app/main.py` | everything | FastAPI app entry point |
| 26 | `Dockerfile` | None | Container config |
| 27 | `railway.toml` | None | Railway deployment config |

### DB helper stubs needed:

**`app/db/client.py`:**
```python
from supabase import create_client
from app.config import settings

supabase = create_client(settings.supabase_url, settings.supabase_service_key)
```

**`app/db/users.py`:**
```python
from app.db.client import supabase

async def get_or_create_user(phone: str) -> dict:
    result = supabase.table("users").select("*").eq("phone_number", phone).execute()
    if result.data:
        return result.data[0]
    new_user = supabase.table("users").insert({"phone_number": phone}).execute()
    return new_user.data[0]

async def get_user(user_id: str) -> dict:
    result = supabase.table("users").select("*").eq("id", user_id).execute()
    if not result.data:
        return {"timezone": "America/Los_Angeles", "display_name": "there"}
    return result.data[0]

async def get_user_by_phone(phone: str) -> dict | None:
    result = supabase.table("users").select("*").eq("phone_number", phone).execute()
    return result.data[0] if result.data else None

async def update_user(user_id: str, updates: dict) -> dict:
    result = supabase.table("users").update(updates).eq("id", user_id).execute()
    return result.data[0] if result.data else {}
```

**`app/db/contacts_cache.py`:**
```python
from app.db.client import supabase

async def search_cached_contacts(user_id: str, query: str, limit: int = 5) -> list[dict]:
    """Search contacts cache by display name (case-insensitive partial match)."""
    result = supabase.table("contacts_cache")\
        .select("display_name, email, phone")\
        .eq("user_id", user_id)\
        .ilike("display_name", f"%{query}%")\
        .limit(limit)\
        .execute()
    return result.data

async def upsert_cached_contact(user_id: str, display_name: str, email: str, phone: str = "", source: str = "google_contacts"):
    """Add or update a contact in the cache."""
    if not email:
        return  # Skip contacts without email — not useful for scheduling
    supabase.table("contacts_cache").upsert(
        {
            "user_id": user_id,
            "display_name": display_name,
            "email": email,
            "phone": phone,
            "source": source,
        },
        on_conflict="user_id,email"
    ).execute()

async def increment_interaction_count(user_id: str, email: str):
    """Bump interaction count when a contact is used in scheduling."""
    # Fetch current count
    result = supabase.table("contacts_cache")\
        .select("id, interaction_count")\
        .eq("user_id", user_id)\
        .eq("email", email)\
        .execute()
    if result.data:
        current = result.data[0].get("interaction_count", 0)
        supabase.table("contacts_cache")\
            .update({"interaction_count": current + 1})\
            .eq("id", result.data[0]["id"])\
            .execute()

async def get_frequent_contacts(user_id: str, limit: int = 10) -> list[dict]:
    """Get the user's most frequently referenced contacts."""
    result = supabase.table("contacts_cache")\
        .select("display_name, email, phone, interaction_count")\
        .eq("user_id", user_id)\
        .order("interaction_count", desc=True)\
        .limit(limit)\
        .execute()
    return result.data
```

**`app/db/conversations.py`:**
```python
from app.db.client import supabase

async def get_or_create_conversation(user_id: str, chat_id: str) -> dict:
    result = supabase.table("conversations").select("*").eq("user_id", user_id).execute()
    if result.data:
        conv = result.data[0]
        if chat_id and conv.get("linq_chat_id") != chat_id:
            supabase.table("conversations").update({"linq_chat_id": chat_id}).eq("id", conv["id"]).execute()
            conv["linq_chat_id"] = chat_id
        return conv
    new_conv = supabase.table("conversations").insert({
        "user_id": user_id,
        "linq_chat_id": chat_id,
    }).execute()
    return new_conv.data[0]

async def update_summary(conversation_id: str, summary: str):
    supabase.table("conversations").update({
        "summary": summary,
        "summary_token_count": len(summary) // 4,
    }).eq("id", conversation_id).execute()
```

**`app/db/pending_actions.py`:**
```python
from app.db.client import supabase

async def get_pending_actions(conversation_id: str) -> list:
    result = supabase.table("pending_actions")\
        .select("*")\
        .eq("conversation_id", conversation_id)\
        .eq("status", "pending")\
        .execute()
    return result.data

async def create_pending_action(conversation_id: str, action_type: str, payload: dict) -> dict:
    result = supabase.table("pending_actions").insert({
        "conversation_id": conversation_id,
        "action_type": action_type,
        "action_payload": payload,
    }).execute()
    return result.data[0]

async def update_action_status(action_id: str, status: str):
    supabase.table("pending_actions").update({"status": status}).eq("id", action_id).execute()
```

### Utility file stubs:

**`app/utils/crypto.py`:**
```python
import hmac
import hashlib
import time

def verify_hmac_sha256(secret: str, payload: bytes, signature: str, timestamp: str = None, max_age_seconds: int = 300) -> bool:
    """
    Verify an HMAC-SHA256 webhook signature with optional replay protection.
    Returns False if signature is invalid or timestamp is too old.
    """
    # Replay protection
    if timestamp:
        try:
            ts = int(timestamp)
            if abs(time.time() - ts) > max_age_seconds:
                return False
        except (ValueError, TypeError):
            return False

    expected = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()

    # Handle both "sha256=xxxx" and raw hex formats
    if signature.startswith("sha256="):
        return hmac.compare_digest(f"sha256={expected}", signature)
    return hmac.compare_digest(expected, signature)
```

**`app/utils/time_utils.py`:**
```python
from datetime import datetime, timedelta
import pytz

def now_in_tz(timezone: str = "America/Los_Angeles") -> datetime:
    """Get current datetime in the specified timezone."""
    return datetime.now(pytz.timezone(timezone))

def format_time_range(start_iso: str, end_iso: str, timezone: str = "America/Los_Angeles") -> str:
    """Format a time range as human-readable string. E.g., 'Saturday Jan 15, 2:00 PM - 3:30 PM'"""
    tz = pytz.timezone(timezone)
    start = datetime.fromisoformat(start_iso).astimezone(tz)
    end = datetime.fromisoformat(end_iso).astimezone(tz)

    if start.date() == end.date():
        return f"{start.strftime('%A %b %d, %I:%M %p')} - {end.strftime('%I:%M %p')}"
    return f"{start.strftime('%A %b %d, %I:%M %p')} - {end.strftime('%A %b %d, %I:%M %p')}"

def date_range_to_iso(date_start: str, date_end: str, timezone: str = "America/Los_Angeles") -> tuple[str, str]:
    """Convert YYYY-MM-DD date strings to ISO 8601 datetime strings covering the full day range."""
    tz = pytz.timezone(timezone)
    start = tz.localize(datetime.strptime(date_start, "%Y-%m-%d").replace(hour=0, minute=0, second=0))
    end = tz.localize(datetime.strptime(date_end, "%Y-%m-%d").replace(hour=23, minute=59, second=59))
    return start.isoformat(), end.isoformat()

def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token for English text."""
    return len(text) // 4
```

---

## CRITICAL IMPLEMENTATION NOTES

1. **Linq webhook payload structure** varies between sandbox and production. The defensive parser in `linq_webhook.py` handles three known variants — always test with your actual sandbox to see which format you receive. Log the raw payload on first setup.

2. **Google OAuth `access_type=offline` and `prompt=consent`** are BOTH required to get a refresh token. Without `prompt=consent`, Google only sends the refresh token on the first authorization — if the user revokes and re-authorizes, you won't get one.

3. **The Google People API `searchContacts` requires a warmup request** with an empty query before the first real search per session. Without this, search results may be stale or empty. Do this once during contact sync.

4. **FreeBusy API returns empty busy arrays for TWO reasons**: the person is genuinely free, OR you don't have access to their calendar. ALWAYS check the `errors` array. If there are errors with `reason: "notFound"`, treat it as "unknown" not "free."

5. **Claude's tool-calling loop can iterate up to 15 times.** In practice, simple requests take 1-3 iterations, group scheduling takes 4-8. If it hits 15, something went wrong — return a graceful error.

6. **iMessage has a ~20,000 character limit per message** but aim for under 1,500 characters per message for readability. Split long responses at paragraph boundaries.

7. **Railway's PORT environment variable** is set automatically. Use `${PORT:-8000}` in your start command.

8. **Supabase service key vs anon key**: Use the service role key server-side (bypasses RLS). Never expose it to clients. The anon key is for client-side only (not needed for this project).

9. **Supabase Python client (`supabase-py`) is synchronous** — it does NOT support async/await natively. The `async def` functions in this codebase use `supabase-py` synchronously inside async functions. This works fine because Supabase calls are fast (~50ms) and the hackathon won't hit scale issues. For production, replace with raw `asyncpg` or use `run_in_executor`. Do NOT add `await` before `supabase.table(...)` calls — they are not awaitable.

10. **The `python-multipart` package is required** for FastAPI to parse form data from the poll page. Without it, `await request.form()` throws a runtime error. It's included in requirements.txt.

11. **Google OAuth testing mode** allows up to 100 test users without app verification. Add each team member's Google account as a test user in the Google Cloud Console under "OAuth consent screen" → "Test users". Without this, they'll see a "This app isn't verified" error that blocks sign-in.

12. **The auth link sent during onboarding** goes directly to Google's OAuth URL (not through your server). The `state` parameter carries the user's phone number so the callback can link the Google account to the right user. This is secure because the state is only used as a lookup key, not for authorization.

13. **When creating events with attendees**, Google Calendar automatically sends invitation emails if `sendUpdates="all"`. This means you do NOT need to separately email attendees for events — the `send_email` tool is only needed for availability polls and custom coordination where you need to send something Google Calendar doesn't handle.
