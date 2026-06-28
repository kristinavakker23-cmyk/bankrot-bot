"""
Bankrot Bot — ищет лоты на банкротских торгах (lot-online.ru / РАД).
Сравнивает с рыночными ценами (drom.ru, Bing).
Версия для Render.com (webhook mode).
"""
import os, re, sys, time, json, logging, requests, threading
from datetime import datetime
from zoneinfo import ZoneInfo
from flask import Flask, request as flask_request
from bs4 import BeautifulSoup
from market_price import search_market_prices, calculate_margin
from llm_analyzer import llm_analyze_lot, llm_compare_lots, is_available as llm_available

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHAT_ID = os.getenv("CHAT_ID", "")
TIMEZONE = os.getenv("TIMEZONE", "Europe/Moscow")
DAILY_HOUR = int(os.getenv("DAILY_HOUR", "9"))
DAILY_MINUTE = int(os.getenv("DAILY_MINUTE", "0"))
PORT = int(os.getenv("PORT", "10000"))
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL", "")
API = f"https://api.telegram.org/bot{BOT_TOKEN}"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                    handlers=[logging.StreamHandler(sys.stdout)])
log = logging.getLogger("bankrot")

# ─── Telegram ──────────────────────────────────────────

def api_call(method, **kwargs):
    try:
        r = requests.post(f"{API}/{method}", json=kwargs, timeout=30)
        return r.json()
    except Exception as e:
        log.error(f"API {method}: {e}")
        return {"ok": False}

def send_message(cid, text, parse_mode="HTML"):
    if len(text) > 4000:
        parts, t = [], text
        while t:
            if len(t) <= 4000:
                parts.append(t); break
            cut = t[:4000].rfind("\n\n")
            if cut < 0: cut = t[:4000].rfind("\n")
            if cut < 0: cut = 4000
            parts.append(t[:cut]); t = t[cut:]
        for p in parts:
            api_call("sendMessage", chat_id=cid, text=p, parse_mode=parse_mode,
                     disable_web_page_preview=True)
    else:
        api_call("sendMessage", chat_id=cid, text=text, parse_mode=parse_mode,
                 disable_web_page_preview=True)

def answer(cid, text):
    send_message(cid, text)

# ─── Категории и маржа ─────────────────────────────────
# lot-online.ru category_id -> (название, ожидаемая маржа%)

RAD_CATEGORIES = {
    # Транспорт
    44: ("🚗 Легковые автомобили", 40),
    45: ("🚛 Грузовики/спецтехника", 55),
    48: ("📦 Прицепы", 45),
    49: ("⛵ Водный транспорт", 50),
    51: ("🚂 ЖД транспорт", 60),
    53: ("🚐 Иной транспорт", 45),
    165: ("🏍 Мототехника", 55),
    61: ("🔧 Автозапчасти", 60),
    # Оборудование
    55: ("🏦 Банковское оборудование", 60),
    167: ("📡 Сетевое оборудование", 70),
    57: ("🏭 Производственное оборудование", 80),
    58: ("⚙️ Иное оборудование", 65),
    60: ("💻 Бытовая/компьютерная техника", 70),
    # Недвижимость
    22: ("🏢 Здания", 50),
    23: ("🏪 Нежилые помещения", 45),
    25: ("🏗 Производственные объекты", 55),
    26: ("🅿️ Паркинги/гаражи", 40),
    34: ("🏠 Квартиры", 35),
    38: ("🏡 Дома/коттеджи", 40),
    # Прочее
    64: ("🔩 Металлолом", 35),
    70: ("📦 Иное имущество", 50),
    62: ("🪙 Монеты", 60),
    63: ("🪑 Мебель", 45),
}

# Ключевые слова для доп. фильтрации (приоритет, маржа)
KW_MARGINS = {
    "ноутбук": (1, 80), "ноутбуки": (1, 80), "смартфон": (1, 60),
    "телефон": (1, 50), "сервер": (1, 90), "компьютер": (1, 70),
    "монитор": (1, 60), "принтер": (2, 40), "роутер": (2, 50),
    "станок": (1, 100), "генератор": (1, 80), "компрессор": (2, 70),
    "холодильник": (1, 60), "стиральная": (1, 50), "кондиционер": (1, 70),
    "велосипед": (1, 60), "тренажёр": (1, 60), "инструмент": (1, 70),
    "автомобиль": (1, 40), "грузовик": (1, 50), "экскаватор": (1, 60),
    "погрузчик": (1, 60), "трактор": (1, 50), "кран": (1, 55),
}

