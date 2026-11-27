import ctypes
import os
import subprocess
import sys
import time
import pyautogui as pag
from modules.screen import virtual_display
IS_WINDOWS = sys.platform == "win32"
if not IS_WINDOWS:
    from AppKit import NSWorkspace
mw,mh = pag.size()

def runAppleScript(code):
    cmd = ''' osascript -e '{}' '''.format(code)
    os.system(cmd)

def isAppOpenMac(app="roblox"):
    tmp = os.popen("ps -Af").read()
    return app.lower() in tmp.lower()

def _promptAccessibility(ax):
    """Best-effort native Accessibility prompt; callers report missing even if this fails."""
    cf = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
    cf.CFDictionaryCreate.restype = ctypes.c_void_p
    cf.CFDictionaryCreate.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_void_p), ctypes.c_long, ctypes.c_void_p, ctypes.c_void_p]
    cf.CFRelease.restype = None
    cf.CFRelease.argtypes = [ctypes.c_void_p]
    ax.AXIsProcessTrustedWithOptions.restype = ctypes.c_bool
    ax.AXIsProcessTrustedWithOptions.argtypes = [ctypes.c_void_p]

    key = ctypes.c_void_p.in_dll(ax, "kAXTrustedCheckOptionPrompt")
    value = ctypes.c_void_p.in_dll(cf, "kCFBooleanTrue")
    if not key.value or not value.value:
        return
    keys = (ctypes.c_void_p * 1)(key)
    values = (ctypes.c_void_p * 1)(value)
    options = None
    try:
        options = cf.CFDictionaryCreate(
            None, keys, values, 1,
            ctypes.byref(ctypes.c_void_p.in_dll(cf, "kCFTypeDictionaryKeyCallBacks")),
            ctypes.byref(ctypes.c_void_p.in_dll(cf, "kCFTypeDictionaryValueCallBacks")),
        )
        if options:
            ax.AXIsProcessTrustedWithOptions(options)
    finally:
        if options:
            cf.CFRelease(options)

def missingPermissions():
    """Names of the macOS permissions Terminal still needs. An API missing on an older macOS is skipped."""
    missing = []
    try:
        ax = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices")
        ax.AXIsProcessTrusted.restype = ctypes.c_bool
        if not ax.AXIsProcessTrusted():
            missing.append("Accessibility")
            try:
                _promptAccessibility(ax)
            except Exception:
                pass  # prompt setup is best-effort; Accessibility is already reported
    except (OSError, AttributeError):
        pass  # framework or function missing on this macOS, so skip the check
    try:
        cg = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")
        preflight = getattr(cg, "CGPreflightScreenCaptureAccess", None)
        request = getattr(cg, "CGRequestScreenCaptureAccess", None)
        if preflight is None and request is None:
            raise AttributeError  # neither API exists on this macOS
        granted = False
        if preflight is not None:
            preflight.restype = ctypes.c_bool
            granted = bool(preflight())
        if not granted and request is not None:
            # Preflight never prompts. Requesting also adds Terminal to the Screen Recording list.
            request.restype = ctypes.c_bool
            granted = bool(request())
        if not granted:
            missing.append("Screen & System Audio Recording")
    except (OSError, AttributeError):
        pass  # framework or function missing on this macOS, so skip the check
    return missing

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

def enterRobloxFullscreen():
    """Make a windowed Roblox fullscreen so its title bar is gone and screen coordinates start at the top of the game."""
    import Quartz
    import ApplicationServices as AX
    # The pid comes from the live window list. NSWorkspace's list goes stale in the macro's child process.
    for win in Quartz.CGWindowListCopyWindowInfo(Quartz.kCGWindowListExcludeDesktopElements | Quartz.kCGWindowListOptionOnScreenOnly, Quartz.kCGNullWindowID):
        if f'{win.get(Quartz.kCGWindowOwnerName, "")} {win.get(Quartz.kCGWindowName, "")}'.strip() == "Roblox Roblox":
            err, windows = AX.AXUIElementCopyAttributeValue(AX.AXUIElementCreateApplication(win[Quartz.kCGWindowOwnerPID]), "AXWindows", None)
            if err == 0 and windows:
                err, fullscreen = AX.AXUIElementCopyAttributeValue(windows[0], "AXFullScreen", None)
                if err == 0 and not fullscreen:
                    err = AX.AXUIElementSetAttributeValue(windows[0], "AXFullScreen", True)
                    if err != 0:
                        print(f"Roblox fullscreen request failed with AX error {err}; window bounds may include the title bar.")
                    time.sleep(1.5) # the fullscreen animation
            return


# ---- Windows ----
# Roblox is found by its process, not its window title, so a browser tab named "Roblox" never matches.
# The website installer runs RobloxPlayerBeta.exe. The Microsoft Store version runs Windows10Universal.exe
# inside a window that ApplicationFrameHost.exe owns.
ROBLOX_EXES = ("RobloxPlayerBeta.exe", "Windows10Universal.exe")

