from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

TaskSource = Literal["dongchedi", "guazi"]
StageStatusValue = Literal["pending", "running", "done", "failed", "interrupted"]

STAGES_BY_SOURCE: dict[str, list[str]] = {
    "dongchedi": ["brands", "series", "overviews", "details", "ocr_price"],
    "guazi": ["brands", "series", "overviews", "details"],
}

LEGACY_PROGRESS_KEYS = {
    "completed_brand_ids": "completed_brands_series",
    "completed_overview_series_ids": "completed_overviews",
    "completed_detail_ids": "completed_details",
    "completed_ocr_ids": "completed_ocr",
}


def now_iso() -> str:
    return datetime.now().isoformat()


def _unique_strings(items: List[str]) -> List[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        value = str(item).strip()
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _load_progress_values(payload: Dict[str, Any], modern_key: str) -> List[str]:
    values = list(payload.get(modern_key, []))
    legacy_key = LEGACY_PROGRESS_KEYS.get(modern_key)
    if legacy_key:
        values.extend(payload.get(legacy_key, []))
    return _unique_strings(values)


@dataclass(slots=True)
class DatabaseConfig:
    host: str = ""
    port: int = 3306
    user: str = ""
    password: str = ""
    database: str = ""
    charset: str = "utf8mb4"

    def to_dict(self, *, include_password: bool = True) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "host": self.host,
            "port": self.port,
            "user": self.user,
            "database": self.database,
            "charset": self.charset,
        }
        if include_password:
            data["password"] = self.password
        return data

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "DatabaseConfig":
        payload = data or {}
        return cls(
            host=str(payload.get("host", "")),
            port=int(payload.get("port", 3306)),
            user=str(payload.get("user", "")),
            password=str(payload.get("password", "")),
            database=str(payload.get("database", "")),
            charset=str(payload.get("charset", "utf8mb4")),
        )


@dataclass(slots=True)
class SelectionItem:
    item_id: str
    name: str = ""
    parent_id: str = ""

    def to_dict(self) -> Dict[str, str]:
        return {
            "item_id": self.item_id,
            "name": self.name,
            "parent_id": self.parent_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SelectionItem":
        return cls(
            item_id=str(data.get("item_id", "")),
            name=str(data.get("name", "")),
            parent_id=str(data.get("parent_id", "")),
        )


@dataclass(slots=True)
class TaskScope:
    cities: List[str] = field(default_factory=list)
    brands: List[SelectionItem] = field(default_factory=list)
    series: List[SelectionItem] = field(default_factory=list)
    enabled_stages: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cities": _unique_strings(self.cities),
            "brands": [item.to_dict() for item in self.brands if item.item_id],
            "series": [item.to_dict() for item in self.series if item.item_id],
            "enabled_stages": _unique_strings(self.enabled_stages),
        }

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "TaskScope":
        payload = data or {}
        return cls(
            cities=_unique_strings(list(payload.get("cities", []))),
            brands=[SelectionItem.from_dict(item) for item in payload.get("brands", [])],
            series=[SelectionItem.from_dict(item) for item in payload.get("series", [])],
            enabled_stages=_unique_strings(list(payload.get("enabled_stages", []))),
        )


@dataclass(slots=True)
class StageStatus:
    status: StageStatusValue = "pending"
    updated_at: str = field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, str]:
        return {"status": self.status, "updated_at": self.updated_at}

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "StageStatus":
        payload = data or {}
        return cls(
            status=str(payload.get("status", "pending")),
            updated_at=str(payload.get("updated_at", now_iso())),
        )