# ─── Парсинг lot-online.ru ──────────────────────────────

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
           "Accept": "text/html"}

def fetch_rad_lots(max_pages=5):
    """Парсим каталог lot-online.ru по категориям."""
    all_lots = []
    for cat_id, (cat_name, cat_margin) in RAD_CATEGORIES.items():
        try:
            url = f"https://catalog.lot-online.ru/index.php?dispatch=categories.view&category_id={cat_id}"
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, "lxml")
            lots = _parse_catalog_page(soup, cat_id, cat_name, cat_margin)
            all_lots.extend(lots)
            log.info(f"  {cat_name}: {len(lots)} лотов")
        except Exception as e:
            log.error(f"  {cat_name}: {e}")
    log.info(f"Всего с RAD: {len(all_lots)} лотов")
    return all_lots


def _parse_catalog_page(soup, cat_id, cat_name, cat_margin):
    """Парсим страницу каталога lot-online.ru."""
    lots = []
    # Основные карточки лотов
    cards = soup.select(".ty-grid-list__item")
    if not cards:
        cards = soup.select(".ty-compact-list__item")

    for card in cards:
        # Название — ссылка с product_id и текстом
        title = ""
        url = ""
        for a in card.find_all("a", href=True):
            href = a.get("href", "")
            if "products.view" in href and "product_id" in href:
                text = a.get_text(strip=True)
                if text and len(text) > len(title):
                    title = text
                    pid_m = re.search(r"product_id=(\d+)", href)
                    if pid_m:
                        url = f"https://catalog.lot-online.ru/index.php?dispatch=products.view&product_id={pid_m.group(1)}"

        if not title or len(title) < 5:
            continue

        # Цена — .ty-price или ищем число с ₽
        price = 0
        price_el = card.select_one(".ty-price")
        if price_el:
            price_text = price_el.get_text(strip=True)
            price_num = re.sub(r"[^\d]", "", price_text)
            if price_num:
                price = float(price_num)
        if price <= 0:
            # Фоллбэк: ищем любое число > 999
            for txt in card.find_all(string=re.compile(r"\d{4,}")):
                clean = re.sub(r"[^\d]", "", txt)
                if clean and int(clean) > 999:
                    price = float(clean)
                    break

        if price <= 0:
            continue

        # Дата окончания
        date_end = ""
        card_text = card.get_text()
        days_match = re.search(r"Торги через (\d+) дн", card_text)
        if days_match:
            date_end = f"через {days_match.group(1)} дн."

        lots.append({
            "title": title[:120],
            "price": price,
            "url": url,
            "cat_id": cat_id,
            "cat_name": cat_name,
            "cat_margin": cat_margin,
            "date_end": date_end,
            "source": "lot-online.ru (РАД)",
            "description": "",
        })

    return lots


def fetch_rad_by_keyword(keyword):
    """Поиск по ключевому слову на lot-online.ru."""
    lots = []
    try:
        url = f"https://catalog.lot-online.ru/index.php?dispatch=categories.view&category_id=9876&q={keyword}"
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, "lxml")
            lots = _parse_catalog_page(soup, 0, f"Поиск: {keyword}", 50)
    except Exception as e:
        log.error(f"RAD search '{keyword}': {e}")
    return lots

# ─── Анализ ────────────────────────────────────────────

def analyze(lots, keyword=None):
    result = []
    for lot in lots:
        title = (lot.get("title", "") or "").lower()
        text = title

        # Маржа из категории
        base_margin = lot.get("cat_margin", 40)

        # Доп. маржа по ключевым словам
        kw_margin = 0
        kw_found = ""
        for kw, (p, m) in KW_MARGINS.items():
            if kw in text:
                if m > kw_margin:
                    kw_margin = m
                    kw_found = kw

        margin = max(base_margin, kw_margin)
        lot["margin"] = margin
        lot["keywords"] = kw_found or lot.get("cat_name", "")

        # Скор
        price = lot.get("price", 0)
        pb = 1.3 if price <= 50000 else (1.1 if price <= 500000 else 0.8)
        lot["score"] = margin * pb

        result.append(lot)

    result.sort(key=lambda x: x["score"], reverse=True)
    return result

