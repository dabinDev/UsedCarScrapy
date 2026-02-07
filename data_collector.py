#!/usr/bin/env python3
"""
懂车帝数据采集程序
读取品牌分析结果，循环采集各品牌的具体数据
"""

import asyncio
import json
import os
from datetime import datetime
from dongchedi_precise_crawler import DongchediPreciseCrawler

class DataCollector:
    def __init__(self):
        self.crawler = DongchediPreciseCrawler()
        self.brands_file = "brands_analysis.json"
        self.output_dir = "brand_data"
        self.collected_data = []
    
    async def load_brands_analysis(self):
        """加载品牌分析结果"""
        try:
            with open(self.brands_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            print(f"✅ 成功加载品牌分析结果")
            print(f"📅 分析时间: {data['analysis_time']}")
            print(f"📊 总品牌数: {data['total_brands']}")
            
            return data['brands']
            
        except FileNotFoundError:
            print(f"❌ 未找到品牌分析文件: {self.brands_file}")
            print("请先运行 brand_analyzer.py 进行品牌分析")
            return None
        except Exception as e:
            print(f"❌ 加载品牌分析失败: {e}")
            return None
    
    async def collect_brand_data(self, brand_info, max_records=None):
        """采集单个品牌的数据"""
        brand_id = brand_info['brand_id']
        brand_name = brand_info['brand_name']
        total_pages = brand_info['total_pages']
        data_range = brand_info['data_range']
        
        print(f"\n🚗 开始采集品牌: {brand_name}")
        print(f"📊 预计数据量: {data_range} 条 ({total_pages}页)")
        
        if max_records:
            print(f"🎯 限制采集数量: {max_records} 条")
        
        try:
            # 计算需要采集的页数
            pages_to_crawl = self._calculate_pages_to_crawl(total_pages, brand_info['current_page_count'], max_records)
            
            if pages_to_crawl == 0:
                print(f"⏭️  跳过 {brand_name} (无数据或达到限制)")
                return None
            
            print(f"📄 计划采集 {pages_to_crawl} 页数据")
            
            # 使用爬虫的智能采集方法
            brand_data = await self.crawler.intelligent_crawl_brand(
                brand_id, brand_name, pages_to_crawl
            )
            
            if brand_data:
                # 保存品牌数据到单独文件
                await self._save_brand_data(brand_name, brand_data)
                
                result_info = {
                    "brand_id": brand_id,
                    "brand_name": brand_name,
                    "collected_count": len(brand_data),
                    "pages_crawled": pages_to_crawl,
                    "collection_time": datetime.now().isoformat(),
                    "success": True
                }
                
                print(f"✅ {brand_name} 采集完成: {len(brand_data)} 条数据")
                return result_info
            else:
                print(f"❌ {brand_name} 采集失败")
                return {
                    "brand_id": brand_id,
                    "brand_name": brand_name,
                    "collected_count": 0,
                    "pages_crawled": 0,
                    "collection_time": datetime.now().isoformat(),
                    "success": False,
                    "error": "采集返回空数据"
                }
        
        except Exception as e:
            print(f"❌ 采集 {brand_name} 时出错: {e}")
            return {
                "brand_id": brand_id,
                "brand_name": brand_name,
                "collected_count": 0,
                "pages_crawled": 0,
                "collection_time": datetime.now().isoformat(),
                "success": False,
                "error": str(e)
            }
    
    def _calculate_pages_to_crawl(self, total_pages, records_per_page, max_records):
        """计算需要采集的页数"""
        if total_pages == 0:
            return 0
        
        if max_records is None:
            # 采集所有数据
            return total_pages
        
        # 计算需要多少页才能达到max_records
        needed_pages = (max_records + records_per_page - 1) // records_per_page
        
        # 不超过总页数
        return min(needed_pages, total_pages)
    
    async def _save_brand_data(self, brand_name, brand_data):
        """保存品牌数据到单独文件"""
        # 创建输出目录
        os.makedirs(self.output_dir, exist_ok=True)
        
        # 生成文件名（去除特殊字符）
        safe_name = "".join(c for c in brand_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        filename = f"{safe_name}_{len(brand_data)}_records.json"
        filepath = os.path.join(self.output_dir, filename)
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump({
                    "brand_name": brand_name,
                    "collection_time": datetime.now().isoformat(),
                    "total_records": len(brand_data),
                    "data": brand_data
                }, f, ensure_ascii=False, indent=2)
            
            print(f"💾 数据已保存到: {filename}")
            
        except Exception as e:
            print(f"❌ 保存 {brand_name} 数据失败: {e}")
    
    async def collect_all_brands(self, max_records_per_brand=None, selected_brands=None):
        """采集所有品牌的数据"""
        print("🚗 懂车帝数据采集程序")
        print("=" * 60)
        
        # 加载品牌分析结果
        brands = await self.load_brands_analysis()
        if not brands:
            return
        
        # 过滤品牌
        if selected_brands:
            brands = [b for b in brands if b['brand_name'] in selected_brands]
            print(f"🎯 采集指定品牌: {', '.join(selected_brands)}")
        
        # 过滤掉无数据的品牌
        valid_brands = [b for b in brands if b['total_pages'] > 0]
        print(f"📊 有效品牌数: {len(valid_brands)} (有数据的品牌)")
        
        if not valid_brands:
            print("❌ 没有找到有数据的品牌")
            return
        
        # 采集数据
        collection_results = []
        total_collected = 0
        
        for i, brand in enumerate(valid_brands, 1):
            print(f"\n🔄 [{i}/{len(valid_brands)}] 开始采集品牌数据")
            
            result = await self.collect_brand_data(brand, max_records_per_brand)
            
            if result:
                collection_results.append(result)
                if result['success']:
                    total_collected += result['collected_count']
            
            # 添加延迟避免请求过快
            await asyncio.sleep(2)
        
        # 保存采集总结
        await self._save_collection_summary(collection_results, total_collected)
        
        # 显示采集统计
        self._show_collection_stats(collection_results, total_collected)
    
    async def _save_collection_summary(self, results, total_collected):
        """保存采集总结"""
        summary = {
            "collection_time": datetime.now().isoformat(),
            "total_brands_attempted": len(results),
            "successful_collections": len([r for r in results if r['success']]),
            "failed_collections": len([r for r in results if not r['success']]),
            "total_records_collected": total_collected,
            "results": results
        }
        
        try:
            with open("collection_summary.json", 'w', encoding='utf-8') as f:
                json.dump(summary, f, ensure_ascii=False, indent=2)
            
            print(f"\n💾 采集总结已保存到: collection_summary.json")
            
        except Exception as e:
            print(f"❌ 保存采集总结失败: {e}")
    
    def _show_collection_stats(self, results, total_collected):
        """显示采集统计"""
        print("\n" + "=" * 60)
        print("📊 数据采集统计")
        print("=" * 60)
        
        successful = [r for r in results if r['success']]
        failed = [r for r in results if not r['success']]
        
        print(f"📈 采集结果:")
        print(f"   - 尝试品牌数: {len(results)}")
        print(f"   - 成功采集: {len(successful)}")
        print(f"   - 采集失败: {len(failed)}")
        print(f"   - 总记录数: {total_collected:,}")
        
        if successful:
            print(f"\n✅ 成功采集的品牌:")
            for result in successful:
                print(f"   - {result['brand_name']}: {result['collected_count']} 条")
        
        if failed:
            print(f"\n❌ 采集失败的品牌:")
            for result in failed:
                error = result.get('error', '未知错误')
                print(f"   - {result['brand_name']}: {error}")

async def main():
    """主函数"""
    collector = DataCollector()
    
    # 可以配置采集参数
    max_records_per_brand = None  # None表示采集所有数据，或者设置具体数字如1000
    selected_brands = None  # None表示采集所有品牌，或者指定品牌列表如 ['大众', '丰田']
    
    await collector.collect_all_brands(max_records_per_brand, selected_brands)

if __name__ == "__main__":
    asyncio.run(main())
