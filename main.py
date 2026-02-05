import asyncio
import logging
import sqlite3
import aiohttp
import feedparser
from datetime import datetime
from fastapi import FastAPI
import uvicorn
from contextlib import asynccontextmanager
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import os

# Конфигурация
API_TOKEN = os.getenv('BOT_TOKEN')
CHAT_ID = int(os.getenv('CHAT_ID'))
VENDORS_AND_KEYWORDS = [
    'Lenovo', 'Dell', 'Cisco', 'Huawei', 'Supermicro', 'Nvidia', 'NetApp', 
    'IBM', 'Brocade', 'Fortinet', 'Juniper', 'VMware', 'Veeam', 'HPE', 
    'HP', 'Oracle', 'Fujitsu', 'EMC', 'техническая поддержка', 'сервисная поддержка', 
    'консалтинг', 'IT услуги', 'IT решения', 'поставка оборудования'
]

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
scheduler = AsyncIOScheduler()

class Form(StatesGroup):
    waiting_company = State()
    waiting_companies_list = State()

# Глобальные переменные для бота
app_state = {}

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
    """Ежедневная проверка тендеров"""
    print(f"[{datetime.now()}] Проверка тендеров...")
    
    conn = sqlite3.connect('tenders.db')
    c = conn.cursor()
    companies = c.execute("SELECT inn, name FROM companies").fetchall()
    
    if not companies:
        print("Нет компаний для мониторинга")
        return
    
    seen_urls = {row[0] for row in c.execute("SELECT url FROM seen_tenders")}
    new_tenders = []
    
   platforms = {
    'Bidzaar': 'https://bidzaar.com/rss/new',
    'Сбербанк-АСТ': 'https://utp.sberbank-ast.ru/rss/rss.xml',
    'ЭТП Газпромбанк': 'https://etpgpb.ru/rss/rss.xml',
    'РТС-Тендер': 'https://www.rts-tender.ru/rss/rss.ashx',
    'РосТендер': 'https://rostender.info/rss',
    'BiCoTender': 'https://www.bicotender.ru/rss.xml',
    'B2B-Center': 'https://www.b2b-center.ru/rss/rss.xml',
}

    
    async with aiohttp.ClientSession() as session:
        for platform, rss_url in platforms.items():
            try:
                feed = feedparser.parse(rss_url)
                for entry in feed.entries:
                    title_lower = entry.title.lower()
                    if any(kw.lower() in title_lower for kw in VENDORS_AND_KEYWORDS):
                        for inn, company_name in companies:
                            if company_name.lower() in title_lower or inn in entry.get('summary', ''):
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
    
    for tender in new_tenders:
        message = f"""🔔 **Новый тендер!**

🏢 **Компания**: {tender['company']}
📋 **Закупка**: {tender['title']}
🌐 **Площадка**: {tender['platform']}
📅 **Публикация**: {tender['pub_date']}
⏰ **Окончание**: {tender['end_date']}
🔗 {tender['url']}"""
        try:
            await bot.send_message(CHAT_ID, message, parse_mode='Markdown')
            print(f"Отправлено: {tender['title']}")
            await asyncio.sleep(1)
        except Exception as e:
            print(f"Ошибка отправки: {e}")

# Aiogram handlers
@dp.message(Command('start'))
async def start_handler(message: types.Message):
    await message.reply("🤖 **Бот мониторинга IT-тендеров запущен!**\n\n"
                       "**Команды**:\n"
                       "`/add_company` - 1 компания\n"
                       "`/load_companies` - список\n"
                       "`/list` - все компании\n\n"
                       "ℹ️ Проверка каждые **2 мин** (тест)",
                       parse_mode='Markdown')

@dp.message(Command('add_company'))
async def add_company(message: types.Message, state: FSMContext):
    await message.reply("➕ **Компания**:\n\n`Газпром 1234567890`", parse_mode='Markdown')
    await state.set_state(Form.waiting_company)

@dp.message(Form.waiting_company)
async def process_company(message: types.Message, state: FSMContext):
    try:
        parts = message.text.rsplit(maxsplit=1)
        name, inn = parts[0].strip(), parts[1].strip()
        conn = sqlite3.connect('tenders.db')
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO companies (inn, name) VALUES (?, ?)", (inn, name))
        conn.commit()
        conn.close()
        await message.reply(f"✅ **Добавлена**: `{name}` (`{inn}`)", parse_mode='Markdown')
    except:
        await message.reply("❌ **Формат**: `Название ИНН`", parse_mode='Markdown')
    await state.clear()

@dp.message(Command('load_companies'))
async def load_companies(message: types.Message, state: FSMContext):
    await message.reply("📋 **Список компаний**:\n\n"
                       "`Газпром 1234567890`\n"
                       "`Роснефть 7778889990`\n\n"
                       "**название + ПРОБЕЛ + ИНН**",
                       parse_mode='Markdown')
    await state.set_state(Form.waiting_companies_list)

@dp.message(Form.waiting_companies_list)
async def process_companies_list(message: types.Message, state: FSMContext):
    companies_added = 0
    lines = message.text.strip().split('\n')
    conn = sqlite3.connect('tenders.db')
    c = conn.cursor()
    
    for line in lines:
        line = line.strip()
        if not line or len(line.split()) < 2: continue
        try:
            parts = line.rsplit(maxsplit=1)
            name, inn = parts[0].strip(), parts[1].strip()
            c.execute("INSERT OR REPLACE INTO companies (inn, name) VALUES (?, ?)", (inn, name))
            companies_added += 1
        except Exception as e:
            print(f"Ошибка: {e}")
    
    conn.commit()
    conn.close()
    await message.reply(f"✅ **Загружено: {companies_added} компаний**\n`/list`", parse_mode='Markdown')
    await state.clear()

@dp.message(Command('list'))
async def list_companies(message: types.Message):
    conn = sqlite3.connect('tenders.db')
    c = conn.cursor()
    companies = c.execute("SELECT name, inn FROM companies").fetchall()
    conn.close()
    
    if companies:
        text = f"📋 **Компании** ({len(companies)}):\n\n"
        for i, (name, inn) in enumerate(companies, 1):
            text += f"{i}. **{name}** (`{inn}`)\n"
        await message.reply(text, parse_mode='Markdown')
    else:
        await message.reply("📭 **Пусто**\n`/add_company` или `/load_companies`", parse_mode='Markdown')

# FastAPI app
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    init_db()
    scheduler.add_job(check_tenders, 'interval', minutes=2)  # Тест 2 мин
    scheduler.start()
    app_state['scheduler'] = scheduler
    print("🚀 Бот + FastAPI запущены!")
    yield
    # Shutdown
    scheduler.shutdown()

app = FastAPI(lifespan=lifespan)

@app.get("/")
async def root():
    return {"status": "IT Tender Bot running", "companies": "check /list"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