# ─── Форматирование ───────────────────────────────────

def fmt_lot(lot, i):
    p = lot.get("price", 0)
    m = lot.get("margin", 0)
    sell = int(p * (1 + m / 100))
    profit = sell - p
    title = lot.get("title", "?")
    if len(title) > 70: title = title[:67] + "..."
    url = lot.get("url", "")
    cat = lot.get("cat_name", "")
    end = lot.get("date_end", "")

    msg = (
        f"<b>{i}. {title}</b>\n"
        f"Цена на торгах: <b>{p:,.0f} руб.</b>\n"
    )

    # Если есть анализ рынка — показываем
    ma = lot.get("market_analysis")
    if ma and ma.get("status") != "no_data":
        msg += (
            f"Рыночная цена: <b>{ma['avg_market']:,} руб.</b>\n"
            f"{ma['emoji']} Маржа: <b>{ma['margin_pct']}%</b>\n"
            f"Рекомендация: {ma['recommendation']}\n"
            f"Продать за: <b>{ma['optimal_sell']:,} руб.</b>\n"
            f"Прибыль: ~<b>{ma['profit_optimal']:,} руб.</b>\n"
            f"Срок продажи: {ma['time_estimate']}\n"
        )
        if ma.get("sources"):
            srcs = ", ".join(ma["sources"].keys())
            msg += f"Источники цен: {srcs}\n"
        msg += f"Найдено цен на рынке: {ma['total_prices']}\n"
    else:
        msg += (
            f"Ожидаемая маржа: <b>{m}%</b>\n"
            f"Продать за: ~<b>{sell:,.0f} руб.</b>\n"
            f"Прибыль: ~<b>{profit:,.0f} руб.</b>\n"
        )

    if cat: msg += f"Категория: {cat}\n"
    if end: msg += f"Окончание: {end}\n"
    msg += "Источник: lot-online.ru (РАД)\n"
    if url: msg += f'<a href="{url}">Перейти к лоту</a>\n'
    return msg


def fmt_lot_full(lot, i):
    """Полный отчёт по лоту с анализом рынка."""
    p = lot.get("price", 0)
    title = lot.get("title", "?")
    url = lot.get("url", "")
    cat = lot.get("cat_name", "")
    end = lot.get("date_end", "")

    msg = f"<b>📊 АНАЛИЗ ЛОТА #{i}</b>\n"
    msg += f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    msg += f"<b>{title}</b>\n\n"

    msg += f"<b>🏦 Цена на торгах:</b> {p:,.0f} руб.\n"

    ma = lot.get("market_analysis")
    if ma and ma.get("status") != "no_data":
        msg += f"<b>🏪 Рыночная цена:</b> {ma['avg_market']:,} руб.\n"
        msg += f"  Минимум: {ma['min_market']:,} руб.\n"
        msg += f"  Максимум: {ma['max_market']:,} руб.\n" if ma.get('max_market') else ""
        msg += f"\n{ma['emoji']} <b>МАРЖА: {ma['margin_pct']}%</b>\n"
        msg += f"{ma['recommendation']}\n\n"

        msg += f"<b>💰 РЕКОМЕНДАЦИЯ ПО ПРОДАЖЕ:</b>\n"
        msg += f"  Быстрая продажа: {ma['quick_sell']:,} руб. (прибыль {ma['profit_quick']:,})\n"
        msg += f"  Оптимальная цена: {ma['optimal_sell']:,} руб. (прибыль {ma['profit_optimal']:,})\n"
        msg += f"  Максимальная цена: {ma['max_sell']:,} руб.\n\n"

        msg += f"  ⏱ Срок продажи: {ma['time_estimate']}\n"
        msg += f"  💸 Налог 13%: ~{ma.get('tax', 0):,} руб.\n"
        msg += f"  📈 Чистая прибыль: ~{ma.get('profit_net', 0):,} руб.\n"

        if ma.get("sources"):
            msg += f"\n<b>📍 Источники цен:</b>\n"
            for src, info in ma["sources"].items():
                note = info.get("note", "")
                msg += f"  • {src}: {info['count']} цен, средняя {info['avg']:,} руб."
                if note:
                    msg += f" ({note})"
                msg += "\n"
    else:
        msg += f"⚠️ Нет данных о рыночных ценах\n"
        m = lot.get("margin", 0)
        sell = int(p * (1 + m / 100))
        profit = sell - p
        msg += f"Ожидаемая маржа: {m}%\n"
        msg += f"Продать за: ~{sell:,} руб.\n"
        msg += f"Прибыль: ~{profit:,} руб.\n"

    if cat: msg += f"\nКатегория: {cat}"
    if end: msg += f"\nОкончание: {end}"
    msg += f"\nИсточник: lot-online.ru (РАД)\n"
    if url: msg += f'<a href="{url}">Перейти к лоту</a>\n'
    return msg


