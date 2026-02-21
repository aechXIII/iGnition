import threading

from ignition.core.config_store import ConfigStore
from ignition.core.ignition_controller import IgnitionController
from ignition.core.logging_setup import configure_logging


class AppState:
    def __init__(self, *, config_store: ConfigStore, controller: IgnitionController) -> None:
        self.config_store = config_store
        self.controller = controller

    @classmethod
    def create(cls) -> "AppState":
        config_store = ConfigStore.default()
        configure_logging(log_dir=config_store.paths.log_dir)
        controller = IgnitionController(config_store=config_store)
        return cls(config_store=config_store, controller=controller)

    def run_headless(self) -> int:
        self.controller.start()
        stop_event = threading.Event()
        try:
            stop_event.wait()
        except KeyboardInterrupt:
            return 0
        finally:
            self.controller.stop()
        return 0
