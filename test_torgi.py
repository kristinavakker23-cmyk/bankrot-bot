"""Изучаем структуру данных torgi.gov.ru"""
import requests, json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
     "Accept": "application/json"}

# Берём 20 лотов без фильтров, чтобы изучить структуру
r = requests.get("https://torgi.gov.ru/new/api/public/lotcards/search?limit=20&offset=0",
                 headers=H, timeout=15)
data = r.json()
lots = data.get("content", [])
print(f"Total: {data.get('totalElements', '?')}")
print(f"Got: {len(lots)} lots")
print()

# Смотрим уникальные biddType
bidd_types = set()
lot_statuses = set()
regions = set()
for lot in lots:
    bt = lot.get("biddType", {})
    bidd_types.add(f"{bt.get('code', '?')} -> {bt.get('name', '?')}")
    lot_statuses.add(lot.get("lotStatus", "?"))
    regions.add(lot.get("region", "?"))

print("=== biddType (уникальные) ===")
for bt in sorted(bidd_types):
    print(f"  {bt}")

print("\n=== lotStatus (уникальные) ===")
for s in sorted(lot_statuses):
    print(f"  {s}")

print("\n=== Регионы ===")
for r_ in sorted(regions)[:10]:
    print(f"  {r_}")

# Смотрим полную структуру первого лота
if lots:
    print("\n=== ПОЛНАЯ СТРУКТУРА ПЕРВОГО ЛОТА ===")
    print(json.dumps(lots[0], ensure_ascii=False, indent=2))

# Теперь ищем банкротские торги — ищем biddType с "банкрот" в названии
print("\n\n=== ПОИСК БАНКРОТСКИХ ===")
# Берём больше лотов и фильтруем по biddType.name
for offset in range(0, 200, 20):
    r = requests.get(f"https://torgi.gov.ru/new/api/public/lotcards/search?limit=20&offset={offset}",
                     headers=H, timeout=15)
    data = r.json()
    lots = data.get("content", [])
    for lot in lots:
        bt = lot.get("biddType", {})
        name = bt.get("name", "")
        code = bt.get("code", "")
        if "банкрот" in name.lower() or "bankrupt" in code.lower() or "Банкрот" in name:
            print(f"  FOUND BANKRUPT LOT!")
            print(f"    biddType: {code} -> {name}")
            print(f"    lotStatus: {lot.get('lotStatus')}")
            print(f"    lotName: {lot.get('lotName', '?')[:80]}")
            print(f"    price: {lot.get('startPrice', '?')}")
            print(f"    orgName: {lot.get('orgName', '?')[:50]}")
            print()

print("Done scanning 200 lots")
