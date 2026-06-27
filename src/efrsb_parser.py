"""
Парсер ЕФРСБ (bankrot.fedresurs.ru)
Используем внутренний API Angular-приложения + httpx
"""
import httpx
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# ЕФРСБ использует внутренний API, который обслуживает Angular фронтенд
EFRSB_API_BASE = "https://bankrot.fedresurs.ru/api"

# Заголовки для имитации браузера
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://bankrot.fedresurs.ru/",
    "Origin": "https://bankrot.fedresurs.ru",
}


async def fetch_efrsb_lots(client: httpx.AsyncClient, category_keywords: list) -> List[Dict]:
    """
    Получаем лоты из ЕФРСБ через их внутренний API.
    Пробуем разные эндпоинты, т.к. ЕФРСБ периодически меняет API.
    """
    lots = []
    
    # Пробуем несколько вариантов API
    api_endpoints = [
        "/Trade/GetTradesForSearch",
        "/Trade/GetTrades",
        "/Search/FindTrades",
        "/lotcards/search",
    ]
    
    # Базовый payload для POST-запроса
    now = datetime.now()
    payload = {
        "offset": 0,
        "limit": 50,
        "searchString": "",
        "categories": [],
        "dateFrom": (now - timedelta(days=3)).strftime("%Y-%m-%d"),
        "dateTo": now.strftime("%Y-%m-%d"),
        "priceFrom": 0,
        "priceTo": 10000000,
        "isPhysical": False,
        "tradeTypeId": "",
        "regionId": "",
    }

    for endpoint in api_endpoints:
        url = f"{EFRSB_API_BASE}{endpoint}"
        try:
            resp = await client.post(url, json=payload, headers=HEADERS, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, dict) and "items" in data:
                    for item in data["items"][:50]:
                        lot = _parse_efrsb_lot(item)
                        if lot:
                            lots.append(lot)
                elif isinstance(data, list):
                    for item in data[:50]:
                        lot = _parse_efrsb_lot(item)
                        if lot:
                            lots.append(lot)
                if lots:
                    logger.info(f"ЕФРСБ: получено {len(lots)} лотов через {endpoint}")
                    return lots
        except Exception as e:
            logger.debug(f"ЕФРСБ {endpoint}: {e}")
            continue

    # Если API не сработал — пробуем парсить HTML (фоллбэк)
    html_lots = await _parse_efrsb_html(client)
    lots.extend(html_lots)
    return lots


async def _parse_efrsb_html(client: httpx.AsyncClient) -> List[Dict]:
    """Фоллбэк: парсим HTML страницу торгов ЕФРСБ"""
    from bs4 import BeautifulSoup
    lots = []
    
    url = "https://bankrot.fedresurs.ru/TradeList.aspx"
    try:
        resp = await client.get(url, headers=HEADERS, timeout=15)
        if resp.status_code == 200:
            html = resp.text
            soup = BeautifulSoup(html, "lxml")
            
            # Ищем таблицу с лотами
            rows = soup.select("table tr")
            for row in rows[1:]:  # пропускаем заголовок
                cols = row.find_all("td")
                if len(cols) >= 4:
                    lot = {
                        "source": "ЕФРСБ",
                        "title": cols[0].get_text(strip=True),
                        "price": _parse_price(cols[1].get_text(strip=True)),
                        "description": cols[2].get_text(strip=True) if len(cols) > 2 else "",
                        "url": _extract_link(cols[0]),
                        "date_end": cols[3].get_text(strip=True) if len(cols) > 3 else "",
                        "photos_count": 0,
                        "source_site": "bankrot.fedresurs.ru",
                    }
                    if lot["price"] and lot["price"] > 0:
                        lots.append(lot)
    except Exception as e:
        logger.error(f"ЕФРСБ HTML парсинг: {e}")
    
    return lots


def _parse_efrsb_lot(item: dict) -> Optional[Dict]:
    """Парсим один лот из ответа ЕФРСБ API"""
    try:
        title = item.get("lotName", "") or item.get("title", "") or item.get("name", "")
        price_str = item.get("currentPrice", 0) or item.get("startPrice", 0) or item.get("price", 0)
        
        if isinstance(price_str, str):
            price = _parse_price(price_str)
        else:
            price = float(price_str) if price_str else 0
            
        if not title or price <= 0:
            return None
            
        lot_id = item.get("id", "") or item.get("lotId", "")
        url = f"https://bankrot.fedresurs.ru/TradeLotCard.aspx?id={lot_id}" if lot_id else ""
        
        return {
            "source": "ЕФРСБ",
            "title": title,
            "price": price,
            "description": item.get("description", "") or item.get("lotDescription", ""),
            "url": url,
            "date_end": item.get("tradeEndDate", "") or item.get("endDate", ""),
            "photos_count": len(item.get("photos", []) or []),
            "source_site": "bankrot.fedresurs.ru",
        }
    except Exception as e:
        logger.debug(f"Ошибка парсинга лота ЕФРСБ: {e}")
        return None


def _parse_price(price_str: str) -> float:
    """Парсим цену из строки (убираем пробелы, заменяем запятые)"""
    try:
        cleaned = price_str.replace(" ", "").replace("\xa0", "").replace(",", ".").replace("₽", "").strip()
        return float(cleaned) if cleaned else 0
    except (ValueError, AttributeError):
        return 0


def _extract_link(element) -> str:
    """Извлекаем ссылку из HTML-элемента"""
    a_tag = element.find("a") if hasattr(element, "find") else None
    if a_tag and a_tag.get("href"):
        href = a_tag["href"]
        if not href.startswith("http"):
            return f"https://bankrot.fedresurs.ru{href}"
        return href
    return ""
