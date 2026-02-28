from modules.screen.screenshot import mssScreenshot
import pyautogui as pag
import numpy as np
from PIL import Image
import os
import time
import platform
import mss
from modules.screen.screenData import getScreenData, scaleRegion, scaleX, scaleY
import io
import warnings

BASE_SCREEN_WIDTH = 2880
BASE_SCREEN_HEIGHT = 1800

_IS_WINDOWS = platform.system() == "Windows"

if not _IS_WINDOWS:
    import mss.darwin
    mss.darwin.IMAGE_OPTIONS = 0

ocrLib = None
useLangPref = True
if not _IS_WINDOWS:
    try:
        from ocrmac import ocrmac #see if ocr mac is installed
        ocrLib = "ocrmac"
    except:
        pass

if ocrLib is None:
    try:
        from paddleocr import PaddleOCR
        ocrP = PaddleOCR(lang='en', show_log = False, use_angle_cls=False)
        print("Imported paddleocr")
        ocrLib = "paddleocr"
    except:
        try:
            import easyocr
            import ssl
            ssl._create_default_https_context = ssl._create_unverified_context
            easyocrGPU = False
            try:
                import torch
                hasCuda = torch.cuda.is_available()
                hasMps = hasattr(torch.backends, "mps") and torch.backends.mps.is_available()
                if _IS_WINDOWS:
                    easyocrGPU = hasCuda
                else:
                    easyocrGPU = hasCuda or hasMps
            except Exception:
                easyocrGPU = False

            if not easyocrGPU:
                warnings.filterwarnings(
                    "ignore",
                    message=".*pin_memory.*no accelerator is found.*",
                    category=UserWarning,
                )

            print(f"Imported easyocr (gpu_preferred={easyocrGPU})")
            try:
                easyocrReader = easyocr.Reader(['en'], gpu=easyocrGPU)
            except Exception as readerError:
                if easyocrGPU:
                    print(f"EasyOCR GPU initialization failed, falling back to CPU: {readerError}")
                    easyocrGPU = False
                    easyocrReader = easyocr.Reader(['en'], gpu=False)
                else:
                    raise
            ocrLib = "easyocr"
        except Exception as e:
            print(f"Failed to import any OCR library: {e}")

mw, mh = pag.size()
screenInfo = getScreenData()
ww = screenInfo["screen_width"]
wh = screenInfo["screen_height"]
newUI = False


def scaledRegion(left, top, width, height, anchor_x="left", anchor_y="top"):
    return tuple(int(value) for value in scaleRegion(left, top, width, height, anchor_x, anchor_y, screenInfo))

def getCenter(coords):
    x = coords[0][0]
    y = coords[0][1]
    w = coords[1][0] - x #x2-x1
    h = coords[2][1] - y #y2 -y1
    #calculate center
    return (x+w//2, y+h//2)
def paddleBounding(b):
    #convert all values to int and unpack
    x1,y1,x2,y2 = [int(x) for x in b]
    return ([x1,y1],[x2,y1],[x2,y2],[x1,y2])
    
def ocrMac_(img):
    if useLangPref:
        result = ocrmac.OCR(img,language_preference=['en-US']).recognize(px=True)
    else:
        result = ocrmac.OCR(img).recognize(px=True)
    #convert it to the same format as paddleocr
    #[ ([x1,y1],[x2,y1],[x2,y2],[x1,y2]), (text, confidence) ]
    return [ [paddleBounding(x[2]),(x[0],x[1]) ] for x in result]

def ocrPaddle(img):
    #img = np.asarray(img) 
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_byte_arr = img_byte_arr.getvalue()
    result = ocrP.ocr(img_byte_arr, cls=False)[0]
    return result

def ocrEasy(img):
    img = np.asarray(img)
    result = easyocrReader.readtext(img)
    return [[(x[0]), (x[1], x[2])] for x in result]

def screenshot(**kwargs):
    out = None
    for _ in range(4):
        try: 
            if "region" in kwargs:
                out = pag.screenshot(region=[int(x) for x in kwargs['region']])
            else:
                out = pag.screenshot()
            break
        except FileNotFoundError as e:
            print(e)
            time.sleep(0.5)
    return out

def imToString(m):
    sn = time.time()
    ebY = scaleY(BASE_SCREEN_HEIGHT / 20, screenInfo)
    honeyY = 0
    if newUI:
        ebY = scaleY(BASE_SCREEN_HEIGHT / 14, screenInfo)
        honeyY = scaleY(25, screenInfo)
    if m == "bee bear":
        cap = mssScreenshot(*scaledRegion(1240, BASE_SCREEN_HEIGHT / 22, 400, 150, anchor_x="center"))
        #cap.save("ebutton.png")
    elif m == "egg shop":
        cap = screenshot(region=scaledRegion(2400, 600, 480, 360, anchor_x="right"))
    elif m == "blue":
        cap = mssScreenshot(mw*3//4, mh//3*2, mw//4,mh//3)
    elif m == "chat":
        cap = screenshot(region=(ww*3//4, 0, ww//4,wh//3))
    elif m == "ebutton":
        cap = mssScreenshot(*scaledRegion(1240, 20, 400, 125, anchor_x="center"))
        result = ocrFunc(cap)
        try:
            result = sorted(result, key = lambda x: x[1][1], reverse = True)
            return result[0][1][0]
        except:
            return ""
    elif m == "honey":
        cap = mssScreenshot(*scaledRegion(1199, honeyY, 140, 36, anchor_x="center"))
        if not cap: return ""
        ocrres = ocrFunc(cap)
        honey = ""
        try:
            result = ''.join([x[1][0] for x in ocrres])
            for i in result:
                if i == "(" or i == "+":
                    break
                elif i.isdigit():
                    honey += i
            honey = int(honey)
        except Exception as e:
            print(e)
            print(honey)
        return honey
    elif m == "disconnect":
        cap = screenshot(region=(ww//(3),wh//(2.8),ww//(2.3),wh//(5)))
    elif m == "dialog":
        cap = screenshot(region=scaledRegion(960, 1125, 360, 120, anchor_x="center"))
    if not cap: return ""
    result = ocrFunc(cap)
    try:
        result = sorted(result, key = lambda x: x[1][1], reverse = True)
        out = ''.join([x[1][0] for x in result])
    except:
        out = ""
    return out

def customOCR(X1,Y1,W1,H1,applym=1):
    if applym:
        cap = screenshot(region=scaledRegion(X1, Y1, W1, H1))
    else:
        cap = screenshot(region=(X1,Y1,W1,H1))
    out = ocrFunc(cap)
    if not out is None:
        return out
    else:
        return [[[""],["",0]]]

#accept pillow img
def ocrRead(img):
    out = ocrFunc(img)
    if out is None:
        return [[[""],["",0]]]
    return out
    
if ocrLib == "ocrmac":
    ocrFunc = ocrMac_
    try:
        ocrFunc(mssScreenshot(1,1,10,10))
    except Exception as e:
        print(e)
        print("Language Preferences for ocrmac is disabled")
        useLangPref = False
elif ocrLib == "paddleocr":
    ocrFunc = ocrPaddle
elif ocrLib == "easyocr":
    ocrFunc = ocrEasy
else:
    # Fallback: return empty results if no OCR library is available
    def ocrFunc(img):
        return []
