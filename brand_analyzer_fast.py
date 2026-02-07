#!/usr/bin/env python3
"""
懂车帝品牌分析程序 - 多线程版本
使用线程池并发处理品牌分析，大幅提升处理速度
"""

import asyncio
import json
import os
import threading
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue, Empty
from dongchedi_precise_crawler import DongchediPreciseCrawler

class ThreadSafeBrandAnalyzer:
    def __init__(self, max_workers=5):
        self.crawler = DongchediPreciseCrawler()
        self.output_file = "brands_analysis.json"
        self.max_workers = max_workers
        self.results_lock = threading.Lock()
        self.results = []
        self.processed_count = 0
        self.total_brands = 0
        self.start_time = None
        
    async def analyze_all_brands_threaded(self):
        """使用线程池并发分析所有品牌"""
        print("🚗 懂车帝品牌分析程序 - 多线程版")
        print("=" * 60)
        print(f"🔧 线程池配置: {self.max_workers} 个工作线程")
        
        self.start_time = time.time()
        
        # 获取所有品牌
        print("🔍 正在获取所有品牌信息...")
        brands = await self.crawler.get_all_brands()
        
        if not brands:
            print("❌ 获取品牌信息失败")
            return
        
        self.total_brands = len(brands)
        print(f"✅ 成功获取 {self.total_brands} 个品牌")
        print(f"🎯 开始并发分析，预计处理时间: {self._estimate_time(self.total_brands)}")
        
        # 创建任务队列
        task_queue = Queue()
        for brand in brands:
            task_queue.put(brand)
        
        # 启动线程池
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有任务
            futures = []
            for i in range(self.max_workers):
                future = executor.submit(self._worker_thread, task_queue, i + 1)
                futures.append(future)
            
            # 等待所有线程完成
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    print(f"❌ 线程执行错误: {e}")
        
        # 保存最终结果
        await self._save_final_results()
        
        # 显示最终统计
        self._show_final_statistics()
    
    def _worker_thread(self, task_queue, thread_id):
        """工作线程函数"""
        print(f"🧵 线程 {thread_id} 启动")
        
        # 为每个线程创建独立的爬虫实例
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            thread_crawler = DongchediPreciseCrawler()
            
            while True:
                try:
                    # 从队列获取任务
                    brand = task_queue.get(timeout=1)
                    
                    # 处理品牌
                    result = loop.run_until_complete(
                        self._analyze_single_brand_safe(thread_crawler, brand, thread_id)
                    )
                    
                    # 线程安全地保存结果
                    with self.results_lock:
                        self.results.append(result)
                        self.processed_count += 1
                        
                        # 实时保存进度
                        if self.processed_count % 10 == 0:
                            self._save_progress()
                        
                        # 显示进度
                        progress = (self.processed_count / self.total_brands) * 100
                        elapsed = time.time() - self.start_time
                        eta = (elapsed / self.processed_count) * (self.total_brands - self.processed_count)
                        
                        print(f"📊 进度: {self.processed_count}/{self.total_brands} "
                              f"({progress:.1f}%) | "
                              f"线程{thread_id}: {brand['name']} | "
                              f"ETA: {eta:.0f}秒")
                    
                    # 标记任务完成
                    task_queue.task_done()
                    
                except Empty:
                    # 队列为空，退出线程
                    break
                except Exception as e:
                    print(f"❌ 线程{thread_id}处理品牌时出错: {e}")
                    task_queue.task_done()
        
        finally:
            loop.close()
            print(f"🧵 线程 {thread_id} 结束")
    
    async def _analyze_single_brand_safe(self, crawler, brand, thread_id):
        """安全地分析单个品牌"""
        brand_id = brand["brand_id"]
        brand_name = brand["name"]
        
        try:
            # 计算品牌数据量
            result = await crawler.calculate_brand_total_data(brand_id, brand_name)
            
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
                    "data_level": self._get_data_level(result['total_pages']),
                    "processed_by": f"thread_{thread_id}",
                    "success": True
                }
                
                return brand_info
            else:
                # 分析失败，返回基本信息
                brand_info = {
                    "brand_id": brand_id,
                    "brand_name": brand_name,
                    "total_pages": 0,
                    "data_range": "0",
                    "min_total_data": 0,
                    "max_total_data": 0,
                    "current_page_count": 0,
                    "calculation_method": "failed",
                    "data_level": "未知",
                    "processed_by": f"thread_{thread_id}",
                    "success": False
                }
                
                return brand_info
        
        except Exception as e:
            # 异常处理
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
                "processed_by": f"thread_{thread_id}",
                "success": False,
                "error": str(e)
            }
            
            return brand_info
    
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
    
    def _save_progress(self):
        """保存进度到临时文件"""
        progress_data = {
            "progress_time": datetime.now().isoformat(),
            "processed_count": self.processed_count,
            "total_brands": self.total_brands,
            "progress_percentage": (self.processed_count / self.total_brands) * 100,
            "results": self.results
        }
        
        try:
            with open("brands_analysis_progress.json", 'w', encoding='utf-8') as f:
                json.dump(progress_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠️ 保存进度失败: {e}")
    
    async def _save_final_results(self):
        """保存最终分析结果"""
        analysis_data = {
            "analysis_time": datetime.now().isoformat(),
            "total_brands": self.total_brands,
            "processed_count": self.processed_count,
            "thread_count": self.max_workers,
            "total_processing_time": time.time() - self.start_time,
            "brands": self.results
        }
        
        try:
            with open(self.output_file, 'w', encoding='utf-8') as f:
                json.dump(analysis_data, f, ensure_ascii=False, indent=2)
            
            print(f"\n💾 最终结果已保存到: {self.output_file}")
            
            # 删除进度文件
            if os.path.exists("brands_analysis_progress.json"):
                os.remove("brands_analysis_progress.json")
            
        except Exception as e:
            print(f"❌ 保存最终结果失败: {e}")
    
    def _show_final_statistics(self):
        """显示最终统计信息"""
        print("\n" + "=" * 60)
        print("📊 品牌分析最终统计")
        print("=" * 60)
        
        total_time = time.time() - self.start_time
        successful_brands = len([r for r in self.results if r.get('success', False)])
        
        print(f"🎯 处理统计:")
        print(f"   - 总品牌数: {self.total_brands}")
        print(f"   - 成功分析: {successful_brands}")
        print(f"   - 分析失败: {self.total_brands - successful_brands}")
        print(f"   - 处理时间: {total_time:.1f} 秒")
        print(f"   - 平均速度: {self.total_brands/total_time:.2f} 品牌/秒")
        print(f"   - 线程数量: {self.max_workers}")
        
        # 按数据级别分类统计
        level_stats = {}
        total_data_min = 0
        total_data_max = 0
        
        for brand in self.results:
            level = brand['data_level']
            level_stats[level] = level_stats.get(level, 0) + 1
            
            if brand['total_pages'] > 0:
                total_data_min += brand['min_total_data']
                total_data_max += brand['max_total_data']
        
        print(f"\n📊 数据级别分布:")
        for level, count in sorted(level_stats.items()):
            percentage = (count / len(self.results)) * 100
            print(f"   - {level}: {count} 个品牌 ({percentage:.1f}%)")
        
        print(f"\n📈 总体数据量:")
        print(f"   - 总数据量范围: {total_data_min:,} - {total_data_max:,} 条")
        
        # 显示前10大数据品牌
        top_brands = sorted([b for b in self.results if b['total_pages'] > 0], 
                           key=lambda x: x['max_total_data'], reverse=True)[:10]
        
        print(f"\n🏆 数据量前10品牌:")
        for i, brand in enumerate(top_brands, 1):
            print(f"   {i:2d}. {brand['brand_name']:8s} - {brand['data_range']} 条 ({brand['total_pages']}页)")
    
    def _estimate_time(self, brand_count):
        """估算处理时间"""
        # 基于经验值：每个品牌约2-3秒
        avg_time_per_brand = 2.5
        total_time = brand_count * avg_time_per_brand / self.max_workers
        
        if total_time < 60:
            return f"{total_time:.0f} 秒"
        elif total_time < 3600:
            return f"{total_time/60:.1f} 分钟"
        else:
            return f"{total_time/3600:.1f} 小时"

async def main():
    """主函数"""
    # 可以调整线程数量，建议3-8个
    analyzer = ThreadSafeBrandAnalyzer(max_workers=10)
    await analyzer.analyze_all_brands_threaded()

if __name__ == "__main__":
    asyncio.run(main())
