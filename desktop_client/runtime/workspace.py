from __future__ import annotations

import json
import re
import shutil
import zipfile
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, Iterable

from desktop_client.models import (
    STAGES_BY_SOURCE,
    StageStatus,
    TaskConfig,
    TaskProgress,
    TaskScope,
    TaskWorkspace,
    now_iso,
)
from desktop_client.runtime.source_defaults import resolve_output_dir

TASK_CONFIG_FILE = "task_config.json"
TASK_SCOPE_FILE = "task_scope.json"
PROGRESS_FILE = "progress.json"
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
DIRECTORIES = ("screenshots",)

_STAGE_PRIORITY = {
    "pending": 0,
    "interrupted": 1,
    "failed": 2,
    "running": 3,
    "done": 4,
}


def slugify(value: str) -> str:
    slug = re.sub(r"[^0-9a-zA-Z_-]+", "-", value.strip()).strip("-").lower()
    return slug or "task"


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
    tmp_path.replace(path)


def _read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


class WorkspaceManager:
    def __init__(self, base_dir: str | Path):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def create_workspace(self, config: TaskConfig, scope: TaskScope) -> TaskWorkspace:
        workspace_name = f"{slugify(config.task_name)}-{slugify(config.source)}"
        root = resolve_output_dir(config.output_dir, cwd=Path.cwd()) if config.output_dir else self.base_dir / workspace_name
        root.mkdir(parents=True, exist_ok=True)

        if config.resume_policy == "restart":
            self.reset_workspace(root)

        for directory in DIRECTORIES:
            (root / directory).mkdir(exist_ok=True)

        existing_scope = self._load_existing_scope(root)
        existing_progress = self._load_existing_progress(root, config.source)
        hydrated_scope = existing_scope if self._scope_is_empty(scope) and existing_scope is not None else scope

        hydrated_config = replace(
            config,
            workspace_dir=str(root),
            output_dir=str(root),
            updated_at=now_iso(),
        )
        progress = existing_progress or TaskProgress.create(hydrated_config.source)
        workspace = TaskWorkspace(root=root, config=hydrated_config, scope=hydrated_scope, progress=progress)
        self.save_workspace(workspace)
        return workspace

    def save_workspace(self, workspace: TaskWorkspace) -> None:
        workspace.root.mkdir(parents=True, exist_ok=True)
        _write_json(workspace.root / TASK_CONFIG_FILE, workspace.config.to_dict())
        _write_json(workspace.root / TASK_SCOPE_FILE, workspace.scope.to_dict())
        workspace.progress.updated_at = now_iso()
        _write_json(workspace.root / PROGRESS_FILE, workspace.progress.to_dict())

    def read_result_file(self, root: str | Path, file_name: str) -> Dict[str, Any]:
        file_path = Path(root) / file_name
        if not file_path.exists():
            return {}
        return _read_json(file_path)

    def write_result_file(self, root: str | Path, file_name: str, payload: Dict[str, Any]) -> Path:
        file_path = Path(root) / file_name
        _write_json(file_path, payload)
        return file_path

    def load_workspace(self, root: str | Path) -> TaskWorkspace:
        root_path = Path(root)
        config = TaskConfig.from_dict(_read_json(root_path / TASK_CONFIG_FILE))
        scope = TaskScope.from_dict(_read_json(root_path / TASK_SCOPE_FILE))
        progress = TaskProgress.from_dict(_read_json(root_path / PROGRESS_FILE), source=config.source)
        return TaskWorkspace(root=root_path, config=config, scope=scope, progress=progress)

    def export_workspace(self, root: str | Path, archive_path: str | Path) -> Path:
        root_path = Path(root)
        archive = Path(archive_path)
        archive.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            for file_name in (TASK_CONFIG_FILE, TASK_SCOPE_FILE, PROGRESS_FILE, *RESULT_FILES):
                file_path = root_path / file_name
                if file_path.exists():
                    bundle.write(file_path, arcname=file_name)

            for directory in DIRECTORIES:
                dir_path = root_path / directory
                if not dir_path.exists():
                    continue
                for file_path in dir_path.rglob("*"):
                    if file_path.is_file():
                        bundle.write(file_path, arcname=str(file_path.relative_to(root_path)))
        return archive

    def import_workspace(self, archive_path: str | Path, *, target_name: str | None = None) -> TaskWorkspace:
        archive = Path(archive_path)
        destination = self.base_dir / (target_name or archive.stem)
        destination.mkdir(parents=True, exist_ok=True)

        if archive.is_dir():
            shutil.copytree(archive, destination, dirs_exist_ok=True)
        else:
            with zipfile.ZipFile(archive, "r") as bundle:
                bundle.extractall(destination)

        workspace = self.load_workspace(destination)
        workspace.config.workspace_dir = str(destination)
        workspace.config.output_dir = str(destination)
        workspace.config.updated_at = now_iso()
        self.save_workspace(workspace)
        return workspace

    def export_progress_file(self, root: str | Path, progress_path: str | Path) -> Path:
        root_path = Path(root)
        output = Path(progress_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root_path / PROGRESS_FILE, output)
        return output

    def reset_workspace(self, root: str | Path) -> None:
        root_path = Path(root)
        for file_name in (TASK_CONFIG_FILE, TASK_SCOPE_FILE, PROGRESS_FILE, *RESULT_FILES):
            file_path = root_path / file_name
            if file_path.exists():
                file_path.unlink()
        for directory in DIRECTORIES:
            dir_path = root_path / directory
            if dir_path.exists():
                shutil.rmtree(dir_path)

    def import_progress_file(self, root: str | Path, progress_path: str | Path) -> TaskProgress:
        workspace = self.load_workspace(root)
        imported = TaskProgress.from_dict(_read_json(Path(progress_path)), source=workspace.config.source)
        workspace.progress = merge_progress(workspace.progress, imported)
        self.save_workspace(workspace)
        return workspace.progress

    def merge_workspaces(
        self,
        primary_root: str | Path,
        secondary_root: str | Path,
        *,
        target_name: str | None = None,
    ) -> TaskWorkspace:
        primary = self.load_workspace(primary_root)
        secondary = self.load_workspace(secondary_root)
        if primary.config.source != secondary.config.source:
            raise ValueError("不同数据源的工作区不能直接合并。")

        destination = self.base_dir / (target_name or f"{Path(primary_root).name}-merged")
        destination.mkdir(parents=True, exist_ok=True)
        for directory in DIRECTORIES:
            (destination / directory).mkdir(parents=True, exist_ok=True)

        merged_config = replace(
            primary.config,
            task_name=target_name or f"{primary.config.task_name}-merged",
            workspace_dir=str(destination),
            output_dir=str(destination),
            updated_at=now_iso(),
        )
        merged_scope = TaskScope(
            cities=_merge_lists(primary.scope.cities, secondary.scope.cities),
            brands=_merge_selection_items(primary.scope.brands, secondary.scope.brands),
            series=_merge_selection_items(primary.scope.series, secondary.scope.series),
            enabled_stages=_merge_lists(primary.scope.enabled_stages, secondary.scope.enabled_stages),
        )
        merged_progress = merge_progress(primary.progress, secondary.progress)
        merged_workspace = TaskWorkspace(
            root=destination,
            config=merged_config,
            scope=merged_scope,
            progress=merged_progress,
        )
        self.save_workspace(merged_workspace)

        for file_name in RESULT_FILES:
            primary_payload = self.read_result_file(primary.root, file_name)
            secondary_payload = self.read_result_file(secondary.root, file_name)
            merged_payload = merge_result_payload(file_name, primary_payload, secondary_payload)
            if merged_payload:
                self.write_result_file(destination, file_name, merged_payload)

        for directory in DIRECTORIES:
            self._merge_directory(primary.root / directory, destination / directory)
            self._merge_directory(secondary.root / directory, destination / directory)

        return self.load_workspace(destination)

    def _merge_directory(self, source: Path, destination: Path) -> None:
        if not source.exists():
            return
        for file_path in source.rglob("*"):
            if not file_path.is_file():
                continue
            target_path = destination / file_path.relative_to(source)
            target_path.parent.mkdir(parents=True, exist_ok=True)
            if not target_path.exists():
                shutil.copy2(file_path, target_path)

    def _load_existing_scope(self, root: Path) -> TaskScope | None:
        scope_path = root / TASK_SCOPE_FILE
        if not scope_path.exists():
            return None
        return TaskScope.from_dict(_read_json(scope_path))

    def _load_existing_progress(self, root: Path, source: str) -> TaskProgress | None:
        progress_path = root / PROGRESS_FILE
        if not progress_path.exists():
            return None
        return TaskProgress.from_dict(_read_json(progress_path), source=source)

    def _scope_is_empty(self, scope: TaskScope) -> bool:
        return not scope.cities and not scope.brands and not scope.series and not scope.enabled_stages


