"""Быстрый тест всех площадок"""
import requests
from bs4 import BeautifulSoup
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

print("=== 1. ЕФРСБ (без прокси) ===")
try:
    r = requests.get("https://bankrot.fedresurs.ru/TradeList.aspx", timeout=10, headers=H)
    print(f"Status: {r.status_code}, len={len(r.text)}")
    soup = BeautifulSoup(r.text, "lxml")
    print(f"Title: {soup.title.text if soup.title else 'none'}")
    tables = soup.select("table")
    print(f"Tables: {len(tables)}")
    links = soup.select("a")
    print(f"Links: {len(links)}")
    for a in links[:5]:
        print(f"  {a.get_text(strip=True)[:50]} -> {a.get('href','')[:60]}")
    # Ищем Angular app
    scripts = soup.select("script[src]")
    print(f"Scripts: {len(scripts)}")
    for s in scripts:
        print(f"  {s.get('src','')}")
except Exception as e:
    print(f"ERROR: {e}")

print()
print("=== 2. ЕФРСБ API (без прокси) ===")
from datetime import datetime, timedelta
now = datetime.now()
payload = {"offset": 0, "limit": 5, "searchString": "",
           "dateFrom": (now - timedelta(days=30)).strftime("%Y-%m-%d"),
           "dateTo": now.strftime("%Y-%m-%d"),
           "priceFrom": 0, "priceTo": 10000000}
for ep in ["/api/Trade/GetTradesForSearch", "/api/Trade/GetTrades"]:
    try:
        r = requests.post(f"https://bankrot.fedresurs.ru{ep}", json=payload, headers=H, timeout=10)
        print(f"POST {ep}: {r.status_code}, len={len(r.text)}")
        if r.status_code == 200:
            print(f"  Content[:300]: {r.text[:300]}")
    except Exception as e:
        print(f"POST {ep}: ERROR {e}")

print()
print("=== 3. lot-online.ru (без прокси) ===")
for url in ["https://api.lot-online.ru/v2/lots?limit=5",
            "https://www.lot-online.ru/api/v2/lots?limit=5",
            "https://lot-online.ru/auction/lots"]:
    try:
        r = requests.get(url, headers=H, timeout=10)
        print(f"GET {url[:50]}: {r.status_code}, len={len(r.text)}")
        if r.status_code == 200 and len(r.text) > 50:
            print(f"  Content[:200]: {r.text[:200]}")
    except Exception as e:
        print(f"GET {url[:50]}: ERROR {e}")

print()
print("=== 4. Торги23, AllTorgs ===")
for url in ["https://torgi23.ru/", "https://alltorgs.ru/", "https://torgiassist.ru/"]:
    try:
        r = requests.get(url, headers=H, timeout=10, allow_redirects=True)
        print(f"{url}: {r.status_code}, len={len(r.text)}, final={r.url[:60]}")
    except Exception as e:
        print(f"{url}: ERROR {e}")
