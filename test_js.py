"""Глубокий анализ ЕФРСБ JS - ищем backend URL"""
import requests, re, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

r = requests.get("https://bankrot.fedresurs.ru/main.9862903b072b93a30fa7.js", headers=H, timeout=15)
js = r.text

# 1. Ищем /backend
print("=== /backend context ===")
for m in re.finditer(r'.{0,100}backend.{0,100}', js):
    print(f"  ...{m.group()}...")
    print()

# 2. Ищем HttpClient вызовы (Angular)
print("=== Angular HttpClient ===")
for m in re.finditer(r'\.http\.\w+\([^)]*\)', js):
    print(f"  {m.group()[:120]}")

# 3. Ищем environment/environment apiUrl
print("\n=== environment refs ===")
for m in re.finditer(r'environment[^;]{0,200}', js):
    text = m.group()[:200]
    if 'url' in text.lower() or 'api' in text.lower():
        print(f"  {text}")

# 4. Ищем apiUrl прямо
print("\n=== apiUrl ===")
for m in re.finditer(r'[aA]pi[Uu]rl[^;]{0,200}', js):
    print(f"  {m.group()[:200]}")

# 5. Ищем URLs с protocol
print("\n=== Full URLs with https ===")
urls = re.findall(r'https://[a-zA-Z0-9._/-]+', js)
unique = list(set(urls))
for u in sorted(unique)[:30]:
    print(f"  {u}")

# 6. Ищем URL construction patterns
print("\n=== URL construction ===")
for m in re.finditer(r'(?:baseUrl|apiBase|backUri|rootUrl|apiPrefix)[^;]{0,200}', js):
    print(f"  {m.group()[:200]}")

# 7. Ищем sroTradePlaces и tradeplaces - это API endpoints
print("\n=== tradePlaces context ===")
for m in re.finditer(r'.{0,50}tradeplaces.{0,100}', js):
    print(f"  {m.group()[:150]}")
for m in re.finditer(r'.{0,50}tpsros.{0,100}', js):
    print(f"  {m.group()[:150]}")
