#!/usr/bin/env python3
"""
懂车帝车系分析程序
针对数据量过大的品牌，按车系进行细分查询以获取完整数据
"""

import asyncio
import json
import os
import threading
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue, Empty
from playwright.async_api import async_playwright
from dongchedi_precise_crawler import DongchediPreciseCrawler

class SeriesAnalyzer:
    def __init__(self, max_workers=3):
        self.crawler = DongchediPreciseCrawler()
        self.output_file = "dongchedi_series.json"
        self.max_workers = max_workers
        self.results_lock = threading.Lock()
        self.results = []
        self.processed_count = 0
        self.total_series = 0
        self.start_time = None
        self.analysis_type = "series_subset"
        
    async def analyze_brands_by_series(self, brands_file="dongchedi_brand.json"):
        """分析指定品牌的车系数据"""
        print("🚗 懂车帝车系分析程序")
        print("=" * 60)
        print(f"🔧 线程池配置: {self.max_workers} 个工作线程")
        
        # 读取品牌分析结果
        try:
            with open(brands_file, 'r', encoding='utf-8') as f:
                brands_data = json.load(f)
        except FileNotFoundError:
            print(f"❌ 未找到品牌分析文件: {brands_file}")
            print("请先运行 brand_analyzer_fast.py")
            return
        
        brand_list = brands_data.get('data') or brands_data.get('brands') or []
        if not brand_list:
            print("❌ 品牌列表为空，无法进行车系分析")
            return
        
        # 筛选需要车系细分的品牌
        big_brands = [b for b in brand_list if b.get('requires_series_analysis', False)]
        
        if not big_brands:
            print("✅ 没有需要车系细分的品牌")
            return
        
        print(f"🎯 发现 {len(big_brands)} 个需要车系细分的品牌:")
        for brand in big_brands:
            print(f"   - {brand['brand_name']}: {brand['total_pages']}页")
        
        self.start_time = time.time()
        
        # 分析每个品牌的车系
        all_series_tasks = []
        
        for brand in big_brands:
            print(f"\n🔍 正在分析 {brand['brand_name']} 的车系...")
            
            try:
                # 获取品牌下的所有车系
                series_list = await self._get_brand_series(brand['brand_id'], brand['brand_name'])
                
                if series_list:
                    print(f"✅ {brand['brand_name']} 共有 {len(series_list)} 个车系")
                    
                    # 为每个车系创建任务
                    for series in series_list:
                        task = {
                            'brand_id': brand['brand_id'],
                            'brand_name': brand['brand_name'],
                            'series_id': series['series_id'],
                            'series_name': series['name']
                        }
                        all_series_tasks.append(task)
                else:
                    print(f"❌ {brand['brand_name']} 未找到车系信息")
                    
            except Exception as e:
                print(f"❌ 获取 {brand['brand_name']} 车系失败: {e}")
        
        if not all_series_tasks:
            print("❌ 没有找到可分析的车系")
            return
        
        self.total_series = len(all_series_tasks)
        print(f"\n🎯 开始分析 {self.total_series} 个车系，预计时间: {self._estimate_time(self.total_series)}")
        
        # 创建任务队列
        task_queue = Queue()
        for task in all_series_tasks:
            task_queue.put(task)
        
        # 启动线程池
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
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
        await self._save_final_results(big_brands)
        
        # 显示统计信息
        self._show_statistics(big_brands)
    
    async def _get_brand_series(self, brand_id, brand_name):
        """获取品牌下的所有车系"""
        try:
            # 访问品牌页面获取车系信息
            url = f"https://www.dongchedi.com/usedcar/x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-{brand_id}-x-1-1-x-x-x-x-x"
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                
                try:
                    await page.goto(url, wait_until="networkidle")
                    await page.wait_for_timeout(3000)
                    
                    # 查找车系选择器或链接
                    series_selectors = [
                        'a[href*="/series/"]',
                        '.series-item a',
                        '.car-series a',
                        '[data-series-id] a',
                        'div[class*="series"] a'
                    ]
                    
                    series_list = []
                    
                    for selector in series_selectors:
                        series_elements = await page.query_selector_all(selector)
                        
                        if series_elements:
                            for element in series_elements:
                                try:
                                    text = await element.text_content()
                                    href = await element.get_attribute('href')
                                    
                                    if text and href and '/series/' in href:
                                        # 提取车系ID
                                        series_id = self._extract_series_id(href)
                                        if series_id:
                                            series_list.append({
                                                'series_id': series_id,
                                                'name': text.strip(),
                                                'href': href
                                            })
                                except Exception:
                                    continue
                            
                            if series_list:
                                break
                    
                    return series_list[:50]  # 限制返回数量，避免过多
                
                finally:
                    await browser.close()
        
        except Exception as e:
            print(f"❌ 获取 {brand_name} 车系失败: {e}")
            return []
    
    def _extract_series_id(self, href):
        """从href中提取车系ID"""
        try:
            # 从URL中提取车系ID，例如: /series/123/ -> 123
            parts = href.split('/series/')
            if len(parts) > 1:
                series_part = parts[1].split('/')[0]
                if series_part.isdigit():
                    return int(series_part)
        except Exception:
            pass
        return None
    
    def _worker_thread(self, task_queue, thread_id):
        """工作线程函数"""
        print(f"🧵 线程 {thread_id} 启动")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            while True:
                try:
                    task = task_queue.get(timeout=1)
                    
                    result = loop.run_until_complete(
                        self._analyze_single_series(task, thread_id)
                    )
                    
                    with self.results_lock:
                        self.results.append(result)
                        self.processed_count += 1
                        
                        # 显示进度
                        progress = (self.processed_count / self.total_series) * 100
                        elapsed = time.time() - self.start_time
                        eta = (elapsed / self.processed_count) * (self.total_series - self.processed_count)
                        
                        print(f"📊 进度: {self.processed_count}/{self.total_series} "
                              f"({progress:.1f}%) | "
                              f"线程{thread_id}: {task['brand_name']} - {task['series_name']} | "
                              f"ETA: {eta:.0f}秒")
                    
                    task_queue.task_done()
                    
                except Empty:
                    break
                except Exception as e:
                    print(f"❌ 线程{thread_id}处理车系时出错: {e}")
                    task_queue.task_done()
        
        finally:
            loop.close()
            print(f"🧵 线程 {thread_id} 结束")
    
    async def _analyze_single_series(self, task, thread_id):
        """分析单个车系的数据量"""
        brand_id = task['brand_id']
        brand_name = task['brand_name']
        series_id = task['series_id']
        series_name = task['series_name']
        timestamp = datetime.now().isoformat()
        
        try:
            # 构建车系URL
            # URL格式: /usedcar/x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-{brand_id}-x-{series_id}-1-x-x-x-x-x
            url = f"https://www.dongchedi.com/usedcar/x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-{brand_id}-x-{series_id}-1-x-x-x-x-x"
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                
                try:
                    await page.goto(url, wait_until="networkidle")
                    await page.wait_for_timeout(3000)
                    
                    # 获取车辆数量
                    vehicle_cards = await page.query_selector_all('a.usedcar-card_card__3vUrx')
                    current_page_count = len(vehicle_cards)
                    
                    # 获取分页信息
                    pagination_info = await self.crawler.get_pagination_info(page)
                    
                    if pagination_info:
                        total_pages = pagination_info.get('total_pages', 1)
                        
                        # 计算数据量范围
                        if total_pages > 1:
                            full_pages_data = (total_pages - 1) * current_page_count
                            min_total = full_pages_data + 1
                            max_total = full_pages_data + current_page_count
                            data_range = f"{min_total}-{max_total}"
                        else:
                            min_total = max_total = current_page_count
                            data_range = f"{current_page_count}"
                        
                        return {
                            'brand_id': brand_id,
                            'brand_name': brand_name,
                            'series_id': series_id,
                            'series_name': series_name,
                            'total_pages': total_pages,
                            'current_page_count': current_page_count,
                            'data_range': data_range,
                            'min_total_data': min_total,
                            'max_total_data': max_total,
                            'processed_by': f"thread_{thread_id}",
                            'last_updated': timestamp,
                            'success': True
                        }
                    else:
                        return {
                            'brand_id': brand_id,
                            'brand_name': brand_name,
                            'series_id': series_id,
                            'series_name': series_name,
                            'total_pages': 1,
                            'current_page_count': current_page_count,
                            'data_range': f"{current_page_count}",
                            'min_total_data': current_page_count,
                            'max_total_data': current_page_count,
                            'processed_by': f"thread_{thread_id}",
                            'last_updated': timestamp,
                            'success': True,
                            'note': '无分页信息'
                        }
                except Exception as e:
                    return {
                        'brand_id': brand_id,
                        'brand_name': brand_name,
                        'series_id': series_id,
                        'series_name': series_name,
                        'total_pages': 0,
                        'current_page_count': 0,
                        'data_range': "0",
                        'min_total_data': 0,
                        'max_total_data': 0,
                        'processed_by': f"thread_{thread_id}",
                        'last_updated': timestamp,
                        'success': False,
                        'error': str(e)
                    }
                
                finally:
                    await browser.close()
        
        except Exception as e:
            return {
                'brand_id': brand_id,
                'brand_name': brand_name,
                'series_id': series_id,
                'series_name': series_name,
                'total_pages': 0,
                'current_page_count': 0,
                'data_range': "0",
                'min_total_data': 0,
                'max_total_data': 0,
                'processed_by': f"thread_{thread_id}",
                'last_updated': timestamp,
                'success': False,
                'error': str(e)
            }
    
    def _estimate_time(self, series_count):
        """估算处理时间"""
        avg_time_per_series = 3.0  # 每个车系约3秒
        total_time = series_count * avg_time_per_series / self.max_workers
        
        if total_time < 60:
            return f"{total_time:.0f} 秒"
        elif total_time < 3600:
            return f"{total_time/60:.1f} 分钟"
        else:
            return f"{total_time/3600:.1f} 小时"
    
    async def _save_final_results(self, big_brands):
        """保存最终分析结果"""
        total_time = time.time() - self.start_time
        success_series = [s for s in self.results if s.get('success')]
        success_brand_count = 0
        brand_summary = []

        for brand in big_brands:
            brand_series = [s for s in self.results if s['brand_id'] == brand['brand_id'] and s.get('success')]
            if brand_series:
                total_min = sum(s['min_total_data'] for s in brand_series)
                total_max = sum(s['max_total_data'] for s in brand_series)
                total_pages = sum(s['total_pages'] for s in brand_series)
                success_brand_count += 1
                brand_summary.append({
                    'brand_id': brand['brand_id'],
                    'brand_name': brand['brand_name'],
                    'series_success': len(brand_series),
                    'total_pages': total_pages,
                    'min_total_data': total_min,
                    'max_total_data': total_max,
                    'data_range': f"{total_min}-{total_max}"
                })

        analysis_data = {
            "metadata": {
                "source": "dongchedi",
                "data_type": self.analysis_type,
                "generator": "series_analyzer",
                "generated_at": datetime.now().isoformat(),
                "version": "1.0",
                "thread_count": self.max_workers
            },
            "summary": {
                "target_brands": len(big_brands),
                "successful_brands": success_brand_count,
                "total_series": self.total_series,
                "processed_series": self.processed_count,
                "successful_series": len(success_series),
                "duration_seconds": total_time
            },
            "brand_summary": brand_summary,
            "data": self.results
        }
        
        try:
            with open(self.output_file, 'w', encoding='utf-8') as f:
                json.dump(analysis_data, f, ensure_ascii=False, indent=2)
            
            print(f"\n💾 车系分析结果已保存到: {self.output_file}")
            
        except Exception as e:
            print(f"❌ 保存结果失败: {e}")
    
    def _show_statistics(self, big_brands):
        """显示统计信息"""
        print("\n" + "=" * 60)
        print("📊 车系分析统计")
        print("=" * 60)
        
        total_time = time.time() - self.start_time
        successful_series = len([r for r in self.results if r['success']])
        
        print(f"🎯 处理统计:")
        print(f"   - 目标品牌数: {len(big_brands)}")
        print(f"   - 总车系数: {self.total_series}")
        print(f"   - 成功分析: {successful_series}")
        print(f"   - 分析失败: {self.total_series - successful_series}")
        print(f"   - 处理时间: {total_time:.1f} 秒")
        print(f"   - 平均速度: {self.total_series/total_time:.2f} 车系/秒")
        
        # 显示品牌汇总
        print(f"\n📈 品牌数据汇总:")
        for brand in big_brands:
            brand_series = [s for s in self.results if s['brand_id'] == brand['brand_id'] and s['success']]
            
            if brand_series:
                total_min = sum(s['min_total_data'] for s in brand_series)
                total_max = sum(s['max_total_data'] for s in brand_series)
                
                print(f"   - {brand['brand_name']}: {len(brand_series)}个车系, "
                      f"数据范围 {total_min:,}-{total_max:,} 条")
            else:
                print(f"   - {brand['brand_name']}: 0个成功车系")

async def main():
    """主函数"""
    analyzer = SeriesAnalyzer(max_workers=3)
    await analyzer.analyze_brands_by_series()

if __name__ == "__main__":
    asyncio.run(main())
