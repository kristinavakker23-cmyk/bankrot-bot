"""Тест парсинга банкротских площадок"""
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"}
proxy = {"http": "http://127.0.0.1:10809", "https": "http://127.0.0.1:10809"}

# ─── 1. ЕФРСБ ───
print("=" * 50)
print("1. ЕФРСБ (bankrot.fedresurs.ru)")
print("=" * 50)

try:
    r = requests.get("https://bankrot.fedresurs.ru/", headers=HEADERS, proxies=proxy, timeout=10)
    print(f"  Main page: {r.status_code}, len={len(r.text)}")
except Exception as e:
    print(f"  Main page ERROR: {e}")

# Пробуем разные API endpoints
now = datetime.now()
payload = {
    "offset": 0, "limit": 10, "searchString": "",
    "dateFrom": (now - timedelta(days=7)).strftime("%Y-%m-%d"),
    "dateTo": now.strftime("%Y-%m-%d"),
    "priceFrom": 0, "priceTo": 10000000
}

api_endpoints = [
    ("POST", "https://bankrot.fedresurs.ru/api/Trade/GetTradesForSearch"),
    ("POST", "https://bankrot.fedresurs.ru/api/Trade/GetTrades"),
    ("POST", "https://bankrot.fedresurs.ru/api/trades"),
    ("GET", "https://bankrot.fedresurs.ru/TradeList.aspx"),
    ("GET", "https://old.bankrot.fedresurs.ru/TradeList.aspx"),
]

for method, url in api_endpoints:
    try:
        if method == "POST":
            r = requests.post(url, json=payload, headers=HEADERS, proxies=proxy, timeout=10)
        else:
            r = requests.get(url, headers=HEADERS, proxies=proxy, timeout=10)
        print(f"  {method} {url}")
        print(f"    Status: {r.status_code}, len={len(r.text)}")
        if r.status_code == 200 and len(r.text) > 50:
            print(f"    Content[:200]: {r.text[:200]}")
    except Exception as e:
        print(f"  {method} {url}: ERROR {e}")

# ─── 2. lot-online.ru ───
print()
print("=" * 50)
print("2. lot-online.ru")
print("=" * 50)

lot_urls = [
    ("GET", "https://api.lot-online.ru/v2/lots?limit=10&sort=new&status=active"),
    ("GET", "https://www.lot-online.ru/api/v2/lots?limit=10"),
    ("GET", "https://lot-online.ru/api/lots?limit=10"),
    ("GET", "https://www.lot-online.ru/auction/lots?status=active"),
]

for method, url in lot_urls:
    try:
        r = requests.get(url, headers=HEADERS, proxies=proxy, timeout=10)
        print(f"  {url}")
        print(f"    Status: {r.status_code}, len={len(r.text)}")
        if r.status_code == 200 and len(r.text) > 50:
            print(f"    Content[:200]: {r.text[:200]}")
    except Exception as e:
        print(f"  {url}: ERROR {e}")

# ─── 3. Другие площадки ───
print()
print("=" * 50)
print("3. Другие площадки")
print("=" * 50)

other_urls = [
    "https://torgiassist.ru/",
    "https://bankrot-spy.ru/",
    "https://alltorgs.ru/",
    "https://prolot.ru/",
    "https://torgi-av.ru/",
    "https://torgi-mo.ru/",
]

for url in other_urls:
    try:
        r = requests.get(url, headers=HEADERS, proxies=proxy, timeout=10, allow_redirects=True)
        print(f"  {url}")
        print(f"    Status: {r.status_code}, len={len(r.text)}, final: {r.url}")
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "lxml")
            title = soup.title.get_text(strip=True) if soup.title else "?"
            print(f"    Title: {title}")
    except Exception as e:
        print(f"  {url}: ERROR {e}")
