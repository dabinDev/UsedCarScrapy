from __future__ import annotations

import sys
from pathlib import Path

from desktop_client.ui.dependencies import gui_dependency_message, has_pyside6


def default_workspace_root() -> Path:
    return Path(__file__).resolve().parent / "workspaces"


def main() -> int:
    if not has_pyside6():
        print(gui_dependency_message())
        return 1

    from PySide6.QtWidgets import QApplication

    from desktop_client.ui.main_window import MainWindow

    app = QApplication(sys.argv)
    window = MainWindow(default_workspace_root())
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

