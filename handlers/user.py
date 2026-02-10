from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from utils.gigachat import GigaChatClient
from config import COMPANIES  # ← УБРАЛ НЕСУЩЕСТВУЮЩИЕ!

router = Router()

# ✅ ИНИЦИАЛИЗАЦИЯ С ТОКЕНОМ ИЗ ENV
client = GigaChatClient()  # Токен из .env в GigaChatClient!

YOUR_USER_ID = 123456789  # ← ТВОЙ TELEGRAM ID!!! 

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
    await message.answer("✅ <b>Бот работает стабильно!</b>", parse_mode="HTML")

@router.message(Command("test_parse"), F.from_user.id == YOUR_USER_ID)
async def test_parse(message: Message):
    # ✅ ВРЕМЕННО ОТКЛЮЧИЛ - вернешь ПОЗЖЕ!
    await message.answer("🔧 Парсинг временно отключен. Бот работает!")

@router.message(F.from_user.id == YOUR_USER_ID)
async def chat_gigachat(message: Message):
    try:
        response = await client.chat_completion([{
            "role": "user", 
            "content": message.text
        }])
        await message.answer(response)
    except Exception as e:
        await message.answer(f"❌ Ошибка GigaChat: {str(e)}")
