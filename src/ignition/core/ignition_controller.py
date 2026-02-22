from __future__ import annotations

import datetime
import json
import logging
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import psutil

from ignition.core.app_launcher import launch_executable
from ignition.core.config_store import ConfigStore
from ignition.core.iracing_monitor import IRacingMonitor
from ignition.core.models import ManagedApp, Profile
from ignition.core.process_killer import (
    graceful_terminate_process,
    graceful_terminate_process_tree,
)
from ignition.core.process_utils import any_process_name_running

logger = logging.getLogger(__name__)

_MAX_LOG = 200

@dataclass
class RunningApp:
    app: ManagedApp
    pid: int
    started_at_monotonic: float

class IgnitionController:
    def __init__(self, config_store: ConfigStore) -> None:
        self._config_store = config_store
        self._lock = threading.RLock()
        self._running: dict[str, RunningApp] = {}
        self._iracing_running = False

        # Pause / monitoring-suspend state
        self._paused = False

        # Activity log
        self._log: list[dict] = []
        self._log_seq = 0
        self._log_lock = threading.Lock()

        # Session history
        self._session_history: list[dict] = []
        self._curr_session_start: datetime.datetime | None = None
        self._curr_session_apps: list[str] = []
        self._history_lock = threading.Lock()
        self._load_session_history()

        # Watchdog (crash-restart)
        self._watchdog_stop: threading.Event | None = None
        self._restart_counts: dict[str, int] = {}

        self._monitor = IRacingMonitor(
            get_trigger_process_names=self._get_trigger_process_names,
            get_poll_interval_seconds=lambda: self._config_store.config.poll_interval_seconds,
            on_iracing_started=self._on_iracing_started,
            on_iracing_stopped=self._on_iracing_stopped,
        )

    def get_session_start_at(self) -> str | None:
        with self._lock:
            if self._curr_session_start is None:
                return None
            return self._curr_session_start.isoformat(timespec="seconds")

    def get_status(self) -> tuple[bool, int]:
        with self._lock:
            return self._iracing_running, len(self._running)

    def get_running_app_ids(self) -> list[str]:
        with self._lock:
            return list(self._running.keys())

    def is_paused(self) -> bool:
        return self._paused

    def get_session_type(self) -> str | None:
        try:
            if any_process_name_running(["iRacingSim64DX11.exe"]):
                return "race"
            if any_process_name_running(["iRacingUI.exe"]):
                return "service"
        except Exception:
            pass
        return None

    def pause(self) -> None:
        self._paused = True
        self._log_event("paused", None, "Monitoring paused")

    def resume(self) -> None:
        self._paused = False
        self._log_event("resumed", None, "Monitoring resumed")

    def get_log_since(self, seq: int) -> list[dict]:
        with self._log_lock:
            return [e for e in self._log if e["seq"] >= seq]

    def clear_log(self) -> None:
        with self._log_lock:
            self._log.clear()

    def get_session_history(self) -> list[dict]:
        with self._history_lock:
            return list(reversed(self._session_history))

    def clear_session_history(self) -> None:
        with self._history_lock:
            self._session_history.clear()
        self._save_session_history()

    def _load_session_history(self) -> None:
        path = self._history_file()
        if path is None or not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                self._session_history = data[-50:]
        except Exception:
            pass

    def _save_session_history(self) -> None:
        path = self._history_file()
        if path is None:
            return
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(self._session_history[-50:], indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            pass

    def _history_file(self) -> Path | None:
        try:
            return self._config_store.paths.session_history_file
        except Exception:
            return None

    @staticmethod
    def _send_windows_toast(title: str, body: str) -> None:
        t = title.replace("'", "''")
        b = body.replace("'", "''")
        ps = (
            "$xml=[Windows.Data.Xml.Dom.XmlDocument,Windows.Data.Xml.Dom.XmlDocument,"
            "ContentType=WindowsRuntime]::new();"
            "$xml.LoadXml('<toast><visual><binding template=\"ToastGeneric\">"
            f"<text>{t}</text><text>{b}</text>"
            "</binding></visual></toast>');"
            "[Windows.UI.Notifications.ToastNotificationManager,"
            "Windows.UI.Notifications,ContentType=WindowsRuntime]"
            "::CreateToastNotifier('iGnition').Show("
            "[Windows.UI.Notifications.ToastNotification,"
            "Windows.UI.Notifications,ContentType=WindowsRuntime]::new($xml))"
        )
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                capture_output=True, timeout=6,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except Exception:
            pass

    def _log_event(self, event_type: str, app_name: str | None, message: str) -> None:
        with self._log_lock:
            entry = {
                "seq":  self._log_seq,
                "time": datetime.datetime.now().strftime("%H:%M:%S"),
                "type": event_type,
                "app":  app_name,
                "msg":  message,
            }
            self._log.append(entry)
            self._log_seq += 1
            if len(self._log) > _MAX_LOG:
                self._log = self._log[-_MAX_LOG:]

    def start(self) -> None:
        self._monitor.start()

    def stop(self) -> None:
        self._monitor.stop()
        self._stop_all_managed(reason="shutdown")

    def start_app_now(self, *, app_id: str) -> None:
        app = self._find_app(app_id)
        if app is None:
            raise KeyError(app_id)
        self._start_app(app)

    def stop_app_now(self, *, app_id: str) -> None:
        with self._lock:
            running = self._running.get(app_id)
        if running is None:
            return
        self._terminate(running)
        with self._lock:
            self._running.pop(app_id, None)

    def _get_active_profile(self) -> Profile:
        cfg = self._config_store.config
        return next((p for p in cfg.profiles if p.profile_id == cfg.active_profile_id), cfg.profiles[0])

    def _get_trigger_process_names(self) -> list[str]:
        if self._paused:
            return []
        profile = self._get_active_profile()
        if not profile.enabled:
            return []
        return list(profile.trigger_process_names)

    def _watchdog_loop(self, stop: threading.Event) -> None:
        while not stop.wait(2.0):
            with self._lock:
                if not self._iracing_running:
                    break
                items = list(self._running.items())
            for app_id, running in items:
                is_alive = True
                try:
                    proc = psutil.Process(running.pid)
                    if not proc.is_running() or proc.status() == psutil.STATUS_ZOMBIE:
                        is_alive = False
                except psutil.NoSuchProcess:
                    is_alive = False
                if not is_alive:
                    with self._lock:
                        if app_id not in self._running:
                            continue
                        self._running.pop(app_id, None)
                    if not running.app.restart_on_crash:
                        self._log_event(
                            "error", running.app.name,
                            f"Process exited unexpectedly (pid {running.pid})",
                        )
                        continue
                    count = self._restart_counts.get(app_id, 0)
                    max_a = max(1, int(running.app.max_restart_attempts))
                    if count >= max_a:
                        self._log_event(
                            "error", running.app.name,
                            f"Crashed — max restarts ({max_a}) reached",
                        )
                        continue
                    self._restart_counts[app_id] = count + 1
                    self._log_event(
                        "launch", running.app.name,
                        f"Crashed — restarting (attempt {count + 1}/{max_a})",
                    )
                    threading.Thread(
                        target=self._start_app, args=(running.app,), daemon=True
                    ).start()

    def _on_iracing_started(self) -> None:
        with self._lock:
            self._iracing_running = True

        if self._paused:
            self._log_event("skipped", None, "iRacing detected — skipped (monitoring paused)")
            return

        profile = self._get_active_profile()
        if not profile.enabled:
            return

        self._log_event("iracing_start", None, "iRacing detected — starting apps")
        logger.info("iRacing detected: start sequence")

        with self._lock:
            self._curr_session_start = datetime.datetime.now()
            self._curr_session_apps = []

        self._restart_counts.clear()

        for app in list(profile.apps):
            with self._lock:
                if not self._iracing_running:
                    break
            if not app.enabled:
                self._log_event("skipped", app.name, "Skipped (app disabled)")
                continue
            if app.start_delay_seconds > 0:
                time.sleep(float(app.start_delay_seconds))
                with self._lock:
                    if not self._iracing_running:
                        break
            self._start_app(app)

        stop = threading.Event()
        self._watchdog_stop = stop
        threading.Thread(
            target=self._watchdog_loop, args=(stop,), name="watchdog", daemon=True
        ).start()

        with self._lock:
            launched = len(self._curr_session_apps)
        if launched > 0:
            notification_mode = self._config_store.config.notification_mode
            if notification_mode != "never":
                msg = f"{launched} app{'s' if launched != 1 else ''} launched"
                threading.Thread(
                    target=self._send_windows_toast,
                    args=("iGnition – Session started", msg),
                    daemon=True,
                ).start()

    def _on_iracing_stopped(self) -> None:
        with self._lock:
            self._iracing_running = False
            session_start = self._curr_session_start
            session_apps = list(self._curr_session_apps)
            self._curr_session_start = None
            self._curr_session_apps = []
        if self._watchdog_stop is not None:
            self._watchdog_stop.set()
            self._watchdog_stop = None
        self._log_event("iracing_stop", None, "iRacing closed — stopping apps")
        logger.info("iRacing closed: stop sequence")
        self._stop_all_managed(reason="iracing-exit")

        if session_start is not None:
            ended = datetime.datetime.now()
            duration = (ended - session_start).total_seconds()
            profile = self._get_active_profile()
            entry = {
                "started_at": session_start.isoformat(timespec="seconds"),
                "ended_at": ended.isoformat(timespec="seconds"),
                "duration_seconds": round(duration),
                "profile_name": profile.name,
                "profile_id": profile.profile_id,
                "apps_launched": session_apps,
            }
            with self._history_lock:
                self._session_history.append(entry)
                if len(self._session_history) > 50:
                    self._session_history = self._session_history[-50:]
            self._save_session_history()

    def _start_app(self, app: ManagedApp) -> None:
        with self._lock:
            if app.app_id in self._running:
                return

        if app.wait_for_process:
            timeout = max(float(app.wait_timeout_seconds or 30.0), 1.0)
            deadline = time.monotonic() + timeout
            self._log_event("skipped", app.name, f"Waiting for {app.wait_for_process}…")
            while time.monotonic() < deadline:
                with self._lock:
                    if not self._iracing_running:
                        return
                if any_process_name_running([app.wait_for_process]):
                    break
                time.sleep(0.5)
            else:
                self._log_event("error", app.name, f"Timed out waiting for {app.wait_for_process}")
                logger.warning("Timeout waiting for %s before %s", app.wait_for_process, app.name)
                return

        try:
            result = launch_executable(
                executable_path=app.executable_path,
                arguments=app.arguments,
                working_directory=app.working_directory,
                start_minimized=app.start_minimized,
                allow_if_already_running=app.start_if_already_running,
            )
        except Exception as exc:
            self._log_event("error", app.name, f"Launch failed: {exc}")
            logger.error("Failed to start %s: %s", app.name, exc)
            return

        if result is None:
            self._log_event("skipped", app.name, "Skipped (already running)")
            logger.info("Skipped (already running): %s", app.name)
            return

        running = RunningApp(app=app, pid=result.pid, started_at_monotonic=time.monotonic())
        with self._lock:
            self._running[app.app_id] = running
            self._curr_session_apps.append(app.name)
        self._log_event("launch", app.name, f"Started (pid {result.pid})")
        logger.info("Started: %s (pid=%s)", app.name, result.pid)

    def _stop_all_managed(self, *, reason: str) -> None:
        with self._lock:
            running_apps = list(self._running.values())
            self._running.clear()

        for running in running_apps:
            if not running.app.kill_on_iracing_exit and reason == "iracing-exit":
                continue
            try:
                self._terminate(running)
                self._log_event("stop", running.app.name, f"Stopped (pid {running.pid})")
                logger.info("Stopped: %s (pid=%s)", running.app.name, running.pid)
            except Exception:
                self._log_event("error", running.app.name, "Failed to stop")
                logger.exception("Failed to stop: %s (pid=%s)", running.app.name, running.pid)

    @staticmethod
    def _terminate(running: RunningApp) -> None:
        grace = float(running.app.shutdown_grace_seconds or 0.0)
        if running.app.kill_process_tree:
            graceful_terminate_process_tree(running.pid, grace)
        else:
            graceful_terminate_process(running.pid, grace)

    def _find_app(self, app_id: str) -> ManagedApp | None:
        profile = self._get_active_profile()
        return next((a for a in profile.apps if a.app_id == app_id), None)
