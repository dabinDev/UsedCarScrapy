from __future__ import annotations

import asyncio
import shutil
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Dict, List, Optional

from desktop_client.models import SelectionItem, TaskWorkspace
from desktop_client.runtime.workspace import WorkspaceManager
from dongchedi_api import DongchediAPI
from playwright.async_api import async_playwright
from playwright_launch import build_chromium_launch_kwargs

BRAND_CATALOG_FILE = "brand_catalog.json"
BRANDS_FILE = "brands.json"
SERIES_CATALOG_FILE = "series_catalog.json"
SERIES_FILE = "series.json"
OVERVIEWS_FILE = "overviews.json"
DETAILS_FILE = "details.json"
IMAGES_FILE = "images.json"
CONFIGS_FILE = "configs.json"


class DongchediRunner:
    def __init__(
        self,
        workspace_manager: WorkspaceManager,
        *,
        api_factory: Optional[Callable[..., Any]] = None,
        page_session_factory: Optional[Callable[[TaskWorkspace], Any]] = None,
        event_callback: Optional[Callable[[str, str], None]] = None,
    ):
        self.workspace_manager = workspace_manager
        self.api_factory = api_factory or DongchediAPI
        self.page_session_factory = page_session_factory
        self.event_callback = event_callback

    async def load_brand_catalog(self, workspace_root: str | Path) -> List[Dict[str, Any]]:
        workspace = self.workspace_manager.load_workspace(workspace_root)
        api = self._build_api(workspace)
        self._emit("info", "开始加载品牌目录。")

        workspace.progress.stages["brands"].status = "running"
        self.workspace_manager.save_workspace(workspace)

        result = await api.fetch_brands_and_series()
        brands = list((result or {}).get("brands") or [])
        hot_brands = list((result or {}).get("hot_brands") or [])

        payload = {
            "metadata": {
                "source": "dongchedi",
                "data_type": "brand_catalog",
                "created_at": datetime.now().isoformat(),
                "total": len(brands),
                "hot_total": len(hot_brands),
            },
            "data": brands,
            "hot_brands": hot_brands,
        }
        self.workspace_manager.write_result_file(workspace.root, BRAND_CATALOG_FILE, payload)
        workspace.progress.stages["brands"].status = "done"
        workspace.progress.stages["brands"].updated_at = datetime.now().isoformat()
        self.workspace_manager.save_workspace(workspace)
        self._emit("info", f"品牌目录加载完成，共 {len(brands)} 个品牌。")
        return brands

    def select_brands(self, workspace_root: str | Path, brand_ids: List[str]) -> List[SelectionItem]:
        workspace = self.workspace_manager.load_workspace(workspace_root)
        payload = self.workspace_manager.read_result_file(workspace.root, BRAND_CATALOG_FILE)
        catalog = list(payload.get("data") or [])
        selected_id_set = {str(raw) for raw in brand_ids}

        selected = [
            SelectionItem(
                item_id=str(item.get("brand_id", "")),
                name=str(item.get("brand_name", "")),
            )
            for item in catalog
            if str(item.get("brand_id", "")) in selected_id_set
        ]

        workspace.scope.brands = selected
        workspace.scope.series = []
        workspace.progress.completed_brand_ids = []
        workspace.progress.completed_series_ids = []
        workspace.progress.completed_overview_series_ids = []
        workspace.progress.completed_detail_ids = []
        workspace.progress.completed_ocr_ids = []
        self._reset_stage(workspace, "series")
        self._reset_stage(workspace, "overviews")
        self._reset_stage(workspace, "details")
        self._reset_stage(workspace, "ocr_price")
        self._clear_files(
            workspace.root,
            SERIES_CATALOG_FILE,
            SERIES_FILE,
            OVERVIEWS_FILE,
            DETAILS_FILE,
            IMAGES_FILE,
            CONFIGS_FILE,
        )
        self._clear_screenshots(workspace.root)
        self.workspace_manager.save_workspace(workspace)
        self.workspace_manager.write_result_file(
            workspace.root,
            BRANDS_FILE,
            {
                "metadata": {
                    "source": "dongchedi",
                    "data_type": "selected_brands",
                    "created_at": datetime.now().isoformat(),
                    "total": len(selected),
                },
                "data": [{"brand_id": item.item_id, "brand_name": item.name} for item in selected],
            },
        )
        self._emit("info", f"已保存品牌选择，共 {len(selected)} 个品牌。")
        return selected

    async def load_series_catalog(self, workspace_root: str | Path) -> List[Dict[str, Any]]:
        workspace = self.workspace_manager.load_workspace(workspace_root)
        api = self._build_api(workspace)

        existing_payload = self.workspace_manager.read_result_file(workspace.root, SERIES_CATALOG_FILE)
        existing_series = list(existing_payload.get("data") or [])
        series_by_id = {
            str(item.get("series_id", "")): item
            for item in existing_series
            if item.get("series_id")
        }

        selected_brands = list(workspace.scope.brands)
        if not selected_brands:
            return list(series_by_id.values())

        selected_brand_ids = [item.item_id for item in selected_brands]
        completed = [
            item_id
            for item_id in workspace.progress.completed_brand_ids
            if item_id in selected_brand_ids
        ]
        completed_set = set(completed)
        workspace.progress.stages["series"].status = "running"
        self.workspace_manager.save_workspace(workspace)

        for brand in selected_brands:
            if brand.item_id in completed_set:
                self._emit("debug", f"跳过已完成品牌 {brand.item_id}。")
                continue
            self._emit("info", f"开始加载品牌 {brand.name} 的车系。")
            series_list = await api.fetch_series_for_brand(brand.item_id, brand.name)
            for series in series_list or []:
                series_by_id[str(series.get('series_id', ''))] = series

            completed.append(brand.item_id)
            completed_set.add(brand.item_id)
            workspace.progress.completed_brand_ids = completed[:]
            workspace.progress.stages["series"].updated_at = datetime.now().isoformat()
            self.workspace_manager.write_result_file(
                workspace.root,
                SERIES_CATALOG_FILE,
                {
                    "metadata": {
                        "source": "dongchedi",
                        "data_type": "series_catalog",
                        "created_at": existing_payload.get("metadata", {}).get("created_at", datetime.now().isoformat()),
                        "updated_at": datetime.now().isoformat(),
                        "selected_brand_total": len(selected_brands),
                        "completed_brand_total": len(completed),
                        "total": len(series_by_id),
                    },
                    "data": sorted(series_by_id.values(), key=lambda item: str(item.get("series_id", ""))),
                },
            )
            self.workspace_manager.save_workspace(workspace)
            self._emit("info", f"品牌 {brand.name} 的车系加载完成，累计 {len(series_by_id)} 个车系。")

        workspace.progress.stages["series"].status = "done"
        workspace.progress.stages["series"].updated_at = datetime.now().isoformat()
        self.workspace_manager.save_workspace(workspace)
        self._emit("info", f"车系目录加载完成，共 {len(series_by_id)} 个车系。")
        return sorted(series_by_id.values(), key=lambda item: str(item.get("series_id", "")))

    def select_series(self, workspace_root: str | Path, series_ids: List[str]) -> List[SelectionItem]:
        workspace = self.workspace_manager.load_workspace(workspace_root)
        payload = self.workspace_manager.read_result_file(workspace.root, SERIES_CATALOG_FILE)
        catalog = list(payload.get("data") or [])
        selected_id_set = {str(raw) for raw in series_ids}

        selected = [
            SelectionItem(
                item_id=str(item.get("series_id", "")),
                name=str(item.get("series_name", "")),
                parent_id=str(item.get("brand_id", "")),
            )
            for item in catalog
            if str(item.get("series_id", "")) in selected_id_set
        ]

        workspace.scope.series = selected
        workspace.progress.completed_series_ids = []
        workspace.progress.completed_overview_series_ids = []
        workspace.progress.completed_detail_ids = []
        workspace.progress.completed_ocr_ids = []
        self._reset_stage(workspace, "overviews")
        self._reset_stage(workspace, "details")
        self._reset_stage(workspace, "ocr_price")
        self._clear_files(workspace.root, OVERVIEWS_FILE, DETAILS_FILE, IMAGES_FILE, CONFIGS_FILE)
        self._clear_screenshots(workspace.root)
        self.workspace_manager.save_workspace(workspace)
        self.workspace_manager.write_result_file(
            workspace.root,
            SERIES_FILE,
            {
                "metadata": {
                    "source": "dongchedi",
                    "data_type": "selected_series",
                    "created_at": datetime.now().isoformat(),
                    "total": len(selected),
                },
                "data": [
                    {
                        "series_id": item.item_id,
                        "series_name": item.name,
                        "brand_id": item.parent_id,
                    }
                    for item in selected
                ],
            },
        )
        self._emit("info", f"已保存车系选择，共 {len(selected)} 个车系。")
        return selected

    async def load_overviews(self, workspace_root: str | Path) -> List[Dict[str, Any]]:
        workspace = self.workspace_manager.load_workspace(workspace_root)
        api = self._build_api(workspace)
        selected_series = list(workspace.scope.series)
        existing_payload = self.workspace_manager.read_result_file(workspace.root, OVERVIEWS_FILE)
        overviews_by_id = {
            str(item.get("sku_id", "")): item
            for item in existing_payload.get("data", [])
            if item.get("sku_id")
        }

        if not selected_series:
            return list(overviews_by_id.values())

        brand_name_map = {item.item_id: item.name for item in workspace.scope.brands}
        selected_series_ids = {item.item_id for item in selected_series}
        completed = [
            item_id
            for item_id in workspace.progress.completed_overview_series_ids
            if item_id in selected_series_ids
        ]
        completed_set = set(completed)
        workspace.progress.stages["overviews"].status = "running"
        self.workspace_manager.save_workspace(workspace)

        screenshot_dir = workspace.root / "screenshots" if workspace.config.enable_ocr else None
        if screenshot_dir:
            screenshot_dir.mkdir(parents=True, exist_ok=True)

        async with self._create_page_session(workspace) as page:
            for series in selected_series:
                if series.item_id in completed_set:
                    self._emit("debug", f"跳过已完成概览车系 {series.item_id}。")
                    continue
                self._emit("info", f"开始抓取概览 {series.name}。")
                cars = await api.fetch_all_car_list(
                    brand_id=series.parent_id,
                    brand_name=brand_name_map.get(series.parent_id, ""),
                    series_id=series.item_id,
                    series_name=series.name,
                    max_pages=workspace.config.max_pages,
                    screenshot_dir=str(screenshot_dir) if screenshot_dir else None,
                    page=page,
                )
                for car in cars or []:
                    if car.get("sku_id"):
                        overviews_by_id[str(car["sku_id"])] = car

                completed.append(series.item_id)
                completed_set.add(series.item_id)
                workspace.progress.completed_overview_series_ids = completed[:]
                workspace.progress.stages["overviews"].updated_at = datetime.now().isoformat()
                self.workspace_manager.write_result_file(
                    workspace.root,
                    OVERVIEWS_FILE,
                    {
                        "metadata": {
                            "source": "dongchedi",
                            "data_type": "overviews",
                            "created_at": existing_payload.get("metadata", {}).get("created_at", datetime.now().isoformat()),
                            "updated_at": datetime.now().isoformat(),
                            "selected_series_total": len(selected_series),
                            "completed_series_total": len(completed),
                            "total": len(overviews_by_id),
                        },
                        "data": sorted(overviews_by_id.values(), key=lambda item: str(item.get("sku_id", ""))),
                    },
                )
                self.workspace_manager.save_workspace(workspace)
                self._emit("info", f"概览 {series.name} 抓取完成，累计 {len(overviews_by_id)} 条。")

        workspace.progress.stages["overviews"].status = "done"
        workspace.progress.stages["overviews"].updated_at = datetime.now().isoformat()
        self.workspace_manager.save_workspace(workspace)
        self._emit("info", f"概览抓取完成，共 {len(overviews_by_id)} 条。")
        return sorted(overviews_by_id.values(), key=lambda item: str(item.get("sku_id", "")))

    async def load_details(self, workspace_root: str | Path, *, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        workspace = self.workspace_manager.load_workspace(workspace_root)
        api = self._build_api(workspace)

        overviews_payload = self.workspace_manager.read_result_file(workspace.root, OVERVIEWS_FILE)
        overviews = list(overviews_payload.get("data") or [])
        if not overviews:
            return []

        details_payload = self.workspace_manager.read_result_file(workspace.root, DETAILS_FILE)
        images_payload = self.workspace_manager.read_result_file(workspace.root, IMAGES_FILE)
        configs_payload = self.workspace_manager.read_result_file(workspace.root, CONFIGS_FILE)

        details_by_id = {
            str(item.get("sku_id", "")): item
            for item in details_payload.get("data", [])
            if item.get("sku_id")
        }
        images_by_id = {
            str(item.get("sku_id", "")): item
            for item in images_payload.get("data", [])
            if item.get("sku_id")
        }
        configs_by_id = {
            str(item.get("sku_id", "")): item
            for item in configs_payload.get("data", [])
            if item.get("sku_id")
        }

        completed_set = set(workspace.progress.completed_detail_ids)
        remaining = [
            item for item in overviews
            if str(item.get("sku_id", "")) and str(item.get("sku_id", "")) not in completed_set
        ]
        if limit is not None:
            remaining = remaining[:limit]
        if not remaining:
            workspace.progress.stages["details"].status = "done"
            workspace.progress.stages["details"].updated_at = datetime.now().isoformat()
            self.workspace_manager.save_workspace(workspace)
            return sorted(details_by_id.values(), key=lambda item: str(item.get("sku_id", "")))

        workspace.progress.stages["details"].status = "running"
        self.workspace_manager.save_workspace(workspace)
        completed = workspace.progress.completed_detail_ids[:]
        worker_total = 1 if self.page_session_factory is not None else max(1, min(workspace.config.max_workers, len(remaining)))
        self._emit("info", f"开始抓取详情，剩余 {len(remaining)} 条，并发 {worker_total}。")

        async def _persist_detail_snapshot() -> None:
            completed.sort(key=str)
            workspace.progress.completed_detail_ids = completed[:]
            workspace.progress.stages["details"].updated_at = datetime.now().isoformat()
            self.workspace_manager.write_result_file(
                workspace.root,
                DETAILS_FILE,
                {
                    "metadata": {
                        "source": "dongchedi",
                        "data_type": "details",
                        "created_at": details_payload.get("metadata", {}).get("created_at", datetime.now().isoformat()),
                        "updated_at": datetime.now().isoformat(),
                        "total": len(details_by_id),
                    },
                    "data": sorted(details_by_id.values(), key=lambda item: str(item.get("sku_id", ""))),
                },
            )
            self.workspace_manager.write_result_file(
                workspace.root,
                IMAGES_FILE,
                {
                    "metadata": {
                        "source": "dongchedi",
                        "data_type": "images",
                        "created_at": images_payload.get("metadata", {}).get("created_at", datetime.now().isoformat()),
                        "updated_at": datetime.now().isoformat(),
                        "total": len(images_by_id),
                    },
                    "data": sorted(images_by_id.values(), key=lambda item: str(item.get("sku_id", ""))),
                },
            )
            self.workspace_manager.write_result_file(
                workspace.root,
                CONFIGS_FILE,
                {
                    "metadata": {
                        "source": "dongchedi",
                        "data_type": "configs",
                        "created_at": configs_payload.get("metadata", {}).get("created_at", datetime.now().isoformat()),
                        "updated_at": datetime.now().isoformat(),
                        "total": len(configs_by_id),
                    },
                    "data": sorted(configs_by_id.values(), key=lambda item: str(item.get("sku_id", ""))),
                },
            )
            self.workspace_manager.save_workspace(workspace)

        async def _record_detail(detail: Dict[str, Any]) -> None:
            sku_id = str(detail.get("sku_id", ""))
            if not sku_id:
                return
            detail_row, image_row, config_row = self._split_detail_payload(detail)
            details_by_id[sku_id] = detail_row
            images_by_id[sku_id] = image_row
            configs_by_id[sku_id] = config_row

            if sku_id not in completed_set:
                completed.append(sku_id)
                completed_set.add(sku_id)

            await _persist_detail_snapshot()
            self._emit("info", f"详情已落盘 {sku_id}，累计 {len(details_by_id)} 条。")

        async def _fetch_single_detail(page: Any, sku_id: str) -> None:
            self._emit("debug", f"抓取详情 {sku_id}。")
            try:
                detail = await api.fetch_car_detail(page, sku_id)
            except Exception as exc:
                error = str(exc).splitlines()[0][:160] if str(exc).splitlines() else str(exc)[:160]
                self._emit("warning", f"详情抓取失败 {sku_id}: {error}")
                return
            if not detail or not detail.get("sku_id"):
                self._emit("warning", f"详情抓取失败或为空：{sku_id}")
                return
            await _record_detail(detail)

        if worker_total == 1:
            async with self._create_page_session(workspace) as page:
                for overview in remaining:
                    await _fetch_single_detail(page, str(overview.get("sku_id", "")))
        else:
            queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
            for overview in remaining:
                queue.put_nowait(overview)

            lock = asyncio.Lock()

            async def _worker(worker_id: int, page: Any) -> None:
                while True:
                    try:
                        overview = queue.get_nowait()
                    except asyncio.QueueEmpty:
                        return

                    sku_id = str(overview.get("sku_id", ""))
                    try:
                        async with lock:
                            self._emit("debug", f"worker-{worker_id} 抓取详情 {sku_id}。")
                        try:
                            detail = await api.fetch_car_detail(page, sku_id)
                        except Exception as exc:
                            error = str(exc).splitlines()[0][:160] if str(exc).splitlines() else str(exc)[:160]
                            async with lock:
                                self._emit("warning", f"详情抓取失败 {sku_id}: {error}")
                            continue
                        if not detail or not detail.get("sku_id"):
                            async with lock:
                                self._emit("warning", f"详情抓取失败或为空：{sku_id}")
                            continue
                        async with lock:
                            await _record_detail(detail)
                    finally:
                        queue.task_done()

            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(
                    **build_chromium_launch_kwargs(
                        headless=workspace.config.headless,
                        slow_mo=getattr(api, "slow_mo", 0),
                    )
                )
                context = await browser.new_context(accept_downloads=True)
                pages = [await context.new_page() for _ in range(worker_total)]
                try:
                    await asyncio.gather(*(_worker(index + 1, page) for index, page in enumerate(pages)))
                finally:
                    for page in pages:
                        await page.close()
                    await context.close()
                    await browser.close()

        workspace.progress.stages["details"].status = "done"
        workspace.progress.stages["details"].updated_at = datetime.now().isoformat()
        self.workspace_manager.save_workspace(workspace)
        self._emit("info", f"详情抓取完成，共 {len(details_by_id)} 条。")
        return sorted(details_by_id.values(), key=lambda item: str(item.get("sku_id", "")))

    def _build_api(self, workspace: TaskWorkspace) -> Any:
        return self.api_factory(headless=workspace.config.headless)

    @asynccontextmanager
    async def _create_page_session(self, workspace: TaskWorkspace) -> AsyncIterator[Any]:
        if self.page_session_factory is not None:
            async with self.page_session_factory(workspace) as page:
                yield page
            return

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(
                **build_chromium_launch_kwargs(headless=workspace.config.headless)
            )
            page = await browser.new_page()
            try:
                yield page
            finally:
                await page.close()
                await browser.close()

    def _split_detail_payload(self, detail: Dict[str, Any]) -> tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
        sku_id = str(detail.get("sku_id", ""))
        detail_row = {key: value for key, value in detail.items() if key not in {"images", "config", "detail_params"}}
        image_row = {"sku_id": sku_id, "images": detail.get("images", [])}
        config_row = {
            "sku_id": sku_id,
            "config": detail.get("config"),
            "detail_params": detail.get("detail_params"),
        }
        return detail_row, image_row, config_row

    def _reset_stage(self, workspace: TaskWorkspace, stage_name: str) -> None:
        stage = workspace.progress.stages.get(stage_name)
        if stage is None:
            return
        stage.status = "pending"
        stage.updated_at = datetime.now().isoformat()

    def _clear_files(self, workspace_root: Path, *file_names: str) -> None:
        for file_name in file_names:
            file_path = workspace_root / file_name
            if file_path.exists():
                file_path.unlink()

    def _clear_screenshots(self, workspace_root: Path) -> None:
        screenshot_dir = workspace_root / "screenshots"
        if screenshot_dir.exists():
            shutil.rmtree(screenshot_dir)
        screenshot_dir.mkdir(parents=True, exist_ok=True)

    def _emit(self, level: str, message: str) -> None:
        if self.event_callback is not None:
            self.event_callback(level, message)
