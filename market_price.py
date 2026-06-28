"""
Модуль анализа рыночных цен v4.
Работает через requests (без Playwright — для Render.com free tier).

Источники:
- drom.ru — для авто (парсинг HTML)
- Bing search — сниппеты с ценами
- Фоллбэк — эвристическая оценка по категории
"""
import re, time, random, logging, json, requests
from bs4 import BeautifulSoup
from urllib.parse import quote

log = logging.getLogger("bankrot.market")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.5",
}

# ─── Категории для эвристической оценки ──────────────
# Если не удаётся найти цену — даём оценку по категории

CATEGORY_MARKET_RANGES = {
    # (тип_лота, ключевые_слова): (min_рыночная, max_рыночная, типичная_маржа%)
    "auto": {
        "keywords": ["автомобил", "легков", "седан", "хэтчбек", "внедорожн", "кроссовер",
                      "toyota", "bmw", "mercedes", "audi", "volkswagen", "hyundai", "kia",
                      "nissan", "honda", "ford", "chevrolet", "land cruiser", "camry", "corolla"],
        "range": (200_000, 15_000_000),
        "typical_margin": 35,
    },
    "truck": {
        "keywords": ["грузовик", "грузов", "груз", "камаз", "газон", "газель", "фургон", "борт"],
        "range": (300_000, 10_000_000),
        "typical_margin": 40,
    },
    "equipment": {
        "keywords": ["экскаватор", "погрузчик", "кран", "трактор", "бульдозер", "компрессор",
                      "генератор", "сварочн", "станок", "фрезерн", "токарн"],
        "range": (100_000, 20_000_000),
        "typical_margin": 60,
    },
    "electronics": {
        "keywords": ["ноутбук", "компьютер", "сервер", "монитор", "принтер", "роутер",
                      "iphone", "samsung", "xiaomi", "sony", "macbook", "ipad", "плазм"],
        "range": (50_000, 1_000_000),
        "typical_margin": 55,
    },
    "furniture": {
        "keywords": ["мебел", "стол", "стул", "шкаф", "диван", "кресло", "кроват", "комод"],
        "range": (5_000, 300_000),
        "typical_margin": 50,
    },
    "realty": {
        "keywords": ["квартир", "комнат", "дом", "коттедж", "помещени", "здани", "гараж",
                      "паркинг", "нежил"],
        "range": (1_000_000, 100_000_000),
        "typical_margin": 30,
    },
    "metal": {
        "keywords": ["металлолом", "металл", "медь", "алюминий", "сталь"],
        "range": (10_000, 500_000),
        "typical_margin": 30,
    },
    "coins": {
        "keywords": ["монет", "банкнот", "купюр", "коллекцион"],
        "range": (5_000, 2_000_000),
        "typical_margin": 40,
    },
}


# ─── Очистка запроса ───────────────────────────────────

def clean_search_query(title):
    """Извлекает ключевые слова из названия лота."""
    title = title.lower()
    stopwords = [
        'лот', 'дело', 'банкрот', 'реализация', 'имущество', 'имущества',
        'торги', 'внешнее', 'управлен', 'конкурсн', 'должник', 'должника',
        'организации', 'процедура', 'банк', 'банкротств', 'взыскание',
        'реализ', 'auction', 'lot', 'bankrupt',
    ]
    for sw in stopwords:
        title = re.sub(r'\b' + sw + r'\w*\b', '', title)
    title = re.sub(r'лот\s*№?\s*\d+', '', title)
    title = re.sub(r'дело\s*№?\s*[\d\-/]+', '', title)
    title = re.sub(r'\d{2}\.\d{2}\.\d{4}', '', title)
    title = re.sub(r'\s+', ' ', title).strip()
    words = title.split()
    if len(words) > 6:
        words = words[:6]
    query = " ".join(words).strip()
    return query if len(query) >= 4 else None


def _detect_category(title):
    """Определяет категорию товара по названию."""
    t = title.lower()
    for cat_id, cat_info in CATEGORY_MARKET_RANGES.items():
        for kw in cat_info["keywords"]:
            if kw in t:
                return cat_id, cat_info
    return None, None


def _is_auto_related(title):
    """Определяет, связан ли лот с автомобилями."""
    auto_kw = [
        'автомобил', 'легков', 'седан', 'хэтчбек', 'универсал',
        'внедорожн', 'кроссовер', 'пикап', 'минивэн',
        'toyota', 'bmw', 'mercedes', 'audi', 'volkswagen', 'hyundai',
        'kia', 'nissan', 'honda', 'ford', 'chevrolet', 'mazda', 'subaru',
        'lexus', 'infiniti', 'volvo', 'jeep', 'mitsubishi', 'suzuki',
        'land cruiser', 'camry', 'corolla', 'rio', 'solaris', 'creta',
    ]
    t = title.lower()
    return any(kw in t for kw in auto_kw)


