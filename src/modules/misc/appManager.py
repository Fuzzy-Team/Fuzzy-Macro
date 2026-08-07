import os
import platform
import subprocess

import pyautogui as pag

_IS_WINDOWS = platform.system() == "Windows"
mw, mh = pag.size()


if _IS_WINDOWS:
    # Roblox Windows clients use RobloxPlayerBeta.exe, not "roblox.exe".
    _ROBLOX_PROCESS_NAMES = (
        "RobloxPlayerBeta.exe",
        "RobloxPlayer.exe",
        "Roblox.exe",
    )

    def _is_roblox_app(app):
        name = (app or "").strip().lower().replace(".exe", "")
        return name in ("roblox", "robloxplayerbeta", "robloxplayer")

    def _process_names_for_app(app):
        if _is_roblox_app(app):
            return _ROBLOX_PROCESS_NAMES
        raw = (app or "").strip()
        if not raw:
            return ()
        if raw.lower().endswith(".exe"):
            return (raw,)
        return (f"{raw}.exe",)

    def _tasklist_has_image(image_name):
        try:
            output = subprocess.check_output(
                ["tasklist", "/FI", f"IMAGENAME eq {image_name}"],
                stderr=subprocess.DEVNULL,
            ).decode("utf-8", errors="ignore")
            return image_name.lower() in output.lower()
        except Exception:
            return False

    def _enum_windows_matching(app_or_title, callback):
        """Call callback(hwnd, title) for visible windows matching app/title. Stop if callback returns False."""
        import ctypes
        import ctypes.wintypes

        user32 = ctypes.windll.user32
        needle = (app_or_title or "").strip().lower()
        search_terms = [needle] if needle else []
        if needle in ("roblox", "roblox roblox") or _is_roblox_app(app_or_title):
            search_terms = ["roblox"]

        def _enum_callback(hwnd, _):
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
                if callback(hwnd, title) is False:
                    return False
            return True

        enum_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.c_void_p)
        user32.EnumWindows(enum_proc(_enum_callback), None)

    def _focus_window_by_app(app="Roblox"):
        try:
            import ctypes

            user32 = ctypes.windll.user32
            focused = {"ok": False}

            def _focus(hwnd, _title):
                user32.ShowWindow(hwnd, 9)  # SW_RESTORE
                user32.SetForegroundWindow(hwnd)
                focused["ok"] = True
                return False

            _enum_windows_matching(app, _focus)
            return focused["ok"]
        except Exception:
            return False

    def isAppOpen(app="roblox"):
        try:
            for image_name in _process_names_for_app(app):
                if _tasklist_has_image(image_name):
                    return True
            # Fallback: Roblox may be present as a titled window even if process filter fails
            if _is_roblox_app(app):
                found = {"ok": False}

                def _mark(hwnd, _title):
                    found["ok"] = True
                    return False

                _enum_windows_matching("roblox", _mark)
                return found["ok"]
            return False
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
            app_name = (app or "").lower().replace(".exe", "")
            if _is_roblox_app(app):
                return "roblox" in title
            return app_name in title or title in app_name
        except Exception:
            return False

    def openApp(app="Roblox"):
        # Match macOS semantics: only focus an already-running app.
        # Returning False when Roblox is closed lets callers trigger rejoin.
        try:
            if _is_roblox_app(app):
                if not isAppOpen("roblox"):
                    return False
                return _focus_window_by_app("Roblox")

            if not isAppOpen(app):
                return False
            return _focus_window_by_app(app)
        except Exception:
            return False

    def openDeeplink(link):
        try:
            subprocess.Popen(["cmd", "/c", "start", "", link], shell=False)
        except Exception:
            os.startfile(link)

    def closeApp(app):
        for image_name in _process_names_for_app(app):
            try:
                subprocess.call(
                    ["taskkill", "/IM", image_name],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception:
                pass

    def forceQuitApp(app):
        for image_name in _process_names_for_app(app):
            try:
                subprocess.call(
                    ["taskkill", "/F", "/IM", image_name],
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
            results = []

            def _collect(hwnd, _title):
                rect = ctypes.wintypes.RECT()
                user32.GetWindowRect(hwnd, ctypes.byref(rect))
                width = rect.right - rect.left
                height = rect.bottom - rect.top
                # Prefer the main game window over tiny helper windows
                if width >= 200 and height >= 200:
                    results.append((rect.left, rect.top, width, height))
                return True

            _enum_windows_matching(windowName, _collect)
            if results:
                # Largest matching window is usually the Roblox client
                results.sort(key=lambda r: r[2] * r[3], reverse=True)
                return results[0]
        except Exception:
            pass
        return 0, 0, mw, mh

    def maximiseAppWindow(app="Roblox"):
        try:
            import ctypes

            sw_maximize = 3
            user32 = ctypes.windll.user32

            def _maximize(hwnd, _title):
                user32.ShowWindow(hwnd, sw_maximize)
                return False

            _enum_windows_matching(app, _maximize)
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
