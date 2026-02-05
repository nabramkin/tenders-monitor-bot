import asyncio
import logging
import sqlite3
import aiohttp
import feedparser
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import os

# Конфигурация
API_TOKEN = os.getenv('BOT_TOKEN')
CHAT_ID = int(os.getenv('CHAT_ID'))  # Ваш Telegram ID
VENDORS = ['Lenovo', 'Dell', 'Cisco', 'Huawei', 'Supermicro', 'Nvidia', 'NetApp', 
           'IBM', 'Brocade', 'Fortinet', 'Juniper', 'VMware', 'Veeam', 'HPE', 
           'HP', 'Oracle', 'Fujitsu', 'EMC']
KEYWORDS = ['техническая поддержка', 'сервисная поддержка', 'консалтинг', 
           'IT решения', 'IT услуги', 'поставка оборудования']

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
scheduler = AsyncIOScheduler()

class Form(StatesGroup):
    waiting_company = State()

# База данных
def init_db():
    conn = sqlite3.connect('tenders.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS companies 
                 (inn TEXT PRIMARY KEY, name TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS seen_tenders 
                 (url TEXT PRIMARY KEY, title TEXT, company TEXT, 
                  pub_date TEXT, end_date TEXT, platform TEXT)''')
    conn.commit()
    conn.close()

async def check_tenders():
    """Ежедневная проверка тендеров в 10:00"""
    print(f"[{datetime.now()}] Проверка тендеров...")
    
    conn = sqlite3.connect('tenders.db')
    c = conn.cursor()
    c.execute("SELECT inn, name FROM companies")
    companies = c.fetchall()
    
    if not companies:
        print("Нет компаний для мониторинга")
        return
    
    seen_urls = {row[0] for row in c.execute("SELECT url FROM seen_tenders")}
    new_tenders = []
    
    # RSS ленты площадок (замените на реальные после регистрации)
    platforms = {
       platforms = {
    # Агрегаторы (все площадки разом)
    'РТС+TenderGuru': 'https://www.rts-tender.ru/rss/rss.ashx',
    'РосТендер': 'https://rostender.info/rss',
    'BiCoTender': 'https://www.bicotender.ru/rss.xml',
    
    # Прямые площадки
    'B2B-Center': 'https://www.b2b-center.ru/rss/rss.xml',
    'Bidzaar': 'https://bidzaar.com/rss/new',
}

    }
    
    async with aiohttp.ClientSession() as session:
        for platform, rss_url in platforms.items():
            try:
                feed = feedparser.parse(rss_url)
                for entry in feed.entries:
                    title = entry.title.lower()
                    
                    # Фильтр по вендорам, ключевым словам и компаниям
                    f any(keyword.lower() in title_lower for keyword in vendors_keywords):
                        
                        for inn, company_name in companies:
                            if company_name.lower() in title or inn in entry.get('summary', ''):
                                if entry.link not in seen_urls:
                                    new_tenders.append({
                                        'platform': platform,
                                        'title': entry.title,
                                        'url': entry.link,
                                        'pub_date': getattr(entry, 'published', 'Неизвестно'),
                                        'end_date': getattr(entry, 'updated', 'Неизвестно'),
                                        'company': company_name
                                    })
                                    c.execute('''INSERT OR IGNORE INTO seen_tenders 
                                               (url, title, company, pub_date, end_date, platform)
                                               VALUES (?, ?, ?, ?, ?, ?)''',
                                            (entry.link, entry.title, company_name,
                                             entry.get('published'), entry.get('updated'), platform))
                conn.commit()
            except Exception as e:
                print(f"Ошибка {platform}: {e}")
    
    conn.close()
    
    # Отправка уведомлений
    for tender in new_tenders:
        message = f"""🔔 Новый тендер!

🏢 **Компания**: {tender['company']}
📋 **Закупка**: {tender['title']}
🌐 **Площадка**: {tender['platform']}
📅 **Публикация**: {tender['pub_date']}
⏰ **Окончание**: {tender['end_date']}
🔗 {tender['url']}"""
        
        try:
            await bot.send_message(CHAT_ID, message, parse_mode='Markdown')
            print(f"Отправлено: {tender['title']}")
            await asyncio.sleep(1)  # Rate limit
        except Exception as e:
            print(f"Ошибка отправки: {e}")

@dp.message(Command('start'))
async def start_handler(message: types.Message):
    await message.reply("🤖 Бот мониторинга IT-тендеров запущен!\n"
                       f"Добавьте компании командой /add_company\n"
                       "Проверка ежедневно в 10:00")

@dp.message(Command('add_company'))
async def add_company(message: types.Message, state: FSMContext):
    await message.reply("Введите название и ИНН компании (пример: Газпром 1234567890):")
    await state.set_state(Form.waiting_company)

@dp.message(Form.waiting_company)
async def process_company(message: types.Message, state: FSMContext):
    try:
        name, inn = message.text.rsplit(maxsplit=1)
        conn = sqlite3.connect('tenders.db')
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO companies (inn, name) VALUES (?, ?)", (inn, name))
        conn.commit()
        conn.close()
        await message.reply(f"✅ Добавлена компания: {name} (ИНН: {inn})")
    except:
        await message.reply("❌ Неверный формат. Пример: Газпром 1234567890")
    await state.clear()

@dp.message(Command('list'))
async def list_companies(message: types.Message):
    conn = sqlite3.connect('tenders.db')
    c = conn.cursor()
    companies = c.execute("SELECT name, inn FROM companies").fetchall()
    conn.close()
    
    if companies:
        text = "📋 Компании для мониторинга:\n\n" + \
               "\n".join([f"• {name} ({inn})" for name, inn in companies])
    else:
        text = "Список пуст"
    await message.reply(text)

async def on_startup():
    init_db()
    scheduler.add_job(check_tenders, 'cron', hour=10, minute=0)
    scheduler.start()
    print("🚀 Бот запущен, планировщик активен")

from fastapi import FastAPI
import uvicorn
from contextlib import asynccontextmanager

app = FastAPI()

@app.get("/")
async def root():
    return {"status": "bot running"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

if __name__ == '__main__':
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == '__main__':
    asyncio.run(dp.start_polling(bot, on_startup=on_startup))
