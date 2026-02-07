# 懂车帝二手车数据爬虫项目

## ⚠️ 重要声明

**这是一个基于 Playwright 框架的二手车数据爬虫项目，用于从懂车帝二手车频道抓取品牌、车系和车型数据。**

**仅用于学习和研究目的，不涉及任何商业用途。主体代码都是大模型自主生成。**

## 📋 项目简介

本项目是一个网络爬虫示例，展示了如何使用 Playwright 框架进行网页数据抓取。项目主要功能包括：

- 从懂车帝二手车频道抓取汽车品牌数据
- 获取各品牌下的车系信息
- 收集具体车型的详细数据
- **智能分页检测和数据量估算**
- **分离式架构：品牌分析 + 数据采集**
- 数据存储为 JSON 格式

## 🛠️ 技术栈

- **Python 3.x**
- **Playwright** - 网页自动化框架
- **Requests** - HTTP 请求库
- **JSON** - 数据存储格式

## 📁 项目结构

```
carInfoHandle/
├── dongchedi_precise_crawler.py      # 核心爬虫类
├── comprehensive_brand_analyzer.py   # 综合品牌车系分析程序（推荐）
├── brand_analyzer.py                 # 品牌分析程序（单线程版）
├── brand_analyzer_fast.py            # 品牌分析程序（多线程版）
├── series_analyzer.py                # 车系分析程序
├── data_collector.py                 # 数据采集程序
├── comprehensive_brand_analysis.json # 综合品牌+车系汇总（自动生成）
├── dongchedi_brand.json              # 品牌分析结果（自动生成）
├── dongchedi_series.json             # 车系分析结果（自动生成）
├── dongchedi_car_detail.json         # 采集总结（自动生成）
├── brand_data/                       # 各品牌车型明细（自动生成）
└── README.md                         # 使用说明
```

## 🚀 使用步骤

### 推荐方案：综合品牌车系分析
```bash
python comprehensive_brand_analyzer.py
```

**功能：**
- 获取所有品牌信息
- 获取所有品牌的车系信息
- 分析每个车系的精确数据量
- 基于车系数据计算品牌精确数据量
- 建立品牌-车系关联关系
- 生成 `comprehensive_brand_analysis.json` 文件

**优势：**
- ✅ 不限制任何品牌，获取完整数据
- ✅ 基于车系级别的精确数据估算
- ✅ 避免167页限制问题
- ✅ 提供品牌-车系完整关联关系

### 备选方案：分步分析

#### 第一步：品牌分析
```bash
python brand_analyzer_fast.py
```

**功能：**
- 获取所有品牌信息
- 计算每个品牌的大概数据量
- 检测超过167页限制的超大数据品牌
- 生成 `dongchedi_brand.json` 文件（含 metadata/summary/data 结构）

#### 第二步：车系分析（可选）
```bash
python series_analyzer.py
```

**功能：**
- 针对超过167页限制的品牌
- 按车系进行细分查询
- 获取每个车系的准确数据量
- 生成 `dongchedi_series.json` 文件（含 metadata/summary/data 结构）

#### 第三步：数据采集
```bash
python data_collector.py
```

**功能：**
- 读取 `dongchedi_brand.json`（及可选 `dongchedi_series.json`）
- 循环采集各品牌的具体数据
- 将单品牌数据保存到 `brand_data/` 目录
- 生成统一采集总结 `dongchedi_car_detail.json`

## ⚙️ 配置选项

### 限制采集数量
在 `data_collector.py` 的 `main()` 函数中修改：

```python
# 每个品牌最多采集1000条数据
max_records_per_brand = 1000

# 只采集指定品牌
selected_brands = ['大众', '丰田', '本田']
```

### 采集所有数据
```python
# 采集所有数据
max_records_per_brand = None
selected_brands = None
```

## 📊 输出文件说明

### comprehensive_brand_analysis.json
**综合分析结果（推荐使用）**，包含：
- 所有品牌的精确数据量（基于车系汇总）
- 所有车系的详细数据量
- 品牌-车系完整关联关系
- 数据级别分类（基于实际数据量）

### dongchedi_brand.json
品牌分析结果，采用统一结构：
- `metadata`：数据来源、生成时间、版本、线程数
- `summary`：品牌总数、数据范围、需细分品牌统计
- `data`：逐品牌详情（含 `requires_series_analysis`、`data_level`、`last_updated` 等）

### dongchedi_series.json
车系分析结果，结构同样由 `metadata` + `summary` + `data` 组成：
- `summary` 统计目标品牌、成功品牌、车系列数
- `brand_summary` 聚合各品牌车系估算
- `data` 记录每个车系的页数、数据范围、处理线程、更新时间

