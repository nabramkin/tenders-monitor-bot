import aiohttp
import base64
import uuid
import os
import ssl
from datetime import datetime, timedelta
from config import GIGACHAT_CLIENT_ID
from aiogram import Bot
from typing import Optional

class GigaChatClient:
    def __init__(self):
        self.client_id = GIGACHAT_CLIENT_ID
        self.access_token: Optional[str] = None
        self.token_expires_at: Optional[datetime] = None
        self.base_url = "https://gigachat.devices.sberbank.ru/api/v1"
        self.token_url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
        
        # SSL без проверки (только если реально работает)
        self.ssl_context = ssl.create_default_context()
        self.ssl_context.check_hostname = False
        self.ssl_context.verify_mode = ssl.CERT_NONE

    def _is_token_expired_or_invalid(self) -> bool:
        if not self.access_token or not self.token_expires_at:
            return True
        return datetime.utcnow() >= self.token_expires_at

    async def _ensure_token(self):
        if not self._is_token_expired_or_invalid():
            return self.access_token

        auth_string = f"{self.client_id}:{self.client_id}"
        auth_b64 = base64.b64encode(auth_string.encode()).decode()

        headers = {
            'Content-Type': 'application/x-www-urlencoded',
            'Accept': 'application/json',
            'RqUID': str(uuid.uuid4())
        }
        data = {'scope': 'GIGACHAT_API_PERS'}

        connector = aiohttp.TCPConnector(ssl=self.ssl_context)
        timeout = aiohttp.ClientTimeout(total=30)

        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            async with session.post(
                self.token_slash,
                headers=headers,
                auth=aiohttp.BasicAuth(self.client_id, self.client_id),
                data=data,
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    self.access_token = result["access_token"]
                    # Аккуратно: если GigaChat даёт ttl (в секундах)
                    ttl = result.get("expires_in", 1800)  # 30 мин
                    self.token_expires_at = datetime.utcnow() + timedelta(seconds=ttl - 60)
                    return self.access_token
                else:
                    error_text = await resp.text()
                    raise Exception(f"Token error {resp.status}: {error_text}")

    async def get_token(self):
        """Публичный getter, всегда проверяет срок действия."""
        await self._ensure_token()
        return self.access_token

    async def chat_completion(self, messages, model="GigaChat:latest"):
        """Чат с GigaChat."""
        token = await self.get_token()

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "RqUID": str(uuid.uuid4())
        }

        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 2000
        }

        connector = aiohttp.TCPConnector(ssl=self.ssl_context)
        timeout = aiohttp.ClientTimeout(total=60)

        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            async with session.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    return result["choices"][0]["message"]["content"]
                else:
                    error_text = await resp.text()
                    raise Exception(f"GigaChat API error {resp.status}: {error_text}")
