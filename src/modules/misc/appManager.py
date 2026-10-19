import sys
import re
import os
import subprocess
import time
from modules.misc.appleScript import runAppleScript
import pygetwindow as gw
import pyautogui as pag
from AppKit import NSWorkspace
from ApplicationServices import AXUIElementIsAttributeSettable, AXUIElementCreateApplication, kAXErrorSuccess, AXUIElementSetAttributeValue, AXUIElementCopyAttributeValue, AXValueCreate, kAXValueCGPointType, kAXValueCGSizeType, AXUIElementCopyAttributeNames
from Quartz import CGPoint, CGSize
from CoreFoundation import CFRelease
from modules.screen import macroDisplay

def isAppOpenMac(app="roblox"):
    tmp = os.popen("ps -Af").read()
    return app in tmp[:]

def openAppMac(app="Roblox"):
    if not isAppOpenMac(app): return False
    runAppleScript('activate application "{}"'.format(app))
    subprocess.run(["open", "-a", app])
    workspace = NSWorkspace.sharedWorkspace()
    for runningApp in workspace.runningApplications():
        if runningApp.localizedName() == app:
            runningApp.activateWithOptions_(1 << 1)
            break
    return True

def isAppFocusedMac(app="Roblox"):
    try:
        workspace = NSWorkspace.sharedWorkspace()
        frontmost = workspace.frontmostApplication()
        if not frontmost:
            return False
        frontmost_name = frontmost.localizedName() or ""
        app_name = app or ""
        frontmost_name = frontmost_name.lower()
        app_name = app_name.lower()
        return app_name in frontmost_name or frontmost_name in app_name
    except Exception:
        return False

