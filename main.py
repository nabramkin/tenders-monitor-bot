import os
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import feedparser
from fastapi import FastAPI, Request
import uvicorn

from aiogram import Bot, Dispatcher, types
from aiogram.types import Update
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage

from apscheduler.schedulers.asyncio import AsyncIOScheduler


# ----------------------------
# CONFIG / ENV
# ----------------------------
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("tender-bot")

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

CHAT_ID = int(os.getenv("CHAT_ID") or "0")
if CHAT_ID == 0:
    log.warning("CHAT_ID is not set (0). Bot will NOT be able to send daily digest.")

COMPANIES_RAW = os.getenv("COMPANIES", "").strip()

# Render hostname for webhook
RENDER_HOST = os.getenv("RENDER_EXTERNAL_HOSTNAME") or "localhost:8000"
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
WEBHOOK_URL = f"https://{RENDER_HOST}{WEBHOOK_PATH}"

PORT = int(os.getenv("PORT", "8000"))

# Москва
MOSCOW_TZ = ZoneInfo("Europe/Moscow")

# RSS платформы
PLATFORMS = {
    "Bidzaar": "https://bidzaar.com/rss/new",
    "Сбербанк-АСТ": "https://utp.sberbank-ast.ru/rss/rss.xml",
    "ЭТП Газпромбанк": "https://etpgpb.ru/rss/rss.xml",
    "РТС-Тендер": "https://www.rts-tender.ru/rss/rss.ashx",
    "РосТендер": "https://rostender.info/rss",
    "BiCoTender": "https://www.bicotender.ru/rss.xml",
    "B2B-Center": "https://www.b2b-center.ru/rss/rss.xml",
}

# Ключевые слова
VENDORS_AND_KEYWORDS = [
    "Lenovo", "Dell", "Cisco", "Huawei", "Supermicro", "Nvidia", "NetApp",
    "IBM", "Brocade", "Fortinet", "Juniper", "VMware", "Veeam", "HPE",
    "HP", "Oracle", "Fujitsu", "EMC", "техническая поддержка", "сервисная поддержка",
    "консалтинг", "IT услуги", "IT решения", "поставка оборудования"
]


# ----------------------------
# PARSING COMPANIES FROM ENV
# ----------------------------
def parse_companies(raw: str) -> list[tuple[str, str]]:
    """
    Returns list of (name, inn).
    Accepts:
      - lines: "Name|INN"
      - or single line separated by ';'
    """
    raw = (raw or "").strip()
    if not raw:
        return []

    parts: list[str] = []
    # allow both ; and newlines
    for chunk in raw.split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        parts.extend([line.strip() for line in chunk.splitlines() if line.strip()])

    companies: list[tuple[str, str]] = []
    for line in parts:
        if "|" not in line:
            continue
        name, inn = line.split("|", 1)
        name, inn = name.strip(), inn.strip()
        if name and inn:
            companies.append((name, inn))

    return companies


def companies_to_text(companies: list[tuple[str, str]]) -> str:
    if not companies:
        return "📭 Компаний нет. Задай ENV `COMPANIES` в формате `Название|ИНН`."
    lines = [f"{i}. **{name}** (`{inn}`)" for i, (name, inn) in enumerate(companies, 1)]
    return "📋 **Компании:**\n\n" + "\n".join(lines)


# ----------------------------
# BOT
# ----------------------------
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
scheduler = AsyncIOScheduler(timezone=MOSCOW_TZ)


# ----------------------------
# CORE LOGIC
# ----------------------------
def collect_tenders(companies: list[tuple[str, str]]) -> list[dict]:
    """
    Collects tenders from RSS *for this run only*.
    No DB, no history. Dedupe only by URL within this run.
    """
    found: list[dict] = []
    seen_links: set[str] = set()

    for platform, rss_url in PLATFORMS.items():
        try:
            feed = feedparser.parse(rss_url)
            entries = getattr(feed, "entries", []) or []

            for entry in entries:
                title = getattr(entry, "title", "") or ""
                summary = (
                    getattr(entry, "summary", "")
                    or getattr(entry, "description", "")
                    or ""
                )

                haystack = (title + " " + summary).lower()

                link = getattr(entry, "link", "") or ""
                if not link or link in seen_links:
                    continue

                # keyword must be present (ищем по title+summary)
                if not any(kw.lower() in haystack for kw in VENDORS_AND_KEYWORDS):
                    continue

                # match company in title+summary
                for company_name, inn in companies:
                    if company_name.lower() in haystack:
                        seen_links.add(link)
                        pub_date = getattr(entry, "published", None) or getattr(entry, "updated", None) or "Неизвестно"
                        end_date = getattr(entry, "updated", None) or "Неизвестно"

                        found.append({
                            "platform": platform,
                            "title": title,
                            "url": link,
                            "pub_date": str(pub_date),
                            "end_date": str(end_date),
                            "company": company_name,
                            "inn": inn,
                        })
                        break

        except Exception as e:
            log.exception("RSS error on %s: %s", platform, e)

    return found


