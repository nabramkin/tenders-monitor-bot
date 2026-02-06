import os
import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import feedparser
import aiohttp
from fastapi import FastAPI
import uvicorn

from aiogram import Bot, Dispatcher, types
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

# куда слать ежедневную рассылку (в 10:00 МСК)
CHAT_ID = int(os.getenv("CHAT_ID") or "0")

# просто список компаний "для ориентира" (не участвует в фильтрации)
COMPANIES_RAW = os.getenv("COMPANIES", "").strip()

PORT = int(os.getenv("PORT", "8000"))
MOSCOW_TZ = ZoneInfo("Europe/Moscow")


# ----------------------------
# RSS
# ----------------------------
PLATFORMS = {
    "BiCoTender": "https://www.bicotender.ru/rss.xml",
    "РосТендер": "https://rostender.info/rss",
    "Bidzaar": "https://bidzaar.com/rss/new",
    "Сбербанк-АСТ": "https://utp.sberbank-ast.ru/rss/rss.xml",
    "ЭТП Газпромбанк": "https://etpgpb.ru/rss/rss.xml",
    "РТС-Тендер": "https://www.rts-tender.ru/rss/rss.ashx",
    "B2B-Center": "https://www.b2b-center.ru/rss/rss.xml",
}

# триггеры (keywords-only)
VENDORS_AND_KEYWORDS = [
    "Lenovo", "Dell", "Cisco", "Huawei", "Supermicro", "Nvidia", "NetApp",
    "IBM", "Brocade", "Fortinet", "Juniper", "VMware", "Veeam", "HPE",
    "HP", "Oracle", "Fujitsu", "EMC",
    "техническая поддержка", "сервисная поддержка",
    "закупка оборудования", "поставка оборудования",
    "IT услуги", "IT решения", "консалтинг",
]


# ----------------------------
# HELPERS
# ----------------------------
def parse_companies(raw: str) -> list[tuple[str, str]]:
    raw = (raw or "").strip()
    if not raw:
        return []
    parts: list[str] = []
    for chunk in raw.split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        parts.extend([line.strip() for line in chunk.splitlines() if line.strip()])
    out: list[tuple[str, str]] = []
    for line in parts:
        if "|" not in line:
            continue
        name, inn = line.split("|", 1)
        name, inn = name.strip(), inn.strip()
        if name and inn:
            out.append((name, inn))
    return out


def companies_to_text(companies: list[tuple[str, str]]) -> str:
    if not companies:
        return "Компаний нет. Задай ENV COMPANIES в формате: Название|ИНН"
    lines = [f"{i}. {name} ({inn})" for i, (name, inn) in enumerate(companies, 1)]
    return "Компании:\n" + "\n".join(lines)


def matches_keywords(text_lower: str) -> bool:
    return any(kw.lower() in text_lower for kw in VENDORS_AND_KEYWORDS)


async def parse_feed(url: str):
    """
    Fetch RSS/Atom by HTTP (aiohttp) -> parse text with feedparser.
    This helps with redirects, user-agent, encoding and gives http/final_url for debug.
    """
    timeout = aiohttp.ClientTimeout(total=25)
    headers = {"User-Agent": "Mozilla/5.0 (compatible; TenderBot/1.0)"}

    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
        async with session.get(url, allow_redirects=True) as resp:
            # NOTE: errors="ignore" to avoid decode crashes on bad encodings
            text = await resp.text(errors="ignore")
            feed = feedparser.parse(text)

            # add debug info
            feed.http_status = resp.status
            feed.final_url = str(resp.url)

            return feed


# ----------------------------
# CORE
# ----------------------------
async def collect_tenders() -> tuple[list[dict], dict]:
    found: list[dict] = []
    seen_links: set[str] = set()
    stats = {"total_entries": 0, "keyword_hits": 0, "results": 0, "platforms": {}}

    for platform, rss_url in PLATFORMS.items():
        try:
            feed = await parse_feed(rss_url)
            entries = getattr(feed, "entries", []) or []

            stats["platforms"][platform] = {
                "entries": len(entries),
                "http": getattr(feed, "http_status", None),
                "final_url": getattr(feed, "final_url", ""),
                "bozo": int(getattr(feed, "bozo", 0)),
                "err": str(getattr(feed, "bozo_exception", "")) if getattr(feed, "bozo", 0) else "",
            }

            stats["total_entries"] += len(entries)

            for entry in entries:
                title = getattr(entry, "title", "") or ""
                summary = getattr(entry, "summary", "") or getattr(entry, "description", "") or ""
                haystack = (title + " " + summary).lower()

                link = getattr(entry, "link", "") or ""
                if not link or link in seen_links:
                    continue

                if not matches_keywords(haystack):
                    continue

                stats["keyword_hits"] += 1
                seen_links.add(link)

                pub_date = getattr(entry, "published", None) or getattr(entry, "updated", None) or "Неизвестно"

                found.append({
                    "platform": platform,
                    "title": title,
                    "url": link,
                    "pub_date": str(pub_date),
                })

        except Exception as e:
            log.exception("RSS error %s: %s", platform, e)
            stats["platforms"][platform] = {
                "entries": 0,
                "http": None,
                "final_url": "",
                "bozo": 1,
                "err": str(e),
            }

    stats["results"] = len(found)
    return found, stats


