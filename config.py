import os

# Render автоматически загружает Environment Variables
# load_dotenv() НЕ НУЖЕН в Render!

GIGACHAT_CLIENT_ID = os.getenv("GIGACHAT_CLIENT_ID")
BOT_TOKEN = os.getenv("BOT_TOKEN")
GIGACHAT_AUTH_KEY = os.getenv("GIGACHAT_AUTH_KEY")
YOUR_USER_ID = int(os.getenv("YOUR_USER_ID") or 0)  # Защита от None

# Остальное без изменений
COMPANIES = [
    "АО АКРОН ХОЛДИНГ ИНН6324023665",
    "ПАО Совкомбанк  ИНН4401116480", 
    "АО СЛПК ИНН1121003135",
]

IT_VENDORS = [
    "Cisco", "HPE", "Dell", "Lenovo", "IBM", "Oracle", 
    "Microsoft", "VMware", "Huawei", "Fortinet", "Brocade",
    "Kaspersky", "DrWeb", "1C", "Bitrix24", "BPMSoft"
]

IT_KEYWORDS = [
    "техническая поддержка", "сервисная поддержка", 
    "поставка оборудования", "сервер", "сетевое оборудование",
    "ИТ услуги", "информационная безопасность", "СЗИ",
    "лицензии", "ПО", "software", "облако", "облачные услуги"
]

SITES = [
    "https://rostender.info/search",
    "https://b2b-center.ru/tenders", 
    "https://bidzaar.com/ru/tenders",
    "https://www.rts-tender.ru/search",
    "https://etp.metal-it.ru/torgs",
    "https://zakupki.tmk-group.com/tenders"
]