async def send_daily_digest():
    """Runs daily at 10:00 MSK (and manually via /run)"""
    companies = parse_companies(COMPANIES_RAW)

    now_msk = datetime.now(MOSCOW_TZ).strftime("%Y-%m-%d %H:%M")
    log.info("Digest at %s MSK. Companies: %d", now_msk, len(companies))

    if CHAT_ID == 0:
        log.warning("CHAT_ID is 0 -> skip sending")
        return

    if not companies:
        await bot.send_message(
            CHAT_ID,
            "⚠️ Нет компаний для мониторинга.\n"
            "Задай ENV COMPANIES в формате:\n"
            "Газпром|1234567890",
        )
        return

    tenders = collect_tenders(companies)

    # Группируем по компании
    by_company: dict[str, list[dict]] = {}
    for t in tenders:
        by_company.setdefault(t["company"], []).append(t)

    header = f"📌 Тендеры (дайджест) — {now_msk} MSK\n\n"
    if not tenders:
        msg = header + "Ничего подходящего не нашёл по заданным компаниям/ключевым словам."
        await bot.send_message(CHAT_ID, msg)
        return

    parts = [header]
    for company, items in by_company.items():
        parts.append(f"🏢 {company} — {len(items)}\n")
        for it in items[:30]:
            parts.append(
                f"• {it['platform']} — {it['title']}\n"
                f"  {it['url']}\n"
            )
        parts.append("\n")

    text = "".join(parts)

    # Telegram лимит ~4096, режем
    chunks = [text[i:i + 3500] for i in range(0, len(text), 3500)]
    for ch in chunks:
        await bot.send_message(CHAT_ID, ch)


# ----------------------------
# HANDLERS
# ----------------------------
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.reply(
        "🤖 Tender Bot\n\n"
        "Команды:\n"
        "• /list — показать список компаний (из ENV)\n"
        "• /whoami — показать chat_id\n"
        "• /run — выполнить проверку сейчас\n"
        "• /debug_rss — проверить, живые ли RSS\n\n"
        "Компании задаются через ENV COMPANIES (Название|ИНН).\n"
        "Рассылка: каждый день в 10:00 МСК."
    )


@dp.message(Command("list"))
async def list_handler(message: types.Message):
    companies = parse_companies(COMPANIES_RAW)
    # тут можно Markdown, но безопаснее plain text
    await message.reply(companies_to_text(companies), parse_mode="Markdown")


@dp.message(Command("whoami"))
async def whoami_handler(message: types.Message):
    await message.reply(f"Твой chat_id: {message.chat.id}")


@dp.message(Command("run"))
async def run_now_handler(message: types.Message):
    log.info("RUN command received from chat_id=%s text=%r", message.chat.id, message.text)
    try:
        await message.reply("⏳ Запускаю проверку…")
        await send_daily_digest()
        await message.reply("✅ Готово.")
    except Exception as e:
        log.exception("Error in /run: %s", e)
        await message.reply(f"❌ Ошибка при /run: {e}")


@dp.message(Command("debug_rss"))
async def debug_rss_handler(message: types.Message):
    lines = ["🧪 RSS debug:\n"]
    total = 0
    for platform, rss_url in PLATFORMS.items():
        try:
            feed = feedparser.parse(rss_url)
            n = len(getattr(feed, "entries", []) or [])
            total += n
            lines.append(f"{platform}: {n}")
        except Exception as e:
            lines.append(f"{platform}: ERROR {e}")
    lines.append(f"\nTotal entries: {total}")
    await message.reply("\n".join(lines))


# ----------------------------
# FASTAPI
# ----------------------------
app = FastAPI()

@app.on_event("startup")
async def on_startup():
    await bot.set_webhook(WEBHOOK_URL, drop_pending_updates=True)
    log.info("Webhook set: %s", WEBHOOK_URL)

    # каждый день в 10:00 по Москве
    scheduler.add_job(
        send_daily_digest,
        "cron",
        hour=10,
        minute=0,
        coalesce=True,
        max_instances=1,
    )
    scheduler.start()
    log.info("Scheduler started. Daily digest at 10:00 MSK.")


@app.on_event("shutdown")
async def on_shutdown():
    try:
        await bot.delete_webhook()
    except Exception:
        pass
    try:
        scheduler.shutdown(wait=False)
    except Exception:
        pass


@app.post(WEBHOOK_PATH)
async def webhook(request: Request):
    data = await request.json()
    telegram_update = Update(**data)
    await dp.feed_update(bot, telegram_update)
    return {"ok": True}


@app.get("/")
async def root():
    return {"status": "IT Tender Bot ✅", "webhook": WEBHOOK_URL}


@app.head("/")
async def head_root():
    return {}


@app.get("/health")
async def health():
    return {"status": "healthy"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
