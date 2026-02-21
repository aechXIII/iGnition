from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4


@dataclass
class ManagedApp:
    app_id: str
    name: str
    executable_path: str
    arguments: str = ""
    working_directory: str = ""
    start_delay_seconds: float = 0.0
    start_minimized: bool = False
    start_if_already_running: bool = False
    kill_on_iracing_exit: bool = True
    kill_process_tree: bool = True
    enabled: bool = True
    wait_for_process: str = ""
    wait_timeout_seconds: float = 30.0

    @classmethod
    def create(cls, *, name: str, executable_path: str) -> "ManagedApp":
        return cls(app_id=str(uuid4()), name=name, executable_path=executable_path)

    def to_dict(self) -> dict[str, Any]:
        return {
            "app_id": self.app_id,
            "name": self.name,
            "executable_path": self.executable_path,
            "arguments": self.arguments,
            "working_directory": self.working_directory,
            "start_delay_seconds": self.start_delay_seconds,
            "start_minimized": self.start_minimized,
            "start_if_already_running": self.start_if_already_running,
            "kill_on_iracing_exit": self.kill_on_iracing_exit,
            "kill_process_tree": self.kill_process_tree,
            "enabled": self.enabled,
            "wait_for_process": self.wait_for_process,
            "wait_timeout_seconds": self.wait_timeout_seconds,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ManagedApp":
        return cls(
            app_id=str(raw.get("app_id") or uuid4()),
            name=str(raw.get("name") or ""),
            executable_path=str(raw.get("executable_path") or ""),
            arguments=str(raw.get("arguments") or ""),
            working_directory=str(raw.get("working_directory") or ""),
            start_delay_seconds=float(raw.get("start_delay_seconds") or 0.0),
            start_minimized=bool(raw.get("start_minimized") or False),
            start_if_already_running=bool(raw.get("start_if_already_running") or False),
            kill_on_iracing_exit=bool(raw.get("kill_on_iracing_exit", True)),
            kill_process_tree=bool(raw.get("kill_process_tree", True)),
            enabled=bool(raw.get("enabled", True)),
            wait_for_process=str(raw.get("wait_for_process") or ""),
            wait_timeout_seconds=float(raw.get("wait_timeout_seconds") or 30.0),
        )


@dataclass
class Profile:
    profile_id: str
    name: str
    enabled: bool = True
    trigger_process_names: list[str] = field(default_factory=list)
    apps: list[ManagedApp] = field(default_factory=list)
    color: str = ""

    @classmethod
    def create_default(cls) -> "Profile":
        return cls(
            profile_id=str(uuid4()),
            name="Default",
            enabled=True,
            trigger_process_names=["iRacingSim64DX11.exe", "iRacingUI.exe"],
            apps=[],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "name": self.name,
            "enabled": self.enabled,
            "trigger_process_names": list(self.trigger_process_names),
            "apps": [a.to_dict() for a in self.apps],
            "color": self.color,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "Profile":
        apps_raw = raw.get("apps") or []
        return cls(
            profile_id=str(raw.get("profile_id") or uuid4()),
            name=str(raw.get("name") or "Default"),
            enabled=bool(raw.get("enabled", True)),
            trigger_process_names=[str(x) for x in (raw.get("trigger_process_names") or [])],
            apps=[ManagedApp.from_dict(x) for x in apps_raw if isinstance(x, dict)],
            color=str(raw.get("color") or ""),
        )


@dataclass
class AppConfig:
    schema_version: int
    active_profile_id: str
    profiles: list[Profile]
    poll_interval_seconds: float = 1.0
    minimize_to_tray: bool = True
    iracing_exe_path: str = ""
    trigger_mode: str = "ui"  # "ui" = iRacingUI.exe, "race" = iRacingSim64DX11.exe

    @classmethod
    def default(cls) -> "AppConfig":
        default_profile = Profile.create_default()
        return cls(
            schema_version=1,
            active_profile_id=default_profile.profile_id,
            profiles=[default_profile],
            poll_interval_seconds=1.0,
            minimize_to_tray=True,
            iracing_exe_path="",
            trigger_mode="ui",
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "active_profile_id": self.active_profile_id,
            "profiles": [p.to_dict() for p in self.profiles],
            "poll_interval_seconds": self.poll_interval_seconds,
            "minimize_to_tray": self.minimize_to_tray,
            "iracing_exe_path": self.iracing_exe_path,
            "trigger_mode": self.trigger_mode,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "AppConfig":
        profiles_raw = raw.get("profiles") or []
        profiles = [Profile.from_dict(x) for x in profiles_raw if isinstance(x, dict)]
        if not profiles:
            profiles = [Profile.create_default()]
        active_profile_id = str(raw.get("active_profile_id") or profiles[0].profile_id)
        profile_ids = {p.profile_id for p in profiles}
        if active_profile_id not in profile_ids:
            active_profile_id = profiles[0].profile_id
        return cls(
            schema_version=int(raw.get("schema_version") or 1),
            active_profile_id=active_profile_id,
            profiles=profiles,
            poll_interval_seconds=float(raw.get("poll_interval_seconds") or 1.0),
            minimize_to_tray=bool(raw.get("minimize_to_tray", True)),
            iracing_exe_path=str(raw.get("iracing_exe_path") or ""),
            trigger_mode=str(raw.get("trigger_mode") or "ui"),
        )
