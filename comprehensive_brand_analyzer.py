#!/usr/bin/env python3
"""
懂车帝全品牌车系分析程序
获取所有品牌的车系信息，建立品牌-车系关联关系，进行精确数据估算
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

class ComprehensiveBrandAnalyzer:
    def __init__(self, max_workers=8):
        self.crawler = DongchediPreciseCrawler()
        self.output_file = "comprehensive_brand_analysis.json"
        self.max_workers = max_workers
        self.results_lock = threading.Lock()
        self.brands_data = []
        self.series_data = []
        self.processed_brands = 0
        self.processed_series = 0
        self.total_brands = 0
        self.total_series = 0
        self.start_time = None
        
    async def analyze_all_brands_and_series(self):
        """分析所有品牌及其车系"""
        print("🚗 懂车帝全品牌车系分析程序")
        print("=" * 60)
        print(f"🔧 线程池配置: {self.max_workers} 个工作线程")
        
        self.start_time = time.time()
        
        # 第一步：获取所有品牌基础信息
        print("🔍 第一步：获取所有品牌信息...")
        brands = await self.crawler.get_all_brands()
        
        if not brands:
            print("❌ 获取品牌信息失败")
            return
        
        self.total_brands = len(brands)
        print(f"✅ 成功获取 {self.total_brands} 个品牌")
        
        # 第二步：获取所有品牌的车系信息
        print(f"\n🔍 第二步：获取所有品牌的车系信息...")
        await self._get_all_series_for_brands(brands)
        
        # 第三步：分析车系数据量
        print(f"\n🔍 第三步：分析车系数据量...")
        await self._analyze_all_series_data()
        
        # 第四步：计算品牌精确数据量
        print(f"\n🔍 第四步：计算品牌精确数据量...")
        await self._calculate_precise_brand_data()
        
        # 保存最终结果
        await self._save_final_results()
        
        # 显示统计信息
        self._show_final_statistics()
    
    async def _get_all_series_for_brands(self, brands):
        """获取所有品牌的车系信息"""
        print(f"🎯 开始获取 {len(brands)} 个品牌的车系信息...")
        
        # 创建任务队列
        task_queue = Queue()
        for brand in brands:
            task_queue.put(brand)
        
        # 启动线程池获取车系信息
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = []
            for i in range(min(self.max_workers, len(brands))):
                future = executor.submit(self._series_fetcher_worker, task_queue, i + 1)
                futures.append(future)
            
            # 等待所有线程完成
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    print(f"❌ 车系获取线程错误: {e}")
        
        print(f"✅ 完成！共获取 {len(self.series_data)} 个车系信息")
    
    def _series_fetcher_worker(self, task_queue, thread_id):
        """车系获取工作线程"""
        print(f"🧵 车系获取线程 {thread_id} 启动")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            while True:
                try:
                    brand = task_queue.get(timeout=1)
                    
                    result = loop.run_until_complete(
                        self._get_brand_series_info(brand, thread_id)
                    )
                    
                    with self.results_lock:
                        if result:
                            self.series_data.extend(result)
                        self.processed_brands += 1
                        
                        # 显示进度
                        progress = (self.processed_brands / self.total_brands) * 100
                        elapsed = time.time() - self.start_time
                        eta = (elapsed / self.processed_brands) * (self.total_brands - self.processed_brands)
                        
                        print(f"📊 车系获取进度: {self.processed_brands}/{self.total_brands} "
                              f"({progress:.1f}%) | "
                              f"线程{thread_id}: {brand['name']} | "
                              f"ETA: {eta:.0f}秒")
                    
                    task_queue.task_done()
                    
                except Empty:
                    break
                except Exception as e:
                    print(f"❌ 线程{thread_id}获取车系时出错: {e}")
                    task_queue.task_done()
        
        finally:
            loop.close()
            print(f"🧵 车系获取线程 {thread_id} 结束")
    
    async def _get_brand_series_info(self, brand, thread_id):
        """获取单个品牌的车系信息"""
        brand_id = brand["brand_id"]
        brand_name = brand["name"]
        
        try:
            # 访问品牌页面获取车系信息
            url = f"https://www.dongchedi.com/usedcar/x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-{brand_id}-x-1-1-x-x-x-x-x"
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                
                try:
                    await page.goto(url, wait_until="networkidle")
                    await page.wait_for_timeout(2000)
                    
                    # 多种车系选择器
                    series_selectors = [
                        'a[href*="/series/"]',
                        '.series-item a',
                        '.car-series a',
                        '[data-series-id] a',
                        'div[class*="series"] a',
                        'div[class*="car-series"] a',
                        'div[class*="series-item"] a'
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
                                        if series_id and text.strip():
                                            series_list.append({
                                                'brand_id': brand_id,
                                                'brand_name': brand_name,
                                                'series_id': series_id,
                                                'series_name': text.strip(),
                                                'href': href,
                                                'data_analyzed': False,
                                                'total_pages': 0,
                                                'data_range': "0",
                                                'min_total_data': 0,
                                                'max_total_data': 0
                                            })
                                except Exception:
                                    continue
                            
                            if series_list:
                                break
                    
                    return series_list[:100]  # 限制每个品牌最多100个车系
                
                finally:
                    await browser.close()
        
        except Exception as e:
            print(f"❌ 获取 {brand_name} 车系失败: {e}")
            return []
    
    def _extract_series_id(self, href):
        """从href中提取车系ID"""
        try:
            parts = href.split('/series/')
            if len(parts) > 1:
                series_part = parts[1].split('/')[0]
                if series_part.isdigit():
                    return int(series_part)
        except Exception:
            pass
        return None
    
    async def _analyze_all_series_data(self):
        """分析所有车系的数据量"""
        if not self.series_data:
            print("❌ 没有车系数据可分析")
            return
        
        self.total_series = len(self.series_data)
        print(f"🎯 开始分析 {self.total_series} 个车系的数据量...")
        
        # 创建任务队列
        task_queue = Queue()
        for series in self.series_data:
            task_queue.put(series)
        
        # 启动线程池分析车系数据
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = []
            for i in range(min(self.max_workers, 10)):
                future = executor.submit(self._series_analyzer_worker, task_queue, i + 1)
                futures.append(future)
            
            # 等待所有线程完成
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    print(f"❌ 车系分析线程错误: {e}")
        
        print(f"✅ 完成！共分析 {len([s for s in self.series_data if s['data_analyzed']])} 个车系数据")
    
    def _series_analyzer_worker(self, task_queue, thread_id):
        """车系分析工作线程"""
        print(f"🧵 车系分析线程 {thread_id} 启动")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            while True:
                try:
                    series = task_queue.get(timeout=1)
                    
                    result = loop.run_until_complete(
                        self._analyze_single_series_data(series, thread_id)
                    )
                    
                    with self.results_lock:
                        if result:
                            # 更新车系数据
                            for i, s in enumerate(self.series_data):
                                if (s['brand_id'] == result['brand_id'] and 
                                    s['series_id'] == result['series_id']):
                                    self.series_data[i] = result
                                    break
                        
                        self.processed_series += 1
                        
                        # 显示进度
                        progress = (self.processed_series / self.total_series) * 100
                        elapsed = time.time() - self.start_time
                        eta = (elapsed / self.processed_series) * (self.total_series - self.processed_series) if self.processed_series > 0 else 0
                        
                        print(f"📊 车系分析进度: {self.processed_series}/{self.total_series} "
                              f"({progress:.1f}%) | "
                              f"线程{thread_id}: {series['series_name']} | "
                              f"ETA: {eta:.0f}秒")
                    
                    task_queue.task_done()
                    
                except Empty:
                    break
                except Exception as e:
                    print(f"❌ 线程{thread_id}分析车系时出错: {e}")
                    task_queue.task_done()
        
        finally:
            loop.close()
            print(f"🧵 车系分析线程 {thread_id} 结束")
    
    async def _analyze_single_series_data(self, series, thread_id):
        """分析单个车系的数据量"""
        try:
            # 构建车系URL
            url = f"https://www.dongchedi.com/usedcar/x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-x-{series['brand_id']}-x-{series['series_id']}-1-x-x-x-x-x"
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                
                try:
                    await page.goto(url, wait_until="networkidle")
                    await page.wait_for_timeout(2000)
                    
                    # 获取车辆数量
                    vehicle_cards = await page.query_selector_all('a.usedcar-card_card__3vUrx')
                    current_page_count = len(vehicle_cards)
                    
                    # 获取分页信息
                    pagination_info = await self.crawler.get_pagination_info(page)
                    
                    if pagination_info:
                        total_pages = pagination_info.get('total_pages', 1)
                        
                        # 计算数据量范围
                        if total_pages > 1 and current_page_count > 0:
                            full_pages_data = (total_pages - 1) * current_page_count
                            min_total = full_pages_data + 1
                            max_total = full_pages_data + current_page_count
                            data_range = f"{min_total}-{max_total}"
                        else:
                            min_total = max_total = current_page_count
                            data_range = f"{current_page_count}"
                        
                        # 更新车系数据
                        series.update({
                            'data_analyzed': True,
                            'total_pages': total_pages,
                            'current_page_count': current_page_count,
                            'data_range': data_range,
                            'min_total_data': min_total,
                            'max_total_data': max_total,
                            'analysis_time': datetime.now().isoformat()
                        })
                    else:
                        # 无分页信息
                        series.update({
                            'data_analyzed': True,
                            'total_pages': 1,
                            'current_page_count': current_page_count,
                            'data_range': f"{current_page_count}",
                            'min_total_data': current_page_count,
                            'max_total_data': current_page_count,
                            'analysis_time': datetime.now().isoformat(),
                            'note': '无分页信息'
                        })
                    
                    return series
                
                finally:
                    await browser.close()
        
        except Exception as e:
            series.update({
                'data_analyzed': True,
                'total_pages': 0,
                'current_page_count': 0,
                'data_range': "0",
                'min_total_data': 0,
                'max_total_data': 0,
                'analysis_time': datetime.now().isoformat(),
                'error': str(e)
            })
            return series
    
    async def _calculate_precise_brand_data(self):
        """基于车系数据计算品牌精确数据量"""
        print("🎯 基于车系数据计算品牌精确数据量...")
        
        # 按品牌分组车系数据
        brand_series_map = {}
        for series in self.series_data:
            brand_id = series['brand_id']
            if brand_id not in brand_series_map:
                brand_series_map[brand_id] = {
                    'brand_id': brand_id,
                    'brand_name': series['brand_name'],
                    'series_list': [],
                    'total_series': 0,
                    'analyzed_series': 0,
                    'total_pages': 0,
                    'min_total_data': 0,
                    'max_total_data': 0,
                    'data_range': "0"
                }
            brand_series_map[brand_id]['series_list'].append(series)
        
        # 计算每个品牌的汇总数据
        for brand_id, brand_info in brand_series_map.items():
            series_list = brand_info['series_list']
            analyzed_series = [s for s in series_list if s['data_analyzed'] and s.get('min_total_data', 0) > 0]
            
            brand_info['total_series'] = len(series_list)
            brand_info['analyzed_series'] = len(analyzed_series)
            
            if analyzed_series:
                total_min = sum(s['min_total_data'] for s in analyzed_series)
                total_max = sum(s['max_total_data'] for s in analyzed_series)
                total_pages = sum(s['total_pages'] for s in analyzed_series)
                
                brand_info['total_pages'] = total_pages
                brand_info['min_total_data'] = total_min
                brand_info['max_total_data'] = total_max
                brand_info['data_range'] = f"{total_min}-{total_max}"
                brand_info['data_level'] = self._get_data_level_by_count(total_max)
            else:
                brand_info['data_level'] = "无数据"
        
        self.brands_data = list(brand_series_map.values())
        
        print(f"✅ 完成！计算了 {len(self.brands_data)} 个品牌的精确数据")
    
    def _get_data_level_by_count(self, count):
        """根据数据量判断级别"""
        if count == 0:
            return "无数据"
        elif count <= 300:
            return "少量"
        elif count <= 1200:
            return "中等"
        elif count <= 6000:
            return "大量"
        elif count <= 10000:
            return "海量"
        else:
            return "超大数据"
    
    async def _save_final_results(self):
        """保存最终分析结果"""
        analysis_data = {
            "analysis_time": datetime.now().isoformat(),
            "total_brands": self.total_brands,
            "total_series": self.total_series,
            "processed_brands": self.processed_brands,
            "processed_series": self.processed_series,
            "thread_count": self.max_workers,
            "total_processing_time": time.time() - self.start_time,
            "brands_summary": self.brands_data,
            "series_details": self.series_data
        }
        
        try:
            with open(self.output_file, 'w', encoding='utf-8') as f:
                json.dump(analysis_data, f, ensure_ascii=False, indent=2)
            
            print(f"\n💾 综合分析结果已保存到: {self.output_file}")
            
        except Exception as e:
            print(f"❌ 保存结果失败: {e}")
    
    def _show_final_statistics(self):
        """显示最终统计信息"""
        print("\n" + "=" * 60)
        print("📊 全品牌车系分析最终统计")
        print("=" * 60)
        
        total_time = time.time() - self.start_time
        successful_brands = len([b for b in self.brands_data if b['analyzed_series'] > 0])
        successful_series = len([s for s in self.series_data if s['data_analyzed'] and s.get('min_total_data', 0) > 0])
        
        print(f"🎯 处理统计:")
        print(f"   - 总品牌数: {self.total_brands}")
        print(f"   - 成功分析品牌: {successful_brands}")
        print(f"   - 总车系数: {self.total_series}")
        print(f"   - 成功分析车系: {successful_series}")
        print(f"   - 处理时间: {total_time:.1f} 秒")
        print(f"   - 平均速度: {self.total_brands/total_time:.2f} 品牌/秒")
        
        # 按数据级别分类统计
        level_stats = {}
        total_data_min = 0
        total_data_max = 0
        
        for brand in self.brands_data:
            level = brand['data_level']
            level_stats[level] = level_stats.get(level, 0) + 1
            total_data_min += brand['min_total_data']
            total_data_max += brand['max_total_data']
        
        print(f"\n📊 数据级别分布:")
        for level, count in sorted(level_stats.items()):
            percentage = (count / len(self.brands_data)) * 100
            print(f"   - {level}: {count} 个品牌 ({percentage:.1f}%)")
        
        print(f"\n📈 总体数据量:")
        print(f"   - 总数据量范围: {total_data_min:,} - {total_data_max:,} 条")
        
        # 显示前10大数据品牌
        top_brands = sorted([b for b in self.brands_data if b['min_total_data'] > 0], 
                           key=lambda x: x['max_total_data'], reverse=True)[:10]
        
        print(f"\n🏆 数据量前10品牌:")
        for i, brand in enumerate(top_brands, 1):
            print(f"   {i:2d}. {brand['brand_name']:12s} - {brand['data_range']:12s} 条 "
                  f"({brand['analyzed_series']}/{brand['total_series']}车系)")

async def main():
    """主函数"""
    analyzer = ComprehensiveBrandAnalyzer(max_workers=8)
    await analyzer.analyze_all_brands_and_series()

if __name__ == "__main__":
    asyncio.run(main())
