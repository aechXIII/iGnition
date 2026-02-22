import ctypes
import ctypes.wintypes
import time

import psutil


def _send_wm_close(pid: int) -> None:
    try:
        WM_CLOSE = 0x0010
        SMTO_ABORTIFHUNG = 0x0002

        def _callback(hwnd: int, _: int) -> bool:
            buf = ctypes.wintypes.DWORD(0)
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(buf))
            if buf.value == pid:
                ctypes.windll.user32.SendMessageTimeoutW(
                    hwnd, WM_CLOSE, 0, 0, SMTO_ABORTIFHUNG, 2000, None
                )
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(
            ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM
        )
        ctypes.windll.user32.EnumWindows(WNDENUMPROC(_callback), 0)
    except Exception:
        pass


def graceful_terminate_process(pid: int, grace_seconds: float) -> None:
    if grace_seconds <= 0:
        terminate_process(pid)
        return
    _send_wm_close(pid)
    deadline = time.monotonic() + grace_seconds
    try:
        proc = psutil.Process(pid)
        while time.monotonic() < deadline:
            try:
                if not proc.is_running() or proc.status() == psutil.STATUS_ZOMBIE:
                    return
            except psutil.NoSuchProcess:
                return
            time.sleep(0.3)
    except psutil.NoSuchProcess:
        return
    terminate_process(pid)


def graceful_terminate_process_tree(pid: int, grace_seconds: float) -> None:
    if grace_seconds <= 0:
        terminate_process_tree(pid)
        return
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
    except psutil.NoSuchProcess:
        return
    all_pids = [c.pid for c in children] + [pid]
    for p in all_pids:
        _send_wm_close(p)
    deadline = time.monotonic() + grace_seconds
    procs: list[psutil.Process] = []
    for p in all_pids:
        try:
            procs.append(psutil.Process(p))
        except psutil.NoSuchProcess:
            pass
    while time.monotonic() < deadline and procs:
        alive = []
        for proc in procs:
            try:
                if proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE:
                    alive.append(proc)
            except psutil.NoSuchProcess:
                pass
        procs = alive
        if not procs:
            return
        time.sleep(0.3)
    if procs:
        terminate_process_tree(pid)


def terminate_process(pid: int, *, timeout_seconds: float = 5.0) -> None:
    try:
        proc = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return

    try:
        proc.terminate()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return

    try:
        proc.wait(timeout=timeout_seconds)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return
    except psutil.TimeoutExpired:
        try:
            proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return


def terminate_process_tree(pid: int, *, timeout_seconds: float = 5.0) -> None:
    try:
        parent = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return

    children = []
    try:
        children = parent.children(recursive=True)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        children = []

    procs = [*children, parent]
    for proc in procs:
        try:
            proc.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    _, alive = psutil.wait_procs(procs, timeout=timeout_seconds)
    for proc in alive:
        try:
            proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
