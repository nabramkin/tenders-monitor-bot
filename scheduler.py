import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from config import BOT_TOKEN, YOUR_USER_ID
from aiogram import Bot

scheduler = AsyncIOScheduler()

async def start_scheduler(bot: Bot):
    """Запуск планировщика задач"""
    scheduler.add_job(
        your_tender_check_function,  # ← ЗАМЕНИ на свою функцию!
        trigger='interval',
        minutes=30,
        id='tender_check',
        replace_existing=True
    )
    scheduler.start()
    logging.info("✅ Scheduler запущен (каждые 30 мин)")
    
    # Держим задачу живой
    while True:
        await asyncio.sleep(60)
