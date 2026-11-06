import mss
import sys
if sys.platform == "darwin":
    import mss.darwin
    mss.darwin.IMAGE_OPTIONS = 0
from PIL import Image
import mss.tools
import time
import pyautogui as pag
import numpy as np
import cv2
import os
import tempfile
import subprocess
from modules.screen.screenData import getScreenData
from modules.misc.appManager import getWindowSize

mw, mh = pag.size()
multi = 2 if getScreenData()["display_type"] == "retina" else 1
'''
Theres an issue for a few people where the mss screenshot takes almost a minute to run in the macro process.
This seems to affect any screenshots taken with quartz, but not those taken with filepath
'''
usePillow = False

def pillowGrab(x,y,w,h):
    fh, filepath = tempfile.mkstemp(".png")
    os.close(fh)
    args = ["screencapture"]
    subprocess.call(args + ["-x", filepath])
    im = Image.open(filepath)
    im.load()
    os.unlink(filepath)
    bbox = (x, y, x + w, y + h)
    im_cropped = im.crop(bbox)
    im.close()
    return im_cropped

#returns an NP array, useful for cv2
def mssScreenshotNP(x,y,w,h, save = False):
    if usePillow:
        screen = pillowGrab(int(x*multi),int(y*multi),int(w*multi),int(h*multi))
        screen = np.array(screen)
        screen_bgra = cv2.cvtColor(screen, cv2.COLOR_RGB2BGRA)
        return screen_bgra

    else:
        with mss.mss() as sct:
            # The screen part to capture
            monitor = {"left": int(x), "top": int(y), "width": int(w), "height": int(h)}
            # Grab the data and convert to opencv img
            sct_img = sct.grab(monitor)
            if save: mss.tools.to_png(sct_img.rgb, sct_img.size, output=f"screen-{time.time()}.png")
            return np.array(sct_img)


def mssScreenshot(x=0,y=0,w=mw,h=mh, save = False, filename=None):
    if usePillow:
        return pillowGrab(int(x*multi),int(y*multi),int(w*multi),int(h*multi))
    else:
        with mss.mss() as sct:
            # The screen part to capture
            monitor = {"left": int(x), "top": int(y), "width": int(w), "height": int(h)}
            # Grab the data and convert to pillow img
            sct_img = sct.grab(monitor)
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
        x = x*regionMultipliers[0] if regionMultipliers[0] <= 1 else regionMultipliers[0]
        y *= y*regionMultipliers[1] if regionMultipliers[1] <= 1 else regionMultipliers[1]
        w *= w*regionMultipliers[2] if regionMultipliers[2] <= 1 else regionMultipliers[2]
        h *= h*regionMultipliers[3] if regionMultipliers[3] <= 1 else regionMultipliers[3]
    return mssScreenshot(x,y,w,h, save=bool(filename), filename=filename)

def benchmarkMSS():
    global usePillow
    try:
        with mss.mss() as sct:
            monitor = {"left": 0, "top": 0, "width": 100, "height": 100}
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
def mssScreenshotPillowRGBA(x=0,y=0,w=mw,h=mh):   
    with mss.mss() as sct:
        monitor = {"left": int(x), "top": int(y), "width": int(w), "height": int(h)}
        sct_img = sct.grab(monitor)
        img = Image.frombytes("RGBA", sct_img.size, sct_img.bgra, "raw", "BGRA")
        #img.save(f"buff_area.png")
        return img