### dongchedi_car_detail.json
采集总结，结构为：
- `metadata`：采集任务来源、生成时间、版本
- `summary`：尝试品牌数、成功/失败次数、总采集条数
- `data`：逐品牌采集明细（包含 `data_file` 指向 `brand_data/` 中的文件）

### brand_data/*.json
各品牌的具体数据，每个文件包含：
- 品牌名称
- 采集时间
- 总记录数
- 详细车辆数据

## 📄 JSON 数据结构详解

### dongchedi_brand.json 结构
```json
{
  "metadata": {
    "source": "dongchedi",
    "data_type": "brand_summary",
    "generator": "brand_analyzer",
    "generated_at": "2026-02-07T10:00:00",
    "version": "1.0",
    "thread_count": 5
  },
  "summary": {
    "total_brands": 100,
    "processed_brands": 100,
    "successful_brands": 98,
    "total_data_min": 50000,
    "total_data_max": 60000,
    "requires_series_analysis": 3,
    "data_level_distribution": {
      "少量数据": 50,
      "中等数据": 30,
      "大量数据": 15,
      "海量数据": 2,
      "超大数据": 3
    }
  },
  "data": [
    {
      "brand_id": 1,
      "brand_name": "大众",
      "total_pages": 167,
      "data_range": "10020-10080",
      "min_total_data": 10020,
      "max_total_data": 10080,
      "current_page_count": 60,
      "calculation_method": "pagination",
      "data_level": "超大数据",
      "requires_series_analysis": true,
      "warning": "数据量过大 (167页)，建议按车系细分查询",
      "processed_by": "thread_1",
      "last_updated": "2026-02-07T10:00:05",
      "success": true
    }
  ]
}
```

**字段说明：**
- `metadata.source`：数据来源标识
- `metadata.data_type`：数据类型标识
- `metadata.generator`：生成程序名称
- `metadata.generated_at`：生成时间（ISO 8601格式）
- `metadata.version`：数据结构版本号
- `metadata.thread_count`：使用的线程数
- `summary.total_brands`：总品牌数
- `summary.processed_brands`：已处理品牌数
- `summary.successful_brands`：成功分析的品牌数
- `summary.total_data_min/max`：总数据量估算范围
- `summary.requires_series_analysis`：需要车系细分的品牌数
- `summary.data_level_distribution`：各数据级别的品牌分布
- `data[].brand_id`：品牌ID
- `data[].brand_name`：品牌名称
- `data[].total_pages`：总页数
- `data[].data_range`：数据量范围字符串
- `data[].min_total_data/max_total_data`：最小/最大数据量
- `data[].current_page_count`：当前页数据条数
- `data[].calculation_method`：计算方法
- `data[].data_level`：数据级别（少量/中等/大量/海量/超大数据）
- `data[].requires_series_analysis`：是否需要车系分析
- `data[].warning`：警告信息
- `data[].processed_by`：处理线程标识
- `data[].last_updated`：最后更新时间
- `data[].success`：是否成功

### dongchedi_series.json 结构
```json
{
  "metadata": {
    "source": "dongchedi",
    "data_type": "series_subset",
    "generator": "series_analyzer",
    "generated_at": "2026-02-07T11:00:00",
    "version": "1.0",
    "thread_count": 3
  },
  "summary": {
    "target_brands": 3,
    "successful_brands": 3,
    "total_series": 45,
    "processed_series": 45,
    "successful_series": 45,
    "duration_seconds": 135.5
  },
  "brand_summary": [
    {
      "brand_id": 1,
      "brand_name": "大众",
      "series_success": 15,
      "total_pages": 150,
      "min_total_data": 9000,
      "max_total_data": 9100,
      "data_range": "9000-9100"
    }
  ],
  "data": [
    {
      "brand_id": 1,
      "brand_name": "大众",
      "series_id": 101,
      "series_name": "朗逸",
      "total_pages": 10,
      "current_page_count": 60,
      "data_range": "541-600",
      "min_total_data": 541,
      "max_total_data": 600,
      "processed_by": "thread_1",
      "last_updated": "2026-02-07T11:00:10",
      "success": true
    }
  ]
}
```

**字段说明：**
- `summary.target_brands`：目标品牌数
- `summary.successful_brands`：成功分析的品牌数
- `summary.total_series`：总车系数
- `summary.processed_series`：已处理车系数
- `summary.successful_series`：成功分析的车系数
- `summary.duration_seconds`：处理耗时（秒）
- `brand_summary[].series_success`：成功分析的车系数
- `data[].series_id`：车系ID
- `data[].series_name`：车系名称

