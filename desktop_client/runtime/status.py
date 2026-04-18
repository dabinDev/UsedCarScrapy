from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from desktop_client.runtime.workspace import WorkspaceManager

RESULT_FILES = (
    "brand_catalog.json",
    "brands.json",
    "series_catalog.json",
    "series.json",
    "overviews.json",
    "details.json",
    "images.json",
    "configs.json",
)

STAGE_LABELS = {
    "brands": "品牌",
    "series": "车系",
    "overviews": "概览",
    "details": "详情",
    "ocr_price": "OCR 价格",
}

STATUS_LABELS = {
    "pending": "待执行",
    "running": "进行中",
    "done": "已完成",
    "failed": "失败",
    "interrupted": "已中断",
}

ITEM_STATE_LABELS = {
    "pending": "待执行",
    "series_loaded": "车系已完成",
    "overview_done": "概览已完成",
    "detail_done": "详情已完成",
}


def build_workspace_summary(workspace_root: str | Path, workspace_manager: WorkspaceManager) -> dict[str, Any]:
    workspace = workspace_manager.load_workspace(workspace_root)
    counts: dict[str, int] = {}
    for file_name in RESULT_FILES:
        payload = workspace_manager.read_result_file(workspace.root, file_name)
        counts[file_name] = len(payload.get("data", []))

    return {
        "task_name": workspace.config.task_name,
        "source": workspace.config.source,
        "workspace_root": str(workspace.root),
        "stage_status": {name: state.status for name, state in workspace.progress.stages.items()},
        "counts": counts,
        "selected_brand_total": len(workspace.scope.brands),
        "selected_series_total": len(workspace.scope.series),
        "completed_brand_total": len(workspace.progress.completed_brand_ids),
        "completed_overview_series_total": len(workspace.progress.completed_overview_series_ids),
        "completed_detail_total": len(workspace.progress.completed_detail_ids),
        "completed_ocr_total": len(workspace.progress.completed_ocr_ids),
    }


def format_workspace_summary(summary: dict[str, Any]) -> str:
    counts = summary["counts"]
    rendered_stage_status = " | ".join(
        f"{STAGE_LABELS.get(name, name)}={STATUS_LABELS.get(status, status)}"
        for name, status in summary["stage_status"].items()
    )
    return (
        f"任务名称: {summary['task_name']}\n"
        f"数据源: {summary['source']}\n"
        f"工作区: {summary['workspace_root']}\n"
        f"阶段状态: {rendered_stage_status}\n"
        f"已选品牌: {summary['selected_brand_total']} | 已选车系: {summary['selected_series_total']}\n"
        f"品牌目录: {counts['brand_catalog.json']} | 品牌选择: {counts['brands.json']}\n"
        f"车系目录: {counts['series_catalog.json']} | 车系选择: {counts['series.json']}\n"
        f"概览: {counts['overviews.json']} | 详情: {counts['details.json']}\n"
        f"图片: {counts['images.json']} | 配置: {counts['configs.json']}\n"
        f"已完成品牌目录拉取: {summary['completed_brand_total']}\n"
        f"已完成概览车系: {summary['completed_overview_series_total']}\n"
        f"已完成详情: {summary['completed_detail_total']}\n"
        f"已完成 OCR: {summary['completed_ocr_total']}"
    )


def build_scope_progress(workspace_root: str | Path, workspace_manager: WorkspaceManager) -> dict[str, Any]:
    workspace = workspace_manager.load_workspace(workspace_root)
    overviews_payload = workspace_manager.read_result_file(workspace.root, "overviews.json")
    overviews = list(overviews_payload.get("data", []))

    overview_series_ids = {str(item) for item in workspace.progress.completed_overview_series_ids}
    detail_ids = {str(item) for item in workspace.progress.completed_detail_ids}
    completed_brand_ids = {str(item) for item in workspace.progress.completed_brand_ids}

    sku_ids_by_series: dict[str, set[str]] = defaultdict(set)
    for row in overviews:
        series_id = str(row.get("series_id", "")).strip()
        sku_id = str(row.get("sku_id", "")).strip()
        if series_id and sku_id:
            sku_ids_by_series[series_id].add(sku_id)

    series_states: dict[str, dict[str, Any]] = {}
    for series in workspace.scope.series:
        sku_ids = sku_ids_by_series.get(series.item_id, set())
        detail_done_count = len(sku_ids & detail_ids)
        overview_done = series.item_id in overview_series_ids
        detail_done = overview_done and (not sku_ids or detail_done_count == len(sku_ids))
        progress_percent = (
            100
            if detail_done
            else round((detail_done_count / len(sku_ids)) * 100)
            if overview_done and sku_ids
            else 0
        )
        if detail_done:
            state = "detail_done"
        elif overview_done:
            state = "overview_done"
        else:
            state = "pending"
        series_states[series.item_id] = {
            "state": state,
            "label": ITEM_STATE_LABELS[state],
            "overview_total": len(sku_ids),
            "detail_done_total": detail_done_count,
            "progress_percent": progress_percent,
            "overview_percent": 100 if overview_done else 0,
            "detail_percent": progress_percent,
            "brand_id": series.parent_id,
            "name": series.name,
        }

    selected_series_by_brand: dict[str, list[str]] = defaultdict(list)
    for series in workspace.scope.series:
        selected_series_by_brand[series.parent_id].append(series.item_id)

    brand_states: dict[str, dict[str, Any]] = {}
    for brand in workspace.scope.brands:
        series_ids = selected_series_by_brand.get(brand.item_id, [])
        series_progress_values = [
            int(series_states.get(series_id, {}).get("progress_percent", 0) or 0)
            for series_id in series_ids
        ]
        all_series_done = bool(series_ids) and all(
            series_states.get(series_id, {}).get("state") == "detail_done"
            for series_id in series_ids
        )
        any_series_progress = any(
            series_states.get(series_id, {}).get("state") in {"overview_done", "detail_done"}
            for series_id in series_ids
        )
        if all_series_done:
            state = "detail_done"
        elif brand.item_id in completed_brand_ids or any_series_progress:
            state = "series_loaded"
        else:
            state = "pending"
        progress_percent = (
            100
            if all_series_done
            else round(sum(series_progress_values) / len(series_progress_values))
            if series_progress_values
            else 100
            if brand.item_id in completed_brand_ids
            else 0
        )
        brand_states[brand.item_id] = {
            "state": state,
            "label": ITEM_STATE_LABELS[state],
            "selected_series_total": len(series_ids),
            "completed_series_total": sum(
                1 for series_id in series_ids if series_states.get(series_id, {}).get("state") == "detail_done"
            ),
            "progress_percent": progress_percent,
            "catalog_percent": 100 if brand.item_id in completed_brand_ids else 0,
            "name": brand.name,
        }

    return {
        "brand_states": brand_states,
        "series_states": series_states,
    }
