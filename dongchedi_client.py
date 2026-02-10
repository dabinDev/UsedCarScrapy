#!/usr/bin/env python3
"""
懂车帝二手车采集客户端 - 支持断点续采
- 品牌 -> 车系 -> 列表概览 -> 详情(含图片/配置/参数)
- 输出：brands.json / series.json / overviews.json / details.json / images.json / configs.json
- progress.json 记录采集进度，支持任意阶段断点续采
"""

import asyncio
import json
import os
import re
from datetime import datetime
from typing import Dict, List, Optional

from dongchedi_api import DongchediAPI
from db_manager import DBManager
from ocr_price import LocalOCR, parse_price_from_ocr_text

DEFAULT_OUTPUT_DIR = "client_output"
DEFAULT_MAX_WORKERS = 10
DEFAULT_MAX_PAGES = 167

# ================================================================
# 进度管理
# ================================================================

STAGES = ["brands", "series", "overviews", "details", "ocr_price"]


def _progress_path(output_dir: str) -> str:
    return os.path.join(output_dir, "progress.json")


def _load_progress(output_dir: str) -> Dict:
    path = _progress_path(output_dir)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "config": {},
        "stages": {s: {"status": "pending", "updated_at": None} for s in STAGES},
        "completed_brands_series": [],   # 车系阶段：已完成的brand_id列表
        "completed_overviews": [],       # 概览阶段：已完成的series_id列表
        "completed_details": [],         # 详情阶段：已完成的sku_id列表
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

def _file_path(output_dir: str, name: str) -> str:
    return os.path.join(output_dir, f"{name}.json")


def _write_json(path: str, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # 原子写入：先写临时文件再 rename，避免大文件写入 OSError
    tmp_path = path + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        # Windows 上 rename 前需要先删除目标
        if os.path.exists(path):
            os.remove(path)
        os.rename(tmp_path, path)
    except Exception:
        # 回退：直接写入
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass


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
            "metadata": {"total": len(items), "created_at": datetime.now().isoformat(), "updated_at": datetime.now().isoformat()},
            "data": items,
        }
    _write_json(path, existing)


# ================================================================
# 品牌选择（仅首次运行时交互）
# ================================================================

def _print_brand_list(brands: List[Dict]):
    print("\n可选品牌（前60个）：")
    for idx, b in enumerate(brands[:60], 1):
        print(f"{idx:>2}. {b['brand_name']} (ID: {b['brand_id']})")
    if len(brands) > 60:
        print(f"... 共 {len(brands)} 个品牌")


def _select_brands(brands: List[Dict]) -> List[Dict]:
    _print_brand_list(brands)
    print("\n选择品牌：")
    print("- 输入 all 或直接回车：采集全部品牌")
    print("- 输入编号列表（例如 1,3,5）")
    print("- 输入关键词（例如 '大众,比亚迪'）")

    raw = input("请输入：").strip()
    if not raw or raw.lower() == "all":
        return brands

    selections: List[Dict] = []
    tokens = [t.strip() for t in raw.split(",") if t.strip()]

    if all(t.isdigit() for t in tokens):
        for t in tokens:
            idx = int(t) - 1
            if 0 <= idx < len(brands):
                selections.append(brands[idx])
        return selections or brands

    for name in tokens:
        match = next((b for b in brands if name in b["brand_name"]), None)
        if match:
            selections.append(match)

    return selections or brands


# ================================================================
# 阶段1：品牌采集
# ================================================================

async def stage_brands(api: DongchediAPI, output_dir: str, progress: Dict, db: Optional[DBManager] = None) -> List[Dict]:
    brands_path = _file_path(output_dir, "brands")

    # 已完成 -> 直接读取
    if _stage_status(progress, "brands") == "done":
        data = _read_json(brands_path)
        if data and data.get("data"):
            brands = data["data"]
            print(f"✅ [品牌] 已有 {len(brands)} 个品牌，跳过采集")
            return brands

    print("\n[阶段1] 采集品牌...")
    _mark_stage(progress, "brands", "running")
    _save_progress(output_dir, progress)

    result = await api.fetch_brands_and_series()
    if not result or not result.get("brands"):
        print("❌ 品牌采集失败")
        return []

    all_brands = result["brands"]

    # 首次运行：交互选择品牌
    selected = _select_brands(all_brands)
    print(f"\n已选择 {len(selected)} 个品牌")

    _write_json(brands_path, {
        "metadata": {
            "created_at": datetime.now().isoformat(),
            "total_available": len(all_brands),
            "total_selected": len(selected),
        },
        "data": selected,
    })

    if db:
        await db.upsert_brands(selected)

    _mark_stage(progress, "brands", "done")
    _save_progress(output_dir, progress)
    return selected


