from __future__ import annotations

import importlib.util


def has_pyside6() -> bool:
    return importlib.util.find_spec("PySide6") is not None


def gui_dependency_message() -> str:
    return "缺少 PySide6，请先执行: pip install PySide6"

