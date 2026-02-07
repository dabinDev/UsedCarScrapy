"""
懂车帝精准爬虫 - 针对特定HTML结构
"""

import asyncio
import json
import os
import re
import time
import base64
from datetime import datetime
from playwright.async_api import async_playwright
import requests

print("🚗 懂车帝精准爬虫")
print("="*60)

class BaiduIOCR:
    """百度iOCR客户端"""
    def __init__(self, app_id, api_key, secret_key):
        self.app_id = app_id
        self.api_key = api_key
        self.secret_key = secret_key
        self.access_token = None
        self.token_expires_at = 0
    
    def get_access_token(self):
        """获取百度API访问令牌"""
        if self.access_token and time.time() < self.token_expires_at:
            return self.access_token
        
        url = "https://aip.baidubce.com/oauth/2.0/token"
        params = {
            "grant_type": "client_credentials",
            "client_id": self.api_key,
            "client_secret": self.secret_key
        }
        
        try:
            response = requests.post(url, params=params, timeout=10)
            result = response.json()
            
            if "access_token" in result:
                self.access_token = result["access_token"]
                self.token_expires_at = time.time() + result.get("expires_in", 2592000) - 60
                return self.access_token
            else:
                return None
                
        except Exception as e:
            return None
    
    def recognize_image(self, image_path):
        """使用百度iOCR识别图片"""
        access_token = self.get_access_token()
        if not access_token:
            return None
        
        url = f"https://aip.baidubce.com/rest/2.0/ocr/v1/general_basic?access_token={access_token}"
        
        try:
            with open(image_path, "rb") as f:
                image_data = f.read()
            
            image_b64 = base64.b64encode(image_data).decode()
            
            data = {
                "image": image_b64,
                "language_ch": "CHN_ENG"
            }
            
            headers = {
                "Content-Type": "application/x-www-form-urlencoded"
            }
            
            response = requests.post(url, headers=headers, data=data, timeout=10)
            result = response.json()
            
            if "error_code" in result:
                return None
            
            words_result = result.get("words_result", [])
            recognized_text = "\n".join([item["words"] for item in words_result])
            
            return {
                "success": True,
                "text": recognized_text,
                "raw_result": result
            }
            
        except Exception as e:
            return None

