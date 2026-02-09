"""筛选 dongchedi_brand.json 中 total_pages <= 2 且有数据的品牌"""
import json

data = json.load(open("dongchedi_brand.json", "r", encoding="utf-8"))
# 排除已采集的红旗(brand_id=59)
collected_ids = {59}

brands = [
    b for b in data["data"]
    if b["total_pages"] <= 2
    and b.get("max_total_data", 0) > 0
    and b["brand_id"] not in collected_ids
]
brands.sort(key=lambda x: x["max_total_data"], reverse=True)

total_data = sum(b["max_total_data"] for b in brands)
brand_names = [b["brand_name"] for b in brands]

print(f"共 {len(brands)} 个品牌, 总数据量约 {total_data} 条\n")
for i, b in enumerate(brands, 1):
    print(f"  {i:3d}. {b['brand_name']:12s} ID={b['brand_id']:>5d}  {b['data_range']:>10s}条  {b['total_pages']}页")

print(f"\n品牌名列表（可直接复制到客户端输入）:")
print(",".join(brand_names))
