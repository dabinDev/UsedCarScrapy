#!/usr/bin/env python3
"""
懂车帝完整采集流程测试
逐步测试四个阶段的数据采集，理解每个阶段的数据结构：
  阶段1：品牌数据
  阶段2：车系数据
  阶段3：列表概览数据（含详情链接）
  阶段4：详情页数据（详细参数 + 图片）
"""

import asyncio
import json
import os
import re
from datetime import datetime
from playwright.async_api import async_playwright

# 测试输出目录
TEST_OUTPUT_DIR = "test_results"
os.makedirs(TEST_OUTPUT_DIR, exist_ok=True)


async def test_stage1_brands(page):
    """
    阶段1：获取品牌数据
    访问二手车首页，解析品牌列表
    """
    print("\n" + "=" * 70)
    print("🏷️  阶段1：品牌数据采集测试")
    print("=" * 70)

    url = "https://www.dongchedi.com/usedcar/x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x"
    print(f"🔗 访问: {url}")
    await page.goto(url, wait_until="domcontentloaded")
    await page.wait_for_timeout(5000)

    # 获取品牌链接
    brand_links = await page.query_selector_all('a[href*="usedcar/"]')
    print(f"📋 找到 {len(brand_links)} 个可能的品牌链接")

    brands = []
    for link in brand_links:
        try:
            href = await link.get_attribute('href')
            text = (await link.text_content() or "").strip()

            if not href or not text or text == "不限":
                continue

            # 提取品牌ID
            match = re.search(r'-(\d+)-x-330100-1-', href)
            if not match:
                match = re.search(r'x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-(\d+)-x-', href)
            if match:
                brand_id = int(match.group(1))
                if brand_id not in [b["brand_id"] for b in brands]:
                    # 清理品牌名称
                    brand_name = text
                    if ' ' in brand_name:
                        parts = brand_name.split(' ')
                        if len(parts) >= 2 and parts[0] == parts[1]:
                            brand_name = parts[0]

                    brands.append({
                        "brand_id": brand_id,
                        "name": brand_name,
                        "href": href
                    })
        except Exception:
            continue

    brands.sort(key=lambda x: x["brand_id"])
    print(f"✅ 解析到 {len(brands)} 个品牌")

    # 打印前10个品牌
    print("\n📊 品牌数据示例（前10个）：")
    for b in brands[:10]:
        print(f"   ID: {b['brand_id']:>6}  名称: {b['name']:<10}  链接: {b['href']}")

    # 保存
    result = {
        "stage": "brands",
        "timestamp": datetime.now().isoformat(),
        "total": len(brands),
        "data": brands
    }
    with open(f"{TEST_OUTPUT_DIR}/stage1_brands.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"💾 已保存到 {TEST_OUTPUT_DIR}/stage1_brands.json")

    return brands


async def test_stage2_series(page, brand):
    """
    阶段2：获取指定品牌的车系数据
    访问品牌页面，解析车系筛选项
    """
    brand_id = brand["brand_id"]
    brand_name = brand["name"]

    print("\n" + "=" * 70)
    print(f"🚗 阶段2：车系数据采集测试 - {brand_name} (ID: {brand_id})")
    print("=" * 70)

    # 访问品牌页面
    url = f"https://www.dongchedi.com/usedcar/x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-{brand_id}-x-1-1-x-x-x-x-x"
    print(f"🔗 访问: {url}")
    await page.goto(url, wait_until="domcontentloaded")
    await page.wait_for_timeout(5000)

    # ---- 方法1：从页面筛选栏获取车系 ----
    print("\n📋 方法1：从页面筛选栏获取车系...")
    series_from_filter = []

    # 尝试多种选择器查找车系筛选
    filter_selectors = [
        'a[href*="-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-' + str(brand_id) + '-x-"]',
    ]

    # 更通用的方式：查找所有包含品牌ID的链接，从中筛选车系链接
    all_links = await page.query_selector_all(f'a[href*="-{brand_id}-"]')
    print(f"   找到 {len(all_links)} 个包含品牌ID的链接")

    for link in all_links:
        try:
            href = await link.get_attribute('href') or ""
            text = (await link.text_content() or "").strip()

            if not text or text == "不限" or not href:
                continue

            # 车系链接格式: ...x-{brand_id}-x-{series_id}-1-x...
            # 其中 series_id 不是 "1"（那是分页）
            # URL中品牌ID后面紧跟的是 x-{series_id}-{page}
            match = re.search(
                r'-' + str(brand_id) + r'-x-(\d+)-1-',
                href
            )
            if match:
                series_id = int(match.group(1))
                # 排除分页链接（series_id位置可能是页码）
                # 车系ID通常较大，页码通常较小
                if series_id > 10 and series_id not in [s["series_id"] for s in series_from_filter]:
                    series_from_filter.append({
                        "series_id": series_id,
                        "name": text,
                        "href": href,
                        "brand_id": brand_id,
                        "brand_name": brand_name
                    })
        except Exception:
            continue

    print(f"   ✅ 从筛选栏解析到 {len(series_from_filter)} 个车系")

    # ---- 方法2：尝试从API获取车系 ----
    print("\n📋 方法2：尝试从API获取车系...")
    series_from_api = []
    try:
        api_url = f"https://www.dongchedi.com/motor/pc/car/series/list_by_brand?aid=1839&brand_id={brand_id}&car_type=2"
        api_response = await page.evaluate(f"""
            async () => {{
                try {{
                    const resp = await fetch("{api_url}");
                    return await resp.json();
                }} catch(e) {{
                    return {{ error: e.message }};
                }}
            }}
        """)

        if api_response and not api_response.get("error"):
            print(f"   API响应: {json.dumps(api_response, ensure_ascii=False)[:500]}...")

            # 尝试解析API数据
            data = api_response.get("data", {})
            if isinstance(data, dict):
                series_list = data.get("series_list", []) or data.get("list", [])
                for s in series_list:
                    series_from_api.append({
                        "series_id": s.get("series_id") or s.get("id"),
                        "name": s.get("series_name") or s.get("name"),
                        "brand_id": brand_id,
                        "brand_name": brand_name
                    })
            elif isinstance(data, list):
                for s in data:
                    series_from_api.append({
                        "series_id": s.get("series_id") or s.get("id"),
                        "name": s.get("series_name") or s.get("name"),
                        "brand_id": brand_id,
                        "brand_name": brand_name
                    })

            print(f"   ✅ 从API解析到 {len(series_from_api)} 个车系")
        else:
            print(f"   ❌ API请求失败: {api_response}")
    except Exception as e:
        print(f"   ❌ API请求异常: {e}")

    # ---- 方法3：尝试另一个API ----
    print("\n📋 方法3：尝试二手车专用API...")
    series_from_api2 = []
    try:
        api_url2 = f"https://www.dongchedi.com/motor/pc/car/series/list_new?aid=1839&brand_id={brand_id}"
        api_response2 = await page.evaluate(f"""
            async () => {{
                try {{
                    const resp = await fetch("{api_url2}");
                    return await resp.json();
                }} catch(e) {{
                    return {{ error: e.message }};
                }}
            }}
        """)

        if api_response2 and not api_response2.get("error"):
            print(f"   API响应: {json.dumps(api_response2, ensure_ascii=False)[:500]}...")
            data2 = api_response2.get("data", {})
            if isinstance(data2, dict):
                for key in ["series_list", "list", "series", "data"]:
                    if key in data2 and isinstance(data2[key], list):
                        for s in data2[key]:
                            sid = s.get("series_id") or s.get("id")
                            sname = s.get("series_name") or s.get("name")
                            if sid and sname:
                                series_from_api2.append({
                                    "series_id": sid,
                                    "name": sname,
                                    "brand_id": brand_id,
                                    "brand_name": brand_name
                                })
            print(f"   ✅ 从API2解析到 {len(series_from_api2)} 个车系")
        else:
            print(f"   ❌ API2请求失败: {api_response2}")
    except Exception as e:
        print(f"   ❌ API2请求异常: {e}")

    # 合并结果
    all_series = series_from_filter or series_from_api or series_from_api2
    print(f"\n📊 车系数据汇总：共 {len(all_series)} 个车系")
    for s in all_series[:10]:
        print(f"   车系ID: {s.get('series_id', 'N/A'):>8}  名称: {s['name']}")

    # 同时保存原始页面HTML片段用于分析
    page_html = await page.content()
    with open(f"{TEST_OUTPUT_DIR}/stage2_page_source.html", "w", encoding="utf-8") as f:
        f.write(page_html)
    print(f"💾 页面源码已保存到 {TEST_OUTPUT_DIR}/stage2_page_source.html")

    # 保存
    result = {
        "stage": "series",
        "timestamp": datetime.now().isoformat(),
        "brand": brand,
        "methods": {
            "filter": {"count": len(series_from_filter), "data": series_from_filter},
            "api1": {"count": len(series_from_api), "data": series_from_api},
            "api2": {"count": len(series_from_api2), "data": series_from_api2}
        },
        "merged": all_series
    }
    with open(f"{TEST_OUTPUT_DIR}/stage2_series.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"💾 已保存到 {TEST_OUTPUT_DIR}/stage2_series.json")

    return all_series


async def test_stage3_list_overview(page, brand, series=None):
    """
    阶段3：获取列表概览数据
    从列表页获取每辆车的概览信息和详情链接
    """
    brand_id = brand["brand_id"]
    brand_name = brand["name"]

    print("\n" + "=" * 70)
    if series:
        print(f"📋 阶段3：列表概览数据采集测试 - {brand_name} / {series['name']}")
    else:
        print(f"📋 阶段3：列表概览数据采集测试 - {brand_name}")
    print("=" * 70)

    # 构建URL
    if series:
        series_id = series["series_id"]
        url = f"https://www.dongchedi.com/usedcar/x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-{brand_id}-x-{series_id}-1-x-x-x-x-x"
    else:
        url = f"https://www.dongchedi.com/usedcar/x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-{brand_id}-x-1-1-x-x-x-x-x"

    print(f"🔗 访问: {url}")
    await page.goto(url, wait_until="domcontentloaded")
    await page.wait_for_timeout(5000)

    # 获取车辆卡片
    vehicle_cards = await page.query_selector_all('a.usedcar-card_card__3vUrx')
    print(f"📋 找到 {len(vehicle_cards)} 个车辆卡片")

    vehicles = []
    for i, card in enumerate(vehicle_cards[:5]):  # 只测试前5个
        try:
            print(f"\n   🚗 解析第 {i+1} 个车辆卡片...")

            # 获取href（详情链接）
            href = await card.get_attribute('href') or ""
            full_url = f"https://www.dongchedi.com{href}" if href.startswith('/') else href

            # 提取car_id
            car_id_match = re.search(r'/usedcar/(\d+)', href)
            car_id = car_id_match.group(1) if car_id_match else None

            # 获取卡片内所有文本信息
            # 尝试获取标题
            title_el = await card.query_selector('div[class*="title"]')
            title = (await title_el.text_content()).strip() if title_el else ""

            # 尝试获取所有子元素的文本
            all_text = (await card.text_content() or "").strip()

            # 尝试获取图片
            img_el = await card.query_selector('img')
            img_src = await img_el.get_attribute('src') if img_el else None

            # 尝试获取价格相关元素
            price_els = await card.query_selector_all('span[class*="price"], div[class*="price"]')
            prices = []
            for pel in price_els:
                pt = (await pel.text_content() or "").strip()
                if pt:
                    prices.append(pt)

            # 获取卡片的完整HTML结构（用于分析）
            card_html = await card.evaluate('el => el.outerHTML')

            vehicle = {
                "index": i + 1,
                "car_id": car_id,
                "href": href,
                "detail_url": full_url,
                "title": title,
                "all_text": all_text,
                "prices": prices,
                "thumbnail": img_src,
                "card_html_length": len(card_html)
            }
            vehicles.append(vehicle)

            print(f"      car_id: {car_id}")
            print(f"      标题: {title}")
            print(f"      详情链接: {full_url}")
            print(f"      缩略图: {img_src[:80] if img_src else 'N/A'}...")
            print(f"      价格: {prices}")
            print(f"      全文: {all_text[:100]}...")

        except Exception as e:
            print(f"      ❌ 解析失败: {e}")
            continue

    # 保存第一个卡片的完整HTML用于分析
    if vehicle_cards:
        first_card_html = await vehicle_cards[0].evaluate('el => el.outerHTML')
        with open(f"{TEST_OUTPUT_DIR}/stage3_card_sample.html", "w", encoding="utf-8") as f:
            f.write(first_card_html)
        print(f"\n💾 卡片HTML样本已保存到 {TEST_OUTPUT_DIR}/stage3_card_sample.html")

    # 保存
    result = {
        "stage": "list_overview",
        "timestamp": datetime.now().isoformat(),
        "brand": brand,
        "series": series,
        "url": url,
        "total_cards": len(vehicle_cards),
        "parsed_count": len(vehicles),
        "data": vehicles
    }
    with open(f"{TEST_OUTPUT_DIR}/stage3_list_overview.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"💾 已保存到 {TEST_OUTPUT_DIR}/stage3_list_overview.json")

    return vehicles


async def test_stage4_detail(page, vehicle):
    """
    阶段4：获取详情页数据
    访问车辆详情页，获取详细参数和图片
    """
    car_id = vehicle.get("car_id")
    detail_url = vehicle.get("detail_url")
    title = vehicle.get("title", "未知车型")

    print("\n" + "=" * 70)
    print(f"🔍 阶段4：详情页数据采集测试 - {title}")
    print("=" * 70)
    print(f"🔗 访问: {detail_url}")

    await page.goto(detail_url, wait_until="domcontentloaded")
    await page.wait_for_timeout(5000)

    detail_data = {
        "car_id": car_id,
        "detail_url": detail_url,
        "title": title,
        "basic_info": {},
        "params": {},
        "images": [],
        "raw_sections": {}
    }

    # ---- 1. 获取基本信息 ----
    print("\n📋 1. 获取基本信息...")
    try:
        # 获取页面标题
        page_title = await page.title()
        detail_data["page_title"] = page_title
        print(f"   页面标题: {page_title}")

        # 尝试获取价格
        price_selectors = [
            'span[class*="price"]',
            'div[class*="price"]',
            '[class*="Price"]',
            '[class*="amount"]'
        ]
        for sel in price_selectors:
            els = await page.query_selector_all(sel)
            for el in els:
                text = (await el.text_content() or "").strip()
                if text and ('万' in text or re.search(r'\d', text)):
                    detail_data["basic_info"]["price_text"] = text
                    print(f"   价格: {text}")
                    break
            if detail_data["basic_info"].get("price_text"):
                break

    except Exception as e:
        print(f"   ❌ 获取基本信息失败: {e}")

    # ---- 2. 获取详细参数 ----
    print("\n📋 2. 获取详细参数...")
    try:
        # 尝试多种参数区域选择器
        param_selectors = [
            'div[class*="param"]',
            'div[class*="info"]',
            'div[class*="detail"]',
            'div[class*="config"]',
            'table',
            'dl',
            'div[class*="basic"]',
            'div[class*="spec"]'
        ]

        for sel in param_selectors:
            els = await page.query_selector_all(sel)
            if els:
                print(f"   选择器 '{sel}' 找到 {len(els)} 个元素")
                for j, el in enumerate(els[:3]):  # 只看前3个
                    text = (await el.text_content() or "").strip()
                    if text and len(text) > 10:
                        key = f"{sel}_{j}"
                        detail_data["raw_sections"][key] = text[:500]
                        print(f"      [{j}] {text[:150]}...")

        # 尝试查找 key-value 对
        kv_selectors = [
            'div[class*="item"]',
            'li[class*="item"]',
            'div[class*="row"]',
            'span[class*="label"]'
        ]

        params_found = {}
        for sel in kv_selectors:
            els = await page.query_selector_all(sel)
            for el in els:
                text = (await el.text_content() or "").strip()
                # 尝试匹配 "标签：值" 或 "标签 值" 格式
                if '：' in text or ':' in text:
                    parts = re.split(r'[：:]', text, 1)
                    if len(parts) == 2:
                        k, v = parts[0].strip(), parts[1].strip()
                        if k and v and len(k) < 20:
                            params_found[k] = v

        if params_found:
            detail_data["params"] = params_found
            print(f"\n   ✅ 解析到 {len(params_found)} 个参数:")
            for k, v in list(params_found.items())[:15]:
                print(f"      {k}: {v}")

    except Exception as e:
        print(f"   ❌ 获取参数失败: {e}")

    # ---- 3. 获取图片 ----
    print("\n📋 3. 获取图片...")
    try:
        # 获取所有图片
        img_els = await page.query_selector_all('img')
        all_images = []
        for img in img_els:
            src = await img.get_attribute('src') or ""
            alt = await img.get_attribute('alt') or ""
            # 过滤掉小图标和无关图片
            if src and ('car' in src.lower() or 'auto' in src.lower() or
                       'img' in src.lower() or 'photo' in src.lower() or
                       '.jpg' in src.lower() or '.png' in src.lower() or
                       '.webp' in src.lower()):
                # 过滤掉太小的图片（通常是图标）
                width = await img.get_attribute('width')
                if width and width.isdigit() and int(width) < 50:
                    continue
                all_images.append({
                    "src": src,
                    "alt": alt
                })

        # 去重
        seen = set()
        unique_images = []
        for img in all_images:
            if img["src"] not in seen:
                seen.add(img["src"])
                unique_images.append(img)

        detail_data["images"] = unique_images
        print(f"   ✅ 找到 {len(unique_images)} 张图片")
        for img in unique_images[:10]:
            print(f"      {img['alt'] or '无alt'}: {img['src'][:80]}...")

        # 尝试查找图片轮播/画廊
        gallery_selectors = [
            'div[class*="gallery"]',
            'div[class*="swiper"]',
            'div[class*="carousel"]',
            'div[class*="slider"]',
            'div[class*="photo"]',
            'div[class*="image-list"]'
        ]
        for sel in gallery_selectors:
            gallery = await page.query_selector(sel)
            if gallery:
                gallery_imgs = await gallery.query_selector_all('img')
                print(f"   🖼️ 图片画廊 '{sel}' 包含 {len(gallery_imgs)} 张图片")

    except Exception as e:
        print(f"   ❌ 获取图片失败: {e}")

    # ---- 4. 保存页面快照用于分析 ----
    print("\n📋 4. 保存页面快照...")
    try:
        # 保存完整页面HTML
        page_html = await page.content()
        with open(f"{TEST_OUTPUT_DIR}/stage4_detail_page.html", "w", encoding="utf-8") as f:
            f.write(page_html)
        print(f"   💾 详情页HTML已保存到 {TEST_OUTPUT_DIR}/stage4_detail_page.html")

        # 截图
        await page.screenshot(path=f"{TEST_OUTPUT_DIR}/stage4_detail_screenshot.png", full_page=True)
        print(f"   📸 详情页截图已保存到 {TEST_OUTPUT_DIR}/stage4_detail_screenshot.png")

    except Exception as e:
        print(f"   ❌ 保存快照失败: {e}")

    # ---- 5. 尝试通过API获取详情 ----
    print("\n📋 5. 尝试通过API获取详情...")
    try:
        if car_id:
            api_urls = [
                f"https://www.dongchedi.com/motor/pc/used_car/detail?car_id={car_id}",
                f"https://www.dongchedi.com/motor/pc/used_car/info?car_id={car_id}",
            ]
            for api_url in api_urls:
                api_resp = await page.evaluate(f"""
                    async () => {{
                        try {{
                            const resp = await fetch("{api_url}");
                            return await resp.json();
                        }} catch(e) {{
                            return {{ error: e.message }};
                        }}
                    }}
                """)
                if api_resp and not api_resp.get("error"):
                    print(f"   ✅ API成功: {api_url}")
                    # 保存API响应
                    api_filename = api_url.split("/")[-1].split("?")[0]
                    with open(f"{TEST_OUTPUT_DIR}/stage4_api_{api_filename}.json", "w", encoding="utf-8") as f:
                        json.dump(api_resp, f, ensure_ascii=False, indent=2)
                    print(f"   💾 API响应已保存到 {TEST_OUTPUT_DIR}/stage4_api_{api_filename}.json")

                    # 简要展示API数据结构
                    print(f"   📊 API数据结构:")
                    if isinstance(api_resp.get("data"), dict):
                        for key in list(api_resp["data"].keys())[:20]:
                            val = api_resp["data"][key]
                            val_str = str(val)[:100] if val else "null"
                            print(f"      {key}: {val_str}")
                    detail_data["api_data"] = api_resp
                else:
                    print(f"   ❌ API失败: {api_url} -> {str(api_resp)[:200]}")
    except Exception as e:
        print(f"   ❌ API请求异常: {e}")

    # 保存汇总结果
    # 移除过大的字段以便查看
    save_data = {k: v for k, v in detail_data.items() if k != "api_data"}
    save_data["api_data_saved_separately"] = bool(detail_data.get("api_data"))

    result = {
        "stage": "detail",
        "timestamp": datetime.now().isoformat(),
        "data": save_data
    }
    with open(f"{TEST_OUTPUT_DIR}/stage4_detail.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n💾 已保存到 {TEST_OUTPUT_DIR}/stage4_detail.json")

    return detail_data


async def main():
    """主测试流程"""
    print("🚗 懂车帝完整采集流程测试")
    print("=" * 70)
    print("测试目标：理解每个阶段的数据结构和可用字段")
    print(f"测试时间：{datetime.now().isoformat()}")
    print(f"输出目录：{TEST_OUTPUT_DIR}/")
    print("=" * 70)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        try:
            # ========== 阶段1：品牌 ==========
            brands = await test_stage1_brands(page)
            if not brands:
                print("❌ 未获取到品牌数据，终止测试")
                return

            # 选择一个中等数据量的品牌进行后续测试（如"奇瑞"或列表中的第一个）
            test_brand = None
            for preferred in ["奇瑞", "吉利", "长安", "比亚迪"]:
                test_brand = next((b for b in brands if preferred in b["name"]), None)
                if test_brand:
                    break
            if not test_brand:
                test_brand = brands[0]

            print(f"\n🎯 选择测试品牌: {test_brand['name']} (ID: {test_brand['brand_id']})")

            # ========== 阶段2：车系 ==========
            series_list = await test_stage2_series(page, test_brand)

            # 选择第一个车系进行后续测试
            test_series = series_list[0] if series_list else None
            if test_series:
                print(f"\n🎯 选择测试车系: {test_series['name']} (ID: {test_series.get('series_id', 'N/A')})")

            # ========== 阶段3：列表概览 ==========
            vehicles = await test_stage3_list_overview(page, test_brand, test_series)
            if not vehicles:
                print("❌ 未获取到列表数据，终止测试")
                return

            # 选择第一辆车进行详情测试
            test_vehicle = vehicles[0]
            print(f"\n🎯 选择测试车辆: {test_vehicle.get('title', 'N/A')} (ID: {test_vehicle.get('car_id', 'N/A')})")

            # ========== 阶段4：详情 ==========
            detail = await test_stage4_detail(page, test_vehicle)

            # ========== 汇总 ==========
            print("\n" + "=" * 70)
            print("📊 测试汇总")
            print("=" * 70)
            print(f"阶段1 - 品牌: {len(brands)} 个品牌")
            print(f"阶段2 - 车系: {len(series_list)} 个车系 ({test_brand['name']})")
            print(f"阶段3 - 列表: {len(vehicles)} 辆车概览")
            print(f"阶段4 - 详情: 参数 {len(detail.get('params', {}))} 个, 图片 {len(detail.get('images', []))} 张")
            print(f"\n📁 所有测试结果已保存到 {TEST_OUTPUT_DIR}/ 目录")
            print("   - stage1_brands.json        品牌数据")
            print("   - stage2_series.json         车系数据")
            print("   - stage2_page_source.html    车系页面源码")
            print("   - stage3_list_overview.json  列表概览数据")
            print("   - stage3_card_sample.html    卡片HTML样本")
            print("   - stage4_detail.json         详情数据")
            print("   - stage4_detail_page.html    详情页源码")
            print("   - stage4_detail_screenshot.png 详情页截图")
            print("   - stage4_api_*.json          API响应数据")

        except Exception as e:
            print(f"\n❌ 测试过程出错: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await browser.close()

    print("\n✅ 测试完成！")


if __name__ == "__main__":
    asyncio.run(main())
