import asyncio
from datetime import datetime, timedelta
from config import COMPANIES, IT_VENDORS, IT_KEYWORDS, SITES

async def scrape_all_sites():
    """Заглушка для демонстрации; в продакшен — реализовать парсинг."""
    await asyncio.sleep(1)  # имитация задержки
    t = datetime.now().strftime("%H:%M:%S")
    return [
        {"title": "Тендер 1", "company": "АКРОН", "date": datetime.now().date(),
         "url": "#", "source": "rostender.info"},
        {"title": "Тендер 2 ИТ‑услуги", "company": "Совкомбанк", "date": datetime.now().date(),
         "url": "#", "source": "b2b-center.ru"},
    ]


def is_it_relevant(tender) -> bool:
    text = f"{tender['title']} {tender['company']}".lower()
    # 1. Компании по ИНН
    company_inns = [c.split()[-1] for c in COMPANIES]
    if any(inn in text for inn in company_inns):
        return True
    # 2. Вендоры
    if any(vendor.lower() in text for vendor in IT_VENDORS):
        return True
    # 3. Ключевые слова ИТ
    if any(keyword in text for keyword in IT_KEYWORDS):
        return True
    return False


def format_tender_message(tenders) -> str:
    """Превращает список тендеров в читаемый текст‑отчёт."""
    if not tenders:
        return "🔹 За последние 2 дня новых ИТ‑тендеров не найдено."

    lines = [f"📌 <b>Найдено {len(tenders)} ИТ‑тендера:</b>"]
    for t in tenders:
        lines.append(
            f"▸ <b>{t['company']}</b>\n"
            f"   👉 {t['title']}\n"
            f"   🌐 {t['source']:30} | {t['date']}"
        )
    return "\n\n".join(lines)
