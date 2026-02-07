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
        
        # 创建目录
        os.makedirs(self.screenshot_dir, exist_ok=True)
        os.makedirs("data", exist_ok=True)
    
    def extract_car_id_from_href(self, href):
        """从href中提取车辆ID"""
        if not href:
            return None
        
        # 从 /usedcar/22563498 提取 22563498
        match = re.search(r'/usedcar/(\d+)', href)
        if match:
            return match.group(1)
        
        return None
    
    async def crawl_page(self, page_num):
        """爬取指定页面"""
        # 修改URL以获取全部车型，而不是特定品牌
        url = f"https://www.dongchedi.com/usedcar/x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-{page_num}-x-x-x-x-x"
        
        print(f"📄 正在爬取第 {page_num} 页...")
        print(f"🔗 URL: {url}")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            page = await browser.new_page()
            
            try:
                await page.goto(url, wait_until="networkidle")
                await page.wait_for_timeout(3000)
                
                # 滚动加载
                await page.evaluate("""
                    () => {
                        window.scrollTo(0, document.body.scrollHeight);
                        return new Promise(resolve => setTimeout(resolve, 2000));
                    }
                """)
                
                # 精准查找车辆卡片
                await page.wait_for_selector('a.usedcar-card_card__3vUrx', timeout=10000)
                
                # 获取所有车辆卡片
                vehicle_cards = await page.query_selector_all('a.usedcar-card_card__3vUrx')
                
                if not vehicle_cards:
                    print(f"❌ 第 {page_num} 页未找到车辆卡片")
                    await browser.close()
                    return []
                
                print(f"✅ 找到 {len(vehicle_cards)} 个车辆卡片")
                
                vehicles_data = []
                
                for i, card in enumerate(vehicle_cards):
                    try:
                        print(f"  🚗 处理第 {i+1} 个车辆卡片...")
                        
                        # 提取href链接
                        href = await card.get_attribute('href')
                        car_id = self.extract_car_id_from_href(href)
                        
                        if not car_id:
                            car_id = f"page{page_num}_car{i+1:02d}"
                        
                        print(f"    🆔 车辆ID: {car_id}")
                        print(f"    🔗 链接: {href}")
                        
                        # 生成文件名: 页码-序号 (01-1, 01-2, ..., 10-99)
                        filename = f"{page_num:02d}-{i+1:02d}"
                        
                        # 截取整个卡片
                        screenshot_path = os.path.join(self.screenshot_dir, f"{filename}.png")
                        
                        # 滚动到卡片位置
                        await card.scroll_into_view_if_needed()
                        await page.wait_for_timeout(500)
                        
                        # 截图
                        await card.screenshot(path=screenshot_path)
                        print(f"    📸 截图保存: {filename}.png")
                        
                        # 提取基本信息
                        # 车型名称
                        title_element = await card.query_selector('p.line-1')
                        title = await title_element.text_content() if title_element else ""
                        
                        print(f"    📝 车型: {title}")
                        
                        # 保存车辆信息
                        vehicle_info = {
                            "filename": filename,
                            "car_id": car_id,
                            "href": href,
                            "title": title,
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
                print(f"❌ 第 {page_num} 页爬取失败: {e}")
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
    
    async def crawl_all_pages(self, max_pages=None):
        """爬取所有页面"""
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
        
        # 1. 爬取页面和截图
        for page in range(1, max_pages + 1):
            print(f"\n{'='*60}")
            vehicles_data = await self.crawl_page(page)
            
            if vehicles_data:
                all_vehicles_data.extend(vehicles_data)
                print(f"✅ 第 {page} 页完成，获取 {len(vehicles_data)} 辆车")
                print(f"📊 累计获取: {len(all_vehicles_data)} 辆车")
            else:
                print(f"❌ 第 {page} 页未获取到数据")
                # 如果连续3页没有数据，可能已经到最后一页
                if page > max_pages - 3:
                    print(f"⚠️ 连续无数据页面，可能已到达最后一页")
                    break
            
            if page < max_pages:
                print(f"⏱️ 等待2秒后继续下一页...")
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
    print("• 精准价格提取（二手车价格 + 新车指导价）")
    print("• 百度iOCR高精度识别")
    print("• 智能文件命名和批量处理")
    print("="*60)
    
    # 获取用户输入
    while True:
        try:
            user_input = input("\n📝 请输入要爬取的页数 (0=全部页面, 1-100=指定页数): ").strip()
            
            if not user_input:
                print("❌ 请输入有效数字")
                continue
            
            page_num = int(user_input)
            
            if page_num < 0:
                print("❌ 页数不能为负数")
                continue
            elif page_num > 100:
                print("⚠️ 页数过多，限制为100页")
                page_num = 100
            
            break
            
        except ValueError:
            print("❌ 请输入有效数字")
            continue
        except KeyboardInterrupt:
            print("\n👋 用户取消操作")
            return
    
    print(f"\n🎯 开始爬取: {'全部页面' if page_num == 0 else f'{page_num}页'}")
    print("="*60)
    
    crawler = DongchediPreciseCrawler()
    
    # 爬取数据
    vehicles_data = await crawler.crawl_all_pages(max_pages=page_num)
    
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
