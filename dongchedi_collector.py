#!/usr/bin/env python3
"""
懂车帝完整数据采集程序
四阶段流程：品牌 → 车系 → 列表概览 → 详情页
基于 __NEXT_DATA__ 提取结构化数据
"""

import asyncio
import json
import os
import time
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from playwright.async_api import async_playwright
from dongchedi_api import DongchediAPI


class DongchediCollector:
    """懂车帝完整数据采集器"""

    def __init__(self, max_workers=5, headless=True):
        self.api = DongchediAPI(headless=headless)
        self.max_workers = max_workers
        self.headless = headless

        # 输出文件
        self.brand_file = "dongchedi_brand.json"
        self.series_file = "dongchedi_series.json"
        self.overview_file = "dongchedi_car_overview.json"
        self.detail_file = "dongchedi_car_detail.json"
        self.detail_dir = "car_detail_data"

        # 运行时数据
        self.brands = []
        self.all_series = []
        self.all_overviews = []

        # 线程安全
        self.lock = threading.Lock()

    # ================================================================
    # 阶段1+2：品牌 + 车系
    # ================================================================

    async def stage1_brands(self):
        """阶段1：采集所有品牌"""
        print("\n" + "=" * 60)
        print("📌 阶段1：采集品牌数据")
        print("=" * 60)

        result = await self.api.fetch_brands_and_series()
        if not result:
            print("❌ 品牌采集失败")
            return False

        self.brands = result["brands"]
        hot_brands = result["hot_brands"]

        # 保存
        brand_data = {
            "metadata": {
                "source": "dongchedi",
                "data_type": "brand_list",
                "generator": "dongchedi_collector",
                "generated_at": datetime.now().isoformat(),
                "version": "2.0",
            },
            "summary": {
                "total_brands": len(self.brands),
                "hot_brands": len(hot_brands),
            },
            "data": self.brands,
        }

        with open(self.brand_file, "w", encoding="utf-8") as f:
            json.dump(brand_data, f, ensure_ascii=False, indent=2)

        print(f"   ✅ {len(self.brands)} 个品牌已保存到 {self.brand_file}")
        return True

    async def stage2_series(self):
        """阶段2：采集所有品牌的车系"""
        print("\n" + "=" * 60)
        print("📌 阶段2：采集车系数据")
        print("=" * 60)

        if not self.brands:
            # 尝试从文件加载
            if os.path.exists(self.brand_file):
                with open(self.brand_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.brands = data.get("data", [])
            if not self.brands:
                print("❌ 无品牌数据，请先运行阶段1")
                return False

        total = len(self.brands)
        print(f"   🎯 共 {total} 个品牌需要采集车系")
        print(f"   🔧 线程数: {self.max_workers}")

        start_time = time.time()
        self.all_series = []
        processed = 0
        failed = 0

        # 多线程采集
        def worker(brand):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                series = loop.run_until_complete(
                    self.api.fetch_series_for_brand(brand["brand_id"], brand["brand_name"])
                )
                return brand, series
            except Exception as e:
                return brand, None
            finally:
                loop.close()

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(worker, b): b for b in self.brands}

            for future in as_completed(futures):
                brand, series = future.result()
                processed += 1

                if series is not None:
                    with self.lock:
                        self.all_series.extend(series)
                    print(f"   [{processed}/{total}] ✅ {brand['brand_name']}: {len(series)} 个车系")
                else:
                    failed += 1
                    print(f"   [{processed}/{total}] ❌ {brand['brand_name']}: 采集失败")

        duration = time.time() - start_time

        # 保存
        series_data = {
            "metadata": {
                "source": "dongchedi",
                "data_type": "series_list",
                "generator": "dongchedi_collector",
                "generated_at": datetime.now().isoformat(),
                "version": "2.0",
                "thread_count": self.max_workers,
            },
            "summary": {
                "total_brands": total,
                "processed_brands": processed,
                "failed_brands": failed,
                "total_series": len(self.all_series),
                "duration_seconds": round(duration, 1),
            },
            "data": self.all_series,
        }

        with open(self.series_file, "w", encoding="utf-8") as f:
            json.dump(series_data, f, ensure_ascii=False, indent=2)

        print(f"\n   ✅ {len(self.all_series)} 个车系已保存到 {self.series_file}")
        print(f"   ⏱️  耗时: {duration:.1f}秒")
        return True

    # ================================================================
    # 阶段3：列表概览
    # ================================================================

    async def stage3_overview(self, target_brands=None, max_pages_per=167):
        """
        阶段3：采集列表概览数据
        target_brands: 指定品牌名称列表，None=全部
        """
        print("\n" + "=" * 60)
        print("📌 阶段3：采集列表概览数据")
        print("=" * 60)

        # 加载车系数据
        if not self.all_series:
            if os.path.exists(self.series_file):
                with open(self.series_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.all_series = data.get("data", [])

        # 加载品牌数据
        if not self.brands:
            if os.path.exists(self.brand_file):
                with open(self.brand_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.brands = data.get("data", [])

        if not self.brands:
            print("❌ 无品牌数据")
            return False

        # 筛选目标品牌
        brands_to_process = self.brands
        if target_brands:
            brands_to_process = [b for b in self.brands if b["brand_name"] in target_brands]
            print(f"   🎯 指定品牌: {', '.join(target_brands)}")

        print(f"   📊 共 {len(brands_to_process)} 个品牌")

        start_time = time.time()
        self.all_overviews = []
        brand_stats = []

        for i, brand in enumerate(brands_to_process, 1):
            bid = brand["brand_id"]
            bname = brand["brand_name"]
            print(f"\n   [{i}/{len(brands_to_process)}] 🏷️  {bname}")

            # 获取该品牌的车系
            brand_series = [s for s in self.all_series if s.get("brand_id") == bid]

            brand_cars = []

            if brand_series:
                # 按车系逐个采集（更精确，避免167页限制）
                for s in brand_series:
                    cars = await self.api.fetch_all_car_list(
                        bid, bname,
                        series_id=s["series_id"],
                        series_name=s["series_name"],
                        max_pages=max_pages_per,
                    )
                    brand_cars.extend(cars)
                    await asyncio.sleep(0.3)
            else:
                # 无车系数据，直接按品牌采集
                brand_cars = await self.api.fetch_all_car_list(
                    bid, bname, max_pages=max_pages_per
                )

            self.all_overviews.extend(brand_cars)
            brand_stats.append({
                "brand_id": bid,
                "brand_name": bname,
                "series_count": len(brand_series),
                "car_count": len(brand_cars),
            })
            print(f"      📊 {bname}: {len(brand_cars)} 条")

        duration = time.time() - start_time

        # 保存
        overview_data = {
            "metadata": {
                "source": "dongchedi",
                "data_type": "car_overview",
                "generator": "dongchedi_collector",
                "generated_at": datetime.now().isoformat(),
                "version": "2.0",
            },
            "summary": {
                "total_brands": len(brands_to_process),
                "total_cars": len(self.all_overviews),
                "duration_seconds": round(duration, 1),
                "brand_stats": brand_stats,
            },
            "data": self.all_overviews,
        }

        with open(self.overview_file, "w", encoding="utf-8") as f:
            json.dump(overview_data, f, ensure_ascii=False, indent=2)

        print(f"\n   ✅ {len(self.all_overviews)} 条概览数据已保存到 {self.overview_file}")
        print(f"   ⏱️  耗时: {duration:.1f}秒")
        return True

    # ================================================================
    # 阶段4：详情页
    # ================================================================

    async def stage4_details(self, max_concurrent=3):
        """
        阶段4：采集详情页数据（真实价格+参数+图片）
        """
        print("\n" + "=" * 60)
        print("📌 阶段4：采集详情页数据")
        print("=" * 60)

        # 加载概览数据
        if not self.all_overviews:
            if os.path.exists(self.overview_file):
                with open(self.overview_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.all_overviews = data.get("data", [])

        if not self.all_overviews:
            print("❌ 无概览数据，请先运行阶段3")
            return False

        total = len(self.all_overviews)
        print(f"   🎯 共 {total} 辆车需要采集详情")
        print(f"   🔧 并发数: {max_concurrent}")

        os.makedirs(self.detail_dir, exist_ok=True)

        start_time = time.time()
        all_details = []
        success_count = 0
        fail_count = 0

        # 按品牌分组
        brand_groups = {}
        for car in self.all_overviews:
            bname = car.get("brand_name", "未知")
            if bname not in brand_groups:
                brand_groups[bname] = []
            brand_groups[bname].append(car)

        for brand_name, cars in brand_groups.items():
            print(f"\n   🏷️  {brand_name}: {len(cars)} 辆")

            brand_details = []

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=self.headless, slow_mo=self.api.slow_mo)

                # 创建多个页面并发采集
                pages = []
                for _ in range(min(max_concurrent, len(cars))):
                    pg = await browser.new_page()
                    pages.append(pg)

                try:
                    for batch_start in range(0, len(cars), max_concurrent):
                        batch = cars[batch_start:batch_start + max_concurrent]
                        tasks = []

                        for idx, car in enumerate(batch):
                            pg = pages[idx % len(pages)]
                            sku_id = car.get("sku_id")
                            tasks.append(self._fetch_detail_safe(pg, sku_id))

                        results = await asyncio.gather(*tasks)

                        for car, detail in zip(batch, results):
                            if detail:
                                brand_details.append(detail)
                                success_count += 1
                            else:
                                fail_count += 1

                            current = success_count + fail_count
                            if current % 10 == 0 or current == total:
                                print(f"      进度: {current}/{total} (成功: {success_count}, 失败: {fail_count})")

                        await asyncio.sleep(0.5)

                finally:
                    for pg in pages:
                        await pg.close()
                    await browser.close()

            # 保存单品牌详情
            if brand_details:
                all_details.extend(brand_details)
                brand_file = os.path.join(
                    self.detail_dir,
                    f"{brand_name}_{len(brand_details)}_details.json"
                )
                with open(brand_file, "w", encoding="utf-8") as f:
                    json.dump({
                        "brand_name": brand_name,
                        "total": len(brand_details),
                        "collected_at": datetime.now().isoformat(),
                        "data": brand_details,
                    }, f, ensure_ascii=False, indent=2)
                print(f"      💾 {brand_name}: {len(brand_details)} 条已保存")

        duration = time.time() - start_time

        # 保存总汇总
        detail_summary = {
            "metadata": {
                "source": "dongchedi",
                "data_type": "car_detail_full",
                "generator": "dongchedi_collector",
                "generated_at": datetime.now().isoformat(),
                "version": "2.0",
            },
            "summary": {
                "total_attempted": total,
                "successful": success_count,
                "failed": fail_count,
                "total_images": sum(len(d.get("images", [])) for d in all_details),
                "duration_seconds": round(duration, 1),
            },
            "data": all_details,
        }

        with open(self.detail_file, "w", encoding="utf-8") as f:
            json.dump(detail_summary, f, ensure_ascii=False, indent=2)

        print(f"\n   ✅ {success_count} 条详情数据已保存到 {self.detail_file}")
        print(f"   ❌ 失败: {fail_count} 条")
        print(f"   ⏱️  耗时: {duration:.1f}秒")
        return True

    async def _fetch_detail_safe(self, page, sku_id):
        """安全地采集单个详情"""
        try:
            return await self.api.fetch_car_detail(page, sku_id)
        except Exception as e:
            return None

    # ================================================================
    # 完整流程
    # ================================================================

    async def run_all(self, target_brands=None, skip_stages=None):
        """
        运行完整采集流程
        target_brands: 指定品牌列表，None=全部
        skip_stages: 跳过的阶段列表，如 [1, 2] 跳过品牌和车系采集
        """
        skip = skip_stages or []

        print("🚗 懂车帝完整数据采集")
        print("=" * 60)
        print(f"⏰ 开始时间: {datetime.now().isoformat()}")
        if target_brands:
            print(f"🎯 目标品牌: {', '.join(target_brands)}")
        print(f"🔧 线程数: {self.max_workers}")
        print("=" * 60)

        total_start = time.time()

        if 1 not in skip:
            await self.stage1_brands()

        if 2 not in skip:
            await self.stage2_series()

        if 3 not in skip:
            await self.stage3_overview(target_brands=target_brands)

        if 4 not in skip:
            await self.stage4_details()

        total_duration = time.time() - total_start

        print("\n" + "=" * 60)
        print("🎉 采集完成！")
        print("=" * 60)
        print(f"⏱️  总耗时: {total_duration:.1f}秒")
        print(f"📁 输出文件:")
        print(f"   - {self.brand_file}    品牌数据")
        print(f"   - {self.series_file}   车系数据")
        print(f"   - {self.overview_file} 概览数据")
        print(f"   - {self.detail_file}   详情数据")
        print(f"   - {self.detail_dir}/   各品牌详情")


async def main():
    """主函数 - 可配置运行"""
    collector = DongchediCollector(
        max_workers=5,
        headless=True,
    )

    # ====== 配置选项 ======

    # 指定品牌（None=全部）
    target_brands = None
    # target_brands = ["奇瑞", "吉利"]

    # 跳过阶段（如已有品牌/车系数据可跳过）
    skip_stages = None
    # skip_stages = [1, 2]  # 跳过品牌和车系采集

    await collector.run_all(
        target_brands=target_brands,
        skip_stages=skip_stages,
    )


if __name__ == "__main__":
    asyncio.run(main())
