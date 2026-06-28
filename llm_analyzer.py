"""
LLM-анализатор лотов через OpenRouter (бесплатные модели).
Анализирует лоты банкротских торгов, сравнивает с рынком, даёт рекомендации.
"""
import os
import json
import logging
import requests
import time

log = logging.getLogger("llm")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Бесплатные модели (приоритет: качество + скорость + русский язык)
MODELS = [
    "deepseek/deepseek-v4-flash",
    "deepseek/deepseek-chat",
    "deepseek/deepseek-v3.2",
    "nvidia/nemotron-3-nano-30b-a3b:free",
]

SYSTEM_PROMPT = """Ты — аналитик банкротских торгов в России. Отвечай ТОЛЬКО на русском.
НЕ пиши процесс рассуждений. Пиши ТОЛЬКО готовый ответ.
Отвечай 5-10 строками. Без шаблонов и заголовков — просто текст."""


def llm_analyze_lot(title, price, market_data=None, category="", retry=0):
    """
    Анализирует лот через OpenRouter LLM.
    Возвращает текст анализа или None при ошибке.
    """
    if not OPENROUTER_API_KEY:
        log.warning("OPENROUTER_API_KEY not set")
        return None

    # Формируем контекст с рыночными данными
    market_info = ""
    if market_data:
        market_info = f"\nДАННЫЕ РЫНКА:\n{market_data}"
    else:
        market_info = "\nДАННЫЕ РЫНКА: Нет данных с сайтов. Используй общие знания о рынке."

    user_msg = f"""Лот с банкротских торгов:
{title}
Цена на торгах: {price:,.0f} руб.
Категория: {category}
Источник: catalog.lot-online.ru
{market_info}

Оцени рыночную стоимость, рассчитай маржу с учётом налогов и расходов, дай рекомендацию по покупке. Ответь 5-10 строками на русском."""

    model = MODELS[retry] if retry < len(MODELS) else MODELS[0]

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://bankrot-bot.onrender.com",
        "X-Title": "Bankrot Bot",
    }

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        "max_tokens": 600,
        "temperature": 0.3,
    }

    try:
        r = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=90)

        if r.status_code == 200:
            data = r.json()
            text = data["choices"][0]["message"]["content"]
            # Убираем chain-of-thought если модель его показала
            lines = text.split("\n")
            clean_lines = []
            skip = False
            for line in lines:
                lower = line.lower().strip()
                # Пропускаем строки с рассуждениями
                if any(x in lower for x in [
                    "let me", "we need", "we must", "first,", "step 1",
                    "thinking:", "the user", "we should", "actually,",
                    "simplify:", "but need", "assume", "so potential",
                    "we have lot", "but they gave", "so fair market"
                ]):
                    skip = True
                    continue
                if skip and not line.strip():
                    skip = False
                    continue
                if not skip:
                    clean_lines.append(line)
            if clean_lines:
                text = "\n".join(clean_lines)
            return text.strip()

        elif r.status_code == 429:
            # Rate limit — пробуем следующую модель
            retry_after = int(r.headers.get("Retry-After", "12"))
            log.warning(f"Rate limited on {model}, retry after {retry_after}s")
            if retry < len(MODELS) - 1:
                time.sleep(min(retry_after, 15))
                return llm_analyze_lot(title, price, market_data, category, retry + 1)
            return None

        else:
            log.error(f"OpenRouter {r.status_code}: {r.text[:200]}")
            if retry < len(MODELS) - 1:
                return llm_analyze_lot(title, price, market_data, category, retry + 1)
            return None

    except requests.exceptions.Timeout:
        log.warning(f"OpenRouter timeout on {model}")
        if retry < len(MODELS) - 1:
            return llm_analyze_lot(title, price, market_data, category, retry + 1)
        return None
    except Exception as e:
        log.error(f"OpenRouter error: {e}")
        return None


def llm_compare_lots(lots_text):
    """
    Сравнивает несколько лотов через LLM.
    Возвращает текст сравнения.
    """
    if not OPENROUTER_API_KEY:
        return None

    user_msg = f"""Сравни эти лоты банкротских торгов и выбери лучшие для покупки:

{lots_text}

Дай краткое сравнение (максимум 10 строк):
- Какой лот самый выгодный и почему
- Какой лот лучше избегать и почему
- Общая рекомендация"""

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://bankrot-bot.onrender.com",
        "X-Title": "Bankrot Bot",
    }

    payload = {
        "model": MODELS[0],
        "messages": [
            {"role": "system", "content": "Ты аналитик банкротских торгов. Отвечай кратко на русском."},
            {"role": "user", "content": user_msg},
        ],
        "max_tokens": 400,
        "temperature": 0.3,
    }

    try:
        r = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=45)
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        log.error(f"LLM compare error: {e}")

    return None


def is_available():
    """Проверяет доступность OpenRouter API."""
    if not OPENROUTER_API_KEY:
        return False
    try:
        r = requests.get(
            "https://openrouter.ai/api/v1/models",
            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
            timeout=10,
        )
        return r.status_code == 200
    except:
        return False
