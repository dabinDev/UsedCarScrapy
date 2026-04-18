"""
数据库管理模块 - 实时同步采集数据到 MySQL
使用 aiomysql 异步连接池，与采集流程无缝集成
"""

import json
import aiomysql
from datetime import datetime
from typing import Dict, List, Optional

from db_config import DB_CONFIG

BRAND_UPSERT_SQL = """
    INSERT INTO brand (brand_id, brand_name, brand_logo, pinyin, source)
    VALUES (%s, %s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE
        brand_name=VALUES(brand_name),
        brand_logo=VALUES(brand_logo),
        pinyin=VALUES(pinyin)
"""

SERIES_UPSERT_SQL = """
    INSERT INTO series (series_id, brand_id, series_name, image_url, source)
    VALUES (%s, %s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE
        brand_id=VALUES(brand_id),
        series_name=VALUES(series_name),
        image_url=VALUES(image_url)
"""

OVERVIEW_UPSERT_SQL = """
    INSERT INTO car_overview (
        sku_id, spu_id, brand_id, series_id, car_id,
        title, car_name, car_year, image, sh_price,
        car_source_city, transfer_cnt, mileage, shop_id,
        car_source_type, authentication_method, tags, detail_url,
        source, collected_at
    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    ON DUPLICATE KEY UPDATE
        title=VALUES(title), car_name=VALUES(car_name),
        car_year=VALUES(car_year), image=VALUES(image),
        sh_price=VALUES(sh_price),
        car_source_city=VALUES(car_source_city),
        transfer_cnt=VALUES(transfer_cnt), mileage=VALUES(mileage),
        tags=VALUES(tags), collected_at=VALUES(collected_at)
"""

CAR_DETAIL_UPSERT_SQL = """
    INSERT INTO car_detail (
        sku_id, spu_id, title, important_text,
        sh_price, official_price, include_tax_price,
        source_sh_price, source_official_price,
        brand_id, brand_name, series_id, series_name,
        car_id, car_name, year, body_color,
        description, detail_url, detail_params_url,
        price_source, source, collected_at
    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    ON DUPLICATE KEY UPDATE
        title=VALUES(title), sh_price=VALUES(sh_price),
        official_price=VALUES(official_price),
        include_tax_price=VALUES(include_tax_price),
        description=VALUES(description),
        price_source=VALUES(price_source),
        collected_at=VALUES(collected_at)
"""

CAR_PARAMS_UPSERT_SQL = """
    INSERT INTO car_params (
        sku_id, register_city, source_city, transfer_cnt,
        register_date, displacement, transmission,
        emission, drive_mode, mileage,
        maintenance, body_color, interior_color
    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    ON DUPLICATE KEY UPDATE
        register_city=VALUES(register_city),
        source_city=VALUES(source_city),
        transfer_cnt=VALUES(transfer_cnt),
        register_date=VALUES(register_date),
        displacement=VALUES(displacement),
        transmission=VALUES(transmission),
        emission=VALUES(emission),
        drive_mode=VALUES(drive_mode),
        mileage=VALUES(mileage),
        maintenance=VALUES(maintenance),
        body_color=VALUES(body_color),
        interior_color=VALUES(interior_color)
"""

CAR_CONFIG_UPSERT_SQL = """
    INSERT INTO car_config (
        sku_id, power, transmission, drive_type, dimensions,
        detail_params
    ) VALUES (%s,%s,%s,%s,%s,%s)
    ON DUPLICATE KEY UPDATE
        power=VALUES(power), transmission=VALUES(transmission),
        drive_type=VALUES(drive_type), dimensions=VALUES(dimensions),
        detail_params=VALUES(detail_params)
"""

CAR_IMAGE_INSERT_SQL = """
    INSERT INTO car_image (sku_id, image_url, sort_order)
    VALUES (%s, %s, %s)
"""

