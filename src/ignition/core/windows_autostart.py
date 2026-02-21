import sys
import winreg


class WindowsAutostart:
    RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

    def __init__(self, *, app_name: str) -> None:
        self._app_name = app_name

    def is_enabled(self) -> bool:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.RUN_KEY, 0, winreg.KEY_READ) as key:
                winreg.QueryValueEx(key, self._app_name)
                return True
        except FileNotFoundError:
            return False
        except OSError:
            return False

    def enable(self) -> None:
        cmd = self._build_command()
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, self._app_name, 0, winreg.REG_SZ, cmd)

    def disable(self) -> None:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                winreg.DeleteValue(key, self._app_name)
        except FileNotFoundError:
            return
        except OSError:
            return

    def _build_command(self) -> str:
        exe = sys.executable
        frozen = bool(getattr(sys, "frozen", False))
        if frozen:
            return f'"{exe}" --background'
        return f'"{exe}" -m ignition --background'
