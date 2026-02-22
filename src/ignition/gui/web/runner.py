from __future__ import annotations

import json
import logging
import sys
import threading
import time
from pathlib import Path

import webview

from ignition.core.state import AppState
from ignition.gui.tray import SystemTray
from ignition.gui.web.api import IgnitionApi


logger = logging.getLogger(__name__)

def _get_assets_dir() -> Path:
    """Return assets directory — works both in dev and PyInstaller bundle."""
    if getattr(sys, "frozen", False):
        # Running inside a PyInstaller bundle: _MEIPASS is the temp extraction dir
        return Path(sys._MEIPASS) / "ignition" / "gui" / "assets"  # type: ignore[attr-defined]
    return Path(__file__).parent.parent / "assets"

_ASSETS_DIR = _get_assets_dir()


def _run_status_push(api: IgnitionApi, window: webview.Window, stop_event: threading.Event) -> None:
    """Background thread: push iRacing status + log updates to the frontend."""
    last_log_seq = 0

    while not stop_event.is_set():
        time.sleep(0.8)
        if stop_event.is_set():
            return
        try:
            status = api.get_status()
            new_entries = api.get_log_since(last_log_seq)
            if new_entries:
                last_log_seq = new_entries[-1]["seq"] + 1

            status_js = json.dumps({
                "iracing_running":  status["iracing_running"],
                "managed_count":    status["managed_count"],
                "paused":           status["paused"],
                "session_type":     status.get("session_type"),
                "running_app_ids":  status.get("running_app_ids", []),
                "session_start_at": status.get("session_start_at"),
            })
            entries_js = json.dumps(new_entries)
            js = (
                f"window.__ignitionStatusUpdate && "
                f"window.__ignitionStatusUpdate({status_js}, {entries_js})"
            )
            window.evaluate_js(js)
        except Exception:
            continue


def run_webview(*, state: AppState, start_in_background: bool) -> int:
    api = IgnitionApi(state=state)
    state.controller.start()

    _window_ref: list[webview.Window | None] = [None]
    _push_stop = threading.Event()
    _force_quit: list[bool] = [False]

    def tray_open() -> None:
        w = _window_ref[0]
        if w:
            try:
                w.show()
            except Exception:
                pass

    def tray_quit() -> None:
        _force_quit[0] = True
        api.quit_app()

    tray = SystemTray(
        on_open=tray_open,
        on_quit=tray_quit,
        get_profiles=api.get_profiles,
        on_switch_profile=api.set_active_profile,
        get_active_profile_name=api.get_active_profile_name,
    )
    tray.start()

    index_path = _ASSETS_DIR / "index.html"

    window = webview.create_window(
        title="iGnition",
        url=str(index_path),
        js_api=api,
        width=1200,
        height=740,
        min_size=(900, 580),
        background_color="#0E0F11",
        hidden=start_in_background,
    )

    _window_ref[0] = window
    api.bind_window(window)
    api.bind_force_quit(lambda: _force_quit.__setitem__(0, True))
    api.bind_profiles_changed(tray.rebuild_menu)

    def _apply_window_icon() -> None:
        """Set taskbar + titlebar icon via Win32 WM_SETICON (ctypes, no extra deps)."""
        ico = _ASSETS_DIR / "ignition_logo.ico"
        if not ico.exists():
            return
        try:
            import ctypes
            import ctypes.wintypes
            import os
            import time
            time.sleep(0.3)  # wait for edge webview window to be fully created
            user32 = ctypes.windll.user32
            WM_SETICON, ICON_SMALL, ICON_BIG, IMAGE_ICON, LR_LOADFROMFILE = (
                0x0080, 0, 1, 1, 0x10
            )
            current_pid = os.getpid()
            found_hwnd: list[int] = []

            @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
            def _enum_cb(hwnd: int, _lparam: int) -> bool:
                pid = ctypes.wintypes.DWORD()
                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                if pid.value == current_pid and user32.IsWindowVisible(hwnd):
                    found_hwnd.append(hwnd)
                    return False  # stop enumeration
                return True

            user32.EnumWindows(_enum_cb, 0)
            hwnd = found_hwnd[0] if found_hwnd else 0
            if not hwnd:
                return
            path_w = str(ico)
            hicon_s = user32.LoadImageW(None, path_w, IMAGE_ICON, 32,  32,  LR_LOADFROMFILE)
            hicon_b = user32.LoadImageW(None, path_w, IMAGE_ICON, 256, 256, LR_LOADFROMFILE)
            if hicon_s:
                user32.SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hicon_s)
            if hicon_b:
                user32.SendMessageW(hwnd, WM_SETICON, ICON_BIG, hicon_b)
        except Exception:
            pass

    def on_loaded() -> None:
        push_thread = threading.Thread(
            target=_run_status_push,
            args=(api, window, _push_stop),
            daemon=True,
            name="status-push",
        )
        push_thread.start()
        icon_thread = threading.Thread(target=_apply_window_icon, daemon=True, name="win-icon")
        icon_thread.start()

    def on_closing() -> bool:
        if _force_quit[0]:
            return True
        if state.config_store.config.minimize_to_tray:
            try:
                window.hide()
            except Exception:
                pass
            return False
        return True

    window.events.loaded += on_loaded
    window.events.closing += on_closing

    try:
        webview.start(debug=False, private_mode=False)
    finally:
        _push_stop.set()
        state.controller.stop()
        tray.stop()

    return 0
