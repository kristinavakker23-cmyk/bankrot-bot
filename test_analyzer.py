"""Тест анализатора"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from src.analyzer import analyze_lots, format_daily_digest
import config

# Тестовые данные
test_lots = [
    {"source": "Тест", "title": "Ноутбук ASUS VivoBook", "price": 15000, "description": "ноутбук игровой", "url": "https://example.com/1", "date_end": "", "photos_count": 3, "source_site": "test"},
    {"source": "Тест", "title": "Сервер HP ProLiant", "price": 50000, "description": "сервер рабочий", "url": "https://example.com/2", "date_end": "", "photos_count": 5, "source_site": "test"},
    {"source": "Тест", "title": "Станок токарный", "price": 120000, "description": "токарный станок ЧПУ", "url": "https://example.com/3", "date_end": "", "photos_count": 2, "source_site": "test"},
    {"source": "Тест", "title": "Холодильник Samsung", "price": 8000, "description": "холодильник двухкамерный", "url": "https://example.com/4", "date_end": "", "photos_count": 1, "source_site": "test"},
    {"source": "Тест", "title": "Стол офисный", "price": 3000, "description": "офисная мебель", "url": "https://example.com/5", "date_end": "", "photos_count": 1, "source_site": "test"},
]

analyzed = analyze_lots(test_lots, config.CATEGORIES, min_price=1000, max_price=5000000)
print(f"Analyzed: {len(analyzed)} lots")
for lot in analyzed:
    title = lot["title"]
    price = lot["price"]
    margin = lot["estimated_margin"]
    score = lot["score"]
    print(f"  {title} | Price: {price} | Margin: {margin}% | Score: {score:.1f}")

digest = format_daily_digest(analyzed, max_lots=5)
print()
print(digest[:800])
