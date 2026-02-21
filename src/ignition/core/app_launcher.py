from __future__ import annotations

import os
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ignition.core.process_utils import any_process_exe_running


@dataclass(frozen=True)
class LaunchResult:
    pid: int


def launch_executable(
    *,
    executable_path: str,
    arguments: str,
    working_directory: str,
    start_minimized: bool,
    allow_if_already_running: bool,
) -> LaunchResult | None:

    if not executable_path:
        raise ValueError("Executable path is required")
    if not os.path.exists(executable_path):
        raise FileNotFoundError(executable_path)

    if not allow_if_already_running and any_process_exe_running(executable_path):
        return None

    args = [executable_path]
    if arguments.strip():
        args.extend(shlex.split(arguments, posix=False))

    cwd = working_directory.strip() or str(Path(executable_path).parent)

    startupinfo = None
    if start_minimized and os.name == "nt":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = 7  # SW_SHOWMINNOACTIVE (not exported by subprocess module)

    proc = subprocess.Popen(
        args,
        cwd=cwd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        startupinfo=startupinfo,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0,
    )
    return LaunchResult(pid=int(proc.pid))
