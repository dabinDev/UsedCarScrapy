"""按数据量均衡拆分为3组"""
import json

data = json.load(open("dongchedi_brand.json", "r", encoding="utf-8"))
names = "保时捷,日产,路虎,吉利汽车,福特,特斯拉,广汽传祺,现代,长安,雷克萨斯,哈弗,马自达,沃尔沃,凯迪拉克,MINI,五菱汽车,小鹏汽车,理想汽车,雪佛兰,领克,奇瑞,起亚,坦克,蔚来,斯柯达,荣威,宝骏,Jeep,捷豹,名爵,标致,埃安,吉利银河,极氪,三菱,林肯,零跑汽车,AITO,小米汽车".split(",")
brands = [b for b in data["data"] if b["brand_name"] in names]
brands.sort(key=lambda x: x["max_total_data"], reverse=True)

# 贪心法均衡分配
groups = [[] for _ in range(3)]
sums = [0] * 3
for b in brands:
    idx = sums.index(min(sums))
    groups[idx].append(b)
    sums[idx] += b["max_total_data"]

for i, g in enumerate(groups, 1):
    total = sum(b["max_total_data"] for b in g)
    hours = total / 50 / 60
    print(f"\n{'='*55}")
    print(f"终端{i}: {len(g)} 个品牌, ~{total:,} 条, 详情约 {hours:.1f} 小时")
    print(f"{'='*55}")
    for b in sorted(g, key=lambda x: x["max_total_data"], reverse=True):
        print(f"  {b['brand_name']:12s} {b['data_range']:>12s}条  {b['total_pages']:>3d}页")
    print(f"\n品牌输入:")
    print(",".join(b["brand_name"] for b in g))
