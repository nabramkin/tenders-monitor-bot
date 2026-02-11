from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timedelta
import asyncio

from scrapers.contests import scrape_all_sites, is_it_relevant, format_tender_message
from config import YOUR_USER_ID

async def send_daily_tenders(bot: Bot):
    """Ежедневная рассылка ИТ‑тендеров 1 раз в день между 10:00 и 12:00."""
    tenders = await scrape_all_sites()
    it_tenders = [t for t in tenders if is_it_relevant(t)]
    # последние 2 дня
    fresh = [t for t in it_tenders if t["date"] >= datetime.now().date() - timedelta(days=2)]

    text = format_tender_message(fresh)
    try:
        await bot.send_message(
            chat_id=YOUR_USER_ID,
            text=text,
            parse_mode="HTML"
        )
    except Exception as e:
        print(f"❌ Ошибка рассылки: {e}")


async def start_scheduler(bot: Bot):
    """Запускаем асинхронный планировщик."""
    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_daily_tenders, CronTrigger(hour="10-11", minute=0, jitter=2*60), args=[bot])
    scheduler.add_job(print, CronTrigger(hour="*", minute="30", jitter=20), args=["🤖 [SERVICE] GigaChat token updated (stub)."])
    scheduler.start()

    try:
        while True:
            await asyncio.sleep(60)
    except asyncio.CancelledError:
        scheduler.shutdown(wait=True)
