from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from utils.gigachat import GigaChatClient
from config import COMPANIES, YOUR_USER_ID
from scrapers.contests import scrape_all_sites
import asyncio

router = Router()

@router.message(Command("start"))
async def start_cmd(message: Message):
    await message.answer(
        "🤖 <b>ИТ-Тендеры Bot готов!</b>\n\n"
        f"🏢 Отслеживаю <b>{len(COMPANIES)}</b> компаний\n"
        "📡 Пиши название компании или 'все тендеры'"
    )

@router.message(F.text, F.from_user.id == YOUR_USER_ID)
async def handle_message(message: Message):
    try:
        # АВТО: парсим + фильтруем ВСЕ 20+ компаний
        tenders = await scrape_all_sites()
        company_inns = [c.split()[-1] for c in COMPANIES]
        
        # Контекст для GigaChat (ТОЛЬКО твои компании)
        context = f"📊 АКТУАЛЬНЫЕ ИТ-ТЕНДЕРЫ ({len(COMPANIES)} компаний):\n\n"
        your_tenders = []
        
        for t in tenders:
            for inn in company_inns:
                if inn in str(t).lower():
                    your_tenders.append(t)
                    context += f"✅ {t['company']}: {t['title'][:70]} [{t['source']}]\n"
                    break
        
        if not your_tenders:
            context += "❌ Свежих тендеров твоих компаний нет\n"
        
        context += f"\n🏢 Компании: " + ", ".join([c.split()[0] for c in COMPANIES[:6]]) + "..."
        
        # GigaChat с умным контекстом
        messages = [
            {"role": "system", "content": "Ты эксперт по ИТ-тендерам. Используй только данные из контекста."},
            {"role": "user", "content": f"{context}\n\nВопрос: {message.text}"}
        ]
        
        client = GigaChatClient()
        response = await client.chat_completion(messages)
        await message.answer(response)
        
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")

@router.message(Command("debug"))
async def debug(message: Message):
    tenders = await scrape_all_sites()
    await message.answer(f"🔍 Найдено тендеров: {len(tenders)}")
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
