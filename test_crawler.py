#!/usr/bin/env python3
"""
测试懂车帝爬虫的核心功能
"""

import asyncio
from dongchedi_precise_crawler import DongchediPreciseCrawler

async def test_crawler():
    """测试爬虫核心功能"""
    print("🧪 开始测试懂车帝爬虫...")
    
    crawler = DongchediPreciseCrawler()
    
    # 测试1: 获取品牌信息
    print("\n📋 测试1: 获取品牌信息")
    await crawler.get_all_brands()
    
    if crawler.brands:
        print(f"✅ 成功获取 {len(crawler.brands)} 个品牌")
        
        # 测试2: 计算单个品牌数据量
        print("\n📊 测试2: 计算品牌数据量")
        test_brand = crawler.brands[0]  # 取第一个品牌测试
        print(f"🧪 测试品牌: {test_brand['name']} (ID: {test_brand['brand_id']})")
        
        data_info = await crawler.calculate_brand_total_data(
            test_brand['brand_id'], 
            test_brand['name']
        )
        
        if data_info:
            print(f"✅ 数据量计算成功:")
            print(f"   - 当前页车辆数: {data_info['current_page_count']}")
            print(f"   - 总页数: {data_info['total_pages']}")
            print(f"   - 估计总数据量: {data_info['estimated_total']}")
            print(f"   - 计算方式: {data_info['calculation_method']}")
        else:
            print("❌ 数据量计算失败")
    else:
        print("❌ 品牌获取失败")
    
    print("\n🎉 测试完成!")

if __name__ == "__main__":
    asyncio.run(test_crawler())
