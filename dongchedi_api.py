#!/usr/bin/env python3
"""
懂车帝数据采集核心模块
基于 __NEXT_DATA__ 提取结构化JSON数据，绕过字体反爬
"""

import asyncio
import json
import re
import os
import time
from datetime import datetime
from playwright.async_api import async_playwright


class DongchediAPI:
    """懂车帝数据采集核心类 - 基于 __NEXT_DATA__ 提取"""

    BASE_URL = "https://www.dongchedi.com"
    USEDCAR_URL = f"{BASE_URL}/usedcar"

    def __init__(self, headless=True, slow_mo=0):
        self.headless = headless
        self.slow_mo = slow_mo

    # ================================================================
    # 通用工具方法
    # ================================================================

    async def _extract_next_data(self, page):
        """从页面提取 __NEXT_DATA__ JSON"""
        try:
            script = await page.query_selector('script#__NEXT_DATA__')
            if script:
                raw = await script.text_content()
                return json.loads(raw)
        except Exception:
            pass
        # 备用：正则匹配
        try:
            html = await page.content()
            match = re.search(r'__NEXT_DATA__[^>]*>(.*?)</script>', html)
            if match:
                return json.loads(match.group(1))
        except Exception:
            pass
        return None

    def _build_list_url(self, brand_id=None, series_id=None, page_num=1):
        """构建列表页URL
        URL格式: /usedcar/x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-{brand}-x-{series}-{page}-x-x-x-x-x
        """
        brand_part = str(brand_id) if brand_id else "x"
        series_part = str(series_id) if series_id else "1"
        return f"{self.USEDCAR_URL}/x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-{brand_part}-x-{series_part}-{page_num}-x-x-x-x-x"

    def _build_detail_url(self, sku_id):
        """构建详情页URL"""
        return f"{self.USEDCAR_URL}/{sku_id}"

    # ================================================================
    # 阶段1+2：品牌 + 车系采集
    # ================================================================

    async def fetch_brands_and_series(self):
        """
        一次请求获取所有品牌和热门车系
        返回: { brands: [...], hot_brands: [...], series_sample: [...] }
        """
        print("🏷️  阶段1+2：采集品牌和车系数据...")
        url = self._build_list_url()
        print(f"   🔗 {url}")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless, slow_mo=self.slow_mo)
            page = await browser.new_page()
            try:
                await page.goto(url, wait_until="domcontentloaded")
                await page.wait_for_timeout(5000)

                data = await self._extract_next_data(page)
                if not data:
                    print("   ❌ 无法提取 __NEXT_DATA__")
                    return None

                props = data.get("props", {}).get("pageProps", {})

                # --- 品牌 ---
                all_brand = props.get("allBrand", {})
                brand_groups = all_brand.get("brand", [])
                hot_brands_raw = all_brand.get("hot_brand", [])

                brands = []
                seen_ids = set()
                # brand_groups 是按字母分组的列表
                for group in brand_groups:
                    if isinstance(group, dict):
                        # 单个品牌
                        bid = group.get("brand_id")
                        if bid and bid not in seen_ids:
                            seen_ids.add(bid)
                            brands.append(self._normalize_brand(group))
                    elif isinstance(group, list):
                        # 一组品牌
                        for item in group:
                            if isinstance(item, dict):
                                bid = item.get("brand_id")
                                if bid and bid not in seen_ids:
                                    seen_ids.add(bid)
                                    brands.append(self._normalize_brand(item))

                hot_brands = []
                for hb in hot_brands_raw:
                    bid = hb.get("brand_id")
                    if bid:
                        hot_brands.append(self._normalize_brand(hb))

                # 如果 brand_groups 解析为空，从 hot_brands 补充
                if not brands and hot_brands:
                    brands = hot_brands

                brands.sort(key=lambda x: x["brand_id"])

                # --- 热门车系（tabData中） ---
                tab_data = props.get("tabData", {})
                tab_series = tab_data.get("car_series_list", [])
                tab_brands = tab_data.get("car_brand_list", [])

                print(f"   ✅ 品牌: {len(brands)} 个, 热门品牌: {len(hot_brands)} 个")
                print(f"   ✅ tabData车系: {len(tab_series)} 个, tabData品牌: {len(tab_brands)} 个")

                return {
                    "brands": brands,
                    "hot_brands": hot_brands,
                    "tab_series": tab_series,
                    "tab_brands": tab_brands,
                }
            finally:
                await browser.close()

    async def fetch_series_for_brand(self, brand_id, brand_name, browser=None):
        """
        获取指定品牌的所有车系
        直接从品牌列表页的 __NEXT_DATA__.seriesList 获取
        """
        url = self._build_list_url(brand_id=brand_id)

        should_close = False
        if browser is None:
            pw = await async_playwright().start()
            browser = await pw.chromium.launch(headless=self.headless, slow_mo=self.slow_mo)
            should_close = True

        page = await browser.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded")
            await page.wait_for_timeout(4000)

            data = await self._extract_next_data(page)
            if not data:
                return []

            props = data.get("props", {}).get("pageProps", {})
            series_list_raw = props.get("seriesList", [])

            series_list = []
            for s in series_list_raw:
                series_list.append({
                    "series_id": s.get("series_id"),
                    "series_name": s.get("series_name"),
                    "image_url": s.get("image_url", ""),
                    "brand_id": brand_id,
                    "brand_name": brand_name,
                })

            return series_list
        finally:
            await page.close()
            if should_close:
                await browser.close()

    def _normalize_brand(self, raw):
        """标准化品牌数据"""
        info = raw.get("info", {})
        return {
            "brand_id": raw.get("brand_id") or info.get("brand_id"),
            "brand_name": raw.get("brand_name") or info.get("brand_name", ""),
            "brand_logo": raw.get("brand_logo") or info.get("brand_logo", ""),
            "pinyin": info.get("pinyin", ""),
        }

    # ================================================================
    # 阶段3：列表概览采集
    # ================================================================

    async def fetch_car_list_page(self, page, brand_id=None, series_id=None, page_num=1):
        """
        获取单页列表概览数据
        返回: { total, has_more, cars: [...] }
        """
        url = self._build_list_url(brand_id, series_id, page_num)
        await page.goto(url, wait_until="domcontentloaded")
        await page.wait_for_timeout(4000)

        data = await self._extract_next_data(page)
        if not data:
            return None

        props = data.get("props", {}).get("pageProps", {})
        car_list = props.get("carList", {})

        total = car_list.get("total", 0)
        has_more = car_list.get("has_more", False)
        sku_list = car_list.get("search_sh_sku_info_list", [])

        cars = []
        for sku in sku_list:
            cars.append(self._normalize_car_overview(sku))

        return {
            "total": total,
            "has_more": has_more,
            "page_num": page_num,
            "count": len(cars),
            "cars": cars,
        }

    async def fetch_all_car_list(self, brand_id, brand_name, series_id=None, series_name=None, max_pages=167):
        """
        翻页获取品牌/车系下所有车辆概览
        """
        label = f"{brand_name}"
        if series_name:
            label += f"/{series_name}"

        print(f"   📋 采集列表: {label}")

        all_cars = []

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless, slow_mo=self.slow_mo)
            page = await browser.new_page()

            try:
                for pg in range(1, max_pages + 1):
                    result = await self.fetch_car_list_page(page, brand_id, series_id, pg)

                    if not result or not result["cars"]:
                        break

                    all_cars.extend(result["cars"])
                    total = result["total"]

                    if pg == 1:
                        print(f"      总数: {total}, 第1页: {result['count']} 条")

                    if not result["has_more"]:
                        break

                    # 避免请求过快
                    await asyncio.sleep(0.5)

            finally:
                await browser.close()

        print(f"      ✅ 共采集 {len(all_cars)} 条概览数据")
        return all_cars

    def _normalize_car_overview(self, sku):
        """标准化列表概览数据"""
        return {
            "sku_id": sku.get("sku_id"),
            "spu_id": sku.get("spu_id"),
            "title": sku.get("title", ""),
            "brand_id": sku.get("brand_id"),
            "brand_name": sku.get("brand_name", ""),
            "series_id": sku.get("series_id"),
            "series_name": sku.get("series_name", ""),
            "car_id": sku.get("car_id"),
            "car_name": sku.get("car_name", ""),
            "car_year": sku.get("car_year"),
            "image": sku.get("image", ""),
            "car_source_city": sku.get("car_source_city_name", ""),
            "transfer_cnt": sku.get("transfer_cnt", 0),
            "shop_id": sku.get("shop_id", ""),
            "car_source_type": sku.get("car_source_type", ""),
            "authentication_method": sku.get("authentication_method", ""),
            "tags": [t.get("text", "") for t in (sku.get("tags") or [])],
            "detail_url": f"{self.BASE_URL}/usedcar/{sku.get('sku_id')}",
            # 以下字段被字体加密，列表页无法直接获取真实值
            "_encrypted_sh_price": sku.get("sh_price", ""),
            "_encrypted_official_price": sku.get("official_price", ""),
            "_encrypted_mileage": sku.get("car_mileage", ""),
            "_encrypted_sub_title": sku.get("sub_title", ""),
        }

    # ================================================================
    # 阶段4：详情页采集
    # ================================================================

    async def fetch_car_detail(self, page, sku_id):
        """
        获取单辆车的详情数据（参数+图片+真实价格）
        """
        url = self._build_detail_url(sku_id)
        await page.goto(url, wait_until="domcontentloaded")
        await page.wait_for_timeout(4000)

        data = await self._extract_next_data(page)
        if not data:
            return None

        props = data.get("props", {}).get("pageProps", {})
        sku = props.get("skuDetail", {})

        if not sku:
            return None

        return self._normalize_car_detail(sku, sku_id)

    def _normalize_car_detail(self, sku, sku_id):
        """标准化详情页数据"""
        car_info = sku.get("car_info", {})
        config = sku.get("car_config_overview", {})
        power = config.get("power", {})
        space = config.get("space", {})
        manipulation = config.get("manipulation", {})
        shop = sku.get("shop_info", {})
        report = sku.get("report", {})
        financial = sku.get("financial_info", {})

        # 真实价格（分→万元）
        source_sh = sku.get("source_sh_price", 0)
        source_official = sku.get("source_offical_price", 0)
        sh_price_wan = round(source_sh / 10000, 2) if source_sh else None
        official_price_wan = round(source_official / 10000, 2) if source_official else None

        # other_params → dict
        other_params = {}
        for p in (sku.get("other_params") or []):
            name = p.get("name", "")
            value = p.get("value", "")
            if name:
                other_params[name] = value

        # important_text 解析
        important_text = sku.get("important_text", "")

        # 亮点配置
        highlights = []
        for h in (sku.get("high_light_config") or []):
            highlights.append({
                "name": h.get("name", ""),
                "icon": h.get("icon", ""),
            })

        # 标签
        tags = []
        for t in (sku.get("tags") or []):
            tags.append(t.get("text", ""))

        return {
            "sku_id": str(sku_id),
            "spu_id": str(sku.get("spu_id", "")),
            "title": sku.get("title", ""),
            "important_text": important_text,

            # 真实价格
            "sh_price": sh_price_wan,
            "official_price": official_price_wan,
            "include_tax_price": sku.get("include_tax_price", ""),
            "source_sh_price": source_sh,
            "source_offical_price": source_official,

            # 基本信息
            "brand_id": car_info.get("brand_id"),
            "brand_name": car_info.get("brand_name", ""),
            "series_id": car_info.get("series_id") or config.get("series_id"),
            "series_name": car_info.get("series_name", "") or config.get("series_name", ""),
            "car_id": car_info.get("car_id"),
            "car_name": car_info.get("car_name", ""),
            "year": car_info.get("year"),
            "body_color": car_info.get("body_color", ""),

            # 参数
            "params": other_params,

            # 配置
            "config": {
                "power": {
                    "capacity": power.get("capacity", ""),
                    "horsepower": power.get("horsepower", ""),
                    "fuel_form": power.get("fuel_form", ""),
                    "gearbox": power.get("gearbox_description", ""),
                    "acceleration_time": power.get("acceleration_time", ""),
                },
                "space": {
                    "length": space.get("length", ""),
                    "width": space.get("width", ""),
                    "height": space.get("height", ""),
                    "wheelbase": space.get("wheelbase", ""),
                },
                "manipulation": {
                    "driver_form": manipulation.get("driver_form", ""),
                    "front_suspension": manipulation.get("front_suspension_form", ""),
                    "rear_suspension": manipulation.get("rear_suspension_form", ""),
                },
            },

            # 图片
            "images": sku.get("head_images", []),

            # 亮点配置
            "highlights": highlights,

            # 商家信息
            "shop": {
                "shop_id": shop.get("shop_id", ""),
                "shop_name": shop.get("shop_name", ""),
                "shop_short_name": shop.get("shop_short_name", ""),
                "city_name": shop.get("city_name", ""),
                "shop_address": shop.get("shop_address", ""),
                "business_time": shop.get("business_time", ""),
                "sales_range": shop.get("sales_range", ""),
                "sales_car_num": shop.get("sales_car_num", 0),
            },

            # 检测报告
            "report": {
                "has_report": report.get("has_report", False),
                "eva_level": report.get("eva_level", 0),
                "overview": report.get("overview") or [],
            },

            # 金融
            "financial": {
                "down_payment": financial.get("down_payment", ""),
                "month_pay": financial.get("month_pay", ""),
                "repayment_cycle": financial.get("repayment_cycle", 0),
            },

            # 标签
            "tags": tags,

            # 描述
            "description": sku.get("sh_car_desc", ""),

            "detail_url": self._build_detail_url(sku_id),
            "collected_at": datetime.now().isoformat(),
        }
