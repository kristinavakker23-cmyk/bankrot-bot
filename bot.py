"""
Bankrot Bot — Telegram-бот для поиска лотов на торгах.
Источник: torgi.gov.ru (Единая торговая площадка).
Версия для Render.com (webhook mode).
"""
import os
import re
import sys
import time
import json
import logging
import requests
import threading
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from flask import Flask, request as flask_request

# === НАСТРОЙКА ===
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHAT_ID = os.getenv("CHAT_ID", "")
TIMEZONE = os.getenv("TIMEZONE", "Europe/Moscow")
DAILY_HOUR = int(os.getenv("DAILY_HOUR", "9"))
DAILY_MINUTE = int(os.getenv("DAILY_MINUTE", "0"))
MIN_PRICE = float(os.getenv("MIN_PRICE", "1000"))
MAX_PRICE = float(os.getenv("MAX_PRICE", "5000000"))
PORT = int(os.getenv("PORT", "10000"))
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL", "")

API = f"https://api.telegram.org/bot{BOT_TOKEN}"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                    handlers=[logging.StreamHandler(sys.stdout)])
log = logging.getLogger("bankrot")

# === TELEGRAM ===

def api_call(method, **kwargs):
    try:
        r = requests.post(f"{API}/{method}", json=kwargs, timeout=30)
        data = r.json()
        if not data.get("ok"):
            log.error(f"API error: {data}")
        return data
    except Exception as e:
        log.error(f"API {method} failed: {e}")
        return {"ok": False}

def send_message(chat_id, text, parse_mode="HTML"):
    if len(text) > 4000:
        parts = []
        while text:
            if len(text) <= 4000:
                parts.append(text)
                break
            cut = text[:4000].rfind("\n\n")
            if cut == -1: cut = text[:4000].rfind("\n")
            if cut == -1: cut = 4000
            parts.append(text[:cut])
            text = text[cut:]
        for part in parts:
            api_call("sendMessage", chat_id=chat_id, text=part,
                     parse_mode=parse_mode, disable_web_page_preview=True)
    else:
        api_call("sendMessage", chat_id=chat_id, text=text,
                 parse_mode=parse_mode, disable_web_page_preview=True)

def answer(chat_id, text):
    send_message(chat_id, text)

# === КАТЕГОРИИ ДЛЯ МАРЖИНАЛЬНОСТИ ===
# Ключевые слова -> (приоритет 1-3, ожидаемая маржа %)
CATEGORIES = {
    # Техника (легко перепродать)
    "ноутбук": (1, 80), "ноутбуки": (1, 80), "смартфон": (1, 60),
    "телефон": (1, 50), "планшет": (1, 70), "монитор": (1, 60),
    "сервер": (1, 90), "компьютер": (1, 70), "принтер": (2, 40),
    "роутер": (2, 50), "сетевое": (2, 60), "фотоаппарат": (1, 80),
    "камера": (1, 70), "наушники": (2, 60), "проектор": (1, 70),
    "ресивер": (2, 50), "видеорегистратор": (2, 60),
    # Авто и техника
    "автомобиль": (1, 40), "грузовик": (1, 50), "экскаватор": (1, 60),
    "погрузчик": (1, 60), "трактор": (1, 50), "спецтехника": (1, 60),
    "автобус": (1, 45), "мотоцикл": (2, 50), "прицеп": (2, 50),
    "кран": (1, 55), "бульдозер": (1, 55), "автокран": (1, 55),
    # Промышленное
    "станок": (1, 100), "конвейер": (1, 80), "генератор": (1, 80),
    "компрессор": (2, 70), "сварочный": (2, 60), "лазерный": (2, 80),
    "3d-принтер": (1, 100), "фрезерный": (1, 90), "токарный": (1, 90),
    "пресс": (2, 70), "формовочный": (2, 70), "литьевой": (2, 70),
    # Бытовая техника
    "холодильник": (1, 60), "стиральная машина": (1, 50),
    "кондиционер": (1, 70), "телевизор": (1, 50), "ТВ": (1, 50),
    "духовой": (2, 40), "посудомоечная": (2, 40),
    # Инструмент
    "инструмент": (1, 70), "перфоратор": (2, 60), "дрель": (2, 50),
    "болгарка": (2, 50), "лобзик": (2, 50), "сверлильный": (2, 60),
    # Спорт
    "велосипед": (1, 60), "тренажёр": (1, 60),
    # Металл (лом)
    "медь": (2, 40), "алюминий": (2, 35), "латунь": (2, 38),
    # Мебель (офисная)
    "офисная мебель": (2, 40), "стол": (3, 30), "стул": (3, 25),
}

