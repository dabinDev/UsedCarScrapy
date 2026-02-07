#!/usr/bin/env python3
"""
从已保存的 __NEXT_DATA__ 中提取关键数据结构
"""
import json

# ========== 列表页数据 ==========
print("=" * 70)
print("列表页 __NEXT_DATA__ 数据结构分析")
print("=" * 70)

data = json.load(open('test_results/stage2_next_data.json', 'r', encoding='utf-8'))
props = data['props']['pageProps']

# 1. 车系列表
print("\n=== seriesList (车系列表) ===")
sl = props.get('seriesList', [])
print(f"共 {len(sl)} 个车系")
for s in sl[:5]:
    print(json.dumps(s, ensure_ascii=False, indent=2))

# 2. 品牌列表
print("\n=== allBrand (所有品牌) ===")
ab = props.get('allBrand', {})
print(f"allBrand keys: {list(ab.keys())}")
brand_data = ab.get('brand', [])
print(f"brand count: {len(brand_data)}")
if brand_data:
    print(f"first brand type: {type(brand_data[0])}")
    if isinstance(brand_data[0], dict):
        print(f"first brand keys: {list(brand_data[0].keys())[:15]}")
        print(json.dumps(brand_data[0], ensure_ascii=False, indent=2)[:500])
    elif isinstance(brand_data[0], list):
        print(f"first brand is list, len={len(brand_data[0])}")
        if brand_data[0] and isinstance(brand_data[0][0], dict):
            print(f"first item keys: {list(brand_data[0][0].keys())[:15]}")
            print(json.dumps(brand_data[0][0], ensure_ascii=False, indent=2)[:500])

hot_brand = ab.get('hot_brand', [])
print(f"\nhot_brand count: {len(hot_brand)}")
if hot_brand:
    print(json.dumps(hot_brand[0], ensure_ascii=False, indent=2)[:500])

# 3. 车辆列表 (carList)
print("\n=== carList (车辆列表概览) ===")
cl = props.get('carList', {})
print(f"has_more: {cl.get('has_more')}")
print(f"total: {cl.get('total')}")
print(f"fontStyleString length: {len(cl.get('fontStyleString', ''))}")
sku_list = cl.get('search_sh_sku_info_list', [])
print(f"sku count: {len(sku_list)}")

if sku_list:
    first = sku_list[0]
    print(f"\nFirst SKU keys: {list(first.keys())}")
    print(f"\nFirst SKU full dump:")
    print(json.dumps(first, ensure_ascii=False, indent=2)[:2000])

# 4. tabData
print("\n=== tabData ===")
td = props.get('tabData', {})
print(f"tabData keys: {list(td.keys())}")
csl = td.get('car_series_list', [])
print(f"car_series_list count: {len(csl)}")
if csl:
    print(f"first car_series_list item:")
    print(json.dumps(csl[0], ensure_ascii=False, indent=2)[:500])

cbl = td.get('car_brand_list', [])
print(f"car_brand_list count: {len(cbl)}")
if cbl:
    print(f"first car_brand_list item:")
    print(json.dumps(cbl[0], ensure_ascii=False, indent=2)[:500])

# ========== 详情页数据 ==========
print("\n\n" + "=" * 70)
print("详情页 __NEXT_DATA__ 数据结构分析")
print("=" * 70)

data2 = json.load(open('test_results/stage4_next_data.json', 'r', encoding='utf-8'))
sku = data2['props']['pageProps']['skuDetail']

print("\n=== 价格信息 ===")
print(f"  include_tax_price (含税价): {sku.get('include_tax_price')}")
print(f"  offical_price (官方指导价): {sku.get('offical_price')}")
print(f"  sh_price (二手价): {sku.get('sh_price')}")
print(f"  source_sh_price (二手价分): {sku.get('source_sh_price')}")
print(f"  source_offical_price (官方价分): {sku.get('source_offical_price')}")

print("\n=== car_info (基本信息) ===")
print(json.dumps(sku['car_info'], ensure_ascii=False, indent=2))

print("\n=== important_text ===")
print(f"  {sku.get('important_text')}")

print("\n=== important_params ===")
for p in sku.get('important_params', []):
    print(f"  {p['name']}: {p['value']}")

print("\n=== other_params ===")
for p in sku.get('other_params', []):
    print(f"  {p['name']}: {p['value']}")

print("\n=== car_config_overview (车辆配置) ===")
print(json.dumps(sku['car_config_overview'], ensure_ascii=False, indent=2))

print("\n=== head_images (图片) ===")
imgs = sku.get('head_images', [])
print(f"共 {len(imgs)} 张图片")
for i, url in enumerate(imgs):
    print(f"  [{i}] {url[:100]}...")

print("\n=== shop_info (商家信息) ===")
print(json.dumps(sku.get('shop_info', {}), ensure_ascii=False, indent=2))

print("\n=== report (检测报告) ===")
rpt = sku.get('report', {})
print(f"  has_report: {rpt.get('has_report')}")
print(f"  eva_level: {rpt.get('eva_level')}")
overview = rpt.get('overview', [])
if isinstance(overview, dict):
    print(f"  overview keys: {list(overview.keys())[:10]}")
elif isinstance(overview, list):
    print(f"  overview count: {len(overview)}")
    if overview:
        print(f"  overview[0]: {json.dumps(overview[0], ensure_ascii=False)[:200]}")
img_list = rpt.get('image_list') or []
print(f"  image_list count: {len(img_list)}")
if img_list:
    print(f"  first image: {json.dumps(img_list[0], ensure_ascii=False)[:200]}")

print("\n=== high_light_config (亮点配置) ===")
for h in sku.get('high_light_config', []):
    print(f"  {json.dumps(h, ensure_ascii=False)[:150]}")

print("\n=== financial_info (金融信息) ===")
print(json.dumps(sku.get('financial_info', {}), ensure_ascii=False, indent=2))

print("\n=== tags ===")
print(json.dumps(sku.get('tags', []), ensure_ascii=False, indent=2))

print("\n=== title / sku_id ===")
print(f"  title: {sku.get('title')}")
print(f"  sku_id: {sku.get('sku_id')}")
print(f"  spu_id: {sku.get('spu_id')}")

# 保存汇总
summary = {
    "list_page": {
        "seriesList_sample": sl[:2] if sl else [],
        "carList_total": cl.get('total'),
        "carList_has_more": cl.get('has_more'),
        "carList_sku_count": len(sku_list),
        "carList_first_sku": sku_list[0] if sku_list else None,
        "has_fontStyleString": bool(cl.get('fontStyleString')),
    },
    "detail_page": {
        "title": sku.get('title'),
        "sku_id": sku.get('sku_id'),
        "include_tax_price": sku.get('include_tax_price'),
        "offical_price": sku.get('offical_price'),
        "sh_price": sku.get('sh_price'),
        "source_sh_price": sku.get('source_sh_price'),
        "source_offical_price": sku.get('source_offical_price'),
        "car_info": sku.get('car_info'),
        "important_text": sku.get('important_text'),
        "important_params": sku.get('important_params'),
        "other_params": sku.get('other_params'),
        "car_config_overview": sku.get('car_config_overview'),
        "head_images_count": len(sku.get('head_images', [])),
        "head_images": sku.get('head_images', []),
        "shop_info": sku.get('shop_info'),
        "report_has": rpt.get('has_report'),
        "high_light_config": sku.get('high_light_config'),
        "tags": sku.get('tags'),
    }
}

with open('test_results/test_summary.json', 'w', encoding='utf-8') as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)
print(f"\n\n💾 汇总已保存到 test_results/test_summary.json")
