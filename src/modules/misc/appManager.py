import os
import platform
import shutil
import subprocess

import pyautogui as pag

_IS_WINDOWS = platform.system() == "Windows"
_IS_MACOS = platform.system() == "Darwin"
_IS_LINUX = platform.system() == "Linux"
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

elif _IS_LINUX:
    # Primary Linux Roblox client is Sober; also allow Wine/Proton process names.
    _ROBLOX_PROCESS_NAMES = (
        "sober",
        "sober_services",
        "RobloxPlayerBeta",
        "RobloxPlayer",
        "Roblox",
        "roblox-player",
    )
    _HAS_XDOTOOL = shutil.which("xdotool") is not None
    _HAS_WMCTRL = shutil.which("wmctrl") is not None

    def _is_roblox_app(app):
        name = (app or "").strip().lower().replace(".exe", "")
        return name in ("roblox", "robloxplayerbeta", "robloxplayer", "sober")

    def _search_terms_for(app_or_title):
        needle = (app_or_title or "").strip().lower()
        if not needle or needle in ("roblox", "roblox roblox") or _is_roblox_app(app_or_title):
            return ("roblox", "sober")
        return (needle,)

    def _pgrep_running(pattern):
        try:
            subprocess.check_output(
                ["pgrep", "-f", pattern],
                stderr=subprocess.DEVNULL,
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
        # /proc fallback when pgrep is unavailable
        try:
            for entry in os.listdir("/proc"):
                if not entry.isdigit():
                    continue
                try:
                    with open(f"/proc/{entry}/comm", "r", encoding="utf-8", errors="ignore") as fh:
                        if pattern.lower() in fh.read().strip().lower():
                            return True
                    with open(f"/proc/{entry}/cmdline", "rb") as fh:
                        cmdline = fh.read().replace(b"\x00", b" ").decode("utf-8", errors="ignore")
                        if pattern.lower() in cmdline.lower():
                            return True
                except Exception:
                    continue
        except Exception:
            pass
        return False

    def _xdotool_window_ids(terms):
        ids = []
        if not _HAS_XDOTOOL:
            return ids
        for term in terms:
            try:
                out = subprocess.check_output(
                    ["xdotool", "search", "--name", term],
                    stderr=subprocess.DEVNULL,
                    text=True,
                )
                for wid in out.strip().splitlines():
                    if wid and wid not in ids:
                        ids.append(wid)
            except Exception:
                continue
        return ids

    def _wmctrl_windows(terms):
        """Return list of (wid_hex, x, y, w, h, title)."""
        results = []
        if not _HAS_WMCTRL:
            return results
        try:
            out = subprocess.check_output(
                ["wmctrl", "-lG"],
                stderr=subprocess.DEVNULL,
                text=True,
            )
        except Exception:
            return results
        for line in out.splitlines():
            parts = line.split(None, 7)
            if len(parts) < 8:
                continue
            wid, _desk, x, y, w, h, _host, title = parts
            title_l = title.lower()
            if any(term in title_l for term in terms):
                try:
                    results.append((wid, int(x), int(y), int(w), int(h), title))
                except ValueError:
                    continue
        return results

    def _window_geometry(wid):
        if _HAS_XDOTOOL:
            try:
                out = subprocess.check_output(
                    ["xdotool", "getwindowgeometry", "--shell", str(wid)],
                    stderr=subprocess.DEVNULL,
                    text=True,
                )
                geo = {}
                for line in out.splitlines():
                    if "=" in line:
                        key, value = line.split("=", 1)
                        geo[key.strip()] = int(value.strip())
                return geo.get("X", 0), geo.get("Y", 0), geo.get("WIDTH", mw), geo.get("HEIGHT", mh)
            except Exception:
                pass
        return None

    def _largest_matching_geometry(app_or_title):
        terms = _search_terms_for(app_or_title)
        candidates = []

        for wid in _xdotool_window_ids(terms):
            geo = _window_geometry(wid)
            if geo and geo[2] >= 200 and geo[3] >= 200:
                candidates.append(geo)

        for _wid, x, y, w, h, _title in _wmctrl_windows(terms):
            if w >= 200 and h >= 200:
                candidates.append((x, y, w, h))

        if not candidates:
            return None
        candidates.sort(key=lambda r: r[2] * r[3], reverse=True)
        return candidates[0]

    def _focus_window(app_or_title="Roblox"):
        terms = _search_terms_for(app_or_title)
        for wid in _xdotool_window_ids(terms):
            try:
                subprocess.call(
                    ["xdotool", "windowactivate", "--sync", str(wid)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return True
            except Exception:
                continue
        for wid, *_rest in _wmctrl_windows(terms):
            try:
                subprocess.call(
                    ["wmctrl", "-i", "-a", wid],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return True
            except Exception:
                continue
        return False

    def isAppOpen(app="roblox"):
        try:
            if _is_roblox_app(app):
                for name in _ROBLOX_PROCESS_NAMES:
                    if _pgrep_running(name):
                        return True
                return _largest_matching_geometry("roblox") is not None
            return _pgrep_running(app)
        except Exception:
            return False

    def isAppFocused(app="Roblox"):
        try:
            terms = _search_terms_for(app)
            if _HAS_XDOTOOL:
                try:
                    active = subprocess.check_output(
                        ["xdotool", "getactivewindow", "getwindowname"],
                        stderr=subprocess.DEVNULL,
                        text=True,
                    ).strip().lower()
                    return any(term in active for term in terms)
                except Exception:
                    pass
            if _HAS_WMCTRL:
                try:
                    out = subprocess.check_output(
                        ["xprop", "-root", "_NET_ACTIVE_WINDOW"],
                        stderr=subprocess.DEVNULL,
                        text=True,
                    )
                    active_id = out.strip().split()[-1].lower() if out.strip() else ""
                    if active_id and active_id != "0x0":
                        for wid, *_rest, title in _wmctrl_windows(terms):
                            if wid.lower() == active_id or active_id in wid.lower():
                                return True
                except Exception:
                    pass
            return False
        except Exception:
            return False

    def openApp(app="Roblox"):
        try:
            if _is_roblox_app(app):
                if not isAppOpen("roblox"):
                    return False
                return _focus_window("Roblox")
            if not isAppOpen(app):
                return False
            return _focus_window(app)
        except Exception:
            return False

    def openDeeplink(link):
        opener = shutil.which("xdg-open") or "xdg-open"
        try:
            subprocess.Popen([opener, link], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            subprocess.Popen(["gio", "open", link], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def closeApp(app):
        names = _ROBLOX_PROCESS_NAMES if _is_roblox_app(app) else ((app or "").strip(),)
        for name in names:
            if not name:
                continue
            try:
                subprocess.call(
                    ["pkill", "-f", name],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception:
                pass

    def forceQuitApp(app):
        names = _ROBLOX_PROCESS_NAMES if _is_roblox_app(app) else ((app or "").strip(),)
        for name in names:
            if not name:
                continue
            try:
                subprocess.call(
                    ["pkill", "-9", "-f", name],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception:
                pass
            try:
                subprocess.call(
                    ["killall", "-9", name],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except Exception:
                pass

    def getWindowSize(windowName):
        geo = _largest_matching_geometry(windowName)
        if geo:
            return geo
        return 0, 0, mw, mh

    def maximiseAppWindow(app="Roblox"):
        terms = _search_terms_for(app)
        for wid in _xdotool_window_ids(terms):
            try:
                subprocess.call(
                    ["xdotool", "windowsize", str(wid), str(mw), str(mh)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                subprocess.call(
                    ["xdotool", "windowmove", str(wid), "0", "0"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return
            except Exception:
                continue
        for wid, *_rest in _wmctrl_windows(terms):
            try:
                subprocess.call(
                    ["wmctrl", "-i", "-r", wid, "-b", "add,maximized_vert,maximized_horz"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return
            except Exception:
                continue

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
