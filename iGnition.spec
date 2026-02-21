# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_submodules

hiddenimports = collect_submodules("pystray")

a = Analysis(
    ["src/ignition/__main__.py"],
    pathex=["src"],
    binaries=[],
    datas=[
        ("src/ignition/gui/assets/index.html",        "ignition/gui/assets"),
        ("src/ignition/gui/assets/app.js",            "ignition/gui/assets"),
        ("src/ignition/gui/assets/style.css",         "ignition/gui/assets"),
        ("src/ignition/gui/assets/ignition_logo.ico", "ignition/gui/assets"),
        ("src/ignition/gui/assets/ignition_logo.png", "ignition/gui/assets"),
        ("src/ignition/gui/assets/car-steering-wheel-svgrepo-com.svg", "ignition/gui/assets"),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="iGnition",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    icon="src/ignition/gui/assets/ignition_logo.ico",
)
