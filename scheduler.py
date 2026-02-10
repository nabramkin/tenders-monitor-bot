import asyncio
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from config import BOT_TOKEN, YOUR_USER_ID
from aiogram import Bot

scheduler = AsyncIOScheduler()

async def start_scheduler(bot: Bot):
    """Рассылка ТОЛЬКО с 10:00 до 12:00 каждые 30 мин"""
    
    # Понедельник-Пятница, 10:00-12:00 каждые 30 мин
    scheduler.add_job(
        send_tenders_to_owner,  # ← ТВОЯ ФУНКЦИЯ
        CronTrigger(
            hour="10-11", 
            minute="0,30", 
            day_of_week="mon-fri"
        ),
        id='morning_tenders',
        replace_existing=True
    )
    scheduler.start()
    logging.info("✅ Scheduler: 10:00-12:00 Пн-Пт каждые 30 мин")
    
    while True:
        await asyncio.sleep(60)
