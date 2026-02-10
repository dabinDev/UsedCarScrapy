#!/usr/bin/env python3
"""
瓜子二手车采集客户端 - 对齐懂车帝数据结构，支持断点续采
流程：城市(本地) -> 品牌 -> 车系 -> 概览(列表) -> 详情
输出：brands.json / series.json / overviews.json / details.json / images.json / configs.json
progress.json 记录采集进度，支持任意阶段断点续采
"""

import asyncio
import json
import os
from datetime import datetime
from typing import Dict, List, Optional

from guazi_api import GuaziAPI
from guazi_config import (
    CITY_MAP, HOT_CITIES, get_all_cities,
    get_cached_brands, set_cached_brands,
    get_cached_series, set_cached_series,
)
from db_manager import DBManager

DEFAULT_OUTPUT_DIR = "guazi_output"
DEFAULT_MAX_WORKERS = 8
# 移动端每个车系页面最多40条，不支持翻页

STAGES = ["brands", "series", "overviews", "details"]


# ================================================================
# 进度管理（参考 dongchedi_client）
# ================================================================

def _progress_path(output_dir: str) -> str:
    return os.path.join(output_dir, "progress.json")


def _file_path(output_dir: str, name: str) -> str:
    return os.path.join(output_dir, f"{name}.json")


def _load_progress(output_dir: str) -> Dict:
    path = _progress_path(output_dir)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "config": {},
        "stages": {s: {"status": "pending", "updated_at": None} for s in STAGES},
        "completed_brands_series": [],  # 车系阶段：已完成的 brand_slug 列表
        "completed_overviews": [],      # 概览阶段：已完成的 "city|brand|series" 键
        "completed_details": [],        # 详情阶段：已完成的 sku_id 列表
    }


def _save_progress(output_dir: str, progress: Dict):
    progress["updated_at"] = datetime.now().isoformat()
    path = _progress_path(output_dir)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)


def _mark_stage(progress: Dict, stage: str, status: str):
    progress["stages"][stage] = {
        "status": status,
        "updated_at": datetime.now().isoformat(),
    }


def _stage_status(progress: Dict, stage: str) -> str:
    return progress["stages"].get(stage, {}).get("status", "pending")


# ================================================================
# JSON 读写
# ================================================================

def _write_json(path: str, payload):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def _read_json(path: str):
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"⚠️ JSON文件损坏，将重建: {path} ({e})")
        return None


def _append_to_json_array(path: str, items: List[Dict]):
    """追加数据到JSON文件的data数组中（增量保存）"""
    existing = _read_json(path)
    if existing and "data" in existing:
        existing["data"].extend(items)
        existing["metadata"]["total"] = len(existing["data"])
        existing["metadata"]["updated_at"] = datetime.now().isoformat()
    else:
        existing = {
            "metadata": {
                "total": len(items),
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
            },
            "data": items,
        }
    _write_json(path, existing)


# ================================================================
# 城市选择（本地处理，不提交数据库）
# ================================================================

def _select_cities(progress: Dict) -> List[str]:
    """选择要采集的城市列表"""
    # 如果进度中已有城市配置，直接返回
    saved = progress.get("config", {}).get("cities")
    if saved:
        return saved

    print("\n[城市选择]")
    print(f"  瓜子覆盖 {len(CITY_MAP)} 个城市")
    print(f"  热门城市({len(HOT_CITIES)}个): " + ", ".join(
        f"{CITY_MAP.get(c, c)}({c})" for c in HOT_CITIES[:15]) + " ...")
    print()
    print("  选项：")
    print("  1. all  - 全部城市（按热门优先排序）")
    print("  2. hot  - 仅热门城市")
    print("  3. 输入城市代码，逗号分隔（如 bj,sh,gz）")
    raw = input("  请选择（默认 all）：").strip().lower()

    if not raw or raw == "all":
        # 热门城市优先，其余按字母排序
        rest = sorted([c for c in CITY_MAP if c not in HOT_CITIES])
        cities = HOT_CITIES + rest
    elif raw == "hot":
        cities = list(HOT_CITIES)
    else:
        tokens = [t.strip() for t in raw.split(",") if t.strip()]
        cities = [t for t in tokens if t in CITY_MAP]
        if not cities:
            print("  ⚠️ 无有效城市代码，使用全部城市")
            rest = sorted([c for c in CITY_MAP if c not in HOT_CITIES])
            cities = HOT_CITIES + rest

    print(f"  ✅ 已选择 {len(cities)} 个城市")
    return cities


