import sys
import re
import os
import subprocess
import json
import time
from modules.misc.appleScript import runAppleScript
import pygetwindow as gw
import pyautogui as pag
from AppKit import NSWorkspace
from ApplicationServices import AXUIElementIsAttributeSettable, AXUIElementCreateApplication, kAXErrorSuccess, AXUIElementSetAttributeValue, AXUIElementCopyAttributeValue, AXValueCreate, kAXValueCGPointType, kAXValueCGSizeType, AXUIElementCopyAttributeNames
from Quartz import CGPoint, CGSize
mw,mh = pag.size()

VIRTUAL_MONITOR_WIDTH = 1920
VIRTUAL_MONITOR_HEIGHT = 1080
VIRTUAL_MONITOR_STRICT_MODE = False
VIRTUAL_MONITOR_START_TIMEOUT = 8

_virtual_monitor_state = {
    "active": False,
    "display_id": None,
}
_virtual_monitor_process = None


def _projectRoot():
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def _virtualMonitorHelperPath():
    return os.path.join(_projectRoot(), "src", "data", "bin", "virtual_display_helper")


def _isVirtualMonitorEnabled():
    try:
        from modules.misc import settingsManager
        settings = settingsManager.loadAllSettings()
        return bool(settings.get("use_virtual_monitor", False))
    except Exception:
        return False


