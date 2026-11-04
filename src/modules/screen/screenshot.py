import mss
import mss.darwin
mss.darwin.IMAGE_OPTIONS = 0
from PIL import Image
import mss.tools
import time
import numpy as np
import cv2
import os
import tempfile
import subprocess
from modules.screen.screenData import getScreenData
from modules.screen import virtual_display
from modules.misc.appManager import getWindowSize
from modules.controls.sleep import heartbeat

mw, mh = virtual_display.screen_size()
multi = 2 if getScreenData()["display_type"] == "retina" else 1
'''
Theres an issue for a few people where the mss screenshot takes almost a minute to run in the macro process.
This seems to affect any screenshots taken with quartz, but not those taken with filepath
'''
usePillow = False

def pillowGrab(x,y,w,h):
    fh, filepath = tempfile.mkstemp(".png")
    os.close(fh)
    try:
        if virtual_display.active():
            args = ["screencapture", "-R{},{},{},{}".format(int(x), int(y), int(w), int(h))]
        else:
            args = ["screencapture"]
        subprocess.call(args + ["-x", filepath])
        with Image.open(filepath) as im:
            im.load()
            if virtual_display.active():
                if im.size != (int(w), int(h)):
                    raise virtual_display.DisplayError("The virtual-display capture is not at 1x scale.")
                return im.crop((0, 0, int(w), int(h)))
            return im.crop((x, y, x + w, y + h))
    finally:
        try:
            os.unlink(filepath)
        except OSError:
            pass

#returns an NP array, useful for cv2
def mssScreenshotNP(x,y,w,h, save = False):
    heartbeat()
    x, y = virtual_display.to_global(x, y)
    if usePillow:
        scale = 1 if virtual_display.active() else multi
        screen = pillowGrab(int(x*scale), int(y*scale), int(w*scale), int(h*scale))
        if save: screen.save(f"screen-{time.time()}.png")
        screen = np.array(screen)
        screen_bgra = cv2.cvtColor(screen, cv2.COLOR_RGB2BGRA)
        return screen_bgra

    else:
        with mss.mss() as sct:
            # The screen part to capture
            monitor = {"left": int(x), "top": int(y), "width": int(w), "height": int(h)}
            # Grab the data and convert to opencv img
            sct_img = sct.grab(monitor)
            if virtual_display.active() and sct_img.size != (int(w), int(h)):
                raise virtual_display.DisplayError("The virtual-display capture is not at 1x scale.")
            if save: mss.tools.to_png(sct_img.rgb, sct_img.size, output=f"screen-{time.time()}.png")
            return np.array(sct_img)


def mssScreenshot(x=0,y=0,w=None,h=None, save = False, filename=None):
    heartbeat()
    default_w, default_h = virtual_display.screen_size() if virtual_display.active() else (mw, mh)
    w = default_w if w is None else w
    h = default_h if h is None else h
    x, y = virtual_display.to_global(x, y)
    if usePillow:
        scale = 1 if virtual_display.active() else multi
        img = pillowGrab(int(x*scale), int(y*scale), int(w*scale), int(h*scale))
        if save: img.save(filename if filename else f"screen-{time.time()}.png")
        return img
    else:
        with mss.mss() as sct:
            # The screen part to capture
            monitor = {"left": int(x), "top": int(y), "width": int(w), "height": int(h)}
            # Grab the data and convert to pillow img
            sct_img = sct.grab(monitor)
            if virtual_display.active() and sct_img.size != (int(w), int(h)):
                raise virtual_display.DisplayError("The virtual-display capture is not at 1x scale.")
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            if save: mss.tools.to_png(sct_img.rgb, sct_img.size, output=filename if filename else f"screen-{time.time()}.png")
            return img

def screenshotRobloxWindow(filename = None, regionMultipliers = None):
    res = getWindowSize("roblox roblox")
    if res:
        x,y,w,h = res
    else:
        x = 0
        y = 0
        w = mw
        h = mh
    if regionMultipliers:
        x += w*regionMultipliers[0] if regionMultipliers[0] <= 1 else regionMultipliers[0]
        y += h*regionMultipliers[1] if regionMultipliers[1] <= 1 else regionMultipliers[1]
        w = w*regionMultipliers[2] if regionMultipliers[2] <= 1 else regionMultipliers[2]
        h = h*regionMultipliers[3] if regionMultipliers[3] <= 1 else regionMultipliers[3]
    return mssScreenshot(x,y,w,h, save=bool(filename), filename=filename)

def benchmarkMSS():
    global usePillow
    try:
        with mss.mss() as sct:
            x, y = virtual_display.to_global(0, 0)
            monitor = {"left": x, "top": y, "width": 100, "height": 100}
            start = time.time()
            sct.grab(monitor)
            duration = time.time() - start
            if duration > 1:
                print(f"MSS took {duration:.2f}s — switching to Pillow.")
                usePillow = True
            else:
                print(f"MSS is fast enough: {duration:.2f}s")
                return True
    except Exception as e:
        print(f"[ERROR] MSS failed: {e} — switching to Pillow.")
        usePillow = True
    
    return False

#returns a rgba pillow screenshot
def mssScreenshotPillowRGBA(x=0,y=0,w=None,h=None):
    if virtual_display.active():
        return mssScreenshot(x, y, w, h).convert("RGBA")
    with mss.mss() as sct:
        monitor = {"left": int(x), "top": int(y), "width": int(mw if w is None else w), "height": int(mh if h is None else h)}
        shot = sct.grab(monitor)
        return Image.frombytes("RGBA", shot.size, shot.bgra, "raw", "BGRA")