SHOP_UPSERT_SQL = """
    INSERT INTO shop (shop_id, shop_name, shop_short_name, city, address,
                      business_time, sales_range, sales_car_num, source)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE
        shop_name=VALUES(shop_name), shop_short_name=VALUES(shop_short_name),
        city=VALUES(city), address=VALUES(address),
        business_time=VALUES(business_time), sales_range=VALUES(sales_range),
        sales_car_num=VALUES(sales_car_num)
"""

CAR_HIGHLIGHT_UPSERT_SQL = """
    INSERT INTO car_highlight (sku_id, highlights, tags)
    VALUES (%s, %s, %s)
    ON DUPLICATE KEY UPDATE
        highlights=VALUES(highlights), tags=VALUES(tags)
"""

CAR_REPORT_UPSERT_SQL = """
    INSERT INTO car_report (sku_id, has_report, report_data)
    VALUES (%s, %s, %s)
    ON DUPLICATE KEY UPDATE
        has_report=VALUES(has_report), report_data=VALUES(report_data)
"""

CAR_FINANCIAL_UPSERT_SQL = """
    INSERT INTO car_financial (sku_id, financial_data)
    VALUES (%s, %s)
    ON DUPLICATE KEY UPDATE financial_data=VALUES(financial_data)
"""


def _safe_str(val, default=""):
    """安全转换：dict/list -> JSON字符串, None -> default, 其他 -> str"""
    if val is None:
        return default
    if isinstance(val, (dict, list)):
        return json.dumps(val, ensure_ascii=False)
    return val


def _clean_price(val):
    """清洗价格字段：'18.61万' -> 18.61, 纯数字直接返回, 无法解析返回None"""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return val
    s = str(val).strip().replace(",", "")
    s = s.replace("万", "").replace("元", "").strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _build_brand_row(brand: Dict):
    bid = str(brand.get("brand_id") or brand.get("brand_slug", ""))
    source = "guazi" if brand.get("brand_slug") else "dongchedi"
    return (
        bid,
        brand.get("brand_name", ""),
        brand.get("brand_logo", ""),
        brand.get("pinyin") or brand.get("brand_slug", ""),
        source,
    )


def _build_series_row(series: Dict):
    sid = str(series.get("series_id") or series.get("series_slug", ""))
    bid = str(series.get("brand_id") or series.get("brand_slug", ""))
    source = "guazi" if series.get("series_slug") else "dongchedi"
    return (
        sid,
        bid,
        series.get("series_name", ""),
        series.get("image_url", ""),
        source,
    )


def _build_overview_row(car: Dict, collected_at: Optional[str] = None):
    source = "guazi" if str(car.get("sku_id", "")).startswith("c") else "dongchedi"
    tags = car.get("tags")
    tags_json = json.dumps(tags, ensure_ascii=False) if tags else None
    now = collected_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return (
        str(car.get("sku_id", "")),
        _safe_str(car.get("spu_id"), None),
        _safe_str(car.get("brand_id"), None),
        _safe_str(car.get("series_id"), None),
        _safe_str(car.get("car_id"), None),
        car.get("title", ""),
        car.get("car_name", ""),
        _safe_str(car.get("car_year"), None),
        car.get("image", ""),
        _clean_price(car.get("sh_price")),
        car.get("car_source_city", ""),
        car.get("transfer_cnt", 0),
        _safe_str(car.get("_encrypted_mileage") or car.get("mileage"), ""),
        str(car.get("shop_id", "")),
        car.get("car_source_type", ""),
        car.get("authentication_method", ""),
        tags_json,
        car.get("detail_url", ""),
        source,
        now,
    )


