#!/usr/bin/env python3
"""
测试多个车型的数据量计算
"""

import asyncio
from dongchedi_precise_crawler import DongchediPreciseCrawler

async def test_multiple_brands():
    """测试多个品牌的数据量计算"""
    crawler = DongchediPreciseCrawler()
    
    # 测试多个品牌
    test_brands = [
        {"id": 1, "name": "大众"},
        {"id": 2, "name": "丰田"},
        {"id": 3, "name": "本田"},
        {"id": 4, "name": "奥迪"},
        {"id": 5, "name": "宝马"},
        {"id": 6, "name": "奔驰"},
        {"id": 7, "name": "日产"},
        {"id": 10409, "name": "奇瑞风云"},
    ]
    
    print("🚗 懂车帝多品牌数据量测试")
    print("=" * 60)
    
    for brand in test_brands:
        print(f"\n🧪 测试品牌: {brand['name']} (ID: {brand['id']})")
        print("-" * 40)
        
        try:
            # 计算数据量
            result = await crawler.calculate_brand_total_data(brand['id'], brand['name'])
            
            if result:
                print(f"✅ {brand['name']} 品牌数据量计算成功:")
                print(f"   - 当前页车辆数: {result['current_page_count']}")
                print(f"   - 总页数: {result['total_pages']}")
                print(f"   - 数据范围: {result['data_range']} 条")
                print(f"   - 最少数据量: {result['min_total_data']} 条")
                print(f"   - 最多数据量: {result['max_total_data']} 条")
                print(f"   - 计算方式: {result.get('calculation_method', 'unknown')}")
                
                # 计算数据量级别
                total_pages = result['total_pages']
                if total_pages <= 5:
                    level = "少量"
                elif total_pages <= 20:
                    level = "中等"
                elif total_pages <= 100:
                    level = "大量"
                else:
                    level = "海量"
                
                print(f"   - 数据级别: {level} ({total_pages}页)")
            else:
                print(f"❌ {brand['name']} 品牌数据量计算失败")
                
        except Exception as e:
            print(f"❌ 测试 {brand['name']} 时出错: {e}")
        
        # 添加延迟避免请求过快
        await asyncio.sleep(2)
    
    print("\n" + "=" * 60)
    print("🎯 多品牌测试完成")

if __name__ == "__main__":
    asyncio.run(test_multiple_brands())
