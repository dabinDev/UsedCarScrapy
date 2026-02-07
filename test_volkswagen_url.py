#!/usr/bin/env python3
"""
测试大众品牌的正确URL和分页检测
"""

import asyncio
from playwright.async_api import async_playwright

async def test_volkswagen_url():
    """测试大众品牌的URL和分页"""
    print("🧪 测试大众品牌URL和分页检测...")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        try:
            # 使用你提供的正确URL
            url = "https://www.dongchedi.com/usedcar/x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-1-x-1-1-x-x-x-x-x"
            print(f"🔗 访问URL: {url}")
            
            await page.goto(url, wait_until="networkidle")
            await page.wait_for_timeout(5000)
            
            # 获取页面标题确认
            title = await page.title()
            print(f"📄 页面标题: {title}")
            
            # 查找车辆卡片
            vehicle_cards = await page.query_selector_all('a.usedcar-card_card__3vUrx')
            print(f"🚗 当前页车辆数: {len(vehicle_cards)}")
            
            # 尝试多种分页选择器
            pagination_selectors = [
                'div[class*="jsx-1325911405"]',
                'div[class*="pagination"]',
                'ul[class*="pagination"]',
                '.pagination',
                'div[class*="page"]',
                'div[class*="pager"]'
            ]
            
            for selector in pagination_selectors:
                pagination_element = await page.query_selector(selector)
                if pagination_element:
                    print(f"✅ 找到分页元素: {selector}")
                    
                    # 获取所有分页链接
                    page_links = await pagination_element.query_selector_all('a')
                    print(f"📄 分页链接数量: {len(page_links)}")
                    
                    # 显示前10个分页链接的文本和href
                    for i, link in enumerate(page_links[:10]):
                        text = await link.text_content()
                        href = await link.get_attribute('href')
                        print(f"   {i+1}. 文本: '{text}', href: {href}")
                    
                    break
            else:
                print("❌ 未找到任何分页元素")
                
            # 等待用户查看
            print("⏳ 等待10秒供查看...")
            await page.wait_for_timeout(10000)
            
        except Exception as e:
            print(f"❌ 测试失败: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(test_volkswagen_url())
