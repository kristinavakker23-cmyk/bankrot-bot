"""Ищем банкротские лоты - правильный biddType на torgi.gov.ru + ЕФРСБ API"""
import requests, json, re, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
     "Accept": "application/json"}

# ═══════════════════════════════════════════════════════
# torgi.gov.ru - ищем ВСЕ biddType
# ═══════════════════════════════════════════════════════
print("=" * 60)
print("torgi.gov.ru - все biddType")
print("=" * 60)

bidd_types = {}
for offset in range(0, 500, 20):
    r = requests.get(f"https://torgi.gov.ru/new/api/public/lotcards/search?limit=20&offset={offset}",
                     headers=H, timeout=15)
    data = r.json()
    for lot in data.get("content", []):
        bt = lot.get("biddType", {})
        code = bt.get("code", "?")
        name = bt.get("name", "?")
        if code not in bidd_types:
            bidd_types[code] = name
    if len(bidd_types) >= 30:
        break

print(f"Found {len(bidd_types)} unique biddTypes:")
for code, name in sorted(bidd_types.items()):
    marker = " <-- БАНКРОТ" if "банкрот" in name.lower() else ""
    print(f"  {code}: {name[:80]}{marker}")

# ═══════════════════════════════════════════════════════
# ЕФРСБ - анализ JS на реальные API вызовы
# ═══════════════════════════════════════════════════════
print()
print("=" * 60)
print("ЕФРСБ - HTTP calls в JS")
print("=" * 60)

try:
    r = requests.get("https://bankrot.fedresurs.ru/main.9862903b072b93a30fa7.js",
                     headers=H, timeout=15)
    js = r.text
    
    # Ищем http.get/post/put/delete вызовы
    http_calls = re.findall(r'\.http\.(get|post|put|delete)\s*\(\s*["\']([^"\']+)["\']', js)
    print(f"HTTP calls found: {len(http_calls)}")
    for method, url in http_calls:
        print(f"  .{method.upper()} {url[:80]}")
    
    # Ищем backUri и базовый URL
    back_uri = re.findall(r'backUri[=:]\s*["\']([^"\']+)["\']', js)
    print(f"\nbackUri: {back_uri[:5]}")
    
    # Ищем apiUrl, baseUrl
    base_urls = re.findall(r'(?:apiUrl|ApiUrl|baseUrl|BaseUrl|BASE_URL|API_URL)\s*[=:]\s*["\']([^"\']+)["\']', js)
    print(f"api/base URLs: {base_urls[:10]}")
    
    # Ищем sroTradePlaces и tradePlaces URL
    trade_places = re.findall(r'(?:tradePlaces|sroTradePlaces)[^{]*\{[^}]*url:\s*["\']([^"\']+)["\']', js)
    print(f"tradePlaces URLs: {trade_places[:10]}")
    
    # Ищем any URL с /b/ или /api/
    api_paths = re.findall(r'["\'](/(?:b|api)[^"\']{5,80})["\']', js)
    unique_paths = list(set(api_paths))
    print(f"\nAPI-like paths: {len(unique_paths)}")
    for p in sorted(unique_paths)[:30]:
        print(f"  {p}")

except Exception as e:
    print(f"ERROR: {e}")

# ═══════════════════════════════════════════════════════
# Пробуем ЕФРСБ API через /b/ path (частый Angular prefix)
# ═══════════════════════════════════════════════════════
print()
print("=" * 60)
print("ЕФРСБ - пробуем реальные API endpoints")
print("=" * 60)

efrsb_tests = [
    ("GET", "https://bankrot.fedresurs.ru/b/trades?limit=5"),
    ("GET", "https://bankrot.fedresurs.ru/b/api/trades?limit=5"),
    ("GET", "https://bankrot.fedresurs.ru/b/Trade/GetTrades"),
    ("GET", "https://bankrot.fedresurs.ru/b/tradeList"),
    ("GET", "https://bankrot.fedresurs.ru/b/lotList"),
    ("POST", "https://bankrot.fedresurs.ru/b/trades"),
    ("GET", "https://bankrot.fedresurs.ru/b/api/v1/trades?limit=5"),
    ("GET", "https://bankrot.fedresurs.ru/trades?limit=5"),
    ("GET", "https://bankrot.fedresurs.ru/lotList?limit=5"),
    ("GET", "https://bankrot.fedresurs.ru/lots?limit=5"),
]

for method, url in efrsb_tests:
    try:
        if method == "POST":
            r = requests.post(url, json={"limit": 5}, headers=H, timeout=8)
        else:
            r = requests.get(url, headers=H, timeout=8)
        is_json = "json" in r.headers.get("content-type", "")
        print(f"  {method} {url}")
        print(f"    {r.status_code} len={len(r.text)} json={is_json}")
        if is_json and len(r.text) > 10:
            print(f"    {r.text[:200]}")
    except Exception as e:
        print(f"  {method} {url}: ERROR {e}")
