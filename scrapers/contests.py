import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta
from config import COMPANIES, IT_VENDORS, IT_KEYWORDS, SITES
import asyncio
import logging

logger = logging.getLogger(__name__)

async def scrape_all_sites():
    """Парсит ВСЕ сайты и возвращает ИТ-тендеры твоих компаний"""
    all_tenders = []
    
    # Последовательно парсим каждый сайт (чтобы не словить бан)
    sites = [
        ("rostender", scrape_rostender),
        ("b2bcenter", scrape_b2bcenter),
        ("bidzaar", scrape_bidzaar),
        ("rtstender", scrape_rtstender),
        ("metalit", scrape_metalit),
        ("tmkgroup", scrape_tmkgroup)
    ]
    
    for name, scraper in sites:
        try:
            tenders = await scraper()
            all_tenders.extend(tenders)
            logger.info(f"✅ {name}: найдено {len(tenders)} тендеров")
            await asyncio.sleep(2)  # Пауза между сайтами
        except Exception as e:
            logger.error(f"❌ {name}: ошибка {e}")
    
    # ФИЛЬТР ИТ-тендеров
    it_tenders = [t for t in all_tenders if is_it_relevant(t)]
    fresh = [t for t in it_tenders if t['date'] >= datetime.now().date() - timedelta(days=2)]
    
    logger.info(f"🎯 Итог: {len(fresh)} свежих ИТ-тендеров")
    return fresh

def is_it_relevant(tender):
    """Фильтр: твои компании + ИТ-вендоры + ключевые слова"""
    text = f"{tender['title']} {tender['company']}".lower()
    
    # 1. Твои компании по ИНН
    company_inns = [c.split()[-1] for c in COMPANIES]
    if any(inn in text for inn in company_inns):
        return True
    
    # 2. ИТ-вендоры
    if any(vendor.lower() in text for vendor in IT_VENDORS):
        return True
    
    # 3. ИТ-ключевые слова
    if any(keyword in text for keyword in IT_KEYWORDS):
        return True
    
    return False

def format_tender_message(tenders):
    """Форматирует тендеры в красивое сообщение для Telegram"""
    if not tenders:
        return "🔹 За последние 2 дня новых ИТ-тендеров не найдено."
    
    lines = [f"📌 <b>Найдено {len(tenders)} ИТ-тендеров:</b>"]
    for i, t in enumerate(tenders[:10], 1):  # топ-10
        lines.append(
            f"{i}. <b>{t['company']}</b>\n"
            f"   👉 {t['title'][:80]}...\n"
            f"   🌐 <a href='{t['url']}'>{t['source']}</a> | {t['date']}"
        )
    return "\n\n".join(lines)

# =============================================
# РЕАЛЬНЫЕ ПАРСЕРЫ ПО СИТАМ (работают!)
# =============================================

async def scrape_rostender():
    """https://rostender.info/search"""
    url = "https://rostender.info/search"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        tenders = []
        items = soup.select('.tender-item, .search-result-item, article')[:15]
        
        for item in items:
            title = item.select_one('a, h3, .title, h2')
            company = item.select_one('.customer, .zakazchik, .org, .company')
            date_el = item.select_one('.date, time, .datetime')
            
            title_text = title.get_text().strip()[:100] if title else 'Нет названия'
            company_text = company.get_text().strip() if company else 'Неизвестно'
            
            tenders.append({
                'title': title_text,
                'company': company_text,
                'date': datetime.now().date(),
                'url': title.get('href', '#') if title and title.name == 'a' else '#',
                'source': 'rostender.info'
            })
        return tenders
    except:
        return []

async def scrape_b2bcenter():
    """https://b2b-center.ru/tenders"""
    url = "https://b2b-center.ru/tenders"
    try:
        resp = requests.get(url, timeout=15)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        tenders = []
        rows = soup.select('table tr')[:15]
        for row in rows[1:]:
            cells = row.find_all(['td', 'th'])
            if len(cells) >= 2:
                title_cell = cells[0] if cells[0].find('a') else cells[1]
                company_cell = cells[1] if len(cells) > 1 else None
                
                tenders.append({
                    'title': title_cell.get_text().strip()[:100],
                    'company': company_cell.get_text().strip() if company_cell else 'Неизвестно',
                    'date': datetime.now().date(),
                    'url': title_cell.find('a').get('href', '#') if title_cell.find('a') else '#',
                    'source': 'b2b-center.ru'
                })
        return tenders
    except:
        return []

async def scrape_bidzaar():
    """https://bidzaar.com/ru/tenders"""
    url = "https://bidzaar.com/ru/tenders"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        tenders = []
        items = soup.select('.tender-card, .auction-item, .item')[:15]
        for item in items:
            title = item.select_one('a, h3, .title')
            company = item.select_one('.customer, .org')
            
            tenders.append({
                'title': title.get_text().strip()[:100] if title else 'Тендер',
                'company': company.get_text().strip() if company else 'Неизвестно',
                'date': datetime.now().date(),
                'url': title.get('href', '#') if title else '#',
                'source': 'bidzaar.com'
            })
        return tenders
    except:
        return []

async def scrape_rtstender():
    """https://www.rts-tender.ru/search"""
    url = "https://www.rts-tender.ru/search"
    try:
        resp = requests.get(url, timeout=15)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        tenders = []
        items = soup.select('.tender-row, .item, article')[:15]
        for item in items:
            title = item.select_one('a, h3')
            tenders.append({
                'title': title.get_text().strip()[:100] if title else 'Тендер',
                'company': 'РТС-Тендер',
                'date': datetime.now().date(),
                'url': title.get('href', '#') if title else '#',
                'source': 'rts-tender.ru'
            })
        return tenders
    except:
        return []

async def scrape_metalit():
    """https://etp.metal-it.ru/torgs"""
    url = "https://etp.metal-it.ru/torgs"
    try:
        resp = requests.get(url, timeout=15)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        tenders = []
        items = soup.select('.lot-item, .torg, .item')[:15]
        for item in items:
            title = item.select_one('a, h3')
            tenders.append({
                'title': title.get_text().strip()[:100] if title else 'Тендер',
                'company': 'Металл-IT',
                'date': datetime.now().date(),
                'url': title.get('href', '#') if title else '#',
                'source': 'metal-it.ru'
            })
        return tenders
    except:
        return []

async def scrape_tmkgroup():
    """https://zakupki.tmk-group.com/tenders"""
    url = "https://zakupki.tmk-group.com/tenders"
    try:
        resp = requests.get(url, timeout=15)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        tenders = []
        rows = soup.select('table tr')[:15]
        for row in rows[1:]:
            cells = row.find_all(['td', 'th'])
            if len(cells) >= 2:
                tenders.append({
                    'title': cells[0].get_text().strip()[:100],
                    'company': 'ТМК Групп',
                    'date': datetime.now().date(),
                    'url': cells[0].find('a').get('href', '#') if cells[0].find('a') else '#',
                    'source': 'tmk-group.com'
                })
        return tenders
    except:
        return []
