import pyautogui as pag
import time
from modules.screen import screenData
from operator import itemgetter
from modules.misc.appManager import getWindowSize
from modules.screen.screenshot import mssScreenshot

class RobloxWindowBounds:
    '''
    Class to handle roblox window info and bss y offset
    '''

    def __init__(self):
        self.screenw, self.screenh = pag.size()
        self.mx = 0
        self.my = 0
        self.mw = self.screenw
        self.mh = self.screenh
        self.yOffset = 21 #bss offset due to the new ui
        self.contentYOffset = 0 #get area of content (excludes title bar/tab bar)

        screenInfo = screenData.getScreenData()
        self.display_type, self.ww, self.wh, self.ysm, self.xsm, self.ylm, self.xlm = itemgetter("display_type", "screen_width","screen_height", "y_multiplier", "x_multiplier", "y_length_multiplier", "x_length_multiplier")(screenInfo)
        self.isRetina = self.display_type == "retina"
        self.multi = 2 if self.isRetina else 1 #used for pixel calculation compatibility between retina and non-retina displays
    
    def setRobloxWindowBounds(self, setYOffset = True):
        self.mx, self.my, self.mw, self.mh = getWindowSize("roblox roblox")

        #calculate y offset and the actual roblox content bounds
        if setYOffset:
            top = self._honeyLabelTop()
            if top is not None:
                self.contentYOffset = max((top//self.multi)-15-self.yOffset, 0)
                if self.contentYOffset != 0:
                    pag.hotkey("ctrl", "command", "f")
                    time.sleep(0.5)
                    self.mx, self.my, self.mw, self.mh = getWindowSize("roblox roblox")
                    top = self._honeyLabelTop()
                    self.contentYOffset = max((top//self.multi)-15-self.yOffset, 0) if top is not None else 0
                self.my+=self.contentYOffset
                self.mh-=self.contentYOffset


    def _honeyLabelTop(self):
        """Top pixel row of the 'Honey' label in the honey bar, or None if it isn't found."""
        #imported here because the main process imports this module and shouldn't load the OCR models
        import modules.screen.ocr as ocr
        tops = []
        for box, (text, _conf) in ocr.ocrRead(mssScreenshot(self.mx, self.my, self.mw, self.mh//3)):
            if ''.join(ch for ch in text.lower() if ch.isalnum()).startswith("honey"):
                tops.append(min(p[1] for p in box))
        return int(min(tops)) if tops else None
