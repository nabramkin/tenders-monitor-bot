import aioschedule
import asyncio
from datetime import datetime
from utils.gigachat import GigaChatClient
from config import YOUR_USER_ID, COMPANIES
from scrapers.contests import scrape_all_sites

client = GigaChatClient()
daily_sent = set()

async def daily_report(bot):
    now = datetime.now()
    
    # 10:00-12:00 и не отправляли сегодня
    if 10 <= now.hour < 12 and now.date() not in daily_sent:
        try:
            print(f"🔍 Парсинг тендеров... {now}")
            contests = await scrape_all_sites()
            
            if not contests:
                await bot.send_message(YOUR_USER_ID, "📭 ИТ-тендеров сегодня нет")
                return
            
            # Форматируем для GigaChat
            data_text = ""
            for c in contests:
                trigger = "⭐ Твоя компания" if any(inn in c['title']+c['company'] 
                    for inn in [comp.split()[-1] for comp in COMPANIES]) else "💻 ИТ"
                data_text += f"{trigger}: {c['title']}\n{c['company']} | {c['source']}\n{c['url']}\n\n"
            
            report = await client.chat_completion([{
                "role": "user", 
                "content": f"""ИТ-тендеры для компаний: {', '.join(COMPANIES)}

Фокус: техподдержка, оборудование, вендоры (Cisco, HPE, Microsoft...)

Данные:
{data_text}

📊 Сделай краткий дайджест:
• Группируй по типу (оборудование/ПО/услуги)
• Выдели горячие (сегодня/завтра) 
• Цены если есть
• Markdown с кликабельными ссылками"""
            }])
            
            await bot.send_message(YOUR_USER_ID, f"💻 <b>ИТ-Дайджест {now.strftime('%d.%m')}</b>\n\n{report}", parse_mode="HTML")
            daily_sent.add(now.date())
            print(f"✅ Отчёт отправлен: {len(contests)} тендеров")
            
        except Exception as e:
            print(f"❌ Ошибка отчёта: {e}")
            await bot.send_message(YOUR_USER_ID, f"❌ Ошибка парсинга: {e}")

async def start_scheduler(bot):
    aioschedule.every().hour.do(lambda: asyncio.create_task(daily_report(bot)))
    while True:
        aioschedule.run_pending()
        await asyncio.sleep(60)