# ================================================================
# 阶段1：品牌采集
# ================================================================

async def stage_brands(api: GuaziAPI, output_dir: str, progress: Dict,
                       cities: List[str]) -> List[Dict]:
    brands_path = _file_path(output_dir, "brands")

    if _stage_status(progress, "brands") == "done":
        data = _read_json(brands_path)
        if data and data.get("data"):
            brands = data["data"]
            print(f"✅ [品牌] 已有 {len(brands)} 个品牌，跳过采集")
            return brands

    # 先检查本地缓存
    cached = get_cached_brands()
    if cached:
        print(f"✅ [品牌] 从本地缓存加载 {len(cached)} 个品牌")
        _write_json(brands_path, {
            "metadata": {
                "created_at": datetime.now().isoformat(),
                "total": len(cached),
                "source": "cache",
            },
            "data": cached,
        })
        _mark_stage(progress, "brands", "done")
        _save_progress(output_dir, progress)
        return cached

    print("\n[阶段1] 采集品牌...")
    _mark_stage(progress, "brands", "running")
    _save_progress(output_dir, progress)

    # 用第一个城市获取品牌列表
    city = cities[0] if cities else "bj"
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=api.headless, slow_mo=api.slow_mo)
        try:
            brands = await api.fetch_brands(city, browser=browser)
        finally:
            await browser.close()

    if not brands:
        print("❌ 品牌采集失败")
        return []

    print(f"   ✅ 获取到 {len(brands)} 个品牌")

    # 保存到本地缓存
    set_cached_brands(brands)

    _write_json(brands_path, {
        "metadata": {
            "created_at": datetime.now().isoformat(),
            "total": len(brands),
            "city_used": city,
        },
        "data": brands,
    })

    _mark_stage(progress, "brands", "done")
    _save_progress(output_dir, progress)
    return brands


# ================================================================
# 阶段2：车系采集（逐品牌增量保存）
# ================================================================

async def stage_series(api: GuaziAPI, output_dir: str, progress: Dict,
                       brands: List[Dict], cities: List[str]) -> List[Dict]:
    series_path = _file_path(output_dir, "series")
    completed_slugs = set(progress.get("completed_brands_series", []))

    if _stage_status(progress, "series") == "done":
        data = _read_json(series_path)
        if data and data.get("data"):
            print(f"✅ [车系] 已有 {len(data['data'])} 个车系，跳过采集")
            return data["data"]

    # 先检查本地缓存
    cached = get_cached_series()
    if cached and not completed_slugs:
        print(f"✅ [车系] 从本地缓存加载 {len(cached)} 个车系")
        _write_json(series_path, {
            "metadata": {
                "created_at": datetime.now().isoformat(),
                "total": len(cached),
                "source": "cache",
            },
            "data": cached,
        })
        _mark_stage(progress, "series", "done")
        _save_progress(output_dir, progress)
        return cached

    existing_series = []
    if os.path.exists(series_path):
        data = _read_json(series_path)
        if data and data.get("data"):
            existing_series = data["data"]

    remaining = [b for b in brands if b["brand_slug"] not in completed_slugs]
    if not remaining:
        _mark_stage(progress, "series", "done")
        _save_progress(output_dir, progress)
        set_cached_series(existing_series)
        return existing_series

    total = len(brands)
    done_count = total - len(remaining)
    city = cities[0] if cities else "bj"
    print(f"\n[阶段2] 采集车系... (已完成 {done_count}/{total} 个品牌，使用城市 {CITY_MAP.get(city, city)})")
    _mark_stage(progress, "series", "running")
    _save_progress(output_dir, progress)

    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=api.headless, slow_mo=api.slow_mo)
        try:
            for i, brand in enumerate(remaining, done_count + 1):
                slug = brand["brand_slug"]
                bname = brand["brand_name"]
                print(f"   [{i}/{total}] {bname} ({slug})...")
                try:
                    result = await api.fetch_series_for_brand(city, slug, bname, browser=browser)
                    if result:
                        _append_to_json_array(series_path, result)
                        existing_series.extend(result)
                        print(f"   ✅ {bname}: {len(result)} 个车系")
                    else:
                        print(f"   ⚠️ {bname}: 无车系")
                except Exception as e:
                    print(f"   ❌ {bname}: {e}")

                completed_slugs.add(slug)
                progress["completed_brands_series"] = list(completed_slugs)
                _save_progress(output_dir, progress)
        finally:
            await browser.close()

    # 保存到本地缓存
    set_cached_series(existing_series)

    _mark_stage(progress, "series", "done")
    _save_progress(output_dir, progress)
    print(f"   ✅ 车系采集完成，共 {len(existing_series)} 个车系")
    return existing_series


