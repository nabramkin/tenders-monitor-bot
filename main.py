import asyncio
import os
import logging
from flask import Flask
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from config import BOT_TOKEN
from handlers.user import router as user_router
from scheduler import start_scheduler

app = Flask(__name__)

@app.route("/")
@app.route("/health")
def health():
    return "✅ Bot health OK"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def cleanup_webhook(bot):
    try:
        webhook_info = await bot.get_webhook_info()
        logger.info(f"🔍 Webhook: {webhook_info.url}")
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("✅ Webhook удалён")
    except Exception as e:
        logger.error(f"Webhook error: {e}")

async def run_bot():
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    await cleanup_webhook(bot)
    
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(user_router)
    
    scheduler_task = asyncio.create_task(start_scheduler(bot))
    
    try:
        logger.info("🚀 Bot started")
        await dp.start_polling(bot, skip_updates=True)
    except Exception as e:
        logger.error(f"❌ Bot error: {e}")
    finally:
        await bot.session.close()
        scheduler_task.cancel()
        logger.info("✅ Bot stopped")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    
    def run_flask():
        app.run(host="0.0.0.0", port=port, debug=False)
    
    from threading import Thread
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    logger.info(f"🌐 Flask на {port}")
    asyncio.run(run_bot())
