import sys
from dataclasses import dataclass

from ignition.core.single_instance import SingleInstance
from ignition.core.state import AppState
from ignition.gui.bootstrap import run_gui


@dataclass(frozen=True)
class AppLaunchOptions:
    start_in_background: bool
    headless: bool


def run_app(*, start_in_background: bool, headless: bool) -> int:
    with SingleInstance(name="iGnition") as instance:
        if not instance.acquired:
            return 0

        state = AppState.create()
        options = AppLaunchOptions(start_in_background=start_in_background, headless=headless)
        if options.headless:
            return state.run_headless()
        return run_gui(state=state, start_in_background=options.start_in_background)
