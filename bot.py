"""
Bankrot Bot — Telegram-бот для поиска лотов на банкротских торгах.
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
from bs4 import BeautifulSoup

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

# === TELEGRAM API ===

def api_call(method, **kwargs):
    try:
        r = requests.post(f"{API}/{method}", json=kwargs, timeout=30)
        data = r.json()
        if not data.get("ok"):
            log.error(f"API error: {data}")
        return data
    except Exception as e:
        log.error(f"API call {method} failed: {e}")
        return {"ok": False}

def send_message(chat_id, text, parse_mode="HTML"):
    if len(text) > 4000:
        parts = []
        while text:
            if len(text) <= 4000:
                parts.append(text)
                break
            cut = text[:4000].rfind("\n\n")
            if cut == -1:
                cut = text[:4000].rfind("\n")
            if cut == -1:
                cut = 4000
            parts.append(text[:cut])
            text = text[cut:]
        for part in parts:
            api_call("sendMessage", chat_id=chat_id, text=part, parse_mode=parse_mode,
                     disable_web_page_preview=True)
    else:
        api_call("sendMessage", chat_id=chat_id, text=text, parse_mode=parse_mode,
                 disable_web_page_preview=True)

def answer(chat_id, text):
    send_message(chat_id, text)

# === ПРОКСИ ===

def _get_proxy():
    try:
        requests.get("https://httpbin.org/ip", timeout=3)
        return None
    except Exception:
        return {"http": "http://127.0.0.1:10809", "https": "http://127.0.0.1:10809"}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "ru-RU,ru;q=0.9",
}

# === КАТЕГОРИИ (ключевое слово -> приоритет, маржа%) ===

CATEGORIES = {
    "ноутбук": {"p": 1, "m": 80}, "ноутбуки": {"p": 1, "m": 80},
    "смартфон": {"p": 1, "m": 60}, "телефон": {"p": 1, "m": 50},
    "планшет": {"p": 1, "m": 70}, "монитор": {"p": 1, "m": 60},
    "сервер": {"p": 1, "m": 90}, "компьютер": {"p": 1, "m": 70},
    "принтер": {"p": 2, "m": 40}, "роутер": {"p": 2, "m": 50},
    "сетевое": {"p": 2, "m": 60}, "фотоаппарат": {"p": 1, "m": 80},
    "камера": {"p": 1, "m": 70}, "наушники": {"p": 2, "m": 60},
    "автомобиль": {"p": 1, "m": 40}, "грузовик": {"p": 1, "m": 50},
    "экскаватор": {"p": 1, "m": 60}, "погрузчик": {"p": 1, "m": 60},
    "трактор": {"p": 1, "m": 50}, "спецтехника": {"p": 1, "m": 60},
    "станок": {"p": 1, "m": 100}, "конвейер": {"p": 1, "m": 80},
    "холодильная камера": {"p": 1, "m": 90}, "генератор": {"p": 1, "m": 80},
    "сварочный": {"p": 2, "m": 60}, "лазерный": {"p": 2, "m": 80},
    "3d-принтер": {"p": 1, "m": 100}, "фрезерный": {"p": 1, "m": 90},
    "токарный": {"p": 1, "m": 90}, "холодильник": {"p": 1, "m": 60},
    "стиральная": {"p": 1, "m": 50}, "кондиционер": {"p": 1, "m": 70},
    "телевизор": {"p": 1, "m": 50}, "инструмент": {"p": 1, "m": 70},
    "велосипед": {"p": 1, "m": 60}, "тренажёр": {"p": 1, "m": 60},
    "медь": {"p": 2, "m": 40}, "алюминий": {"p": 2, "m": 35},
}

def _category(kw):
    tech = ["ноутбук","ноутбуки","смартфон","телефон","планшет","монитор","сервер","компьютер","принтер","роутер","сетевое","фотоаппарат","камера","наушники"]
    auto = ["автомобиль","грузовик","экскаватор","погрузчик","трактор","спецтехника"]
    ind = ["станок","конвейер","холодильная камера","генератор","сварочный","лазерный","3d-принтер","фрезерный","токарный"]
    home = ["холодильник","стиральная","кондиционер","телевизор"]
    if kw in tech: return "Электроника"
    if kw in auto: return "Авто/Спецтехника"
    if kw in ind: return "Промоборудование"
    if kw in home: return "Бытовая техника"
    return "Прочее"

# === ПАРСИНГ ===

def _parse_price(s):
    try:
        c = s.replace(" ","").replace("\xa0","").replace(",",".")
        c = re.sub(r"[^\d.]", "", c)
        return float(c) if c else 0
    except: return 0

def fetch_efrsb():
    proxy = _get_proxy()
    lots = []
    # API
    now = datetime.now()
    payload = {"offset": 0, "limit": 50, "searchString": "",
               "dateFrom": (now - timedelta(days=3)).strftime("%Y-%m-%d"),
               "dateTo": now.strftime("%Y-%m-%d"),
               "priceFrom": 0, "priceTo": 10000000}
    for url in ["https://bankrot.fedresurs.ru/api/Trade/GetTradesForSearch",
                "https://bankrot.fedresurs.ru/api/Trade/GetTrades"]:
        try:
            r = requests.post(url, json=payload, headers=HEADERS, proxies=proxy, timeout=15)
            if r.status_code == 200:
                data = r.json()
                items = data if isinstance(data, list) else data.get("items", [])
                for item in items[:50]:
                    try:
                        title = item.get("lotName","") or item.get("title","") or item.get("name","")
                        pv = item.get("currentPrice",0) or item.get("startPrice",0) or item.get("price",0)
                        price = float(pv) if isinstance(pv,(int,float)) else _parse_price(str(pv))
                        if not title or price <= 0: continue
                        lid = item.get("id","") or item.get("lotId","")
                        u = f"https://bankrot.fedresurs.ru/TradeLotCard.aspx?id={lid}" if lid else ""
                        lots.append({"source":"ЕФРСБ","title":title,"price":price,
                                     "description":item.get("description",""),"url":u,
                                     "date_end":item.get("tradeEndDate",""),"photos":len(item.get("photos",[]) or [])})
                    except: pass
                if lots:
                    log.info(f"ЕФРСБ API: {len(lots)} лотов")
                    return lots
        except Exception as e:
            log.debug(f"ЕФРСБ API: {e}")
    # HTML
    try:
        r = requests.get("https://bankrot.fedresurs.ru/TradeList.aspx", headers=HEADERS, proxies=proxy, timeout=15)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "lxml")
            for row in soup.select("table tr")[1:]:
                cols = row.find_all("td")
                if len(cols) >= 3:
                    t = cols[0].get_text(strip=True)
                    p = _parse_price(cols[1].get_text(strip=True))
                    a = cols[0].find("a")
                    u = ""
                    if a and a.get("href"):
                        h = a["href"]
                        u = h if h.startswith("http") else f"https://bankrot.fedresurs.ru{h}"
                    if t and p > 0:
                        lots.append({"source":"ЕФРСБ","title":t,"price":p,
                                     "description":cols[2].get_text(strip=True) if len(cols)>2 else "",
                                     "url":u,"date_end":cols[3].get_text(strip=True) if len(cols)>3 else "","photos":0})
            if lots: log.info(f"ЕФРСБ HTML: {len(lots)} лотов")
    except Exception as e:
        log.error(f"ЕФРСБ HTML: {e}")
    return lots

def fetch_lot_online():
    proxy = _get_proxy()
    lots = []
    for url in ["https://api.lot-online.ru/v2/lots?limit=50&sort=new&status=active",
                "https://www.lot-online.ru/api/v2/lots?limit=50"]:
        try:
            r = requests.get(url, headers=HEADERS, proxies=proxy, timeout=15)
            if r.status_code == 200:
                data = r.json()
                items = data if isinstance(data, list) else data.get("lots", data.get("items", data.get("data", [])))
                for item in items[:50]:
                    try:
                        title = item.get("title","") or item.get("name","")
                        price = 0
                        for k in ["current_price","start_price","price","min_price"]:
                            v = item.get(k)
                            if v:
                                price = float(v) if isinstance(v,(int,float)) else _parse_price(str(v))
                                if price > 0: break
                        if not title or price <= 0: continue
                        u = item.get("url","")
                        if not u:
                            lid = item.get("id","")
                            u = f"https://www.lot-online.ru/lot/{lid}" if lid else ""
                        lots.append({"source":"lot-online.ru","title":title,"price":price,
                                     "description":item.get("description",""),"url":u,
                                     "date_end":item.get("end_date",""),"photos":len(item.get("photos",[]) or [])})
                    except: pass
                if lots:
                    log.info(f"lot-online.ru API: {len(lots)} лотов")
                    return lots
        except Exception as e:
            log.debug(f"lot-online.ru API: {e}")
    # HTML
    try:
        r = requests.get("https://www.lot-online.ru/auction/lots?status=active",
                         headers=HEADERS, proxies=proxy, timeout=15)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "lxml")
            links = [a for a in soup.find_all("a", href=True) if "/lot/" in a.get("href","")]
            for a in links[:50]:
                t = a.get_text(strip=True)
                h = a["href"]
                if not h.startswith("http"): h = f"https://www.lot-online.ru{h}"
                if t and len(t) > 3:
                    lots.append({"source":"lot-online.ru","title":t,"price":0,
                                 "description":"","url":h,"date_end":"","photos":0})
            if lots: log.info(f"lot-online.ru HTML: {len(lots)} лотов")
    except Exception as e:
        log.debug(f"lot-online.ru HTML: {e}")
    return lots

# === АНАЛИЗ ===

def analyze(lots):
    result = []
    for lot in lots:
        p = lot.get("price", 0)
        if p < MIN_PRICE or p > MAX_PRICE: continue
        title = (lot.get("title","") or "").lower()
        desc = (lot.get("description","") or "").lower()
        text = f"{title} {desc}"
        best = None
        best_score = 0
        for kw, meta in CATEGORIES.items():
            if kw in text:
                m = meta["m"]
                pr = {1:1.5, 2:1.0, 3:0.7}.get(meta["p"], 1.0)
                tb = 2.0 if kw in title else 1.0
                pb = 1.3 if p <= 5000 else (1.1 if p <= 50000 else 0.8)
                score = m * pr * tb * pb
                if score > best_score:
                    best_score = score
                    best = {"keywords": kw, "margin": m, "category": _category(kw), "score": score}
        if best:
            lot.update(best)
            result.append(lot)
    result.sort(key=lambda x: x["score"], reverse=True)
    return result

def fmt_lot(lot, i):
    p = lot.get("price", 0)
    m = lot.get("margin", 0)
    sell = int(p * (1 + m / 100))
    profit = sell - p
    title = lot.get("title", "?")
    if len(title) > 70: title = title[:67] + "..."
    url = lot.get("url", "")
    msg = (
        f"<b>{i}. {title}</b>\n"
        f"Цена: <b>{p:,.0f} руб.</b>\n"
        f"Маржа: <b>{m}%</b>\n"
        f"Продать за: ~<b>{sell:,.0f} руб.</b>\n"
        f"Прибыль: ~<b>{profit:,.0f} руб.</b>\n"
        f"Категория: {lot.get('category','')}\n"
        f"Источник: {lot.get('source','')}\n"
    )
    if url: msg += f'<a href="{url}">Перейти к лоту</a>\n'
    return msg

def fmt_digest(lots, n=10):
    if not lots:
        return "<b>Банкротские торги</b>\n\nСегодня подходящих лотов нет."
    lines = ["<b>ТОП лотов на сегодня</b>\n━━━━━━━━━━━━━━━━━━━━━\n"]
    for i, lot in enumerate(lots[:n], 1):
        lines.append(fmt_lot(lot, i))
        lines.append("───────────────────")
    avg = sum(l.get("margin",0) for l in lots) / len(lots)
    best = max(lots, key=lambda x: x.get("margin",0))
    lines.append(f"\nВсего: {len(lots)} лотов | Средняя маржа: {avg:.0f}%")
    lines.append(f"Лучший: {best['title'][:40]}... | Маржа: {best['margin']}%")
    return "\n".join(lines)

# === КОМАНДЫ БОТА ===

def handle_command(chat_id, text, user):
    cmd = text.split()[0].lower() if text else ""
    log.info(f"Command {cmd} from chat={chat_id}")

    if cmd == "/start":
        answer(chat_id,
            "<b>Бот банкротских торгов</b>\n\n"
            "Ищу лучшие лоты на аукционах по банкротству\n"
            "и присылаю вам каждый день.\n\n"
            "<b>Команды:</b>\n"
            "/scan — поиск лотов прямо сейчас\n"
            "/help — справка\n\n"
            f"Рассылка каждый день в {DAILY_HOUR:02d}:{DAILY_MINUTE:02d} МСК")

    elif cmd == "/help":
        answer(chat_id,
            "<b>Как пользоваться:</b>\n\n"
            "/scan — найти лоты с высокой маржой\n"
            "Бот сканирует ЕФРСБ и агрегаторы, находит\n"
            "лоты, которые можно перепродать с прибылью.\n\n"
            "Ежедневная рассылка — каждый день в утро.")

    elif cmd == "/scan":
        send_message(chat_id, "Сканирую банкротские торги... 15-30 секунд.")
        try:
            all_lots = []
            try:
                efrsb = fetch_efrsb()
                all_lots.extend(efrsb)
            except Exception as e:
                log.error(f"EFRSB error: {e}")
            try:
                lotol = fetch_lot_online()
                all_lots.extend(lotol)
            except Exception as e:
                log.error(f"lot-online error: {e}")

            analyzed = analyze(all_lots)
            digest = fmt_digest(analyzed, 10)
            send_message(chat_id, digest)
            log.info(f"Scan done: {len(analyzed)} analyzed from {len(all_lots)} total")
        except Exception as e:
            log.error(f"Scan error: {e}", exc_info=True)
            answer(chat_id, "Ошибка сканирования. Попробуйте позже.")

    else:
        answer(chat_id, "Неизвестная команда. /help")

# === ЧАТ ID ===

def load_chat_ids():
    ids = set()
    if CHAT_ID:
        ids.add(int(CHAT_ID))
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

# === ЕЖЕДНЕВНАЯ РАССЫЛКА ===

def do_daily_bankrot():
    log.info("Daily bankrot digest started")
    for cid in load_chat_ids():
        try:
            all_lots = []
            try: all_lots.extend(fetch_efrsb())
            except: pass
            try: all_lots.extend(fetch_lot_online())
            except: pass
            analyzed = analyze(all_lots)
            if analyzed:
                send_message(cid, "Банкротские торги — утренний дайджест:")
                send_message(cid, fmt_digest(analyzed, 10))
            else:
                answer(cid, "Банкротские торги: сегодня подходящих лотов нет.")
        except Exception as e:
            log.error(f"Daily bankrot error: {e}", exc_info=True)

def daily_scheduler():
    tz = ZoneInfo(TIMEZONE)
    last = None
    while True:
        try:
            now = datetime.now(tz)
            key = now.strftime("%Y-%m-%d")
            if now.hour == DAILY_HOUR and now.minute == DAILY_MINUTE and last != key:
                do_daily_bankrot()
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

    # Webhook
    if RENDER_EXTERNAL_URL:
        webhook_url = f"{RENDER_EXTERNAL_URL}/webhook"
        result = api_call("setWebhook", url=webhook_url)
        if result.get("ok"):
            log.info(f"Webhook set: {webhook_url}")
        else:
            log.error(f"Webhook failed: {result}")

    # Menu
    api_call("setMyCommands", commands=[
        {"command": "scan", "description": "Поиск лотов на банкротских торгах"},
        {"command": "help", "description": "Справка"},
    ])

    # Scheduler
    threading.Thread(target=daily_scheduler, daemon=True).start()
    log.info(f"Daily digest at {DAILY_HOUR:02d}:{DAILY_MINUTE:02d} ({TIMEZONE})")

    # Flask
    log.info(f"Server on port {PORT}...")
    app.run(host="0.0.0.0", port=PORT, debug=False)

if __name__ == "__main__":
    main()
