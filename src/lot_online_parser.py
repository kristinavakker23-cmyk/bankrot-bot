"""
Парсер lot-online.ru — агрегатор банкротских торгов
"""
import httpx
import logging
from datetime import datetime
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ru-RU,ru;q=0.9",
}


async def fetch_lot_online_lots(client: httpx.AsyncClient) -> List[Dict]:
    """Получаем лоты с lot-online.ru через API"""
    lots = []
    
    # lot-online.ru использует API
    api_urls = [
        "https://api.lot-online.ru/v2/lots?limit=50&sort=new&status=active",
        "https://lot-online.ru/api/lots?limit=50&sort=new",
        "https://www.lot-online.ru/api/v2/lots?limit=50",
    ]
    
    for url in api_urls:
        try:
            resp = await client.get(url, headers=HEADERS, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                items = data if isinstance(data, list) else data.get("lots", data.get("items", data.get("data", [])))
                for item in items[:50]:
                    lot = _parse_lot(item)
                    if lot:
                        lots.append(lot)
                if lots:
                    logger.info(f"lot-online.ru: получено {len(lots)} лотов")
                    return lots
        except Exception as e:
            logger.debug(f"lot-online.ru API ({url}): {e}")
            continue
    
    # Фоллбэк: HTML парсинг
    html_lots = await _parse_lot_online_html(client)
    lots.extend(html_lots)
    return lots


async def _parse_lot_online_html(client: httpx.AsyncClient) -> List[Dict]:
    """Фоллбэк: парсим HTML страницу lot-online.ru"""
    from bs4 import BeautifulSoup
    lots = []
    
    urls_to_try = [
        "https://www.lot-online.ru/auction/lots?status=active&sort=new",
        "https://lot-online.ru/auction/lots",
    ]
    
    for url in urls_to_try:
        try:
            resp = await client.get(url, headers=HEADERS, timeout=15)
            if resp.status_code == 200:
                html = resp.text
                soup = BeautifulSoup(html, "lxml")
                
                # Ищем карточки лотов
                cards = soup.select(".lot-card, .lot-item, [data-lot], .auction-lot, .card")
                if not cards:
                    # Пробуем найти любые ссылки на лоты
                    links = soup.find_all("a", href=True)
                    lot_links = [a for a in links if "/lot/" in a.get("href", "") or "/lots/" in a.get("href", "")]
                    for link in lot_links[:50]:
                        title = link.get_text(strip=True)
                        href = link["href"]
                        if not href.startswith("http"):
                            href = f"https://www.lot-online.ru{href}"
                        if title and len(title) > 3:
                            lots.append({
                                "source": "lot-online.ru",
                                "title": title,
                                "price": 0,
                                "description": "",
                                "url": href,
                                "date_end": "",
                                "photos_count": 0,
                                "source_site": "lot-online.ru",
                            })
                else:
                    for card in cards[:50]:
                        lot = _parse_html_card(card)
                        if lot:
                            lots.append(lot)
                
                if lots:
                    logger.info(f"lot-online.ru HTML: найдено {len(lots)} лотов")
                    break
        except Exception as e:
            logger.debug(f"lot-online.ru HTML ({url}): {e}")
            continue
    
    return lots


def _parse_html_card(card) -> Optional[Dict]:
    """Парсим карточку лота из HTML"""
    try:
        title_el = card.select_one(".lot-card__title, .lot-title, h3, h4, .title")
        title = title_el.get_text(strip=True) if title_el else ""
        
        price_el = card.select_one(".lot-card__price, .price, .lot-price")
        price = 0
        if price_el:
            price_text = price_el.get_text(strip=True)
            price = _parse_price(price_text)
        
        link_el = card.select_one("a[href]")
        url = ""
        if link_el:
            url = link_el.get("href", "")
            if not url.startswith("http"):
                url = f"https://www.lot-online.ru{url}"
        
        img_count = len(card.select("img"))
        
        if title and price > 0:
            return {
                "source": "lot-online.ru",
                "title": title,
                "price": price,
                "description": "",
                "url": url,
                "date_end": "",
                "photos_count": img_count,
                "source_site": "lot-online.ru",
            }
    except Exception:
        pass
    return None


def _parse_lot(item: dict) -> Optional[Dict]:
    """Парсим лот из API ответа"""
    try:
        title = item.get("title", "") or item.get("name", "") or item.get("lot_name", "")
        
        price_keys = ["current_price", "start_price", "price", "min_price", "lot_price"]
        price = 0
        for key in price_keys:
            val = item.get(key)
            if val:
                if isinstance(val, str):
                    price = _parse_price(val)
                else:
                    price = float(val)
                if price > 0:
                    break
        
        if not title or price <= 0:
            return None
            
        url = item.get("url", "") or item.get("link", "")
        if not url:
            lot_id = item.get("id", "") or item.get("lot_id", "")
            if lot_id:
                url = f"https://www.lot-online.ru/lot/{lot_id}"
        
        return {
            "source": "lot-online.ru",
            "title": title,
            "price": price,
            "description": item.get("description", ""),
            "url": url,
            "date_end": item.get("end_date", "") or item.get("auction_end", ""),
            "photos_count": len(item.get("photos", []) or []),
            "source_site": "lot-online.ru",
        }
    except Exception:
        return None


def _parse_price(price_str: str) -> float:
    try:
        cleaned = price_str.replace(" ", "").replace("\xa0", "").replace(",", ".").replace("₽", "").replace("руб", "").strip()
        return float(cleaned) if cleaned else 0
    except (ValueError, AttributeError):
        return 0
