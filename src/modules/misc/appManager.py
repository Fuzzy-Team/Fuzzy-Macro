import os
import subprocess
import time
import pyautogui as pag
from modules.screen import virtual_display
from AppKit import NSWorkspace
mw,mh = pag.size()

def runAppleScript(code):
    cmd = ''' osascript -e '{}' '''.format(code)
    os.system(cmd)

def isAppOpenMac(app="roblox"):
    tmp = os.popen("ps -Af").read()
    return app.lower() in tmp.lower()

def openWith(*args):
    """Run macOS open. It can hang when Launch Services is stuck, so give up after 30 seconds
    instead of freezing the main app's crash recovery or the macro's rejoin."""
    try:
        subprocess.run(["open", *args], timeout=30)
    except subprocess.TimeoutExpired:
        print("open timed out")

def openAppMac(app="Roblox"):
    if not isAppOpenMac(app): return False
    runAppleScript('activate application "{}"'.format(app))
    openWith("-a", app)
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
    openWith(link)

def closeApp(app):
    pids = [
        runningApp.processIdentifier()
        for runningApp in NSWorkspace.sharedWorkspace().runningApplications()
        if (runningApp.localizedName() or "").casefold() == app.casefold()
    ]
    try:
        subprocess.call(["pkill", app], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
    except Exception:
        pass
    try:
        subprocess.run(["osascript", "-e", 'quit application "{}"'.format(app)], timeout=10)
    except subprocess.TimeoutExpired:
        print("quit application timed out")
    deadline = time.monotonic() + 10
    for pid in pids:
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


# Set the functions to use macOS implementations
openApp = openAppMac
isAppOpen = isAppOpenMac
isAppFocused = isAppFocusedMac
