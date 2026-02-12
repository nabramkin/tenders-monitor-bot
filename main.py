import asyncio
import os
import logging
from flask import Flask, request
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from config import BOT_TOKEN, YOUR_USER_ID
from handlers.user import router as user_router
from scheduler import start_scheduler
import threading

# Flask для Render (ОБЯЗАТЕЛЬНО!)
app = Flask(__name__)

@app.route("/")
@app.route("/health")
def health():
    return "✅ Bot health OK - Render port detected!"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Глобальные переменные для бота
bot_instance = None
dp_instance = None

async def cleanup_webhook(bot):
    """Жёсткое удаление webhook"""
    try:
        webhook_info = await bot.get_webhook_info()
        logger.info(f"🔍 Webhook: {webhook_info.url}")
        
        for _ in range(3):
            await bot.delete_webhook(drop_pending_updates=True)
            await asyncio.sleep(0.5)
        
        final_info = await bot.get_webhook_info()
        logger.info(f"✅ Webhook чист: {final_info.url is None}")
    except Exception as e:
        logger.error(f"Webhook cleanup error: {e}")

async def start_bot():
    """Запуск бота в фоне"""
    global bot_instance, dp_instance
    
    bot_instance = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    await cleanup_webhook(bot_instance)
    
    dp_instance = Dispatcher(storage=MemoryStorage())
    dp_instance.include_router(user_router)
    
    scheduler_task = asyncio.create_task(start_scheduler(bot_instance))
    
    try:
        logger.info("🚀 Bot polling started")
        await dp_instance.start_polling(
            bot_instance,
            skip_updates=True
        )
    except Exception as e:
        logger.error(f"❌ Bot error: {e}")
    finally:
        await bot_instance.session.close()
        if scheduler_task and not scheduler_task.done():
            scheduler_task.cancel()

def run_bot_thread():
    """Бот в отдельном потоке asyncio"""
    try:
        asyncio.run(start_bot())
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    
    # 1. Flask запускается ПЕРВЫМ (Render увидит порт!)
    logger.info(f"🌐 Flask на порту {port}")
    threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=port, debug=False),
        daemon=True
    ).start()
    
    # 2. Бот запускается ВТОРЫМ (не блокирует Flask)
    logger.info("🤖 Starting bot...")
    run_bot_thread()
        # Финальная проверка
        webhook_info = await bot.get_webhook_info()
        if webhook_info.url or webhook_info.pending_update_count > 0:
            logger.warning(f"⚠️  Webhook всё ещё жив: {webhook_info}")
        else:
            logger.info("✅ Webhook полностью чистый!")
            
    except Exception as e:
        logger.error(f"❌ Ошибка очистки webhook: {e}")

async def run_bot():
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    try:
        # 1. ЖЁСТКАЯ ОЧИСТКА ВЕБХУКОВ
        await cleanup_webhook(bot)
        
        # 2. Инициализируем диспетчер
        dp = Dispatcher(storage=MemoryStorage())
        dp.include_router(user_router)
        
        # 3. Планировщик
        scheduler_task = asyncio.create_task(start_scheduler(bot))
        
        logger.info("🚀 Запуск polling...")
        # 4. Поллинг с обработкой ошибок
        await dp.start_polling(
            bot, 
            skip_updates=True,
            handle_signals=False  # Render сам управляет сигналами
        )
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка бота: {e}")
        raise
    finally:
        logger.info("🛑 Закрытие бота...")
        await bot.session.close()
        if scheduler_task and not scheduler_task.done():
            scheduler_task.cancel()
        logger.info("✅ Бот остановлен")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    
    def run_flask():
        app.run(
            host="0.0.0.0",
            port=port,
            debug=False,
            use_reloader=False
        )
    
    # Flask в фоне
    from threading import Thread
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Бот в основном потоке
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("🛑 Получен сигнал остановки")
        # Финальная проверка
        webhook_info = await bot.get_webhook_info()
        if webhook_info.url or webhook_info.pending_update_count > 0:
            logger.warning(f"⚠️  Webhook всё ещё жив: {webhook_info}")
        else:
            logger.info("✅ Webhook полностью чистый!")
            
    except Exception as e:
        logger.error(f"❌ Ошибка очистки webhook: {e}")

async def run_bot():
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    try:
        # 1. ЖЁСТКАЯ ОЧИСТКА ВЕБХУКОВ
        await cleanup_webhook(bot)
        
        # 2. Инициализируем диспетчер
        dp = Dispatcher(storage=MemoryStorage())
        dp.include_router(user_router)
        
        # 3. Планировщик
        scheduler_task = asyncio.create_task(start_scheduler(bot))
        
        logger.info("🚀 Запуск polling...")
        # 4. Поллинг с обработкой ошибок
        await dp.start_polling(
            bot, 
            skip_updates=True,
            handle_signals=False  # Render сам управляет сигналами
        )
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка бота: {e}")
        raise
    finally:
        logger.info("🛑 Закрытие бота...")
        await bot.session.close()
        if scheduler_task and not scheduler_task.done():
            scheduler_task.cancel()
        logger.info("✅ Бот остановлен")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    
    def run_flask():
        app.run(
            host="0.0.0.0",
            port=port,
            debug=False,
            use_reloader=False
        )
    
    # Flask в фоне
    from threading import Thread
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Бот в основном потоке
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("🛑 Получен сигнал остановки")
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
