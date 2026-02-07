#!/usr/bin/env python3
"""
懂车帝品牌分析程序
获取所有品牌信息和大概数据量，保存到JSON文件
"""

import asyncio
import json
import os
from datetime import datetime
from dongchedi_precise_crawler import DongchediPreciseCrawler

class BrandAnalyzer:
    def __init__(self):
        self.crawler = DongchediPreciseCrawler()
        self.output_file = "brands_analysis.json"
    
    async def analyze_all_brands(self):
        """分析所有品牌的数据量"""
        print("🚗 懂车帝品牌分析程序")
        print("=" * 60)
        
        # 获取所有品牌
        print("🔍 正在获取所有品牌信息...")
        brands = await self.crawler.get_all_brands()
        
        if not brands:
            print("❌ 获取品牌信息失败")
            return
        
        print(f"✅ 成功获取 {len(brands)} 个品牌")
        
        # 分析每个品牌的数据量
        analyzed_brands = []
        
        for i, brand in enumerate(brands, 1):
            brand_id = brand["brand_id"]
            brand_name = brand["name"]
            
            print(f"\n📊 [{i}/{len(brands)}] 分析品牌: {brand_name}")
            print("-" * 40)
            
            try:
                # 计算品牌数据量
                result = await self.crawler.calculate_brand_total_data(brand_id, brand_name)
                
                if result:
                    brand_info = {
                        "brand_id": brand_id,
                        "brand_name": brand_name,
                        "total_pages": result['total_pages'],
                        "data_range": result['data_range'],
                        "min_total_data": result['min_total_data'],
                        "max_total_data": result['max_total_data'],
                        "current_page_count": result['current_page_count'],
                        "calculation_method": result.get('calculation_method', 'unknown'),
                        "data_level": self._get_data_level(result['total_pages'])
                    }
                    
                    analyzed_brands.append(brand_info)
                    
                    print(f"✅ {brand_name} 分析完成:")
                    print(f"   - 总页数: {result['total_pages']}")
                    print(f"   - 数据范围: {result['data_range']} 条")
                    print(f"   - 数据级别: {brand_info['data_level']}")
                else:
                    print(f"❌ {brand_name} 分析失败")
                    # 仍然保存基本信息，但标记为分析失败
                    brand_info = {
                        "brand_id": brand_id,
                        "brand_name": brand_name,
                        "total_pages": 0,
                        "data_range": "0",
                        "min_total_data": 0,
                        "max_total_data": 0,
                        "current_page_count": 0,
                        "calculation_method": "failed",
                        "data_level": "未知"
                    }
                    analyzed_brands.append(brand_info)
                
            except Exception as e:
                print(f"❌ 分析 {brand_name} 时出错: {e}")
                # 保存错误信息
                brand_info = {
                    "brand_id": brand_id,
                    "brand_name": brand_name,
                    "total_pages": 0,
                    "data_range": "0",
                    "min_total_data": 0,
                    "max_total_data": 0,
                    "current_page_count": 0,
                    "calculation_method": "error",
                    "data_level": "错误",
                    "error": str(e)
                }
                analyzed_brands.append(brand_info)
            
            # 添加延迟避免请求过快
            await asyncio.sleep(1)
        
        # 保存分析结果
        await self._save_analysis_results(analyzed_brands)
        
        # 显示统计信息
        self._show_statistics(analyzed_brands)
    
    def _get_data_level(self, total_pages):
        """根据页数判断数据级别"""
        if total_pages == 0:
            return "无数据"
        elif total_pages <= 5:
            return "少量"
        elif total_pages <= 20:
            return "中等"
        elif total_pages <= 100:
            return "大量"
        else:
            return "海量"
    
    async def _save_analysis_results(self, analyzed_brands):
        """保存分析结果到JSON文件"""
        analysis_data = {
            "analysis_time": datetime.now().isoformat(),
            "total_brands": len(analyzed_brands),
            "brands": analyzed_brands
        }
        
        try:
            with open(self.output_file, 'w', encoding='utf-8') as f:
                json.dump(analysis_data, f, ensure_ascii=False, indent=2)
            
            print(f"\n💾 分析结果已保存到: {self.output_file}")
            
        except Exception as e:
            print(f"❌ 保存分析结果失败: {e}")
    
    def _show_statistics(self, analyzed_brands):
        """显示统计信息"""
        print("\n" + "=" * 60)
        print("📊 品牌分析统计")
        print("=" * 60)
        
        # 按数据级别分类统计
        level_stats = {}
        total_data_min = 0
        total_data_max = 0
        successful_brands = 0
        
        for brand in analyzed_brands:
            level = brand['data_level']
            level_stats[level] = level_stats.get(level, 0) + 1
            
            if brand['total_pages'] > 0:
                successful_brands += 1
                total_data_min += brand['min_total_data']
                total_data_max += brand['max_total_data']
        
        print(f"📈 总体统计:")
        print(f"   - 总品牌数: {len(analyzed_brands)}")
        print(f"   - 成功分析: {successful_brands}")
        print(f"   - 分析失败: {len(analyzed_brands) - successful_brands}")
        print(f"   - 总数据量范围: {total_data_min:,} - {total_data_max:,} 条")
        
        print(f"\n📊 数据级别分布:")
        for level, count in sorted(level_stats.items()):
            percentage = (count / len(analyzed_brands)) * 100
            print(f"   - {level}: {count} 个品牌 ({percentage:.1f}%)")
        
        # 显示前10大数据品牌
        top_brands = sorted([b for b in analyzed_brands if b['total_pages'] > 0], 
                           key=lambda x: x['max_total_data'], reverse=True)[:10]
        
        print(f"\n🏆 数据量前10品牌:")
        for i, brand in enumerate(top_brands, 1):
            print(f"   {i:2d}. {brand['brand_name']:8s} - {brand['data_range']} 条 ({brand['total_pages']}页)")

async def main():
    """主函数"""
    analyzer = BrandAnalyzer()
    await analyzer.analyze_all_brands()

if __name__ == "__main__":
    asyncio.run(main())
