# 懂车帝二手车数据爬虫项目

## ⚠️ 重要声明

**这是一个基于 Playwright 框架的二手车数据爬虫项目，用于从懂车帝二手车频道抓取品牌、车系和车型数据。**

**仅用于学习和研究目的，不涉及任何商业用途。主体代码都是大模型自主生成。**

## 📋 项目简介

本项目通过提取懂车帝页面中的 `__NEXT_DATA__` 结构化 JSON 数据，实现四阶段完整数据采集：

1. **品牌采集** - 获取所有汽车品牌（637+个）
2. **车系采集** - 获取各品牌下的车系信息
3. **列表概览** - 翻页采集所有车辆的概览数据（含详情链接）
4. **详情采集** - 访问详情页获取真实价格、详细参数、高清图片

**核心优势：** 基于 `__NEXT_DATA__` 提取，绕过字体反爬机制，直接获取真实价格和里程数据。

## 🛠️ 技术栈

- **Python 3.x**
- **Playwright** - 网页自动化框架
- **asyncio** - 异步并发
- **threading** - 多线程并行

## 📁 项目结构

```
carInfoHandle/
├── dongchedi_api.py              # 核心采集模块（基于 __NEXT_DATA__）
├── dongchedi_collector.py        # 完整流程编排器（四阶段串联）
├── test_new_flow.py              # 快速验证测试（单品牌跑通四阶段）
├── dongchedi_brand.json          # 品牌数据（自动生成）
├── dongchedi_series.json         # 车系数据（自动生成）
├── dongchedi_car_overview.json   # 列表概览数据（自动生成）
├── dongchedi_car_detail.json     # 详情数据汇总（自动生成）
├── car_detail_data/              # 各品牌详情数据（自动生成）
└── README.md
```

## 🚀 使用步骤

### 一键完整采集
```bash
python dongchedi_collector.py
```

自动执行四个阶段：品牌 → 车系 → 列表概览 → 详情页。

### 配置选项

在 `dongchedi_collector.py` 的 `main()` 函数中修改：

```python
collector = DongchediCollector(
    max_workers=5,    # 车系采集线程数
    headless=True,    # 是否无头模式
)

# 指定品牌（None=全部）
target_brands = ["奇瑞", "吉利"]

# 跳过已完成的阶段
skip_stages = [1, 2]  # 跳过品牌和车系采集
```

### 快速测试
```bash
python test_new_flow.py
```

用一个小品牌跑通四阶段，验证数据结构。

## 🔑 技术原理：__NEXT_DATA__

懂车帝是 Next.js 应用，每个页面的 `<script id="__NEXT_DATA__">` 标签包含完整的结构化 JSON 数据。

### 反爬机制

懂车帝对价格、里程等敏感数字使用**自定义字体加密**（`fontStyleString`），DOM 中显示为乱码。

**解决方案：**
- 列表页的 `sh_price`、`official_price`、`car_mileage` 被加密 → 无法直接使用
- 详情页的 `source_sh_price`（单位：分）和 `source_offical_price` 是**真实数值**
- `important_text` 字段（如 `"2023年上牌 | 1万公里 | 沈阳车源"`）也是明文

### 各页面数据来源

| 页面 | __NEXT_DATA__ 路径 | 关键数据 |
|------|---------------------|----------|
| 列表页 | `pageProps.allBrand` | 所有品牌（按字母分组） |
| 列表页 | `pageProps.seriesList` | 当前品牌的车系列表 |
| 列表页 | `pageProps.carList` | 车辆概览列表 + 总数 + 翻页标记 |
| 详情页 | `pageProps.skuDetail` | 完整车辆信息（真实价格/参数/图片） |

## 📊 四阶段数据结构

### 阶段1：dongchedi_brand.json（品牌数据）

```json
{
  "metadata": {
    "source": "dongchedi",
    "data_type": "brand_list",
    "generator": "dongchedi_collector",
    "generated_at": "2026-02-07T17:00:00",
    "version": "2.0"
  },
  "summary": {
    "total_brands": 637,
    "hot_brands": 20
  },
  "data": [
    {
      "brand_id": 1,
      "brand_name": "大众",
      "brand_logo": "https://p1-dcd.byteimg.com/img/...",
      "pinyin": "D"
    }
  ]
}
```

| 字段 | 说明 |
|------|------|
| `brand_id` | 品牌唯一ID |
| `brand_name` | 品牌名称 |
| `brand_logo` | 品牌Logo URL |
| `pinyin` | 拼音首字母（用于分组） |

### 阶段2：dongchedi_series.json（车系数据）