def _build_detail_row(detail: Dict):
    sku_id = detail.get("sku_id")
    if not sku_id:
        return None

    source_official_price = detail.get("source_official_price")
    if source_official_price is None:
        source_official_price = detail.get("source_offical_price")

    return (
        str(sku_id),
        _safe_str(detail.get("spu_id"), None),
        _safe_str(detail.get("title"), ""),
        _safe_str(detail.get("important_text"), ""),
        _clean_price(detail.get("sh_price")),
        _clean_price(detail.get("official_price")),
        _clean_price(detail.get("include_tax_price")),
        _clean_price(detail.get("source_sh_price")),
        _clean_price(source_official_price),
        _safe_str(detail.get("brand_id"), None),
        _safe_str(detail.get("brand_name"), ""),
        _safe_str(detail.get("series_id"), None),
        _safe_str(detail.get("series_name"), ""),
        _safe_str(detail.get("car_id"), None),
        _safe_str(detail.get("car_name"), ""),
        _safe_str(detail.get("year"), None),
        _safe_str(detail.get("body_color"), ""),
        _safe_str(detail.get("description"), None),
        _safe_str(detail.get("detail_url"), ""),
        _safe_str(detail.get("detail_params_url"), ""),
        detail.get("price_source", ""),
        "guazi" if str(sku_id).startswith("c") else "dongchedi",
        _safe_str(detail.get("collected_at"), None),
    )


def _build_params_row(detail: Dict):
    sku_id = detail.get("sku_id")
    params = detail.get("params") or {}
    if not sku_id or not params:
        return None

    displacement = params.get("排量") or params.get("发动机") or ""
    transmission = params.get("变速箱") or ""
    return (
        str(sku_id),
        _safe_str(params.get("上牌地"), ""),
        _safe_str(params.get("车源地"), ""),
        _safe_str(params.get("过户次数"), ""),
        _safe_str(params.get("上牌时间"), ""),
        _safe_str(displacement, ""),
        _safe_str(transmission, ""),
        _safe_str(params.get("排放标准"), ""),
        _safe_str(params.get("驱动方式"), ""),
        _safe_str(params.get("里程/车龄"), ""),
        _safe_str(params.get("保养方式") or params.get("基础车况") or "", ""),
        _safe_str(params.get("车身颜色"), ""),
        _safe_str(params.get("内饰颜色"), ""),
    )


def _build_config_row(detail: Dict):
    sku_id = detail.get("sku_id")
    if not sku_id:
        return None

    config = detail.get("config") or {}
    detail_params = detail.get("detail_params")
    if not config and not detail_params:
        return None

    detail_params_json = json.dumps(detail_params, ensure_ascii=False) if detail_params else None
    return (
        str(sku_id),
        _safe_str(config.get("power"), ""),
        _safe_str(config.get("transmission"), ""),
        _safe_str(config.get("drive_type") or config.get("manipulation", {}).get("driver_form") or "", ""),
        _safe_str(config.get("dimensions") or config.get("space") or "", ""),
        detail_params_json,
    )


def _build_image_rows(detail: Dict):
    sku_id = detail.get("sku_id")
    images = detail.get("images") or []
    if not sku_id or not images:
        return []

    return [
        (
            str(sku_id),
            image if isinstance(image, str) else image.get("url", ""),
            index,
        )
        for index, image in enumerate(images)
    ]


def _build_shop_row(detail: Dict):
    shop = detail.get("shop") or {}
    shop_id = shop.get("shop_id") or shop.get("id")
    if not shop_id:
        return None

    sku_id = detail.get("sku_id")
    return (
        str(shop_id),
        _safe_str(shop.get("shop_name"), ""),
        _safe_str(shop.get("shop_short_name"), ""),
        _safe_str(shop.get("city") or shop.get("city_name"), ""),
        _safe_str(shop.get("shop_address") or shop.get("address"), ""),
        _safe_str(shop.get("business_time"), ""),
        _safe_str(shop.get("sales_range"), ""),
        shop.get("sales_car_num", 0) or 0,
        "guazi" if str(sku_id).startswith("c") else "dongchedi",
    )


def _build_highlight_row(detail: Dict):
    sku_id = detail.get("sku_id")
    if not sku_id:
        return None

    highlights = detail.get("highlights")
    tags = detail.get("tags")
    if not highlights and not tags:
        return None

    return (
        str(sku_id),
        json.dumps(highlights, ensure_ascii=False) if highlights else None,
        json.dumps(tags, ensure_ascii=False) if tags else None,
    )