def merge_progress(current: TaskProgress, imported: TaskProgress) -> TaskProgress:
    if current.source != imported.source:
        raise ValueError("断点文件数据源不匹配，无法合并。")

    merged_stages = {}
    for stage in STAGES_BY_SOURCE[current.source]:
        current_stage = current.stages.get(stage, StageStatus())
        imported_stage = imported.stages.get(stage, StageStatus())
        if _STAGE_PRIORITY[imported_stage.status] > _STAGE_PRIORITY[current_stage.status]:
            merged_stages[stage] = imported_stage
        else:
            merged_stages[stage] = current_stage

    merged = TaskProgress(
        source=current.source,
        stages=merged_stages,
        completed_brand_ids=_merge_lists(current.completed_brand_ids, imported.completed_brand_ids),
        completed_series_ids=_merge_lists(current.completed_series_ids, imported.completed_series_ids),
        completed_overview_series_ids=_merge_lists(
            current.completed_overview_series_ids,
            imported.completed_overview_series_ids,
        ),
        completed_detail_ids=_merge_lists(current.completed_detail_ids, imported.completed_detail_ids),
        completed_ocr_ids=_merge_lists(current.completed_ocr_ids, imported.completed_ocr_ids),
        last_error=imported.last_error or current.last_error,
        updated_at=now_iso(),
    )
    return merged


