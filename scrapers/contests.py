import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta
from config import COMPANIES, IT_VENDORS, IT_KEYWORDS
import asyncio

async def scrape_all_sites():
    """Собирает ТОЛЬКО ИТ-тендеры"""
    all_tenders = []
    
    tasks = [
        scrape_rostender(),
        scrape_b2bcenter(),
        scrape_bidzaar(), 
        scrape_rstender(),
        scrape_metalit(),
        scrape_tmkgroup()
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for result in results:
        if isinstance(result, list):
            all_tenders.extend(result)
    
    it_tenders = [t for t in all_tenders if is_it_relevant(t)]
    fresh = [t for t in it_tenders if t['date'] >= datetime.now().date() - timedelta(days=2)]
    
    return fresh

def is_it_relevant(tender):
    """ИТ ФИЛЬТР: компании + вендоры + ключевые слова"""
    text = f"{tender['title']} {tender['company']}".lower()
    
    # 1. Твои компании
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

async def scrape_rostender():
    url = "https://rostender.info/search"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(resp.text, 'html.parser')
        return parse_generic_tenders(soup, '.tender-item, .search-result-item', 'rostender.info')
    except:
        return []

async def scrape_b2bcenter():
    url = "https://b2b-center.ru/tenders"
    try:
        resp = requests.get(url, timeout=15)
        soup = BeautifulSoup(resp.text, 'html.parser')
        return parse_table_tenders(soup, 'b2b-center.ru')
    except:
        return []

async def scrape_bidzaar():
    url = "https://bidzaar.com/ru/tenders"
    try:
        resp = requests.get(url, timeout=15)
        soup = BeautifulSoup(resp.text, 'html.parser')
        return parse_generic_tenders(soup, '.tender-card, .auction-item', 'bidzaar.com')
    except:
        return []

async def scrape_rstender():
    url = "https://www.rts-tender.ru/search"
    try:
        resp = requests.get(url, timeout=15)
        soup = BeautifulSoup(resp.text, 'html.parser')
        return parse_generic_tenders(soup, '.tender-row', 'rts-tender.ru')
    except:
        return []

async def scrape_metalit():
    url = "https://etp.metal-it.ru/torgs"
    try:
        resp = requests.get(url, timeout=15)
        soup = BeautifulSoup(resp.text, 'html.parser')
        return parse_generic_tenders(soup, '.lot-item', 'metal-it.ru')
    except:
        return []

async def scrape_tmkgroup():
    url = "https://zakupki.tmk-group.com/tenders"
    try:
        resp = requests.get(url, timeout=15)
        soup = BeautifulSoup(resp.text, 'html.parser')
        return parse_table_tenders(soup, 'tmk-group.com')
    except:
        return []

def parse_generic_tenders(soup, selector, source):
    tenders = []
    items = soup.select(selector)[:15]
    for item in items:
        title = item.select_one('a, h3, .title') or item
        company = item.select_one('.customer, .zakazchik, .org') 
        date_el = item.select_one('.date, time')
        
        tenders.append({
            'title': title.get_text().strip()[:100] if title else 'Нет названия',
            'company': company.get_text().strip() if company else 'Неизвестно',
            'date': datetime.now().date(),
            'url': title.get('href', '#') if title and title.name == 'a' else '#',
            'source': source
        })
    return tenders

def parse_table_tenders(soup, source):
    tenders = []
    rows = soup.select('table tr')[:15]
    for row in rows[1:]:  # пропускаем заголовок
        cells = row.find_all(['td', 'th'])
        if len(cells) >= 2:
            title_cell = cells[0] if cells[0].find('a') else cells[1]
            tenders.append({
                'title': title_cell.get_text().strip()[:100],
                'company': cells[0].get_text().strip() if len(cells) > 1 else 'Неизвестно',
                'date': datetime.now().date(),
                'url': title_cell.find('a').get('href', '#') if title_cell.find('a') else '#',
                'source': source
            })
    return tenders
