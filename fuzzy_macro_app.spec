# -*- mode: python ; coding: utf-8 -*-

import os
import subprocess
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules


ROOT = Path.cwd()
TARGET_ARCH = os.environ.get("FUZZY_TARGET_ARCH", "universal2") or None


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


def git_ignored(path):
    result = subprocess.run(
        ["git", "check-ignore", "--quiet", "--no-index", "--", str(path)],
        cwd=ROOT,
    )
    if result.returncode == 0:
        return True
    if result.returncode == 1:
        return False
    raise RuntimeError(f"Unable to evaluate .gitignore rules for {path}")


def add_release_file(datas, path, destination="."):
    source = ROOT / path
    if source.is_file() and not git_ignored(path):
        datas.append((str(source), destination))


def add_release_tree(datas, path):
    source_root = ROOT / path
    if not source_root.exists():
        return

    for source in source_root.rglob("*"):
        relative = source.relative_to(ROOT)
        if git_ignored(relative):
            continue
        if source.is_file():
            destination = relative.parent
            datas.append((str(source), str(destination)))


datas = []
for release_tree in ("src", "paths", "settings"):
    add_release_tree(datas, release_tree)

for release_file in ("README.md", "LICENSE", "HELP.txt", "install_dependencies.command"):
    add_release_file(datas, release_file)

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
    target_arch=TARGET_ARCH,
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
        "LSMinimumSystemVersion": "10.12.0",
        "LSMinimumSystemVersionByArchitecture": {
            "x86_64": "10.12.0",
            "arm64": "11.0.0",
        },
        "NSAppleEventsUsageDescription": "Fuzzy Macro needs to control Roblox while the macro is running.",
        "NSInputMonitoringUsageDescription": "Fuzzy Macro uses keyboard hotkeys to start and stop the macro.",
    },
)
