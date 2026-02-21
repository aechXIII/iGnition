from dataclasses import dataclass
from pathlib import Path

from platformdirs import PlatformDirs


@dataclass(frozen=True)
class AppPaths:
    config_dir: Path
    log_dir: Path

    @property
    def config_file(self) -> Path:
        return self.config_dir / "config.json"

    @property
    def session_history_file(self) -> Path:
        return self.config_dir / "session_history.json"

    @classmethod
    def default(cls) -> "AppPaths":
        dirs = PlatformDirs(appname="iGnition", appauthor=False)
        config_dir = Path(dirs.user_config_dir)
        log_dir = Path(dirs.user_log_dir)
        return cls(config_dir=config_dir, log_dir=log_dir)
