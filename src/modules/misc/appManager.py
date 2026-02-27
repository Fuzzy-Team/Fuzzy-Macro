import sys
import re
import os
import subprocess
import platform
import pygetwindow as gw
import pyautogui as pag

_IS_WINDOWS = platform.system() == "Windows"
mw, mh = pag.size()

if _IS_WINDOWS:
    def isAppOpen(app="roblox"):
        try:
            output = subprocess.check_output(
                ["tasklist", "/FI", f"IMAGENAME eq {app}.exe"],
                stderr=subprocess.DEVNULL
            ).decode("utf-8", errors="ignore")
            return app.lower() in output.lower()
        except Exception:
            return False

    def openApp(app="Roblox"):
        try:
            import ctypes
            ctypes.windll.shell32.ShellExecuteW(None, "open", app, None, None, 1)
            return True
        except Exception:
            return False

    def openDeeplink(link):
        import subprocess
        try:
            subprocess.Popen(["cmd", "/c", "start", "", link], shell=False)
        except Exception:
            os.startfile(link)

    def closeApp(app):
        try:
            subprocess.call(["taskkill", "/IM", f"{app}.exe"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

    def forceQuitApp(app):
        """Forcefully terminate an app/process on Windows."""
        try:
            subprocess.call(["taskkill", "/F", "/IM", f"{app}.exe"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

    def getWindowSize(windowName):
        try:
            import ctypes
            user32 = ctypes.windll.user32

            def _enum_callback(hwnd, results):
                if not user32.IsWindowVisible(hwnd):
                    return True
                length = user32.GetWindowTextLengthW(hwnd)
                if length == 0:
                    return True
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                title = buf.value
                if windowName.lower() in title.lower():
                    rect = ctypes.wintypes.RECT()
                    user32.GetWindowRect(hwnd, ctypes.byref(rect))
                    results.append((rect.left, rect.top,
                                    rect.right - rect.left,
                                    rect.bottom - rect.top))
                return True

            WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.py_object)
            results = []
            user32.EnumWindows(WNDENUMPROC(_enum_callback), results)
            if results:
                return results[0]
        except Exception:
            pass
        # Fallback: full screen
        return 0, 0, mw, mh

    def maximiseAppWindow(app="Roblox"):
        try:
            import ctypes
            SW_MAXIMIZE = 3
            user32 = ctypes.windll.user32

            def _enum_callback(hwnd, _):
                if not user32.IsWindowVisible(hwnd):
                    return True
                length = user32.GetWindowTextLengthW(hwnd)
                if length == 0:
                    return True
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                title = buf.value
                if app.lower() in title.lower():
                    user32.ShowWindow(hwnd, SW_MAXIMIZE)
                    return False
                return True

            WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.py_object)
            user32.EnumWindows(WNDENUMPROC(_enum_callback), None)
        except Exception:
            pass

    def setAppFullscreen(app="Roblox", fullscreen=True):
        if fullscreen:
            maximiseAppWindow(app)

else:
    from modules.misc.appleScript import runAppleScript
    from AppKit import NSWorkspace
    from ApplicationServices import (AXUIElementIsAttributeSettable,
                                      AXUIElementCreateApplication, kAXErrorSuccess,
                                      AXUIElementSetAttributeValue,
                                      AXUIElementCopyAttributeValue, AXValueCreate,
                                      kAXValueCGPointType, kAXValueCGSizeType,
                                      AXUIElementCopyAttributeNames)
    from Quartz import CGPoint, CGSize
    from CoreFoundation import CFRelease

    def isAppOpen(app="roblox"):
        tmp = os.popen("ps -Af").read()
        return app in tmp[:]

    def openApp(app="Roblox"):
        if not isAppOpen(app): return False
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

    def maximiseAppWindow(app="Roblox"):
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

    setAppFullscreen = setAppFullscreenMac