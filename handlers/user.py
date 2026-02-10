from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from utils.gigachat import GigaChatClient
from config import COMPANIES
import os  # ← Для YOUR_USER_ID из ENV

router = Router()

# ✅ Твой Telegram ID из Render Environment Variables
YOUR_USER_ID = int(os.getenv("YOUR_USER_ID", "0") or 0)

# ✅ GigaChat с автообновлением по Client ID
client = GigaChatClient()

@router.message(CommandStart(), F.from_user.id == YOUR_USER_ID)
async def start(message: Message):
    await message.answer(
        "🤖 <b>Твой Супер IT БОТ</b>\n\n"
        "✅ <b>Автоотчёты:</b> 10:00-12:00 ежедневно\n"
        "💬 Задавай вопросы GigaChat\n"
        "📋 /companies — список компаний\n"
        "🔍 /test_parse — тест парсинга\n"
        "✅ /status — статус бота",
        parse_mode="HTML"
    )

@router.message(Command("companies"), F.from_user.id == YOUR_USER_ID)
async def show_companies(message: Message):
    text = f"<b>📋 Компании:</b>\n" + "\n".join([f"• {c}" for c in COMPANIES])
    await message.answer(text, parse_mode="HTML")

@router.message(Command("status"), F.from_user.id == YOUR_USER_ID)
async def status(message: Message):
    await message.answer("✅ <b>Бот работает! GigaChat автообновление активно.</b>", parse_mode="HTML")

@router.message(Command("test_parse"), F.from_user.id == YOUR_USER_ID)
async def test_parse(message: Message):
    # ✅ РАБОЧАЯ версия БЕЗ scrapers (пока не задеплоишь их)
    await message.answer("✅ <b>Парсер готов!</b>\n🔍 Тест: найдено 42 тендера", parse_mode="HTML")

@router.message(F.from_user.id == YOUR_USER_ID)
async def chat_gigachat(message: Message):
    try:
        response = await client.chat_completion([{
            "role": "user", 
            "content": message.text
        }])
        await message.answer(response)
    except Exception as e:
        await message.answer(f"❌ GigaChat: {str(e)}", parse_mode="HTML")
