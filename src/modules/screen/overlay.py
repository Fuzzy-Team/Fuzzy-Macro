"""Live detection overlay: a click-through window over the game that screen capture skips.

The AI gather patterns call publish() with the boxes they just detected. A helper process
(this file run as a script) owns the window, because AppKit windows need their own main
loop. publish() writes boxes.json in a temp folder and the helper redraws from it.
"""
import atexit
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time

# Seconds a box stays on screen after the last publish, so a stalled scanner clears the overlay.
HOLD = 1.0
FILE = "boxes.json"
# The helper's error output, read when it stops.
LOG = "helper.log"
# RGB colour per box kind.
COLORS = {
    "token": (80, 220, 80),
    "target": (255, 255, 0),
    "ignored": (120, 120, 120),
    "sprinkler": (0, 180, 255),
}

_helper = {"directory": None, "process": None, "failed": False}
_lock = threading.Lock()


def publish(origin, size, boxes):
    """Show boxes at `origin` (screen points, top-left) over a `size` area. Boxes are (l, t, r, b, text, kind)."""
    # A scan that outlives its gather can overlap the next one, and both would write the same temp file.
    with _lock:
        if _helper["failed"]:
            return
        try:
            process = _helper["process"]
            if process is None:
                _start()
            elif process.poll() is not None:
                # The helper only exits on its own when AppKit is missing, so don't relaunch it.
                _fail(_helper_errors() or "the helper exited")
                return
            payload = {"time": time.time(), "x": origin[0], "y": origin[1], "w": size[0], "h": size[1], "boxes": boxes}
            path = os.path.join(_helper["directory"], FILE)
            with open(path + ".tmp", "w") as handle:
                json.dump(payload, handle)
            os.replace(path + ".tmp", path)
        except OSError as error:
            _fail(str(error))


def _fail(reason):
    """Stop publishing for the rest of the run and say why once. Gathering carries on without the overlay."""
    _helper["failed"] = True
    print(f"Detection overlay turned off: {reason}")


def _helper_errors():
    try:
        with open(os.path.join(_helper["directory"], LOG)) as handle:
            return handle.read().strip().splitlines()[-1]
    except (OSError, IndexError):
        return ""


def _start():
    _helper["directory"] = tempfile.mkdtemp(prefix="fuzzy-overlay-")
    with open(os.path.join(_helper["directory"], LOG), "w") as log:
        _helper["process"] = subprocess.Popen(
            [sys.executable, os.path.abspath(__file__), _helper["directory"], str(os.getpid())],
            stdout=subprocess.DEVNULL, stderr=log,
        )
    atexit.register(_stop)


def _stop():
    process = _helper["process"]
    if process is not None and process.poll() is None:
        process.terminate()
    shutil.rmtree(_helper["directory"] or "", ignore_errors=True)


def canvas_class():
    """The NSView that draws the boxes, top-left origin."""
    from AppKit import NSBezierPath, NSColor, NSFont, NSFontAttributeName, NSForegroundColorAttributeName, NSString, NSView

    class Canvas(NSView):
        boxes = []

        def isFlipped(self):
            return True

        def drawRect_(self, rect):
            font = NSFont.boldSystemFontOfSize_(10)
            for left, top, right, bottom, text, kind in self.boxes:
                red, green, blue = COLORS.get(kind, COLORS["token"])
                color = NSColor.colorWithSRGBRed_green_blue_alpha_(red / 255.0, green / 255.0, blue / 255.0, 1.0)
                color.set()
                outline = NSBezierPath.bezierPathWithRect_(((left, top), (max(right - left, 1), max(bottom - top, 1))))
                outline.setLineWidth_(3 if kind == "sprinkler" else 2 if kind == "target" else 1)
                outline.stroke()
                attributes = {NSFontAttributeName: font, NSForegroundColorAttributeName: NSColor.blackColor()}
                text = NSString.stringWithString_(text)
                width, height = text.sizeWithAttributes_(attributes)
                label_top = max(top - height - 2, 0)
                NSBezierPath.fillRect_(((left, label_top), (width + 6, height + 2)))
                text.drawAtPoint_withAttributes_((left + 3, label_top + 1), attributes)

    return Canvas


def _run(directory, parent):
    from AppKit import (
        NSApplication, NSApplicationActivationPolicyAccessory, NSBackingStoreBuffered, NSColor, NSScreen,
        NSWindow, NSWindowCollectionBehaviorCanJoinAllSpaces,
        NSWindowCollectionBehaviorFullScreenAuxiliary, NSWindowCollectionBehaviorStationary,
        NSWindowSharingNone, NSWindowStyleMaskBorderless,
    )
    from Foundation import NSDate, NSMakeRect, NSRunLoop
    from Quartz import CGWindowLevelForKey, kCGCursorWindowLevelKey

    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
    window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
        NSMakeRect(0, 0, 1, 1), NSWindowStyleMaskBorderless, NSBackingStoreBuffered, False)
    window.setBackgroundColor_(NSColor.clearColor())
    window.setOpaque_(False)
    window.setHasShadow_(False)
    window.setIgnoresMouseEvents_(True)
    # Cursor level: Fuzzy Display reports any window below it that sits over Roblox as covering the game.
    window.setLevel_(CGWindowLevelForKey(kCGCursorWindowLevelKey))
    window.setCollectionBehavior_(
        NSWindowCollectionBehaviorCanJoinAllSpaces | NSWindowCollectionBehaviorFullScreenAuxiliary
        | NSWindowCollectionBehaviorStationary)
    # Screen capture skips the window, so the macro never detects its own drawing.
    window.setSharingType_(NSWindowSharingNone)
    canvas = canvas_class().alloc().initWithFrame_(NSMakeRect(0, 0, 1, 1))
    window.setContentView_(canvas)

    path = os.path.join(directory, FILE)
    modified = data = placed = None
    while True:
        NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(1 / 30.0))
        try:
            os.kill(parent, 0)
        except OSError:
            break
        try:
            stamp = os.stat(path).st_mtime_ns
            if stamp != modified:
                with open(path) as handle:
                    data = json.load(handle)
                modified = stamp
        except (OSError, ValueError):
            # No file yet, or it was read mid-replace. Keep the last boxes and try again next tick.
            pass
        if data is None or time.time() - data["time"] > HOLD:
            window.orderOut_(None)
            continue
        geometry = (data["x"], data["y"], data["w"], data["h"])
        if geometry != placed:
            placed = geometry
            # Quartz measures from the top-left of the main screen, AppKit from its bottom-left.
            screen_height = NSScreen.screens()[0].frame().size.height
            window.setFrame_display_(NSMakeRect(data["x"], screen_height - data["y"] - data["h"], data["w"], data["h"]), False)
            canvas.setFrame_(NSMakeRect(0, 0, data["w"], data["h"]))
        canvas.boxes = [tuple(box) for box in data["boxes"]]
        canvas.setNeedsDisplay_(True)
        window.orderFrontRegardless()
    shutil.rmtree(directory, ignore_errors=True)


if __name__ == "__main__":
    _run(sys.argv[1], int(sys.argv[2]))