# ─── Поиск цен на drom.ru ────────────────────────────

def search_drom(title, timeout=15):
    """Drom.ru возвращает горячие объявления (поиск не фильтрует по моделям).
    Используем только если точное название модели есть в JSON-LD."""
    query = clean_search_query(title)
    if not query:
        return []
    prices = []
    try:
        url = f"https://auto.drom.ru/all/page1/?q={quote(query)}"
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        if r.status_code != 200:
            return []

        soup = BeautifulSoup(r.text, "lxml")

        # Берём только JSON-LD Car, строго фильтруем по названию
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
                if not isinstance(data, dict):
                    continue
                if data.get("@type") == "Car":
                    name = data.get("name", "")
                    price = data.get("offers", {}).get("price", 0)
                    if price and name:
                        name_lower = name.lower()
                        query_words = [w for w in query.lower().split() if len(w) > 2]
                        # Требуем совпадения минимум 2 слов из запроса
                        matches = sum(1 for w in query_words if w in name_lower)
                        if matches >= 2:
                            prices.append(int(float(price)))
            except (json.JSONDecodeError, ValueError):
                continue

    except Exception as e:
        log.error(f"Drom error: {e}")
    return prices


# ─── Поиск цен через Bing snippets ───────────────────

def search_bing(query, timeout=15):
    """Ищет цены через Bing сниппеты."""
    prices = []
    try:
        url = f"https://www.bing.com/search?q={quote(query)}&setlang=ru"
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        if r.status_code != 200:
            return []
        soup = BeautifulSoup(r.text, "lxml")
        # Ищем цены в сниппетах
        for el in soup.find_all(["p", "span", "div", "li"]):
            text = el.get_text(strip=True)
            if len(text) < 20:
                continue
            matches = re.findall(r"(\d[\d\s\xa0]{4,15})\s*(?:₽|руб|RUB)", text, re.IGNORECASE)
            for m in matches:
                clean = re.sub(r"[\s\xa0]+", "", m)
                if clean.isdigit():
                    val = int(clean)
                    if 1000 <= val <= 500_000_000:
                        prices.append(val)
        # Фоллбэк: ищем просто большие числа рядом с ₽ или руб
        if not prices:
            raw = re.findall(r"(\d[\d\s\xa0]{4,15})\s*(?:₽|руб)", r.text, re.IGNORECASE)
            for p in raw:
                clean = re.sub(r"[\s\xa0]+", "", p)
                if clean.isdigit():
                    val = int(clean)
                    if 1000 <= val <= 500_000_000:
                        prices.append(val)
    except Exception as e:
        log.error(f"Bing error: {e}")
    return prices


# ─── Основная функция поиска ──────────────────────────

