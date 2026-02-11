import aiohttp
import uuid
import ssl
from datetime import datetime, timedelta
from config import GIGACHAT_AUTH_KEY  # ← ТВОЙ "Ключ авторизации" из кабинета Сбера!

class GigaChatClient:
    def __init__(self):
        self.auth_key = GIGACHAT_AUTH_KEY
        self.access_token = None
        self.token_expires_at = None
        self.base_url = "https://gigachat.devices.sberbank.ru/api/v1"
        self.token_url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
        
        # SSL без проверки (для Сбера)
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

        # ✅ HEADERS по документации Сбера
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json',
            'RqUID': str(uuid.uuid4()),
            'Authorization': f'Basic {self.auth_key}'  # ← ТВОЙ ГОТОВЫЙ КЛЮЧ!
        }
        
        form_data = {'scope': 'GIGACHAT_API_PERS'}

        connector = aiohttp.TCPConnector(ssl=self.ssl_context)
        timeout = aiohttp.ClientTimeout(total=30)
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            async with session.post(
                self.token_url,
                headers=headers,
                data=form_data
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    self.access_token = result["access_token"]
                    ttl = result.get("expires_in", 1800)
                    self.token_expires_at = datetime.utcnow() + timedelta(seconds=ttl - 60)
                    return self.access_token
                else:
                    error_text = await resp.text()
                    raise Exception(f"Token error {resp.status}: {error_text}")

    async def chat_completion(self, messages, model="GigaChat:latest"):
        token = await self._ensure_token()
        
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