def openDeeplink(link):
    subprocess.call(["open", link])

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
    # also try killall as a fallback (suppress errors/output)
    try:
        subprocess.call(["killall", "-9", app], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

#returns the window bounds relative to the display the macro runs on
def getWindowSize(windowName):
    import Quartz
    ox, oy = macroDisplay.origin()
    mw, mh = macroDisplay.size()
    
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
                x = int(bounds.get('X', 0)) - ox
                y = int(bounds.get('Y', 0)) - oy
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
    ox, oy, mw, mh = macroDisplay.bounds()
    pos = AXValueCreate(kAXValueCGPointType, CGPoint(ox, oy))
    size = AXValueCreate(kAXValueCGSizeType, CGSize(mw, mh))
    AXUIElementSetAttributeValue(windowRef, "AXPosition", pos)
    AXUIElementSetAttributeValue(windowRef, "AXSize", size)

def _waitForFullscreen(windowRef, fullscreen, timeout=3):
    deadline = time.time() + timeout
    while time.time() < deadline:
        _, value = AXUIElementCopyAttributeValue(windowRef, "AXFullScreen", None)
        if bool(value) == fullscreen:
            return True
        time.sleep(0.1)
    return False

def _exitFullscreen(windowRef):
    """Leave fullscreen and wait for the window to settle. Roblox sometimes
    ignores the first request, so keep asking (Revolution Macro does the same:
    up to 15 tries 0.1s apart, then 2s for Roblox to restore its window)."""
    for _ in range(15):
        AXUIElementSetAttributeValue(windowRef, "AXFullScreen", False)
        time.sleep(0.1)
        _, value = AXUIElementCopyAttributeValue(windowRef, "AXFullScreen", None)
        if not value:
            break
    #roblox restores its saved window after the space closes. Moving it before
    #then gets overwritten, putting it back on the main display
    time.sleep(2)

def _getWindow(pid):
    appRef = AXUIElementCreateApplication(pid)
    err, windowRef = AXUIElementCopyAttributeValue(appRef, "AXMainWindow", None)
    if err == kAXErrorSuccess and windowRef is not None:
        return windowRef
    #the main window isn't always reported while its fullscreen space is hidden
    err, windows = AXUIElementCopyAttributeValue(appRef, "AXWindows", None)
    if err == kAXErrorSuccess and windows:
        return windows[0]
    return None

def _windowOnDisplay(windowRef, displayBounds):
    """True if the window is centred on the display. Uses the accessibility
    frame, which (unlike the on-screen window list) is still reported while
    the window's fullscreen space is not the visible one."""
    from ApplicationServices import AXValueGetValue
    dx, dy, dw, dh = displayBounds
    _, pos = AXUIElementCopyAttributeValue(windowRef, "AXPosition", None)
    _, size = AXUIElementCopyAttributeValue(windowRef, "AXSize", None)
    if pos is None or size is None:
        return False
    _, point = AXValueGetValue(pos, kAXValueCGPointType, None)
    _, extent = AXValueGetValue(size, kAXValueCGSizeType, None)
    cx = point.x + extent.width / 2
    cy = point.y + extent.height / 2
    return dx <= cx < dx + dw and dy <= cy < dy + dh

def _waitForWindowOnDisplay(windowRef, displayBounds, timeout=3):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _windowOnDisplay(windowRef, displayBounds):
            return True
        time.sleep(0.1)
    return False

_windowLockPath = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/user/virtual_display/window.lock"))

class _WindowLock:
    """Stops the GUI and macro processes from moving the window at the same time."""
    def __enter__(self):
        import fcntl
        os.makedirs(os.path.dirname(_windowLockPath), exist_ok=True)
        self.file = open(_windowLockPath, "w")
        fcntl.flock(self.file, fcntl.LOCK_EX)
        return self

    def __exit__(self, *args):
        import fcntl
        fcntl.flock(self.file, fcntl.LOCK_UN)
        self.file.close()

def moveAppToMacroDisplayMac(app="Roblox"):
    """Keep the app's window fullscreen on the display the macro runs on (the
    Fuzzy Macro virtual display).
    Returns True if the window had to be moved or made fullscreen."""
    displayBounds = macroDisplay.bounds()
    dx, dy, dw, dh = displayBounds
    if (dx, dy) == (0, 0):
        return False

    workspace = NSWorkspace.sharedWorkspace()
    for runningApp in workspace.runningApplications():
        if runningApp.localizedName() == app:
            pid = runningApp.processIdentifier()
            break
    else:
        return False

    with _WindowLock():
        changed = False
        for _ in range(3):
            windowRef = _getWindow(pid)
            if windowRef is None:
                return changed
            _, isFullscreen = AXUIElementCopyAttributeValue(windowRef, "AXFullScreen", None)
            onDisplay = _windowOnDisplay(windowRef, displayBounds)
            if onDisplay and isFullscreen:
                return changed

            changed = True
            if not onDisplay:
                #fullscreen windows can't be moved, so leave fullscreen first
                if isFullscreen:
                    _exitFullscreen(windowRef)
                AXUIElementSetAttributeValue(windowRef, "AXPosition", AXValueCreate(kAXValueCGPointType, CGPoint(dx, dy)))
                AXUIElementSetAttributeValue(windowRef, "AXSize", AXValueCreate(kAXValueCGSizeType, CGSize(dw, dh)))
                if not _waitForWindowOnDisplay(windowRef, displayBounds):
                    continue
            #fullscreen on the virtual display, so there is no title bar or menu bar
            AXUIElementSetAttributeValue(windowRef, "AXFullScreen", True)
            _waitForFullscreen(windowRef, True)
            #wait for the fullscreen animation to finish, then check it stayed
            time.sleep(1.5)
        return changed

# Set the functions to use macOS implementations
openApp = openAppMac
isAppOpen = isAppOpenMac
isAppFocused = isAppFocusedMac
maximiseAppWindow = maximiseAppWindowMac
setAppFullscreen = setAppFullscreenMac
moveAppToMacroDisplay = moveAppToMacroDisplayMac
