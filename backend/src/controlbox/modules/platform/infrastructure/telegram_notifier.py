import httpx

from controlbox.modules.supabase.infrastructure.crypto import SecretEncryptor


class TelegramNotifier:
    def __init__(self, encryptor: SecretEncryptor) -> None:
        self._encryptor = encryptor

    async def send_alert(
        self,
        *,
        bot_token_enc: str | None,
        chat_id: str | None,
        message: str,
        severity: str = "warning",
    ) -> tuple[bool, str]:
        if not bot_token_enc or not chat_id:
            return False, "Telegram not configured"
        try:
            token = self._encryptor.decrypt(bot_token_enc)
        except Exception:
            return False, "Invalid bot token"

        icon = "🔴" if severity == "critical" else "⚠️"
        text = f"{icon} *ControlBox Alert*\n{message}"
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    url,
                    json={
                        "chat_id": chat_id.strip(),
                        "text": text,
                        "parse_mode": "Markdown",
                        "disable_web_page_preview": True,
                    },
                )
                data = response.json()
                if not response.is_success or not data.get("ok"):
                    desc = data.get("description", response.text)
                    return False, f"Telegram API error: {desc}"
                return True, "Sent"
        except httpx.HTTPError as exc:
            return False, str(exc)

    async def test_connection(
        self,
        *,
        bot_token: str,
        chat_id: str,
    ) -> tuple[bool, str]:
        token = bot_token.strip()
        cid = chat_id.strip()
        if not token or not cid:
            return False, "Bot token and chat ID are required"

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    url,
                    json={
                        "chat_id": cid,
                        "text": "✅ ControlBox: Telegram alerts configured successfully.",
                        "disable_web_page_preview": True,
                    },
                )
                data = response.json()
                if not response.is_success or not data.get("ok"):
                    return False, data.get("description", "Telegram test failed")
                return True, "Test message sent to Telegram"
        except httpx.HTTPError as exc:
            return False, str(exc)