def _category(kw):
    tech = ["ноутбук","ноутбуки","смартфон","телефон","планшет","монитор","сервер",
            "компьютер","принтер","роутер","сетевое","фотоаппарат","камера","наушники",
            "проектор","ресивер","видеорегистратор"]
    auto = ["автомобиль","грузовик","экскаватор","погрузчик","трактор","спецтехника",
            "автобус","мотоцикл","прицеп","кран","бульдозер","автокран"]
    ind = ["станок","конвейер","генератор","компрессор","сварочный","лазерный",
           "3d-принтер","фрезерный","токарный","пресс","формовочный","литьевой"]
    home = ["холодильник","стиральная машина","кондиционер","телевизор","ТВ","духовой","посудомоечная"]
    tool = ["инструмент","перфоратор","дрель","болгарка","лобзик","сверлильный"]
    if kw in tech: return "💻 Электроника"
    if kw in auto: return "🚗 Авто/Спецтехника"
    if kw in ind: return "🏭 Промоборудование"
    if kw in home: return "🏠 Бытовая техника"
    if kw in tool: return "🔧 Инструменты"
    return "📦 Прочее"

# === ПАРСИНГ torgi.gov.ru ===

TG_HEADERS = {"Accept": "application/json", "User-Agent": "Mozilla/5.0"}

def fetch_torgi_lots():
    """Получаем лоты с torgi.gov.ru — API только GET с пагинацией."""
    all_lots = []
    offset = 0
    batch = 100
    max_lots = 1000  # не более 1000 за раз (чтобы не задолбать API)

    while offset < max_lots:
        try:
            url = f"https://torgi.gov.ru/new/api/public/lotcards/search?limit={batch}&offset={offset}"
            r = requests.get(url, headers=TG_HEADERS, timeout=20)
            if r.status_code != 200:
                log.warning(f"torgi.gov.ru: status {r.status_code}")
                break
            data = r.json()
            content = data.get("content", [])
            if not content:
                break
            for lot in content:
                parsed = _parse_torgi_lot(lot)
                if parsed:
                    all_lots.append(parsed)
            offset += batch
            log.info(f"torgi.gov.ru: загружено {len(all_lots)} лотов (offset={offset})")
            if data.get("last", True):
                break
        except Exception as e:
            log.error(f"torgi.gov.ru fetch error: {e}")
            break

    log.info(f"torgi.gov.ru: итого {len(all_lots)} лотов")
    return all_lots


def _parse_torgi_lot(lot):
    """Парсим один лот с torgi.gov.ru."""
    try:
        title = lot.get("lotName", "") or ""
        description = lot.get("lotDescription", "") or ""
        price = lot.get("priceMin", 0) or 0
        if isinstance(price, str):
            price = float(price) if price else 0

        if not title or price <= 0:
            return None

        # Ссылка на лот
        lot_id = lot.get("id", "")
        url = f"https://torgi.gov.ru/new/public/lotcards/regcard/{lot_id}" if lot_id else ""

        # Категория и тип
        category = lot.get("category", {})
        cat_name = category.get("name", "") if isinstance(category, dict) else ""

        bidd_type = lot.get("biddType", {})
        bidd_name = bidd_type.get("name", "") if isinstance(bidd_type, dict) else ""

        bidd_form = lot.get("biddForm", {})
        form_name = bidd_form.get("name", "") if isinstance(bidd_form, dict) else ""

        status = lot.get("lotStatus", "")

        # Дата окончания
        end_time = lot.get("biddEndTime", "")

        # Количество фото
        images = lot.get("lotImages", [])
        photos_count = len(images) if images else 0

        # Доп. атрибуты
        attrs = lot.get("attributes", [])
        attr_text = " ".join([
            a.get("value", {}).get("name", "") if isinstance(a.get("value"), dict)
            else str(a.get("value", ""))
            for a in (attrs or [])
        ])

        return {
            "title": title,
            "description": description,
            "price": price,
            "url": url,
            "category": cat_name,
            "bidd_type": bidd_name,
            "bidd_form": form_name,
            "status": status,
            "date_end": end_time,
            "photos": photos_count,
            "attributes": attr_text,
            "source": "torgi.gov.ru",
        }
    except Exception as e:
        return None

# === АНАЛИЗ МАРЖИНАЛЬНОСТИ ===

