"""ЕФРСБ - ищем ВСЕ запросы в JS"""
import requests, re, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

H = {"User-Agent": "Mozilla/5.0"}

r = requests.get("https://bankrot.fedresurs.ru/main.9862903b072b93a30fa7.js", headers=H, timeout=15)
js = r.text

# Ищем все строки похожие на URL paths (начинаются с / или содержат /)
print("=== Все паттерны URL в JS ===")

# Ищем в контексте fetch/get/post
for pattern in [
    r'\.get\("([^"]+)"',
    r'\.post\("([^"]+)"',
    r'\.put\("([^"]+)"',
    r'\.delete\("([^"]+)"',
    r'url:\s*"([^"]+)"',
    r'url:\s*\'([^\']+)\'',
]:
    matches = re.findall(pattern, js)
    if matches:
        unique = list(set(matches))
        print(f"\nPattern {pattern[:30]}:")
        for m in sorted(unique):
            if len(m) > 3:
                print(f"  {m}")

# Ищем backendUrl
print("\n=== backendUrl ===")
for m in re.finditer(r'backendUrl[^}]{0,300}', js):
    print(f"  {m.group()[:200]}")

# Ищем все строки с "url:" перед которыми есть ключевые слова
print("\n=== url: patterns ===")
for m in re.finditer(r'(\w+)\s*:\s*\{[^}]*url:\s*["\']([^"\']+)["\']', js):
    print(f"  {m.group(1)}: {m.group(2)}")

# Ищем paths с / в контексте API
print("\n=== all paths with / ===")
paths = re.findall(r'["\'](/[a-zA-Z][a-zA-Z0-9/._-]{2,50})["\']', js)
unique = sorted(set(paths))
for p in unique:
    if not p.startswith("/assets") and not p.startswith("/polyfill") and not p.startswith("/runtime"):
        print(f"  {p}")
