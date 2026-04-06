import httpx
import logging
from app.config import settings
from app.utils.text_format import build_text_part

logger = logging.getLogger(__name__)


class LinqClient:
    """Client for Linq Partner API V3 (iMessage, RCS, SMS)."""

    def __init__(self):
        self.base_url = settings.linq_base_url
        self.headers = {
            "Authorization": f"Bearer {settings.linq_api_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        self.phone_number = settings.linq_phone_number

    async def create_chat(
        self,
        to_phone: str,
        message: str,
        preferred_service: str = "iMessage",
        effect: dict = None,
    ) -> dict:
        """Create a new chat and send the first message (V3 format)."""
        payload = {
            "from": self.phone_number,
            "to": [to_phone],
            "message": {
                "parts": [build_text_part(message)]
            },
        }
        if effect:
            payload["message"]["effect"] = effect

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
    ) -> dict:
        """Send a message to an existing chat (V3 format).
        Automatically converts markdown bold/italic to iMessage text_decorations.
        """
        message_obj = {
            "parts": [build_text_part(text)]
        }
        if effect:
            message_obj["effect"] = effect
        if reply_to_message_id:
            message_obj["reply_to"] = {"message_id": reply_to_message_id, "part_index": 0}
        payload = {"message": message_obj}

        async with httpx.AsyncClient() as client:
            logger.info(f"Sending message to chat {chat_id}: {str(payload)[:200]}")
            resp = await client.post(
                f"{self.base_url}/chats/{chat_id}/messages",
                headers=self.headers,
                json=payload,
                timeout=30.0,
            )
            if resp.status_code >= 400:
                logger.error(f"Linq send_message error {resp.status_code}: {resp.text}")
            resp.raise_for_status()
            return resp.json()

    async def send_typing_indicator(self, chat_id: str) -> None:
        """Show typing bubble in the user's iMessage."""
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"{self.base_url}/chats/{chat_id}/typing",
                    headers=self.headers,
                    timeout=10.0,
                )
        except Exception as e:
            logger.warning(f"Failed to send typing indicator: {e}")

    async def send_reaction(self, chat_id: str, message_id: str, reaction: str) -> None:
        """Send a tapback reaction."""
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


linq_client = LinqClient()
