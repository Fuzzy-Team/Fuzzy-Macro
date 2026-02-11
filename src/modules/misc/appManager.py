import sys
import re
import os
import subprocess
from modules.misc.appleScript import runAppleScript
import pygetwindow as gw
import pyautogui as pag
from AppKit import NSWorkspace
from ApplicationServices import AXUIElementIsAttributeSettable, AXUIElementCreateApplication, kAXErrorSuccess, AXUIElementSetAttributeValue, AXUIElementCopyAttributeValue, AXValueCreate, kAXValueCGPointType, kAXValueCGSizeType, AXUIElementCopyAttributeNames
from Quartz import CGPoint, CGSize
from CoreFoundation import CFRelease
mw,mh = pag.size()

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

# Set the functions to use macOS implementations
openApp = openAppMac
isAppOpen = isAppOpenMac
maximiseAppWindow = maximiseAppWindowMac
setAppFullscreen = setAppFullscreenMac