# ================================================================
# 阶段3：概览采集（按 城市×品牌×车系 增量保存）
# ================================================================

async def stage_overviews(api: GuaziAPI, output_dir: str, progress: Dict,
                          cities: List[str], series_list: List[Dict]) -> List[Dict]:
    overviews_path = _file_path(output_dir, "overviews")
    completed_keys = set(progress.get("completed_overviews", []))

    if _stage_status(progress, "overviews") == "done":
        data = _read_json(overviews_path)
        if data and data.get("data"):
            print(f"✅ [概览] 已有 {len(data['data'])} 条概览，跳过采集")
            return data["data"]

    existing = []
    if os.path.exists(overviews_path):
        data = _read_json(overviews_path)
        if data and data.get("data"):
            existing = data["data"]

    # 构建任务列表：城市 × 车系
    tasks = []
    for city in cities:
        for s in series_list:
            key = f"{city}|{s['brand_slug']}|{s['series_slug']}"
            if key not in completed_keys:
                tasks.append((city, s["brand_slug"], s["brand_name"],
                              s["series_slug"], s["series_name"], key))

    if not tasks:
        _mark_stage(progress, "overviews", "done")
        _save_progress(output_dir, progress)
        return existing

    total_all = len(cities) * len(series_list)
    done_count = total_all - len(tasks)
    print(f"\n[阶段3] 采集列表概览... ({len(cities)} 城市 × {len(series_list)} 车系 = {total_all} 组合)")
    print(f"   已完成 {done_count}/{total_all}，剩余 {len(tasks)}")
    _mark_stage(progress, "overviews", "running")
    _save_progress(output_dir, progress)

    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=api.headless, slow_mo=api.slow_mo)
        try:
            for idx, (city, brand_slug, brand_name, series_slug, series_name, key) in enumerate(tasks, done_count + 1):
                city_name = CITY_MAP.get(city, city)
                label = f"{city_name}/{brand_name}/{series_name}"
                print(f"   [{idx}/{total_all}] {label}")
                try:
                    cars = await api.fetch_all_car_list(
                        city_code=city, brand_slug=brand_slug, brand_name=brand_name,
                        series_slug=series_slug, series_name=series_name,
                        browser=browser,
                    )
                    if cars:
                        _append_to_json_array(overviews_path, cars)
                        existing.extend(cars)
                        print(f"   ✅ {label}: {len(cars)} 条")
                    else:
                        print(f"   ⚠️ {label}: 无数据")
                except Exception as e:
                    print(f"   ❌ {label}: {e}")

                completed_keys.add(key)
                progress["completed_overviews"] = list(completed_keys)
                _save_progress(output_dir, progress)
        finally:
            await browser.close()

    _mark_stage(progress, "overviews", "done")
    _save_progress(output_dir, progress)
    print(f"   ✅ 概览采集完成，共 {len(existing)} 条")
    return existing


# ================================================================
# 阶段4：详情采集（逐批增量保存）
# ================================================================

