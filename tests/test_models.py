"""Tests for core data models (ManagedApp, Profile, AppConfig)."""
import pytest

from ignition.core.models import AppConfig, ManagedApp, Profile


class TestManagedApp:
    def test_create_sets_app_id(self):
        app = ManagedApp.create(name="SimHub", executable_path=r"C:\SimHub.exe")
        assert app.app_id
        assert app.name == "SimHub"
        assert app.executable_path == r"C:\SimHub.exe"

    def test_to_dict_roundtrip(self):
        app = ManagedApp.create(name="SimHub", executable_path=r"C:\SimHub.exe")
        app2 = ManagedApp.from_dict(app.to_dict())
        assert app2.app_id == app.app_id
        assert app2.name == app.name
        assert app2.executable_path == app.executable_path

    def test_from_dict_defaults(self):
        app = ManagedApp.from_dict({"app_id": "x", "name": "A", "executable_path": "B"})
        assert app.enabled is True
        assert app.kill_on_iracing_exit is True
        assert app.kill_process_tree is True
        assert app.start_minimized is False
        assert app.start_delay_seconds == 0.0

    def test_from_dict_preserves_kill_on_exit_false(self):
        app = ManagedApp.from_dict({
            "app_id": "x", "name": "A", "executable_path": "B",
            "kill_on_iracing_exit": False,
        })
        assert app.kill_on_iracing_exit is False

    def test_from_dict_generates_app_id_if_missing(self):
        app = ManagedApp.from_dict({"name": "A", "executable_path": "B"})
        assert app.app_id  # should be a generated UUID


class TestProfile:
    def test_create_default(self):
        p = Profile.create_default()
        assert p.name == "Default"
        assert p.enabled is True
        assert len(p.trigger_process_names) > 0
        assert p.profile_id

    def test_to_dict_roundtrip(self):
        p = Profile.create_default()
        p2 = Profile.from_dict(p.to_dict())
        assert p2.profile_id == p.profile_id
        assert p2.name == p.name
        assert p2.trigger_process_names == p.trigger_process_names

    def test_from_dict_with_apps(self):
        app = ManagedApp.create(name="X", executable_path="X.exe")
        p = Profile.create_default()
        p.apps = [app]
        p2 = Profile.from_dict(p.to_dict())
        assert len(p2.apps) == 1
        assert p2.apps[0].name == "X"

    def test_from_dict_ignores_invalid_app_entries(self):
        raw = Profile.create_default().to_dict()
        raw["apps"] = ["not-a-dict", None, {"name": "A", "executable_path": "B"}]
        p = Profile.from_dict(raw)
        assert len(p.apps) == 1


class TestAppConfig:
    def test_default(self):
        cfg = AppConfig.default()
        assert len(cfg.profiles) == 1
        assert cfg.active_profile_id == cfg.profiles[0].profile_id
        assert cfg.poll_interval_seconds == 1.0
        assert cfg.minimize_to_tray is True

    def test_to_dict_roundtrip(self):
        cfg = AppConfig.default()
        cfg2 = AppConfig.from_dict(cfg.to_dict())
        assert cfg2.active_profile_id == cfg.active_profile_id
        assert len(cfg2.profiles) == len(cfg.profiles)
        assert cfg2.trigger_mode == cfg.trigger_mode

    def test_from_dict_invalid_active_profile_falls_back(self):
        raw = AppConfig.default().to_dict()
        raw["active_profile_id"] = "nonexistent-id"
        cfg = AppConfig.from_dict(raw)
        assert cfg.active_profile_id == cfg.profiles[0].profile_id

    def test_from_dict_empty_profiles_creates_default(self):
        raw = AppConfig.default().to_dict()
        raw["profiles"] = []
        cfg = AppConfig.from_dict(raw)
        assert len(cfg.profiles) == 1

    def test_from_dict_preserves_trigger_mode(self):
        raw = AppConfig.default().to_dict()
        raw["trigger_mode"] = "race"
        cfg = AppConfig.from_dict(raw)
        assert cfg.trigger_mode == "race"