def fmt_digest(lots, n=10):
    if not lots:
        return "<b>Торги — дайджест</b>\n\nСегодня подходящих лотов нет."
    lines = ["<b>ТОП лотов на сегодня</b>\n━━━━━━━━━━━━━━━━━━━━━\n"]
    for i, lot in enumerate(lots[:n], 1):
        lines.append(fmt_lot(lot, i))
        lines.append("───────────────────")
    avg = sum(l.get("margin", 0) for l in lots) / len(lots)
    best = max(lots, key=lambda x: x.get("margin", 0))

    # Считаем статистику по рыночным ценам
    analyzed_count = sum(1 for l in lots if l.get("market_analysis", {}).get("status") not in (None, "no_data"))
    profitable = sum(1 for l in lots if l.get("market_analysis", {}).get("margin_pct", 0) > 15)

    lines.append(f"\nВсего: {len(lots)} лотов | Средняя маржа: {avg:.0f}%")
    lines.append(f"Проанализировано: {analyzed_count}/{len(lots)} | Выгодных (>15%): {profitable}")
    lines.append(f"Лучший: {best['title'][:40]}... | Маржа: {best['margin']}%")
    lines.append(f"\n💡 /analyze [номер] — подробный анализ лота")
    return "\n".join(lines)

# ─── Chat IDs ──────────────────────────────────────────

def load_chat_ids():
    ids = set()
    if CHAT_ID: ids.add(int(CHAT_ID))
    try:
        with open("chat_ids.txt") as f:
            for line in f:
                l = line.strip()
                if l: ids.add(int(l))
    except FileNotFoundError: pass
    return ids

def save_chat_id(cid):
    ids = load_chat_ids()
    if cid not in ids:
        with open("chat_ids.txt", "a") as f:
            f.write(f"{cid}\n")

# ─── Команды ───────────────────────────────────────────

