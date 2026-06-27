import requests, json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

H = {'Accept': 'application/json', 'User-Agent': 'Mozilla/5.0'}
r = requests.get('https://torgi.gov.ru/new/api/public/lotcards/search?limit=50&offset=0', headers=H, timeout=20)
data = r.json()
lots = data.get('content', [])
total = data.get('totalElements', '?')
print(f'Total: {total}, Got: {len(lots)}')
print()

# Все уникальные категории
cats = set()
statuses = set()
for lot in lots:
    cat = lot.get('category', {})
    if isinstance(cat, dict):
        cats.add(cat.get('name', '?'))
    statuses.add(lot.get('lotStatus', '?'))

print('=== КАТЕГОРИИ ===')
for c in sorted(cats):
    print(f'  {c}')
print()
print('=== СТАТУСЫ ===')
for s in sorted(statuses):
    print(f'  {s}')
print()

# Первые 30 лотов
for i, lot in enumerate(lots[:30], 1):
    title = lot.get('lotName', '?')[:70]
    price = lot.get('priceMin', 0)
    cat = lot.get('category', {})
    cat_name = cat.get('name', '?') if isinstance(cat, dict) else '?'
    status = lot.get('lotStatus', '?')
    print(f'{i}. {title}')
    print(f'   {price} руб. | {cat_name} | {status}')