def search_market_prices(title):
    """
    Ищет рыночные цены для товара.
    Стратегия:
    1. Если авто: drom.ru → Bing
    2. Если не авто: Bing (разные запросы)
    3. Если ничего не нашли: эвристика по категории
    """
    query = clean_search_query(title)
    if not query:
        return None

    all_prices = []
    sources = {}

    # 1. Если авто — drom.ru
    if _is_auto_related(title):
        drom = search_drom(title)
        if drom:
            sources["drom.ru"] = {"count": len(drom), "avg": sum(drom) // len(drom)}
            all_prices.extend(drom)
            log.info(f"Drom: {len(drom)} prices for '{query}'")
        time.sleep(random.uniform(0.5, 1.0))

    # 2. Bing с основным запросом
    bing1 = search_bing(f"{query} купить цена")
    if bing1:
        sources["Bing"] = {"count": len(bing1), "avg": sum(bing1) // len(bing1)}
        all_prices.extend(bing1)
        log.info(f"Bing: {len(bing1)} prices for '{query}'")
    time.sleep(random.uniform(0.3, 0.7))

    # 3. Если мало цен — Bing с упрощённым запросом
    if len(all_prices) < 3:
        words = query.split()
        if len(words) > 3:
            short_query = " ".join(words[:3])
            bing2 = search_bing(f"{short_query} купить цена")
            if bing2:
                sources["Bing (short)"] = {"count": len(bing2), "avg": sum(bing2) // len(bing2)}
                all_prices.extend(bing2)
                log.info(f"Bing short: {len(bing2)} prices")

    # 4. Если совсем ничего — эвристика по категории
    if not all_prices:
        cat_id, cat_info = _detect_category(title)
        if cat_info:
            min_r, max_r = cat_info["range"]
            # Грубая оценка: берём медиану диапазона
            estimated_market = (min_r + max_r) // 4  # Берём нижнюю четверть
            sources["эвристика"] = {
                "count": 1,
                "avg": estimated_market,
                "note": f"По категории '{cat_id}'",
            }
            all_prices.append(estimated_market)
            log.info(f"Heuristic: {cat_id} -> {estimated_market:,} RUB")

    if not all_prices:
        return None

    # Анализ
    avg_price = sum(all_prices) // len(all_prices)
    min_price = min(all_prices)
    max_price = max(all_prices)
    sorted_p = sorted(all_prices)
    median_price = sorted_p[len(sorted_p) // 2]

    return {
        "query": query,
        "total_prices": len(all_prices),
        "avg": avg_price,
        "min": min_price,
        "max": max_price,
        "median": median_price,
        "prices": all_prices[:15],
        "sources": sources,
    }


# ─── Расчёт маржи ────────────────────────────────────

def calculate_margin(auction_price, market_analysis):
    """Рассчитывает оптимальную маржу на основе рыночных цен."""
    if not market_analysis or market_analysis["total_prices"] == 0:
        return {
            "status": "no_data",
            "emoji": "❓",
            "recommendation": "Нет данных о рыночных ценах.",
            "margin_pct": 0,
        }

    avg_market = market_analysis["avg"]
    min_market = market_analysis["min"]
    median_market = market_analysis["median"]

    # Стоимость (торг + оформление + логистика + налог 13%)
    trade_cost = auction_price * 1.10  # +10% на торг/логистику

    # Маржа относительно средней рыночной цены
    if trade_cost > 0:
        margin_pct = ((avg_market - trade_cost) / trade_cost) * 100
    else:
        margin_pct = 0

    # Оптимальная цена продажи (на 8% ниже средней — быстрая продажа)
    optimal_sell = int(avg_market * 0.92)
    # Быстрая продажа (чуть дешевле минимума)
    quick_sell = int(min_market * 0.95)
    # Максимальная цена (долгая продажа)
    max_sell = int(avg_market * 0.98)

    # Прибыль (без учёта налога)
    profit_avg = int(avg_market - trade_cost)
    profit_optimal = int(optimal_sell - trade_cost)
    profit_quick = int(quick_sell - trade_cost)

    # Налог на прибыль 13%
    tax = 0.13

    # Рекомендация
    if margin_pct >= 50:
        status, emoji, rec = "excellent", "🟢", "ОТЛИЧНАЯ возможность! Высокая маржа."
    elif margin_pct >= 30:
        status, emoji, rec = "good", "🟡", "Хорошая сделка. Стоит рассмотреть."
    elif margin_pct >= 15:
        status, emoji, rec = "moderate", "🟠", "Средняя маржа. Рискованно, но можно попробовать."
    elif margin_pct > 0:
        status, emoji, rec = "low", "🔴", "Низкая маржа. Высокий риск."
    else:
        status, emoji, rec = "negative", "⛔", "НЕ ВЫГОДНО. Рыночная цена ниже стоимости."

    # Время продажи
    if profit_optimal > 200_000:
        time_est = "1-2 недели"
    elif profit_optimal > 50_000:
        time_est = "2-4 недели"
    elif profit_optimal > 10_000:
        time_est = "1-3 месяца"
    elif profit_optimal > 0:
        time_est = "3-6 месяцев"
    else:
        time_est = "неопределённо"

    return {
        "status": status,
        "emoji": emoji,
        "recommendation": rec,
        "margin_pct": round(margin_pct, 1),
        "avg_market": avg_market,
        "min_market": min_market,
        "median_market": median_market,
        "optimal_sell": optimal_sell,
        "quick_sell": quick_sell,
        "max_sell": max_sell,
        "profit_avg": profit_avg,
        "profit_optimal": profit_optimal,
        "profit_quick": profit_quick,
        "trade_cost": int(trade_cost),
        "time_estimate": time_est,
        "tax": int(profit_optimal * tax) if profit_optimal > 0 else 0,
        "profit_net": int(profit_optimal * (1 - tax)) if profit_optimal > 0 else 0,
        "sources": market_analysis.get("sources", {}),
        "total_prices": market_analysis.get("total_prices", 0),
    }