def analyze_lots(lots):
    """Фильтруем и ранжируем лоты по марже."""
    result = []
    for lot in lots:
        price = lot.get("price", 0)
        if price < MIN_PRICE or price > MAX_PRICE:
            continue
        title = (lot.get("title", "") or "").lower()
        desc = (lot.get("description", "") or "").lower()
        attrs = (lot.get("attributes", "") or "").lower()
        text = f"{title} {desc} {attrs}"

        best_score = 0
        best_kw = None
        best_margin = 0

        for kw, (priority, margin) in CATEGORIES.items():
            if kw in text:
                p_mult = {1: 1.5, 2: 1.0, 3: 0.7}.get(priority, 1.0)
                title_bonus = 2.0 if kw in title else 1.0
                price_bonus = 1.3 if price <= 5000 else (1.1 if price <= 50000 else 0.8)
                score = margin * p_mult * title_bonus * price_bonus
                if score > best_score:
                    best_score = score
                    best_kw = kw
                    best_margin = margin

        if best_kw:
            lot["score"] = best_score
            lot["margin"] = best_margin
            lot["keywords"] = best_kw
            lot["category_tg"] = _category(best_kw)
            result.append(lot)

    result.sort(key=lambda x: x["score"], reverse=True)
    return result

# === ФОРМАТИРОВАНИЕ ===

def fmt_lot(lot, i):
    p = lot["price"]
    m = lot["margin"]
    sell = int(p * (1 + m / 100))
    profit = sell - p
    title = lot["title"]
    if len(title) > 70: title = title[:67] + "..."
    url = lot.get("url", "")
    cat = lot.get("category", "") or lot.get("category_tg", "")
    form = lot.get("bidd_form", "")
    end = lot.get("date_end", "")
    if end and "T" in end:
        try:
            end = datetime.fromisoformat(end.replace("Z", "+00:00")).strftime("%d.%m.%Y %H:%M")
        except: pass

    msg = (
        f"<b>{i}. {title}</b>\n"
        f"Цена: <b>{p:,.0f} руб.</b>\n"
        f"Маржа: <b>{m}%</b>\n"
        f"Продать за: ~<b>{sell:,.0f} руб.</b>\n"
        f"Прибыль: ~<b>{profit:,.0f} руб.</b>\n"
    )
    if cat: msg += f"Категория: {cat}\n"
    if form: msg += f"Тип торгов: {form}\n"
    if end: msg += f"Окончание: {end}\n"
    msg += f"Источник: torgi.gov.ru\n"
    if url: msg += f'<a href="{url}">Перейти к лоту</a>\n'
    return msg


def fmt_digest(lots, n=10):
    if not lots:
        return (
            "<b>Торги — дайджест</b>\n\n"
            "Сегодня подходящих лотов нет.\n"
            "Попробуйте изменить фильтры (/help)."
        )
    lines = ["<b>ТОП лотов на сегодня</b>\n━━━━━━━━━━━━━━━━━━━━━\n"]
    for i, lot in enumerate(lots[:n], 1):
        lines.append(fmt_lot(lot, i))
        lines.append("───────────────────")
    avg = sum(l.get("margin", 0) for l in lots) / len(lots)
    best = max(lots, key=lambda x: x.get("margin", 0))
    lines.append(f"\nВсего: {len(lots)} лотов | Средняя маржа: {avg:.0f}%")
    lines.append(f"Лучший: {best['title'][:40]}... | Маржа: {best['margin']}%")
    return "\n".join(lines)

# === ЧАТ ID ===

def load_chat_ids():
    ids = set()
    if CHAT_ID: ids.add(int(CHAT_ID))
    try:
        with open("chat_ids.txt") as f:
            for line in f:
                line = line.strip()
                if line: ids.add(int(line))
    except FileNotFoundError: pass
    return ids

def save_chat_id(cid):
    ids = load_chat_ids()
    if cid not in ids:
        with open("chat_ids.txt", "a") as f:
            f.write(f"{cid}\n")
        log.info(f"New chat_id: {cid}")

# === КОМАНДЫ ===

