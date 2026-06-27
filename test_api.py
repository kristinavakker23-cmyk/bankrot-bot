"""Поиск рабочих API для банкротских торгов"""
import requests, json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
     "Accept": "application/json"}

print("=== 1. torgi.gov.ru API ===")
# torgi.gov.ru имеет открытый API для торгов
urls = [
    "https://torgi.gov.ru/new/api/public/lotcards/search?biddType=3&status=3&sort=0&limit=5&offset=0",
    "https://torgi.gov.ru/new/api/public/lotcards/search?biddType=3&status=3&limit=5",
    "https://torgi.gov.ru/api/public/lotcards/search?biddType=3&limit=5",
    "https://torgi.gov.ru/new/api/public/lotcards?biddType=3&limit=5",
    "https://torgi.gov.ru/new/api/public/bidd/search?biddType=3&status=3&limit=5",
]
for url in urls:
    try:
        r = requests.get(url, headers=H, timeout=10)
        print(f"  {url[:70]}...")
        print(f"    {r.status_code} len={len(r.text)}")
        if r.status_code == 200 and len(r.text) > 10:
            print(f"    {r.text[:300]}")
    except Exception as e:
        print(f"    ERROR: {e}")

print()
print("=== 2. torgi.gov.ru POST ===")
for url in [
    "https://torgi.gov.ru/new/api/public/lotcards/search",
    "https://torgi.gov.ru/new/api/public/bidd/search",
]:
    try:
        payload = {"biddType": 3, "status": 3, "limit": 5, "offset": 0}
        r = requests.post(url, json=payload, headers=H, timeout=10)
        print(f"  POST {url[:60]}...")
        print(f"    {r.status_code} len={len(r.text)}")
        if r.status_code == 200 and len(r.text) > 10:
            print(f"    {r.text[:300]}")
    except Exception as e:
        print(f"    ERROR: {e}")

print()
print("=== 3. bankrot.fedresurs.ru - пробуем JS API ===")
# ЕФРСБ - Angular SPA, данные внутри JS бандла
# Смотрим какие API вызовы делает фронтенд
try:
    r = requests.get("https://bankrot.fedresurs.ru/main.9862903b072b93a30fa7.js", 
                     headers=H, timeout=10)
    print(f"  main.js: {r.status_code}, len={len(r.text)}")
    if r.status_code == 200:
        # Ищем API эндпоинты в JS
        import re
        apis = re.findall(r'["\']([^"\']*(?:api|trade|lot|search)[^"\']*)["\']', r.text, re.IGNORECASE)
        unique = list(set(apis))[:20]
        print(f"  API endpoints found: {len(unique)}")
        for a in unique:
            print(f"    {a[:80]}")
except Exception as e:
    print(f"  ERROR: {e}")

print()
print("=== 4. bankrot.fedresurs.ru - фоллбэк API ===")
# Пробуем разные варианты API на основе анализа Angular SPA
endpoints = [
    ("GET", "https://bankrot.fedresurs.ru/assets/api/trades?limit=5"),
    ("GET", "https://bankrot.fedresurs.ru/api/v1/trades?limit=5"),
    ("GET", "https://bankrot.fedresurs.ru/api/trades?limit=5"),
    ("POST", "https://bankrot.fedresurs.ru/api/trades/search"),
    ("GET", "https://efrsb.ru/api/v1/trades?limit=5"),
    ("GET", "https://efrsb.ru/trades?limit=5"),
]
for method, url in endpoints:
    try:
        if method == "POST":
            r = requests.post(url, json={"limit": 5}, headers=H, timeout=8)
        else:
            r = requests.get(url, headers=H, timeout=8)
        print(f"  {method} {url}")
        print(f"    {r.status_code} len={len(r.text)}")
        if r.status_code == 200 and len(r.text) > 10:
            print(f"    {r.text[:300]}")
    except Exception as e:
        print(f"    ERROR: {e}")

print()
print("=== 5. Альтернативные площадки ===")
alt_urls = [
    "https://bankrotstvo.ru/api/lots?limit=5",
    "https://bankrotstvo.ru/torgi",
    "https://sudact.ru/regular/court/bankruptcy/",
    "https://kad.arbitr.ru/",
    "https://zachestnyibiznes.ru/bankrotstvo",
]
for url in alt_urls:
    try:
        r = requests.get(url, headers=H, timeout=8, allow_redirects=True)
        print(f"  {url}")
        print(f"    {r.status_code} len={len(r.text)} final={r.url[:60]}")
        if r.status_code == 200 and len(r.text) > 100:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(r.text, "lxml")
            title = soup.title.text.strip() if soup.title else "?"
            print(f"    Title: {title}")
    except Exception as e:
        print(f"    ERROR: {e}")
