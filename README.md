# Mosaic

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
   git clone https://github.com/yourname/mosaic.git
   cd mosaic
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

See `projectResearch.md` for complete technical details.

## License

MIT
