from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable, Generator

import pystray
from PIL import Image, ImageDraw

_ICON_PATH = Path(__file__).parent / "assets" / "ignition_logo.png"


def _build_icon_image() -> Image.Image:
    if _ICON_PATH.exists():
        return Image.open(_ICON_PATH).convert("RGBA").resize((64, 64), Image.LANCZOS)
    # fallback: drawn placeholder
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([6, 6, size - 6, size - 6], radius=12, fill=(26, 26, 26, 255))
    draw.text((20, 18), "iG", fill=(255, 255, 255, 255))
    return img


class SystemTray:
    def __init__(
        self,
        *,
        on_open: Callable[[], None],
        on_quit: Callable[[], None],
        get_profiles: Callable[[], list[dict]] | None = None,
        on_switch_profile: Callable[[str], None] | None = None,
    ) -> None:
        self.on_open = on_open
        self.on_quit = on_quit
        self._get_profiles = get_profiles
        self._on_switch_profile = on_switch_profile
        self._thread: threading.Thread | None = None
        self._icon = pystray.Icon(
            "iGnition",
            _build_icon_image(),
            "iGnition",
            self._build_menu(),
        )

    def _build_menu(self) -> pystray.Menu:
        items: list = [pystray.MenuItem("Open", lambda icon, item: self.on_open())]
        if self._get_profiles is not None:
            items.append(
                pystray.MenuItem("Profiles", pystray.Menu(self._iter_profile_items))
            )
        items.append(pystray.Menu.SEPARATOR)
        items.append(pystray.MenuItem("Quit", lambda icon, item: self.on_quit()))
        return pystray.Menu(*items)

    def _iter_profile_items(self) -> Generator:
        if self._get_profiles is None:
            return
        try:
            profiles = self._get_profiles()
        except Exception:
            return
        for p in profiles:
            pid = p.get("profile_id", "")
            name = p.get("name", "?")
            is_active = bool(p.get("is_active"))

            def _make_action(profile_id: str) -> Callable:
                def action(icon: pystray.Icon, item: pystray.MenuItem) -> None:
                    if self._on_switch_profile:
                        self._on_switch_profile(profile_id)
                return action

            yield pystray.MenuItem(
                name,
                _make_action(pid),
                checked=lambda item, active=is_active: active,
                radio=True,
            )

    def rebuild_menu(self) -> None:
        """Rebuild tray menu after profile list changes."""
        try:
            self._icon.menu = self._build_menu()
            self._icon.update_menu()
        except Exception:
            pass

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._icon.run, name="tray", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        try:
            self._icon.stop()
        except Exception:
            pass
