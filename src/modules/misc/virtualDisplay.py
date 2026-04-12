import os
import platform
import select
import subprocess
import time
import json

from AppKit import NSScreen

from modules.controls import mouse
from modules.misc import appManager, settingsManager

DISPLAY_NAME = "Fuzzy Macro Virtual Display"
DISPLAY_WIDTH = 1920
DISPLAY_HEIGHT = 1080
_virtual_display_process = None
_virtual_display_state = None


def isVirtualMonitorEnabled(settings=None):
    if settings is None:
        settings = settingsManager.loadAllSettings()
    return bool(settings.get("virtual_monitor", False))


def _helper_paths():
    root = settingsManager.getProjectRoot()
    helper_dir = os.path.join(root, "src", "native", "virtual_display_helper")
    source_path = os.path.join(helper_dir, "main.swift")
    header_path = os.path.join(helper_dir, "CGVirtualDisplayPrivate.h")
    build_script_path = os.path.join(helper_dir, "build.sh")
    binary_path = os.path.join(root, "src", "data", "bin", "virtual_display_helper_bin")
    return helper_dir, source_path, header_path, build_script_path, binary_path


def _screen_name(screen):
    try:
        return screen.localizedName()
    except Exception:
        return ""


def _screen_frame(screen):
    frame = screen.frame()
    return {
        "x": int(frame.origin.x),
        "y": int(frame.origin.y),
        "width": int(frame.size.width),
        "height": int(frame.size.height),
    }


def _screen_display_id(screen):
    try:
        return int(screen.deviceDescription()["NSScreenNumber"])
    except Exception:
        return None


def findVirtualMonitor(display_id=None):
    for screen in NSScreen.screens():
        frame = _screen_frame(screen)
        if display_id is not None and _screen_display_id(screen) == int(display_id):
            return frame
        name = _screen_name(screen)
        if name == DISPLAY_NAME and frame["width"] == DISPLAY_WIDTH and frame["height"] == DISPLAY_HEIGHT:
            return frame
    return None


def buildVirtualMonitorHelperIfNeeded():
    helper_dir, source_path, header_path, build_script_path, binary_path = _helper_paths()
    source_mtime = max(os.path.getmtime(source_path), os.path.getmtime(header_path))
    if os.path.exists(binary_path) and os.path.getmtime(binary_path) >= source_mtime:
        return binary_path

    if not os.path.exists(source_path):
        raise FileNotFoundError(f"Virtual monitor helper source not found: {source_path}")
    if not os.path.exists(build_script_path):
        raise FileNotFoundError(f"Virtual monitor helper build script not found: {build_script_path}")

    result = subprocess.run(
        [build_script_path],
        cwd=helper_dir,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        output = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"Failed to build virtual monitor helper: {output[-1200:]}")
    return binary_path


def _helper_is_running():
    return _virtual_display_process is not None and _virtual_display_process.poll() is None


def _read_helper_state(timeout=5):
    if _virtual_display_process is None or _virtual_display_process.stdout is None:
        return None

    readable, _, _ = select.select([_virtual_display_process.stdout], [], [], timeout)
    if not readable:
        return None

    line = _virtual_display_process.stdout.readline().strip()
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return None


def _helper_status(binary_path):
    result = subprocess.run(
        [binary_path, "status"],
        capture_output=True,
        text=True,
        timeout=5,
    )
    try:
        return json.loads(result.stdout.strip() or "{}")
    except json.JSONDecodeError:
        return {"active": False, "error": result.stderr.strip()}


def ensureVirtualMonitor(timeout=30):
    global _virtual_display_state
    global _virtual_display_process

    if platform.system() != "Darwin":
        raise RuntimeError("Virtual monitor mode is only supported on macOS.")

    binary_path = buildVirtualMonitorHelperIfNeeded()

    status = _helper_status(binary_path)
    if status.get("active"):
        _virtual_display_state = status
        return {
            "x": int(status.get("x") or 0),
            "y": int(status.get("y") or 0),
            "width": int(status.get("width") or DISPLAY_WIDTH),
            "height": int(status.get("height") or DISPLAY_HEIGHT),
        }

    if not _helper_is_running():
        _virtual_display_process = subprocess.Popen(
            [binary_path, "start", "--width", str(DISPLAY_WIDTH), "--height", str(DISPLAY_HEIGHT)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        _virtual_display_state = _read_helper_state()
        if _virtual_display_state and _virtual_display_state.get("error"):
            raise RuntimeError(_virtual_display_state["error"])
        if _virtual_display_state and _virtual_display_state.get("active"):
            return {
                "x": int(_virtual_display_state.get("x") or 0),
                "y": int(_virtual_display_state.get("y") or 0),
                "width": int(_virtual_display_state.get("width") or DISPLAY_WIDTH),
                "height": int(_virtual_display_state.get("height") or DISPLAY_HEIGHT),
            }

    start = time.time()
    while time.time() - start < timeout:
        if _virtual_display_process is not None and _virtual_display_process.poll() is not None:
            stderr = (_virtual_display_process.stderr.read() if _virtual_display_process.stderr else "").strip()
            raise RuntimeError(f"Virtual monitor helper exited early: {stderr}")
        status = _helper_status(binary_path)
        if status.get("active"):
            _virtual_display_state = status
            return {
                "x": int(status.get("x") or 0),
                "y": int(status.get("y") or 0),
                "width": int(status.get("width") or DISPLAY_WIDTH),
                "height": int(status.get("height") or DISPLAY_HEIGHT),
            }
        time.sleep(0.5)

    if _virtual_display_process is not None and _virtual_display_process.poll() is None:
        _virtual_display_process.terminate()
    raise TimeoutError("Timed out waiting for the virtual display to appear.")


def moveRobloxToVirtualMonitor(frame=None):
    if frame is None:
        frame = ensureVirtualMonitor()
    if not appManager.openApp("Roblox"):
        return False
    target_width = max(1, int(frame.get("width") or DISPLAY_WIDTH))
    target_height = max(1, int(frame.get("height") or DISPLAY_HEIGHT))

    for _ in range(10):
        if appManager.setAppWindowFrame(
            "Roblox",
            frame["x"],
            frame["y"],
            target_width,
            target_height,
        ):
            mouse.moveTo(
                frame["x"] + target_width // 2,
                frame["y"] + target_height // 2,
                delay=0,
            )
            return True
        time.sleep(0.5)
    return False


def stopVirtualMonitor():
    global _virtual_display_process
    global _virtual_display_state

    try:
        binary_path = buildVirtualMonitorHelperIfNeeded()
        subprocess.run(
            [binary_path, "stop"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        pass

    if _virtual_display_process is not None and _virtual_display_process.poll() is None:
        try:
            _virtual_display_process.terminate()
            _virtual_display_process.wait(timeout=5)
        except Exception:
            pass

    _virtual_display_process = None
    _virtual_display_state = None
