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
        access_type="offline",
        prompt="consent",
        include_granted_scopes="true",
        state=user_phone,
    )
    return auth_url


async def exchange_code(code: str, user_phone: str) -> dict:
    """Exchange authorization code for tokens and store them."""
    flow = create_auth_flow()
    flow.fetch_token(code=code)
    creds = flow.credentials

    from google.oauth2 import id_token
    from google.auth.transport import requests as google_requests
    id_info = id_token.verify_oauth2_token(
        creds.id_token,
        google_requests.Request(),
        settings.google_client_id,
    )
    email = id_info["email"]

    data = {
        "email": email,
        "access_token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_expiry": creds.expiry.isoformat() if creds.expiry else None,
        "scopes": list(creds.scopes) if creds.scopes else SCOPES,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    user_result = supabase.table("users").select("id").eq("phone_number", user_phone).execute()
    if user_result.data:
        user_id = user_result.data[0]["id"]
    else:
        result = supabase.table("users").insert({"phone_number": user_phone}).execute()
        user_id = result.data[0]["id"]

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

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        supabase.table("linked_accounts").update({
            "access_token": creds.token,
            "token_expiry": creds.expiry.isoformat() if creds.expiry else None,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", account["id"]).execute()

    return creds