@dataclass(slots=True)
class TaskProgress:
    source: TaskSource
    stages: Dict[str, StageStatus]
    completed_brand_ids: List[str] = field(default_factory=list)
    completed_series_ids: List[str] = field(default_factory=list)
    completed_overview_series_ids: List[str] = field(default_factory=list)
    completed_detail_ids: List[str] = field(default_factory=list)
    completed_ocr_ids: List[str] = field(default_factory=list)
    last_error: str = ""
    updated_at: str = field(default_factory=now_iso)

    @classmethod
    def create(cls, source: TaskSource) -> "TaskProgress":
        return cls(
            source=source,
            stages={stage: StageStatus(status="pending") for stage in STAGES_BY_SOURCE[source]},
        )

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "source": self.source,
            "stages": {name: value.to_dict() for name, value in self.stages.items()},
            "completed_brand_ids": _unique_strings(self.completed_brand_ids),
            "completed_series_ids": _unique_strings(self.completed_series_ids),
            "completed_overview_series_ids": _unique_strings(self.completed_overview_series_ids),
            "completed_detail_ids": _unique_strings(self.completed_detail_ids),
            "completed_ocr_ids": _unique_strings(self.completed_ocr_ids),
            "last_error": self.last_error,
            "updated_at": self.updated_at,
        }
        for modern_key, legacy_key in LEGACY_PROGRESS_KEYS.items():
            payload[legacy_key] = list(payload[modern_key])
        return payload

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]], *, source: Optional[TaskSource] = None) -> "TaskProgress":
        payload = data or {}
        task_source = source or payload.get("source", "dongchedi")
        stage_names = STAGES_BY_SOURCE[task_source]
        stage_data = payload.get("stages", {})
        return cls(
            source=task_source,
            stages={stage: StageStatus.from_dict(stage_data.get(stage)) for stage in stage_names},
            completed_brand_ids=_load_progress_values(payload, "completed_brand_ids"),
            completed_series_ids=_unique_strings(list(payload.get("completed_series_ids", []))),
            completed_overview_series_ids=_load_progress_values(payload, "completed_overview_series_ids"),
            completed_detail_ids=_load_progress_values(payload, "completed_detail_ids"),
            completed_ocr_ids=_load_progress_values(payload, "completed_ocr_ids"),
            last_error=str(payload.get("last_error", "")),
            updated_at=str(payload.get("updated_at", now_iso())),
        )


@dataclass(slots=True)
class TaskConfig:
    task_name: str
    source: TaskSource
    workspace_dir: str
    output_dir: str
    max_workers: int = 10
    max_pages: int = 167
    enable_db: bool = False
    enable_ocr: bool = False
    headless: bool = True
    auto_resume: bool = True
    resume_policy: str = "resume"
    db_config: Optional[DatabaseConfig] = None
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    def to_dict(self, *, include_password: bool = True) -> Dict[str, Any]:
        return {
            "task_name": self.task_name,
            "source": self.source,
            "workspace_dir": self.workspace_dir,
            "output_dir": self.output_dir,
            "max_workers": self.max_workers,
            "max_pages": self.max_pages,
            "enable_db": self.enable_db,
            "enable_ocr": self.enable_ocr,
            "headless": self.headless,
            "auto_resume": self.auto_resume,
            "resume_policy": self.resume_policy,
            "db_config": self.db_config.to_dict(include_password=include_password) if self.db_config else None,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TaskConfig":
        return cls(
            task_name=str(data.get("task_name", "")),
            source=str(data.get("source", "dongchedi")),
            workspace_dir=str(data.get("workspace_dir", "")),
            output_dir=str(data.get("output_dir", "")),
            max_workers=int(data.get("max_workers", 10)),
            max_pages=int(data.get("max_pages", 167)),
            enable_db=bool(data.get("enable_db", False)),
            enable_ocr=bool(data.get("enable_ocr", False)),
            headless=bool(data.get("headless", True)),
            auto_resume=bool(data.get("auto_resume", True)),
            resume_policy=str(data.get("resume_policy", "resume" if bool(data.get("auto_resume", True)) else "restart")),
            db_config=DatabaseConfig.from_dict(data.get("db_config")) if data.get("db_config") else None,
            created_at=str(data.get("created_at", now_iso())),
            updated_at=str(data.get("updated_at", now_iso())),
        )


@dataclass(slots=True)
class TaskWorkspace:
    root: Path
    config: TaskConfig
    scope: TaskScope
    progress: TaskProgress
