from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from config import YOUR_USER_ID, COMPANIES
from utils.gigachat import GigaChatClient
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aiogram import Bot

router = Router(name="user")

client = GigaChatClient()

# Команда /start
@router.message(CommandStart(), F.from_user.id == YOUR_USER_ID)
async def cmd_start(message: Message):
    await message.answer(
        "🤖 <b>Твой Супер IT БОТ</b>\n\n"
        "✅ <b>Автоотчёты:</b> 10:00–12:00 ежедневно\n"
        "💬 Задавай вопросы GigaChat\n"
        "📋 /companies — список компаний\n"
        "🔍 /test_parse — тест парсинга\n"
        "✅ /status — статус бота",
        parse_mode="HTML"
    )


@router.message(Command("companies"), F.from_user.id == YOUR_USER_ID)
async def show_companies(message: Message):
    text = "<b>📋 Компании‑мишени:</b>\n" + "\n".join([f"• {c}" for c in COMPANIES])
    await message.answer(text, parse_mode="HTML")


@router.message(Command("status"), F.from_user.id == YOUR_USER_ID)
async def status(message: Message):
    await message.answer(
        "✅ <b>Бот работает! GigaChat автообновление активно.</b>",
        parse_mode="HTML"
    )


@router.message(Command("test_parse"), F.from_user.id == YOUR_USER_ID)
async def test_parse(message: Message):
    from scrapers.contests import scrape_all_sites, is_it_relevant, format_tender_message
    tenders = await scrape_all_sites()
    it_tenders = [t for t in tenders if is_it_relevant(t)]
    fresh = [t for t in it_tenders if t['date'] >= datetime.now().date() - timedelta(days=2)]
    text = format_tender_message(fresh)
    await message.answer(text, parse_mode="HTML")


@router.message(F.from_user.id == YOUR_USER_ID)
async def chat_gigachat(message: Message):
    if not message.text:
        await message.answer("⚠️ Отправь текстовый вопрос.")
        return

    try:
        response = await client.chat_completion([{
            "role": "user",
            "content": message.text
        }])
        await message.answer(response, parse_mode="HTML")
    except Exception as e:
        await message.answer(
            f"❌ Ошибка GigaChat: <code>{str(e)}</code>",
            parse_mode="HTML"
        )
