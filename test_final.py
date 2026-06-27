"""Финальный тест: ЕФРСБ все endpoints + torgi.gov.ru без фильтра"""
import requests, json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
     "Accept": "application/json, text/plain, */*",
     "Referer": "https://bankrot.fedresurs.ru/"}

BASE = "https://bankrot.fedresurs.ru/backend"

# ЕФРСБ все endpoints
print("=== ЕФРСБ backend endpoints ===")
endpoints = [
    "bankrupts", "tradeplaces", "tradeorgs", "tpsros", "amsros",
    "arbitrmanagers", "disqualificants", "moratorium",
    "extrajudicialbankruptcy", "EAEU", "error",
    # Попробуем с query params
    "bankrupts?limit=5&offset=0",
    "tradeplaces?limit=5&offset=0",
    "arbitrmanagers?limit=5&offset=0",
    # Комбинированные
    "bankrupts/search",
    "tradeplaces/search",
]

for ep in endpoints:
    url = f"{BASE}/{ep}"
    try:
        r = requests.get(url, headers=H, timeout=8)
        ct = r.headers.get("content-type", "?")[:30]
        print(f"  GET /{ep}: {r.status_code} ct={ct} len={len(r.text)}")
        if r.status_code == 200 and "json" in ct:
            data = r.json()
            if isinstance(data, dict):
                print(f"    keys: {list(data.keys())[:8]}")
            elif isinstance(data, list):
                print(f"    list: {len(data)} items")
    except Exception as e:
        print(f"  GET /{ep}: ERROR {e}")

# torgi.gov.ru - сортируем по дате создания (новые первыми)
print()
print("=== torgi.gov.ru - новые лоты ===")
r = requests.get("https://torgi.gov.ru/new/api/public/lotcards/search?limit=10&sort=createDate&sortDirection=desc",
                 headers=H, timeout=15)
data = r.json()
lots = data.get("content", [])
print(f"Total: {data.get('totalElements')}, Got: {len(lots)}")
for lot in lots[:5]:
    name = lot.get("lotName", "?")[:60]
    price = lot.get("priceMin", "?")
    bt = lot.get("biddType", {}).get("name", "?")[:40]
    cat = lot.get("category", {}).get("name", "?")
    status = lot.get("lotStatus", "?")
    print(f"  {name} | {price} руб. | {status} | {cat}")

# torgi.gov.ru - ищем лоты с электроникой/техникой в названии
print()
print("=== torgi.gov.ru - поиск по ключевым словам ===")
keywords = ["ноутбук", "компьютер", "сервер", "автомобиль", "станок", "оборудование", "холодильник"]
for kw in keywords:
    r = requests.get(f"https://torgi.gov.ru/new/api/public/lotcards/search?limit=5&searchString={kw}",
                     headers=H, timeout=10)
    data = r.json()
    total = data.get("totalElements", 0)
    lots = data.get("content", [])
    print(f"  '{kw}': total={total}, got={len(lots)}")
    for lot in lots[:2]:
        name = lot.get("lotName", "?")[:50]
        price = lot.get("priceMin", "?")
        print(f"    {name} | {price} руб.")
