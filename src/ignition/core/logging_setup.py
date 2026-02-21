import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys


def configure_logging(*, log_dir: Path) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "ignition.log"

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    for handler in list(root.handlers):
        root.removeHandler(handler)

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")

    try:
        file_handler = RotatingFileHandler(
            filename=str(log_file),
            maxBytes=1_000_000,
            backupCount=3,
            encoding="utf-8",
            delay=True,
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
    except OSError:
        root.addHandler(logging.NullHandler())

    if _stderr_usable():
        stream_handler = logging.StreamHandler(stream=sys.stderr)
        stream_handler.setFormatter(formatter)
        root.addHandler(stream_handler)

    logging.raiseExceptions = False


def _stderr_usable() -> bool:
    err = getattr(sys, "stderr", None)
    if err is None:
        return False
    try:
        err.fileno()
    except Exception:
        return False
    return True
