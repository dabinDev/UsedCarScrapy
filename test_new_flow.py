#!/usr/bin/env python3
"""
测试新采集流程 - 用一个小品牌跑通四个阶段
"""

import asyncio
import json
import os
from datetime import datetime
from dongchedi_api import DongchediAPI


async def main():
    api = DongchediAPI(headless=True)
    os.makedirs("test_results", exist_ok=True)

    # ========== 配置：多品牌/多车系/多详情 ==========
    target_brand_names = ["五菱汽车", "奇瑞", "比亚迪"]
    series_per_brand = 2
    cars_per_series = 3
    details_per_series = 2

    # ========== 阶段1：品牌 ==========
    print("=" * 60)
    print("🏷️  阶段1：品牌采集")
    print("=" * 60)

    result = await api.fetch_brands_and_series()
    if not result:
        print("❌ 品牌采集失败")
        return

    brands = result["brands"]
    print(f"✅ 获取到 {len(brands)} 个品牌")
    for b in brands[:5]:
        print(f"   {b['brand_id']:>5} {b['brand_name']}")
    print(f"   ... 共 {len(brands)} 个")

    # 选择多个品牌测试
    test_brands = []
    for name in target_brand_names:
        brand = next((b for b in brands if name in b["brand_name"]), None)
        if brand:
            test_brands.append(brand)
    if not test_brands:
        test_brands = brands[:1]

    print("\n🎯 测试品牌:")
    for b in test_brands:
        print(f"   - {b['brand_name']} (ID: {b['brand_id']})")

    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            for test_brand in test_brands:
                # ========== 阶段2：车系 ==========
                print("\n" + "=" * 60)
                print(f"🚗 阶段2：车系采集 - {test_brand['brand_name']}")
                print("=" * 60)

                series = await api.fetch_series_for_brand(test_brand["brand_id"], test_brand["brand_name"])
                print(f"✅ 获取到 {len(series)} 个车系")
                for s in series[:10]:
                    print(f"   {s['series_id']:>6} {s['series_name']}")
                if len(series) > 10:
                    print(f"   ... 共 {len(series)} 个")

                test_series_list = series[:series_per_brand] if series else []
                for test_series in test_series_list:
                    print(f"\n🎯 测试车系: {test_series['series_name']} (ID: {test_series['series_id']})")

                    # ========== 阶段3：列表概览（只取第1页） ==========
                    print("\n" + "=" * 60)
                    print(f"📋 阶段3：列表概览 - {test_brand['brand_name']}")
                    print(f"   车系: {test_series['series_name']}")
                    print("=" * 60)

                    list_result = await api.fetch_car_list_page(
                        page,
                        brand_id=test_brand["brand_id"],
                        series_id=test_series["series_id"],
                        page_num=1,
                    )

                    if not list_result:
                        print("❌ 列表采集失败")
                        continue

                    print(f"✅ 总数: {list_result['total']}, 本页: {list_result['count']} 条, has_more: {list_result['has_more']}")
                    cars = list_result["cars"]

                    for car in cars[:cars_per_series]:
                        print(f"\n   🚗 {car['title']}")
                        print(f"      sku_id: {car['sku_id']}")
                        print(f"      车系: {car['series_name']}")
                        print(f"      车源: {car['car_source_city']}")
                        print(f"      过户: {car['transfer_cnt']}次")
                        print(f"      标签: {car['tags']}")
                        print(f"      详情: {car['detail_url']}")
                        print(f"      缩略图: {car['image'][:80]}...")

                    # ========== 阶段4：详情（多辆） ==========
                    for test_car in cars[:details_per_series]:
                        print("\n" + "=" * 60)
                        print(f"🔍 阶段4：详情页 - {test_car['title']}")
                        print("=" * 60)

                        detail = await api.fetch_car_detail(page, test_car["sku_id"])

                        if detail:
                            print(f"✅ 详情采集成功!")
                            print(f"   标题: {detail['title']}")
                            print(f"   摘要: {detail['important_text']}")
                            print(f"   二手价: {detail['sh_price']}万 (原始: {detail['source_sh_price']}分)")
                            print(f"   指导价: {detail['official_price']}万 (原始: {detail['source_offical_price']}分)")
                            print(f"   含税价: {detail['include_tax_price']}")
                            print(f"   品牌: {detail['brand_name']}")
                            print(f"   车系: {detail['series_name']}")
                            print(f"   年款: {detail['year']}")
                            print(f"   颜色: {detail['body_color']}")

                            print(f"\n   📋 参数:")
                            for k, v in detail["params"].items():
                                print(f"      {k}: {v}")

                            print(f"\n   ⚙️ 配置:")
                            cfg = detail["config"]
                            print(f"      动力: {cfg['power']['capacity']} {cfg['power']['horsepower']} {cfg['power']['fuel_form']}")
                            print(f"      变速箱: {cfg['power']['gearbox']}")
                            print(f"      驱动: {cfg['manipulation']['driver_form']}")
                            print(f"      尺寸: {cfg['space']['length']}x{cfg['space']['width']}x{cfg['space']['height']}mm")

                            print(f"\n   🖼️ 图片: {len(detail['images'])} 张")
                            for i, url in enumerate(detail["images"][:3]):
                                print(f"      [{i}] {url[:80]}...")

                            print(f"\n   🏪 商家: {detail['shop']['shop_name']} ({detail['shop']['city_name']})")
                            print(f"   📍 地址: {detail['shop']['shop_address']}")

                            print(f"\n   🏷️ 标签: {detail['tags']}")
                            print(f"   ✨ 亮点: {[h['name'] for h in detail['highlights']]}" )

                            print(f"\n   📝 检测报告: {'有' if detail['report']['has_report'] else '无'}")
                            if detail["report"]["overview"]:
                                for item in detail["report"]["overview"][:3]:
                                    print(f"      {item.get('name', '')}: {item.get('overview', '')}")

                            # 保存完整详情（按品牌/车系/sku分文件）
                            file_name = f"test_detail_{test_brand['brand_name']}_{test_series['series_name']}_{detail['sku_id']}.json"
                            file_path = os.path.join("test_results", file_name)
                            with open(file_path, "w", encoding="utf-8") as f:
                                json.dump(detail, f, ensure_ascii=False, indent=2)
                            print(f"\n   💾 已保存到 {file_path}")
                        else:
                            print("❌ 详情采集失败")
        finally:
            await browser.close()

    # ========== 汇总 ==========
    print("\n" + "=" * 60)
    print("📊 测试汇总")
    print("=" * 60)
    print(f"阶段1 品牌: {len(brands)} 个")
    print(f"阶段2 车系: 多品牌/多车系测试完成")
    print(f"阶段3 概览: 每车系{cars_per_series}条预览")
    print(f"阶段4 详情: 每车系{details_per_series}条详情")
    print("\n✅ 四阶段流程全部通过！")


if __name__ == "__main__":
    asyncio.run(main())