def _build_report_row(detail: Dict):
    sku_id = detail.get("sku_id")
    report = detail.get("report")
    if not sku_id or report is None:
        return None

    return (
        str(sku_id),
        1 if report else 0,
        json.dumps(report, ensure_ascii=False) if isinstance(report, dict) else None,
    )


def _build_financial_row(detail: Dict):
    sku_id = detail.get("sku_id")
    financial = detail.get("financial")
    if not sku_id or not financial:
        return None

    return (
        str(sku_id),
        json.dumps(financial, ensure_ascii=False),
    )


class DBManager:
    """异步 MySQL 数据库管理器"""

    def __init__(self):
        self._pool: Optional[aiomysql.Pool] = None

    async def connect(self):
        """创建连接池"""
        self._pool = await aiomysql.create_pool(
            host=DB_CONFIG["host"],
            port=DB_CONFIG["port"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            db=DB_CONFIG["database"],
            charset=DB_CONFIG.get("charset", "utf8mb4"),
            autocommit=True,
            minsize=2,
            maxsize=20,
        )
        print(f"✅ 数据库连接成功: {DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}")

    async def close(self):
        """关闭连接池"""
        if self._pool:
            self._pool.close()
            await self._pool.wait_closed()
            print("✅ 数据库连接已关闭")

    async def _execute(self, sql: str, args=None):
        """执行单条SQL"""
        async with self._pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute(sql, args)
                return cur.lastrowid

    async def _executemany(self, sql: str, args_list: list):
        """批量执行SQL"""
        if not args_list:
            return
        async with self._pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.executemany(sql, args_list)

    # ================================================================
    # 品牌
    # ================================================================

    async def upsert_brand(self, brand: Dict):
        await self._execute(BRAND_UPSERT_SQL, _build_brand_row(brand))

    async def upsert_brands(self, brands: List[Dict]):
        await self._executemany(BRAND_UPSERT_SQL, [_build_brand_row(brand) for brand in brands])
        print(f"   💾 品牌入库: {len(brands)} 条")

    # ================================================================
    # 车系
    # ================================================================

    async def upsert_series(self, s: Dict):
        await self._execute(SERIES_UPSERT_SQL, _build_series_row(s))

    async def upsert_series_list(self, series_list: List[Dict]):
        await self._executemany(SERIES_UPSERT_SQL, [_build_series_row(series) for series in series_list])
        print(f"   💾 车系入库: {len(series_list)} 条")

    # ================================================================
    # 概览
    # ================================================================

    async def upsert_overview(self, car: Dict):
        await self._execute(OVERVIEW_UPSERT_SQL, _build_overview_row(car))

    async def upsert_overviews(self, cars: List[Dict]):
        collected_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        await self._executemany(
            OVERVIEW_UPSERT_SQL,
            [_build_overview_row(car, collected_at=collected_at) for car in cars],
        )
        print(f"   💾 概览入库: {len(cars)} 条")

    # ================================================================
    # 详情（拆分到多张表）
    # ================================================================

    async def upsert_detail(self, d: Dict):
        """一条详情数据 → 写入 car_detail + car_params + car_config + car_image + shop + car_highlight + car_report + car_financial"""
        sku_id = d.get("sku_id")
        if not sku_id:
            return

        detail_row = _build_detail_row(d)
        if detail_row:
            await self._execute(CAR_DETAIL_UPSERT_SQL, detail_row)

        params_row = _build_params_row(d)
        if params_row:
            await self._execute(CAR_PARAMS_UPSERT_SQL, params_row)

        config_row = _build_config_row(d)
        if config_row:
            await self._execute(CAR_CONFIG_UPSERT_SQL, config_row)

        image_rows = _build_image_rows(d)
        if image_rows:
            await self._delete_car_images([str(sku_id)])
            await self._executemany(CAR_IMAGE_INSERT_SQL, image_rows)

        shop_row = _build_shop_row(d)
        if shop_row:
            await self._execute(SHOP_UPSERT_SQL, shop_row)

        highlight_row = _build_highlight_row(d)
        if highlight_row:
            await self._execute(CAR_HIGHLIGHT_UPSERT_SQL, highlight_row)

        report_row = _build_report_row(d)
        if report_row:
            await self._execute(CAR_REPORT_UPSERT_SQL, report_row)

        financial_row = _build_financial_row(d)
        if financial_row:
            await self._execute(CAR_FINANCIAL_UPSERT_SQL, financial_row)

    async def _delete_car_images(self, sku_ids: List[str], chunk_size: int = 200):
        normalized_ids = list(dict.fromkeys(str(sku_id) for sku_id in sku_ids if sku_id))
        if not normalized_ids:
            return

        for offset in range(0, len(normalized_ids), chunk_size):
            chunk = normalized_ids[offset : offset + chunk_size]
            placeholders = ", ".join(["%s"] * len(chunk))
            sql = f"DELETE FROM car_image WHERE sku_id IN ({placeholders})"
            await self._execute(sql, tuple(chunk))

    async def upsert_details(self, details: List[Dict]):
        detail_map = {}
        for detail in details:
            sku_id = detail.get("sku_id")
            if sku_id:
                detail_map[str(sku_id)] = detail

        normalized_details = list(detail_map.values())
        detail_rows = []
        params_rows = []
        config_rows = []
        image_rows = []
        image_sku_ids = []
        shop_rows_by_id = {}
        highlight_rows = []
        report_rows = []
        financial_rows = []

        for detail in normalized_details:
            try:
                detail_row = _build_detail_row(detail)
                if detail_row:
                    detail_rows.append(detail_row)

                params_row = _build_params_row(detail)
                if params_row:
                    params_rows.append(params_row)

                config_row = _build_config_row(detail)
                if config_row:
                    config_rows.append(config_row)

                current_image_rows = _build_image_rows(detail)
                if current_image_rows:
                    image_sku_ids.append(str(detail["sku_id"]))
                    image_rows.extend(current_image_rows)

                shop_row = _build_shop_row(detail)
                if shop_row:
                    shop_rows_by_id[shop_row[0]] = shop_row

                highlight_row = _build_highlight_row(detail)
                if highlight_row:
                    highlight_rows.append(highlight_row)

                report_row = _build_report_row(detail)
                if report_row:
                    report_rows.append(report_row)

                financial_row = _build_financial_row(detail)
                if financial_row:
                    financial_rows.append(financial_row)
            except Exception as e:
                print(f"   ⚠️ 详情入库构建失败 sku_id={detail.get('sku_id')}: {e}")

        try:
            await self._executemany(CAR_DETAIL_UPSERT_SQL, detail_rows)
            await self._executemany(CAR_PARAMS_UPSERT_SQL, params_rows)
            await self._executemany(CAR_CONFIG_UPSERT_SQL, config_rows)
            await self._delete_car_images(image_sku_ids)
            await self._executemany(CAR_IMAGE_INSERT_SQL, image_rows)
            await self._executemany(SHOP_UPSERT_SQL, list(shop_rows_by_id.values()))
            await self._executemany(CAR_HIGHLIGHT_UPSERT_SQL, highlight_rows)
            await self._executemany(CAR_REPORT_UPSERT_SQL, report_rows)
            await self._executemany(CAR_FINANCIAL_UPSERT_SQL, financial_rows)
        except Exception as e:
            print(f"   ⚠️ 批量详情入库失败，回退逐条写入: {e}")
            for detail in normalized_details:
                try:
                    await self.upsert_detail(detail)
                except Exception as inner:
                    print(f"   ⚠️ 详情入库失败 sku_id={detail.get('sku_id')}: {inner}")

        print(f"   💾 详情入库: {len(normalized_details)} 条")
