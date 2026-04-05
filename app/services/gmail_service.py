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
    """Send an availability poll email with a link to the web-based poll page."""
    poll_url = f"{settings.app_base_url}/poll/{poll_id}"

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
        <p style="color: #999; font-size: 12px;">Sent by Mosaic on behalf of {user_name}</p>
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

        payload = msg.get("payload", {})
        body = ""

        if payload.get("mimeType") == "text/plain":
            body = base64.urlsafe_b64decode(payload["body"]["data"]).decode()
        else:
            for part in payload.get("parts", []):
                if part.get("mimeType") == "text/plain":
                    body = base64.urlsafe_b64decode(part["body"]["data"]).decode()
                    break

        headers = {h["name"]: h["value"] for h in payload.get("headers", [])}

        replies.append({
            "message_id": msg["id"],
            "from": headers.get("From", ""),
            "date": headers.get("Date", ""),
            "body": body,
        })

    return replies
