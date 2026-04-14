# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


def optional_submodules(package):
    try:
        return collect_submodules(package)
    except Exception:
        return []


def optional_data_files(package):
    try:
        return collect_data_files(package)
    except Exception:
        return []


datas = [
    ("src", "src"),
    ("paths", "paths"),
    ("settings", "settings"),
    ("README.md", "."),
    ("LICENSE", "."),
    ("HELP.txt", "."),
    ("install_dependencies.command", "."),
]

datas += optional_data_files("eel")
datas += optional_data_files("webview")
datas += optional_data_files("ocrmac")

hiddenimports = [
    "bottle_websocket",
    "geventwebsocket",
    "pynput.keyboard._darwin",
    "pynput.mouse._darwin",
    "rubicon.objc",
    "webview.platforms.cocoa",
]


a = Analysis(
    ["src/main.py"],
    pathex=["src"],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "gevent.tests",
        "greenlet.tests",
        "matplotlib.tests",
        "matplotlib.backends.backend_gtk3",
        "matplotlib.backends.backend_gtk4",
        "matplotlib.backends.backend_qt",
        "matplotlib.backends.backend_qt5",
        "matplotlib.backends.backend_qtagg",
        "matplotlib.backends.backend_wx",
        "PyQt5",
        "PyQt6",
        "PySide2",
        "PySide6",
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Fuzzy Macro",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="Fuzzy Macro",
)

app = BUNDLE(
    coll,
    name="Fuzzy Macro.app",
    icon="src/webapp/assets/general/icon.png",
    bundle_identifier="com.fuzzyteam.fuzzymacro",
    info_plist={
        "NSAppleEventsUsageDescription": "Fuzzy Macro needs to control Roblox while the macro is running.",
        "NSInputMonitoringUsageDescription": "Fuzzy Macro uses keyboard hotkeys to start and stop the macro.",
    },
)