```json
{
  "metadata": {
    "source": "dongchedi",
    "data_type": "series_list",
    "generator": "dongchedi_collector",
    "generated_at": "2026-02-07T17:05:00",
    "version": "2.0",
    "thread_count": 5
  },
  "summary": {
    "total_brands": 637,
    "processed_brands": 637,
    "failed_brands": 2,
    "total_series": 4500,
    "duration_seconds": 320.5
  },
  "data": [
    {
      "series_id": 1092,
      "series_name": "瑞虎3x",
      "image_url": "http://p9-dcd.byteimg.com/...",
      "brand_id": 18,
      "brand_name": "奇瑞"
    }
  ]
}
```

| 字段 | 说明 |
|------|------|
| `series_id` | 车系唯一ID |
| `series_name` | 车系名称 |
| `image_url` | 车系图片 URL |
| `brand_id` | 所属品牌ID |
| `brand_name` | 所属品牌名称 |

### 阶段3：dongchedi_car_overview.json（列表概览）

```json
{
  "metadata": {
    "source": "dongchedi",
    "data_type": "car_overview",
    "generator": "dongchedi_collector",
    "generated_at": "2026-02-07T18:00:00",
    "version": "2.0"
  },
  "summary": {
    "total_brands": 637,
    "total_cars": 58000,
    "duration_seconds": 3600,
    "brand_stats": [
      { "brand_id": 1, "brand_name": "大众", "series_count": 15, "car_count": 10050 }
    ]
  },
  "data": [
    {
      "sku_id": 22676374,
      "spu_id": 22109990,
      "title": "瑞虎3x 2022款 钻石版 1.5L CVT3克拉II型",
      "brand_id": 18,
      "brand_name": "奇瑞",
      "series_id": 1092,
      "series_name": "瑞虎3x",
      "car_id": 59627,
      "car_name": "钻石版 1.5L CVT3克拉II型",
      "car_year": 2022,
      "image": "https://p3-dcd-sign.byteimg.com/...",
      "car_source_city": "沈阳",
      "transfer_cnt": 1,
      "shop_id": "46274",
      "car_source_type": "自营",
      "authentication_method": "非官方认证",
      "tags": ["检测报告"],
      "detail_url": "https://www.dongchedi.com/usedcar/22676374",
      "_encrypted_sh_price": ".",
      "_encrypted_official_price": ".",
      "_encrypted_mileage": ""
    }
  ]
}
```

| 字段 | 说明 |
|------|------|
| `sku_id` | 车辆唯一ID（用于构建详情URL） |
| `spu_id` | SPU ID |
| `title` | 完整标题 |
| `brand_id` / `brand_name` | 品牌信息 |
| `series_id` / `series_name` | 车系信息 |
| `car_year` | 年款 |
| `image` | 缩略图 URL |
| `car_source_city` | 车源城市 |
| `transfer_cnt` | 过户次数 |
| `tags` | 标签列表 |
| `detail_url` | 详情页链接 |
| `_encrypted_*` | 被字体加密的字段（需到详情页获取真实值） |

### 阶段4：dongchedi_car_detail.json（详情数据）

