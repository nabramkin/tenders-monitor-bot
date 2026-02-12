from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from utils.gigachat import GigaChatClient
from config import COMPANIES, YOUR_USER_ID, IT_VENDORS, IT_KEYWORDS
from scrapers.contests import scrape_all_sites
import asyncio

router = Router()

# Состояния для FSM (если нужно)
class Form(StatesGroup):
    waiting_company = State()

@router.message(Command("start"))
async def cmd_start(message: Message):
    """Стартовая команда"""
    await message.answer(
        "🤖 <b>ИТ-Тендеры Bot</b>\n\n"
        f"🏢 Отслеживаю <b>{len(COMPANIES)}</b> компаний\n\n"
        "<b>Команды:</b>\n"
        "/list — список всех компаний\n"
        "/tenders — свежие тендеры\n"
        "/debug — диагностика парсера\n"
        "АКРОН — тендеры конкретной компании\n\n"
        "💬 Пиши название компании для отчёта!"
    )

@router.message(Command("list"))
async def cmd_list(message: Message):
    """Список всех компаний"""
    companies_text = "<b>🏢 Твои компании ({len(COMPANIES)}):</b>\n\n"
    for i, company in enumerate(COMPANIES[:20], 1):
        companies_text += f"{i}. {company}\n"
    if len(COMPANIES) > 20:
        companies_text += f"\n... и ещё {len(COMPANIES)-20}"
    
    await message.answer(companies_text, parse_mode="HTML")

@router.message(Command("tenders"))
async def cmd_tenders(message: Message):
    """Все свежие тендеры"""
    try:
        tenders = await scrape_all_sites()
        if not tenders:
            await message.answer("❌ Тендеры не найдены")
            return
        
        msg = f"<b>📊 Свежие тендеры ({len(tenders)}):</b>\n\n"
        for i, t in enumerate(tenders[:10], 1):
            msg += f"{i}. <b>{t['company']}</b>\n   {t['title'][:70]}...\n   <a href='{t['url']}'>{t['source']}</a>\n\n"
        
        await message.answer(msg, parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ Ошибка парсера: {e}")

@router.message(Command("debug"))
async def cmd_debug(message: Message):
    """Диагностика"""
    try:
        tenders = await scrape_all_sites()
        msg = f"🔍 <b>Диагностика:</b>\n\n📊 Всего тендеров: {len(tenders)}\n🏢 Компаний: {len(COMPANIES)}"
        await message.answer(msg, parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ {e}")

@router.message(Command("status"))
async def cmd_status(message: Message):
    """Статус бота"""
    await message.answer("✅ Бот работает!")

# GigaChat ТОЛЬКО для запросов о компаниях/тендерах
@router.message(F.text & F.from_user.id == YOUR_USER_ID)
async def handle_gigachat(message: Message):
    text = message.text.lower().strip()
    
    # ПРОВЕРКА: команда или название компании?
    if any(cmd in text for cmd in ["/start", "/list", "/tenders", "/debug", "/status"]):
        return  # Команда — игнорируем
    
    # Ищем компанию в списке
    company_found = None
    for company in COMPANIES:
        if any(word in text for word in company.lower().split()[:3]):  # Первые 3 слова компании
            company_found = company
            break
    
    # Если нашли компанию — GigaChat с контекстом
    if company_found:
        try:
            tenders = await scrape_all_sites()
            company_inns = [c.split()[-1] for c in COMPANIES]
            
            context = f"🏢 Компания: {company_found}\n\n"
            company_tenders = []
            
            for t in tenders:
                if any(inn in str(t).lower() for inn in company_inns):
                    if company_found.lower() in str(t).lower():
                        company_tenders.append(t)
                        context += f"✅ {t['title'][:60]} [{t['source']}]\n"
            
            if not company_tenders:
                context += "❌ Свежих тендеров нет\n"
            
            messages = [
                {"role": "system", "content": "Ты эксперт по ИТ-тендерам этой компании."},
                {"role": "user", "content": f"{context}\nВопрос: {message.text}"}
            ]
            
            client = GigaChatClient()
            response = await client.chat_completion(messages)
            await message.answer(response)
            
        except Exception as e:
            await message.answer(f"❌ Ошибка GigaChat: {e}")
    else:
        # Не компания — обычный ответ
        await message.answer("🏢 Напиши название компании из списка (/list)")


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
