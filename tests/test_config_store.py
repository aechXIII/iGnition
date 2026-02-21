"""Tests for ConfigStore — save/load/import/export."""
import json
import pathlib

import pytest

from ignition.core.config_store import ConfigStore
from ignition.core.models import AppConfig, ManagedApp, Profile
from ignition.core.paths import AppPaths


def _make_store(tmp_path: pathlib.Path) -> ConfigStore:
    paths = AppPaths(config_dir=tmp_path / "config", log_dir=tmp_path / "logs")
    paths.config_dir.mkdir(parents=True)
    config = AppConfig.default()
    ConfigStore._save_to_file(paths.config_file, config)
    return ConfigStore(paths=paths, config=config)


class TestConfigStore:
    def test_save_and_reload(self, tmp_path: pathlib.Path):
        store = _make_store(tmp_path)
        store.config.profiles[0].name = "MyProfile"
        store.save()

        raw = json.loads(store.paths.config_file.read_text(encoding="utf-8"))
        assert raw["profiles"][0]["name"] == "MyProfile"

    def test_load_from_file_roundtrip(self, tmp_path: pathlib.Path):
        store = _make_store(tmp_path)
        store.config.poll_interval_seconds = 2.5
        store.save()

        loaded = ConfigStore._load_from_file(store.paths.config_file)
        assert loaded.poll_interval_seconds == 2.5

    def test_default_creates_config_file_if_missing(self, tmp_path: pathlib.Path, monkeypatch):
        def fake_default():
            return AppPaths(
                config_dir=tmp_path / "cfg",
                log_dir=tmp_path / "log",
            )

        monkeypatch.setattr(AppPaths, "default", staticmethod(fake_default))
        store = ConfigStore.default()
        assert store.paths.config_file.exists()
        assert len(store.config.profiles) >= 1

    def test_default_loads_existing_config(self, tmp_path: pathlib.Path, monkeypatch):
        def fake_default():
            return AppPaths(
                config_dir=tmp_path / "cfg",
                log_dir=tmp_path / "log",
            )

        monkeypatch.setattr(AppPaths, "default", staticmethod(fake_default))
        # First boot — creates file
        store1 = ConfigStore.default()
        store1.config.profiles[0].name = "Saved"
        store1.save()

        # Second boot — should load existing
        store2 = ConfigStore.default()
        assert store2.config.profiles[0].name == "Saved"

    def test_default_recovers_from_corrupt_config(self, tmp_path: pathlib.Path, monkeypatch):
        def fake_default():
            return AppPaths(
                config_dir=tmp_path / "cfg",
                log_dir=tmp_path / "log",
            )

        monkeypatch.setattr(AppPaths, "default", staticmethod(fake_default))
        (tmp_path / "cfg").mkdir(parents=True)
        (tmp_path / "cfg" / "config.json").write_text("not valid json{{{", encoding="utf-8")

        store = ConfigStore.default()
        # Should recover to default config
        assert len(store.config.profiles) >= 1
        # Backup should be created (config.json → config.bak)
        assert (tmp_path / "cfg" / "config.bak").exists()

    def test_export_and_import(self, tmp_path: pathlib.Path):
        store = _make_store(tmp_path)
        store.config.poll_interval_seconds = 3.0
        store.save()

        export_path = tmp_path / "export.json"
        store.export_to_file(export_path)

        store2 = _make_store(tmp_path / "other")
        store2.import_from_file(export_path)
        assert store2.config.poll_interval_seconds == 3.0
