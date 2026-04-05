from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from app.services.google_auth import create_auth_flow, exchange_code, get_auth_url
from app.services.contacts_service import sync_contacts_to_cache
from app.services.linq import linq_client
from app.db.users import update_user
from app.db.client import supabase
import asyncio
import logging

logger = logging.getLogger(__name__)

auth_router = APIRouter()


@auth_router.get("/google")
async def google_auth_start(phone: str):
    """Start the Google OAuth flow. Called when user taps the auth link."""
    auth_url = get_auth_url(phone)
    return RedirectResponse(auth_url)


@auth_router.get("/google/callback")
async def google_auth_callback(request: Request):
    """Handle the OAuth callback from Google."""
    code = request.query_params.get("code")
    state = request.query_params.get("state")

    if not code or not state:
        return HTMLResponse("<h1>Error: Missing authorization code</h1>", status_code=400)

    try:
        result = await exchange_code(code, state)
        user_id = result["user_id"]
        email = result["email"]

        await update_user(user_id, {
            "onboarding_complete": True,
            "display_name": email.split("@")[0],
        })

        asyncio.create_task(sync_contacts_to_cache(user_id))

        user_data = supabase.table("users").select("phone_number").eq("id", user_id).execute()
        conv_data = supabase.table("conversations").select("linq_chat_id").eq("user_id", user_id).execute()

        if conv_data.data and conv_data.data[0].get("linq_chat_id"):
            await linq_client.send_message(
                conv_data.data[0]["linq_chat_id"],
                f"You're all set! 🎉 I've connected your Google account ({email}). Your Calendar, Gmail, and Contacts are now linked.\n\nTry saying: \"What's on my calendar today?\"",
            )
        elif user_data.data:
            try:
                chat_result = await linq_client.create_chat(
                    to_phone=user_data.data[0]["phone_number"],
                    message=f"You're all set! 🎉 I've connected your Google account ({email}). Your Calendar, Gmail, and Contacts are now linked.\n\nTry saying: \"What's on my calendar today?\"",
                )
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
