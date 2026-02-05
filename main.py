import asyncio
import logging
import sqlite3
import aiohttp
import feedparser
from datetime import datetime
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
    waiting_companies_list = State()  # Для массовой загрузки

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
    companies = c.execute("SELECT inn, name FROM companies").fetchall()
    
    if not companies:
        print("Нет компаний для мониторинга")
        return
    
    seen_urls = {row[0] for row in c.execute("SELECT url FROM seen_tenders")}
    new_tenders = []
    
    # RSS ленты агрегаторов и площадок
    platforms = {
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
                    
                    # Фильтр по вендорам/ключевым словам
                    if any(kw.lower() in title_lower for kw in VENDORS_AND_KEYWORDS):
                        # Фильтр по компаниям
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
    
    # Отправка уведомлений
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

@dp.message(Command('start'))
async def start_handler(message: types.Message):
    await message.reply("🤖 **Бот мониторинга IT-тендеров запущен!**\n\n"
                       "**Команды**:\n"
                       "`/add_company` - добавить 1 компанию\n"
                       "`/load_companies` - загрузить список\n"
                       "`/list` - показать все компании\n\n"
                       "ℹ️ Проверка **ежедневно в 10:00**", parse_mode='Markdown')

@dp.message(Command('add_company'))
async def add_company(message: types.Message, state: FSMContext):
    await message.reply("➕ **Введите компанию**:\n\n"
                       "`Газпром 1234567890`", parse_mode='Markdown')
    await state.set_state(Form.waiting_company)

@dp.message(Form.waiting_company)
async def process_company(message: types.Message, state: FSMContext):
    try:
        parts = message.text.rsplit(maxsplit=1)
        name, inn = parts[0], parts[1]
        conn = sqlite3.connect('tenders.db')
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO companies (inn, name) VALUES (?, ?)", (inn.strip(), name.strip()))
        conn.commit()
        conn.close()
        await message.reply(f"✅ **Добавлена**: `{name}` (`{inn}`)", parse_mode='Markdown')
    except:
        await message.reply("❌ **Неверный формат**:\n`Название ИНН`", parse_mode='Markdown')
    await state.clear()

@dp.message(Command('load_companies'))
async def load_companies(message: types.Message, state: FSMContext):
    await message.reply("📋 **Отправьте список компаний**:\n\n"
                       "`Газпром 1234567890`\n"
                       "`Роснефть 7778889990`\n"
                       "`Лукойл 1112223330`\n\n"
                       "**Формат**: название + ПРОБЕЛ + ИНН на строку",
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
        if not line or len(line.split()) < 2:
            continue
        try:
            parts = line.rsplit(maxsplit=1)
            name, inn = parts[0].strip(), parts[1].strip()
            c.execute("INSERT OR REPLACE INTO companies (inn, name) VALUES (?, ?)", (inn, name))
            companies_added += 1
        except Exception as e:
            print(f"Ошибка строки '{line}': {e}")
    
    conn.commit()
    conn.close()
    
    await message.reply(f"✅ **Загружено компаний: {companies_added}**\n"
                       f"📋 Посмотреть: `/list`", parse_mode='Markdown')
    await state.clear()

@dp.message(Command('list'))
async def list_companies(message: types.Message):
    conn = sqlite3.connect('tenders.db')
    c = conn.cursor()
    companies = c.execute("SELECT name, inn FROM companies").fetchall()
    conn.close()
    
    if companies:
        text = f"📋 **Компании для мониторинга** ({len(companies)} шт.):\n\n"
        for i, (name, inn) in enumerate(companies, 1):
            text += f"{i}. **{name}** (`{inn}`)\n"
        text += f"\nℹ️ **Мониторинг ежедневно в 10:00**"
        await message.reply(text, parse_mode='Markdown')
    else:
        await message.reply("📭 **Список пуст**\n\n"
                           "➕ `/add_company \"Компания ИНН\"`\n"
                           "📋 `/load_companies` (списком)", parse_mode='Markdown')

async def on_startup():
    init_db()
    scheduler.add_job(check_tenders, 'interval', minutes=2)  # ТЕСТ: каждые 2 мин
    # scheduler.add_job(check_tenders, 'cron', hour=10, minute=0)  # ПРОД: 10:00
    scheduler.start()
    print("🚀 Бот запущен, планировщик активен")

if __name__ == '__main__':
    asyncio.run(dp.start_polling(bot, on_startup=on_startup))
