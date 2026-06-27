"""
Модуль анализа и фильтрации лотов.
Определяет маржинальность, приоритет, ранжирует лоты.
"""
import re
import logging
from typing import List, Dict, Tuple

logger = logging.getLogger(__name__)


def analyze_lots(lots: List[Dict], categories: dict, 
                  min_price: float = 1000, max_price: float = 5_000_000) -> List[Dict]:
    """
    Анализирует лоты, считает маржу и приоритет.
    Возвращает отсортированный по марже список.
    """
    analyzed = []
    
    for lot in lots:
        score = _calculate_score(lot, categories)
        if score is None:
            continue
            
        lot["score"] = score["score"]
        lot["matched_keywords"] = score["keywords"]
        lot["estimated_margin"] = score["margin"]
        lot["category"] = score["category"]
        
        # Фильтр по цене
        price = lot.get("price", 0)
        if price < min_price or price > max_price:
            continue
            
        analyzed.append(lot)
    
    # Сортируем по score (маржа * приоритет)
    analyzed.sort(key=lambda x: x["score"], reverse=True)
    
    logger.info(f"Проанализировано {len(analyzed)} лотов из {len(lots)}")
    return analyzed


def _calculate_score(lot: dict, categories: dict) -> dict:
    """
    Считаем score лота на основе ключевых слов в заголовке и описании.
    Score = estimated_margin * priority_multiplier
    """
    title = (lot.get("title", "") or "").lower()
    description = (lot.get("description", "") or "").lower()
    text = f"{title} {description}"
    
    best_match = None
    best_score = 0
    
    for keyword, meta in categories.items():
        keyword_lower = keyword.lower()
        if keyword_lower in text:
            # Нашли ключевое слово
            margin = meta["margin"]
            priority = meta["priority"]
            
            # Множитель приоритета (1 = высший)
            priority_mult = {1: 1.5, 2: 1.0, 3: 0.7}.get(priority, 1.0)
            
            # Бонус за совпадение в заголовке (более точно)
            title_bonus = 2.0 if keyword_lower in title else 1.0
            
            # Штраф если лот уже с маленькой ценой (всё равно маржинально)
            price = lot.get("price", 0)
            price_bonus = 1.0
            if 1000 <= price <= 5000:
                price_bonus = 1.3  # дешёвые лоты — легко купить
            elif 5000 < price <= 50000:
                price_bonus = 1.1
            elif price > 500000:
                price_bonus = 0.8  # дорогие — сложнее продать быстро
            
            score = margin * priority_mult * title_bonus * price_bonus
            
            if score > best_score:
                best_score = score
                best_match = {
                    "score": score,
                    "keywords": keyword,
                    "margin": margin,
                    "category": _get_category_name(keyword),
                }
    
    return best_match


def _get_category_name(keyword: str) -> str:
    """Определяем общую категорию по ключевому слову"""
    tech_kw = ["ноутбук", "ноутбуки", "смартфон", "телефон", "сотовый", "планшет", 
               "монитор", "сервер", "компьютер", "принтер", "сканер", "роутер", "switch",
               "сетевое", "офисная техника", "фотоаппарат", "камера", "видеокамера", "наушники"]
    
    auto_kw = ["автомобиль", "машина", "грузовик", "экскаватор", "погрузчик", "трактор",
               "спецтехника", "автобус", "мотоцикл", "прицеп"]
    
    industry_kw = ["станок", "конвейер", "холодильная камера", "морозильная", "компрессор",
                   "генератор", "сварка", "сварочный", "лазерный", "3D-принтер", "фрезерный",
                   "токарный", "пресс"]
    
    home_kw = ["холодильник", "стиральная машина", "посудомоечная", "духовой шкаф",
               "кондиционер", "сплит-система", "телевизор", "TV", "LED", "музыкальная"]
    
    tool_kw = ["инструмент", "перфоратор", "дрель"]
    
    sport_kw = ["велосипед", "тренажёр"]
    
    metal_kw = ["металл", "медь", "алюминий"]
    
    if keyword in tech_kw:
        return "💻 Электроника / Техника"
    elif keyword in auto_kw:
        return "🚗 Авто / Спецтехника"
    elif keyword in industry_kw:
        return "🏭 Промоборудование"
    elif keyword in home_kw:
        return "🏠 Бытовая техника"
    elif keyword in tool_kw:
        return "🔧 Инструменты"
    elif keyword in sport_kw:
        return "🚴 Спорт / Отдых"
    elif keyword in metal_kw:
        return "🔩 Металл"
    else:
        return "📦 Прочее"


