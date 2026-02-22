from __future__ import annotations

import copy
import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

import webview

from ignition.core.app_launcher import launch_executable
from ignition.core.models import ManagedApp, Profile
from ignition.core.state import AppState
from ignition.core.windows_autostart import WindowsAutostart

logger = logging.getLogger(__name__)


class IgnitionApi:
    """JS-to-Python bridge exposed via window.pywebview.api."""

    def __init__(self, *, state: AppState, window: webview.Window | None = None) -> None:
        self._state = state
        self._autostart = WindowsAutostart(app_name="iGnition")
        self._window: webview.Window | None = window
        self._icon_cache: dict[str, str | None] = {}
        self._icon_cache_path = state.config_store.paths.config_dir / "icon-cache.json"
        self._load_icon_cache()
        self._on_profiles_changed: Callable[[], None] | None = None
        self._force_quit_setter: Callable[[], None] | None = None

    def bind_profiles_changed(self, cb: Callable[[], None]) -> None:
        self._on_profiles_changed = cb

    def bind_force_quit(self, setter: Callable[[], None]) -> None:
        self._force_quit_setter = setter

    def _notify_profiles_changed(self) -> None:
        if self._on_profiles_changed is not None:
            try:
                self._on_profiles_changed()
            except Exception:
                pass

    def _load_icon_cache(self) -> None:
        try:
            if self._icon_cache_path.exists():
                data = json.loads(self._icon_cache_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self._icon_cache = {k: v for k, v in data.items()}
        except Exception:
            pass

    def _save_icon_cache(self) -> None:
        try:
            self._icon_cache_path.parent.mkdir(parents=True, exist_ok=True)
            self._icon_cache_path.write_text(
                json.dumps(self._icon_cache, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            pass

    def bind_window(self, window: webview.Window) -> None:
        self._window = window

    def get_status(self) -> dict[str, Any]:
        iracing_running, managed_count = self._state.controller.get_status()
        paused = self._state.controller.is_paused()
        session_type = self._state.controller.get_session_type() if iracing_running else None
        running_app_ids = self._state.controller.get_running_app_ids()
        session_start_at = self._state.controller.get_session_start_at()
        return {
            "iracing_running": iracing_running,
            "managed_count": managed_count,
            "paused": paused,
            "session_type": session_type,
            "running_app_ids": running_app_ids,
            "session_start_at": session_start_at,
        }

    def get_profiles(self) -> list[dict[str, Any]]:
        cfg = self._state.config_store.config
        result = []
        for profile in cfg.profiles:
            d = profile.to_dict()
            d["is_active"] = profile.profile_id == cfg.active_profile_id
            d["app_count"] = len(profile.apps)
            result.append(d)
        return result

    def get_active_profile_name(self) -> str:
        return self._active_profile().name

    def add_profile(self, name: str) -> dict[str, Any]:
        name = name.strip()
        if not name:
            return {"ok": False, "error": "Name is required."}
        profile = Profile.create_default()
        profile.name = name
        profile.apps = []
        self._state.config_store.config.profiles.append(profile)
        self._state.config_store.save()
        self._notify_profiles_changed()
        return {"ok": True, "profile_id": profile.profile_id}

    def remove_profile(self, profile_id: str) -> dict[str, Any]:
        cfg = self._state.config_store.config
        if len(cfg.profiles) == 1:
            return {"ok": False, "error": "At least one profile must remain."}
        cfg.profiles = [p for p in cfg.profiles if p.profile_id != profile_id]
        if cfg.active_profile_id == profile_id:
            cfg.active_profile_id = cfg.profiles[0].profile_id
        self._state.config_store.save()
        self._notify_profiles_changed()
        return {"ok": True}

    def duplicate_profile(self, profile_id: str) -> dict[str, Any]:
        cfg = self._state.config_store.config
        source = next((p for p in cfg.profiles if p.profile_id == profile_id), None)
        if source is None:
            return {"ok": False, "error": "Profile not found."}
        new_profile = copy.deepcopy(source)
        new_profile.profile_id = str(uuid4())
        new_profile.name = source.name + " (copy)"
        for app in new_profile.apps:
            app.app_id = str(uuid4())
        cfg.profiles.append(new_profile)
        self._state.config_store.save()
        self._notify_profiles_changed()
        return {"ok": True, "profile_id": new_profile.profile_id}

    def set_active_profile(self, profile_id: str) -> dict[str, Any]:
        cfg = self._state.config_store.config
        if not any(p.profile_id == profile_id for p in cfg.profiles):
            return {"ok": False, "error": "Profile not found."}
        cfg.active_profile_id = profile_id
        self._state.config_store.save()
        self._notify_profiles_changed()
        return {"ok": True}

    def set_profile_triggers(self, profile_id: str, triggers_csv: str) -> dict[str, Any]:
        items = [x.strip() for x in triggers_csv.split(",") if x.strip()]
        if not items:
            return {"ok": False, "error": "At least one trigger process name is required."}
        cfg = self._state.config_store.config
        profile = next((p for p in cfg.profiles if p.profile_id == profile_id), None)
        if profile is None:
            return {"ok": False, "error": "Profile not found."}
        profile.trigger_process_names = items
        profile.trigger_mode = "custom"
        self._state.config_store.save()
        return {"ok": True}

    def set_profile_trigger_mode(self, profile_id: str, mode: str) -> dict[str, Any]:
        if mode not in ("ui", "race"):
            return {"ok": False, "error": "Invalid mode."}
        cfg = self._state.config_store.config
        profile = next((p for p in cfg.profiles if p.profile_id == profile_id), None)
        if profile is None:
            return {"ok": False, "error": "Profile not found."}
        profile.trigger_mode = mode
        profile.trigger_process_names = (
            ["iRacingUI.exe"] if mode == "ui" else ["iRacingSim64DX11.exe"]
        )
        self._state.config_store.save()
        return {"ok": True}

    def rename_profile(self, profile_id: str, name: str) -> dict[str, Any]:
        name = name.strip()
        if not name:
            return {"ok": False, "error": "Name is required."}
        cfg = self._state.config_store.config
        profile = next((p for p in cfg.profiles if p.profile_id == profile_id), None)
        if profile is None:
            return {"ok": False, "error": "Profile not found."}
        profile.name = name
        self._state.config_store.save()
        self._notify_profiles_changed()
        return {"ok": True}

    def set_profile_color(self, profile_id: str, color: str) -> dict[str, Any]:
        cfg = self._state.config_store.config
        profile = next((p for p in cfg.profiles if p.profile_id == profile_id), None)
        if profile is None:
            return {"ok": False, "error": "Profile not found."}
        profile.color = str(color or "")
        self._state.config_store.save()
        return {"ok": True}

    def toggle_profile_enabled(self, profile_id: str) -> dict[str, Any]:
        cfg = self._state.config_store.config
        profile = next((p for p in cfg.profiles if p.profile_id == profile_id), None)
        if profile is None:
            return {"ok": False, "error": "Profile not found."}
        profile.enabled = not profile.enabled
        self._state.config_store.save()
        return {"ok": True, "enabled": profile.enabled}

    def get_apps(self) -> list[dict[str, Any]]:
        return [a.to_dict() for a in self._active_profile().apps]

    def add_app(self, app_json: str) -> dict[str, Any]:
        try:
            raw = json.loads(app_json)
        except json.JSONDecodeError as exc:
            return {"ok": False, "error": str(exc)}

        exe = str(raw.get("executable_path") or "").strip()
        name = str(raw.get("name") or "").strip()
        if not exe:
            return {"ok": False, "error": "Executable path is required."}
        if not name:
            return {"ok": False, "error": "Name is required."}

        app = ManagedApp.from_dict({**raw, "app_id": str(uuid4())})
        self._active_profile().apps.append(app)
        self._state.config_store.save()
        return {"ok": True, "app_id": app.app_id}

    def edit_app(self, app_json: str) -> dict[str, Any]:
        try:
            raw = json.loads(app_json)
        except json.JSONDecodeError as exc:
            return {"ok": False, "error": str(exc)}

        app_id = str(raw.get("app_id") or "")
        if not app_id:
            return {"ok": False, "error": "app_id is required."}

        profile = self._active_profile()
        idx = next((i for i, a in enumerate(profile.apps) if a.app_id == app_id), None)
        if idx is None:
            return {"ok": False, "error": "App not found."}

        profile.apps[idx] = ManagedApp.from_dict(raw)
        self._state.config_store.save()
        return {"ok": True}

    def remove_app(self, app_id: str) -> dict[str, Any]:
        profile = self._active_profile()
        before = len(profile.apps)
        profile.apps = [a for a in profile.apps if a.app_id != app_id]
        self._state.config_store.save()
        return {"ok": len(profile.apps) < before}

    def undo_remove_app(self, app_json: str, position: int) -> dict[str, Any]:
        try:
            raw = json.loads(app_json)
        except json.JSONDecodeError as exc:
            return {"ok": False, "error": str(exc)}
        app = ManagedApp.from_dict(raw)
        profile = self._active_profile()
        pos = max(0, min(int(position), len(profile.apps)))
        profile.apps.insert(pos, app)
        self._state.config_store.save()
        return {"ok": True}

    def reorder_apps(self, ordered_ids_json: str) -> dict[str, Any]:
        try:
            ordered_ids: list[str] = json.loads(ordered_ids_json)
        except json.JSONDecodeError as exc:
            return {"ok": False, "error": str(exc)}

        profile = self._active_profile()
        id_to_app = {a.app_id: a for a in profile.apps}
        profile.apps = [id_to_app[i] for i in ordered_ids if i in id_to_app]
        self._state.config_store.save()
        return {"ok": True}

    def toggle_app_enabled(self, app_id: str) -> dict[str, Any]:
        profile = self._active_profile()
        app = next((a for a in profile.apps if a.app_id == app_id), None)
        if app is None:
            return {"ok": False, "error": "App not found."}
        app.enabled = not app.enabled
        self._state.config_store.save()
        return {"ok": True, "enabled": app.enabled}

    def test_launch_app(self, app_id: str) -> dict[str, Any]:
        profile = self._active_profile()
        app = next((a for a in profile.apps if a.app_id == app_id), None)
        if app is None:
            return {"ok": False, "error": "App not found."}
        try:
            result = launch_executable(
                executable_path=app.executable_path,
                arguments=app.arguments,
                working_directory=app.working_directory,
                start_minimized=app.start_minimized,
                allow_if_already_running=True,  # always allow for test launch
            )
            pid = result.pid if result else None
            return {"ok": True, "pid": pid}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def get_profile_apps(self, profile_id: str) -> list[dict[str, Any]]:
        cfg = self._state.config_store.config
        profile = next((p for p in cfg.profiles if p.profile_id == profile_id), None)
        if profile is None:
            return []
        return [a.to_dict() for a in profile.apps]

    def start_app(self, app_id: str) -> dict[str, Any]:
        try:
            self._state.controller.start_app_now(app_id=app_id)
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def stop_app(self, app_id: str) -> dict[str, Any]:
        try:
            self._state.controller.stop_app_now(app_id=app_id)
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def get_monitoring_paused(self) -> bool:
        return self._state.controller.is_paused()

    def set_monitoring_paused(self, paused: bool) -> dict[str, Any]:
        if paused:
            self._state.controller.pause()
        else:
            self._state.controller.resume()
        return {"ok": True, "paused": paused}

    def get_log_since(self, seq: int) -> list[dict]:
        return self._state.controller.get_log_since(seq)

    def clear_log(self) -> dict[str, Any]:
        self._state.controller.clear_log()
        return {"ok": True}

    def get_session_history(self) -> list[dict]:
        return self._state.controller.get_session_history()

    def clear_session_history(self) -> dict[str, Any]:
        self._state.controller.clear_session_history()
        return {"ok": True}

    def get_common_apps(self) -> list[dict[str, Any]]:
        candidates = [
            {"name": "SimHub", "paths": [
                r"%LOCALAPPDATA%\SimHub\SimHub.exe",
                r"C:\Program Files (x86)\SimHub\SimHub.exe",
            ]},
            {"name": "CrewChief", "paths": [
                r"%LOCALAPPDATA%\CrewChiefV4\CrewChiefV4.exe",
                r"C:\Program Files (x86)\CrewChief\CrewChiefV4.exe",
            ]},
            {"name": "JoyToKey", "paths": [
                r"C:\Program Files (x86)\JoyToKey\JoyToKey.exe",
                r"%ProgramFiles%\JoyToKey\JoyToKey.exe",
            ]},
            {"name": "TrackIR", "paths": [
                r"C:\Program Files (x86)\NaturalPoint\TrackIR 5\TrackIR5.exe",
                r"%ProgramFiles%\NaturalPoint\SmartNav3\TrackIR.exe",
            ]},
            {"name": "VoiceAttack", "paths": [
                r"C:\Program Files (x86)\VoiceAttack\VoiceAttack.exe",
                r"%ProgramFiles(x86)%\VoiceAttack\VoiceAttack.exe",
            ]},
            {"name": "MoTeC i2", "paths": [
                r"C:\Program Files (x86)\MoTeC\i2 Pro\I2Pro.exe",
                r"C:\Program Files\MoTeC\i2 Pro\I2Pro.exe",
            ]},
            {"name": "RaceLab Apps", "paths": [
                r"%LOCALAPPDATA%\RaceLabApps\RaceLabApps.exe",
            ]},
            {"name": "Sim Commander", "paths": [
                r"C:\Program Files\Next Level Racing\Sim Commander 4\Sim Commander 4.exe",
            ]},
            {"name": "Fanatec Control Panel", "paths": [
                r"C:\Program Files\Fanatec\Fanatec Software\FanatecApp.exe",
                r"C:\Program Files (x86)\Fanatec\FanatecApp.exe",
            ]},
            {"name": "OBS Studio", "paths": [
                r"C:\Program Files\obs-studio\bin\64bit\obs64.exe",
                r"C:\Program Files (x86)\obs-studio\bin\64bit\obs64.exe",
            ]},
            {"name": "Logitech G HUB", "paths": [
                r"%LOCALAPPDATA%\LGHUB\lghub.exe",
                r"C:\Program Files\LGHUB\lghub.exe",
            ]},
            {"name": "RTSS (RivaTuner Statistics Server)", "paths": [
                r"C:\Program Files (x86)\RivaTuner Statistics Server\RTSS.exe",
            ]},
            {"name": "Helicorsa", "paths": [
                r"%LOCALAPPDATA%\Helicorsa\Helicorsa.exe",
                r"C:\Program Files\Helicorsa\Helicorsa.exe",
            ]},
            {"name": "Sim Dashboard Server", "paths": [
                r"%LOCALAPPDATA%\Sim Dashboard Server\Sim Dashboard Server.exe",
                r"C:\Program Files (x86)\Sim Dashboard Server\Sim Dashboard Server.exe",
            ]},
            {"name": "Garage 61", "paths": [
                r"%LOCALAPPDATA%\Garage61\garage61.exe",
                r"C:\Program Files\Garage61\garage61.exe",
            ]},
            {"name": "Pitskill", "paths": [
                r"%LOCALAPPDATA%\Pitskill\Pitskill.exe",
                r"C:\Program Files\Pitskill\Pitskill.exe",
            ]},
            {"name": "SRS (Simulated Racing System)", "paths": [
                r"C:\Program Files (x86)\SRS\SRS.exe",
                r"%LOCALAPPDATA%\SRS\SRS.exe",
            ]},
        ]
        found = []
        for entry in candidates:
            for raw_path in entry["paths"]:
                expanded = os.path.expandvars(raw_path)
                if os.path.isfile(expanded):
                    found.append({"name": entry["name"], "executable_path": expanded})
                    break
        return found

    def get_app_icon(self, exe_path: str) -> str | None:
        if not exe_path or not os.path.isfile(exe_path):
            return None
        if exe_path in self._icon_cache:
            return self._icon_cache[exe_path]
        result = self._extract_exe_icon(exe_path)
        self._icon_cache[exe_path] = result
        self._save_icon_cache()
        return result

    @staticmethod
    def _extract_exe_icon(exe_path: str) -> str | None:
        escaped = exe_path.replace("'", "''")
        ps = (
            "Add-Type -AssemblyName System.Drawing; "
            f"$i=[System.Drawing.Icon]::ExtractAssociatedIcon('{escaped}'); "
            "if($i){$b=$i.ToBitmap();"
            "$m=New-Object System.IO.MemoryStream;"
            "$b.Save($m,[System.Drawing.Imaging.ImageFormat]::Png);"
            "$b.Dispose();$i.Dispose();"
            "[Convert]::ToBase64String($m.ToArray())}"
        )
        try:
            r = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
                capture_output=True, text=True, timeout=8,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            b64 = r.stdout.strip()
            if b64:
                return f"data:image/png;base64,{b64}"
        except Exception:
            pass
        return None

    def get_settings(self) -> dict[str, Any]:
        cfg = self._state.config_store.config
        return {
            "poll_interval_seconds": cfg.poll_interval_seconds,
            "minimize_to_tray": cfg.minimize_to_tray,
            "iracing_exe_path": cfg.iracing_exe_path,
            "trigger_mode": cfg.trigger_mode,
            "notification_mode": cfg.notification_mode,
        }

    def save_settings(self, settings_json: str) -> dict[str, Any]:
        try:
            raw = json.loads(settings_json)
        except json.JSONDecodeError as exc:
            return {"ok": False, "error": str(exc)}
        poll_interval = float(raw.get("poll_interval_seconds") or 1.0)
        if poll_interval <= 0:
            return {"ok": False, "error": "Poll interval must be greater than zero."}
        cfg = self._state.config_store.config
        cfg.poll_interval_seconds = poll_interval
        cfg.minimize_to_tray = bool(raw.get("minimize_to_tray", True))
        cfg.iracing_exe_path = str(raw.get("iracing_exe_path") or "").strip()
        mode = str(raw.get("trigger_mode") or "ui")
        if mode not in ("ui", "race"):
            mode = "ui"
        if mode != cfg.trigger_mode:
            _mode_defaults: dict[str, list[str]] = {
                "ui":   ["iRacingUI.exe"],
                "race": ["iRacingSim64DX11.exe"],
            }
            old_names = {x.lower() for x in _mode_defaults.get(cfg.trigger_mode, [])}
            new_names = _mode_defaults[mode]
            for profile in cfg.profiles:
                # skip profiles with custom triggers
                if {x.lower() for x in profile.trigger_process_names} == old_names:
                    profile.trigger_process_names = list(new_names)
        cfg.trigger_mode = mode
        cfg.notification_mode = str(raw.get("notification_mode") or "always")
        if cfg.notification_mode not in ("always", "never"):
            cfg.notification_mode = "always"
        self._state.config_store.save()
        return {"ok": True}

    def launch_iracing(self) -> dict[str, Any]:
        cfg = self._state.config_store.config
        path = cfg.iracing_exe_path.strip()

        # If no explicit path is configured, prefer launching through Steam.
        # This avoids the graphics-config wizard that appears when iRacingUI.exe
        # is started directly without the Steam runtime.
        if not path:
            try:
                os.startfile("steam://rungameid/266410")
                return {"ok": True}
            except Exception:
                pass  # Steam not installed or not found — fall through to direct launch

        # Fall back to direct exe (non-Steam install or user-specified path)
        if not path:
            candidates = [
                r"C:\Program Files (x86)\iRacing\iRacingUI.exe",
                r"C:\Program Files\iRacing\iRacingUI.exe",
                os.path.expandvars(r"%LOCALAPPDATA%\iRacingUI\iRacingUI.exe"),
            ]
            for c in candidates:
                if os.path.isfile(c):
                    path = c
                    break

        if not path:
            return {"ok": False, "error": "iRacing not found. Install via Steam, or set the exe path in Settings."}
        try:
            subprocess.Popen([path], cwd=str(Path(path).parent),
                             creationflags=subprocess.CREATE_NO_WINDOW)
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def browse_iracing_exe(self) -> str | None:
        if self._window is None:
            return None
        result = self._window.create_file_dialog(
            webview.OPEN_DIALOG,
            allow_multiple=False,
            file_types=("Executable (*.exe)", "All files (*.*)"),
        )
        if result and len(result) > 0:
            return result[0]
        return None

    def get_autostart_enabled(self) -> bool:
        return self._autostart.is_enabled()

    def set_autostart(self, enabled: bool) -> dict[str, Any]:
        try:
            if enabled:
                self._autostart.enable()
            else:
                self._autostart.disable()
            return {"ok": True}
        except OSError as exc:
            return {"ok": False, "error": str(exc)}

    def browse_exe(self) -> str | None:
        if self._window is None:
            return None
        result = self._window.create_file_dialog(
            webview.OPEN_DIALOG,
            allow_multiple=False,
            file_types=("Executable (*.exe)", "All files (*.*)"),
        )
        if result and len(result) > 0:
            return result[0]
        return None

    def browse_directory(self) -> str | None:
        if self._window is None:
            return None
        result = self._window.create_file_dialog(webview.FOLDER_DIALOG)
        if result and len(result) > 0:
            return result[0]
        return None

    def save_file_dialog(self, filename: str = "config.json") -> str | None:
        if self._window is None:
            return None
        result = self._window.create_file_dialog(
            webview.SAVE_DIALOG,
            save_filename=filename,
            file_types=("JSON (*.json)",),
        )
        return result if isinstance(result, str) else None

    def open_file_dialog(self) -> str | None:
        if self._window is None:
            return None
        result = self._window.create_file_dialog(
            webview.OPEN_DIALOG,
            allow_multiple=False,
            file_types=("JSON (*.json)", "All files (*.*)"),
        )
        if result and len(result) > 0:
            return result[0]
        return None

    def export_config(self, path: str) -> dict[str, Any]:
        try:
            self._state.config_store.export_to_file(Path(path))
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def import_config(self, path: str) -> dict[str, Any]:
        try:
            self._state.config_store.import_from_file(Path(path))
            self._notify_profiles_changed()
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def open_config_folder(self) -> None:
        os.startfile(str(self._state.config_store.paths.config_dir))

    def open_log_folder(self) -> None:
        os.startfile(str(self._state.config_store.paths.log_dir))

    def get_config_path(self) -> str:
        return str(self._state.config_store.paths.config_file)

    def quit_app(self) -> None:
        if self._force_quit_setter is not None:
            self._force_quit_setter()
        self._state.controller.stop()
        if self._window is not None:
            self._window.destroy()

    def _active_profile(self) -> Profile:
        cfg = self._state.config_store.config
        return next(
            (p for p in cfg.profiles if p.profile_id == cfg.active_profile_id),
            cfg.profiles[0],
        )
