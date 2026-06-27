"""
Автономный сканер — проверка парсинга без Telegram.
Запуск: python scan.py
"""
import asyncio
import sys
import os
import httpx
import logging

sys.path.insert(0, os.path.dirname(__file__))

from src.efrsb_parser import fetch_efrsb_lots
from src.lot_online_parser import fetch_lot_online_lots
from src.analyzer import analyze_lots
import config

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)


async def scan():
    print("=" * 60)
    print("  BANKROT BOT - Автономный сканер")
    print("=" * 60)
    print()
    
    all_lots = []
    
    async with httpx.AsyncClient(verify=False) as client:
        # ЕФРСБ
        print("[1/2] Сканирую ЕФРСБ (bankrot.fedresurs.ru)...")
        try:
            efrsb_lots = await fetch_efrsb_lots(client, list(config.CATEGORIES.keys()))
            print(f"  -> Найдено: {len(efrsb_lots)} лотов")
            all_lots.extend(efrsb_lots)
        except Exception as e:
            print(f"  -> Ошибка: {e}")
        
        # lot-online.ru
        print("[2/2] Сканирую lot-online.ru...")
        try:
            lot_online_lots = await fetch_lot_online_lots(client)
            print(f"  -> Найдено: {len(lot_online_lots)} лотов")
            all_lots.extend(lot_online_lots)
        except Exception as e:
            print(f"  -> Ошибка: {e}")
    
    print()
    print(f"Всего найдено: {len(all_lots)} лотов")
    print()
    
    if not all_lots:
        print("Лоты не найдены. Возможные причины:")
        print("  - Сайты заблокировали запрос")
        print("  - Изменилась структура API")
        print("  - Нет активных торгов")
        print()
        print("Бот продолжит работу через Telegram即使 через API-фоллбэки.")
        return
    
    # Анализ
    print("=" * 60)
    print("  АНАЛИЗ МАРЖИНАЛЬНОСТИ")
    print("=" * 60)
    print()
    
    analyzed = analyze_lots(
        all_lots,
        config.CATEGORIES,
        min_price=config.MIN_PRICE,
        max_price=config.MAX_PRICE,
    )
    
    print(f"Проанализировано: {len(analyzed)} лотов (с фильтрами)")
    print()
    
    # Топ-10
    top = analyzed[:10]
    for i, lot in enumerate(top, 1):
        title = lot["title"][:60]
        price = lot["price"]
        margin = lot["estimated_margin"]
        category = lot["category"]
        keywords = lot["matched_keywords"]
        
        print(f"  #{i} {title}")
        print(f"     Цена: {price:,.0f} rub. | Маржа: {margin}% | {category}")
        print(f"     Ключ: {keywords}")
        print()
    
    # Статистика
    if analyzed:
        avg_margin = sum(l["estimated_margin"] for l in analyzed) / len(analyzed)
        max_margin = max(analyzed, key=lambda x: x["estimated_margin"])
        
        print("=" * 60)
        print(f"  СТАТИСТИКА:")
        print(f"  Всего лотов:       {len(all_lots)}")
        print(f"  С фильтрами:       {len(analyzed)}")
        print(f"  Средняя маржа:     {avg_margin:.0f}%")
        print(f"  Лучший лот:        {max_margin['title'][:40]}")
        print(f"  Маржа лучшего:     {max_margin['estimated_margin']}%")
        print(f"  Цена лучшего:      {max_margin['price']:,.0f} rub.")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(scan())
