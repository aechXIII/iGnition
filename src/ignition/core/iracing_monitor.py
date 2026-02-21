from __future__ import annotations

import logging
import threading
import time
from typing import Callable

from ignition.core.process_utils import any_process_name_running


logger = logging.getLogger(__name__)


class IRacingMonitor:
    def __init__(
        self,
        *,
        get_trigger_process_names: Callable[[], list[str]],
        get_poll_interval_seconds: Callable[[], float],
        on_iracing_started: Callable[[], None],
        on_iracing_stopped: Callable[[], None],
    ) -> None:
        self._get_trigger_process_names = get_trigger_process_names
        self._get_poll_interval_seconds = get_poll_interval_seconds
        self._on_iracing_started = on_iracing_started
        self._on_iracing_stopped = on_iracing_stopped

        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._was_running = False

    def start(self) -> None:
        if self._thread is not None:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="iracing-monitor", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is None:
            return
        self._thread.join(timeout=3.0)
        self._thread = None

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                running = any_process_name_running(self._get_trigger_process_names())
            except Exception:
                logger.exception("Process scan failed")
                running = False

            if running and not self._was_running:
                self._was_running = True
                try:
                    threading.Thread(
                        target=self._on_iracing_started,
                        daemon=True,
                        name="iracing-start",
                    ).start()
                except Exception:
                    logger.exception("on_iracing_started handler failed")
            elif not running and self._was_running:
                self._was_running = False
                try:
                    threading.Thread(
                        target=self._on_iracing_stopped,
                        daemon=True,
                        name="iracing-stop",
                    ).start()
                except Exception:
                    logger.exception("on_iracing_stopped handler failed")

            try:
                interval = float(self._get_poll_interval_seconds())
            except Exception:
                interval = 1.0
            time.sleep(max(0.25, interval))