async def stage_details(api: GuaziAPI, output_dir: str, progress: Dict,
                        overviews: List[Dict], max_workers: int,
                        db: Optional[DBManager] = None):
    details_path = _file_path(output_dir, "details")
    images_path = _file_path(output_dir, "images")
    configs_path = _file_path(output_dir, "configs")
    completed_ids = set(progress.get("completed_details", []))

    if _stage_status(progress, "details") == "done":
        data = _read_json(details_path)
        cnt = len(data["data"]) if data and data.get("data") else 0
        print(f"✅ [详情] 已有 {cnt} 条详情，跳过采集")
        return

    remaining = [c for c in overviews if c.get("sku_id") and c["sku_id"] not in completed_ids]

    if not remaining:
        _mark_stage(progress, "details", "done")
        _save_progress(output_dir, progress)
        return

    total = len(overviews)
    done_count = total - len(remaining)
    print(f"\n[阶段4] 采集详情... (已完成 {done_count}/{total}，剩余 {len(remaining)})")
    print(f"   并发数: {max_workers}，每 {max_workers} 条保存一次进度")
    _mark_stage(progress, "details", "running")
    _save_progress(output_dir, progress)

    from playwright.async_api import async_playwright

    queue: asyncio.Queue = asyncio.Queue()
    for car in remaining:
        await queue.put(car)

    lock = asyncio.Lock()
    batch_buffer: List[Dict] = []
    SAVE_EVERY = max_workers

    async def _save_batch():
        nonlocal batch_buffer
        if not batch_buffer:
            return
        to_save = batch_buffer[:]
        batch_buffer = []

        detail_rows = []
        image_rows = []
        config_rows = []
        for d in to_save:
            sku_id = d["sku_id"]
            detail_rows.append({k: d.get(k) for k in [
                "sku_id", "spu_id", "title", "important_text",
                "sh_price", "official_price", "include_tax_price",
                "source_sh_price", "source_offical_price",
                "brand_id", "brand_name", "series_id", "series_name",
                "car_id", "car_name", "year", "body_color",
                "params", "shop", "report", "financial",
                "tags", "highlights", "description",
                "detail_url", "detail_params_url", "collected_at",
            ]})
            image_rows.append({"sku_id": sku_id, "images": d.get("images", [])})
            config_rows.append({"sku_id": sku_id, "config": d.get("config"),
                                "detail_params": d.get("detail_params")})

        _append_to_json_array(details_path, detail_rows)
        _append_to_json_array(images_path, image_rows)
        _append_to_json_array(configs_path, config_rows)

        if db:
            await db.upsert_details(to_save)

        progress["completed_details"] = list(completed_ids)
        _save_progress(output_dir, progress)
        print(f"   ✅ 进度: {len(completed_ids)}/{total}")

    async def _worker(worker_id: int, page):
        while True:
            try:
                car = queue.get_nowait()
            except asyncio.QueueEmpty:
                break

            sku_id = car["sku_id"]
            try:
                detail = await api.fetch_car_detail(page, sku_id, detail_url=car.get("detail_url"))
            except Exception as e:
                print(f"   ⚠️ worker-{worker_id} sku={sku_id} 异常: {e}")
                detail = None

            if detail and detail.get("sku_id"):
                async with lock:
                    completed_ids.add(detail["sku_id"])
                    batch_buffer.append(detail)
                    if len(batch_buffer) >= SAVE_EVERY:
                        await _save_batch()

            queue.task_done()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=api.headless, slow_mo=api.slow_mo)
        try:
            num_workers = min(max_workers, len(remaining))
            # 移动端需要用 mobile context
            contexts = []
            pages = []
            for _ in range(num_workers):
                ctx = await api.create_mobile_context(browser)
                pg = await ctx.new_page()
                contexts.append(ctx)
                pages.append(pg)
            workers = [asyncio.create_task(_worker(i, pages[i])) for i in range(num_workers)]
            await asyncio.gather(*workers)
            async with lock:
                await _save_batch()
        finally:
            for pg in pages:
                try:
                    await pg.close()
                except Exception:
                    pass
            for ctx in contexts:
                try:
                    await ctx.close()
                except Exception:
                    pass
            await browser.close()

    _mark_stage(progress, "details", "done")
    _save_progress(output_dir, progress)
    print(f"   ✅ 详情采集完成，共 {len(completed_ids)} 条")


# ================================================================
# 主流程
# ================================================================

