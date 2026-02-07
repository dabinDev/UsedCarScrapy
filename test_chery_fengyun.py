#!/usr/bin/env python3
"""
测试奇瑞风云品牌的数据量计算
"""

import asyncio
from dongchedi_precise_crawler import DongchediPreciseCrawler

async def test_chery_fengyun():
    """测试奇瑞风云品牌"""
    print("🧪 测试奇瑞风云品牌...")
    
    crawler = DongchediPreciseCrawler()
    
    # 奇瑞风云的品牌ID是10409
    brand_id = 10409
    brand_name = "奇瑞风云"
    
    # 计算数据量
    result = await crawler.calculate_brand_total_data(brand_id, brand_name)
    
    if result:
        print(f"✅ {brand_name} 品牌数据量计算成功:")
        print(f"   - 当前页车辆数: {result['current_page_count']}")
        print(f"   - 总页数: {result['total_pages']}")
        print(f"   - 数据范围: {result['data_range']} 条")
        print(f"   - 最少数据量: {result['min_total_data']} 条")
        print(f"   - 最多数据量: {result['max_total_data']} 条")
        print(f"   - 计算方式: {result.get('calculation_method', 'unknown')}")
    else:
        print(f"❌ {brand_name} 品牌数据量计算失败")

if __name__ == "__main__":
    asyncio.run(test_chery_fengyun())
