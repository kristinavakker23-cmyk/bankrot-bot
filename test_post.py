"""ЕФРСБ POST + torgi.gov.ru POST"""
import requests, json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
     "Accept": "application/json",
     "Content-Type": "application/json",
     "Referer": "https://bankrot.fedresurs.ru/",
     "Origin": "https://bankrot.fedresurs.ru"}

BASE = "https://bankrot.fedresurs.ru/backend"

# ЕФРСБ - POST с разными payloads
print("=== ЕФРСБ POST ===")
endpoints = ["tradeplaces", "tpsros", "amsros", "arbitrmanagers", "disqualificants"]
payloads = [
    {"limit": 5, "offset": 0},
    {"limit": 5, "offset": 0, "searchString": ""},
    {"limit": 5, "offset": 0, "searchString": "торг"},
    {},
]

for ep in endpoints:
    for payload in payloads:
        url = f"{BASE}/{ep}"
        try:
            r = requests.post(url, json=payload, headers=H, timeout=8)
            ct = r.headers.get("content-type", "?")[:30]
            print(f"  POST /{ep} {json.dumps(payload, ensure_ascii=False)[:40]}")
            print(f"    {r.status_code} ct={ct} len={len(r.text)}")
            if r.status_code == 200 and "json" in ct:
                data = r.json()
                if isinstance(data, dict):
                    print(f"    keys: {list(data.keys())[:8]}")
                    if "content" in data:
                        print(f"    content: {len(data['content'])} items, total={data.get('totalElements')}")
                elif isinstance(data, list):
                    print(f"    list: {len(data)} items")
                    if data:
                        print(f"    first: {json.dumps(data[0], ensure_ascii=False)[:200]}")
                break  # Если заработало, не пробуем другие payload
        except Exception as e:
            print(f"    ERROR: {e}")
    print()

# torgi.gov.ru - POST поиск
print("=== torgi.gov.ru POST ===")
for payload in [
    {"limit": 5, "searchString": "автомобиль"},
    {"limit": 5, "lotName": "автомобиль"},
    {"limit": 5, "query": "автомобиль"},
    {"limit": 5, "filter": {"lotName": "автомобиль"}},
]:
    try:
        r = requests.post("https://torgi.gov.ru/new/api/public/lotcards/search",
                         json=payload, headers=H, timeout=10)
        data = r.json() if r.status_code == 200 else {}
        total = data.get("totalElements", "?")
        items = len(data.get("content", []))
        print(f"  POST payload={json.dumps(payload, ensure_ascii=False)[:50]}")
        print(f"    {r.status_code} total={total} items={items}")
        if items > 0:
            print(f"    first: {data['content'][0].get('lotName', '?')[:60]}")
    except Exception as e:
        print(f"  POST: ERROR {e}")

# torgi.gov.ru - GET с правильными фильтрами
print()
print("=== torgi.gov.ru - lotStatus=ACTIVE ===")
for status in ["ACTIVE", "PUBLISHED", "IN_PROGRESS", "REVIEW"]:
    r = requests.get(f"https://torgi.gov.ru/new/api/public/lotcards/search?limit=5&lotStatus={status}",
                     headers={"Accept": "application/json"}, timeout=10)
    data = r.json()
    total = data.get("totalElements", "?")
    items = len(data.get("content", []))
    print(f"  lotStatus={status}: total={total} items={items}")
    if items > 0:
        lot = data["content"][0]
        print(f"    {lot.get('lotName', '?')[:50]} | {lot.get('lotStatus')} | {lot.get('priceMin')}")
