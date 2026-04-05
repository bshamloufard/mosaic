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
        """Create a new chat and send the first message."""
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
