import os
from dotenv import load_dotenv

load_dotenv()

# === Telegram ===
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "YOUR_BOT_TOKEN_HERE")
CHAT_ID = os.getenv("CHAT_ID", "YOUR_CHAT_ID_HERE")

# === Расписание ===
DAILY_HOUR = int(os.getenv("DAILY_HOUR", "9"))   # час отправки (МСК)
DAILY_MINUTE = int(os.getenv("DAILY_MINUTE", "0"))

# === Фильтры ===
MIN_PRICE = int(os.getenv("MIN_PRICE", "1000"))        # минимальная цена лота (₽)
MAX_PRICE = int(os.getenv("MAX_PRICE", "5000000"))     # максимальная цена лота (₽)
MIN_PHOTOS = int(os.getenv("MIN_PHOTOS", "1"))         # минимум фото у лота

# === Категории для поиска (ключевые слова) ===
# Формат: ключевое слово -> (приоритет, примерная маржа %)
CATEGORIES = {
    # Техника и электроника
    "ноутбук":          {"priority": 1, "margin": 80},
    "ноутбуки":         {"priority": 1, "margin": 80},
    "смартфон":         {"priority": 1, "margin": 60},
    "телефон":          {"priority": 1, "margin": 50},
    "сотовый":          {"priority": 1, "margin": 50},
    "планшет":          {"priority": 1, "margin": 70},
    "монитор":          {"priority": 1, "margin": 60},
    "сервер":           {"priority": 1, "margin": 90},
    "компьютер":        {"priority": 1, "margin": 70},
    "принтер":          {"priority": 2, "margin": 40},
    "сканер":           {"priority": 2, "margin": 40},
    "роутер":           {"priority": 2, "margin": 50},
    "switch":           {"priority": 2, "margin": 50},
    "сетевое":          {"priority": 2, "margin": 60},
    "офисная техника":  {"priority": 2, "margin": 50},
    "фотоаппарат":      {"priority": 1, "margin": 80},
    "камера":           {"priority": 1, "margin": 70},
    "видеокамера":      {"priority": 1, "margin": 70},
    "наушники":         {"priority": 2, "margin": 60},

    # Авто и спецтехника
    "автомобиль":       {"priority": 1, "margin": 40},
    "машина":           {"priority": 1, "margin": 40},
    "грузовик":         {"priority": 1, "margin": 50},
    "экскаватор":       {"priority": 1, "margin": 60},
    "погрузчик":        {"priority": 1, "margin": 60},
    "трактор":          {"priority": 1, "margin": 50},
    "спецтехника":      {"priority": 1, "margin": 60},
    "автобус":          {"priority": 1, "margin": 45},
    "мотоцикл":         {"priority": 2, "margin": 50},
    "прицеп":           {"priority": 2, "margin": 50},

    # Промышленное оборудование
    "станок":           {"priority": 1, "margin": 100},
    "конвейер":         {"priority": 1, "margin": 80},
    "холодильная камера": {"priority": 1, "margin": 90},
    "морозильная":      {"priority": 1, "margin": 90},
    "компрессор":        {"priority": 2, "margin": 70},
    "генератор":        {"priority": 1, "margin": 80},
    "сварка":           {"priority": 2, "margin": 60},
    "сварочный":        {"priority": 2, "margin": 60},
    "лазерный":         {"priority": 2, "margin": 80},
    "3D-принтер":       {"priority": 1, "margin": 100},
    "фрезерный":        {"priority": 1, "margin": 90},
    "токарный":         {"priority": 1, "margin": 90},
    "пресс":            {"priority": 2, "margin": 70},

    # Бытовая техника
    "холодильник":      {"priority": 1, "margin": 60},
    "стиральная машина": {"priority": 1, "margin": 50},
    "посудомоечная":    {"priority": 2, "margin": 40},
    "духовой шкаф":     {"priority": 2, "margin": 40},
    "кондиционер":      {"priority": 1, "margin": 70},
    "сплит-система":    {"priority": 1, "margin": 70},
    "телевизор":        {"priority": 1, "margin": 50},
    "TV":               {"priority": 1, "margin": 50},
    "LED":              {"priority": 2, "margin": 50},
    "музыкальная":      {"priority": 2, "margin": 60},
    "инструмент":       {"priority": 1, "margin": 70},
    "перфоратор":       {"priority": 2, "margin": 60},
    "дрель":            {"priority": 2, "margin": 50},

    # Мебель и товары
    "мебель":           {"priority": 2, "margin": 40},
    "офисная мебель":   {"priority": 2, "margin": 40},

    # Спорт и отдых
    "велосипед":        {"priority": 1, "margin": 60},
    "тренажёр":         {"priority": 1, "margin": 60},

    # Металл
    "металл":           {"priority": 3, "margin": 30},
    "медь":             {"priority": 2, "margin": 40},
    "алюминий":         {"priority": 2, "margin": 35},
}

# === Площадки для парсинга ===
SOURCES = {
    "efrsb": True,        # bankrot.fedresurs.ru
    "lot_online": True,   # lot-online.ru
}