# ================================================================
# 阶段2：车系采集（逐品牌增量保存）
# ================================================================

async def stage_series(api: DongchediAPI, output_dir: str, progress: Dict, brands: List[Dict], db: Optional[DBManager] = None) -> List[Dict]:
    series_path = _file_path(output_dir, "series")
    completed_ids = set(int(x) for x in progress.get("completed_brands_series", []))

    # 全部完成
    if _stage_status(progress, "series") == "done":
        data = _read_json(series_path)
        if data and data.get("data"):
            print(f"✅ [车系] 已有 {len(data['data'])} 个车系，跳过采集")
            return data["data"]

    # 部分完成 -> 读取已有数据
    existing_series = []
    if os.path.exists(series_path):
        data = _read_json(series_path)
        if data and data.get("data"):
            existing_series = data["data"]

    remaining = [b for b in brands if b["brand_id"] not in completed_ids]
    if not remaining:
        _mark_stage(progress, "series", "done")
        _save_progress(output_dir, progress)
        return existing_series

    total = len(brands)
    done_count = total - len(remaining)
    print(f"\n[阶段2] 采集车系... (已完成 {done_count}/{total} 个品牌)")
    _mark_stage(progress, "series", "running")
    _save_progress(output_dir, progress)

    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=api.headless, slow_mo=api.slow_mo)
        context = await browser.new_context(accept_downloads=True)
        try:
            for i, brand in enumerate(remaining, done_count + 1):
                bid = brand["brand_id"]
                bname = brand["brand_name"]
                print(f"   [{i}/{total}] {bname}...")
                try:
                    result = await api.fetch_series_for_brand(bid, bname, browser=context)
                    if result:
                        # 增量追加
                        _append_to_json_array(series_path, result)
                        existing_series.extend(result)
                        if db:
                            await db.upsert_series_list(result)
                        print(f"   ✅ {bname}: {len(result)} 个车系")
                    else:
                        print(f"   ⚠️ {bname}: 无车系")
                except Exception as e:
                    print(f"   ❌ {bname}: {e}")

                # 标记该品牌完成
                completed_ids.add(bid)
                progress["completed_brands_series"] = list(completed_ids)
                _save_progress(output_dir, progress)
        finally:
            await context.close()
            await browser.close()

    _mark_stage(progress, "series", "done")
    _save_progress(output_dir, progress)
    print(f"   ✅ 车系采集完成，共 {len(existing_series)} 个车系")
    return existing_series


# ================================================================
# 阶段3：列表概览（逐车系增量保存）
# ================================================================

async def stage_overviews(api: DongchediAPI, output_dir: str, progress: Dict,
                          brands: List[Dict], series_list: List[Dict], max_pages: int,
                          db: Optional[DBManager] = None,
                          enable_screenshot: bool = False) -> List[Dict]:
    overviews_path = _file_path(output_dir, "overviews")
    completed_ids = set(int(x) for x in progress.get("completed_overviews", []))

    # 截图目录
    screenshot_dir = None
    if enable_screenshot:
        screenshot_dir = os.path.join(output_dir, "screenshots")
        os.makedirs(screenshot_dir, exist_ok=True)

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

    # 按品牌分组
    brand_map = {b["brand_id"]: b for b in brands}
    remaining = [s for s in series_list if s["series_id"] not in completed_ids]

    if not remaining:
        _mark_stage(progress, "overviews", "done")
        _save_progress(output_dir, progress)
        return existing

    total = len(series_list)
    done_count = total - len(remaining)
    print(f"\n[阶段3] 采集列表概览... (已完成 {done_count}/{total} 个车系)")
    if screenshot_dir:
        print(f"   📸 截图已启用，保存到: {screenshot_dir}")
    _mark_stage(progress, "overviews", "running")
    _save_progress(output_dir, progress)

    for i, s in enumerate(remaining, done_count + 1):
        sid = s["series_id"]
        sname = s.get("series_name", str(sid))
        bid = s.get("brand_id")
        brand = brand_map.get(bid, {})
        bname = brand.get("brand_name", "")

        print(f"   [{i}/{total}] {bname}/{sname}...")
        try:
            cars = await api.fetch_all_car_list(
                brand_id=bid, brand_name=bname,
                series_id=sid, series_name=sname,
                max_pages=max_pages,
                screenshot_dir=screenshot_dir,
            )
            if cars:
                _append_to_json_array(overviews_path, cars)
                existing.extend(cars)
                if db:
                    await db.upsert_overviews(cars)
                print(f"   ✅ {sname}: {len(cars)} 条")
            else:
                print(f"   ⚠️ {sname}: 无数据")
        except Exception as e:
            print(f"   ❌ {sname}: {e}")

        completed_ids.add(sid)
        progress["completed_overviews"] = list(completed_ids)
        _save_progress(output_dir, progress)

    _mark_stage(progress, "overviews", "done")
    _save_progress(output_dir, progress)
    shot_count = len(os.listdir(screenshot_dir)) if screenshot_dir and os.path.isdir(screenshot_dir) else 0
    suffix = f"，截图: {shot_count}" if screenshot_dir else ""
    print(f"   ✅ 概览采集完成，共 {len(existing)} 条{suffix}")
    return existing


