import os
import subprocess
import time
import pyautogui as pag
from modules.screen import virtual_display
from AppKit import NSWorkspace
from ApplicationServices import AXUIElementCreateApplication, AXUIElementSetAttributeValue, AXUIElementCopyAttributeValue, AXValueCreate, kAXValueCGPointType, kAXValueCGSizeType, AXUIElementCopyAttributeNames
from Quartz import CGPoint, CGSize
mw,mh = pag.size()

def runAppleScript(code):
    cmd = ''' osascript -e '{}' '''.format(code)
    os.system(cmd)

def isAppOpenMac(app="roblox"):
    processName = "RobloxPlayer" if app.casefold() == "roblox" else app
    return subprocess.run(["pgrep", "-ix", processName], stdout=subprocess.DEVNULL).returncode == 0

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
    for runningApp in NSWorkspace.sharedWorkspace().runningApplications():
        if (runningApp.localizedName() or "").casefold() == app.casefold():
            pid = runningApp.processIdentifier()
            if not runningApp.terminate():
                raise RuntimeError("Could not close {}.".format(app))
            deadline = time.monotonic() + 10
            while True:
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    break
                if time.monotonic() >= deadline:
                    raise RuntimeError("{} did not exit. Close it before restarting the macro.".format(app))
                time.sleep(0.1)

def getWindowSize(windowName):
    if virtual_display.active() and "roblox" in windowName.lower():
        virtual_display.state(require_window=True)
        return 0, 0, virtual_display.WIDTH, virtual_display.HEIGHT
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
    if virtual_display.active() and app.lower() == "roblox":
        virtual_display.prepare_window()
        return
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
    if virtual_display.active() and app.lower() == "roblox":
        virtual_display.prepare_window()
        return
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

# Set the functions to use macOS implementations
openApp = openAppMac
isAppOpen = isAppOpenMac
isAppFocused = isAppFocusedMac
maximiseAppWindow = maximiseAppWindowMac
setAppFullscreen = setAppFullscreenMac
