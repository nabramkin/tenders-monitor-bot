import aiohttp
import base64
import uuid
import os
from config import GIGACHAT_CLIENT_ID

class GigaChatClient:
    def __init__(self):
        self.client_id = GIGACHAT_CLIENT_ID
        self.access_token = None
        self.base_url = "https://gigachat.devices.sberbank.ru/api/v1"
        self.token_url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"

    async def get_token(self):
        """Точно как в твоём cURL примере"""
        if self.access_token:
            return self.access_token

        # Basic Auth: client_id:client_id (пароль = client_id!)
        auth_string = f"{self.client_id}:{self.client_id}"
        auth_b64 = base64.b64encode(auth_string.encode()).decode()

        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Accept': 'application/json',
            'RqUID': str(uuid.uuid4())  # уникальный ID запроса
        }
        
        data = {
            'scope': 'GIGACHAT_API_PERS'
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.token_url,
                headers=headers,
                auth=aiohttp.BasicAuth(self.client_id, self.client_id),  # или через заголовок
                data=data
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    self.access_token = result["access_token"]
                    return self.access_token
                else:
                    raise Exception(f"Token error: {resp.status}")

    async def chat_completion(self, messages, model="GigaChat:latest"):
        """Запрос к GigaChat"""
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
        
        async with aiohttp.ClientSession() as session:
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
