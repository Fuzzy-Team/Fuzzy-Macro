import os
import platform
import subprocess

import pyautogui as pag

_IS_WINDOWS = platform.system() == "Windows"
mw, mh = pag.size()


if _IS_WINDOWS:
    def isAppOpen(app="roblox"):
        try:
            output = subprocess.check_output(
                ["tasklist", "/FI", f"IMAGENAME eq {app}.exe"],
                stderr=subprocess.DEVNULL,
            ).decode("utf-8", errors="ignore")
            return app.lower() in output.lower()
        except Exception:
            return False

    def isAppFocused(app="Roblox"):
        try:
            import ctypes

            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            length = user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                return False
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            title = buf.value.lower()
            app_name = (app or "").lower()
            return app_name in title or title in app_name
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
        try:
            subprocess.Popen(["cmd", "/c", "start", "", link], shell=False)
        except Exception:
            os.startfile(link)

    def closeApp(app):
        try:
            subprocess.call(
                ["taskkill", "/IM", f"{app}.exe"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass

    def forceQuitApp(app):
        try:
            subprocess.call(
                ["taskkill", "/F", "/IM", f"{app}.exe"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass

    def getWindowSize(windowName):
        try:
            import ctypes
            import ctypes.wintypes

            user32 = ctypes.windll.user32
            normalized_name = (windowName or "").strip().lower()
            search_terms = [normalized_name] if normalized_name else []
            if normalized_name == "roblox roblox":
                search_terms.append("roblox")

            def _enum_callback(hwnd, results):
                if not user32.IsWindowVisible(hwnd):
                    return True
                length = user32.GetWindowTextLengthW(hwnd)
                if length == 0:
                    return True
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                title = buf.value
                title_l = title.lower()
                if any(term and term in title_l for term in search_terms):
                    rect = ctypes.wintypes.RECT()
                    user32.GetWindowRect(hwnd, ctypes.byref(rect))
                    results.append((
                        rect.left,
                        rect.top,
                        rect.right - rect.left,
                        rect.bottom - rect.top,
                    ))
                return True

            callback = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.py_object)
            results = []
            user32.EnumWindows(callback(_enum_callback), results)
            if results:
                return results[0]
        except Exception:
            pass
        return 0, 0, mw, mh

    def maximiseAppWindow(app="Roblox"):
        try:
            import ctypes
            import ctypes.wintypes

            sw_maximize = 3
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
                    user32.ShowWindow(hwnd, sw_maximize)
                    return False
                return True

            callback = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.py_object)
            user32.EnumWindows(callback(_enum_callback), None)
        except Exception:
            pass

    def setAppFullscreen(app="Roblox", fullscreen=True):
        if fullscreen:
            maximiseAppWindow(app)

else:
    from ApplicationServices import (
        AXUIElementCopyAttributeNames,
        AXUIElementCopyAttributeValue,
        AXUIElementCreateApplication,
        AXUIElementSetAttributeValue,
        AXValueCreate,
        kAXValueCGPointType,
        kAXValueCGSizeType,
    )
    from AppKit import NSWorkspace
    from CoreFoundation import CFRelease
    from Quartz import CGPoint, CGSize

    from modules.misc.appleScript import runAppleScript

    def isAppOpen(app="roblox"):
        tmp = os.popen("ps -Af").read()
        return app in tmp[:]

    def isAppFocused(app="Roblox"):
        try:
            workspace = NSWorkspace.sharedWorkspace()
            frontmost = workspace.frontmostApplication()
            if not frontmost:
                return False
            frontmost_name = (frontmost.localizedName() or "").lower()
            app_name = (app or "").lower()
            return app_name in frontmost_name or frontmost_name in app_name
        except Exception:
            return False

    def openApp(app="Roblox"):
        if not isAppOpen(app):
            return False
        runAppleScript('activate application "{}"'.format(app))
        subprocess.run(["open", "-a", app])
        workspace = NSWorkspace.sharedWorkspace()
        for running_app in workspace.runningApplications():
            if running_app.localizedName() == app:
                running_app.activateWithOptions_(1 << 1)
                break
        return True

    def openDeeplink(link):
        subprocess.call(["open", link])

    def closeApp(app):
        try:
            subprocess.call(["pkill", app], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass
        os.system("""osascript -e 'quit application "Roblox"'""")

    def forceQuitApp(app):
        try:
            subprocess.call(["pkill", "-9", app], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass
        try:
            subprocess.call(["killall", "-9", app], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

    def getWindowSize(windowName):
        import Quartz

        window_list = Quartz.CGWindowListCopyWindowInfo(
            Quartz.kCGWindowListExcludeDesktopElements | Quartz.kCGWindowListOptionOnScreenOnly,
            Quartz.kCGNullWindowID,
        )

        for win in window_list:
            owner = win.get(Quartz.kCGWindowOwnerName, "")
            name = win.get(Quartz.kCGWindowName, "")
            title = f"{owner} {name}".strip()

            if windowName.lower() in title.lower():
                bounds = win.get("kCGWindowBounds", {})
                if bounds:
                    x = int(bounds.get("X", 0))
                    y = int(bounds.get("Y", 0))
                    w = int(bounds.get("Width", mw))
                    h = int(bounds.get("Height", mh))
                    return x, y, w, h

        return 0, 0, mw, mh

    def setAppFullscreen(app="Roblox", fullscreen=True):
        workspace = NSWorkspace.sharedWorkspace()
        for running_app in workspace.runningApplications():
            if running_app.localizedName() == app:
                pid = running_app.processIdentifier()
                break
        else:
            return

        app_ref = AXUIElementCreateApplication(pid)
        _, window_ref = AXUIElementCopyAttributeValue(app_ref, "AXMainWindow", None)
        AXUIElementSetAttributeValue(window_ref, "AXFullScreen", fullscreen)

    def maximiseAppWindow(app="Roblox"):
        workspace = NSWorkspace.sharedWorkspace()
        for running_app in workspace.runningApplications():
            if running_app.localizedName() == app:
                pid = running_app.processIdentifier()
                break
        else:
            return

        app_ref = AXUIElementCreateApplication(pid)
        _, window_ref = AXUIElementCopyAttributeValue(app_ref, "AXMainWindow", None)
        _, attributes = AXUIElementCopyAttributeNames(window_ref, None)
        pos = AXValueCreate(kAXValueCGPointType, CGPoint(0, 0))
        size = AXValueCreate(kAXValueCGSizeType, CGSize(mw, mh))
        AXUIElementSetAttributeValue(window_ref, "AXPosition", pos)
        AXUIElementSetAttributeValue(window_ref, "AXSize", size)