async def main():
    print("=" * 60)
    print("🚀 瓜子二手车采集客户端（移动端模式，对齐懂车帝结构，支持断点续采）")
    print("=" * 60)

    output_dir = input(f"输出目录（默认 {DEFAULT_OUTPUT_DIR}）：").strip() or DEFAULT_OUTPUT_DIR
    os.makedirs(output_dir, exist_ok=True)

    progress = _load_progress(output_dir)

    # 检测是否有未完成的任务
    has_progress = any(_stage_status(progress, s) in ("done", "running") for s in STAGES)
    if has_progress:
        status_str = " | ".join(f"{s}={_stage_status(progress, s)}" for s in STAGES)
        print(f"\n📋 检测到上次进度: {status_str}")
        choice = input("继续上次采集？(Y/n)：").strip().lower()
        if choice == "n":
            progress = {
                "config": {},
                "stages": {s: {"status": "pending", "updated_at": None} for s in STAGES},
                "completed_brands_series": [],
                "completed_overviews": [],
                "completed_details": [],
            }
            for name in ["brands", "series", "overviews", "details", "images", "configs", "progress"]:
                p = _file_path(output_dir, name)
                if os.path.exists(p):
                    os.remove(p)
            print("🗑️ 已清空旧数据，重新开始")

    # ---- 步骤0：城市选择（本地处理） ----
    if not progress.get("config", {}).get("cities"):
        cities = _select_cities(progress)
        if not progress.get("config"):
            progress["config"] = {}
        progress["config"]["cities"] = cities
        _save_progress(output_dir, progress)
    else:
        cities = progress["config"]["cities"]
        print(f"📋 使用上次城市配置: {len(cities)} 个城市")

    # ---- 配置（仅首次） ----
    if not progress.get("config", {}).get("max_workers"):
        mw = input(f"并发数（默认 {DEFAULT_MAX_WORKERS}）：").strip()
        max_workers = int(mw) if mw.isdigit() else DEFAULT_MAX_WORKERS
        progress["config"]["max_workers"] = max_workers
        _save_progress(output_dir, progress)
    else:
        max_workers = progress["config"]["max_workers"]
        print(f"📋 使用上次配置: 并发={max_workers}")
    print(f"   （移动端模式：每个车系页面最多40条，无需翻页）")

    api = GuaziAPI(headless=True)

    # 数据库连接（可选）
    db: Optional[DBManager] = None
    enable_db = progress.get("config", {}).get("enable_db")
    if enable_db is None:
        db_choice = input("是否同步到MySQL数据库？(y/N)：").strip().lower()
        enable_db = db_choice == "y"
        progress["config"]["enable_db"] = enable_db
        _save_progress(output_dir, progress)

    if enable_db:
        try:
            db = DBManager()
            await db.connect()
        except Exception as e:
            print(f"⚠️ 数据库连接失败: {e}")
            print("   将仅保存到JSON文件，不同步数据库")
            db = None

    try:
        # 阶段1：品牌
        brands = await stage_brands(api, output_dir, progress, cities)
        if not brands:
            print("❌ 无品牌数据，退出")
            return

        # 阶段2：车系
        series_list = await stage_series(api, output_dir, progress, brands, cities)
        if not series_list:
            print("⚠️ 无车系数据")

        # 阶段3：概览（城市×车系 轮询，移动端单页最多40条）
        overviews = await stage_overviews(api, output_dir, progress, cities, series_list)

        # 阶段4：详情
        await stage_details(api, output_dir, progress, overviews, max_workers, db=db)

        print("\n" + "=" * 60)
        print("✅ 瓜子全部采集完成!")
        print(f"   城市: {len(cities)}")
        print(f"   品牌: {len(brands)}")
        print(f"   车系: {len(series_list)}")
        print(f"   概览: {len(overviews)}")
        det = _read_json(_file_path(output_dir, "details"))
        det_count = len(det["data"]) if det and det.get("data") else 0
        print(f"   详情: {det_count}")
        print(f"   输出: {os.path.abspath(output_dir)}")
        if db:
            from db_config import DB_CONFIG
            print(f"   数据库: {DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}")
        print("=" * 60)
    finally:
        if db:
            await db.close()


if __name__ == "__main__":
    asyncio.run(main())