# ================================================================
# 阶段4：详情采集（逐批增量保存）
# ================================================================

async def stage_details(api: DongchediAPI, output_dir: str, progress: Dict,
                        overviews: List[Dict], max_workers: int,
                        db: Optional[DBManager] = None):
    details_path = _file_path(output_dir, "details")
    images_path = _file_path(output_dir, "images")
    configs_path = _file_path(output_dir, "configs")
    completed_ids = set(int(x) for x in progress.get("completed_details", []))

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

    # 用 asyncio.Queue 做任务分发，每个 worker 独占一个 page
    queue: asyncio.Queue = asyncio.Queue()
    for car in remaining:
        await queue.put(car)

    # 收集结果用锁保护
    lock = asyncio.Lock()
    batch_buffer: List[Dict] = []
    SAVE_EVERY = max_workers  # 每完成 N 条保存一次

    async def _save_batch():
        """将缓冲区数据保存到JSON和数据库"""
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

        # 一次性批量写入（每个文件只读写一次）
        try:
            _append_to_json_array(details_path, detail_rows)
            _append_to_json_array(images_path, image_rows)
            _append_to_json_array(configs_path, config_rows)
        except Exception as e:
            print(f"   ⚠️ 保存JSON失败: {e}，数据暂存内存，下次重试")
            # 把数据放回缓冲区，下次再保存
            batch_buffer.extend(to_save)
            return

        if db:
            try:
                await db.upsert_details(to_save)
            except Exception:
                pass

        progress["completed_details"] = list(completed_ids)
        _save_progress(output_dir, progress)
        print(f"   ✅ 进度: {len(completed_ids)}/{total}")

    async def _worker(worker_id: int, page):
        """单个 worker：从队列取任务，用自己独占的 page 采集"""
        while True:
            try:
                car = queue.get_nowait()
            except asyncio.QueueEmpty:
                break

            sku_id = car["sku_id"]
            try:
                detail = await api.fetch_car_detail(page, sku_id)
            except Exception as e:
                err_msg = str(e).split("\n")[0][:100]
                # 浏览器/页面已关闭，停止该 worker
                if "closed" in err_msg.lower() or "Target" in err_msg:
                    print(f"   ⚠️ worker-{worker_id} 浏览器已关闭，停止")
                    queue.task_done()
                    break
                print(f"   ⚠️ worker-{worker_id} sku={sku_id} 异常: {err_msg}")
                detail = None

            if detail and detail.get("sku_id"):
                async with lock:
                    completed_ids.add(detail["sku_id"])
                    batch_buffer.append(detail)
                    if len(batch_buffer) >= SAVE_EVERY:
                        await _save_batch()

            queue.task_done()

    async with async_playwright() as p:
        # 详情页强制用无头浏览器，支持并发
        browser = await p.chromium.launch(headless=True, slow_mo=api.slow_mo)
        try:
            # 每个 worker 创建独立的 page
            num_workers = min(max_workers, len(remaining))
            pages = [await browser.new_page() for _ in range(num_workers)]
            workers = [asyncio.create_task(_worker(i, pages[i])) for i in range(num_workers)]
            await asyncio.gather(*workers)

            # 保存剩余缓冲
            async with lock:
                await _save_batch()
        finally:
            for pg in pages:
                try:
                    await pg.close()
                except Exception:
                    pass
            await browser.close()

    _mark_stage(progress, "details", "done")
    _save_progress(output_dir, progress)
    print(f"   ✅ 详情采集完成，共 {len(completed_ids)} 条")


# ================================================================
# 阶段5：OCR价格补充（读取本地截图 + WinOCR 异步解析价格）
# ================================================================

