"""筛选 dongchedi_brand.json 中 total_pages > 2 的品牌（排除红旗）"""
import json

data = json.load(open("dongchedi_brand.json", "r", encoding="utf-8"))
# 排除红旗(59)
excluded_ids = {59}

brands = [
    b for b in data["data"]
    if b["total_pages"] > 2
    and b.get("max_total_data", 0) > 0
    and b["brand_id"] not in excluded_ids
]
brands.sort(key=lambda x: x["max_total_data"], reverse=True)

total_data = sum(b["max_total_data"] for b in brands)
total_pages = sum(b["total_pages"] for b in brands)
brand_names = [b["brand_name"] for b in brands]

print(f"共 {len(brands)} 个品牌, 总数据量约 {total_data:,} 条, 总页数 {total_pages:,} 页\n")

# 按数据级别分组
levels = {}
for b in brands:
    lv = b.get("data_level", "未知")
    levels.setdefault(lv, []).append(b)

for lv in ["超大数据", "海量", "大量", "中等", "少量"]:
    if lv not in levels:
        continue
    group = levels[lv]
    group_data = sum(b["max_total_data"] for b in group)
    print(f"\n{'='*50}")
    print(f"📊 {lv} ({len(group)} 个品牌, ~{group_data:,} 条)")
    print(f"{'='*50}")
    for i, b in enumerate(group, 1):
        print(f"  {i:3d}. {b['brand_name']:12s} ID={b['brand_id']:>5d}  {b['data_range']:>12s}条  {b['total_pages']:>3d}页")

print(f"\n\n品牌名列表（可直接复制到客户端输入）:")
print(",".join(brand_names))