def format_lot_message(lot: dict, index: int) -> str:
    """Форматирует лот в красивое сообщение для Telegram"""
    price = lot.get("price", 0)
    margin = lot.get("estimated_margin", 0)
    estimated_sell = int(price * (1 + margin / 100))
    profit = estimated_sell - price
    
    # Эмодзи по марже
    if margin >= 80:
        margin_emoji = "🔥🔥🔥"
    elif margin >= 50:
        margin_emoji = "🔥🔥"
    elif margin >= 30:
        margin_emoji = "🔥"
    else:
        margin_emoji = "💰"
    
    source = lot.get("source", "Неизвестно")
    url = lot.get("url", "")
    keywords = lot.get("matched_keywords", "")
    category = lot.get("category", "")
    
    title = lot.get("title", "Без названия")
    # Обрезаем длинное название
    if len(title) > 80:
        title = title[:77] + "..."
    
    msg = (
        f"<b>{index}. {title}</b>\n"
        f"\n"
        f"💰 <b>Цена:</b> {price:,.0f} ₽\n"
        f"📈 <b>Примерная маржа:</b> {margin}% {margin_emoji}\n"
        f"💵 <b>Можно продать за:</b> ~{estimated_sell:,.0f} ₽\n"
        f"💸 <b>Прибыль:</b> ~{profit:,.0f} ₽\n"
        f"\n"
        f"📂 <b>Категория:</b> {category}\n"
        f"🏷 <b>Ключевое слово:</b> {keywords}\n"
        f"🌐 <b>Источник:</b> {source}\n"
    )
    
    if url:
        msg += f"🔗 <a href=\"{url}\">Перейти к лоту</a>\n"
    
    return msg


def format_daily_digest(lots: List[Dict], max_lots: int = 10) -> str:
    """Формирует ежедневный дайджест"""
    if not lots:
        return (
            "📋 <b>Дайджест банкротских торгов</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n\n"
            "😔 Сегодня подходящих лотов не найдено.\n"
            "Попробуйте расширить поиск или изменить фильтры."
        )
    
    header = (
        "📋 <b>🔥 ТОП лотов на сегодня</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
    )
    
    # Берём топ-N лотов
    top_lots = lots[:max_lots]
    
    messages = [header]
    for i, lot in enumerate(top_lots, 1):
        msg = format_lot_message(lot, i)
        messages.append(msg)
        messages.append("───────────────────\n")
    
    # Статистика в конце
    total_lots = len(lots)
    avg_margin = sum(l.get("estimated_margin", 0) for l in lots) / len(lots) if lots else 0
    max_margin_lot = max(lots, key=lambda x: x.get("estimated_margin", 0)) if lots else None
    
    stats = (
        f"\n📊 <b>Статистика:</b>\n"
        f"• Всего найдено: {total_lots} лотов\n"
        f"• Средняя маржа: {avg_margin:.0f}%\n"
    )
    
    if max_margin_lot:
        stats += (
            f"• 🏆 Лучший лот: {max_margin_lot.get('title', '')[:40]}...\n"
            f"  Маржа: {max_margin_lot.get('estimated_margin', 0)}% | "
            f"Цена: {max_margin_lot.get('price', 0):,.0f} ₽\n"
        )
    
    messages.append(stats)
    
    return "\n".join(messages)
