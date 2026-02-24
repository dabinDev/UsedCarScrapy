"""
数据库管理模块 - 实时同步采集数据到 MySQL
使用 aiomysql 异步连接池，与采集流程无缝集成
"""

import json
import aiomysql
from datetime import datetime
from typing import Dict, List, Optional

from db_config import DB_CONFIG


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
        sql = """
            INSERT INTO brand (brand_id, brand_name, brand_logo, pinyin, source)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                brand_name=VALUES(brand_name),
                brand_logo=VALUES(brand_logo),
                pinyin=VALUES(pinyin)
        """
        bid = str(brand.get("brand_id") or brand.get("brand_slug", ""))
        source = "guazi" if brand.get("brand_slug") else "dongchedi"
        await self._execute(sql, (
            bid,
            brand.get("brand_name", ""),
            brand.get("brand_logo", ""),
            brand.get("pinyin") or brand.get("brand_slug", ""),
            source,
        ))

    async def upsert_brands(self, brands: List[Dict]):
        for b in brands:
            await self.upsert_brand(b)
        print(f"   💾 品牌入库: {len(brands)} 条")

    # ================================================================
    # 车系
    # ================================================================

    async def upsert_series(self, s: Dict):
        sql = """
            INSERT INTO series (series_id, brand_id, series_name, image_url, source)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                brand_id=VALUES(brand_id),
                series_name=VALUES(series_name),
                image_url=VALUES(image_url)
        """
        sid = str(s.get("series_id") or s.get("series_slug", ""))
        bid = str(s.get("brand_id") or s.get("brand_slug", ""))
        source = "guazi" if s.get("series_slug") else "dongchedi"
        await self._execute(sql, (
            sid,
            bid,
            s.get("series_name", ""),
            s.get("image_url", ""),
            source,
        ))

    async def upsert_series_list(self, series_list: List[Dict]):
        for s in series_list:
            await self.upsert_series(s)
        print(f"   💾 车系入库: {len(series_list)} 条")

    # ================================================================
    # 概览
    # ================================================================

    async def upsert_overview(self, car: Dict):
        source = "guazi" if str(car.get("sku_id", "")).startswith("c") else "dongchedi"
        sql = """
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
        tags = car.get("tags")
        tags_json = json.dumps(tags, ensure_ascii=False) if tags else None
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        await self._execute(sql, (
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
        ))

    async def upsert_overviews(self, cars: List[Dict]):
        for c in cars:
            await self.upsert_overview(c)
        print(f"   💾 概览入库: {len(cars)} 条")

    # ================================================================
    # 详情（拆分到多张表）
    # ================================================================

    async def upsert_detail(self, d: Dict):
        """一条详情数据 → 写入 car_detail + car_params + car_config + car_image + shop + car_highlight + car_report + car_financial"""
        sku_id = d.get("sku_id")
        if not sku_id:
            return

        # 判断数据来源
        source = "guazi" if str(sku_id).startswith("c") else "dongchedi"

        # --- car_detail ---
        await self._execute("""
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
        """, (
            str(sku_id),
            _safe_str(d.get("spu_id"), None),
            _safe_str(d.get("title"), ""),
            _safe_str(d.get("important_text"), ""),
            _clean_price(d.get("sh_price")),
            _clean_price(d.get("official_price")),
            _clean_price(d.get("include_tax_price")),
            _clean_price(d.get("source_sh_price")),
            _clean_price(d.get("source_offical_price")),
            _safe_str(d.get("brand_id"), None),
            _safe_str(d.get("brand_name"), ""),
            _safe_str(d.get("series_id"), None),
            _safe_str(d.get("series_name"), ""),
            _safe_str(d.get("car_id"), None),
            _safe_str(d.get("car_name"), ""),
            _safe_str(d.get("year"), None),
            _safe_str(d.get("body_color"), ""),
            _safe_str(d.get("description"), None),
            _safe_str(d.get("detail_url"), ""),
            _safe_str(d.get("detail_params_url"), ""),
            d.get("price_source", ""),
            source,
            _safe_str(d.get("collected_at"), None),
        ))

        # --- car_params ---
        params = d.get("params") or {}
        if params:
            # 兼容懂车帝和瓜子的参数键名
            displacement = params.get("排量") or params.get("发动机") or ""
            transmission = params.get("变速箱") or ""
            await self._execute("""
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
            """, (
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
            ))

        # --- car_config ---
        config = d.get("config") or {}
        detail_params = d.get("detail_params")
        if config or detail_params:
            dp_json = json.dumps(detail_params, ensure_ascii=False) if detail_params else None
            await self._execute("""
                INSERT INTO car_config (
                    sku_id, power, transmission, drive_type, dimensions,
                    detail_params
                ) VALUES (%s,%s,%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE
                    power=VALUES(power), transmission=VALUES(transmission),
                    drive_type=VALUES(drive_type), dimensions=VALUES(dimensions),
                    detail_params=VALUES(detail_params)
            """, (
                str(sku_id),
                _safe_str(config.get("power"), ""),
                _safe_str(config.get("transmission"), ""),
                _safe_str(config.get("drive_type") or config.get("manipulation", {}).get("driver_form") or "", ""),
                _safe_str(config.get("dimensions") or config.get("space") or "", ""),
                dp_json,
            ))

        # --- car_image ---
        images = d.get("images") or []
        if images:
            # 先删旧图片再插入，保证幂等
            await self._execute("DELETE FROM car_image WHERE sku_id=%s", (str(sku_id),))
            for idx, url in enumerate(images):
                img_url = url if isinstance(url, str) else url.get("url", "")
                await self._execute("""
                    INSERT INTO car_image (sku_id, image_url, sort_order)
                    VALUES (%s, %s, %s)
                """, (str(sku_id), img_url, idx))

        # --- shop ---
        shop = d.get("shop") or {}
        shop_id = shop.get("shop_id") or shop.get("id")
        if shop_id:
            await self._execute("""
                INSERT INTO shop (shop_id, shop_name, shop_short_name, city, address,
                                  business_time, sales_range, sales_car_num, source)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    shop_name=VALUES(shop_name), shop_short_name=VALUES(shop_short_name),
                    city=VALUES(city), address=VALUES(address),
                    business_time=VALUES(business_time), sales_range=VALUES(sales_range),
                    sales_car_num=VALUES(sales_car_num)
            """, (
                str(shop_id),
                _safe_str(shop.get("shop_name"), ""),
                _safe_str(shop.get("shop_short_name"), ""),
                _safe_str(shop.get("city") or shop.get("city_name"), ""),
                _safe_str(shop.get("shop_address") or shop.get("address"), ""),
                _safe_str(shop.get("business_time"), ""),
                _safe_str(shop.get("sales_range"), ""),
                shop.get("sales_car_num", 0) or 0,
                source,
            ))

        # --- car_highlight ---
        highlights = d.get("highlights")
        tags = d.get("tags")
        if highlights or tags:
            hl_json = json.dumps(highlights, ensure_ascii=False) if highlights else None
            tg_json = json.dumps(tags, ensure_ascii=False) if tags else None
            await self._execute("""
                INSERT INTO car_highlight (sku_id, highlights, tags)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    highlights=VALUES(highlights), tags=VALUES(tags)
            """, (str(sku_id), hl_json, tg_json))

        # --- car_report ---
        report = d.get("report")
        if report is not None:
            has_report = 1 if report else 0
            rp_json = json.dumps(report, ensure_ascii=False) if isinstance(report, dict) else None
            await self._execute("""
                INSERT INTO car_report (sku_id, has_report, report_data)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    has_report=VALUES(has_report), report_data=VALUES(report_data)
            """, (str(sku_id), has_report, rp_json))

        # --- car_financial ---
        financial = d.get("financial")
        if financial:
            fn_json = json.dumps(financial, ensure_ascii=False)
            await self._execute("""
                INSERT INTO car_financial (sku_id, financial_data)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE financial_data=VALUES(financial_data)
            """, (str(sku_id), fn_json))

    async def upsert_details(self, details: List[Dict]):
        for d in details:
            try:
                await self.upsert_detail(d)
            except Exception as e:
                print(f"   ⚠️ 详情入库失败 sku_id={d.get('sku_id')}: {e}")
        print(f"   💾 详情入库: {len(details)} 条")
