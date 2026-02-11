import asyncio
import os
import logging
from flask import Flask
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from config import BOT_TOKEN, YOUR_USER_ID
from handlers.user import router as user_router
from scheduler import start_scheduler

# Flask только для простого ping, не для gunicorn; Render будет как `web: python main.py`
app = Flask(__name__)

@app.route('/')
@app.route('/health')
def ping():
    return "✅ Bot alive! 👋"

logging.basicConfig(level=logging.INFO)

async def main():
    bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(user_router)

    # Для отладки: отправим в чат /start сообщение при запуске
    try:
        await bot.send_message(chat_id=YOUR_USER_ID, text="✅ Бот запущен!")
    except Exception as _:
        pass

    # Запускаем планировщик в фоне
    scheduler_task = asyncio.create_task(start_scheduler(bot))

    try:
        # Бот: polling + Flask в отдельном потоке
        await asyncio.gather(
            dp.start_polling(bot, skip_updates=True),
            asyncio.to_thread(
                lambda: app.run(
                    host="0.0.0.0",
                    port=int(os.environ.get("PORT", 10000)),
                    debug=False,
                    use_reloader=False
                )
            )
        )
    except (KeyboardInterrupt, SystemExit):
        logging.info("🛑 Остановка бота...")
    finally:
        await bot.session.close()
        if not scheduler_task.done():
            scheduler_task.cancel()
        logging.info("✅ Все сервисы остановлены.")

if __name__ == "__main__":
    asyncio.run(main())