def handle_command(cid, text, user):
    cmd = text.split()[0].lower() if text else ""
    args = text.split()[1:] if text else []
    log.info(f"Command {cmd} from chat={cid}")

    if cmd == "/start":
        answer(cid,
            "<b>Бот банкротских торгов (РАД)</b>\n\n"
            "Сканирую catalog.lot-online.ru — ЭТП РАД.\n"
            "Нахожу лоты с высокой маржинальностью.\n"
            "Сравниваю с рыночными ценами (drom.ru, Bing).\n"
            "🤖 AI-анализ через Gemma (OpenRouter).\n\n"
            "<b>Команды:</b>\n"
            "/scan — поиск лотов с анализом цен\n"
            "/scan авто — поиск по ключевому слову\n"
            "/analyze 3 — подробный анализ лота #3 + AI\n"
            "/categories — список категорий\n"
            "/help — справка\n\n"
            f"Рассылка: {DAILY_HOUR:02d}:{DAILY_MINUTE:02d} МСК")

    elif cmd == "/help":
        llm_status = "✅ Включён" if llm_available() else "❌ Не настроен"
        answer(cid,
            "<b>Как пользоваться:</b>\n\n"
            "/scan — топ-10 лотов с анализом рынка\n"
            "/scan ноутбук — поиск по слову\n"
            "/scan авто — поиск авто\n"
            "/analyze 3 — подробный анализ лота #3 + AI\n\n"
            "<b>Анализ включает:</b>\n"
            "• Рыночные цены (drom.ru для авто, Bing)\n"
            "• Расчёт маржи и прибыли\n"
            "• Рекомендацию по цене продажи\n"
            "• Оценку срока продажи\n"
            "• <b>AI-анализ лотов (Gemma via OpenRouter)</b>\n\n"
            f"<b>AI-анализатор:</b> {llm_status}\n\n"
            "<b>Категории:</b>\n"
            "🚗 Авто (919 лотов)\n"
            "🚛 Грузовики/спецтехника (230)\n"
            "💻 Компьютерная техника (19)\n"
            "🏭 Производственное оборудование (89)\n"
            "📡 Сетевое оборудование (88)\n"
            "🏠 Квартиры (329)\n"
            "🏢 Нежилые помещения (831)\n\n"
            "Маржа считается автоматически по рыночным ценам.")

    elif cmd == "/categories":
        lines = ["<b>Категории на РАД:</b>\n"]
        for cid_, (name, margin) in sorted(RAD_CATEGORIES.items()):
            lines.append(f"  {name} — маржа ~{margin}%")
        answer(cid, "\n".join(lines))

    elif cmd == "/scan":
        keyword = " ".join(args) if args else None
        send_message(cid, "Сканирую РАД (lot-online.ru) + анализ рыночных цен... 1-2 минуты.")
        try:
            if keyword:
                lots = fetch_rad_by_keyword(keyword)
            else:
                lots = fetch_rad_lots()
            analyzed = analyze(lots, keyword)

            # Анализируем рыночные цены для топ-5 лотов
            total_lots = len(analyzed)
            for i, lot in enumerate(analyzed[:5], 1):
                send_message(cid, f"🔍 Анализ ({i}/5): {lot['title'][:50]}...")
                try:
                    market = search_market_prices(lot["title"])
                    if market:
                        margin = calculate_margin(lot["price"], market)
                        lot["market_analysis"] = margin
                        log.info(f"Market: {lot['title'][:40]} -> {margin['margin_pct']}%")
                except Exception as e:
                    log.error(f"Market analysis error: {e}")

            msg = ""
            if keyword:
                msg = f"Результаты: «{keyword}»\n\n"
            msg += fmt_digest(analyzed, 10)
            send_message(cid, msg)
            # Сохраняем для /analyze
            handle_command._last_lots = analyzed

            # AI-сравнение топ-3 лотов
            if llm_available() and len(analyzed) >= 2:
                send_message(cid, "🤖 AI-сравнение топ-3 лотов...")
                lots_for_compare = ""
                for i, lot in enumerate(analyzed[:3], 1):
                    lots_for_compare += (
                        f"{i}. {lot['title']} | Цена: {lot['price']:,.0f} руб. | "
                        f"Категория: {lot.get('cat_name', '?')}\n"
                    )
                    ma = lot.get("market_analysis")
                    if ma and ma.get("status") != "no_data":
                        lots_for_compare += f"   Рыночная: {ma.get('avg_market', '?')} руб. | Маржа: {ma.get('margin_pct', '?')}%\n"

                comparison = llm_compare_lots(lots_for_compare)
                if comparison:
                    send_message(cid, f"<b>🤖 AI-СРАВНЕНИЕ:</b>\n\n{comparison}")

            log.info(f"Scan: {total_lots} lots, analyzed top 5")
        except Exception as e:
            log.error(f"Scan error: {e}", exc_info=True)
            answer(cid, "Ошибка сканирования.")

    elif cmd == "/analyze":
        if not args:
            answer(cid, "Использование: /analyze 3 (номер лота из последнего /scan)")
            return
        try:
            lot_num = int(args[0])
        except ValueError:
            answer(cid, "Номер лота должен быть числом.")
            return

        # Сохраняем лоты для команды analyze
        if not hasattr(handle_command, '_last_lots'):
            answer(cid, "Сначала выполните /scan для поиска лотов.")
            return

        lots = handle_command._last_lots
        if lot_num < 1 or lot_num > len(lots):
            answer(cid, f"Лот #{lot_num} не найден. Доступно: 1-{len(lots)}")
            return

        lot = lots[lot_num - 1]
        send_message(cid, f"🔍 Анализирую лот #{lot_num}: {lot['title'][:50]}...")

        try:
            market = search_market_prices(lot["title"])
            if market:
                margin = calculate_margin(lot["price"], market)
                lot["market_analysis"] = margin
            else:
                lot["market_analysis"] = {"status": "no_data", "emoji": "❓",
                                          "recommendation": "Нет данных"}
        except Exception as e:
            log.error(f"Market analysis error: {e}")
            lot["market_analysis"] = {"status": "error", "emoji": "❌",
                                      "recommendation": f"Ошибка: {e}"}

        # Формируем рыночные данные для LLM
        market_data = ""
        ma = lot.get("market_analysis")
        if ma and ma.get("status") != "no_data":
            market_data = (
                f"Рыночная цена: {ma.get('avg_market', 'нет данных')} руб.\n"
                f"Мин: {ma.get('min_market', '?')} руб., Макс: {ma.get('max_market', '?')} руб.\n"
                f"Маржа по рынку: {ma.get('margin_pct', '?')}%\n"
                f"Источники: {', '.join(ma.get('sources', {}).keys()) if ma.get('sources') else 'Bing/Drom'}"
            )

        msg = fmt_lot_full(lot, lot_num)
        send_message(cid, msg)

        # LLM-анализ
        if llm_available():
            send_message(cid, "🤖 Запрашиваю AI-анализ у LLM...")
            llm_result = llm_analyze_lot(
                title=lot["title"],
                price=lot["price"],
                market_data=market_data,
                category=lot.get("cat_name", ""),
            )
            if llm_result:
                send_message(cid, f"<b>🤖 AI-АНАЛИЗ (Gemma):</b>\n\n{llm_result}")
            else:
                send_message(cid, "⚠️ LLM временно недоступен. Попробуйте позже.")
        else:
            send_message(cid, "ℹ️ LLM не настроен. Добавь OPENROUTER_API_KEY в .env")

        log.info(f"Analyze lot #{lot_num}: {lot['title'][:40]}")

    else:
        answer(cid, "Неизвестная команда. /help")

