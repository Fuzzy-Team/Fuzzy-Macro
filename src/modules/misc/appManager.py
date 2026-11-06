import os
import subprocess
import sys
import pyautogui as pag
IS_WINDOWS = sys.platform == "win32"
if not IS_WINDOWS:
    from AppKit import NSWorkspace
    from ApplicationServices import AXUIElementCreateApplication, AXUIElementSetAttributeValue, AXUIElementCopyAttributeValue, AXValueCreate, kAXValueCGPointType, kAXValueCGSizeType, AXUIElementCopyAttributeNames
    from Quartz import CGPoint, CGSize
mw,mh = pag.size()

def runAppleScript(code):
    cmd = ''' osascript -e '{}' '''.format(code)
    os.system(cmd)

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

# ---- Windows ----
# Roblox is found by its process, not its window title, so a browser tab named "Roblox" never matches.
ROBLOX_EXE = "RobloxPlayerBeta.exe"

if IS_WINDOWS:
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    HWND = wintypes.HWND
    user32.EnumWindows.argtypes = [ctypes.WINFUNCTYPE(wintypes.BOOL, HWND, wintypes.LPARAM), wintypes.LPARAM]
    user32.IsWindowVisible.argtypes = [HWND]
    user32.GetWindowThreadProcessId.argtypes = [HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetForegroundWindow.restype = HWND
    user32.ShowWindow.argtypes = [HWND, ctypes.c_int]
    user32.SetForegroundWindow.argtypes = [HWND]
    user32.GetClientRect.argtypes = [HWND, ctypes.POINTER(wintypes.RECT)]
    user32.ClientToScreen.argtypes = [HWND, ctypes.POINTER(wintypes.POINT)]
    user32.IsIconic.argtypes = [HWND]

def _robloxPids():
    out = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {ROBLOX_EXE}", "/FO", "CSV", "/NH"],
                         capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW).stdout
    pids = set()
    for line in out.splitlines():
        cols = [c.strip('"') for c in line.split('","')]
        if len(cols) > 1 and cols[0].strip('"').lower() == ROBLOX_EXE.lower():
            pids.add(int(cols[1]))
    return pids

def _robloxWindows():
    """Visible top level windows owned by the Roblox player."""
    pids = _robloxPids()
    found = []
    if not pids:
        return found
    def visit(hwnd, _):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value in pids and user32.IsWindowVisible(hwnd):
            found.append(hwnd)
        return True
    user32.EnumWindows(ctypes.WINFUNCTYPE(wintypes.BOOL, HWND, wintypes.LPARAM)(visit), 0)
    return found

def _clientBounds(hwnd):
    """x, y, w, h of the window's content, excluding the title bar and borders."""
    rect = wintypes.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(rect))
    origin = wintypes.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(origin))
    return origin.x, origin.y, rect.right, rect.bottom

def isAppOpenWin(app="roblox"):
    return bool(_robloxPids())

def isAppFocusedWin(app="Roblox"):
    foreground = user32.GetForegroundWindow()
    if not foreground:
        return False
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(foreground, ctypes.byref(pid))
    return pid.value in _robloxPids()

def openAppWin(app="Roblox"):
    windows = _robloxWindows()
    if not windows:
        return False
    hwnd = windows[0]
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, 9) #SW_RESTORE
    user32.SetForegroundWindow(hwnd)
    return True

def openDeeplinkWin(link):
    os.startfile(link)

def closeAppWin(app):
    subprocess.call(["taskkill", "/F", "/IM", ROBLOX_EXE], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW)

def getWindowSizeWin(windowName):
    best = None
    for hwnd in _robloxWindows():
        x, y, w, h = _clientBounds(hwnd)
        if w >= 200 and h >= 200 and (best is None or w * h > best[2] * best[3]):
            best = (x, y, w, h)
    # Window not found or minimised, assume fullscreen
    return best or (0, 0, mw, mh)

def maximiseAppWindowWin(app="Roblox"):
    for hwnd in _robloxWindows():
        user32.ShowWindow(hwnd, 3) #SW_MAXIMIZE

if IS_WINDOWS:
    openApp = openAppWin
    isAppOpen = isAppOpenWin
    isAppFocused = isAppFocusedWin
    maximiseAppWindow = maximiseAppWindowWin
    setAppFullscreen = lambda app="Roblox", fullscreen=True: maximiseAppWindowWin(app)
    openDeeplink = openDeeplinkWin
    closeApp = closeAppWin
    getWindowSize = getWindowSizeWin
else:
    openApp = openAppMac
    isAppOpen = isAppOpenMac
    isAppFocused = isAppFocusedMac
    maximiseAppWindow = maximiseAppWindowMac
    setAppFullscreen = setAppFullscreenMac
