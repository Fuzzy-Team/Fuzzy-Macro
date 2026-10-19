'''
The display the macro drives Roblox on.

All macro coordinates (window bounds, screenshot regions, mouse positions) are
relative to the top-left corner of this display. Normally that is the main
display, whose origin is (0, 0), so they are plain global coordinates. When
Roblox runs on the Fuzzy Macro virtual display, the low-level screenshot and
mouse helpers use toGlobal/toLocal to translate.

The display ID is stored in screen.txt by screenData.setScreenData so every
macro process agrees on which display to use.
'''
import os
import time
import Quartz

_screenPath = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../data/user/screen.txt'))
_REFRESH_SECONDS = 1.0
_cache = {"checked": 0.0, "mtime": None, "display_id": 0, "bounds": None}


def _readDisplayID():
    try:
        mtime = os.path.getmtime(_screenPath)
    except OSError:
        _cache["mtime"] = None
        _cache["display_id"] = 0
        return 0
    if mtime != _cache["mtime"]:
        _cache["mtime"] = mtime
        displayID = 0
        try:
            with open(_screenPath) as f:
                for line in f:
                    key, _, value = line.strip().partition("=")
                    if key == "display_id":
                        displayID = int(value or 0)
                        break
        except (OSError, ValueError):
            displayID = 0
        _cache["display_id"] = displayID
    return _cache["display_id"]


def _isActive(displayID):
    err, ids, count = Quartz.CGGetActiveDisplayList(32, None, None)
    return err == 0 and displayID in ids[:count]


def displayID():
    '''Display the macro runs on. Falls back to the main display if the
    configured display no longer exists.'''
    bounds()
    return _cache["active_id"]


def bounds():
    '''(x, y, width, height) of the macro display in global points.'''
    now = time.monotonic()
    if _cache["bounds"] is not None and now - _cache["checked"] < _REFRESH_SECONDS:
        return _cache["bounds"]
    targetID = _readDisplayID()
    if not targetID or not _isActive(targetID):
        targetID = Quartz.CGMainDisplayID()
    rect = Quartz.CGDisplayBounds(targetID)
    _cache["active_id"] = targetID
    _cache["bounds"] = (int(rect.origin.x), int(rect.origin.y), int(rect.size.width), int(rect.size.height))
    _cache["checked"] = now
    return _cache["bounds"]


def refresh():
    '''Forget cached bounds, e.g. after the virtual display was created.'''
    _cache["mtime"] = None
    _cache["bounds"] = None


def origin():
    x, y, _, _ = bounds()
    return x, y


def size():
    _, _, w, h = bounds()
    return w, h


def isMainDisplay():
    return origin() == (0, 0)


def toGlobal(x, y):
    ox, oy = origin()
    return x + ox, y + oy


def toLocal(x, y):
    ox, oy = origin()
    return x - ox, y - oy
