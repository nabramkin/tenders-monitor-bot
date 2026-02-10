import asyncio
import os
import logging
from flask import Flask
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from config import BOT_TOKEN
from handlers.user import router as user_router
from scheduler import start_scheduler

# Flask для UptimeRobot (синхронный)
app = Flask(__name__)

@app.route('/')
@app.route('/health')
def ping():
    return "✅ Bot alive!"

logging.basicConfig(level=logging.INFO)

async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(user_router)
    
    # Запуск планировщика в фоне
    scheduler_task = asyncio.create_task(start_scheduler(bot))
    
    try:
        # Бот polling (async) + Flask в отдельном потоке (sync)
        await asyncio.gather(
            dp.start_polling(bot, skip_updates=True),
            asyncio.to_thread(
                lambda: app.run(
                    host='0.0.0.0', 
                    port=int(os.environ.get("PORT", 10000)),
                    debug=False,
                    use_reloader=False
                )
            )
        )
    except KeyboardInterrupt:
        logging.info("🛑 Остановка...")
    finally:
        # Корректная остановка
        await bot.session.close()
        if not scheduler_task.done():
            scheduler_task.cancel()
        logging.info("✅ Все остановлено")

if __name__ == "__main__":
    asyncio.run(main())
