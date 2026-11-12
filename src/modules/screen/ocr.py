from modules.controls.sleep import hang_exit
from modules.screen.screenshot import mssScreenshot, mw, mh
import numpy as np
import platform
import threading
import time

ocrLib = None
mac_version = tuple(int(part) for part in platform.mac_ver()[0].split(".")[:2] if part.isdigit())
# Apple Vision OCR is used on Big Sur and newer.  Do not load ocrmac on
# Catalina: recent transitive Core ML wheels can be compiled for a newer macOS
# and emit noisy dyld errors before the fallback OCR is selected.
# Python 3.8 from python.org (used on Intel Macs) reports every macOS 11+ as 10.16.
if len(mac_version) >= 2 and mac_version >= (10, 16):
    try:
        from ocrmac import ocrmac #see if ocr mac is installed
        ocrLib = "ocrmac"
    except:
        pass

if ocrLib is None:
    try:
        import skimage.io
    except ImportError:
        # easyocr imports skimage.io only to read image files, and the macro passes it arrays.
        # scikit-image isn't installed below macOS 10.15 (its wheels bundle a libomp that
        # needs 10.15), so give easyocr a stand-in.
        import sys
        import types
        from PIL import Image
        skimageStub = types.ModuleType("skimage")
        skimageStub.io = types.ModuleType("skimage.io")
        skimageStub.io.imread = lambda path: np.asarray(Image.open(path))
        sys.modules["skimage"] = skimageStub
        sys.modules["skimage.io"] = skimageStub.io
    import easyocr
    import functools
    import ssl
    try:
        # older Python installs may lack system CA certificates; verify with certifi's instead
        import certifi
        ssl._create_default_https_context = functools.partial(ssl.create_default_context, cafile=certifi.where())
    except ImportError:
        pass
    print("Imported easyocr")
    easyocrReader = easyocr.Reader(['en'])
    ocrLib = "easyocr"

# Vision's language preference API (supportedRecognitionLanguages) needs macOS 12
useLangPref = mac_version >= (12, 0)


def paddleBounding(b):
    #convert all values to int and unpack
    x1,y1,x2,y2 = [int(x) for x in b]
    return ([x1,y1],[x2,y1],[x2,y2],[x1,y2])

def accurateVisionWorks():
    """On some Macs Vision's accurate mode fails (a Neural Engine error) and ocrmac hides it by
    returning no text, so every read comes back empty. Fast mode still works there."""
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGB", (240, 80), "white")
    ImageDraw.Draw(img).text((10, 10), "Claim Hive", fill="black", font=ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 40))
    return bool(ocrmac.OCR(img, recognition_level="accurate").recognize())

visionLevel = "accurate" if ocrLib != "ocrmac" or accurateVisionWorks() else "fast"
if ocrLib == "ocrmac":
    print(f"Text reading: Vision {visionLevel} mode")

def readVision(img):
    if useLangPref:
        return ocrmac.OCR(img,language_preference=['en-US'],recognition_level=visionLevel).recognize(px=True)
    return ocrmac.OCR(img,recognition_level=visionLevel).recognize(px=True)

lastVisionCheck = float("-inf")

def ocrMac_(img):
    global visionLevel, lastVisionCheck
    result = readVision(img)
    # Accurate mode can start failing minutes into a run, after the check at load passed. Empty reads
    # are normal when no text is on screen, so test it again on an empty read, at most every 5 seconds.
    if not result and visionLevel == "accurate" and time.monotonic() - lastVisionCheck > 5:
        lastVisionCheck = time.monotonic()
        if not accurateVisionWorks():
            visionLevel = "fast"
            print("Text reading: Vision accurate mode stopped working, switched to fast mode")
            result = readVision(img)
    #convert it to the paddleocr format used across the macro
    #[ ([x1,y1],[x2,y1],[x2,y2],[x1,y2]), (text, confidence) ]
    return [ [paddleBounding(x[2]),(x[0],x[1]) ] for x in result]

def ocrEasy(img):
    img = np.asarray(img)
    result = easyocrReader.readtext(img)
    return [[(x[0]), (x[1], x[2])] for x in result]

#read the blue notification text in the bottom right of the screen
def readBlueText():
    cap = mssScreenshot(mw*3//4, mh//3*2, mw//4,mh//3)
    result = ocrFunc(cap)
    try:
        result = sorted(result, key = lambda x: x[1][1], reverse = True)
        out = ''.join([x[1][0] for x in result])
    except:
        out = ""
    return out

#accept pillow img
def ocrRead(img):
    out = ocrFunc(img)
    if out is None:
        return [[[""],["",0]]]
    return out

ocrLock = threading.Lock()

def lockedOcrMac(img):
    """Vision runs one call at a time and can hang from any thread. If a call never returns, the
    next read gives up waiting after 90s and restarts the macro (controls/sleep.py)."""
    if not ocrLock.acquire(timeout=90):
        hang_exit("Text reading froze: another read held the lock for 90 seconds")
        ocrLock.acquire()  # not the macro process, so there is nothing to restart
    try:
        return ocrMac_(img)
    finally:
        ocrLock.release()

if ocrLib == "ocrmac":
    ocrFunc = lockedOcrMac
elif ocrLib == "easyocr":
    ocrFunc = ocrEasy