def merge_result_payload(file_name: str, left: Dict[str, Any], right: Dict[str, Any]) -> Dict[str, Any]:
    if not left and not right:
        return {}

    data = merge_result_rows(file_name, left.get("data", []), right.get("data", []))
    metadata = {
        "created_at": left.get("metadata", {}).get("created_at")
        or right.get("metadata", {}).get("created_at")
        or now_iso(),
        "updated_at": now_iso(),
        "total": len(data),
    }
    source = left.get("metadata", {}).get("source") or right.get("metadata", {}).get("source")
    data_type = left.get("metadata", {}).get("data_type") or right.get("metadata", {}).get("data_type")
    if source:
        metadata["source"] = source
    if data_type:
        metadata["data_type"] = data_type
    return {"metadata": metadata, "data": data}


def merge_result_rows(file_name: str, left: Iterable[Dict[str, Any]], right: Iterable[Dict[str, Any]]) -> list[Dict[str, Any]]:
    key_name = result_key_name(file_name)
    if key_name is None:
        merged = list(left) + list(right)
        return merged

    rows: dict[str, Dict[str, Any]] = {}
    for item in list(left) + list(right):
        key = str(item.get(key_name, "")).strip()
        if not key:
            continue
        previous = rows.get(key)
        if previous is None or _row_score(item) >= _row_score(previous):
            rows[key] = item
    return sorted(rows.values(), key=lambda item: str(item.get(key_name, "")))


def result_key_name(file_name: str) -> str | None:
    mapping = {
        "brand_catalog.json": "brand_id",
        "brands.json": "brand_id",
        "series_catalog.json": "series_id",
        "series.json": "series_id",
        "overviews.json": "sku_id",
        "details.json": "sku_id",
        "images.json": "sku_id",
        "configs.json": "sku_id",
    }
    return mapping.get(file_name)


def _row_score(row: Dict[str, Any]) -> int:
    score = 0
    for value in row.values():
        if value in ("", None, [], {}, ()):
            continue
        score += 1
    return score


def _merge_lists(left: Iterable[str], right: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for raw in list(left) + list(right):
        value = str(raw).strip()
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _merge_selection_items(left: Iterable[Any], right: Iterable[Any]) -> list[Any]:
    rows: dict[str, Any] = {}
    for item in list(left) + list(right):
        key = getattr(item, "item_id", "")
        if not key:
            continue
        previous = rows.get(key)
        if previous is None:
            rows[key] = item
            continue
        prev_score = _selection_score(previous)
        curr_score = _selection_score(item)
        if curr_score >= prev_score:
            rows[key] = item
    return list(rows.values())


def _selection_score(item: Any) -> int:
    score = 0
    if getattr(item, "item_id", ""):
        score += 1
    if getattr(item, "name", ""):
        score += 1
    if getattr(item, "parent_id", ""):
        score += 1
    return score
