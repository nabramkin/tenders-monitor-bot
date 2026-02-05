import os
import asyncio
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
    log.warning("CHAT_ID is not set (0). Daily digest will NOT be delivered.")

COMPANIES_RAW = os.getenv("COMPANIES", "").strip()

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

# Триггеры: вендоры + типовые ИТ-фразы
VENDORS_AND_KEYWORDS = [
    "Lenovo", "Dell", "Cisco", "Huawei", "Supermicro", "Nvidia", "NetApp",
    "IBM", "Brocade", "Fortinet", "Juniper", "VMware", "Veeam", "HPE",
    "HP", "Oracle", "Fujitsu", "EMC",
    "техническая поддержка", "сервисная поддержка", "закупка оборудования",
    "поставка оборудования", "IT услуги", "IT решения", "консалтинг"
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
# BOT / SCHEDULER
# ----------------------------
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
scheduler = AsyncIOScheduler(timezone=MOSCOW_TZ)


# ----------------------------
# CORE LOGIC (KEYWORDS-ONLY)
# ----------------------------
def _matches_keywords(haystack_lower: str) -> bool:
    return any(kw.lower() in haystack_lower for kw in VENDORS_AND_KEYWORDS)


async def _parse_feed(url: str):
    # feedparser.parse is blocking -> run in thread
    return await asyncio.to_thread(feedparser.parse, url)


async def collect_tenders() -> tuple[list[dict], dict]:
    """
    Collect tenders matching keywords from RSS feeds.
    No company matching. Dedupe by URL within this run.
    Returns: (items, stats)
    """
    found: list[dict] = []
    seen_links: set[str] = set()

    stats = {
        "platforms": {},
        "total_entries": 0,
        "keyword_hits": 0,
        "results": 0,
    }

    for platform, rss_url in PLATFORMS.items():
        try:
            feed = await _parse_feed(rss_url)
            entries = getattr(feed, "entries", []) or []
            stats["platforms"][platform] = {"entries": len(entries), "bozo": getattr(feed, "bozo", 0)}

            stats["total_entries"] += len(entries)

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

                if not _matches_keywords(haystack):
                    continue

                stats["keyword_hits"] += 1
                seen_links.add(link)

                pub_date = getattr(entry, "published", None) or getattr(entry, "updated", None) or "Неизвестно"
                end_date = getattr(entry, "updated", None) or "Неизвестно"

                found.append({
                    "platform": platform,
                    "title": title,
                    "url": link,
                    "pub_date": str(pub_date),
                    "end_date": str(end_date),
                })

        except Exception as e:
            log.exception("RSS error on %s: %s", platform, e)
            stats["platforms"][platform] = {"entries": 0, "error": str(e)}

    stats["results"] = len(found)
    return found, stats


async def send_daily_digest(target_chat_id: int):
    """Send digest to target chat."""
    now_msk = datetime.now(MOSCOW_TZ).strftime("%Y-%m-%d %H:%M")

    companies = parse_companies(COMPANIES_RAW)
    companies_line = ", ".join([f"{name} ({inn})" for name, inn in companies]) if companies else "—"

    tenders, stats = await collect_tenders()

    header = (
        f"📌 Тендеры по ключевым словам — {now_msk} MSK\n"
        f"Мониторим для: {companies_line}\n\n"
    )

    if not tenders:
        msg = (
            header +
            "Ничего подходящего не найдено.\n\n"
            f"Статистика: entries={stats['total_entries']}, keyword_hits={stats['keyword_hits']}, results={stats['results']}"
        )
        await bot.send_message(target_chat_id, msg)
        return

    # группируем по площадкам
    by_platform: dict[str, list[dict]] = {}
    for t in tenders:
        by_platform.setdefault(t["platform"], []).append(t)

    parts = [header]
    for platform, items in by_platform.items():
        parts.append(f"🌐 {platform} — {len(items)}\n")
        for it in items[:30]:
            parts.append(
                f"• {it['title']}\n"
                f"  {it['url']}\n"
            )
        parts.append("\n")

    parts.append(f"Статистика: entries={stats['total_entries']}, keyword_hits={stats['keyword_hits']}, results={stats['results']}\n")

    text = "".join(parts)
    chunks = [text[i:i + 3500] for i in range(0, len(text), 3500)]
    for ch in chunks:
        await bot.send_message(target_chat_id, ch)


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
        "• /run — выполнить проверку сейчас (ответ придёт сюда же)\n"
        "• /debug_rss — проверить RSS (entries/bozo)\n\n"
        "Компании задаются через ENV COMPANIES (Название|ИНН).\n"
        "Рассылка: каждый день в 10:00 МСК (в CHAT_ID)."
    )


@dp.message(Command("list"))
async def list_handler(message: types.Message):
    companies = parse_companies(COMPANIES_RAW)
    await message.reply(companies_to_text(companies), parse_mode="Markdown")


@dp.message(Command("whoami"))
async def whoami_handler(message: types.Message):
    await message.reply(f"Твой chat_id: {message.chat.id}")


@dp.message(Command("run"))
async def run_now_handler(message: types.Message):
    log.info("RUN received from chat_id=%s", message.chat.id)
    try:
        await message.reply("⏳ Запускаю проверку…")
        await send_daily_digest(message.chat.id)
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
            feed = await _parse_feed(rss_url)
            n = len(getattr(feed, "entries", []) or [])
            total += n
            bozo = getattr(feed, "bozo", 0)
            if bozo:
                err = getattr(feed, "bozo_exception", None)
                lines.append(f"{platform}: {n} (bozo=1, err={err})")
            else:
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

    # каждый день в 10:00 по Москве -> отправка в CHAT_ID
    if CHAT_ID != 0:
        scheduler.add_job(
            lambda: asyncio.create_task(send_daily_digest(CHAT_ID)),
            "cron",
            hour=10,
            minute=0,
            coalesce=True,
            max_instances=1,
        )
        log.info("Daily digest scheduled at 10:00 MSK to CHAT_ID=%s", CHAT_ID)
    else:
        log.warning("Daily digest NOT scheduled because CHAT_ID=0")

    scheduler.start()
    log.info("Scheduler started.")


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
    # to avoid 405 for uptime HEAD probes
    return {}


@app.get("/health")
async def health():
    return {"status": "healthy"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