async def stage_ocr_price(api: DongchediAPI, output_dir: str, progress: Dict,
                          max_workers: int = 10, db: Optional[DBManager] = None):
    if _stage_status(progress, "ocr_price") == "done":
        print("✅ [OCR价格] 已完成，跳过")
        return

    screenshot_dir = os.path.join(output_dir, "screenshots")
    if not os.path.isdir(screenshot_dir):
        print("⚠️ 无截图目录，跳过OCR价格解析")
        return

    # 获取所有截图文件 -> sku_id 集合
    shot_files = {f.replace(".png", ""): os.path.join(screenshot_dir, f)
                  for f in os.listdir(screenshot_dir) if f.endswith(".png")}
    if not shot_files:
        print("⚠️ 截图目录为空，跳过OCR价格解析")
        return

    details_path = _file_path(output_dir, "details")
    details_data = _read_json(details_path)

    # 构建 sku_id -> detail 索引
    all_details = details_data["data"] if details_data and details_data.get("data") else []
    detail_index = {str(d["sku_id"]): d for d in all_details if d.get("sku_id")}

    completed_ocr = set(str(x) for x in progress.get("completed_ocr", []))

    # 找出有截图但缺少价格的 sku_id
    missing_ids = []
    for sku_id, shot_path in shot_files.items():
        if sku_id in completed_ocr:
            continue
        target = detail_index.get(sku_id)
        if target and (not target.get("sh_price") or not target.get("official_price")):
            missing_ids.append(sku_id)
        elif not target:
            # 详情还没采集到的也可以先OCR，后续合并
            missing_ids.append(sku_id)

    if not missing_ids:
        print("✅ [OCR价格] 所有有截图的车辆价格已完整，无需OCR")
        _mark_stage(progress, "ocr_price", "done")
        _save_progress(output_dir, progress)
        return

    print(f"\n[阶段5] OCR价格补充（EasyOCR本地识别）...")
    print(f"   截图: {len(shot_files)} 张, 待OCR: {len(missing_ids)}, 已处理: {len(completed_ocr)}")

    _mark_stage(progress, "ocr_price", "running")
    _save_progress(output_dir, progress)

    print("   ⏳ 初始化本地OCR引擎（EasyOCR）...")
    ocr_client = LocalOCR()
    print("   ✅ EasyOCR 引擎就绪")

    import time as _time
    success_count = 0
    processed_count = 0
    SAVE_EVERY = 100
    t0 = _time.time()

    for sku_id in missing_ids:
        shot_path = shot_files[sku_id]
        processed_count += 1

        try:
            # 两次OCR：全图 + 裁剪底部放大（提高新车指导价识别率）
            full_text, crop_text = await ocr_client.recognize_file_twpass_async(shot_path)
            result = parse_price_from_ocr_text(full_text, crop_text) if full_text else None

            # 前10条打印OCR原文用于调试
            if processed_count <= 10:
                preview = full_text.replace('\n', ' | ')[:80] if full_text else "(空)"
                print(f"   🔍 [{sku_id}] OCR: {preview}")
                if result:
                    print(f"      解析: sh={result.get('sh_price')}, official={result.get('official_price')}")
                else:
                    print(f"      解析: 无结果")

            completed_ocr.add(sku_id)

            if result and result.get("sh_price"):
                target = detail_index.get(sku_id)
                if target:
                    # 已有详情记录 → 补充缺失的价格
                    changed = False
                    if result.get("sh_price") and not target.get("sh_price"):
                        target["sh_price"] = result["sh_price"]
                        target["price_source"] = "ocr"
                        changed = True
                    if result.get("official_price") and not target.get("official_price"):
                        target["official_price"] = result["official_price"]
                        changed = True

                    if changed:
                        success_count += 1
                        print(f"   💰 [{sku_id}] 补充: 二手={target.get('sh_price')}万, 新车={target.get('official_price')}万")

                        if db:
                            try:
                                await db._execute(
                                    "UPDATE car_detail SET sh_price=%s, official_price=%s, updated_at=NOW() "
                                    "WHERE sku_id=%s",
                                    (target.get("sh_price"), target.get("official_price"), sku_id)
                                )
                            except Exception:
                                pass
                    elif processed_count <= 10:
                        print(f"      ℹ️ 价格已存在: sh={target.get('sh_price')}, off={target.get('official_price')}")
                else:
                    # 详情未采集到 → 创建一条仅含价格的记录
                    new_record = {
                        "sku_id": sku_id,
                        "sh_price": result.get("sh_price"),
                        "official_price": result.get("official_price"),
                        "price_source": "ocr",
                    }
                    all_details.append(new_record)
                    detail_index[sku_id] = new_record
                    success_count += 1
                    print(f"   💰 [{sku_id}] (新) 二手={result.get('sh_price')}万, 新车={result.get('official_price')}万")

            # 定期保存进度
            if processed_count % SAVE_EVERY == 0:
                elapsed = _time.time() - t0
                speed = processed_count / elapsed if elapsed > 0 else 0
                if all_details:
                    details_data["data"] = all_details
                    details_data["metadata"]["updated_at"] = datetime.now().isoformat()
                    _write_json(details_path, details_data)
                progress["completed_ocr"] = list(completed_ocr)
                _save_progress(output_dir, progress)
                print(f"   ✅ OCR进度: {processed_count}/{len(missing_ids)} "
                      f"(成功: {success_count}, {speed:.1f}张/秒)")

        except Exception as e:
            completed_ocr.add(sku_id)
            print(f"   ⚠️ [{sku_id}] OCR失败: {str(e)[:60]}")

    elapsed = _time.time() - t0
    # 最终保存
    if all_details:
        details_data["data"] = all_details
        details_data["metadata"]["updated_at"] = datetime.now().isoformat()
        _write_json(details_path, details_data)
    progress["completed_ocr"] = list(completed_ocr)
    _save_progress(output_dir, progress)

    _mark_stage(progress, "ocr_price", "done")
    _save_progress(output_dir, progress)
    print(f"   ✅ OCR价格补充完成，成功解析 {success_count}/{len(missing_ids)} 条，耗时 {elapsed:.1f}秒")


