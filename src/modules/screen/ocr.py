from modules.screen.screenshot import mssScreenshot, mw, mh
import numpy as np
import platform

ocrLib = None
mac_version = tuple(int(part) for part in platform.mac_ver()[0].split(".")[:2] if part.isdigit())
# Apple Vision OCR is used on Big Sur and newer.  Do not load ocrmac on
# Catalina: recent transitive Core ML wheels can be compiled for a newer macOS
# and emit noisy dyld errors before the fallback OCR is selected.
if len(mac_version) >= 2 and mac_version >= (11, 0):
    try:
        from ocrmac import ocrmac #see if ocr mac is installed
        ocrLib = "ocrmac"
    except:
        pass

if ocrLib is None:
    import easyocr
    import ssl
    ssl._create_default_https_context = ssl._create_unverified_context
    print("Imported easyocr")
    easyocrReader = easyocr.Reader(['en'])
    ocrLib = "easyocr"

# Vision's language preference API (supportedRecognitionLanguages) needs macOS 12
useLangPref = mac_version >= (12, 0)


def paddleBounding(b):
    #convert all values to int and unpack
    x1,y1,x2,y2 = [int(x) for x in b]
    return ([x1,y1],[x2,y1],[x2,y2],[x1,y2])

def ocrMac_(img):
    if useLangPref:
        result = ocrmac.OCR(img,language_preference=['en-US']).recognize(px=True)
    else:
        result = ocrmac.OCR(img).recognize(px=True)
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

if ocrLib == "ocrmac":
    ocrFunc = ocrMac_
elif ocrLib == "easyocr":
    ocrFunc = ocrEasy
