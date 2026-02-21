import psutil


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
