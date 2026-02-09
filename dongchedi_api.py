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
            return self._extract_next_data_from_html(html)
        except Exception:
            pass
        return None

    def _extract_next_data_from_html(self, html):
        """从HTML字符串中提取 __NEXT_DATA__ JSON"""
        if not html:
            return None
        match = re.search(r'__NEXT_DATA__[^>]*>(.*?)</script>', html)
        if match:
            return json.loads(match.group(1))
        return None

    def _build_list_url(self, brand_id=None, series_id=None, page_num=1, city_id=1):
        """构建列表页URL
        URL格式: /usedcar/x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-{brand}-{series}-{city}-{page}-x-x-x-x-x
        city_id: 1=全国, 330100=杭州 等
        """
        brand_part = str(brand_id) if brand_id else "x"
        series_part = str(series_id) if series_id else "1"
        city_part = str(city_id)
        return f"{self.USEDCAR_URL}/x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-{brand_part}-{series_part}-{city_part}-{page_num}-x-x-x-x-x"

    def _build_detail_url(self, sku_id):
        """构建详情页URL"""
        return f"{self.USEDCAR_URL}/{sku_id}"

    def _build_params_url(self, car_id):
        """构建参数页URL"""
        return f"{self.BASE_URL}/auto/params-carIds-{car_id}"

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

                # allBrand.brand 结构: [{type:1000, info:{pinyin:"A"}}, {type:1001, info:{brand_id, brand_name, ...}}, ...]
                # type 1000 = 字母分组头, type 1001 = 品牌
                for item in brand_groups:
                    if isinstance(item, dict):
                        info = item.get("info", {})
                        bid = info.get("brand_id")
                        if bid and bid not in seen_ids:
                            seen_ids.add(bid)
                            brands.append(self._normalize_brand(item))

                # 备用: props.brands 是按字母分组的嵌套列表
                if not brands:
                    brands_nested = props.get("brands", [])
                    for group in brands_nested:
                        if isinstance(group, list):
                            for item in group:
                                if isinstance(item, dict):
                                    info = item.get("info", {})
                                    bid = info.get("brand_id")
                                    if bid and bid not in seen_ids:
                                        seen_ids.add(bid)
                                        brands.append(self._normalize_brand(item))

                hot_brands = []
                for hb in hot_brands_raw:
                    info = hb.get("info", {})
                    bid = info.get("brand_id")
                    if bid:
                        hot_brands.append(self._normalize_brand(hb))

                # 如果都解析为空，从 hot_brands 补充
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

        car_info = sku.get("car_info") or {}
        car_id = car_info.get("car_id") or sku.get("car_id")
        params_payload = None
        if car_id:
            params_payload = await self.fetch_car_params(page, car_id)

        return self._normalize_car_detail(sku, sku_id, params_payload=params_payload)

    async def fetch_car_params(self, page, car_id):
        """获取详情页的详细参数（/auto/params-carIds-{car_id}）"""
        url = self._build_params_url(car_id)
        try:
            resp = await page.request.get(url)
            if not resp or not resp.ok:
                print(f"      ⚠️ 参数页请求失败: {car_id} status={getattr(resp, 'status', '?')}")
                return None
            html = await resp.text()
            data = self._extract_next_data_from_html(html)
            if not data:
                print(f"      ⚠️ 参数页无__NEXT_DATA__: {car_id}")
                return None
            page_props = data.get("props", {}).get("pageProps", {})
            raw_data = page_props.get("rawData", {})
            if not raw_data:
                print(f"      ⚠️ 参数页无rawData: {car_id}")
                return None
            parsed = self._parse_param_groups(raw_data)
            return {
                "url": url,
                "raw_data": raw_data,
                "param_groups": parsed,
            }
        except Exception as e:
            print(f"      ⚠️ 参数页异常: {car_id} - {e}")
            return None

    def _normalize_car_detail(self, sku, sku_id, params_payload=None):
        """标准化详情页数据"""
        car_info = sku.get("car_info") or {}
        config = sku.get("car_config_overview") or {}
        power = config.get("power") or {}
        space = config.get("space") or {}
        manipulation = config.get("manipulation") or {}
        shop = sku.get("shop_info") or {}
        report = sku.get("report") or {}
        financial = sku.get("financial_info") or {}

        # 真实价格（分→万元，1万元 = 1,000,000分）
        source_sh = sku.get("source_sh_price", 0)
        source_official = sku.get("source_offical_price", 0)
        sh_price_wan = round(source_sh / 1000000, 2) if source_sh else None
        official_price_wan = round(source_official / 1000000, 2) if source_official else None

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

        detail = {
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

        if params_payload:
            detail["detail_params_url"] = params_payload.get("url")
            detail["detail_params"] = params_payload.get("param_groups")
            # raw_data ~300KB/条，不存储，只保留解析后的 param_groups (~20KB)

        return detail

    def _parse_param_groups(self, raw_data):
        """解析参数页的 rawData 结构
        
        rawData 结构:
          properties: [{text, key, type, ...}, ...]
            type=0 分组标题, type=1/2/3 具体参数
          car_info: [{car_name, car_id, info: {key: {value, icon_type, ...}}, ...}]
        
        返回: [{group: '基本信息', params: [{key, name, value, icon_type}, ...]}, ...]
        """
        if not isinstance(raw_data, dict):
            return None

        properties = raw_data.get("properties") or []
        car_info_list = raw_data.get("car_info") or []
        if not properties or not car_info_list:
            return None

        # 取第一辆车的参数值
        car_values = car_info_list[0].get("info") or {}

        groups = []
        current_group = None

        for prop in properties:
            ptype = prop.get("type", -1)
            text = prop.get("text", "")
            key = prop.get("key", "")

            if ptype == 0:
                # 分组标题
                current_group = {"group": text, "group_key": key, "params": []}
                groups.append(current_group)
            elif current_group is not None and key:
                # 具体参数项
                val_info = car_values.get(key, {})
                value = val_info.get("value", "") if isinstance(val_info, dict) else ""
                icon_type = val_info.get("icon_type", 0) if isinstance(val_info, dict) else 0
                current_group["params"].append({
                    "key": key,
                    "name": text,
                    "value": value,
                    "icon_type": icon_type,
                })

        return groups
