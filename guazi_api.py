#!/usr/bin/env python3
"""
瓜子二手车采集核心模块 — 移动端版本（对齐懂车帝字段）
- 使用移动端 m.guazi.com，模拟 iPhone 设备访问，无滑块验证码
- 基于 Playwright 拉取页面，从 HTML 中提取结构化数据
- 输出字段与 dongchedi_api 保持一致，以兼容现有 JSON/数据库结构
- URL 结构（移动端）：
    品牌列表页: https://m.guazi.com/{city}/buy/
    品牌车系页: https://m.guazi.com/{city}/{brand_slug}/
    车系列表页: https://m.guazi.com/{city}/{brand_slug}/{series_slug}/
    详情页:     https://m.guazi.com/car-detail/{clue_id}.html
- 移动端列表页不支持翻页URL，每个车系页面固定返回最多40条
"""

import asyncio
import json
import re
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple

from playwright.async_api import async_playwright, Page, Browser, BrowserContext


# iPhone 设备配置
MOBILE_DEVICE = "iPhone 13"


class GuaziAPI:
    BASE_URL = "https://m.guazi.com"

    def __init__(self, headless: bool = True, slow_mo: int = 0):
        self.headless = headless
        self.slow_mo = slow_mo
        self._pw = None
        self._device_desc = None

    async def _get_device(self):
        """获取移动设备描述符（懒加载）"""
        if self._device_desc is None:
            if self._pw is None:
                self._pw = await async_playwright().start()
            self._device_desc = self._pw.devices[MOBILE_DEVICE]
        return self._device_desc

    async def create_mobile_context(self, browser: Browser) -> BrowserContext:
        """创建移动端浏览器上下文"""
        device = await self._get_device()
        return await browser.new_context(**device)

    # ================================================================
    # 通用工具
    # ================================================================

    async def _goto_safe(self, page: Page, url: str, timeout: int = 20000):
        """安全跳转，超时不抛异常"""
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
        except Exception:
            pass
        await page.wait_for_timeout(2000)

    def _clean_price_wan(self, val) -> Optional[float]:
        """价格清洗：'8.50万' -> 8.5, '22.06' -> 22.06"""
        if val is None:
            return None
        try:
            s = str(val).replace("万元", "").replace("万", "").replace(",", "").replace("¥", "").strip()
            if not s:
                return None
            return round(float(s), 2)
        except Exception:
            return None

    # ================================================================
    # 阶段1：品牌采集 - 从移动端列表页提取所有品牌链接
    # ================================================================

    async def fetch_brands(self, city_code: str, browser: Browser = None) -> List[Dict]:
        """
        获取指定城市下的所有品牌
        从 m.guazi.com/{city}/buy/ 页面提取品牌链接
        返回: [{brand_slug, brand_name}, ...]
        """
        url = f"{self.BASE_URL}/{city_code}/buy/"
        should_close = False
        if browser is None:
            pw = await async_playwright().start()
            browser = await pw.chromium.launch(headless=self.headless, slow_mo=self.slow_mo)
            should_close = True

        ctx = await self.create_mobile_context(browser)
        page = await ctx.new_page()
        try:
            await self._goto_safe(page, url)

            brands = await page.evaluate("""(cityCode) => {
                const links = document.querySelectorAll('a[href]');
                const brandMap = {};
                for (const a of links) {
                    const href = a.getAttribute('href') || '';
                    const match = href.match(new RegExp('^/' + cityCode + '/([a-z][a-z0-9-]+)/$'));
                    if (match) {
                        const slug = match[1];
                        if (['buy', 'sell', 'aboutus', 'app', 'car-detail',
                             'price0','price1','price2','price3','price4','price5',
                             'price6','price7','price8','price9','price10','price11',
                             'price12','price13','price14','price15'].includes(slug)) continue;
                        const text = a.textContent.trim();
                        if (text && text.length < 20 && !brandMap[slug]) {
                            brandMap[slug] = text;
                        }
                    }
                }
                return Object.entries(brandMap).map(([slug, name]) => ({brand_slug: slug, brand_name: name}));
            }""", city_code)

            return brands or []
        finally:
            await page.close()
            await ctx.close()
            if should_close:
                await browser.close()

    # ================================================================
    # 阶段2：车系采集 - 从移动端品牌页提取车系链接
    # ================================================================

    async def fetch_series_for_brand(self, city_code: str, brand_slug: str, brand_name: str,
                                     browser: Browser = None) -> List[Dict]:
        """
        获取指定品牌下的所有车系
        从 m.guazi.com/{city}/{brand_slug}/ 页面提取车系链接
        返回: [{series_slug, series_name, brand_slug, brand_name}, ...]
        """
        url = f"{self.BASE_URL}/{city_code}/{brand_slug}/"
        should_close = False
        if browser is None:
            pw = await async_playwright().start()
            browser = await pw.chromium.launch(headless=self.headless, slow_mo=self.slow_mo)
            should_close = True

        ctx = await self.create_mobile_context(browser)
        page = await ctx.new_page()
        try:
            await self._goto_safe(page, url)

            series_list = await page.evaluate("""(args) => {
                const [cityCode, brandSlug] = args;
                const links = document.querySelectorAll('a[href]');
                const seriesMap = {};
                for (const a of links) {
                    const href = a.getAttribute('href') || '';
                    const pattern = new RegExp('^/' + cityCode + '/' + brandSlug + '/([a-z0-9][a-z0-9-]+)/$');
                    const match = href.match(pattern);
                    if (match) {
                        const slug = match[1];
                        if (/^o\\d+$/.test(slug)) continue;
                        const text = a.textContent.trim();
                        if (text && text.length < 30 && !seriesMap[slug]) {
                            seriesMap[slug] = text;
                        }
                    }
                }
                return Object.entries(seriesMap).map(([slug, name]) => ({
                    series_slug: slug,
                    series_name: name,
                }));
            }""", [city_code, brand_slug])

            for s in (series_list or []):
                s["brand_slug"] = brand_slug
                s["brand_name"] = brand_name

            return series_list or []
        finally:
            await page.close()
            await ctx.close()
            if should_close:
                await browser.close()

    # ================================================================
    # 阶段3：车辆列表采集（概览）— 移动端单页，最多40条
    # ================================================================

    async def fetch_car_list_page(self, page: Page, city_code: str, brand_slug: str,
                                  series_slug: str) -> Optional[Dict]:
        """
        获取移动端车系列表页的车辆数据（单页，最多40条）
        移动端HTML结构：
        <a href="/car-detail/c162856787323491.html">
          <section>
            <div><img src="..." alt="奔驰C级 2024款..."></div>
            <div>
              <h4>奔驰C级 2024款 C 260 L 运动版</h4>
              <div class="flex..."><span data-text="已检测">已检测</span></div>
              <p><span>2024年</span><span>｜</span><span>1.43万公里</span><span>｜</span><span>北京</span></p>
              <div>
                <span class="text-gz-text-red font-din text-lg...font-bold">21.93</span>
                <span class="text-gz-text-red...text-xs">万</span>
              </div>
            </div>
          </section>
        </a>
        """
        url = f"{self.BASE_URL}/{city_code}/{brand_slug}/{series_slug}/"
        await self._goto_safe(page, url)

        cars_raw = await page.evaluate("""() => {
            const results = [];
            const links = document.querySelectorAll('a[href*="car-detail"]');
            const seen = new Set();
            for (const a of links) {
                const href = a.getAttribute('href') || '';
                const match = href.match(/car-detail\\/(c?\\d+)\\.html/);
                if (!match) continue;
                const clueId = match[1];
                if (seen.has(clueId)) continue;
                seen.add(clueId);

                // 标题：h4 或 img[alt]
                const h4 = a.querySelector('h4');
                const imgEl = a.querySelector('img');
                const title = h4 ? h4.textContent.trim() :
                              (imgEl ? (imgEl.getAttribute('alt') || '').trim() : '');

                // 图片
                const image = imgEl ? (imgEl.getAttribute('src') || '') : '';

                // 描述信息：<p> 内多个 <span>，格式 "2024年｜1.43万公里｜北京"
                const pEl = a.querySelector('p');
                const descSpans = pEl ? pEl.querySelectorAll('span') : [];
                const descParts = [];
                for (const s of descSpans) {
                    const t = s.textContent.trim();
                    if (t && t !== '｜' && t !== '|') descParts.push(t);
                }

                // 价格：font-bold 的 span（数字） + 紧跟的"万"
                let priceValue = '';
                const boldSpan = a.querySelector('.font-bold, [class*="font-bold"]');
                if (boldSpan) {
                    priceValue = boldSpan.textContent.trim();
                }

                // 标签：data-text 属性的 span
                const tagEls = a.querySelectorAll('span[data-text]');
                const tags = [];
                for (const t of tagEls) {
                    const txt = t.getAttribute('data-text') || t.textContent.trim();
                    if (txt) tags.push(txt);
                }

                // 首付信息
                const goldSpan = a.querySelector('[class*="text-gz-text-gold"]');
                const downPayment = goldSpan ? goldSpan.textContent.trim() : '';

                results.push({
                    clue_id: clueId,
                    title: title,
                    image: image,
                    desc_parts: descParts,
                    price_value: priceValue,
                    tags: tags,
                    down_payment: downPayment,
                    detail_url: href.startsWith('http') ? href : 'https://m.guazi.com' + href,
                });
            }
            return results;
        }""")

        if not cars_raw:
            return None

        cars = [self._normalize_car_overview(c, city_code, brand_slug, series_slug) for c in cars_raw]
        cars = [c for c in cars if c and c.get("sku_id")]

        return {
            "cars": cars,
            "count": len(cars),
        }

    async def fetch_all_car_list(self, city_code: str, brand_slug: str, brand_name: str,
                                 series_slug: str, series_name: str,
                                 max_pages: int = 1, browser: Browser = None) -> List[Dict]:
        """
        获取车系下所有车辆概览
        移动端单页最多40条，不支持翻页URL
        """
        should_close = False
        if browser is None:
            pw = await async_playwright().start()
            browser = await pw.chromium.launch(headless=self.headless, slow_mo=self.slow_mo)
            should_close = True

        ctx = await self.create_mobile_context(browser)
        page = await ctx.new_page()
        try:
            result = await self.fetch_car_list_page(page, city_code, brand_slug, series_slug)
            if not result or not result.get("cars"):
                return []
            print(f"      {result['count']} 条")
            return result["cars"]
        finally:
            await page.close()
            await ctx.close()
            if should_close:
                await browser.close()

    def _normalize_car_overview(self, car: Dict, city_code: str, brand_slug: str, series_slug: str) -> Dict:
        """标准化概览数据，对齐懂车帝字段"""
        sku_id = str(car.get("clue_id") or "")

        price_text = car.get("price_value", "")
        sh_price = self._clean_price_wan(price_text)

        tags = car.get("tags") or []

        # 解析描述字段：['2024年', '1.43万公里', '北京']
        desc_parts = car.get("desc_parts") or []
        car_year = desc_parts[0] if len(desc_parts) > 0 else None
        mileage = desc_parts[1] if len(desc_parts) > 1 else None
        source_city = desc_parts[2] if len(desc_parts) > 2 else city_code
        desc_text = " | ".join(desc_parts)

        return {
            "sku_id": sku_id,
            "spu_id": None,
            "title": car.get("title", ""),
            "brand_id": None,
            "brand_name": brand_slug,
            "series_id": None,
            "series_name": series_slug,
            "car_id": None,
            "car_name": car.get("title", ""),
            "car_year": car_year,
            "image": car.get("image", ""),
            "car_source_city": source_city,
            "transfer_cnt": 0,
            "shop_id": "",
            "car_source_type": "guazi",
            "authentication_method": "",
            "tags": tags,
            "detail_url": car.get("detail_url", ""),
            "_encrypted_sh_price": None,
            "_encrypted_official_price": None,
            "_encrypted_mileage": mileage,
            "_encrypted_sub_title": desc_text,
            "sh_price": sh_price,
            "down_payment": car.get("down_payment", ""),
        }

    # ================================================================
    # 阶段4：详情采集 — 移动端详情页
    # ================================================================
    # 移动端详情页HTML结构（已验证）：
    #   <h1 class="summary-title">奔驰C级 2024款 C 260 L 运动版</h1>
    #   <div class="price-current">
    #     <div class="price-now"><span class="value">22.06</span><span class="unit">万</span></div>
    #     <div class="price-ref">新车指导价 38.39 万</div>
    #   </div>
    #   <span>1.43万公里/1年9个月</span>
    #   <span>基础车况极品/理赔0次/过户0次</span>
    #   <span>1.5T</span> 发动机 / <span>自动</span> 变速箱 / <span>国六</span> 排放标准
    #   亮点配置: 后排调节副驾位, 自适应巡航, ...
    #   <img src="https://image-pub.guazistatic.com/...">

    async def fetch_car_detail(self, page: Page, sku_id: str,
                               detail_url: Optional[str] = None) -> Optional[Dict]:
        """获取单辆车的详情数据（移动端）"""
        url = detail_url or f"{self.BASE_URL}/car-detail/{sku_id}.html"
        await self._goto_safe(page, url, timeout=15000)

        raw = await page.evaluate("""() => {
            const result = {};

            // 标题
            const h1 = document.querySelector('h1.summary-title, h1');
            result.title = h1 ? h1.textContent.trim() : '';

            // 价格：.price-now .value + .unit
            const priceVal = document.querySelector('.price-now .value, .price-current .value');
            const priceUnit = document.querySelector('.price-now .unit, .price-current .unit');
            result.sh_price = priceVal ? priceVal.textContent.trim() : '';

            // 新车指导价：.price-ref
            const priceRef = document.querySelector('.price-ref');
            result.official_price_text = priceRef ? priceRef.textContent.trim() : '';

            // 图片
            const imgEls = document.querySelectorAll('img[src*="guazi"]');
            result.images = [];
            const seenImgs = new Set();
            for (const img of imgEls) {
                const src = img.getAttribute('src') || '';
                if (src && !seenImgs.has(src)) {
                    seenImgs.add(src);
                    result.images.push(src);
                }
            }

            // 从页面文本提取参数信息
            const allText = document.body.innerText;
            const lines = allText.split('\\n').map(l => l.trim()).filter(l => l.length > 0);
            result.text_lines = lines.slice(0, 100);

            // 标签：data-text span
            result.tags = [];
            const tagEls = document.querySelectorAll('span[data-text]');
            for (const t of tagEls) {
                const txt = t.getAttribute('data-text') || t.textContent.trim();
                if (txt && txt.length < 30) result.tags.push(txt);
            }

            // 亮点配置
            result.highlights = [];
            const spans = document.querySelectorAll('span');
            let inHighlights = false;
            for (const s of spans) {
                const t = s.textContent.trim();
                if (t === '亮点配置') { inHighlights = true; continue; }
                if (t === '本车卖点') break;
                if (inHighlights && t && t.length < 20 && t.length > 1) {
                    result.highlights.push(t);
                }
            }

            // 车况信息
            result.condition = {};
            for (const line of lines) {
                if (line.includes('万公里')) result.condition.mileage = line;
                if (line.includes('基础车况')) result.condition.basic = line;
                if (line.includes('过户')) result.condition.transfer = line;
                if (line.includes('非泡水')) result.condition.not_flooded = true;
                if (line.includes('非火烧')) result.condition.not_burned = true;
                if (line.includes('非重大事故')) result.condition.no_major_accident = true;
            }

            // 动力参数
            result.power = {};
            for (let i = 0; i < lines.length; i++) {
                if (lines[i] === '发动机' && i > 0) result.power.engine = lines[i-1];
                if (lines[i] === '变速箱' && i > 0) result.power.gearbox = lines[i-1];
                if (lines[i] === '排放标准' && i > 0) result.power.emission = lines[i-1];
                if (lines[i] === '驱动方式' && i > 0) result.power.drive = lines[i-1];
            }

            // 描述/卖点
            result.description = '';
            for (let i = 0; i < lines.length; i++) {
                if (lines[i] === '本车卖点' && i + 1 < lines.length) {
                    result.description = lines[i+1];
                    break;
                }
            }

            return result;
        }""")

        if not raw or not raw.get("title"):
            return None

        return self._normalize_car_detail(raw, sku_id, detail_url or url)

    def _normalize_car_detail(self, raw: Dict, sku_id: str, detail_url: str) -> Dict:
        """标准化详情数据，对齐懂车帝字段"""
        sh_price = self._clean_price_wan(raw.get("sh_price"))

        # 解析新车指导价："新车指导价 38.39 万" 或 "新车指导价38.39万"
        official_text = raw.get("official_price_text", "")
        official_price = None
        m = re.search(r"([\d.]+)", official_text)
        if m:
            official_price = self._clean_price_wan(m.group(1))

        tags = list(set(raw.get("tags", [])))
        images = raw.get("images", [])
        power = raw.get("power", {})
        condition = raw.get("condition", {})
        highlights = raw.get("highlights", [])

        # 从 condition.mileage 提取里程和车龄
        mileage_text = condition.get("mileage", "")

        # 构建 params
        params = {}
        if power.get("engine"):
            params["发动机"] = power["engine"]
        if power.get("gearbox"):
            params["变速箱"] = power["gearbox"]
        if power.get("emission"):
            params["排放标准"] = power["emission"]
        if power.get("drive"):
            params["驱动方式"] = power["drive"]
        if mileage_text:
            params["里程/车龄"] = mileage_text
        if condition.get("basic"):
            params["基础车况"] = condition["basic"]

        detail = {
            "sku_id": str(sku_id),
            "spu_id": "",
            "title": raw.get("title", ""),
            "important_text": "",
            "sh_price": sh_price,
            "official_price": official_price,
            "include_tax_price": None,
            "source_sh_price": None,
            "source_offical_price": None,
            "brand_id": None,
            "brand_name": "",
            "series_id": None,
            "series_name": "",
            "car_id": None,
            "car_name": raw.get("title", ""),
            "year": None,
            "body_color": "",
            "params": params,
            "config": {
                "power": {
                    "capacity": power.get("engine", ""),
                    "horsepower": "",
                    "fuel_form": "",
                    "gearbox": power.get("gearbox", ""),
                    "acceleration_time": "",
                },
                "space": {},
                "manipulation": {
                    "driver_form": power.get("drive", ""),
                    "front_suspension": "",
                    "rear_suspension": "",
                },
            },
            "images": images,
            "highlights": [{"name": h, "icon": ""} for h in highlights],
            "shop": {
                "shop_id": "",
                "shop_name": "",
                "shop_short_name": "",
                "city_name": "",
                "shop_address": "",
                "business_time": "",
                "sales_range": "",
                "sales_car_num": 0,
            },
            "report": {
                "has_report": bool(condition),
                "eva_level": 0,
                "overview": [],
                "not_flooded": condition.get("not_flooded", False),
                "not_burned": condition.get("not_burned", False),
                "no_major_accident": condition.get("no_major_accident", False),
            },
            "financial": {
                "down_payment": None,
                "month_pay": None,
                "repayment_cycle": None,
            },
            "tags": tags,
            "description": raw.get("description", ""),
            "detail_url": detail_url,
            "collected_at": datetime.now().isoformat(),
        }

        return detail


__all__ = ["GuaziAPI"]
