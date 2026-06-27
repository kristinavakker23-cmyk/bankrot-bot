"""Глубокий поиск API - torgi.gov.ru + ЕФРСБ JS"""
import requests, json, re, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
     "Accept": "application/json, text/plain, */*",
     "Accept-Language": "ru-RU,ru;q=0.9"}

# ═══════════════════════════════════════════════════════
# torgi.gov.ru - ищем правильные параметры
# ═══════════════════════════════════════════════════════
print("=" * 60)
print("torgi.gov.ru API - подбираем параметры")
print("=" * 60)

# Стандартный ответ уже был: content:[], totalElements:0
# Значит biddType=3 (банкротство) + status=3 (активные) — пусто
# Пробуем другие комбинации
tests = [
    # Без фильтров
    "?limit=5",
    "?limit=5&offset=0",
    # Разные biddType
    "?biddType=1&status=3&limit=5",
    "?biddType=2&status=3&limit=5",
    "?biddType=4&status=3&limit=5",
    "?biddType=5&status=3&limit=5",
    # Без status
    "?biddType=3&limit=5",
    # С catCode (категория "Прочее")
    "?biddType=3&status=3&catCode=95&limit=5",
    "?biddType=3&status=3&catCode=96&limit=5",
    # Разные сортировки
    "?biddType=3&status=3&sort=1&limit=5",
    "?biddType=3&status=3&sort=2&limit=5",
    # Поиск по тексту
    "?biddType=3&status=3&searchString=ноутбук&limit=5",
    "?biddType=3&status=3&searchString=автомобиль&limit=5",
    # Все торги без фильтра по типу
    "?status=3&limit=5",
    "?limit=5&sort=0",
]

base = "https://torgi.gov.ru/new/api/public/lotcards/search"
for params in tests:
    url = f"{base}{params}"
    try:
        r = requests.get(url, headers=H, timeout=8)
        data = r.json() if r.status_code == 200 else {}
        total = data.get("totalElements", "?")
        content_len = len(data.get("content", []))
        print(f"  {params[:65]}")
        print(f"    {r.status_code} total={total} items={content_len}")
        if content_len > 0:
            first = data["content"][0]
            print(f"    FIRST: {json.dumps(first, ensure_ascii=False)[:200]}")
    except Exception as e:
        print(f"  {params[:65]}: ERROR {e}")

# ═══════════════════════════════════════════════════════
# ЕФРСБ - анализ JS бандла
# ═══════════════════════════════════════════════════════
print()
print("=" * 60)
print("ЕФРСБ - анализ API из JavaScript")
print("=" * 60)

try:
    r = requests.get("https://bankrot.fedresurs.ru/main.9862903b072b93a30fa7.js",
                     headers=H, timeout=15)
    js = r.text
    
    # Ищем URL API
    url_patterns = re.findall(r'["\']((?:https?://)?[^"\']*(?:api|trade|lot|search|bidd)[^"\']*)["\']', js, re.IGNORECASE)
    unique_urls = list(set([u for u in url_patterns if len(u) > 10 and len(u) < 200]))
    print(f"  URLs found: {len(unique_urls)}")
    for u in sorted(unique_urls)[:30]:
        print(f"    {u[:100]}")
    
    # Ищем ApiUrl и базовый URL
    api_refs = re.findall(r'(?:ApiUrl|apiUrl|api_url|baseUrl|BASE_URL)\s*[=:]\s*["\']([^"\']+)["\']', js)
    print(f"\n  ApiUrl refs: {api_refs[:10]}")
    
    # Ищем trade-related
    trade_refs = re.findall(r'["\']([^"\']*trade[^"\']*)["\']', js, re.IGNORECASE)
    unique_trade = list(set([t for t in trade_refs if "/" in t and len(t) < 100]))
    print(f"\n  Trade paths: {len(unique_trade)}")
    for t in sorted(unique_trade)[:20]:
        print(f"    {t}")
        
except Exception as e:
    print(f"  ERROR: {e}")
