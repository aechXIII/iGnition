from __future__ import annotations

import ctypes


class SingleInstance:
    def __init__(self, name: str) -> None:
        self.name = name
        self.acquired = False
        self._handle: int | None = None

    def __enter__(self) -> "SingleInstance":
        mutex_name = f"Global\\{self.name}"
        handle = ctypes.windll.kernel32.CreateMutexW(None, True, mutex_name)
        last_error = ctypes.windll.kernel32.GetLastError()
        self._handle = int(handle) if handle else None
        self.acquired = last_error != 183
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._handle is not None:
            ctypes.windll.kernel32.CloseHandle(self._handle)
            self._handle = None
