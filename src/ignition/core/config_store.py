import json
from dataclasses import dataclass
from pathlib import Path

from ignition.core.models import AppConfig
from ignition.core.paths import AppPaths
from ignition.core.storage import atomic_write_text


@dataclass
class ConfigStore:
    paths: AppPaths
    config: AppConfig

    @classmethod
    def default(cls) -> "ConfigStore":
        paths = AppPaths.default()
        paths.config_dir.mkdir(parents=True, exist_ok=True)
        paths.log_dir.mkdir(parents=True, exist_ok=True)

        config_file = paths.config_file
        if config_file.exists():
            try:
                config = cls._load_from_file(config_file)
            except Exception:
                backup = config_file.with_suffix(".bak")
                try:
                    config_file.replace(backup)
                except OSError:
                    pass
                config = AppConfig.default()
                cls._save_to_file(config_file, config)
        else:
            config = AppConfig.default()
            cls._save_to_file(config_file, config)
        return cls(paths=paths, config=config)

    @staticmethod
    def _load_from_file(path: Path) -> AppConfig:
        raw_text = path.read_text(encoding="utf-8")
        raw = json.loads(raw_text)
        if not isinstance(raw, dict):
            return AppConfig.default()
        return AppConfig.from_dict(raw)

    @staticmethod
    def _save_to_file(path: Path, config: AppConfig) -> None:
        payload = json.dumps(config.to_dict(), indent=2, ensure_ascii=False)
        atomic_write_text(path, payload, encoding="utf-8")

    def save(self) -> None:
        self._save_to_file(self.paths.config_file, self.config)

    def import_from_file(self, path: Path) -> None:
        config = self._load_from_file(path)
        self.config = config
        self.save()

    def export_to_file(self, path: Path) -> None:
        self._save_to_file(path, self.config)