```json
{
  "metadata": {
    "source": "dongchedi",
    "data_type": "car_detail_full",
    "generator": "dongchedi_collector",
    "generated_at": "2026-02-07T20:00:00",
    "version": "2.0"
  },
  "summary": {
    "total_attempted": 58000,
    "successful": 57500,
    "failed": 500,
    "total_images": 517500,
    "duration_seconds": 7200
  },
  "data": [
    {
      "sku_id": "22676374",
      "spu_id": "22109990",
      "title": "瑞虎3x 2022款 钻石版 1.5L CVT3克拉II型",
      "important_text": "2023年上牌 | 1万公里 | 沈阳车源",

      "sh_price": 3.98,
      "official_price": 6.49,
      "include_tax_price": "7.19万",
      "source_sh_price": 3980000,
      "source_offical_price": 6490000,

      "brand_id": 18,
      "brand_name": "奇瑞",
      "series_id": 1092,
      "series_name": "瑞虎3x",
      "car_id": 59627,
      "car_name": "钻石版 1.5L CVT3克拉II型",
      "year": 2022,
      "body_color": "白色",

      "params": {
        "上牌地": "沈阳",
        "车源地": "沈阳",
        "过户次数": "1次",
        "上牌时间": "2023年04月",
        "排量": "1.5L",
        "变速箱": "自动",
        "保养方式": "无保养",
        "车身颜色": "白色",
        "内饰颜色": "深色"
      },

      "config": {
        "power": {
          "capacity": "1.5L",
          "horsepower": "116马力",
          "fuel_form": "汽油",
          "gearbox": "CVT无级变速(模拟9挡)",
          "acceleration_time": "-"
        },
        "space": {
          "length": "4200",
          "width": "1760",
          "height": "1570",
          "wheelbase": "2555"
        },
        "manipulation": {
          "driver_form": "前置前驱",
          "front_suspension": "麦弗逊式独立悬挂",
          "rear_suspension": "纵臂扭转梁式非独立悬挂"
        }
      },

      "images": [
        "https://p9-dcd-sign.byteimg.com/tos-cn-i-f042mdwyw7/...",
        "https://p9-dcd-sign.byteimg.com/tos-cn-i-f042mdwyw7/..."
      ],

      "highlights": [
        { "name": "上坡辅助", "icon": "https://..." },
        { "name": "定速巡航", "icon": "https://..." }
      ],

      "shop": {
        "shop_id": "46274",
        "shop_name": "沈阳市聚达车业",
        "shop_short_name": "沈阳众联车行",
        "city_name": "沈阳",
        "shop_address": "沈阳市于洪区红星路五洲车世界室外众联车行",
        "business_time": "00:00-23:00",
        "sales_range": "售全国",
        "sales_car_num": 3
      },

      "report": {
        "has_report": true,
        "eva_level": 0,
        "overview": [
          { "name": "安全/底盘", "overview": "气囊安全、传动、悬挂、转向、制动系统,无更换,或异常。" }
        ]
      },

      "financial": {
        "down_payment": "1.2",
        "month_pay": "939",
        "repayment_cycle": 36
      },

      "tags": ["懂车帝认证｜3星", "含过户费"],
      "description": "大家好，今天给大家介绍一款性价比超高的二手车...",
      "detail_url": "https://www.dongchedi.com/usedcar/22676374",
      "collected_at": "2026-02-07T20:05:00"
    }
  ]
}
```

#### 详情字段说明

| 分类 | 字段 | 说明 |
|------|------|------|
| **标识** | `sku_id` | 车辆唯一ID |
| | `spu_id` | SPU ID |
| | `title` | 完整标题 |
| | `important_text` | 摘要（明文，含上牌时间/里程/车源） |
| **真实价格** | `sh_price` | 二手价（万元，如 `3.98`） |
| | `official_price` | 官方指导价（万元，如 `6.49`） |
| | `include_tax_price` | 含税价（字符串） |
| | `source_sh_price` | 二手价原始值（分，如 `3980000`） |
| | `source_offical_price` | 指导价原始值（分） |
| **基本信息** | `brand_id` / `brand_name` | 品牌 |
| | `series_id` / `series_name` | 车系 |
| | `year` | 年款 |
| | `body_color` | 车身颜色 |
| **参数** | `params` | 字典：上牌地/车源地/过户次数/上牌时间/排量/变速箱/保养/颜色 |
| **配置** | `config.power` | 排量/马力/燃油/变速箱/加速时间 |
| | `config.space` | 长/宽/高/轴距（mm） |
| | `config.manipulation` | 驱动形式/前后悬挂 |
| **图片** | `images` | 高清图片URL数组（通常9张） |
| **亮点** | `highlights` | 亮点配置列表（名称+图标） |
| **商家** | `shop` | 店名/地址/营业时间/销售范围 |
| **检测** | `report` | 检测报告（有无/评级/各项概述） |
| **金融** | `financial` | 首付/月供/期数 |
| **其他** | `tags` | 标签列表 |
| | `description` | 车辆描述文案 |

### car_detail_data/{品牌名}_N_details.json（单品牌详情）

与 `dongchedi_car_detail.json` 中的 `data[]` 结构相同，按品牌拆分存储。

## ⚖️ 免责声明

- 本项目仅用于技术学习和研究目的
- 请遵守目标网站的 robots.txt 和使用条款
- 不得用于商业用途或大规模数据采集
- 使用本项目所产生的任何后果由使用者自行承担

## 📝 注意事项

1. 请合理控制爬取频率，避免对目标网站造成压力
2. 建议在学习和测试环境中使用
3. 定期检查目标网站的结构变化，及时调整代码
4. **运行顺序：** `dongchedi_collector.py` 自动按阶段顺序执行，也可通过 `skip_stages` 跳过已完成阶段
5. **网络延迟：** 程序已内置延迟避免请求过快
6. **数据量：** 全量采集可能需要数小时，建议先用 `test_new_flow.py` 验证

---

**再次声明：此项目完全用于学习目的，代码主要由 AI 大模型生成，仅供技术研究和学习交流使用。**