if IS_WINDOWS:
    import psutil
    import pydirectinput
    from ctypes import wintypes
    user32 = ctypes.windll.user32

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
    user32.GetAncestor.argtypes = [HWND, wintypes.UINT]
    user32.GetAncestor.restype = HWND
    user32.GetClassNameW.argtypes = [HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowTextW.argtypes = [HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.FindWindowExW.argtypes = [HWND, HWND, wintypes.LPCWSTR, wintypes.LPCWSTR]
    user32.FindWindowExW.restype = HWND
    user32.GetWindowLongW.argtypes = [HWND, ctypes.c_int]
    user32.GetWindowLongW.restype = ctypes.c_long

def _robloxPids():
    names = {exe.lower() for exe in ROBLOX_EXES}
    return {process.pid for process in psutil.process_iter(["name"]) if (process.info["name"] or "").lower() in names}

def _windowText(hwnd, read):
    buffer = ctypes.create_unicode_buffer(256)
    read(hwnd, buffer, 256)
    return buffer.value

def _storeRobloxContent(hwnd):
    """The Store version's drawing area, or None if hwnd is not its window frame."""
    if _windowText(hwnd, user32.GetClassNameW) != "ApplicationFrameWindow" or _windowText(hwnd, user32.GetWindowTextW) != "Roblox":
        return None
    return user32.FindWindowExW(hwnd, None, "ApplicationFrameInputSinkWindow", None) or None

def _robloxWindows():
    """Visible windows of the Roblox player. For the Store version this is its content window inside the frame."""
    pids = _robloxPids()
    found = []
    if not pids:
        return found
    def visit(hwnd, _):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not user32.IsWindowVisible(hwnd):
            return True
        if pid.value in pids:
            found.append(hwnd)
        elif content := _storeRobloxContent(hwnd):
            found.append(content)
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

def hasRobloxWindow():
    """False when Roblox is closed, including when only its tray icon is left."""
    return bool(_robloxWindows())

def isAppFocusedWin(app="Roblox"):
    foreground = user32.GetForegroundWindow()
    if not foreground:
        return False
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(foreground, ctypes.byref(pid))
    return pid.value in _robloxPids() or any(user32.GetAncestor(hwnd, 2) == foreground for hwnd in _robloxWindows())

def openAppWin(app="Roblox"):
    windows = _robloxWindows()
    if not windows:
        return False
    hwnd = user32.GetAncestor(windows[0], 2) #GA_ROOT: the Store version's frame, not its content window
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, 9) #SW_RESTORE
    user32.SetForegroundWindow(hwnd)
    return True

def openDeeplinkWin(link):
    os.startfile(link)

def closeAppWin(app):
    subprocess.call(["taskkill", "/F"] + [arg for exe in ROBLOX_EXES for arg in ("/IM", exe)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW)

def getWindowSizeWin(windowName):
    best = None
    for hwnd in _robloxWindows():
        x, y, w, h = _clientBounds(hwnd)
        if w >= 200 and h >= 200 and (best is None or w * h > best[2] * best[3]):
            best = (x, y, w, h)
    # Window not found or minimised, assume fullscreen
    return best or (0, 0, mw, mh)

_fullscreenRequested = None #the window F11 was last pressed for

def enterRobloxFullscreenWin():
    """Press F11 for a windowed Roblox, which has a title bar. F11 only toggles, so it is never pressed
    for a window without a title bar or one it already pressed it for: a wrong guess would flip it back out."""
    global _fullscreenRequested
    windows = _robloxWindows()
    if not windows:
        return
    root = user32.GetAncestor(windows[0], 2) #GA_ROOT: the Store version's frame, not its content window
    if root == _fullscreenRequested or not user32.GetWindowLongW(root, -16) & 0xC00000: #GWL_STYLE, WS_CAPTION
        return
    openAppWin()
    time.sleep(0.3)
    if not isAppFocusedWin(): #F11 would go to another window, so try again on the next call
        return
    _fullscreenRequested = root
    pydirectinput.press("f11") #Roblox reads scancodes, which pyautogui doesn't send
    time.sleep(1.5) # the fullscreen animation

def missingPermissionsWin():
    return []

if IS_WINDOWS:
    openApp = openAppWin
    isAppOpen = isAppOpenWin
    isAppFocused = isAppFocusedWin
    openDeeplink = openDeeplinkWin
    closeApp = closeAppWin
    getWindowSize = getWindowSizeWin
    enterRobloxFullscreen = enterRobloxFullscreenWin
    missingPermissions = missingPermissionsWin
else:
    # Set the functions to use macOS implementations
    openApp = openAppMac
    isAppOpen = isAppOpenMac
    isAppFocused = isAppFocusedMac