def _runVirtualMonitorCommand(args, timeout=10):
    helper_path = _virtualMonitorHelperPath()
    if not os.path.exists(helper_path):
        raise FileNotFoundError(f"Virtual monitor helper not found: {helper_path}")
    if not os.access(helper_path, os.X_OK):
        raise PermissionError(f"Virtual monitor helper is not executable: {helper_path}")

    process = subprocess.run(
        [helper_path, *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    stdout = (process.stdout or "").strip()
    stderr = (process.stderr or "").strip()

    payload = None
    if stdout:
        for line in reversed(stdout.splitlines()):
            candidate = line.strip()
            if not candidate:
                continue
            try:
                payload = json.loads(candidate)
                break
            except Exception:
                continue

    if process.returncode != 0:
        raise RuntimeError(stderr or stdout or "Virtual monitor helper command failed")
    return payload or {}


def _refreshScreenData():
    try:
        from modules.screen import screenData
        screenData.setScreenData()
    except Exception:
        pass


def _startVirtualMonitorProcess():
    global _virtual_monitor_process
    helper_path = _virtualMonitorHelperPath()
    if not os.path.exists(helper_path):
        raise FileNotFoundError(f"Virtual monitor helper not found: {helper_path}")
    if not os.access(helper_path, os.X_OK):
        raise PermissionError(f"Virtual monitor helper is not executable: {helper_path}")

    _virtual_monitor_process = subprocess.Popen(
        [
            helper_path,
            "start",
            "--width",
            str(VIRTUAL_MONITOR_WIDTH),
            "--height",
            str(VIRTUAL_MONITOR_HEIGHT),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    deadline = time.time() + VIRTUAL_MONITOR_START_TIMEOUT
    while time.time() < deadline:
        try:
            payload = _runVirtualMonitorCommand(["status"], timeout=2)
            if payload.get("active"):
                _virtual_monitor_state["active"] = True
                _virtual_monitor_state["display_id"] = payload.get("display_id")
                _virtual_monitor_state["x"] = payload.get("x")
                _virtual_monitor_state["y"] = payload.get("y")
                _virtual_monitor_state["width"] = payload.get("width", VIRTUAL_MONITOR_WIDTH)
                _virtual_monitor_state["height"] = payload.get("height", VIRTUAL_MONITOR_HEIGHT)
                return True
        except Exception:
            pass
        time.sleep(0.2)
    return False


def startVirtualMonitor(force=False):
    if sys.platform != "darwin":
        return False
    if not force and not _isVirtualMonitorEnabled():
        return False
    if _virtual_monitor_state.get("active"):
        return True

    try:
        if _startVirtualMonitorProcess():
            _refreshScreenData()
            return True
        raise RuntimeError("Timed out waiting for virtual monitor to become active")
    except Exception as e:
        _virtual_monitor_state["active"] = False
        _virtual_monitor_state["display_id"] = None
        print(f"[VirtualMonitor] Failed to start helper: {e}")
        if VIRTUAL_MONITOR_STRICT_MODE:
            raise
        return False


def stopVirtualMonitor(force=False):
    global _virtual_monitor_process
    if sys.platform != "darwin":
        return False
    if not force and not _isVirtualMonitorEnabled():
        return False

    try:
        _runVirtualMonitorCommand(["stop"], timeout=5)
    except Exception as e:
        print(f"[VirtualMonitor] Failed to stop helper: {e}")
        if VIRTUAL_MONITOR_STRICT_MODE:
            raise
        return False

    _virtual_monitor_state["active"] = False
    _virtual_monitor_state["display_id"] = None
    if _virtual_monitor_process and _virtual_monitor_process.poll() is None:
        try:
            _virtual_monitor_process.terminate()
        except Exception:
            pass
    _virtual_monitor_process = None
    _refreshScreenData()
    return True


def getVirtualMonitorState():
    state = {
        "active": False,
        "display_id": _virtual_monitor_state.get("display_id"),
        "width": VIRTUAL_MONITOR_WIDTH,
        "height": VIRTUAL_MONITOR_HEIGHT,
        "x": _virtual_monitor_state.get("x", 0),
        "y": _virtual_monitor_state.get("y", 0),
    }
    if sys.platform != "darwin":
        return state

    try:
        payload = _runVirtualMonitorCommand(["status"], timeout=3)
        if isinstance(payload, dict):
            state.update(payload)
        _virtual_monitor_state["active"] = bool(state.get("active", False))
        _virtual_monitor_state["display_id"] = state.get("display_id")
        _virtual_monitor_state["x"] = state.get("x", 0)
        _virtual_monitor_state["y"] = state.get("y", 0)
        _virtual_monitor_state["width"] = state.get("width", VIRTUAL_MONITOR_WIDTH)
        _virtual_monitor_state["height"] = state.get("height", VIRTUAL_MONITOR_HEIGHT)
    except Exception:
        pass
    return state


def prepareVirtualMonitorIfEnabled():
    if sys.platform != "darwin":
        return True
    if not _isVirtualMonitorEnabled():
        return True

    state = getVirtualMonitorState()
    if state.get("active"):
        return True

    print("[VirtualMonitor] Starting bundled virtual monitor at 1920x1080")
    success = startVirtualMonitor(force=True)
    if not success:
        print("[VirtualMonitor] Continuing Roblox launch without virtual monitor")
    time.sleep(0.5)
    return success

def isAppOpenMac(app="roblox"):
    tmp = os.popen("ps -Af").read()
    return app in tmp[:]

def openAppMac(app="Roblox"):
    if app.lower() == "roblox":
        prepareVirtualMonitorIfEnabled()
    if not isAppOpenMac(app): return False
    runAppleScript('activate application "{}"'.format(app))
    subprocess.run(["open", "-a", app])
    workspace = NSWorkspace.sharedWorkspace()
    for runningApp in workspace.runningApplications():
        if runningApp.localizedName() == app:
            runningApp.activateWithOptions_(1 << 1)
            break
    # If virtual monitor is enabled and active, move and fullscreen the app
    try:
        if _isVirtualMonitorEnabled():
            state = getVirtualMonitorState()
            if state.get("active"):
                # give the app a moment to create its windows
                time.sleep(0.8)
                _moveAppToVirtualMonitorAndFullscreen(app)
    except Exception:
        pass
    return True

def openDeeplink(link):
    if isinstance(link, str) and link.lower().startswith("roblox://"):
        prepareVirtualMonitorIfEnabled()
    subprocess.call(["open", link])
    # After deeplink, ensure Roblox is on the virtual monitor if enabled
    try:
        if isinstance(link, str) and link.lower().startswith("roblox://") and _isVirtualMonitorEnabled():
            time.sleep(0.8)
            _moveAppToVirtualMonitorAndFullscreen("Roblox")
    except Exception:
        pass

def closeApp(app):
    try:
        subprocess.call(["pkill", app], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass
    cmd = """
        osascript -e 'quit application "Roblox"'
    """
    os.system(cmd)

def forceQuitApp(app):
    """Forcefully terminate an app/process. More aggressive than closeApp.

    Uses SIGKILL on macOS.
    """
    try:
        subprocess.call(["pkill", "-9", app], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

def forceCloseApp(app):
    forceQuitApp(app)
    # also try killall as a fallback (suppress errors/output)
    try:
        subprocess.call(["killall", "-9", app], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

def getWindowSize(windowName):
    import Quartz
    
    windowList = Quartz.CGWindowListCopyWindowInfo(
        Quartz.kCGWindowListExcludeDesktopElements | Quartz.kCGWindowListOptionOnScreenOnly, 
        Quartz.kCGNullWindowID
    )
    
    for win in windowList:
        owner = win.get(Quartz.kCGWindowOwnerName, '')
        name = win.get(Quartz.kCGWindowName, '')
        title = f'{owner} {name}'.strip()
        
        if windowName.lower() in title.lower():
            bounds = win.get('kCGWindowBounds', {})
            if bounds:
                x = int(bounds.get('X', 0))
                y = int(bounds.get('Y', 0))
                w = int(bounds.get('Width', mw))
                h = int(bounds.get('Height', mh))
                return x, y, w, h
    
    # Window not found, most likely fullscreen (but unfocused)
    return 0, 0, mw, mh


def setAppFullscreenMac(app="Roblox", fullscreen=True):
    workspace = NSWorkspace.sharedWorkspace()
    for runningApp in workspace.runningApplications():
        if runningApp.localizedName() == app:
            pid = runningApp.processIdentifier()
            break
    else:
        return
    
    appRef = AXUIElementCreateApplication(pid)
    _, windowRef = AXUIElementCopyAttributeValue(appRef, "AXMainWindow", None)
    AXUIElementSetAttributeValue(windowRef, "AXFullScreen", fullscreen)

def maximiseAppWindowMac(app="Roblox"):
    workspace = NSWorkspace.sharedWorkspace()
    for runningApp in workspace.runningApplications():
        if runningApp.localizedName() == app:
            pid = runningApp.processIdentifier()
            break
    else:
        return
    
    appRef = AXUIElementCreateApplication(pid)
    _, windowRef = AXUIElementCopyAttributeValue(appRef, "AXMainWindow", None)
    _, attributes = AXUIElementCopyAttributeNames(windowRef, None)
    pos = AXValueCreate(kAXValueCGPointType, CGPoint(0, 0))
    size = AXValueCreate(kAXValueCGSizeType, CGSize(mw, mh))
    AXUIElementSetAttributeValue(windowRef, "AXPosition", pos)
    AXUIElementSetAttributeValue(windowRef, "AXSize", size)


def _moveAppToVirtualMonitorAndFullscreen(app="Roblox", wait_timeout=8):
    """Move the application's main window to the virtual monitor bounds and make it fullscreen.

    Returns True on success, False otherwise.
    """
    if sys.platform != "darwin":
        return False
    state = getVirtualMonitorState()
    if not state.get("active"):
        return False

    deadline = time.time() + wait_timeout
    while time.time() < deadline:
        try:
            workspace = NSWorkspace.sharedWorkspace()
            pid = None
            for runningApp in workspace.runningApplications():
                if runningApp.localizedName() == app:
                    pid = runningApp.processIdentifier()
                    break
            if not pid:
                time.sleep(0.25)
                continue

            appRef = AXUIElementCreateApplication(pid)
            status, windowRef = AXUIElementCopyAttributeValue(appRef, "AXMainWindow", None)
            if status != kAXErrorSuccess or windowRef is None:
                time.sleep(0.25)
                continue

            # Position and size
            pos = AXValueCreate(kAXValueCGPointType, CGPoint(state.get("x", 0), state.get("y", 0)))
            size = AXValueCreate(kAXValueCGSizeType, CGSize(state.get("width", VIRTUAL_MONITOR_WIDTH), state.get("height", VIRTUAL_MONITOR_HEIGHT)))
            try:
                AXUIElementSetAttributeValue(windowRef, "AXPosition", pos)
                AXUIElementSetAttributeValue(windowRef, "AXSize", size)
            except Exception:
                pass

            # Try to set fullscreen via accessibility attribute; fallback to existing helper
            try:
                AXUIElementSetAttributeValue(windowRef, "AXFullScreen", True)
            except Exception:
                try:
                    setAppFullscreenMac(app, True)
                except Exception:
                    pass

            try:
                runAppleScript('activate application "{}"'.format(app))
            except Exception:
                pass

            try:
                center_x = int(state.get("x", 0) + (state.get("width", VIRTUAL_MONITOR_WIDTH) / 2))
                center_y = int(state.get("y", 0) + (state.get("height", VIRTUAL_MONITOR_HEIGHT) / 2))
                pag.moveTo(center_x, center_y, duration=0)
            except Exception:
                pass

            # Do not manually CFRelease objects returned/managed by PyObjC
            # PyObjC manages lifetime and explicit CFRelease can cause double-free.

            return True
        except Exception:
            time.sleep(0.25)
    return False

# Set the functions to use macOS implementations
openApp = openAppMac
isAppOpen = isAppOpenMac
maximiseAppWindow = maximiseAppWindowMac
setAppFullscreen = setAppFullscreenMac
