import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

_FALLBACK_MESSAGE_SHOWN = False


def build_chromium_launch_kwargs(*, headless: bool, slow_mo: Optional[int] = None) -> Dict[str, Any]:
    kwargs: Dict[str, Any] = {"headless": headless}
    if slow_mo is not None:
        kwargs["slow_mo"] = slow_mo

    executable_path = os.getenv("PLAYWRIGHT_EXECUTABLE_PATH")
    if executable_path:
        executable = Path(executable_path).expanduser()
        if executable.exists():
            kwargs["executable_path"] = str(executable)
            return kwargs

    channel = os.getenv("PLAYWRIGHT_BROWSER_CHANNEL")
    if channel:
        kwargs["channel"] = channel
        return kwargs

    if _has_bundled_chromium():
        return kwargs

    fallback_channel = _detect_windows_browser_channel()
    if fallback_channel:
        kwargs["channel"] = fallback_channel
        _show_fallback_message(fallback_channel)

    return kwargs


def _has_bundled_chromium() -> bool:
    browsers_root = _resolve_browsers_root()
    if browsers_root is None or not browsers_root.exists():
        return False

    candidates = (
        "chromium-*/chrome-win/chrome.exe",
        "chromium-*/chrome-linux/chrome",
        "chromium-*/chrome-mac/Chromium.app",
    )
    for pattern in candidates:
        if any(browsers_root.glob(pattern)):
            return True
    return False


def _resolve_browsers_root() -> Optional[Path]:
    custom_root = os.getenv("PLAYWRIGHT_BROWSERS_PATH")
    if custom_root and custom_root != "0":
        return Path(custom_root).expanduser()

    if os.name == "nt":
        local_appdata = os.getenv("LOCALAPPDATA")
        if not local_appdata:
            return None
        return Path(local_appdata) / "ms-playwright"

    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "ms-playwright"

    return Path.home() / ".cache" / "ms-playwright"


def _detect_windows_browser_channel() -> Optional[str]:
    if os.name != "nt":
        return None

    channel_paths = {
        "chrome": _windows_program_files_paths("Google", "Chrome", "Application", "chrome.exe"),
        "msedge": _windows_program_files_paths("Microsoft", "Edge", "Application", "msedge.exe"),
    }
    for channel, paths in channel_paths.items():
        if any(path.exists() for path in paths):
            return channel
    return None


def _windows_program_files_paths(*parts: str) -> tuple[Path, ...]:
    roots = (
        os.getenv("ProgramFiles"),
        os.getenv("ProgramFiles(x86)"),
    )
    return tuple(Path(root, *parts) for root in roots if root)


def _show_fallback_message(channel: str) -> None:
    global _FALLBACK_MESSAGE_SHOWN
    if _FALLBACK_MESSAGE_SHOWN:
        return

    browser_name = "Chrome" if channel == "chrome" else "Edge"
    print(f"[Playwright] Bundled Chromium not found, fallback to system {browser_name}")
    _FALLBACK_MESSAGE_SHOWN = True
