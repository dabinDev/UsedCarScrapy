from __future__ import annotations

from typing import Dict, Iterable, List

from desktop_client.models import DatabaseConfig, SelectionItem, TaskConfig, TaskScope


def parse_selection_lines(raw: str, *, allow_parent: bool = False) -> List[SelectionItem]:
    items: list[SelectionItem] = []
    for line in _split_tokens(raw):
        parts = [part.strip() for part in line.split(":")]
        if not parts or not parts[0]:
            continue

        if allow_parent and len(parts) >= 3:
            items.append(SelectionItem(item_id=parts[0], name=parts[1], parent_id=parts[2]))
        elif len(parts) >= 2:
            items.append(SelectionItem(item_id=parts[0], name=parts[1]))
        else:
            items.append(SelectionItem(item_id=parts[0], name=parts[0]))
    return items


def parse_text_list(raw: str) -> List[str]:
    values: list[str] = []
    seen: set[str] = set()
    for token in _split_tokens(raw):
        if token in seen:
            continue
        seen.add(token)
        values.append(token)
    return values


def format_selection_lines(items: Iterable[SelectionItem], *, include_parent: bool = False) -> str:
    lines: list[str] = []
    for item in items:
        if include_parent and item.parent_id:
            lines.append(f"{item.item_id}:{item.name}:{item.parent_id}")
        else:
            lines.append(f"{item.item_id}:{item.name}")
    return "\n".join(lines)


def build_scope(cities_raw: str, brands_raw: str, series_raw: str, enabled_stages: Iterable[str]) -> TaskScope:
    return TaskScope(
        cities=parse_text_list(cities_raw),
        brands=parse_selection_lines(brands_raw, allow_parent=False),
        series=parse_selection_lines(series_raw, allow_parent=True),
        enabled_stages=list(enabled_stages),
    )


def build_task_config(payload: Dict[str, object]) -> TaskConfig:
    db_enabled = bool(payload.get("enable_db", False))
    db_config = None
    if db_enabled:
        db_config = DatabaseConfig(
            host=str(payload.get("db_host", "")),
            port=int(payload.get("db_port", 3306)),
            user=str(payload.get("db_user", "")),
            password=str(payload.get("db_password", "")),
            database=str(payload.get("db_database", "")),
            charset=str(payload.get("db_charset", "utf8mb4")),
        )

    return TaskConfig(
        task_name=str(payload.get("task_name", "")).strip(),
        source=str(payload.get("source", "dongchedi")),
        workspace_dir=str(payload.get("workspace_dir", "")),
        output_dir=str(payload.get("output_dir", "")),
        max_workers=int(payload.get("max_workers", 10)),
        max_pages=int(payload.get("max_pages", 167)),
        enable_db=db_enabled,
        enable_ocr=bool(payload.get("enable_ocr", False)),
        headless=bool(payload.get("headless", True)),
        auto_resume=bool(payload.get("auto_resume", True)),
        resume_policy=str(payload.get("resume_policy", "resume" if bool(payload.get("auto_resume", True)) else "restart")),
        db_config=db_config,
    )


def _split_tokens(raw: str) -> List[str]:
    lines = raw.replace(",", "\n").splitlines()
    return [line.strip() for line in lines if line.strip()]
