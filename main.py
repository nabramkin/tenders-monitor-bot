import asyncio
import os
import logging
from flask import Flask
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode          # ← вот так правильно для 3.13+
from aiogram.client.default import DefaultBotProperties
from config import BOT_TOKEN, YOUR_USER_ID
from handlers.user import router as user_router
from scheduler import start_scheduler

# Flask для health‑чека (Render / UptimeRobot)
app = Flask(__name__)

@app.route("/")
@app.route("/health")
def health():
    return "✅ Bot + Flask health check OK"

logging.basicConfig(level=logging.INFO)

async def run_bot():
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(user_router)
  
    scheduler_task = asyncio.create_task(start_scheduler(bot))
await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot, skip_updates=True)

    try:
        await dp.start_polling(bot, skip_updates=True)
    except (KeyboardInterrupt, SystemExit):
        logging.info("🛑 Остановка бота...")
    finally:
        await bot.session.close()
        if not scheduler_task.done():
            scheduler_task.cancel()
        logging.info("✅ Все сервисы остановлены.")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))

    def run_flask():
        app.run(
            host="0.0.0.0",
            port=port,
            debug=False,
            use_reloader=False
        )

    from threading import Thread
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()

    asyncio.run(run_bot())