async def send_digest(chat_id: int):
    now_msk = datetime.now(MOSCOW_TZ).strftime("%Y-%m-%d %H:%M")
    companies = parse_companies(COMPANIES_RAW)
    companies_line = ", ".join([f"{n}({i})" for n, i in companies]) if companies else "—"

    tenders, stats = await collect_tenders()

    header = (
        f"Тендеры по ключевым словам — {now_msk} МСК\n"
        f"Компании (для ориентира): {companies_line}\n\n"
    )

    if not tenders:
        msg = (
            header +
            "Ничего подходящего не найдено.\n\n"
            f"Статистика: entries={stats['total_entries']}, keyword_hits={stats['keyword_hits']}, results={stats['results']}"
        )
        await bot.send_message(chat_id, msg)
        return

    by_platform: dict[str, list[dict]] = {}
    for t in tenders:
        by_platform.setdefault(t["platform"], []).append(t)

    parts = [header]
    for platform, items in by_platform.items():
        parts.append(f"{platform}: {len(items)}\n")
        for it in items[:30]:
            parts.append(f"- {it['title']}\n  {it['url']}\n")
        parts.append("\n")

    parts.append(
        f"Статистика: entries={stats['total_entries']}, keyword_hits={stats['keyword_hits']}, results={stats['results']}\n"
    )

    text = "".join(parts)
    chunks = [text[i:i + 3500] for i in range(0, len(text), 3500)]
    for ch in chunks:
        await bot.send_message(chat_id, ch)


# ----------------------------
# BOT / DISPATCHER / SCHEDULER
# ----------------------------
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
scheduler = AsyncIOScheduler(timezone=MOSCOW_TZ)


async def daily_job():
    if CHAT_ID == 0:
        log.warning("CHAT_ID=0; daily job skipped")
        return
    await send_digest(CHAT_ID)


# ----------------------------
# HANDLERS
# ----------------------------
@dp.message(Command("start"))
async def start_handler(message: types.Message):
    await message.reply(
        "Tender Bot (polling)\n\n"
        "Команды:\n"
        "/list — компании из ENV\n"
        "/whoami — твой chat_id\n"
        "/run — запуск проверки сейчас\n"
        "/debug_rss — диагностика RSS\n\n"
        "Ежедневная рассылка: 10:00 МСК (в CHAT_ID)."
    )


@dp.message(Command("list"))
async def list_handler(message: types.Message):
    companies = parse_companies(COMPANIES_RAW)
    await message.reply(companies_to_text(companies))


@dp.message(Command("whoami"))
async def whoami_handler(message: types.Message):
    await message.reply(f"Твой chat_id: {message.chat.id}")


@dp.message(Command("run"))
async def run_handler(message: types.Message):
    await message.reply("Запускаю проверку…")
    try:
        await send_digest(message.chat.id)
        await message.reply("Готово.")
    except Exception as e:
        log.exception("Error in /run: %s", e)
        await message.reply(f"Ошибка: {e}")


@dp.message(Command("debug_rss"))
async def debug_rss_handler(message: types.Message):
    lines = ["RSS debug:\n"]
    total = 0

    for platform, rss_url in PLATFORMS.items():
        try:
            feed = await parse_feed(rss_url)
            n = len(getattr(feed, "entries", []) or [])
            total += n

            bozo = int(getattr(feed, "bozo", 0))
            http = getattr(feed, "http_status", None)
            final_url = getattr(feed, "final_url", "")

            if bozo:
                lines.append(
                    f"{platform}: {n} (http={http}, bozo=1, url={final_url}, err={getattr(feed, 'bozo_exception', None)})"
                )
            else:
                lines.append(f"{platform}: {n} (http={http}, url={final_url})")

        except Exception as e:
            lines.append(f"{platform}: ERROR {e}")

    lines.append(f"\nTotal entries: {total}")
    await message.reply("\n".join(lines))


# ----------------------------
# FASTAPI (health endpoints)
# ----------------------------
app = FastAPI()


@app.on_event("startup")
async def on_startup():
    # ВАЖНО: убираем webhook, чтобы polling работал корректно
    try:
        await bot.delete_webhook(drop_pending_updates=True)
    except Exception:
        pass

    scheduler.add_job(daily_job, "cron", hour=10, minute=0, coalesce=True, max_instances=1)
    scheduler.start()
    log.info("Scheduler started. Daily job at 10:00 MSK. CHAT_ID=%s", CHAT_ID)

    # запускаем polling как фоновую задачу
    asyncio.create_task(dp.start_polling(bot))
    log.info("Polling started.")


@app.get("/")
async def root():
    return {"status": "Tender Bot ✅ (polling)", "tz": "Europe/Moscow"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