class DongchediPreciseCrawler:
    def __init__(self):
        self.ocr_client = BaiduIOCR(
            app_id="7432271",
            api_key="VvC2noYSwA3BVXehBsSGzw6f", 
            secret_key="hROkWlBeefuTgtIsnf6m3pH5M99zLfzz"
        )
        self.all_vehicles = []
        self.screenshot_dir = "screenshots"
        
        # 品牌信息映射 - 将通过动态获取初始化
        self.brands = []
        
        # 创建目录
        os.makedirs(self.screenshot_dir, exist_ok=True)
        os.makedirs("data", exist_ok=True)
    
    async def get_all_brands(self):
        """获取所有品牌信息 - 只从热门页面获取"""
        print("🔍 正在获取所有品牌信息...")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            try:
                # 访问二手车页面
                await page.goto("https://www.dongchedi.com/usedcar/x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x", wait_until="domcontentloaded")
                await page.wait_for_timeout(5000)
                
                # 只从热门页面获取品牌
                print("📋 获取热门品牌...")
                
                # 等待品牌列表加载
                await page.wait_for_timeout(3000)
                
                # 获取品牌链接 - 使用多种选择器尝试
                selectors = [
                    'a[href*="-330100-"]',
                    'a[href*="x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-"]',
                    'div[ref*="155"] a',
                    'div[ref*="17"] a',
                    'a[href*="usedcar/"]'
                ]
                
                brand_items = []
                for selector in selectors:
                    brand_items = await page.query_selector_all(selector)
                    if len(brand_items) > 0:
                        break
                
                for item in brand_items:
                    try:
                        href = await item.get_attribute('href')
                        text = await item.text_content()
                        
                        if href and text and text.strip():
                            # 过滤掉“不限”和其他非品牌链接
                            if text.strip() == "不限":
                                continue
                            
                            # 提取品牌ID - 支持多种URL格式
                            # 格式1: x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-{brand_id}-x-330100-1-x-x-x-x-x
                            brand_id = None
                            
                            # 尝试从URL中提取品牌ID
                            match = re.search(r'-(\d+)-x-330100-1-', href)
                            if match:
                                brand_id = int(match.group(1))
                            else:
                                # 尝试其他格式
                                match = re.search(r'-(\d+)-x-', href)
                                if match:
                                    brand_id = int(match.group(1))
                            
                            if brand_id and brand_id not in [b["brand_id"] for b in self.brands]:
                                # 清理品牌名称
                                brand_name = text.strip()
                                # 移除重复的品牌名（如“奔驰 奔驰”）
                                if ' ' in brand_name:
                                    parts = brand_name.split(' ')
                                    if len(parts) >= 2 and parts[0] == parts[1]:
                                        brand_name = parts[0]
                                
                                self.brands.append({
                                    "brand_id": brand_id,
                                    "name": brand_name
                                })
                                print(f"      ✅ 找到品牌: {brand_name} (ID: {brand_id})")
                    
                    except Exception as e:
                        continue
                
                print(f"✅ 热门页面找到 {len(self.brands)} 个品牌")
                
                # 按品牌ID排序
                self.brands.sort(key=lambda x: x["brand_id"])
                
                print(f"🎉 总共获取到 {len(self.brands)} 个品牌")
                
                # 保存品牌信息到文件
                try:
                    with open("data/all_brands.json", "w", encoding="utf-8") as f:
                        json.dump(self.brands, f, ensure_ascii=False, indent=2)
                    print(f"💾 品牌信息已保存到: data/all_brands.json")
                except Exception as save_error:
                    print(f"⚠️ 保存品牌信息失败: {save_error}")
                
            except Exception as e:
                print(f"❌ 获取品牌信息失败: {e}")
            finally:
                await browser.close()
        
        return self.brands
    
    async def calculate_brand_total_data(self, brand_id, brand_name):
        """计算指定品牌的总数据量"""
        print(f"🔍 正在计算 {brand_name} 品牌的总数据量...")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            try:
                # 访问品牌第一页 - 使用正确的URL格式，所有筛选条件为不限，地区为杭州（330100）
                url = f"https://www.dongchedi.com/usedcar/x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-{brand_id}-x-1-1-x-x-x-x-x"
                await page.goto(url, wait_until="domcontentloaded")
                await page.wait_for_timeout(5000)
                
                # 获取当前页的车辆数量
                vehicle_cards = await page.query_selector_all('a.usedcar-card_card__3vUrx')
                current_page_count = len(vehicle_cards)
                
                # 查找分页信息
                pagination_info = await self.get_pagination_info(page)
                
                if pagination_info:
                    total_pages = pagination_info.get('total_pages', 1)
                    current_page = pagination_info.get('current_page', 1)
                    
                    # 计算数据量范围 - 修正逻辑
                    if total_pages > 1:
                        # 前面所有完整页面的数据量
                        full_pages_data = (total_pages - 1) * current_page_count
                        # 最后一页数据量未知，范围是1到current_page_count
                        min_total = full_pages_data + 1
                        max_total = full_pages_data + current_page_count
                        calculation_method = "range_estimation"
                    else:
                        # 只有1页的情况
                        min_total = current_page_count
                        max_total = current_page_count
                        calculation_method = "direct_count"
                    
                    print(f"📊 {brand_name} 数据量估算:")
                    print(f"  • 当前页: {current_page} 页")
                    print(f"  • 总页数: {total_pages} 页")
                    print(f"  • 每页约: {current_page_count} 条")
                    if total_pages > 1:
                        print(f"  • 数据范围: {min_total}-{max_total} 条")
                        print(f"  • 前面完整页: {(total_pages-1)} * {current_page_count} = {full_pages_data} 条")
                        print(f"  • 最后一页: 1-{current_page_count} 条")
                    else:
                        print(f"  • 总数据量: {current_page_count} 条")
                    
                    return {
                        'total_pages': total_pages,
                        'current_page_count': current_page_count,
                        'min_total_data': min_total,
                        'max_total_data': max_total,
                        'data_range': f"{min_total}-{max_total}",
                        'calculation_method': calculation_method,
                        'current_page': current_page
                    }
                else:
                    # 没有分页，只有当前页数据
                    print(f"📊 {brand_name} 数据量估算:")
                    print(f"  • 当前页: 1 页")
                    print(f"  • 总页数: 1 页")
                    print(f"  • 每页: {current_page_count} 条")
                    print(f"  • 总数据量: {current_page_count} 条")
                    
                    return {
                        'total_pages': 1,
                        'current_page_count': current_page_count,
                        'min_total_data': current_page_count,
                        'max_total_data': current_page_count,
                        'data_range': f"{current_page_count}",
                        'calculation_method': 'direct_count',
                        'current_page': 1
                    }
                    
            except Exception as e:
                print(f"❌ 计算 {brand_name} 数据量失败: {e}")
                return None
            finally:
                await browser.close()
    
    async def get_pagination_info(self, page):
        """获取分页信息 - 改进版本"""
        try:
            # 等待页面加载
            await page.wait_for_timeout(2000)
            
            # 查找分页组件 - 使用正确的选择器
            pagination_selectors = [
                'div[class*="jsx-1325911405"]',
                'div[class*="pagination"]',
                'ul[class*="pagination"]',
                '.pagination'
            ]
            
            pagination_element = None
            for selector in pagination_selectors:
                pagination_element = await page.query_selector(selector)
                if pagination_element:
                    break
            
            if pagination_element:
                # 获取所有分页链接，不限制数量
                page_links = await pagination_element.query_selector_all('a')
                pages = []
                
                print(f"    📄 找到 {len(page_links)} 个分页链接")
                
                for link in page_links:
                    href = await link.get_attribute('href')
                    text = await link.text_content()
                    
                    # 检查href是否包含正确的分页格式
                    if href and '-1-1-' in href:
                        # 从href中提取页码
                        parts = href.split('-1-1-')
                        if len(parts) > 1:
                            page_part = parts[1].split('-')[0]
                            if page_part.isdigit():
                                pages.append(int(page_part))
                                print(f"      📄 从href提取页码: {page_part}")
                    
                    # 同时从文本中提取页码
                    if text and text.strip().isdigit():
                        page_num = int(text.strip())
                        if page_num not in pages:
                            pages.append(page_num)
                            print(f"      📄 从文本提取页码: {page_num}")
                
                print(f"    📊 提取到的页码: {sorted(pages)}")
                
                if pages:
                    total_pages = max(pages)
                    current_page = 1  # 默认当前页为1
                    
                    # 尝试找到当前页（通过检查哪个链接没有href或href指向当前页）
                    for link in page_links:
                        href = await link.get_attribute('href')
                        text = await link.text_content()
                        if text and text.strip().isdigit():
                            page_num = int(text.strip())
                            # 检查是否是当前页（通常当前页的样式不同或没有href）
                            class_attr = await link.get_attribute('class')
                            if class_attr and ('active' in class_attr.lower() or 'current' in class_attr.lower()):
                                current_page = page_num
                                break
                    
                    return {'total_pages': total_pages, 'pages': sorted(set(pages)), 'current_page': current_page}
            
            # 如果没有找到分页组件，尝试通过检查下一页是否存在来判断
            try:
                # 检查第2页是否有数据 - 使用正确的URL格式
                test_url = "https://www.dongchedi.com/usedcar/x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-10409-x-1-2-x-x-x-x-x"
                await page.goto(test_url, wait_until="domcontentloaded")
                await page.wait_for_timeout(2000)
                
                # 检查是否有车辆数据
                vehicle_cards = await page.query_selector_all('a.usedcar-card_card__3vUrx')
                
                if vehicle_cards:
                    # 有数据，继续检查更多页面
                    max_pages = 2
                    
                    # 尝试检查更多页面 - 使用正确的URL格式
                    for page_num in range(3, 11):  # 最多检查10页
                        test_url = f"https://www.dongchedi.com/usedcar/x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-10409-x-1-{page_num}-x-x-x-x-x"
                        await page.goto(test_url, wait_until="domcontentloaded")
                        await page.wait_for_timeout(1500)
                        
                        cards = await page.query_selector_all('a.usedcar-card_card__3vUrx')
                        if cards:
                            max_pages = page_num
                        else:
                            break
                    
                    return {
                        'total_pages': max_pages,
                        'pages': list(range(1, max_pages + 1))
                    }
                else:
                    # 第2页没有数据，只有1页
                    return None
                    
            except Exception as e:
                print(f"    ⚠️ 检查分页时出错: {e}")
                return None
                
        except Exception as e:
            print(f"    ❌ 获取分页信息失败: {e}")
            return None
    
    def extract_car_id_from_href(self, href):
        """从href中提取车辆ID"""
        if not href:
            return None
        
        # 从 /usedcar/22563498 提取 22563498
        match = re.search(r'/usedcar/(\d+)', href)
        if match:
            return match.group(1)
        
        return None
    
    async def crawl_brand_with_limit(self, brand_id, brand_name, data_limit=-1):
        """按数据量限制爬取品牌数据"""
        print(f"🎯 开始爬取 {brand_name} 品牌，目标数据量: {'全部' if data_limit == -1 else f'{data_limit}条'}")
        
        # 先计算总数据量
        data_info = await self.calculate_brand_total_data(brand_id, brand_name)
        
        if not data_info:
            print(f"❌ 无法获取 {brand_name} 的数据信息")
            return []
        
        min_total_data = data_info['min_total_data']
        current_page_count = data_info['current_page_count']
        
        # 计算需要爬取的页数
        if data_limit == -1:
            # 全部数据
            pages_to_crawl = data_info['total_pages']
            target_data = min_total_data
        else:
            # 指定数据量
            target_data = data_limit
            pages_to_crawl = (data_limit + current_page_count - 1) // current_page_count  # 向上取整
            pages_to_crawl = min(pages_to_crawl, data_info['total_pages'])  # 不超过总页数
        
        print(f"📋 爬取计划:")
        print(f"  • 目标数据: {target_data} 条")
        print(f"  • 预计页数: {pages_to_crawl} 页")
        print(f"  • 每页约: {current_page_count} 条")
        
        all_vehicles_data = []
        collected_data = 0
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)  # 保持浏览器打开
            page = await browser.new_page()
            
            try:
                for page_num in range(1, pages_to_crawl + 1):
                    print(f"\n📄 正在爬取 {brand_name} 第 {page_num}/{pages_to_crawl} 页...")
                    
                    # 构建URL - 使用正确的分页格式
                    url = f"https://www.dongchedi.com/usedcar/x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-{brand_id}-x-1-{page_num}-x-x-x-x-x"
                    
                    await page.goto(url, wait_until="networkidle")
                    await page.wait_for_timeout(3000)
                    
                    # 获取车辆卡片
                    vehicle_cards = await page.query_selector_all('a.usedcar-card_card__3vUrx')
                    
                    if not vehicle_cards:
                        print(f"❌ 第 {page_num} 页未找到车辆卡片")
                        break
                    
                    print(f"✅ 第 {page_num} 页找到 {len(vehicle_cards)} 个车辆卡片")
                    
                    # 处理当前页的车辆
                    page_vehicles = []
                    for i, card in enumerate(vehicle_cards):
                        # 检查是否达到目标数据量
                        if data_limit != -1 and collected_data >= data_limit:
                            print(f"🎯 已达到目标数据量 {data_limit} 条，停止爬取")
                            break
                        
                        try:
                            href = await card.get_attribute('href')
                            title_element = await card.query_selector('div[class*="title"]')
                            title = await title_element.text_content() if title_element else ""
                            
                            car_id = self.extract_car_id_from_href(href)
                            filename = f"{page_num:02d}-{i+1:02d}"
                            screenshot_path = f"{self.screenshot_dir}/{filename}.png"
                            
                            # 截图
                            await card.screenshot(path=screenshot_path)
                            
                            vehicle_info = {
                                "filename": filename,
                                "car_id": car_id,
                                "href": href,
                                "title": title,
                                "brand_id": brand_id,
                                "brand_name": brand_name,
                                "screenshot_path": screenshot_path,
                                "page": page_num,
                                "index": i + 1,
                                "crawl_time": datetime.now().isoformat()
                            }
                            
                            page_vehicles.append(vehicle_info)
                            collected_data += 1
                            
                            print(f"  🚗 {collected_data}/{target_data}: {title}")
                            
                        except Exception as e:
                            print(f"    ⚠️ 处理卡片 {i+1} 失败: {e}")
                            continue
                    
                    all_vehicles_data.extend(page_vehicles)
                    
                    # 如果达到目标数据量，退出循环
                    if data_limit != -1 and collected_data >= data_limit:
                        break
                    
                    # 滚动到底部准备翻页
                    await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                    await page.wait_for_timeout(1000)
                    
                print(f"\n🎉 {brand_name} 爬取完成！共获取 {len(all_vehicles_data)} 条数据")
                
            except Exception as e:
                print(f"❌ 爬取 {brand_name} 失败: {e}")
            finally:
                # 不关闭浏览器，保持打开状态
                print(f"🌐 浏览器保持打开状态，可手动查看页面")
                
        return all_vehicles_data
    
    async def crawl_page(self, page_num, brand_id=None):
        """爬取指定页面和品牌 - 所有筛选条件不限，地区全国"""
        if brand_id:
            # 针对特定品牌的URL - 所有条件不限，地区杭州(330100)
            # URL格式: /usedcar/x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-{brand_id}-x-1-{page}-x-x-x-x-x
            url = f"https://www.dongchedi.com/usedcar/x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-{brand_id}-x-1-{page_num}-x-x-x-x-x"
            brand_name = next((b["name"] for b in self.brands if b["brand_id"] == brand_id), f"品牌{brand_id}")
            print(f"📄 正在爬取 {brand_name} 第 {page_num} 页 (全国，不限条件)...")
        else:
            # 全部车型的URL - 所有条件不限，地区杭州
            url = f"https://www.dongchedi.com/usedcar/x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-1-{page_num}-x-x-x-x-x"
            print(f"📄 正在爬取全部车型第 {page_num} 页 (全国，不限条件)...")
            
        print(f"🔗 URL: {url}")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            page = await browser.new_page()
            
            try:
                await page.goto(url, wait_until="networkidle")
                await page.wait_for_timeout(3000)
                
                # 精准查找车辆卡片
                await page.wait_for_selector('a.usedcar-card_card__3vUrx', timeout=10000)
                
                # 获取所有车辆卡片
                vehicle_cards = await page.query_selector_all('a.usedcar-card_card__3vUrx')
                
                if not vehicle_cards:
                    brand_name = next((b["name"] for b in self.brands if b["brand_id"] == brand_id), f"品牌{brand_id}") if brand_id else "全部"
                    print(f"❌ {brand_name} 第 {page_num} 页未找到车辆卡片")
                    await browser.close()
                    return []
                
                print(f"✅ 找到 {len(vehicle_cards)} 个车辆卡片")
                
                vehicles_data = []
                
                for i, card in enumerate(vehicle_cards):
                    try:
                        print(f"  🚗 处理第 {i+1} 个车辆卡片...")
                        
                        href = await card.get_attribute('href')
                        title_element = await card.query_selector('div[class*="title"]')
                        title = await title_element.text_content() if title_element else ""
                        
                        print(f"    📝 车型: {title}")
                        
                        car_id = self.extract_car_id_from_href(href)
                        filename = f"{page_num:02d}-{i+1:02d}"
                        screenshot_path = f"{self.screenshot_dir}/{filename}.png"
                        
                        # 截图
                        await card.screenshot(path=screenshot_path)
                        print(f"    📸 截图已保存: {screenshot_path}")
                        
                        # 保存车辆信息
                        vehicle_info = {
                            "filename": filename,
                            "car_id": car_id,
                            "href": href,
                            "title": title,
                            "brand_id": brand_id,
                            "brand_name": brand_name if brand_id else "全部",
                            "screenshot_path": screenshot_path,
                            "page": page_num,
                            "index": i + 1,
                            "crawl_time": datetime.now().isoformat()
                        }
                        
                        vehicles_data.append(vehicle_info)
                        
                    except Exception as e:
                        print(f"    ⚠️ 处理卡片 {i+1} 失败: {e}")
                        continue
                
                await browser.close()
                return vehicles_data
                
            except Exception as e:
                brand_name = next((b["name"] for b in self.brands if b["brand_id"] == brand_id), f"品牌{brand_id}") if brand_id else "全部"
                print(f"❌ {brand_name} 第 {page_num} 页爬取失败: {e}")
                await browser.close()
                return []
    
    def parse_vehicle_info(self, ocr_result, vehicle_info):
        """解析OCR结果 - 专注于价格提取"""
        if not ocr_result or not ocr_result.get("success"):
            return {
                "filename": vehicle_info["filename"],
                "car_id": vehicle_info["car_id"],
                "href": vehicle_info["href"],
                "title": vehicle_info["title"],
                "model_name": vehicle_info["title"],
                "year": "",
                "mileage": "",
                "location": "",
                "transfer_count": "",
                "used_price": "",
                "new_car_price": "",
                "ocr_text": "",
                "parse_success": False
            }
        
        text = ocr_result["text"]
        print(f"    📝 OCR结果: {text}")
        
        # 基础信息
        car_data = {
            "filename": vehicle_info["filename"],
            "car_id": vehicle_info["car_id"],
            "href": vehicle_info["href"],
            "title": vehicle_info["title"],
            "model_name": vehicle_info["title"],
            "year": "",
            "mileage": "",
            "location": "",
            "transfer_count": "",
            "used_price": "",
            "new_car_price": "",
            "ocr_text": text,
            "parse_success": True
        }
        
        # 专注于价格提取
        lines = text.split('\n')
        used_price = ""
        new_car_price = ""
        
        # 第一遍：查找明确的新车指导价行
        for line in lines:
            line = line.strip()
            if '新车指导价' in line:
                # 匹配 "9.08万新车指导价：16.29万" 格式
                both_match = re.search(r'(\d+\.?\d*)万\s*新车指导价[：:]\s*(\d+\.?\d*)万', line)
                if both_match:
                    used_price = f"{both_match.group(1)}万"      # 第一个是二手车价格
                    new_car_price = f"{both_match.group(2)}万"   # 第二个是新车指导价
                    print(f"    💰 二手车价格: {used_price}")
                    print(f"    🆕 新车指导价: {new_car_price}")
                    break
                
                # 匹配 "新车指导价：16.29万" 格式
                new_price_match = re.search(r'新车指导价[：:]\s*(\d+\.?\d*)万', line)
                if new_price_match:
                    new_car_price = f"{new_price_match.group(1)}万"
                    # 检查行中是否有另一个价格（二手车价格）
                    other_prices = re.findall(r'(\d+\.?\d*)万', line)
                    if len(other_prices) >= 2:
                        # 第一个价格通常是二手车价格
                        used_price = f"{other_prices[0]}万"
                    print(f"    🆕 新车指导价: {new_car_price}")
                    if used_price:
                        print(f"    💰 二手车价格: {used_price}")
                break
        
        # 第二遍：如果没找到二手车价格，单独查找
        if not used_price:
            for line in lines:
                line = line.strip()
                
                # 跳过已处理的新车指导价行
                if '新车指导价' in line:
                    continue
                
                # 跳过包含里程信息的行
                if '万公里' in line:
                    continue
                
                # 跳过包含年份信息的行
                if re.search(r'\d{4}年', line):
                    continue
                
                # 查找孤立的价格行
                if re.match(r'^\d+\.?\d*万$', line):
                    used_price = line
                    print(f"    💰 二手车价格 (孤立): {used_price}")
                    break
                
                # 查找行中的价格（但排除特殊行）
                if '万' in line:
                    match = re.search(r'(\d+\.?\d*)万', line)
                    if match:
                        # 确保这不是检测报告或其他特殊行
                        if not any(keyword in line for keyword in ["检测报告", "过户", "指导价", "新车"]):
                            used_price = f"{match.group(1)}万"
                            print(f"    💰 二手车价格 (行中): {used_price}")
                            break
        
        # 更新数据
        car_data["used_price"] = used_price
        car_data["new_car_price"] = new_car_price
        
        return car_data
    
    async def process_ocr_batch(self, vehicles_data):
        """批量OCR处理"""
        print(f"\n🔍 开始OCR识别，共 {len(vehicles_data)} 张图片...")
        
        processed_vehicles = []
        
        for i, vehicle_info in enumerate(vehicles_data):
            print(f"\n  🖼️ 处理 {vehicle_info['filename']}")
            
            screenshot_path = vehicle_info["screenshot_path"]
            
            if not os.path.exists(screenshot_path):
                print(f"    ❌ 图片不存在: {screenshot_path}")
                continue
            
            # OCR识别
            ocr_result = self.ocr_client.recognize_image(screenshot_path)
            
            if ocr_result:
                # 解析结果
                car_data = self.parse_vehicle_info(ocr_result, vehicle_info)
                processed_vehicles.append(car_data)
                print(f"    ✅ 处理成功")
            else:
                print(f"    ❌ OCR失败")
                failed_data = {
                    "filename": vehicle_info["filename"],
                    "car_id": vehicle_info["car_id"],
                    "href": vehicle_info["href"],
                    "title": vehicle_info["title"],
                    "ocr_text": "",
                    "parse_success": False
                }
                processed_vehicles.append(failed_data)
            
            # 避免请求过快
            await asyncio.sleep(0.5)
        
        return processed_vehicles
    
    async def crawl_all_pages(self, max_pages=None, brands_to_crawl=None):
        """爬取所有页面（支持多品牌）"""
        # 确保品牌信息已获取
        if not self.brands:
            await self.get_all_brands()
        
        if brands_to_crawl is None:
            brands_to_crawl = self.brands  # 默认爬取所有品牌
        
        if max_pages is None:
            print("🚀 开始爬取懂车帝二手车数据...")
            print("📝 提示：输入页数，0表示获取全部页面")
        else:
            print(f"🚀 开始爬取懂车帝前 {max_pages} 页...")
        
        all_vehicles_data = []
        
        if max_pages == 0:
            # 获取全部页面，需要先检测总页数
            print("🔍 检测总页数...")
            total_pages = await self.detect_total_pages()
            if total_pages == 0:
                print("❌ 无法检测总页数，使用默认值100")
                total_pages = 100
            print(f"📊 检测到总页数: {total_pages}")
            max_pages = total_pages
        
        print(f"🎯 将爬取 {len(brands_to_crawl)} 个品牌: {', '.join([b['name'] for b in brands_to_crawl[:10]])}{'...' if len(brands_to_crawl) > 10 else ''}")
        
        # 1. 爬取每个品牌的页面和截图
        for brand in brands_to_crawl:
            brand_id = brand['brand_id']
            brand_name = brand['name']
            
            print(f"\n{'='*60}")
            print(f"🏷️ 开始爬取品牌: {brand_name} (ID: {brand_id})")
            
            for page in range(1, max_pages + 1):
                print(f"\n{'-'*40}")
                vehicles_data = await self.crawl_page(page, brand_id)
                
                if vehicles_data:
                    all_vehicles_data.extend(vehicles_data)
                    print(f"✅ {brand_name} 第 {page} 页完成，获取 {len(vehicles_data)} 辆车")
                    print(f"📊 {brand_name} 累计获取: {len([v for v in all_vehicles_data if v.get('brand_id') == brand_id])} 辆车")
                    print(f"🎯 全部累计获取: {len(all_vehicles_data)} 辆车")
                else:
                    print(f"❌ {brand_name} 第 {page} 页未获取到数据")
                    # 如果连续3页没有数据，可能已经到最后一页
                    if page > max_pages - 3:
                        print(f"⚠️ {brand_name} 连续无数据页面，可能已到达最后一页")
                        break
            
            if page < max_pages:
                print(f"⏱️ 品牌切换等待2秒...")
                await asyncio.sleep(2)
        
        print(f"\n📊 页面爬取完成，共 {len(all_vehicles_data)} 辆车")
        
        # 2. 批量OCR处理
        if all_vehicles_data:
            print(f"\n🔍 开始OCR识别处理...")
            processed_vehicles = await self.process_ocr_batch(all_vehicles_data)
            
            # 3. 保存结果
            actual_pages = max_pages if max_pages != 0 else len(set(v['page'] for v in all_vehicles_data))
            self.save_results(processed_vehicles, pages_crawled=actual_pages)
            
            return processed_vehicles
        else:
            print("❌ 未获取到任何数据")
            return []
    
    async def detect_total_pages(self):
        """检测总页数"""
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                
                # 访问第一页
                url = "https://www.dongchedi.com/usedcar/x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-1-x-x-x-x-x"
                await page.goto(url, wait_until="networkidle")
                await page.wait_for_timeout(2000)
                
                # 查找分页信息
                # 尝试多种可能的分页选择器
                page_selectors = [
                    '.pagination-item:last-child',
                    '.page-num:last-child', 
                    '.pagination a:last-child',
                    '[class*="page"]:last-child',
                    '.total-page'
                ]
                
                total_pages = 0
                for selector in page_selectors:
                    try:
                        element = await page.query_selector(selector)
                        if element:
                            text = await element.text_content()
                            # 提取数字
                            match = re.search(r'(\d+)', text)
                            if match:
                                total_pages = int(match.group(1))
                                if total_pages > 100:  # 限制最大页数
                                    total_pages = 100
                                break
                    except:
                        continue
                
                await browser.close()
                return total_pages
                
        except Exception as e:
            print(f"⚠️ 检测总页数失败: {e}")
            return 0
    
    def save_results(self, vehicles_data, pages_crawled=1):
        """保存结果"""
        results = {
            "crawl_info": {
                "crawl_time": datetime.now().isoformat(),
                "total_vehicles": len(vehicles_data),
                "pages_crawled": pages_crawled,
                "method": "precise_playwright_baidu_iocr",
                "data_source": "dongchedi_used_car_all"
            },
            "vehicles": vehicles_data
        }
        
        with open('data/dongchedi_precise_crawl.json', 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        print(f"\n💾 数据已保存到: data/dongchedi_precise_crawl.json")
        
        # 保存文件名映射
        filename_mapping = []
        for vehicle in vehicles_data:
            filename_mapping.append({
                "filename": vehicle["filename"],
                "car_id": vehicle["car_id"],
                "href": vehicle["href"]
            })
        
        with open('data/filename_mapping.json', 'w', encoding='utf-8') as f:
            json.dump(filename_mapping, f, ensure_ascii=False, indent=2)
        
        print(f"💾 文件名映射已保存到: data/filename_mapping.json")
    
    def print_statistics(self, vehicles_data):
        """打印统计"""
        total = len(vehicles_data)
        if total == 0:
            print(f"\n❌ 未获取到数据")
            return
        
        stats = {
            'total': total,
            'ocr_success': 0,
            'parse_success': 0,
            'model_name': 0,
            'year': 0,
            'mileage': 0,
            'location': 0,
            'used_price': 0,
            'new_car_price': 0
        }
        
        for vehicle in vehicles_data:
            if vehicle.get("ocr_text"):
                stats['ocr_success'] += 1
            if vehicle.get("parse_success"):
                stats['parse_success'] += 1
            if vehicle.get("model_name"):
                stats['model_name'] += 1
            if vehicle.get("year"):
                stats['year'] += 1
            if vehicle.get("mileage"):
                stats['mileage'] += 1
            if vehicle.get("location"):
                stats['location'] += 1
            if vehicle.get("used_price"):
                stats['used_price'] += 1
            if vehicle.get("new_car_price"):
                stats['new_car_price'] += 1
        
        print(f"\n📊 爬取统计:")
        print("="*50)
        print(f"总车辆数: {total}")
        print(f"OCR成功: {stats['ocr_success']}/{total} ({stats['ocr_success']/total*100:.1f}%)")
        print(f"解析成功: {stats['parse_success']}/{total} ({stats['parse_success']/total*100:.1f}%)")
        
        print(f"\n字段提取:")
        print(f"  车型: {stats['model_name']}/{total} ({stats['model_name']/total*100:.1f}%)")
        print(f"  年份: {stats['year']}/{total} ({stats['year']/total*100:.1f}%)")
        print(f"  里程: {stats['mileage']}/{total} ({stats['mileage']/total*100:.1f}%)")
        print(f"  位置: {stats['location']}/{total} ({stats['location']/total*100:.1f}%)")
        print(f"  二手车价: {stats['used_price']}/{total} ({stats['used_price']/total*100:.1f}%)")
        print(f"  新车指导价: {stats['new_car_price']}/{total} ({stats['new_car_price']/total*100:.1f}%)")

async def main():
    """主函数"""
    print("🚗 懂车帝精准爬虫启动")
    print("="*60)
    print("📋 功能说明:")
    print("• 支持爬取懂车帝全部二手车数据")
    print("• 支持多品牌切换爬取")
    print("• 精准价格提取（二手车价格 + 新车指导价）")
    print("• 百度iOCR高精度识别")
    print("• 智能文件命名和批量处理")
    print("="*60)
    
    crawler = DongchediPreciseCrawler()
    
    # 显示可选品牌
    print("\n🏷️ 正在获取品牌信息...")
    await crawler.get_all_brands()
    
    if crawler.brands:
        print(f"\n📋 可选品牌 (共 {len(crawler.brands)} 个):")
        for i, brand in enumerate(crawler.brands, 1):
            print(f"  {i:3d}. {brand['name']} (ID: {brand['brand_id']})")
        print(f"  {len(crawler.brands)+1:3d}. 全部品牌")
    else:
        print("❌ 未获取到品牌信息，使用默认品牌列表")
        return
    
    # 获取用户输入
    while True:
        try:
            # 品牌选择
            brand_input = input("\n📝 请选择品牌 (输入数字，如: 1,2,3 或 'all' 表示全部，或输入品牌名称搜索): ").strip()
            
            brands_to_crawl = None
            if brand_input.lower() == 'all':
                brands_to_crawl = crawler.brands
                print(f"🎯 已选择全部品牌 ({len(brands_to_crawl)} 个)")
            elif brand_input.isdigit():
                # 按数字选择
                brand_indices = [int(x.strip()) for x in brand_input.split(',')]
                brands_to_crawl = []
                for idx in brand_indices:
                    if 1 <= idx <= len(crawler.brands):
                        brands_to_crawl.append(crawler.brands[idx-1])
                    else:
                        print(f"❌ 品牌编号 {idx} 无效")
                        raise ValueError
                
                if not brands_to_crawl:
                    print("❌ 未选择有效品牌")
                    continue
                    
                brand_names = [b['name'] for b in brands_to_crawl]
                print(f"🎯 已选择品牌: {', '.join(brand_names)}")
            else:
                # 按品牌名称搜索
                search_term = brand_input.lower()
                matched_brands = [b for b in crawler.brands if search_term in b['name'].lower()]
                
                if not matched_brands:
                    print(f"❌ 未找到包含 '{brand_input}' 的品牌")
                    continue
                elif len(matched_brands) == 1:
                    brands_to_crawl = matched_brands
                    print(f"🎯 已选择品牌: {matched_brands[0]['name']}")
                else:
                    print(f"🔍 找到 {len(matched_brands)} 个匹配品牌:")
                    for i, brand in enumerate(matched_brands, 1):
                        print(f"  {i}. {brand['name']} (ID: {brand['brand_id']})")
                    
                    choice = input("请选择 (输入数字或 'all' 选择全部): ").strip()
                    if choice.lower() == 'all':
                        brands_to_crawl = matched_brands
                    else:
                        try:
                            choice_indices = [int(x.strip()) for x in choice.split(',')]
                            brands_to_crawl = []
                            for idx in choice_indices:
                                if 1 <= idx <= len(matched_brands):
                                    brands_to_crawl.append(matched_brands[idx-1])
                        except ValueError:
                            print("❌ 输入格式错误")
                            continue
            
            # 数据量选择
            if len(brands_to_crawl) == 1:
                # 单个品牌，显示数据量信息并让用户选择
                selected_brand = brands_to_crawl[0]
                print(f"\n🔍 正在分析 {selected_brand['name']} 品牌数据量...")
                
                data_info = await crawler.calculate_brand_total_data(selected_brand['brand_id'], selected_brand['name'])
                
                if data_info:
                    min_total_data = data_info.get('min_total_data', data_info['estimated_total'])
                    print(f"\n📊 {selected_brand['name']} 数据量分析:")
                    print(f"  • 预计最少数据量: {min_total_data} 条")
                    print(f"  • 总页数: {data_info['total_pages']} 页")
                    print(f"  • 每页约: {data_info['current_page_count']} 条")
                    
                    while True:
                        try:
                            data_input = input(f"\n📝 请输入要采集的数据量 (默认-1为全部，或输入具体数字如: 100): ").strip()
                            
                            if not data_input:
                                data_limit = -1
                            elif data_input == '-1':
                                data_limit = -1
                            else:
                                data_limit = int(data_input)
                                if data_limit <= 0:
                                    print("❌ 数据量必须大于0")
                                    continue
                                if data_limit > min_total_data:
                                    print(f"⚠️ 请求数据量 {data_limit} 超过预计最少数据量 {min_total_data}，将采集全部可用数据")
                                    data_limit = -1
                            
                            target_text = "全部" if data_limit == -1 else f"{data_limit}条"
                            print(f"🎯 将采集 {selected_brand['name']} {target_text} 数据")
                            break
                            
                        except ValueError:
                            print("❌ 请输入有效数字或 -1")
                            continue
                        except KeyboardInterrupt:
                            print("\n👋 用户取消操作")
                            return
                    
                    # 使用新的智能爬取方法
                    vehicles_data = await crawler.crawl_brand_with_limit(
                        selected_brand['brand_id'], 
                        selected_brand['name'], 
                        data_limit
                    )
                    
                else:
                    print(f"❌ 无法获取 {selected_brand['name']} 的数据量信息")
                    vehicles_data = []
                    
            else:
                # 多个品牌，使用传统方式
                while True:
                    try:
                        page_input = input(f"\n📝 请输入要爬取的页数 (0=全部页面, 1-50=指定页数): ").strip()
                        
                        if not page_input:
                            print("❌ 请输入有效数字")
                            continue
                        
                        page_num = int(page_input)
                        
                        if page_num < 0:
                            print("❌ 页数不能为负数")
                            continue
                        elif page_num > 50:
                            print("⚠️ 页数过多，限制为50页")
                            page_num = 50
                        
                        break
                        
                    except ValueError:
                        print("❌ 请输入有效数字")
                        continue
                    except KeyboardInterrupt:
                        print("\n👋 用户取消操作")
                        return
                
                # 使用传统爬取方法
                vehicles_data = await crawler.crawl_all_pages(max_pages=page_num, brands_to_crawl=brands_to_crawl)
            
            break
            
        except ValueError:
            print("❌ 请输入有效数字")
            continue
        except KeyboardInterrupt:
            print("\n👋 用户取消操作")
            return
    
    # 初始化变量
    vehicles_data = []
    page_num = 0
    
    print(f"\n🎯 开始爬取: {'全部页面' if page_num == 0 else f'{page_num}页'}")
    print("="*60)
    
    # 爬取数据
    if len(brands_to_crawl) == 1 and 'vehicles_data' in locals() and vehicles_data:
        # 单品牌智能爬取已完成
        pass
    else:
        # 多品牌传统爬取或单品牌爬取失败
        if len(brands_to_crawl) == 1:
            # 单品牌但智能爬取失败，使用传统方式
            while True:
                try:
                    page_input = input(f"\n📝 请输入要爬取的页数 (0=全部页面, 1-50=指定页数): ").strip()
                    
                    if not page_input:
                        print("❌ 请输入有效数字")
                        continue
                    
                    page_num = int(page_input)
                    
                    if page_num < 0:
                        print("❌ 页数不能为负数")
                        continue
                    elif page_num > 50:
                        print("⚠️ 页数过多，限制为50页")
                        page_num = 50
                    
                    break
                    
                except ValueError:
                    print("❌ 请输入有效数字")
                    continue
                except KeyboardInterrupt:
                    print("\n👋 用户取消操作")
                    return
            
            vehicles_data = await crawler.crawl_all_pages(max_pages=page_num, brands_to_crawl=brands_to_crawl)
        else:
            # 多品牌传统爬取
            vehicles_data = await crawler.crawl_all_pages(max_pages=page_num, brands_to_crawl=brands_to_crawl)
    
    if vehicles_data:
        crawler.print_statistics(vehicles_data)
        
        print(f"\n🎉 爬取完成！")
        print(f"📁 截图: screenshots/ (按页码-序号命名)")
        print(f"📊 数据: data/dongchedi_precise_crawl.json")
        print(f"🗂️  映射: data/filename_mapping.json")
        
        print(f"\n✅ 爬取优势:")
        print("-" * 30)
        print("• 🚗 全部车型覆盖（不再限制大众品牌）")
        print("• 🎯 精准价格提取（二手车价+新车指导价）")
        print("• 📸 智能截图命名（页码-序号格式）")
        print("• 🔍 百度iOCR高精度识别")
        print("• 💾 完整数据保存")
        
        # 显示价格统计
        used_count = sum(1 for v in vehicles_data if v.get('used_price'))
        new_count = sum(1 for v in vehicles_data if v.get('new_car_price'))
        
        print(f"\n💰 价格统计:")
        print("-" * 30)
        print(f"• 二手车价格: {used_count}/{len(vehicles_data)} ({used_count/len(vehicles_data)*100:.1f}%)")
        print(f"• 新车指导价: {new_count}/{len(vehicles_data)} ({new_count/len(vehicles_data)*100:.1f}%)")
        
    else:
        print("❌ 未获取到数据")

if __name__ == "__main__":
    asyncio.run(main())
