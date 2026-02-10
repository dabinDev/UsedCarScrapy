import json

d = json.load(open('client_output/details.json', 'r', encoding='utf-8'))
items = d['data'][:5]
for x in items:
    print(f"{x['sku_id']}: sh={x.get('sh_price')}, off={x.get('official_price')}, source={x.get('price_source','?')}")
