"""快速获取所有品牌列表，区分热门和非热门"""
import asyncio
from dongchedi_api import DongchediAPI


async def main():
    api = DongchediAPI(headless=True)
    result = await api.fetch_brands_and_series()
    if not result:
        print("❌ 获取失败")
        return

    all_brands = result["brands"]
    hot_brands = result["hot_brands"]
    hot_ids = {b["brand_id"] for b in hot_brands}

    print(f"\n📊 品牌统计: 全部={len(all_brands)}, 热门={len(hot_brands)}")

    print(f"\n🔥 热门品牌 ({len(hot_brands)} 个):")
    for i, b in enumerate(hot_brands, 1):
        print(f"   {i:2d}. {b['brand_name']} (ID: {b['brand_id']})")

    non_hot = [b for b in all_brands if b["brand_id"] not in hot_ids]
    print(f"\n📋 非热门品牌 ({len(non_hot)} 个):")
    for i, b in enumerate(non_hot, 1):
        print(f"   {i:3d}. {b['brand_name']} (ID: {b['brand_id']})")

    # 已采集的品牌
    import json, os
    brands_path = "client_output/brands.json"
    if os.path.exists(brands_path):
        data = json.load(open(brands_path, "r", encoding="utf-8"))
        collected_ids = {b["brand_id"] for b in data.get("data", [])}
        remaining = [b for b in non_hot if b["brand_id"] not in collected_ids]
        print(f"\n✅ 已采集品牌: {len(collected_ids)} 个")
        print(f"📌 非热门中未采集: {len(remaining)} 个")


if __name__ == "__main__":
    asyncio.run(main())
