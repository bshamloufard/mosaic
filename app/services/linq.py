import httpx
import logging
from app.config import settings

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
                "parts": [
                    {"type": "text", "value": message}
                ]
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
        """Send a message to an existing chat (V3 format)."""
        payload = {
            "parts": [
                {"type": "text", "value": text}
            ]
        }
        if effect:
            payload["effect"] = effect
        if reply_to_message_id:
            payload["reply_to"] = reply_to_message_id

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