# ================================================================
# 主流程
# ================================================================

async def main():
    print("=" * 60)
    print("🚀 懂车帝采集客户端（支持断点续采）")
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
            # 清空旧文件
            for name in ["brands", "series", "overviews", "details", "images", "configs", "progress"]:
                p = _file_path(output_dir, name)
                if os.path.exists(p):
                    os.remove(p)
            print("🗑️ 已清空旧数据，重新开始")

    # 配置（仅首次）
    if not progress.get("config", {}).get("max_workers"):
        mw = input(f"线程数（默认 {DEFAULT_MAX_WORKERS}）：").strip()
        max_workers = int(mw) if mw.isdigit() else DEFAULT_MAX_WORKERS
        mp = input(f"最大页数（默认 {DEFAULT_MAX_PAGES}）：").strip()
        max_pages = int(mp) if mp.isdigit() else DEFAULT_MAX_PAGES
        progress["config"] = {"max_workers": max_workers, "max_pages": max_pages}
        _save_progress(output_dir, progress)
    else:
        max_workers = progress["config"]["max_workers"]
        max_pages = progress["config"]["max_pages"]
        print(f"📋 使用上次配置: 线程={max_workers}, 最大页数={max_pages}")

    api = DongchediAPI(headless=False)

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

    # OCR价格解析配置（可选）
    enable_ocr = progress.get("config", {}).get("enable_ocr")
    if enable_ocr is None:
        ocr_choice = input("采集完成后是否用OCR解析加密价格？(y/N)：").strip().lower()
        enable_ocr = ocr_choice == "y"
        progress["config"]["enable_ocr"] = enable_ocr
        _save_progress(output_dir, progress)

    try:
        # 阶段1：品牌
        brands = await stage_brands(api, output_dir, progress, db=db)
        if not brands:
            print("❌ 无品牌数据，退出")
            return

        # 阶段2：车系（全自动，不再逐品牌询问）
        series_list = await stage_series(api, output_dir, progress, brands, db=db)
        if not series_list:
            print("⚠️ 无车系数据")

        # 阶段3：概览（启用OCR时同时截图车辆卡片）
        overviews = await stage_overviews(api, output_dir, progress, brands, series_list, max_pages,
                                          db=db, enable_screenshot=enable_ocr)

        # 阶段4：详情（强制无头浏览器并发）
        await stage_details(api, output_dir, progress, overviews, max_workers, db=db)

        # 阶段5：OCR价格补充（读取本地截图文件）
        if enable_ocr:
            await stage_ocr_price(api, output_dir, progress, db=db)

        print("\n" + "=" * 60)
        print("✅ 全部采集完成!")
        print(f"   品牌: {len(brands)}")
        print(f"   车系: {len(series_list)}")
        print(f"   概览: {len(overviews)}")
        det = _read_json(_file_path(output_dir, "details"))
        det_count = len(det["data"]) if det and det.get("data") else 0
        print(f"   详情: {det_count}")
        shot_dir = os.path.join(output_dir, "screenshots")
        if os.path.isdir(shot_dir):
            print(f"   截图: {len(os.listdir(shot_dir))}")
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
