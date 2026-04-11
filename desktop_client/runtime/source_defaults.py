from __future__ import annotations

from pathlib import Path

from db_config import DB_CONFIG
from desktop_client.models import DatabaseConfig, TaskConfig, TaskSource

SOURCE_DEFAULTS: dict[TaskSource, dict[str, object]] = {
    "dongchedi": {
        "task_name": "懂车帝采集任务",
        "output_dir": "client_output",
        "max_workers": 10,
        "max_pages": 167,
        "enable_db": False,
        "enable_ocr": False,
        "headless": False,
        "auto_resume": True,
        "resume_policy": "resume",
    },
    "guazi": {
        "task_name": "瓜子采集任务",
        "output_dir": "guazi_output",
        "max_workers": 8,
        "max_pages": 1,
        "enable_db": False,
        "enable_ocr": False,
        "headless": True,
        "auto_resume": True,
        "resume_policy": "resume",
    },
}


def default_db_config() -> DatabaseConfig:
    return DatabaseConfig.from_dict(DB_CONFIG)


def build_default_task_config(
    source: TaskSource,
    *,
    workspace_dir: str = "",
    output_dir: str | None = None,
) -> TaskConfig:
    profile = SOURCE_DEFAULTS[source]
    resolved_output = output_dir if output_dir is not None else str(profile["output_dir"])
    return TaskConfig(
        task_name=str(profile["task_name"]),
        source=source,
        workspace_dir=workspace_dir,
        output_dir=resolved_output,
        max_workers=int(profile["max_workers"]),
        max_pages=int(profile["max_pages"]),
        enable_db=bool(profile["enable_db"]),
        enable_ocr=bool(profile["enable_ocr"]),
        headless=bool(profile["headless"]),
        auto_resume=bool(profile["auto_resume"]),
        resume_policy=str(profile["resume_policy"]),
        db_config=default_db_config(),
    )


def resolve_output_dir(raw_path: str, *, cwd: str | Path | None = None) -> Path:
    if not raw_path.strip():
        raise ValueError("输出目录不能为空。")

    path = Path(raw_path).expanduser()
    if path.is_absolute():
        return path

    base = Path(cwd) if cwd is not None else Path.cwd()
    return (base / path).resolve()
