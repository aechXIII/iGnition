from ignition.core.state import AppState
from ignition.gui.web.runner import run_webview


def run_gui(*, state: AppState, start_in_background: bool) -> int:
    return run_webview(state=state, start_in_background=start_in_background)