def handle_command(chat_id, text, user):
    cmd = text.split()[0].lower() if text else ""
    args = text.split()[1:] if text else []
    log.info(f"Command {cmd} from chat={chat_id}")

    if cmd == "/start":
        answer(chat_id,
            "<b>Бот для поиска лотов на торгах</b>\n\n"
            "Сканирую torgi.gov.ru — Единую торговую площадку.\n"
            "Нахожу лоты с высокой маржинальностью для перепродажи.\n\n"
            "<b>Команды:</b>\n"
            "/scan — поиск лотов прямо сейчас\n"
            "/scan ноутбук — поиск по ключевому слову\n"
            "/help — справка\n\n"
            f"Рассылка каждый день в {DAILY_HOUR:02d}:{DAILY_MINUTE:02d} МСК")

    elif cmd == "/help":
        answer(chat_id,
            "<b>Как пользоваться:</b>\n\n"
            "/scan — найти топ-10 лотов по марже\n"
            "/scan ноутбук — поиск по ключевому слову\n"
            "/scan 5000-50000 — поиск по цене\n\n"
            "<b>Что ищу:</b>\n"
            "💻 Электроника (ноутбуки, серверы, мониторы)\n"
            "🚗 Авто и спецтехника\n"
            "🏭 Промышленное оборудование\n"
            "🏠 Бытовая техника\n"
            "🔧 Инструменты\n\n"
            "Бот сканирует 1000+ лотов и фильтрует\n"
            "по маржинальности. Ежедневная рассылка — в утро.")

    elif cmd == "/scan":
        keyword = " ".join(args) if args else None
        send_message(chat_id, "Сканирую торги... 20-40 секунд.")
        try:
            lots = fetch_torgi_lots()

            # Фильтр по ключевому слову если указано
            if keyword:
                kw_lower = keyword.lower()
                if "-" in keyword and all(p.replace(" ","").isdigit() for p in keyword.split("-")):
                    # Фильтр по цене: 5000-50000
                    parts = keyword.replace(" ","").split("-")
                    lo, hi = float(parts[0]), float(parts[1])
                    lots = [l for l in lots if lo <= l["price"] <= hi]
                else:
                    lots = [l for l in lots
                            if kw_lower in (l.get("title","") + l.get("description","") + l.get("attributes","")).lower()]

            analyzed = analyze_lots(lots)
            if keyword and "-" not in keyword:
                msg = f"Результаты поиска «{keyword}»:\n\n"
            else:
                msg = ""
            msg += fmt_digest(analyzed, 10)
            send_message(chat_id, msg)
            log.info(f"Scan done: {len(analyzed)} analyzed from {len(lots)} total (keyword={keyword})")
        except Exception as e:
            log.error(f"Scan error: {e}", exc_info=True)
            answer(chat_id, "Ошибка сканирования. Попробуйте позже.")

    else:
        answer(chat_id, "Неизвестная команда. /help")

# === ЕЖЕДНЕВНАЯ РАССЫЛКА ===

def do_daily_digest():
    log.info("Daily digest started")
    for cid in load_chat_ids():
        try:
            lots = fetch_torgi_lots()
            analyzed = analyze_lots(lots)
            if analyzed:
                send_message(cid, "Утренний дайджест торгов:")
                send_message(cid, fmt_digest(analyzed, 10))
            else:
                answer(cid, "Сегодня подходящих лотов нет.")
        except Exception as e:
            log.error(f"Daily digest error: {e}", exc_info=True)

def daily_scheduler():
    tz = ZoneInfo(TIMEZONE)
    last = None
    while True:
        try:
            now = datetime.now(tz)
            key = now.strftime("%Y-%m-%d")
            if now.hour == DAILY_HOUR and now.minute == DAILY_MINUTE and last != key:
                do_daily_digest()
                last = key
        except Exception as e:
            log.error(f"Scheduler error: {e}")
        time.sleep(30)

# === FLASK ===

app = Flask(__name__)

@app.route("/", methods=["GET"])
def index():
    return "Bankrot bot is running!", 200

@app.route("/health", methods=["GET"])
def health():
    return "OK", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = flask_request.get_json()
        if not data: return "OK", 200
        message = data.get("message")
        if not message: return "OK", 200
        chat_id = message["chat"]["id"]
        text = message.get("text", "")
        user = message.get("from", {})
        save_chat_id(chat_id)
        if text.startswith("/"):
            threading.Thread(target=handle_command, args=(chat_id, text, user), daemon=True).start()
    except Exception as e:
        log.error(f"Webhook error: {e}", exc_info=True)
    return "OK", 200

# === MAIN ===

def main():
    log.info("Starting bankrot bot...")
    if not BOT_TOKEN:
        log.error("BOT_TOKEN not set!")
        return

    if RENDER_EXTERNAL_URL:
        webhook_url = f"{RENDER_EXTERNAL_URL}/webhook"
        result = api_call("setWebhook", url=webhook_url)
        if result.get("ok"):
            log.info(f"Webhook set: {webhook_url}")
        else:
            log.error(f"Webhook failed: {result}")

    api_call("setMyCommands", commands=[
        {"command": "scan", "description": "Поиск лотов на торгах"},
        {"command": "help", "description": "Справка"},
    ])

    threading.Thread(target=daily_scheduler, daemon=True).start()
    log.info(f"Daily digest at {DAILY_HOUR:02d}:{DAILY_MINUTE:02d} ({TIMEZONE})")

    log.info(f"Server on port {PORT}...")
    app.run(host="0.0.0.0", port=PORT, debug=False)

if __name__ == "__main__":
    main()
