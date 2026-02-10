import asyncio
import logging
from flask import Flask
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from config import BOT_TOKEN
from handlers.user import router as user_router
from scheduler import start_scheduler

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(user_router)
    
    # Запуск планировщика в фоне
    scheduler_task = asyncio.create_task(start_scheduler(bot))
    
    # Flask для UptimeRobot пингов
    @app.route('/')
    @app.route('/health')
    def ping():
        return "✅ Bot alive!"
    
    try:
        # Бот + Flask вместе
        await asyncio.gather(
            dp.start_polling(bot),
            asyncio.to_thread(app.run, host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
        )
    finally:
        scheduler_task.cancel()

if __name__ == "__main__":
    asyncio.run(main())