### dongchedi_car_detail.json 结构
```json
{
  "metadata": {
    "source": "dongchedi",
    "data_type": "car_collection",
    "generator": "data_collector",
    "generated_at": "2026-02-07T12:00:00",
    "version": "1.0"
  },
  "summary": {
    "total_brands_attempted": 98,
    "successful_collections": 95,
    "failed_collections": 3,
    "total_records_collected": 58000
  },
  "data": [
    {
      "brand_id": 1,
      "brand_name": "大众",
      "collected_count": 10050,
      "pages_crawled": 167,
      "collection_time": "2026-02-07T12:05:00",
      "data_file": "大众_10050_records.json",
      "success": true
    }
  ]
}
```

**字段说明：**
- `summary.total_brands_attempted`：尝试采集的品牌数
- `summary.successful_collections`：成功采集的品牌数
- `summary.failed_collections`：失败的品牌数
- `summary.total_records_collected`：总采集记录数
- `data[].collected_count`：采集的记录数
- `data[].pages_crawled`：爬取的页数
- `data[].collection_time`：采集时间
- `data[].data_file`：数据文件名（指向 `brand_data/` 目录）

### brand_data/*.json 结构
```json
{
  "brand_name": "大众",
  "collection_time": "2026-02-07T12:05:00",
  "total_records": 10050,
  "data": [
    {
      "title": "2020款 大众 朗逸 1.5L 自动风尚版",
      "price": "8.50万",
      "mileage": "3.5万公里",
      "year": "2020",
      "location": "北京",
      "url": "https://www.dongchedi.com/...",
      "collected_at": "2026-02-07T12:05:10"
    }
  ]
}
```

**字段说明：**
- `brand_name`：品牌名称
- `collection_time`：采集时间
- `total_records`：总记录数
- `data[]`：车辆详情数组
- `data[].title`：车辆标题
- `data[].price`：价格
- `data[].mileage`：里程
- `data[].year`：年份
- `data[].location`：所在地
- `data[].url`：详情链接
- `data[].collected_at`：采集时间

## 🎯 使用场景

### 测试场景
```python
# 只采集少量数据进行测试
max_records_per_brand = 100
selected_brands = ['奇瑞风云']  # 选择数据量少的品牌
```

### 生产场景
```python
# 采集所有数据
max_records_per_brand = None
selected_brands = None
```

### 定向采集
```python
# 只采集特定品牌
max_records_per_brand = 5000
selected_brands = ['大众', '丰田', '本田', '奥迪']
```

## 📚 学习要点

本项目适合学习以下内容：

1. **Playwright 基础使用**
   - 页面导航和元素定位
   - 数据抓取和提取
   - 异步操作处理

2. **网页爬虫技术**
   - 动态内容抓取
   - 数据结构化存储
   - 错误处理和重试机制
   - **智能分页检测**
   - **数据量估算算法**

3. **项目组织**
   - 代码结构设计
   - 数据管理
   - 日志记录
   - **分离式架构设计**

## ⚖️ 免责声明

- 本项目仅用于技术学习和研究目的
- 请遵守目标网站的 robots.txt 和使用条款
- 不得用于商业用途或大规模数据采集
- 使用本项目所产生的任何后果由使用者自行承担

## 📝 注意事项

1. 请合理控制爬取频率，避免对目标网站造成压力
2. 建议在学习和测试环境中使用
3. 定期检查目标网站的结构变化，及时调整代码
4. **运行顺序：** 必须先运行 `brand_analyzer.py` 再运行 `data_collector.py`
5. **网络延迟：** 程序已内置延迟避免请求过快
6. **数据量：** 大品牌可能有上万条数据，采集时间较长

## 🔧 故障排除

### 品牌分析失败
- 检查网络连接
- 确认懂车帝网站可正常访问
- 查看错误信息并重试

### 数据采集失败
- 检查 `brands_analysis.json` 是否存在
- 确认品牌ID正确
- 查看具体错误信息

### 内存不足
- 减少 `max_records_per_brand` 值
- 分批采集品牌数据
- 增加系统内存

## 📈 性能优化建议

1. **分批采集：** 将大量品牌分成小批次采集
2. **限流设置：** 调整延迟时间避免被封IP
3. **存储优化：** 定期清理旧数据文件
4. **监控资源：** 监控CPU和内存使用情况

## 🤝 贡献

欢迎提出问题和改进建议，但请记住这是一个学习项目。

---

**再次声明：此项目完全用于学习目的，代码主要由 AI 大模型生成，仅供技术研究和学习交流使用。**
