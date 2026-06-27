"""ЕФРСБ backend API - финальный тест"""
import requests, json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
     "Accept": "application/json, text/plain, */*",
     "Accept-Language": "ru-RU,ru;q=0.9",
     "Referer": "https://bankrot.fedresurs.ru/",
     "Origin": "https://bankrot.fedresurs.ru"}

BASE = "https://bankrot.fedresurs.ru/backend"

# Все возможные endpoints
tests = [
    ("GET", f"{BASE}/bankrupts?limit=5"),
    ("GET", f"{BASE}/tradeplaces?limit=5"),
    ("GET", f"{BASE}/tradeorgs?limit=5"),
    ("GET", f"{BASE}/tpsros?limit=5"),
    ("GET", f"{BASE}/moratorium?limit=5"),
    ("GET", f"{BASE}/trades?limit=5"),
    ("GET", f"{BASE}/lots?limit=5"),
    ("GET", f"{BASE}/settings/help"),
    ("GET", f"{BASE}/settings/yandexMetrics"),
    # Пробуем разные паттерны
    ("GET", f"{BASE}/search/trades?limit=5"),
    ("GET", f"{BASE}/trade/trades?limit=5"),
    ("GET", f"{BASE}/trade/list?limit=5"),
    ("GET", f"{BASE}/trade/lots?limit=5"),
    ("GET", f"{BASE}/lot/list?limit=5"),
    ("GET", f"{BASE}/lot/cards?limit=5"),
    # POST variants
    ("POST", f"{BASE}/bankrupts"),
    ("POST", f"{BASE}/trade/search"),
    ("POST", f"{BASE}/lot/search"),
]

for method, url in tests:
    try:
        if method == "POST":
            r = requests.post(url, json={"limit": 5, "offset": 0}, headers=H, timeout=8)
        else:
            r = requests.get(url, headers=H, timeout=8)
        ct = r.headers.get("content-type", "?")
        is_json = "json" in ct
        print(f"{method} {url.replace(BASE, '')}")
        print(f"  {r.status_code} ct={ct[:40]} len={len(r.text)}")
        if is_json and len(r.text) > 10:
            data = r.json()
            if isinstance(data, list):
                print(f"  LIST: {len(data)} items")
                if data:
                    print(f"  FIRST: {json.dumps(data[0], ensure_ascii=False)[:200]}")
            elif isinstance(data, dict):
                keys = list(data.keys())[:10]
                print(f"  DICT keys: {keys}")
                if "content" in data:
                    print(f"  content: {len(data['content'])} items, total={data.get('totalElements')}")
                elif "items" in data:
                    print(f"  items: {len(data['items'])} items")
                else:
                    print(f"  DATA: {json.dumps(data, ensure_ascii=False)[:300]}")
    except Exception as e:
        print(f"{method} {url.replace(BASE, '')}: ERROR {e}")
    print()
