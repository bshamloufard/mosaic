from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import JSONResponse
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
from app.web.auth_routes import auth_router
from app.web.poll_routes import poll_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        webhook_url = f"{settings.app_base_url}/webhook/linq"
        await linq_client.register_webhook(webhook_url)
        logger.info(f"Linq webhook registered: {webhook_url}")
    except Exception as e:
        logger.warning(f"Could not register Linq webhook (may already exist): {e}")
    yield


app = FastAPI(title="Mosaic", lifespan=lifespan)

app.include_router(auth_router, prefix="/auth")
app.include_router(poll_router, prefix="/poll")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "mosaic"}


@app.post("/webhook/linq")
async def linq_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Receive incoming iMessage via Linq webhook.
    CRITICAL: Return 200 within 2 seconds, process async.
    """
    body = await request.body()
    timestamp = request.headers.get("X-Linq-Timestamp", "")
    signature = request.headers.get("X-Linq-Signature", "")

    if not verify_linq_signature(body, timestamp, signature):
        logger.warning("Invalid Linq webhook signature")
        return JSONResponse({"error": "invalid signature"}, status_code=401)

    payload = await request.json()
    parsed = parse_linq_webhook(payload)

    valid_events = ("message.received", "message.created", "message")
    if parsed["event_type"] not in valid_events:
        return {"status": "ignored"}

    if not parsed["text"]:
        return {"status": "no text"}

    if await is_duplicate_webhook(parsed["message_id"]):
        return {"status": "duplicate"}

    await mark_webhook_processed(parsed["message_id"])

    if parsed["chat_id"]:
        background_tasks.add_task(linq_client.send_typing_indicator, parsed["chat_id"])

    background_tasks.add_task(
        process_incoming_message,
        parsed["from_phone"],
        parsed["text"],
        parsed["chat_id"],
    )

    return {"status": "accepted"}


async def process_incoming_message(phone: str, text: str, chat_id: str):
    """Process an incoming iMessage asynchronously."""
    try:
        user = await get_or_create_user(phone)
        user_id = user["id"]

        if not user.get("onboarding_complete"):
            await handle_onboarding(user, chat_id, text)
            return

        response = await run_agent(
            user_id=user_id,
            user_message=text,
            chat_id=chat_id,
        )

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
        f"Hey! 👋 I'm Mosaic — your personal scheduling assistant.\n\n"
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
