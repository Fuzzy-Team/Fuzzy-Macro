from modules.screen import screenData, virtual_display
from operator import itemgetter
from modules.misc.appManager import getWindowSize, enterRobloxFullscreen

class RobloxWindowBounds:
    '''
    Class to handle roblox window info and bss y offset
    '''

    def __init__(self):
        self.screenw, self.screenh = virtual_display.screen_size()
        self.mx = 0
        self.my = 0
        self.mw = self.screenw
        self.mh = self.screenh
        self.yOffset = 21 #bss offset due to the new ui

        screenInfo = screenData.getScreenData()
        self.display_type, self.ww, self.wh, self.ysm, self.xsm, self.ylm, self.xlm = itemgetter("display_type", "screen_width","screen_height", "y_multiplier", "x_multiplier", "y_length_multiplier", "x_length_multiplier")(screenInfo)
        self.isRetina = self.display_type == "retina"
        self.multi = 2 if self.isRetina else 1 #used for pixel calculation compatibility between retina and non-retina displays

    def setRobloxWindowBounds(self, setYOffset = True):
        if virtual_display.active():
            result = virtual_display.prepare_window()
            if not result.get("window_ready"):
                if setYOffset:
                    raise virtual_display.DisplayError("Roblox has no window on Fuzzy Display.")
                return
            self.mx, self.my, self.mw, self.mh = 0, 0, 1920, 1080
            return
        # A windowed Roblox includes its title bar in the window bounds. Fullscreen removes it.
        if setYOffset:
            enterRobloxFullscreen()
        self.mx, self.my, self.mw, self.mh = getWindowSize("roblox roblox")