# ─── Daily ─────────────────────────────────────────────

def do_daily():
    log.info("Daily digest started")
    for cid in load_chat_ids():
        try:
            lots = fetch_rad_lots()
            analyzed = analyze(lots)
            if analyzed:
                send_message(cid, "Утренний дайджест торгов:")
                send_message(cid, fmt_digest(analyzed, 10))
            else:
                answer(cid, "Сегодня подходящих лотов нет.")
        except Exception as e:
            log.error(f"Daily error: {e}", exc_info=True)

def scheduler():
    tz = ZoneInfo(TIMEZONE)
    last = None
    while True:
        try:
            now = datetime.now(tz)
            key = now.strftime("%Y-%m-%d")
            if now.hour == DAILY_HOUR and now.minute == DAILY_MINUTE and last != key:
                do_daily()
                last = key
        except Exception as e:
            log.error(f"Scheduler: {e}")
        time.sleep(30)

# ─── Flask ─────────────────────────────────────────────

app = Flask(__name__)

@app.route("/")
def index():
    return "Bankrot bot is running!", 200

@app.route("/health")
def health():
    return "OK", 200

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = flask_request.get_json()
        if not data: return "OK", 200
        msg = data.get("message")
        if not msg: return "OK", 200
        save_chat_id(msg["chat"]["id"])
        text = msg.get("text", "")
        if text.startswith("/"):
            threading.Thread(target=handle_command,
                           args=(msg["chat"]["id"], text, msg.get("from", {})),
                           daemon=True).start()
    except Exception as e:
        log.error(f"Webhook: {e}", exc_info=True)
    return "OK", 200

# ─── Main ──────────────────────────────────────────────

def main():
    log.info("Starting bankrot bot (lot-online.ru / RAD)...")
    if not BOT_TOKEN:
        log.error("BOT_TOKEN not set!"); return

    if RENDER_EXTERNAL_URL:
        r = api_call("setWebhook", url=f"{RENDER_EXTERNAL_URL}/webhook")
        log.info(f"Webhook: {r}")

    api_call("setMyCommands", commands=[
        {"command": "scan", "description": "Поиск лотов на торгах"},
        {"command": "analyze", "description": "Подробный AI-анализ лота"},
        {"command": "categories", "description": "Список категорий"},
        {"command": "help", "description": "Справка"},
    ])

    threading.Thread(target=scheduler, daemon=True).start()
    log.info(f"Daily at {DAILY_HOUR:02d}:{DAILY_MINUTE:02d} ({TIMEZONE})")

    log.info(f"Server on {PORT}...")
    app.run(host="0.0.0.0", port=PORT, debug=False)

if __name__ == "__main__":
    main()
