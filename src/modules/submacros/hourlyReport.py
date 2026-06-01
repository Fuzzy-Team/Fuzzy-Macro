from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter
import cv2
import math
import time
import ast
import numpy as np
import platform
from modules.misc.messageBox import msgBox
from modules.screen.imageSearch import locateTransparentImageOnScreen, locateTransparentImage
from modules.screen.screenshot import mssScreenshotNP, mssScreenshot
from modules.misc.imageManipulation import adjustImage
import time
import pyautogui as pag
from modules.screen.ocr import ocrRead, imToString
import copy
from datetime import datetime
from modules.screen.robloxWindow import RobloxWindowBounds
import pickle
import json
from modules.misc.settingsManager import getCurrentProfile, loadFields, getMacroVersion

ww, wh = pag.size()

# ---------------------------------------------------------------------------
# Theme / color configuration
# ---------------------------------------------------------------------------

THEMES = {
    "dark": {
        "bg":           (14, 15, 19),
        "sidebar_bg":   (23, 25, 29),
        "card_bg":      (28, 30, 36),
        "text_primary": (255, 255, 255),
        "text_secondary": (175, 175, 175),
        "grid":         (65, 65, 65),
        "gather":       (166, 255, 124),
        "convert":      (254, 202, 64),
        "bug_run":      (200, 100, 80),
        "other":        (133, 154, 173),
        "honey":        (248, 191, 23),
    },
    "midnight": {
        "bg":           (6, 7, 9),
        "sidebar_bg":   (12, 14, 18),
        "card_bg":      (20, 22, 28),
        "text_primary": (230, 230, 240),
        "text_secondary": (160, 160, 170),
        "grid":         (40, 40, 48),
        "gather":       (130, 220, 90),
        "convert":      (220, 170, 40),
        "bug_run":      (180, 80, 60),
        "other":        (100, 120, 140),
        "honey":        (220, 170, 20),
    },
    "oled": {
        "bg":           (0, 0, 0),
        "sidebar_bg":   (10, 10, 12),
        "card_bg":      (16, 16, 20),
        "text_primary": (255, 255, 255),
        "text_secondary": (200, 200, 210),
        "grid":         (35, 35, 40),
        "gather":       (166, 255, 124),
        "convert":      (254, 202, 64),
        "bug_run":      (255, 80, 60),
        "other":        (140, 160, 180),
        "honey":        (255, 200, 30),
    },
}

ACCENT_COLORS = {
    "green":  (34, 255, 6),
    "purple": (153, 102, 255),
    "blue":   (86, 164, 228),
    "gold":   (254, 202, 64),
    "pink":   (255, 102, 178),
}

# ---------------------------------------------------------------------------
# Macro GUI themes
# Every macro GUI theme (the gui_theme setting) gets a matching report theme so
# the hourly/session report looks like the rest of the macro. Mirroring the
# webapp — where each theme only overrides --primary — the macro themes share a
# common dark base and differ only by their accent colour.
# ---------------------------------------------------------------------------

_MACRO_REPORT_BASE = {
    "bg":             (18, 18, 18),    # webapp --background  #121212
    "sidebar_bg":     (24, 24, 24),
    "card_bg":        (30, 30, 30),    # webapp --surface     #1E1E1E
    "text_primary":   (224, 224, 224), # webapp --text-main   #E0E0E0
    "text_secondary": (160, 160, 160), # webapp --text-dim    #A0A0A0
    "grid":           (60, 60, 60),
    "gather":         (166, 255, 124),
    "convert":        (254, 202, 64),
    "bug_run":        (200, 100, 80),
    "other":          (133, 154, 173),
    "honey":          (248, 191, 23),
}

# normalized gui_theme value -> accent colour (the webapp --primary for that theme)
MACRO_THEME_ACCENTS = {
    "brown":       (171, 128, 98),   # Fuzzy        #ab8062
    "cream":       (239, 218, 152),  # Gifted Fuzzy #efda98
    "red":         (203, 65,  68),   # Precise      #cb4144
    "blue":        (63,  193, 195),  # Bouyant      #3fc1c3
    "commander":   (90,  209, 114),  # Commander    #5ad172
    "purple":      (157, 142, 195),  # Mythic       #9d8ec3
    "basic_black": (255, 200, 0),    # Basic Bee    #ffc800
    "gummy":       (255, 0,   255),  # Gummy        #ff00ff
    "tadpole":     (32,  189, 150),  # Tadpole      #20bd96
    "gifted_tad":  (144, 240, 224),  # Gifted Tad   #90f0e0
}

def _mixColor(base, accent, ratio):
    """Blend a base colour toward the accent (0.0 = base, 1.0 = accent)."""
    ratio = max(0.0, min(1.0, ratio))
    return tuple(int(round(b * (1 - ratio) + a * ratio)) for b, a in zip(base, accent))

def _saturate(color, factor):
    """Push a colour away from grey to amplify its hue (factor > 1 = more vivid).

    Surfaces are tinted toward a saturated version of the accent so that themes
    with similar hues (e.g. the warm Brown and Cream) stay visually distinct
    even at the low tint ratios used for the dark backgrounds."""
    mean = sum(color) / 3.0
    return tuple(int(round(max(0, min(255, mean + (c - mean) * factor)))) for c in color)

# How vivid the accent is made before it is washed into the dark surfaces. The
# highlight/line accent itself stays the true theme colour; only the background
# tints use this boosted version so close hues read as different colours.
_MACRO_TINT_SATURATION = 1.7

# How strongly each palette component is washed toward the theme accent. Dark
# surfaces take a noticeable tint so each theme clearly reads as its colour,
# while text and the semantic activity colours keep most of their own identity
# to stay legible and meaningful.
_MACRO_MIX_RATIOS = {
    "bg":             0.09,
    "sidebar_bg":     0.12,
    "card_bg":        0.14,
    "grid":           0.24,
    "text_primary":   0.04,
    "text_secondary": 0.16,
    "gather":         0.07,
    "convert":        0.07,
    "bug_run":        0.10,
    "other":          0.15,
    "honey":          0.07,
}

# Very subtle tint for the canvas base (the area behind/between panels). Kept
# far lighter than the panels so the report stays dark and the panels still read
# as the theme colour.
_MACRO_BASE_BG_MIX = 0.05

def buildMacroReportTheme(accent):
    """Build a full report palette tinted toward a macro theme's accent colour."""
    tint = _saturate(accent, _MACRO_TINT_SATURATION)
    theme = {
        key: _mixColor(base, tint, _MACRO_MIX_RATIOS.get(key, 0.15))
        for key, base in _MACRO_REPORT_BASE.items()
    }
    theme["accent"] = tuple(accent)
    return theme

# Register a tinted report theme for every macro GUI theme.
for _macroTheme, _macroAccent in MACRO_THEME_ACCENTS.items():
    THEMES[_macroTheme] = buildMacroReportTheme(_macroAccent)

# Aliases so alternate spellings of gui_theme still resolve to a report theme.
_MACRO_THEME_ALIASES = {
    "comander":       "commander",
    "basic_bee":      "basic_black",
    "gifted_tadpole": "gifted_tad",
    "gifted_fuzzy":   "cream",
    "fuzzy":          "brown",
    "mythic":         "purple",
    "precise":        "red",
    "bouyant":        "blue",
    "buoyant":        "blue",
}

def resolveReportTheme(guiTheme, fallback="brown"):
    """Map a macro gui_theme value to its matching report theme key."""
    key = str(guiTheme or "").strip().lower().replace(" ", "_")
    key = _MACRO_THEME_ALIASES.get(key, key)
    if key in THEMES:
        return key
    return fallback if fallback in THEMES else "dark"

# Uptime buff rendering config
# key → (chart_type, max_y, color_or_colors, asset_name)
# chart_type: "stackable" | "binary" | "multi"
# "multi": combined row — color_or_colors is list of (data_key, rgb)
BUFF_RENDER_CONFIG = {
    "boost":         ("multi",     10,  [("blue_boost",(77,147,193)),("red_boost",(200,90,80)),("white_boost",(220,220,220))], "boost_buff"),
    "haste":         ("stackable", 10,  (210, 210, 210), "haste_buff"),
    "focus":         ("stackable", 10,  (30,  191, 5),   "focus_buff"),
    "bomb_combo":    ("stackable", 10,  (160, 160, 160), "bomb_combo_buff"),
    "balloon_aura":  ("stackable", 10,  (50,  80,  200), "balloon_aura_buff"),
    "inspire":       ("stackable", 10,  (195, 191, 18),  "inspire_buff"),
    "reindeerfetch": ("stackable", 10,  (204, 44,  44),  "reindeerfetch_buff"),
    "wealth_clock":  ("stackable", 10,  (255, 215, 0),   "wealth_clock_buff"),
    "tide_blessing": ("stackable", 1.2, (91,  211, 255), "tide_blessing_buff"),
    "mondo":         ("stackable", 10,  (128, 255, 0),   "mondo_buff"),
    "blessing":      ("stackable", 100, (204, 68,  255), "blessing_buff"),
    "bloat":         ("stackable", 5,   (208, 208, 208), "bloat_buff"),
    "honey_mark":    ("stackable", 3,   (255, 209, 25),  "honey_mark_buff"),
    "pollen_mark":   ("stackable", 3,   (255, 233, 148), "pollen_mark_buff"),
    "melody":        ("binary",    1,   (200, 200, 200), "melody_buff"),
    "bear":          ("binary",    1,   (115, 71,  40),  "bear_buff"),
    "baby_love":     ("binary",    1,   (112, 181, 195), "baby_love_buff"),
    "jb_share":      ("binary",    1,   (249, 204, 255), "jb_share_buff"),
    "festive_mark":  ("binary",    1,   (200, 67,  53),  "festive_mark_buff"),
    "popstar":       ("binary",    1,   (0,   150, 255), "popstar_buff"),
    "guiding":       ("binary",    1,   (255, 255, 128), "guiding_buff"),
}

# Asset names for hourly snapshot buffs (point-in-time, shown in sidebar grid)
HOURLY_BUFF_ASSETS = {
    "tabby_love":    "tabby_love_buff",
    "polar_power":   "polar_power_buff",
    "wealth_clock":  "wealth_clock_buff",
    "blessing":      "blessing_buff",
    "bloat":         "bloat_buff",
    "tide_blessing": "tide_blessing_buff",
    "mondo":         "mondo_buff",
}

# Ordered main/important buffs first, situational ones last (shown top-to-bottom in the grid)
MAX_UPTIME_BUFF_OPTIONS = 16
DEFAULT_UPTIME_BUFFS = [
    "boost", "haste", "focus", "bomb_combo", "balloon_aura",
    "inspire", "reindeerfetch", "honey_mark", "pollen_mark",
    "festive_mark", "popstar", "melody", "bear", "baby_love",
    "jb_share", "guiding", "mondo", "blessing", "bloat",
    "tide_blessing", "wealth_clock",
]

def normalizeUptimeBuffSelection(rawBuffs, fallback=None):
    fallback = fallback if fallback is not None else DEFAULT_UPTIME_BUFFS
    if rawBuffs is None or rawBuffs == "":
        rawBuffs = fallback
    if isinstance(rawBuffs, str):
        rawBuffs = rawBuffs.strip()
        if not rawBuffs:
            rawBuffs = fallback
        else:
            rawBuffs = [b.strip() for b in rawBuffs.split(",") if b.strip()]
    normalized = []
    seen = set()
    for buff in rawBuffs or []:
        key = str(buff).strip().lower().replace(" ", "_")
        if key in BUFF_RENDER_CONFIG and key not in seen:
            normalized.append(key)
            seen.add(key)
    return normalized or list(fallback)

def expandUptimeBuffDataKeys(buffList):
    dataKeys = []
    seen = set()
    for key in normalizeUptimeBuffSelection(buffList):
        cfg = BUFF_RENDER_CONFIG.get(key)
        keys = [key]
        if cfg and cfg[0] == "multi":
            keys = [dataKey for dataKey, _ in cfg[2]]
        for dataKey in keys:
            if dataKey not in seen:
                dataKeys.append(dataKey)
                seen.add(dataKey)
    return dataKeys
DEFAULT_HOURLY_BUFFS = [
    "tabby_love", "polar_power", "wealth_clock", "blessing", "bloat",
]
MAX_HOURLY_BUFF_OPTIONS = 5

def normalizeHourlyBuffSelection(rawBuffs, fallback=None):
    fallback = fallback if fallback is not None else DEFAULT_HOURLY_BUFFS
    if rawBuffs is None or rawBuffs == "":
        rawBuffs = fallback
    if isinstance(rawBuffs, str):
        rawBuffs = rawBuffs.strip()
        if not rawBuffs:
            rawBuffs = fallback
        else:
            try:
                parsed = ast.literal_eval(rawBuffs)
                rawBuffs = parsed if isinstance(parsed, (list, tuple)) else rawBuffs
            except (ValueError, SyntaxError):
                pass
            if isinstance(rawBuffs, str):
                rawBuffs = [b.strip() for b in rawBuffs.split(",") if b.strip()]
    normalized = []
    seen = set()
    for buff in rawBuffs or []:
        key = str(buff).strip().lower().replace(" ", "_")
        if key in HOURLY_BUFF_ASSETS and key not in seen:
            normalized.append(key)
            seen.add(key)
        if len(normalized) >= MAX_HOURLY_BUFF_OPTIONS:
            break
    return normalized or list(fallback)

# ---------------------------------------------------------------------------

def versionTuple(v):
    return tuple(map(int, (v.split("."))))
macVer = platform.mac_ver()[0]

# try:
#     hti = Html2Image(size=(1900, 850))
#     if hasattr(hti.browser, 'use_new_headless'):
#         hti.browser.use_new_headless = None

    
# except FileNotFoundError:
#     if versionTuple(macVer) >= versionTuple("10.15"):
#         msgBox(title = "error", text = "Google Chrome could not be found. Ensure that:\
#     \n1. Google Chrome is installed\nGoogle chrome is in the applications folder (open the google chrome dmg file. From the pop up, drag the icon into the folder)")
#     else:
#         hti = None

class BuffDetector():
    def __init__(self, robloxWindow: RobloxWindowBounds):

        self.robloxWindow = robloxWindow
        self.y = 33

        self.buffSize = 76 if self.robloxWindow.isRetina else 39

        self.nectars = {
            "comforting": [[np.array([0, 150, 63]), np.array([20, 155, 70])], (-2,0)],
            "invigorating": [[np.array([0, 128, 95]), np.array([180, 132, 101])], (-2,4)],
            "motivating": [[np.array([160, 150, 63]), np.array([170, 155, 70])], (-2,-2)],
            "refreshing": [[np.array([50, 144, 70]), np.array([70, 151, 75])], (-2,2)],
            "satisfying": [[np.array([130, 163, 36]), np.array([140, 168, 40])], (-2,0)]
        }
        self.nectarKernel = cv2.getStructuringElement(cv2.MORPH_RECT,(3,3))

    def screenshotBuffArea(self):
        return mssScreenshotNP(self.robloxWindow.mx, self.robloxWindow.my+self.robloxWindow.yOffset+33, self.robloxWindow.mw, 45)

    def getBuffQuantityFromImg(self, bgrImg,transform, crop=True, buff=None, intOnly=False):
        #buff size is 76x76
        lower = np.array([0, 102, 0])
        upper = np.array([100, 255, 31])
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))

        mask = cv2.cvtColor(bgrImg, cv2.COLOR_BGR2HLS)
        if crop:
            #crop the text area
            h, w, *_ = mask.shape
            mask = mask[int(h * 0.58):, :]
        if transform:
            #extract only the text (white color)
            mask = cv2.inRange(mask, lower, upper)
            mask = cv2.erode(mask, kernel)
        mask = Image.fromarray(mask)
        if transform:
            mask = ImageOps.invert(mask)
            pass
        
        mask = mask.resize((mask.width * 3, mask.height * 3), Image.LANCZOS)

        #mask.save(f"{time.time()}.png")
        #read the text
        ocrText = ''.join([x[1][0] for x in ocrRead(mask)]).replace(":", ".")
        buffCount = ''.join([x for x in ocrText if x.isdigit() or (not intOnly and x == ".")])

        # Clean up the buffCount to ensure it's a valid number format
        # Remove leading/trailing dots and handle multiple dots
        if not intOnly:
            # Remove leading dots
            buffCount = buffCount.lstrip('.')
            # Remove trailing dots
            buffCount = buffCount.rstrip('.')
            # Replace multiple consecutive dots with single dot
            import re
            buffCount = re.sub(r'\.\.+', '.', buffCount)
            
            # Validate that the result is a valid number (handle cases like "5.3.7" or ".")
            if buffCount:
                try:
                    float(buffCount)
                except ValueError:
                    # If not a valid float, try to extract just the first valid number
                    # Split by '.' and take first two parts to make a valid decimal
                    parts = buffCount.split('.')
                    if len(parts) > 2:
                        # Multiple dots: take first integer part and first decimal part
                        buffCount = f"{parts[0]}.{parts[1]}" if parts[1] else parts[0]
                    elif buffCount == '.':
                        # Just a dot, default to 1
                        buffCount = ''

        if buff:
            print(buff)
            print(ocrText)
            print(f"Filtered buffCount: '{buffCount}'")

        return buffCount if buffCount else '1'
    
    def getBuffQuantityFromImgTight(self, bgrImg, show=False):
        #more aggressive thresholding and masking
        #get only text (rgb [243, 243, 243])
        mask = cv2.inRange(bgrImg, np.array([242, 242, 242]), np.array([245, 245, 245]))
        #dilate to make the text thicker
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        mask = cv2.dilate(mask, kernel)
        img = Image.fromarray(mask)
        img = img.resize((img.width * 3, img.height * 3), Image.LANCZOS)
        #convert to black text on white background for ocr
        #img = ImageOps.invert(img)
        if show:
            img.show()
        ocrText = ''.join([x[1][0] for x in ocrRead(img)])
        hasteVal = ''.join([x for x in ocrText if x.isdigit()])
        return hasteVal if hasteVal else '1'

    def getScaledBuffQuantityFromScreen(self, screen, buffRect, hexColor, maxValue, baseValue=0, decimals=0, variation=6):
        """Estimate Natro-style scaled buff values from the icon fill height."""
        if not buffRect:
            return 0

        x, y, w, h = buffRect
        r = (hexColor >> 16) & 0xFF
        g = (hexColor >> 8) & 0xFF
        b = hexColor & 0xFF
        bgr = np.array([b, g, r])
        lower = np.clip(bgr - variation, 0, 255)
        upper = np.clip(bgr + variation, 0, 255)

        height, width = screen.shape[:2]
        iconWidth = max(1, int(38 * self.robloxWindow.multi))
        y1 = max(0, int(6 * self.robloxWindow.multi))
        y2 = min(height, int(44 * self.robloxWindow.multi))

        candidateXs = [
            int(x),
            int(x + w - iconWidth),
            int(x - iconWidth // 2),
        ]
        bestCrop = None
        bestPixels = -1
        for candidateX in candidateXs:
            x1 = max(0, min(width - 1, candidateX))
            x2 = min(width, x1 + iconWidth)
            crop = screen[y1:y2, x1:x2]
            if crop.size == 0:
                continue
            mask = cv2.inRange(crop, lower, upper)
            pixels = int(cv2.countNonZero(mask))
            if pixels > bestPixels:
                bestPixels = pixels
                bestCrop = crop

        crop = bestCrop
        if crop is None or crop.size == 0:
            return 0

        mask = cv2.inRange(crop, lower, upper)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return 0

        _, topY, _, _ = cv2.boundingRect(max(contours, key=cv2.contourArea))
        fillRatio = max(0.0, min(1.0, (crop.shape[0] - topY) / max(crop.shape[0], 1)))
        value = baseValue + fillRatio * maxValue
        if decimals:
            return round(value, decimals)
        return int(round(value))

    def getTideBlessingValueFromScreen(self, screen, buffRect):
        """Estimate Tide Blessing multiplier from the blue fill height."""
        return self.getScaledBuffQuantityFromScreen(
            screen, buffRect, 0x91c2fd, 0.19, baseValue=1.01, decimals=2, variation=8
        )

    def _ensureBgrBuffScreen(self, screen):
        if screen is None:
            return screen
        if len(screen.shape) == 3 and screen.shape[2] == 4:
            return cv2.cvtColor(screen, cv2.COLOR_BGRA2BGR)
        return screen

    def getTideBlessingAhkStyle(self, screen):
        """Detect Tide Blessing like StatMonitor: find its blue fill and scale it."""
        bgrScreen = self._ensureBgrBuffScreen(screen)
        if bgrScreen is None:
            return "0"
        res = self.detectBuffColorInImage(
            bgrScreen,
            0x91c2fd,
            (8, 1),
            y1=6*self.robloxWindow.multi,
            y2=44*self.robloxWindow.multi,
            variation=8,
            searchDirection=7,
        )
        if not res:
            return "0"
        y = res[1]
        scale = max(float(self.robloxWindow.multi or 1), 1.0)
        value = round(1.01 + 0.19 * ((44.3 * scale - y) / (38 * scale)), 2)
        value = max(1.01, min(1.2, value))
        return str(value) if value else "0"

    def getMondoAhkStyle(self, screen):
        """Detect Mondo Chick Blessing from the AHK icon color and right-side stack digit."""
        bgrScreen = self._ensureBgrBuffScreen(screen)
        if bgrScreen is None:
            return "0"
        height, width = bgrScreen.shape[:2]
        res = self.detectBuffColorInImage(
            bgrScreen,
            0xbea2a3,
            (5, 1),
            y1=20*self.robloxWindow.multi,
            y2=46*self.robloxWindow.multi,
            variation=10,
            searchDirection=7,
        )
        if not res:
            return "0"
        x = res[0]
        x1 = max(0, int(x+16*self.robloxWindow.multi))
        x2 = min(width, int(x+36*self.robloxWindow.multi))
        y1 = int(20*self.robloxWindow.multi)
        y2 = min(height, int(46*self.robloxWindow.multi))
        buffImg = bgrScreen[y1:y2, x1:x2]
        if buffImg.size == 0:
            return "1"
        try:
            return str(min(10, int(self.getBuffQuantityFromImgTight(buffImg, show=False))))
        except (TypeError, ValueError):
            return "1"

    def getBuffsWithImage(self, buffs, save=False, screen = None, threshold=0.7):
        buffQuantity = []
        buffs = buffs.items()

        if screen is None:
            screen = self.screenshotBuffArea()

        for buff,v in buffs:
            templatePosition, transform, stackable = v

            #find the buff
            try:
                buffTemplate = adjustImage("./images/buffs", buff, self.robloxWindow.display_type)
            except FileNotFoundError:
                if buff == "tide_blessing":
                    buffQuantity.append(self.getTideBlessingAhkStyle(screen))
                elif buff == "mondo":
                    buffQuantity.append(self.getMondoAhkStyle(screen))
                else:
                    buffQuantity.append("0")
                continue
            finalBuffValues = []

            for _ in range(3):
                res = locateTransparentImage(buffTemplate, screen, threshold)

                if not res: 
                    finalBuffValues.append(0)
                    break

                #get a screenshot of the buff
                rx, ry = res[1]
                h,w = buffTemplate.shape[:-1]
                if templatePosition == "bottom": 
                    ry-=self.buffSize-h
                elif templatePosition == "middle":
                    rx = max(0, rx-(self.buffSize-w)/2+8)
                    ry -= 30

                cropX = int(rx)
                cropY = int(ry)

                imgHeight, imgWidth, *_ = screen.shape
                cropX = np.clip(cropX, 0, imgWidth - self.buffSize - 5)
                cropY = np.clip(cropY, 0, imgHeight - self.buffSize - 2)
                
                #buff is not stackable, no need to extract text
                if not stackable:
                    finalBuffValues.append(1)
                    if save:
                        fullBuffImgBGR = cv2.cvtColor(screen, cv2.COLOR_RGBA2BGR)[cropY:cropY+self.buffSize+2, cropX:cropX+self.buffSize+5]
                        cv2.imwrite(f"{buff}-{time.time()}.png", fullBuffImgBGR)
                    break
                    
                fullBuffImgBGR = cv2.cvtColor(screen, cv2.COLOR_RGBA2BGR)[cropY:cropY+self.buffSize+2, cropX:cropX+self.buffSize+5]

                if fullBuffImgBGR.size == 0:
                    print(f"Warning: Empty image for buff '{buff}' at ({cropX}, {cropY})")
                    finalBuffValues.append(1)
                    time.sleep(1)
                    continue
                
                if save:
                    cv2.imwrite(f"{buff}-{time.time()}.png", fullBuffImgBGR)

                #filter out everything but the text
                buffVal = self.getBuffQuantityFromImg(fullBuffImgBGR, transform, buff=buff)
                if buffVal == "1":
                    time.sleep(1)
                finalBuffValues.append(buffVal)
            
            maxFinalBuffValue = "0"
            for val in finalBuffValues:
                try:
                    val_float = float(val)
                    max_float = float(maxFinalBuffValue)
                    if val_float > max_float:
                        maxFinalBuffValue = val
                except (ValueError, TypeError) as e:
                    # If we can't convert to float, skip this value or use a default
                    print(f"Warning: Could not convert buff value '{val}' to float: {e}")
                    continue
            buffQuantity.append(maxFinalBuffValue)

        return buffQuantity

    def getBuffWithColor(self, buffs):
        buffQuantity = []
        buffs = buffs.items()

        screen = self.screenshotBuffArea()
        hsv = cv2.cvtColor(screen, cv2.COLOR_BGR2HSV)

        for buff,v in buffs:
            colorRange, transform, stackable = v
            lower, upper = colorRange

            #find the buff
            mask = cv2.inRange(hsv, lower, upper)
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for cnt in contours:
                rect = cv2.boundingRect(cnt)
                x, y, w, h = rect

                #filter area to avoid noise
                if self.buffSize-5 < w < self.buffSize+5:
                     #buff is either present or not, non stackable (0 or 1)
                    if not stackable:
                        buffQuantity.append("1")
                        break

                    #crop out
                    y = min(0, y+self.buffSize-h)
                    buffImgBGR = screen[y:y+self.buffSize, x:x+self.buffSize]
                    out = self.getBuffQuantityFromImg(buffImgBGR, True)
                    buffQuantity.append(out)
                    break
                else:
                    buffQuantity.append("0")
        return buffQuantity
    
    def detectBuffColorInImage(self, screen, hex, minSize, x1=0, y1=0, x2=None, y2=None, variation=0, show=False, searchDirection=1, instances=1):
        
        #convert hex to bgr and setup the color range
        r = (hex >> 16) & 0xFF
        g = (hex >> 8) & 0xFF
        b = hex & 0xFF
        bgr = [b,g,r]
        lower = np.array([x-variation for x in bgr])
        upper = np.array([x+variation for x in bgr])

        #crop screen
        if x2 is None:
            x2 = screen.shape[1]
        if y2 is None:
            y2 = screen.shape[0]
        
        cropped = screen[int(y1):int(y2), max(int(x1),0):int(x2)]

        if cropped is None or cropped.size == 0:
            print(f"Image is blank")
            print(f"Image Size: {screen.size}")
            print(f"Crop info: {(x1,y1,x2,y2)}")
            return []

        mask = cv2.inRange(cropped, lower, upper)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        coords = []
        for cnt in contours:
            rect = cv2.boundingRect(cnt)
            x, y, w, h = rect

            #filter area to avoid noise
            if w > minSize[0]*self.robloxWindow.multi and h > minSize[1]*self.robloxWindow.multi:
                coords.append((x + x1, y + y1, w, h))  # Offset by crop origin

        def sort_key(rect):
            x, y, w, h = rect
            center_x = x + w // 2
            center_y = y + h // 2

            if searchDirection == 1:  # top → left → right → bottom
                return (center_y, center_x)
            elif searchDirection == 2:  # bottom → left → right → top
                return (-center_y, center_x)
            elif searchDirection == 3:  # bottom → right → left → top
                return (-center_y, -center_x)
            elif searchDirection == 4:  # top → right → left → bottom
                return (center_y, -center_x)
            elif searchDirection == 5:  # left → top → bottom → right
                return (center_x, center_y)
            elif searchDirection == 6:  # left → bottom → top → right
                return (center_x, -center_y)
            elif searchDirection == 7:  # right → bottom → top → left
                return (-center_x, -center_y)
            elif searchDirection == 8:  # right → top → bottom → left
                return (-center_x, center_y)
            else:  # fallback to default (top → left)
                return (center_y, center_x)

        # Sort and return only the first match
        if coords:
            coords.sort(key=sort_key)
            out = []
            preview = screen.copy()
            for i in range(min(len(coords), instances)):
                x, y, w, h = coords[i]
                out.append(coords[i])
                if show:
                    cv2.rectangle(preview, (x, y), (x + w, y + h), (0, 255, 0), 2)

            if show:
                cv2.imshow("Detected Buff", preview)
                cv2.waitKey(0)
                cv2.destroyAllWindows()
            if instances == 1:
                return out[0]
            else:
                return out

        return []

        
    def getNectar(self, nectar):
        vals = self.nectars[nectar]
        col, offsetCoords = vals
        offsetX, offsetY = offsetCoords

        #find the buff
        screen = self.screenshotBuffArea()
        buffTemplate = adjustImage("./images/buffs", nectar, self.robloxWindow.display_type)
        res = locateTransparentImage(buffTemplate, screen, 0.5) #get the best match first. At high nectar levels, it becomes hard to detect the nectar icon
        if not res: 
            return 0
        #get a screenshot of the buff
        rx, ry = res[1]
        screenH, screenW, *_ = screen.shape
        cropX = max(0, int(rx+offsetX*self.robloxWindow.multi))
        cropY = max(0, int(ry+offsetY*self.robloxWindow.multi))
        cropX2 = min(screenW, cropX+40*self.robloxWindow.multi)
        cropY2 = min(screenH, cropY+40*self.robloxWindow.multi)
        fullBuffImg = screen[cropY:cropY2, cropX:cropX2]
        h,w, *_ = fullBuffImg.shape
        #get the buff level
        fullBuffImg = cv2.cvtColor(fullBuffImg, cv2.COLOR_RGBA2BGR)
        mask = cv2.cvtColor(fullBuffImg, cv2.COLOR_BGR2HLS)
        mask = cv2.inRange(mask, col[0], col[1])
        #cv2.imshow("mask", mask)
        #cv2.waitKey(0)
        #mask = cv2.erode(mask, self.nectarKernel)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
        if not contours:
            # Avoid treating a matched icon with no colored fill as low nectar.
            return 0
        # return the bounding with the largest area
        _, _, _, buffH = cv2.boundingRect(max(contours, key=cv2.contourArea))
        quantity = max(min(100, (buffH/h*100)), 1)
        return quantity


    def getNectars(self):
        nectarQuantity = []
        for nectar in self.nectars:
            nectarQuantity.append(self.getNectar(nectar))
        return nectarQuantity


class HourlyReport():
    def __init__(self, buffDetector: BuffDetector = None, time_format=24, theme="dark", accent="green", configuredUptimeBuffs=None, configuredHourlyBuffs=None):
        self.configuredUptimeBuffs = normalizeUptimeBuffSelection(configuredUptimeBuffs)
        self.configuredHourlyBuffs = normalizeHourlyBuffSelection(configuredHourlyBuffs)

        # hourly snapshot buff detection config (template-based)
        # key → [position, transform, stackable]
        self.hourBuffs = {k: ["top", True, True] for k in self.configuredHourlyBuffs if k not in ("tide_blessing", "mondo")}
        self.hourBuffs.update({
            "tabby_love":   ["top",    True, True],
            "polar_power":  ["top",    True, True],
            "wealth_clock": ["top",    True, True],
            "blessing":     ["middle", True, True],
            "bloat":        ["top",    True, True],
            "tide_blessing":["top",    True, True],
            "mondo":        ["top",    True, True],
        })
        # keep only the buffs that are actually configured
        self.hourBuffs = {k: v for k, v in self.hourBuffs.items() if k in self.configuredHourlyBuffs}

        self.uptimeBearBuffs = {
            "bearmorph1": ["top", True, False],
            "bearmorph2": ["top", True, False],
            "bearmorph3": ["top", True, False],
            "bearmorph4": ["top", True, False],
            "bearmorph5": ["top", True, False],
            "bearmorph6": ["top", True, False],
        }

        # pixel-color detection for continuous uptime buffs
        self.uptimeBuffsColors = {
            "baby_love":    [0xff8de4f3, (5, 1)],
            "haste":        [0xfff0f0f0, (5, 1)],
            "melody":       [0xff242424, (3, 2)],
            "focus":        [0xff22ff06, (5, 1)],
            "bomb_combo":   [0xff272727, (5, 1)],
            "balloon_aura": [0xfffafd38, (5, 1)],
            "boost":        [0xff90ff8e, (5, 1)],
            "blue_boost":   [0xff56a4e4, (4, 2)],
            "red_boost":    [0xffe46156, (4, 2)],
            "inspire":      [0xfff4ef14, (5, 1)],
            # new buffs — colors for pixel detection (added to extend detection support)
            "reindeerfetch":[0xffcc2c2c, (5, 1)],
            "wealth_clock": [0xffe2ac35, (5, 1)],
            "tide_blessing":[0xff91c2fd, (5, 1)],
            "mondo":        [0xff80ff00, (5, 1)],
            "blessing":     [0xffc8ca3c, (5, 1)],
            "bloat":        [0xff4880cc, (4, 1)],
            "honey_mark":   [0xffffd119, (5, 1)],
            "pollen_mark":  [0xffffe994, (5, 1)],
            "jb_share":     [0xfff9ccff, (5, 1)],
            "festive_mark": [0xffc84335, (5, 1)],
            "popstar":      [0xff0096ff, (5, 1)],
            "guiding":      [0xffffff80, (5, 1)],
        }

        self.buffDetector = buffDetector
        self.hourlyReportDrawer = HourlyReportDrawer(time_format, theme=theme, accent=accent)

        # store theme/accent for re-applying when settings change
        self._theme = theme
        self._accent = accent

        # setup stats
        self.hourlyReportStats = {}
        self.sessionReportStats = {}
        self.sessionUptimeBuffsValues = {}
        self.sessionBuffGatherIntervals = []
        self.latestBuffQuantity = []
        self.latestBuffKeys = []
        self.latestNectarQuantity = []
        self.lastEmbedFields = None

    def _defaultSessionReportStats(self):
        return {
            "honey_per_min": [],
            "backpack_per_min": [],
            "bugs": 0,
            "quests_completed": 0,
            "vicious_bees": 0,
            "gathering_time": 0,
            "converting_time": 0,
            "bug_run_time": 0,
            "misc_time": 0,
        }

    def _defaultHourlyUptimeBuffs(self):
        uptimeBuffs = {k:[0]*600 for k in self.uptimeBuffsColors.keys()}
        for k in ["bear", "white_boost"]:
            uptimeBuffs[k] = [0]*600
        return uptimeBuffs

    def _defaultSessionUptimeBuffs(self):
        sessionUptimeBuffs = {k:[] for k in self.uptimeBuffsColors.keys()}
        for k in ["bear", "white_boost"]:
            sessionUptimeBuffs[k] = []
        return sessionUptimeBuffs

    def configuredUptimeBuffDataKeys(self, settings=None):
        rawBuffs = None
        if isinstance(settings, dict):
            rawBuffs = settings.get("hourly_report_uptime_buffs")
        selectedBuffs = normalizeUptimeBuffSelection(rawBuffs, self.configuredUptimeBuffs)
        self.configuredUptimeBuffs = selectedBuffs
        return expandUptimeBuffDataKeys(selectedBuffs)

    def recordUptimeSample(self, index, sampleValues, isGathering=False, monitoredBuffs=None):
        monitored = set(monitoredBuffs or self._defaultSessionUptimeBuffs().keys())
        for buffName in monitored:
            try:
                value = float(sampleValues.get(buffName, 0) or 0)
            except (TypeError, ValueError):
                value = 0
            if value.is_integer():
                value = int(value)
            if buffName not in self.uptimeBuffsValues:
                self.uptimeBuffsValues[buffName] = [0] * 600
            if 0 <= index < len(self.uptimeBuffsValues[buffName]):
                self.uptimeBuffsValues[buffName][index] = value

            if buffName not in self.sessionUptimeBuffsValues:
                self.sessionUptimeBuffsValues[buffName] = []
            self.sessionUptimeBuffsValues[buffName].append(value)

        if not hasattr(self, "buffGatherIntervals") or self.buffGatherIntervals is None:
            self.buffGatherIntervals = [0] * 600
        if 0 <= index < len(self.buffGatherIntervals):
            self.buffGatherIntervals[index] = 1 if isGathering else 0

        if not hasattr(self, "sessionBuffGatherIntervals") or self.sessionBuffGatherIntervals is None:
            self.sessionBuffGatherIntervals = []
        self.sessionBuffGatherIntervals.append(1 if isGathering else 0)

    def filterOutliers(self, values, threshold=3):
        nonZeroValues = [x for x in values if x]
        
        # If no non-zero values or insufficient data, return original values
        if len(nonZeroValues) < 2:
            return values
        
        # Calculate the mean and standard deviation
        mean = np.mean(nonZeroValues)
        std_dev = np.std(nonZeroValues)

        #standard deviation is 0, no outliers, prevent division by zero
        if std_dev == 0:
            return values 
        
        # Calculate Z-scores
        z_scores = [(x - mean) / std_dev for x in values]
        
        # Filter out values with Z-scores greater than the threshold
        filtered_values = [x for x, z in zip(values, z_scores) if abs(z) < threshold or not x]
        
        return filtered_values

    def generateEmbedFields(self, hourlyReportStats, sessionTime, sessionHoney, honeyThisHour, onlyValidHourlyHoney, buffQuantity, nectarQuantity, planterData, reportType="hourly"):
        """Build old-style Discord embed text fields for hybrid embed+image output."""
        def fmt(n):
            return self.hourlyReportDrawer.millify(n).replace(" ", "")
        def fmtTime(s):
            return self.hourlyReportDrawer.displayTime(s, ['h', 'm', 's']).replace(" ", "")
        def pct(part, total):
            return f"{round(part / total * 100, 1)}%" if total else "0%"
        def planterEmoji(planterName):
            return "🪴" if planterName else "🌱"
        def fieldEmoji(fieldName):
            return "🌼" if fieldName else ""
        def nectarEmoji(nectarName):
            return {
                "comforting": "🌙",
                "motivating": "🍄",
                "satisfying": "💜",
                "refreshing": "💧",
                "invigorating": "🔥",
            }.get(nectarName, "✨")

        avgHoney = max(0, sessionHoney / (sessionTime / 3600)) if sessionTime > 0 else 0
        currentHoney = onlyValidHourlyHoney[-1] if onlyValidHourlyHoney else 0
        totalTime = max(1, hourlyReportStats.get("gathering_time", 0) + hourlyReportStats.get("converting_time", 0) + hourlyReportStats.get("bug_run_time", 0) + hourlyReportStats.get("misc_time", 0))

        fields = []

        if reportType == "session":
            session_lines = [
                f"🍯 Current: {fmt(currentHoney)}",
                f"🍯 Honey Earned: {fmt(honeyThisHour)}",
                f"🍯 Hourly Average: {fmt(avgHoney)}",
                f"🕓 Duration: {fmtTime(sessionTime)}",
            ]
            fields.append({"name": "Session", "value": "\n".join(session_lines), "inline": False})
        else:
            honeyLines = [
                f"🍯 Honey Earned: {fmt(honeyThisHour)}",
                f"🍯 Hourly Average: {fmt(avgHoney)}",
            ]
            fields.append({"name": "Hourly", "value": "\n".join(honeyLines), "inline": False})

            session_lines = [
                f"🍯 Current: {fmt(currentHoney)}",
                f"🍯 Session: {fmt(sessionHoney)}",
                f"🕓 Duration: {fmtTime(sessionTime)}",
            ]
            fields.append({"name": "Session", "value": "\n".join(session_lines), "inline": False})

        # Activity breakdown
        gath = hourlyReportStats.get("gathering_time", 0)
        conv = hourlyReportStats.get("converting_time", 0)
        bug  = hourlyReportStats.get("bug_run_time", 0)
        misc = hourlyReportStats.get("misc_time", 0)
        activity_lines = [
            f"🟢 Gathering: {fmtTime(gath)}",
            f"🟠 Converting: {fmtTime(conv)}",
        ]
        if bug > 0:
            activity_lines.append(f"🔴 Bug Run: {fmtTime(bug)}")
        activity_lines.append(f"🔵 Travelling: {fmtTime(misc)}")
        fields.append({"name": "Activity", "value": "\n".join(activity_lines), "inline": False})

        # Bugs / quests / vicious bees (compact inline)
        stats_parts = []
        if hourlyReportStats.get("bugs", 0):
            stats_parts.append(f"🐛 Bugs: {hourlyReportStats['bugs']}")
        if hourlyReportStats.get("quests_completed", 0):
            stats_parts.append(f"📜 Quests: {hourlyReportStats['quests_completed']}")
        if hourlyReportStats.get("vicious_bees", 0):
            stats_parts.append(f"🐝 Vicious: {hourlyReportStats['vicious_bees']}")
        if stats_parts:
            fields.append({"name": "Stats", "value": "  •  ".join(stats_parts), "inline": False})

        # Nectars (non-zero)
        nectar_names = ["comforting", "motivating", "satisfying", "refreshing", "invigorating"]
        nectar_order = [0, 2, 4, 3, 1]
        nectar_parts = []
        for name, data_index in zip(nectar_names, nectar_order):
            if data_index < len(nectarQuantity) and int(nectarQuantity[data_index] or 0) > 0:
                nectar_parts.append(f"{nectarEmoji(name)} {name.title()}: {int(nectarQuantity[data_index])}%")
        if nectar_parts:
            fields.append({"name": "Nectar", "value": "\n".join(nectar_parts), "inline": False})

        # Planters
        if planterData:
            planter_parts = []
            for i in range(len(planterData.get("planters", []))):
                pname = planterData["planters"][i]
                if not pname:
                    continue
                field = planterData.get("fields", [])[i] if i < len(planterData.get("fields", [])) else ""
                harvest = planterData.get("harvestTimes", [])[i] if i < len(planterData.get("harvestTimes", [])) else 0
                remaining = harvest - time.time()
                timeStr = self.hourlyReportDrawer.displayTime(max(0, remaining), ['h', 'm']) if remaining > 0 else "Ready!"
                planter_parts.append(f"{planterEmoji(pname)} {pname.title()}: {timeStr} {fieldEmoji(field)}")
            if planter_parts:
                fields.append({"name": "Planters", "value": "\n".join(planter_parts), "inline": False})

        return fields

    def generateHourlyReport(self, setdat):
        raw_hourly = setdat.get("hourly_report_hourly_buffs", "") if isinstance(setdat, dict) else ""
        hourly_buffs = normalizeHourlyBuffSelection(raw_hourly, self.configuredHourlyBuffs)
        self.configuredHourlyBuffs = hourly_buffs
        self.hourBuffs = {
            "tabby_love":   ["top",    True, True],
            "polar_power":  ["top",    True, True],
            "wealth_clock": ["top",    True, True],
            "blessing":     ["middle", True, True],
            "bloat":        ["top",    True, True],
            "tide_blessing":["top",    True, True],
            "mondo":        ["top",    True, True],
        }
        self.hourBuffs = {k: v for k, v in self.hourBuffs.items() if k in hourly_buffs}
        buffQuantity = self.buffDetector.getBuffsWithImage(self.hourBuffs)
        nectarQuantity = self.buffDetector.getNectars()
        self.latestBuffQuantity = list(buffQuantity)
        self.latestBuffKeys = list(self.hourBuffs.keys())
        self.latestNectarQuantity = list(nectarQuantity)
        #mssScreenshot(save=True)

        #get the hourly report data

        planterData = ""
        #get planter data
        if setdat["planters_mode"] == 1:
            with open("./data/user/manualplanters.txt", "r") as f:
                planterData = f.read()
            f.close()

            if planterData:
                planterData = ast.literal_eval(planterData)
        elif setdat["planters_mode"] == 2:
            with open("./data/user/auto_planters.json", "r") as f:
                planterData = json.load(f)["planters"]
            f.close()
            planterData = {
                "planters": [p["planter"] for p in planterData],
                "harvestTimes": [p["harvest_time"] for p in planterData],
                "fields": [p["field"] for p in planterData],
            }
            if all(not p for p in planterData["planters"]):
                planterData = ""


        #get history
        with open("data/user/hourly_report_history.txt", "r") as f:
            historyData = ast.literal_eval(f.read())
        f.close()
        
        if len(self.hourlyReportStats["honey_per_min"]) < 3:
            self.hourlyReportStats["honey_per_min"] = [0]*3 + self.hourlyReportStats["honey_per_min"]
        #filter out the honey/min
        print(self.hourlyReportStats["honey_per_min"])
        #self.hourlyReportStats["honey_per_min"] = [x for x in self.hourlyReportStats["honey_per_min"] if x]
        self.hourlyReportStats["honey_per_min"] = self.filterOutliers(self.hourlyReportStats["honey_per_min"])
        #calculate honey/min
        honeyPerMin = [0]
        prevHoney = self.hourlyReportStats["honey_per_min"][0]
        for x in self.hourlyReportStats["honey_per_min"][1:]:
            if x > prevHoney:
                honeyPerMin.append((x-prevHoney)/60)
            prevHoney = x
        
        #calculate some stats
        if len(set(self.hourlyReportStats["honey_per_min"])) <= 1:
            onlyValidHourlyHoney = self.hourlyReportStats["honey_per_min"].copy()
        else:
            onlyValidHourlyHoney = [x for x in self.hourlyReportStats["honey_per_min"] if x] #removes all zeroes
        sessionHoney = max(0, onlyValidHourlyHoney[-1]- self.hourlyReportStats["start_honey"])
        sessionTime = time.time()-self.hourlyReportStats["start_time"]
        honeyThisHour = max(0, onlyValidHourlyHoney[-1] - onlyValidHourlyHoney[0])

        hourlyReportStats = copy.deepcopy(self.hourlyReportStats)

        # determine enabled fields and their patterns from profile settings
        enabled_fields = []
        field_patterns = {}
        try:
            profile_fields_settings = loadFields()
        except Exception:
            profile_fields_settings = {}

        fields_list = setdat.get("fields", []) if isinstance(setdat, dict) else []
        fields_enabled = setdat.get("fields_enabled", []) if isinstance(setdat, dict) else []
        # normalize lengths
        if len(fields_enabled) < len(fields_list):
            fields_enabled += [False] * (len(fields_list) - len(fields_enabled))

        for i, fname in enumerate(fields_list):
            try:
                if fields_enabled[i]:
                    enabled_fields.append(fname)
                    pattern = profile_fields_settings.get(fname, {}).get("shape") if isinstance(profile_fields_settings, dict) else None
                    field_patterns[fname] = pattern or "unknown"
            except Exception:
                continue

        # read customization from settings — the report theme follows the macro's GUI theme
        gui_theme = setdat.get("gui_theme", "Brown") if isinstance(setdat, dict) else "Brown"
        theme  = resolveReportTheme(gui_theme)
        accent = setdat.get("hourly_report_accent", "green") if isinstance(setdat, dict) else "green"
        send_embed_text = setdat.get("hourly_report_embed_text", True) if isinstance(setdat, dict) else True

        # parse configurable buff lists from settings (comma-separated strings)
        raw_uptime = setdat.get("hourly_report_uptime_buffs", "") if isinstance(setdat, dict) else ""
        uptime_buffs = normalizeUptimeBuffSelection(raw_uptime, self.configuredUptimeBuffs)
        detectedBuffByKey = {
            key: buffQuantity[i] if i < len(buffQuantity) else 0
            for i, key in enumerate(self.latestBuffKeys or list(self.hourBuffs.keys()))
        }
        displayBuffQuantity = [detectedBuffByKey.get(key, 0) for key in hourly_buffs]

        # re-apply theme/accent if they changed
        if theme != self._theme or accent != self._accent:
            self.hourlyReportDrawer = HourlyReportDrawer(self.hourlyReportDrawer.time_format, theme=theme, accent=accent)
            self._theme = theme
            self._accent = accent

        canvas = self.hourlyReportDrawer.drawHourlyReport(hourlyReportStats, sessionTime, honeyPerMin,
                                                          sessionHoney, honeyThisHour, onlyValidHourlyHoney,
                                                          displayBuffQuantity, nectarQuantity, planterData,
                                                          self.uptimeBuffsValues, self.buffGatherIntervals,
                                                          enabled_fields, field_patterns,
                                                          configuredUptimeBuffs=uptime_buffs,
                                                          configuredHourlyBuffs=hourly_buffs)
        w, h = canvas.size
        canvas = canvas.resize((int(w*1.2), int(h*1.2)))
        canvas.save("hourlyReport.png")

        # generate embed text fields (stored as attribute for caller to use)
        if send_embed_text:
            self.lastEmbedFields = self.generateEmbedFields(
                hourlyReportStats, sessionTime, sessionHoney, honeyThisHour,
                    onlyValidHourlyHoney, displayBuffQuantity, nectarQuantity, planterData, reportType="hourly")
        else:
            self.lastEmbedFields = None

        return hourlyReportStats

    def resetHourlyStats(self):
        self.hourlyReportStats["honey_per_min"] = []
        self.hourlyReportStats["backpack_per_min"] = []
        self.hourlyReportStats["bugs"] = 0
        self.hourlyReportStats["quests_completed"] = 0
        self.hourlyReportStats["vicious_bees"] = 0
        self.hourlyReportStats["gathering_time"] = 0
        self.hourlyReportStats["converting_time"] = 0
        self.hourlyReportStats["bug_run_time"] = 0
        self.hourlyReportStats["misc_time"] = 0

        self.uptimeBuffsValues = self._defaultHourlyUptimeBuffs()
        self.buffGatherIntervals = [0]*600

        self.saveHourlyReportData()
    
    def resetAllStats(self):
        self.hourlyReportStats["start_time"] = 0
        self.hourlyReportStats["start_honey"] = 0
        self.sessionReportStats = self._defaultSessionReportStats()
        self.sessionUptimeBuffsValues = self._defaultSessionUptimeBuffs()
        self.sessionBuffGatherIntervals = []
        self.latestBuffQuantity = []
        self.latestBuffKeys = []
        self.latestNectarQuantity = []
        self.resetHourlyStats()
    
    def addHourlyStat(self, stat, value):
        if isinstance(self.hourlyReportStats[stat], list):
            self.hourlyReportStats[stat].append(value)
        else:
            self.hourlyReportStats[stat] += value

        # Keep session totals independent from hourly resets.
        if stat in self.sessionReportStats:
            if isinstance(self.sessionReportStats[stat], list):
                self.sessionReportStats[stat].append(value)
            else:
                self.sessionReportStats[stat] += value
        self.saveHourlyReportData()
    
    def setSessionStats(self, start_honey, start_time):
        self.hourlyReportStats["start_honey"] = start_honey
        self.hourlyReportStats["start_time"] = start_time
        self.saveHourlyReportData()
    
    def saveHourlyReportData(self):
        with open("data/user/hourly_report_stats.pkl", "wb") as f:
            pickle.dump({
                "hourlyReportStats": self.hourlyReportStats,
                "sessionReportStats": self.sessionReportStats,
                "uptimeBuffsValues": self.uptimeBuffsValues,
                "buffGatherIntervals": self.buffGatherIntervals,
                "sessionUptimeBuffsValues": self.sessionUptimeBuffsValues,
                "sessionBuffGatherIntervals": self.sessionBuffGatherIntervals,
                "latestBuffQuantity": self.latestBuffQuantity,
                "latestBuffKeys": self.latestBuffKeys,
                "latestNectarQuantity": self.latestNectarQuantity,
            }, f)
    
    def loadHourlyReportData(self):
        with open("data/user/hourly_report_stats.pkl", "rb") as f:
            data = pickle.load(f)
            self.hourlyReportStats = data["hourlyReportStats"]
            self.sessionReportStats = data.get("sessionReportStats", self._defaultSessionReportStats())
            self.uptimeBuffsValues = data.get("uptimeBuffsValues", self._defaultHourlyUptimeBuffs())
            self.buffGatherIntervals = data.get("buffGatherIntervals", [0]*600)
            self.sessionUptimeBuffsValues = data.get("sessionUptimeBuffsValues", self._defaultSessionUptimeBuffs())
            self.sessionBuffGatherIntervals = data.get("sessionBuffGatherIntervals", [])
            self.latestBuffQuantity = data.get("latestBuffQuantity", [])
            self.latestBuffKeys = data.get("latestBuffKeys", [])
            self.latestNectarQuantity = data.get("latestNectarQuantity", [])


class HourlyReportDrawer:
    def __init__(self, time_format=24, theme="dark", accent="green"):
        t = THEMES.get(theme, THEMES["dark"])
        self.backgroundColor = t["bg"]
        self.sideBarBackground = t["sidebar_bg"]
        self.cardBackground = t["card_bg"]
        self.bodyColor = t["text_primary"]
        self.subtleColor = t["text_secondary"]
        self.gridColor = t["grid"]
        self.gatherColor = t["gather"]
        self.convertColor = t["convert"]
        self.otherColor = t["other"]
        self.honeyColor = t["honey"]
        # Macro themes bake in their own accent (the webapp --primary); fall back
        # to the configurable accent palette for the legacy dark/midnight/oled themes.
        self.accentColor = t.get("accent", ACCENT_COLORS.get(accent, ACCENT_COLORS["green"]))
        self.accentColorDim = tuple(max(0, int(c * 0.35)) for c in self.accentColor)

        # Panel / graph chrome. For macro themes this is tinted toward the accent
        # so the whole report (panels, graph backgrounds, gridlines) reflects the
        # theme, not just the highlight line. The canvas base (behind/between the
        # panels) gets only a very faint tint so it reads as a dark backdrop.
        # Legacy themes keep the neutral look.
        if "accent" in t:
            tint = _saturate(self.accentColor, _MACRO_TINT_SATURATION)
            self.baseBackgroundColor = _mixColor((18, 18, 18), tint, _MACRO_BASE_BG_MIX)
            self.panelColor     = _mixColor((32, 30, 32), tint, 0.15)
            self.panelOutline   = _mixColor((40, 38, 40), tint, 0.20)
            self.graphBgColor   = _mixColor((20, 20, 20), tint, 0.10)
            self.graphGridColor = _mixColor((47, 47, 55), tint, 0.22)
            self.graphTickColor = _mixColor((64, 60, 78), tint, 0.22)
        else:
            self.baseBackgroundColor = (18, 18, 18)
            self.panelColor     = (32, 30, 32)
            self.panelOutline   = (40, 38, 40)
            self.graphBgColor   = (20, 20, 20)
            self.graphGridColor = (47, 47, 55)
            self.graphTickColor = (64, 60, 78)

        # canvas width is fixed; height is dynamic (cropped to content at the end)
        self.canvasW = 5800
        self.canvasMaxH = 20000  # generous working height, cropped down after drawing
        self.canvasSize = (self.canvasW, self.canvasMaxH)
        self.sidebarWidth = 1650
        self.leftPadding = 150
        self.sidebarPadding = 110
        self.availableSpace = self.canvasW - self.sidebarWidth - self.leftPadding*2
        self.time_format = time_format
        self.hour = datetime.now().hour
        if self.hour == 0:
            self.hour = 23
        else:
            self.hour -= 1
        self.assetPath = "hourly_report/assets"

    def normalizeUptimeBuffList(self, buffList):
        seen = set()
        normalized = []
        for buff in buffList or []:
            key = str(buff).strip().lower().replace(" ", "_")
            if key in BUFF_RENDER_CONFIG and key not in seen:
                normalized.append(key)
                seen.add(key)
            if len(normalized) >= MAX_UPTIME_BUFF_OPTIONS:
                break
        return normalized or DEFAULT_UPTIME_BUFFS[:MAX_UPTIME_BUFF_OPTIONS]

    def _fitText(self, text, maxWidth, weight="semibold", size=60, minSize=28):
        size = int(size)
        while size > minSize:
            font = self.getFont(weight, size)
            bbox = self.draw.textbbox((0, 0), str(text), font=font)
            if bbox[2] - bbox[0] <= maxWidth:
                return font
            size -= 4
        return self.getFont(weight, minSize)

    def _drawPanel(self, box, title=None, titleSize=64):
        x, y, w, h = box
        self.draw.rounded_rectangle((x, y, x + w, y + h), radius=20, fill=self.panelColor, outline=self.panelOutline, width=10)
        if title:
            font = self.getFont("bold", titleSize)
            bbox = self.draw.textbbox((0, 0), title, font=font)
            self.draw.text((x + (w - (bbox[2] - bbox[0])) / 2, y + 16), title, font=font, fill=self.bodyColor)

    def _drawGraphGrid(self, graph, xTicks=6, yTicks=4, timelineTicks=True):
        x, y, w, h = graph
        fill = (*self.graphBgColor, 128)
        self.draw.rectangle((x - 60, y, x + w + 60, y + h), fill=fill)
        for i in range(xTicks + 1):
            gx = x + w * i / xTicks
            self.draw.line((gx, y, gx, y + h), fill=self.graphGridColor, width=3)
        for i in range(1, yTicks):
            gy = y + h * i / yTicks
            self.draw.line((x - 60, gy, x + w + 60, gy), fill=self.graphGridColor, width=3)
        if timelineTicks:
            for i in range(61):
                gx = x + w * i / 60
                tick = 45 if i % 10 == 0 else 25
                self.draw.line((gx, y + h + 20, gx, y + h + 20 + tick), fill=self.graphTickColor, width=3)

    def _timeLabels(self, count=7):
        labels = []
        base = datetime.now().replace(minute=0, second=0, microsecond=0)
        for i in range(count):
            minute = i * 10
            t = base.replace(hour=(base.hour + (minute // 60)) % 24, minute=minute % 60)
            if self.time_format == 12:
                labels.append(t.strftime("%I:%M %p"))
            else:
                labels.append(t.strftime("%H:%M"))
        return labels

    def _drawTimeLabels(self, graph, y):
        x, _, w, _ = graph
        font = self.getFont("bold", 44)
        labels = self._timeLabels()
        for i, label in enumerate(labels):
            bbox = self.draw.textbbox((0, 0), label, font=font)
            self.draw.text((x + w * i / 6 - (bbox[2] - bbox[0]) / 2, y), label, font=font, fill=self.bodyColor)

    def _drawAreaSeries(self, graph, data, color, maxY=None, minY=0, width=6, alpha=115, smooth=False):
        x, y, w, h = graph
        values = [float(v or 0) for v in (data or [0])]
        if len(values) == 1:
            values = values * 2
        if maxY is None:
            maxY = max(max(values), minY + 1)
        maxY = max(maxY, minY + 1)
        interval = w / max(len(values) - 1, 1)
        pts = []
        for i, val in enumerate(values):
            val = max(minY, min(maxY, val))
            pts.append((x + i * interval, y + h - ((val - minY) / (maxY - minY)) * h))
        poly = [(x, y + h)] + pts + [(x + w, y + h)]
        fill = (*color, alpha) if len(color) == 3 else color
        self.draw.polygon(poly, fill=fill)
        if len(pts) > 1:
            if smooth:
                self.draw.line(pts, fill=color[:3], width=width, joint="curve")
            else:
                self.draw.line(pts, fill=color[:3], width=width)

    def _drawYAxisLabels(self, graph, values, fontSize=40):
        x, y, _, h = graph
        font = self.getFont("bold", fontSize)
        for i, text in enumerate(values):
            bbox = self.draw.textbbox((0, 0), text, font=font)
            self.draw.text((x - 120 - (bbox[2] - bbox[0]), y + h * i / max(len(values) - 1, 1) - 28), text, font=font, fill=self.bodyColor)

    def _durationHMS(self, seconds):
        seconds = max(0, int(seconds or 0))
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        return f"{h:02d}:{m:02d}:{s:02d}"

    def _drawActivityCard(self, region, title, rows, honeyGraphData=None, honeyGraphLabels=None):
        self._drawPanel(region, title)
        x, y, w, h = region
        total = max(1, sum(max(0, r["seconds"]) for r in rows))
        angle = -90
        legendTop = y + (432 if title == "SESSION" else 348)
        pieSize = 280
        pieCenterY = legendTop + 110
        pieTop = pieCenterY - pieSize / 2
        pieLeft = x + 95
        pie = (pieLeft, pieTop, pieLeft + pieSize, pieTop + pieSize)
        for row in rows:
            extent = row["seconds"] / total * 360
            self.draw.pieslice(pie, angle, angle + extent, fill=row["color"])
            angle += extent
        font = self.getFont("bold", 48)
        for i, row in enumerate(rows):
            ly = legendTop + i * 88
            self.draw.rounded_rectangle((x + 650, ly, x + 694, ly + 44), radius=4, fill=row["color"])
            labelFont = self._fitText(row["label"], 200, "bold", 48, 34)
            bbox = self.draw.textbbox((0, 0), row["label"], font=labelFont)
            self.draw.text((x + 620 - (bbox[2] - bbox[0]), ly - 13), row["label"], font=labelFont, fill=self.bodyColor)
            self.draw.text((x + 735, ly - 13), self._durationHMS(row["seconds"]), font=font, fill=self.bodyColor)
            pct = f"{round(row['seconds'] / total * 100)}%"
            bbox = self.draw.textbbox((0, 0), pct, font=font)
            self.draw.text((x + w - 140 - (bbox[2] - bbox[0]), ly - 13), pct, font=font, fill=self.bodyColor)
        if honeyGraphData:
            graph = (x + 200, y + h - 560, w - 280, 480)
            self._drawGraphGrid(graph, xTicks=6, yTicks=4, timelineTicks=False)
            minY = min(honeyGraphData)
            maxY = max(max(honeyGraphData), minY + 1)
            span = maxY - minY
            labels = [self.millify(maxY - span * i / 4) for i in range(5)]
            self._drawYAxisLabels(graph, labels, 28)
            self._drawAreaSeries(graph, honeyGraphData, self.gatherColor, maxY=maxY, minY=minY, alpha=120)
            if honeyGraphLabels:
                small = self.getFont("bold", 30)
                for i, label in enumerate(honeyGraphLabels):
                    bbox = self.draw.textbbox((0, 0), label, font=small)
                    self.draw.text((graph[0] + graph[2] * i / 6 - (bbox[2] - bbox[0]) / 2, graph[1] + graph[3] + 14), label, font=small, fill=self.bodyColor)

    def _currentBuffValue(self, values, key):
        data = values.get(key, []) if isinstance(values, dict) else []
        for val in reversed(data):
            if val:
                return val
        return 0

    def _drawLegacyBuffsCard(self, region, buffQuantity, hourlyBuffList, nectarQuantity, uptimeBuffsValues):
        self._drawPanel(region, "BUFFS")
        x, y, w, _ = region
        iconKeys = normalizeHourlyBuffSelection(hourlyBuffList)
        iconCount = max(1, min(MAX_HOURLY_BUFF_OPTIONS, len(iconKeys)))
        iconSize = 220
        for i, key in enumerate(iconKeys):
            iconX = x + 48 + i * ((w - 96 - iconSize) / max(iconCount - 1, 1))
            iconY = y + 124
            asset = HOURLY_BUFF_ASSETS.get(key, key + "_buff")
            try:
                img = Image.open(f"{self.assetPath}/{asset}.png").convert("RGBA").resize((iconSize, iconSize))
                self.canvas.paste(img, (int(iconX), iconY), img)
            except FileNotFoundError:
                pass
            value = self._currentBuffValue(uptimeBuffsValues, key)
            if not value and key in hourlyBuffList:
                idx = hourlyBuffList.index(key)
                value = buffQuantity[idx] if idx < len(buffQuantity) else 0
            txt = f"x{value}" if value else "x0"
            font = self.getFont("bold", 72)
            bbox = self.draw.textbbox((0, 0), txt, font=font, stroke_width=5)
            self.draw.text((iconX + iconSize - 10 - (bbox[2] - bbox[0]), iconY + int(iconSize * 0.6)), txt, font=font, fill=self.bodyColor, stroke_width=5, stroke_fill=(0, 0, 0))

        nectarNames = ["comforting", "motivating", "satisfying", "refreshing", "invigorating"]
        nectarOrder = [0, 2, 4, 3, 1]
        nectarColors = [(126, 158, 179), (147, 125, 179), (179, 152, 167), (120, 179, 117), (179, 89, 81)]
        for i, name in enumerate(nectarNames):
            dataIndex = nectarOrder[i]
            value = int(nectarQuantity[dataIndex] if dataIndex < len(nectarQuantity) and nectarQuantity[dataIndex] else 0)
            cx = int(x + 150 + i * ((w - 100 - 200) / 4))
            cy = y + 510
            color = nectarColors[i]
            self.draw.arc((cx - 100, cy - 100, cx + 100, cy + 100), -90, -90 + value / 100 * 360, fill=color, width=32)
            self.draw.arc((cx - 100, cy - 100, cx + 100, cy + 100), -90 + value / 100 * 360, 270, fill=tuple(int(c * .3) for c in color), width=32)
            font = self.getFont("bold", 54)
            pct = f"{value}%"
            bbox = self.draw.textbbox((0, 0), pct, font=font)
            self.draw.text((cx - (bbox[2] - bbox[0]) / 2, cy - 28), pct, font=font, fill=color)
            label = name[:3].upper()
            labelFont = self.getFont("bold", 48)
            bbox = self.draw.textbbox((0, 0), label, font=labelFont)
            self.draw.text((cx - (bbox[2] - bbox[0]) / 2, y + 630), label, font=labelFont, fill=color)

    def _drawLegacyPlantersCard(self, region, planterData):
        self._drawPanel(region, "PLANTERS")
        x, y, w, _ = region
        names = []
        fields = []
        times = []
        if planterData:
            for i, name in enumerate(planterData.get("planters", [])[:3]):
                if name:
                    names.append(name)
                    fields.append(planterData.get("fields", [""] * 3)[i])
                    times.append(planterData.get("harvestTimes", [0] * 3)[i] - time.time())
        if not names:
            names, fields, times = ["unknown", "unknown", "unknown"], ["None", "None", "None"], [0, 0, 0]
        slot = w / 3
        for i, name in enumerate(names[:3]):
            cx = x + slot * i + slot / 2
            asset = name.replace(" ", "_") + "_planter"
            try:
                img = Image.open(f"{self.assetPath}/{asset}.png").convert("RGBA").resize((220, 220))
                self.canvas.paste(img, (int(cx - 110), y + 110), img)
            except FileNotFoundError:
                pass
            field = str(fields[i]).title()
            font = self._fitText(field, slot - 60, "bold", 52, 34)
            bbox = self.draw.textbbox((0, 0), field, font=font)
            self.draw.text((cx - (bbox[2] - bbox[0]) / 2, y + 340), field, font=font, fill=self.bodyColor)
            duration = "Ready" if times[i] <= 0 else self.displayTime(times[i], ["h", "m"])
            font = self._fitText(duration, slot - 60, "bold", 46, 32)
            bbox = self.draw.textbbox((0, 0), duration, font=font)
            self.draw.text((cx - (bbox[2] - bbox[0]) / 2, y + 406), duration, font=font, fill=(230, 230, 230))

    def _drawLegacyStatsCard(self, region, statsRows):
        self._drawPanel(region, "STATS")
        x, y, w, _ = region
        rows = [
            ("Total Boss Kills", statsRows.get("bosses", 0)),
            ("Total Vic Kills", statsRows.get("vicious_bees", 0)),
            ("Total Bug Kills", statsRows.get("bugs", 0)),
            ("Total Planters", statsRows.get("planters", 0)),
            ("Quests Done", statsRows.get("quests_completed", 0)),
            ("Disconnects", statsRows.get("disconnects", 0)),
        ]
        rowFont = self.getFont("bold", 60)
        y2 = y + 122
        for label, value in rows:
            self.draw.text((x + 170, y2), label, font=rowFont, fill=self.bodyColor)
            self.draw.text((x + w // 2 + 130, y2), str(int(value or 0)), font=rowFont, fill=self.bodyColor)
            self.draw.rounded_rectangle((x + w // 2 + 470, y2 + 36, x + w // 2 + 520, y2 + 48), radius=6, fill=(102, 102, 102))
            y2 += 78

    def _drawLegacyInfoCard(self, region, reportTitle, sessionTime):
        self._drawPanel(region)
        x, y, w, _ = region
        cx = x + w / 2
        try:
            versionText = f"v{getMacroVersion()}"
        except Exception:
            versionText = "version"
        try:
            profileText = getCurrentProfile()
        except Exception:
            profileText = "unknown"
        lines = [
            (reportTitle, (255, 218, 61), 56),
            (f"Fuzzy Macro - {versionText}", (255, 255, 255), 56),
            (f"Runtime: {self._durationHMS(sessionTime)}", (79, 223, 38), 56),
            (f"Profile: {profileText}", self.accentColor, 56),
            ("Made by Logan :)", (4, 180, 228), 56),
        ]
        yy = y + 34
        for text, color, size in lines:
            font = self._fitText(text, w - 140, "bold", size, 34)
            bbox = self.draw.textbbox((0, 0), text, font=font)
            self.draw.text((cx - (bbox[2] - bbox[0]) / 2, yy), text, font=font, fill=color)
            yy += 74

    def _drawUptimeRows(self, region, uptimeBuffList, uptimeBuffsValues, buffGatherIntervals, reportKind):
        self._drawPanel(region, "BUFF UPTIME")
        x, y, w, h = region
        graphX = x + 320
        graphW = 3600
        top = y + 135
        bottomSpace = 130
        rowH = max(95, (h - 235 - bottomSpace) / max(len(uptimeBuffList), 1))
        for idx, key in enumerate(uptimeBuffList):
            cfg = BUFF_RENDER_CONFIG[key]
            chartType, maxY, colorInfo, asset = cfg
            gy = int(top + idx * rowH)
            gh = int(rowH - 8)
            graph = (graphX, gy, graphW, gh)
            self._drawGraphGrid(graph, xTicks=6, yTicks=2, timelineTicks=False)
            try:
                img = Image.open(f"{self.assetPath}/{asset}.png").convert("RGBA").resize((110, 110))
                self.canvas.paste(img, (x + 75, gy + max(0, (gh - 110) // 2)), img)
            except FileNotFoundError:
                pass
            labelFont = self.getFont("bold", 36 if len(uptimeBuffList) > 12 else 44)
            if chartType == "multi":
                colors = colorInfo
                for dataKey, rgb in colors:
                    data = uptimeBuffsValues.get(dataKey, [0] * 600)
                    self._drawAreaSeries(graph, data, rgb, maxY=maxY, width=4, alpha=80)
            else:
                rgb = colorInfo
                data = uptimeBuffsValues.get(key, [0] * 600)
                self._drawAreaSeries(graph, data, rgb, maxY=maxY, width=4, alpha=115)
            label = f"x0-{maxY}" if chartType != "binary" else "x0-1"
            self.draw.text((x + 74, gy + gh - 38), label, font=labelFont, fill=self.bodyColor)
        self._drawTimeLabels((graphX, top, graphW, h - 260), y + h - 85)

    def _drawStatMonitorReport(self, reportTitle, hourlyReportStats, sessionTime, honeyPerSec, sessionHoney,
                               honeyThisHour, onlyValidHourlyHoney, buffQuantity, nectarQuantity, planterData,
                               uptimeBuffsValues, buffGatherIntervals, configuredUptimeBuffs=None,
                               configuredHourlyBuffs=None, sessionStats=None):
        self.canvasW = 6000
        self.canvasMaxH = 5800
        self.canvasSize = (6000, 5800)
        self.canvas = Image.new("RGBA", self.canvasSize, (*self.baseBackgroundColor, 255))
        self.draw = ImageDraw.Draw(self.canvas)

        regions = {
            "honey/sec": (120, 120, 4080, 1080),
            "stats": (4320, 120, 1560, 5560),
            "backpack": (120, 1320, 4080, 1140),
            "buffs": (120, 2580, 4080, 3100),
        }
        statRegions = {
            "lasthour": (4420, 220, 1360, 1206),
            "session": (4420, 1626, 1360, 1289),
            "buffs": (4420, 3015, 1360, 720),
            "planters": (4420, 3835, 1360, 495),
            "stats": (4420, 4440, 1360, 620),
            "info": (4420, 5160, 1360, 420),
        }
        for key, region in regions.items():
            self._drawPanel(region, None)
        for key, region in statRegions.items():
            self._drawPanel(region, None)

        self._drawPanel(regions["honey/sec"], "HONEY/SEC")
        honeyGraph = (440, 250, 3600, 800)
        self._drawGraphGrid(honeyGraph, xTicks=6, yTicks=4)
        honeyData = honeyPerSec or [0]
        maxHoney = max(max(honeyData), 1)
        self._drawYAxisLabels(honeyGraph, [self.millify(maxHoney - maxHoney * i / 4) for i in range(5)], 40)
        self._drawAreaSeries(honeyGraph, honeyData, (254, 202, 64), maxY=maxHoney, alpha=125)
        self._drawTimeLabels(honeyGraph, regions["honey/sec"][1] + regions["honey/sec"][3] - 85)

        self._drawPanel(regions["backpack"], "BACKPACK")
        backpackGraph = (440, 1450, 3600, 860)
        self._drawGraphGrid(backpackGraph, xTicks=6, yTicks=2)
        self._drawYAxisLabels(backpackGraph, ["100%", "50%", "0%"], 40)
        self._drawAreaSeries(backpackGraph, hourlyReportStats.get("backpack_per_min", [0]), (65, 255, 128), maxY=100, alpha=130)
        self._drawTimeLabels(backpackGraph, regions["backpack"][1] + regions["backpack"][3] - 85)

        uptimeList = self.normalizeUptimeBuffList(configuredUptimeBuffs)
        self._drawUptimeRows(regions["buffs"], uptimeList, uptimeBuffsValues, buffGatherIntervals, reportTitle)

        totalBreakdown = max(1, sessionTime)
        hourRows = [
            {"label": "Gather", "seconds": hourlyReportStats.get("gathering_time", 0), "color": self.gatherColor},
            {"label": "Convert", "seconds": hourlyReportStats.get("converting_time", 0), "color": self.convertColor},
            {"label": "Other", "seconds": hourlyReportStats.get("bug_run_time", 0) + hourlyReportStats.get("misc_time", 0), "color": self.otherColor},
        ]
        sessionSource = sessionStats or {}
        sessionRows = [
            {"label": "Gather", "seconds": sessionSource.get("gathering_time", hourlyReportStats.get("gathering_time", 0)), "color": self.gatherColor},
            {"label": "Convert", "seconds": sessionSource.get("converting_time", hourlyReportStats.get("converting_time", 0)), "color": self.convertColor},
            {"label": "Other", "seconds": sessionSource.get("bug_run_time", hourlyReportStats.get("bug_run_time", 0)) + sessionSource.get("misc_time", hourlyReportStats.get("misc_time", 0)), "color": self.otherColor},
        ]

        self._drawActivityCard(statRegions["lasthour"], "LAST HOUR", hourRows, honeyData, self._timeLabels())
        x, y, w, _ = statRegions["lasthour"]
        topFont = self.getFont("bold", 60)
        self.draw.text((x + 200, y + 96), "Honey Earned", font=topFont, fill=self.bodyColor)
        self.draw.text((x + 720, y + 96), self.millify(honeyThisHour), font=topFont, fill=self.bodyColor)
        self.draw.polygon([(x + 980, y + 119), (x + 955, y + 161), (x + 1005, y + 161)], fill=(0, 255, 0))
        avg = max(0, sessionHoney / (totalBreakdown / 3600)) if totalBreakdown else 0
        self.draw.text((x + 170, y + 180), "Hourly Average", font=topFont, fill=self.bodyColor)
        self.draw.text((x + 720, y + 180), self.millify(avg), font=topFont, fill=self.bodyColor)

        self._drawActivityCard(statRegions["session"], "SESSION", sessionRows, onlyValidHourlyHoney or [0], self._timeLabels())
        x, y, w, _ = statRegions["session"]
        currentHoney = onlyValidHourlyHoney[-1] if onlyValidHourlyHoney else 0
        sessionLines = [("Current Honey", self.millify(currentHoney)), ("Session Honey", self.millify(sessionHoney)), ("Session Time", self._durationHMS(sessionTime))]
        for i, (label, value) in enumerate(sessionLines):
            yy = y + 96 + i * 84
            self.draw.text((x + 210, yy), label, font=topFont, fill=self.bodyColor)
            self.draw.text((x + 720, yy), value, font=topFont, fill=self.bodyColor)

        hourlyBuffList = configuredHourlyBuffs if configuredHourlyBuffs is not None else DEFAULT_HOURLY_BUFFS
        self._drawLegacyBuffsCard(statRegions["buffs"], buffQuantity, hourlyBuffList, nectarQuantity, uptimeBuffsValues)
        self._drawLegacyPlantersCard(statRegions["planters"], planterData)
        statsRows = {
            "bugs": sessionSource.get("total_bugs", sessionSource.get("bugs", hourlyReportStats.get("bugs", 0))),
            "vicious_bees": sessionSource.get("total_vicious_bees", sessionSource.get("vicious_bees", hourlyReportStats.get("vicious_bees", 0))),
            "quests_completed": sessionSource.get("total_quests", sessionSource.get("quests_completed", hourlyReportStats.get("quests_completed", 0))),
            "planters": len([p for p in planterData.get("planters", []) if p]) if planterData else 0,
        }
        self._drawLegacyStatsCard(statRegions["stats"], statsRows)
        self._drawLegacyInfoCard(statRegions["info"], reportTitle, sessionTime)
        return self.canvas

    def transformXLabelTime(self, i, val):
        if i%10:
            return
        hour = self.hour
        if val == 60:
            hour += 1
            if hour == 24:
                hour = 0
            val = 0

        time_str = f"{str(hour).zfill(2)}:{str(val).zfill(2)}"
        if self.time_format == 12:
            # Convert to 12-hour format
            hour_12 = hour % 12
            if hour_12 == 0:
                hour_12 = 12
            am_pm = "AM" if hour < 12 else "PM"
            time_str = f"{str(hour_12).zfill(2)}:{str(val).zfill(2)} {am_pm}"

        return time_str

    def millify(self, n):
        if not n: return "0"
        millnames = ['',' K',' M',' B',' T', 'Qd']
        n = float(n)
        millidx = max(0,min(len(millnames)-1,
                            int(math.floor(0 if n == 0 else math.log10(abs(n))/3))))

        return '{:.2f} {}'.format(n / 10**(3 * millidx), millnames[millidx])

    def displayTime(self, seconds, units = ['w','d','h','m','s']):
        intervals = (
            ('w', 604800),  # 60 * 60 * 24 * 7
            ('d', 86400),    # 60 * 60 * 24
            ('h', 3600),    # 60 * 60
            ('m', 60),
            ('s', 1),
        )
        result = []

        for name, count in intervals:
            value = seconds // count
            if value:
                seconds -= value * count
                if value == 1:
                    name = name.rstrip('s')
                if name in units:
                    value = int(value)
                    if value < 10:
                        value = "0"+str(value)
                    result.append("{}{}".format(value, name))
        if not result:
            return "0s"
        return ' '.join(result)
        
    def getFont(self, weight, fontSize):
        return ImageFont.truetype(f"hourly_report/Inter/static/Inter_18pt-{weight.title()}.ttf", fontSize)

    def getGradientColorAtRatio(self, ratio, gradientSpec):
        #calculates the RGBA color from gradientSpec at a given vertical ratio (0=bottom, 1=top)
        if not gradientSpec:
            return (0, 0, 0, 0) # Default transparent black if no spec

        sorted_stops = sorted(gradientSpec.items()) # list of (position_ratio, color_tuple)

        # Clamp ratio
        ratio = max(0.0, min(1.0, ratio))

        # Find which two stops this ratio is between
        for j in range(len(sorted_stops) - 1):
            pos1, col1 = sorted_stops[j]
            pos2, col2 = sorted_stops[j + 1]
            if pos1 <= ratio <= pos2:
                if pos2 - pos1 == 0:
                    local_ratio = 0
                else:
                    local_ratio = (ratio - pos1) / (pos2 - pos1)

                #interpolate RGBA values
                try:
                    r = int(col1[0] + (col2[0] - col1[0]) * local_ratio)
                    g = int(col1[1] + (col2[1] - col1[1]) * local_ratio)
                    b = int(col1[2] + (col2[2] - col1[2]) * local_ratio)
                    #handle alpha
                    a = 255 
                    if len(col1) > 3 and len(col2) > 3:
                            a = int(col1[3] + (col2[3] - col1[3]) * local_ratio)
                    elif len(col1) > 3:
                        a = col1[3]
                    elif len(col2) > 3:
                        a = col2[3]

                    return (r, g, b, a)
                except IndexError:
                    print(f"Warning: Color tuple length mismatch in gradientSpec between {col1} and {col2}")
                    return (0,0,0,255)

        # If ratio is below the first stop or above the last stop (should not happen with clamping)
        if ratio < sorted_stops[0][0]:
            return sorted_stops[0][1] # Return first color
        else:
            return sorted_stops[-1][1] # Return last color


    def drawGraph(self, graphX, graphY, width, height, xData, datasets, maxY = None, showXAxisLabels=True, showYAxisLabels=True, ticks=5, yLabelFunc=None, xLabelFunc=None):
        # Validate data lengths
        for dataset in datasets:
            data = dataset["data"]
            #pad the data
            data = [0]*(len(xData) - len(data)) + data
        
            # Prevent division by zero with minimal data
            xInterval = width / max(len(data) - 1, 1)
            if not maxY:
                maxY = max(data) if data else 1
                if not maxY:
                    maxY = 1
            else:
                data = [maxY if y > maxY else y for y in data]

            font = self.getFont("semibold", 60)
            fontColor = self.subtleColor
            gridColor = self.gridColor
            #draw xaxis
            if showXAxisLabels:
                for i, val in enumerate(xData):
                    val = xLabelFunc(i, val) if xLabelFunc else val
                    if val:
                        val = str(val)
                        #get the text width, so the text can be centered with the x axis point
                        bbox = self.draw.textbbox((0, 0), val, font=font)
                        textWidth = bbox[2] - bbox[0]
                        self.draw.text((graphX+xInterval*i - textWidth/2, graphY+20), val, font=font, fill= fontColor)
            
            #draw y labels and y grid
            #calculating ticks
            yInterval = height/max(ticks-1, 1)
            yValInterval = maxY/max(ticks-1, 1)

            for i in range(ticks):
                y = graphY - yInterval*i
                if showYAxisLabels:
                    text = yValInterval*i
                    text = yLabelFunc(i, text) if yLabelFunc else text
                    if text:
                        text = str(text)
                        bbox = self.draw.textbbox((0, 0), text, font=font)
                        textWidth = bbox[2] - bbox[0]
                        textHeight = bbox[3] - bbox[1]
                        self.draw.text((graphX - textWidth - 100, y - textHeight/2), text, font=font, fill= fontColor)
                self.draw.line((graphX-30, y, graphX+30+width, y), fill=gridColor, width=3)


            # Collect curve points
            points = []
            for i, val in enumerate(data):
                px = graphX + i * xInterval
                py = graphY - (val / maxY * height)
                points.append((px, py))
            # Close polygon at bottom
            points.append((graphX + (len(xData) - 1) * xInterval, graphY))
            points.append((graphX, graphY))

            #make gradient
            gradientSpec = dataset.get("gradientFill", None)
            if gradientSpec:
                gradient = Image.new('RGBA', (int(width), int(height)), (0, 0, 0, 0))
                grad_draw = ImageDraw.Draw(gradient)
                sorted_stops = sorted(gradientSpec.items())  # list of (position, color)
                stop_positions = [int(pos * height) for pos, _ in sorted_stops]

                for i in range(height):
                    # Normalize position (0 to 1)
                    ratio = i / float(max(height - 1, 1))

                    # Find which two stops this ratio is between
                    for j in range(len(sorted_stops) - 1):
                        pos1, col1 = sorted_stops[j]
                        pos2, col2 = sorted_stops[j + 1]
                        if pos1 <= ratio <= pos2:
                            local_ratio = (ratio - pos1) / (pos2 - pos1)
                            r = int(col1[0] + (col2[0] - col1[0]) * local_ratio)
                            g = int(col1[1] + (col2[1] - col1[1]) * local_ratio)
                            b = int(col1[2] + (col2[2] - col1[2]) * local_ratio)
                            a = int(col1[3] + (col2[3] - col1[3]) * local_ratio)
                            grad_draw.line([(0, height - i), (width, height - i)], fill=(r, g, b, a))
                            break
                

            #composite gradient on dark background
            bg = Image.new('RGBA', (int(width), int(height)), (*self.backgroundColor, 255))
            gradient = Image.alpha_composite(bg, gradient)

            #create a mask with polygon in the shape of the graph
            mask = Image.new('L', (int(width), int(height)), 0)
            mask_draw = ImageDraw.Draw(mask)
            rel_pts = [(px - graphX, py - (graphY - height)) for px, py in points]
            mask_draw.polygon(rel_pts, fill=255)

            #paste the gradient and mask onto the canvas
            self.canvas.paste(gradient, (graphX, graphY - height), mask)

            lineColor = dataset["lineColor"]
            #gradient color.
            if gradientSpec and lineColor == "gradient":
                #draw the line
                for i in range(len(points) - 3):
                    #Since line doesnt accept gradients, we will break the line down into segments, 
                    #and assign each segment a color
                    x0, y0 = points[i]
                    x1, y1 = points[i+1]

                    #calculate length of the line
                    dx = x1 - x0
                    dy = y1 - y0
                    length = math.sqrt(dx*dx + dy*dy)

                    if length == 0: continue # Skip zero-length segments

                    #get the number of segments
                    segmentCount = max(1, int(length / 10))

                    for k in range(segmentCount):
                        t0 = k / segmentCount
                        t1 = (k + 1) / segmentCount

                        sub_x0 = x0 + dx * t0
                        sub_y0 = y0 + dy * t0
                        sub_x1 = x0 + dx * t1
                        sub_y1 = y0 + dy * t1
                        mid_y = (sub_y0 + sub_y1) / 2.0
                        # Convert Y coord to ratio (0=bottom, 1=top)
                        mid_yRatio = (graphY - mid_y) / height if height > 0 else 0.0

                        # Get color for this ratio
                        r, g, b, a = self.getGradientColorAtRatio(mid_yRatio, gradientSpec)

                        self.draw.line(
                            (int(sub_x0), int(sub_y0), int(sub_x1), int(sub_y1)),
                            fill=(r, g, b), # Use opaque RGB for line
                            width=7
                        )

            else:
                # Draw the entire line with a solid color
                # Use points[:len(data)] to only draw line over actual data points, not polygon closing points
                self.draw.line(points[:len(data)], fill=lineColor, width=7)

    def drawDoughnutChart(self, x, y, size, datasets, holeRatio = 0.6):

        total = sum([x["data"] for x in datasets])
        if not total:
            total = 1
        angleStart = -90
        chartArea = (x, y, x+size, y+size)

        #draw the section
        for dataset in datasets:
            angleEnd = angleStart + (dataset["data"] / total) * 360
            self.draw.pieslice(chartArea, angleStart, angleEnd, fill=dataset["color"])
            angleStart = angleEnd

        #draw the hole
        if holeRatio > 0:
            hole_size = int(size * holeRatio)
            offset = (size - hole_size) // 2
            hole_bbox = (x+offset, y+offset, x+offset + hole_size, y+offset + hole_size)
            self.draw.ellipse(hole_bbox, fill=self.sideBarBackground)

    def drawProgressChart(self, x, y, size, percentage, color, holeRatio = 0.6,):
        chartArea = (x, y, x+size, y+size)

        #draw the section
        self.draw.pieslice(chartArea, -90, 360, fill=(*color, 140))
        self.draw.pieslice(chartArea, -90, (int(percentage) / 100) * 360 - 90, fill=color)

        #draw the hole
        if holeRatio > 0:
            hole_size = int(size * holeRatio)
            offset = (size - hole_size) // 2
            hole_bbox = (x+offset, y+offset, x+offset + hole_size, y+offset + hole_size)
            self.draw.ellipse(hole_bbox, fill=self.sideBarBackground)

        font = self.getFont("semibold", 65)
        text = f"{int(percentage)}%"
        text_bbox = self.draw.textbbox((0, 0), text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        self.draw.text((x + (size - text_width) // 2, y + (size - text_height) // 2 - 10), text, fill=self.bodyColor, font=font)

    def drawStatCard(self, x, y, statImage, statValue, statTitle, fontColor = None, imageColor = None, cardWidth = 700, cardHeight = 750):
        leftPadding = x+100
        self.draw.rounded_rectangle((x, y, x+cardWidth, y+cardHeight), fill=self.cardBackground, radius=55)
        #load the image
        img = Image.open(f"{self.assetPath}/{statImage}.png").convert("RGBA")
        width, height = img.size
        imageHeight = 190
        imageWidth = int(width*(imageHeight/height))
        img = img.resize((imageWidth, imageHeight))

        #recolor the image
        if imageColor:
            r,g,b = imageColor
            pixels = img.load()
            for i in range(img.width):
                for j in range(img.height):
                    _, _, _, a = pixels[i, j]
                    if a > 0:  #only recolor non-transparent pixels
                        pixels[i, j] = (r,g,b, a)

        self.canvas.paste(img, (leftPadding, y + 95), img)

        self.draw.text((leftPadding, y+370), str(statValue), font=self.getFont("semibold", 80), fill=fontColor if fontColor else self.bodyColor)
        self.draw.text((leftPadding, y+545), statTitle, font=self.getFont("medium", 52), fill=self.subtleColor)

    def drawBuffUptimeGraphStackableBuff(self, y, datasets, imageName, maxY=10, xData=None, xLabelFunc=None):
        #draw the graph
        graphHeight = 450
        graphXStart = self.leftPadding+450
        if xData is None:
            maxLen = max((len(dataset.get("data", [])) for dataset in datasets), default=0)
            xData = list(range(maxLen if maxLen else 1))
        self.drawGraph(graphXStart, y, self.availableSpace-570, graphHeight, xData, datasets, maxY=maxY, showXAxisLabels=bool(xLabelFunc), showYAxisLabels=False, ticks=3, xLabelFunc=xLabelFunc)

        #load the icon
        imageDimension = 170
        imageX = graphXStart - 200 - imageDimension
        imageY = y - graphHeight//2 - imageDimension//2 + len(datasets)*10
        try:
            img = Image.open(f"{self.assetPath}/{imageName}.png").convert("RGBA")
            img = img.resize((imageDimension, imageDimension))
            self.canvas.paste(img, (imageX, imageY), img)
        except FileNotFoundError:
            pass

        self.draw.text((imageX, imageY + imageDimension), f"x0-{maxY}", font=self.getFont("semibold", 65), fill=self.bodyColor)

        for i, dataset in enumerate(datasets):
            if dataset.get("average"):
                self.draw.text((imageX, imageY - (90+60*i)), dataset["average"], font=self.getFont("semibold", 60), fill=dataset["lineColor"])

    def drawBuffUptimeGraphUnstackableBuff(self, y, datasets, imageName, renderTime = False, xData=None, xLabelFunc=None):

        def transformXLabel(i, val):
            if i%100:
                return
            val //= 10
            hour = self.hour
            if val == 60:
                hour += 1
                if hour == 24:
                    hour = 0
                val = 0
            return f"{str(hour).zfill(2)}:{str(val).zfill(2)}"

        #draw the graph
        graphHeight = 250
        graphXStart = self.leftPadding+450
        if xData is None:
            maxLen = max((len(dataset.get("data", [])) for dataset in datasets), default=0)
            xData = list(range(maxLen if maxLen else 1))
        labelFunc = xLabelFunc if xLabelFunc else transformXLabel
        self.drawGraph(graphXStart, y, self.availableSpace-570, graphHeight, xData, datasets, maxY=1, showXAxisLabels=renderTime or bool(xLabelFunc), showYAxisLabels=False, ticks=2, xLabelFunc=labelFunc)

        #load the icon
        imageDimension = 170
        imageX = graphXStart - 200 - imageDimension
        imageY = y - graphHeight//2 - imageDimension//2 + len(datasets)*10
        try:
            img = Image.open(f"{self.assetPath}/{imageName}.png").convert("RGBA")
            img = img.resize((imageDimension, imageDimension))
            self.canvas.paste(img, (imageX, imageY), img)
        except FileNotFoundError:
            pass

    def drawSessionStat(self, y, imageName, label, value, valueColor):
        imgContainerDimension = 180
        self.draw.rounded_rectangle((self.sidebarX, y, self.sidebarX+imgContainerDimension, y+imgContainerDimension), radius=50, fill=self.cardBackground)
        img = Image.open(f"{self.assetPath}/{imageName}.png").convert("RGBA")
        width, height = img.size
        imageWidth = 120
        imageHeight = int(height*(imageWidth/width))
        img = img.resize((imageWidth, imageHeight))
        #center the image in the container
        self.canvas.paste(img, (self.sidebarX + (imgContainerDimension-imageWidth)//2 , y + (imgContainerDimension-imageHeight)//2), img)

        #draw label and value
        #make sure they are vertically centered with the image container
        font = self.getFont("semibold", 68)
        ascent, _ = font.getmetrics()
        textY = y + (imgContainerDimension - ascent)//2
        self.draw.text((self.sidebarX+imgContainerDimension+50, textY), label, self.bodyColor, font=font)
        #value is right-aligned
        bbox = self.draw.textbbox((0, 0), value, font=font)
        textWidth = bbox[2] - bbox[0]
        self.draw.text((self.canvasSize[0]-self.sidebarPadding-textWidth, textY), str(value), valueColor, font=font)

    def drawTaskTimes(self, y, datasets, totalTime=None):
        legendIconDimension = 80
        font = self.getFont("medium", 68)
        x = self.sidebarX
        totalData = totalTime if totalTime is not None else sum([x["data"] for x in datasets])
        if not totalData:
            totalData = 1

        for dataset in datasets:
            self.draw.rounded_rectangle((x, y, x+legendIconDimension, y+legendIconDimension), fill=dataset["color"], radius=10)
            bbox = self.draw.textbbox((0, 0), dataset["label"], font=font)
            textHeight = bbox[3] - bbox[1]
            textY = y #+ (legendIconDimension - textHeight) // 2 -25
            self.draw.text((x+legendIconDimension + 50, textY), f"{dataset['label']}:", self.bodyColor, font=font)
            self.draw.text((x+legendIconDimension + 600, textY), self.displayTime(dataset["data"]), self.bodyColor, font=font)
            self.draw.text((x+legendIconDimension + 1000, textY), f"{round(dataset['data']/totalData*100, 1)}%", (220,220,220), font=font)
            y+= 150

        y += 100
        doughnutChartSize = 600
        self.drawDoughnutChart(self.sidebarX + 450, y, doughnutChartSize, datasets, holeRatio=0.4)

    def drawPlanters(self, y, planterNames, planterTimes, planterFields):
        fieldNectarIcons = {
            "sunflower": "satisfying",
            "dandelion": "comforting",
            "mushroom": "motivating",
            "blue flower": "refreshing",
            "clover": "invigorating",
            "strawberry": "refreshing",
            "spider": "motivating",
            "bamboo": "comforting",
            "pineapple": "satisfying",
            "stump": "motivating",
            "cactus": "invigorating",
            "pumpkin": "satisfying",
            "pine tree": "comforting",
            "rose": "motivating",
            "mountain top": "invigorating",
            "pepper": "invigorating",
            "coconut": "refreshing"
        }

        planterX = self.sidebarX
        fieldFont = self.getFont("semibold", 68)
        timeFont = self.getFont("semibold", 55)
        for i in range(len(planterNames)):
            if not planterNames[i]:
                continue
            bbox = self.draw.textbbox((0, 0), planterFields[i].title(), font=fieldFont)
            fieldTextWidth = bbox[2] - bbox[0]

            nectarImg = Image.open(f'{self.assetPath}/{fieldNectarIcons[planterFields[i]]}.png')
            width, height = nectarImg.size
            nectarImageHeight = bbox[3] - bbox[1]
            nectarImageWidth = int(width*(nectarImageHeight/height))
            nectarImg = nectarImg.resize((nectarImageWidth, nectarImageHeight))

            fieldAndNectarWidth = fieldTextWidth + nectarImageWidth + 30

            img = Image.open(f'{self.assetPath}/{planterNames[i].replace(" ","_")}_planter.png')
            width, height = img.size
            imageHeight = 250
            imageWidth = int(width*(imageHeight/height))
            img = img.resize((imageWidth, imageHeight))

            timeText = self.displayTime(planterTimes[i], ["h", "m"]) if planterTimes[i] > 0 else "Ready!"
            bbox = self.draw.textbbox((0, 0), timeText, font=timeFont)
            timeTextWidth = bbox[2] - bbox[0]

            maxWidth = max(fieldAndNectarWidth, imageWidth, timeTextWidth)
            self.canvas.paste(img, (planterX + (maxWidth-imageWidth)//2, y), img)
            self.draw.text((planterX + (maxWidth - fieldAndNectarWidth)//2, y+300), planterFields[i].title(), font=fieldFont, fill= self.bodyColor) 
            self.canvas.paste(nectarImg, (planterX + (maxWidth - fieldAndNectarWidth)//2 + fieldTextWidth + 30, y+315), nectarImg)
            self.draw.text((planterX + (maxWidth - timeTextWidth)//2, y+400), timeText, font=timeFont, fill= tuple([205]*3)) 

            planterX += maxWidth + 200

    def drawBuffs(self, y, buffData, hourlyBuffKeys=None, perRow=4):
        if hourlyBuffKeys is None:
            hourlyBuffKeys = DEFAULT_HOURLY_BUFFS

        font = self.getFont("bold", 60)
        availWidth = self.canvasSize[0] - self.sidebarPadding - self.sidebarX
        colWidth = availWidth // perRow
        imageWidth = min(230, colWidth - 30)
        rowHeight = 300
        for i, buffKey in enumerate(hourlyBuffKeys):
            buff = str(buffData[i]) if i < len(buffData) else "0"
            col = i % perRow
            row = i // perRow
            x = self.sidebarX + colWidth * col
            yy = y + row * rowHeight
            assetName = HOURLY_BUFF_ASSETS.get(buffKey, buffKey + "_buff")
            try:
                img = Image.open(f"{self.assetPath}/{assetName}.png").convert("RGBA")
            except FileNotFoundError:
                continue
            width, height = img.size
            imageHeight = int(height * (imageWidth / width))
            img = img.resize((imageWidth, imageHeight))

            overlay = Image.new("RGBA", img.size, (0, 0, 0, 100 if buff == "0" else 20))
            img = Image.alpha_composite(img, overlay)
            self.canvas.paste(img, (x, yy), img)

            if buff != "0":
                buffText = f"x{buff}"
                bbox = self.draw.textbbox((0, 0), buffText, font=font, stroke_width=4)
                textWidth = bbox[2] - bbox[0]
                self.draw.text((x + imageWidth - textWidth - 5, yy + imageHeight - 60 - 15), buffText, fill=self.bodyColor, font=font, stroke_width=4, stroke_fill=(0, 0, 0))

    def drawNectars(self, y, nectarData):
        nectarColors = [(165, 207, 234), (235, 120, 108), (194, 166, 236), (162, 239, 163), (239, 205, 224)]
        nectarNames = ["comforting", "motivating", "satisfying", "refreshing", "invigorating"]
        nectarOrder = [0, 2, 4, 3, 1]
        visibleNectars = [(i, dataIndex) for i, dataIndex in enumerate(nectarOrder) if dataIndex < len(nectarData)]
        count = max(len(visibleNectars), 1)
        availWidth = self.canvasSize[0] - self.sidebarPadding - self.sidebarX
        slot = availWidth // count
        progressChartSize = min(300, slot - 20)
        imageHeight = int(progressChartSize * 0.4)
        for slotIndex, (i, dataIndex) in enumerate(visibleNectars):
            x = self.sidebarX + slotIndex * slot + (slot - progressChartSize) // 2
            self.drawProgressChart(x, y, progressChartSize, nectarData[dataIndex], nectarColors[i], 0.75)

            img = Image.open(f"{self.assetPath}/{nectarNames[i]}.png").convert("RGBA")
            width, height = img.size
            imageWidth = int(width*(imageHeight/height))
            img = img.resize((imageWidth, imageHeight))
            self.canvas.paste(img, (x + (progressChartSize-imageWidth)//2, y+progressChartSize + 60), img)

    def _drawHeaderBanner(self, title, subtitle):
        """Full-width header banner with accent stripe, title (left) and macro identity (right). Returns bottom y."""
        x0, y0 = self.leftPadding, 80
        x1 = self.canvasW - self.leftPadding
        bannerH = 360
        y1 = y0 + bannerH
        self.draw.rounded_rectangle((x0, y0, x1, y1), radius=55, fill=self.cardBackground)
        # title + subtitle
        self.draw.text((x0+90, y0+75), title, fill=self.bodyColor, font=self.getFont("bold", 120))
        self.draw.text((x0+95, y0+235), subtitle, fill=self.subtleColor, font=self.getFont("medium", 58))

        # macro identity on the right
        try:
            icon = Image.open(f"{self.assetPath}/macro_icon.png").convert("RGBA").resize((190, 190))
            iconX = x1 - 230
            iconY = y0 + (bannerH - 190) // 2
            self.canvas.paste(icon, (iconX, iconY), icon)
            textRight = iconX - 45
        except FileNotFoundError:
            textRight = x1 - 60

        try:
            profile_name = getCurrentProfile()
        except Exception:
            profile_name = None
        try:
            version_text = f"v{getMacroVersion()}"
        except Exception:
            version_text = None

        lines = [("Fuzzy Macro", self.getFont("semibold", 68), self.bodyColor)]
        if profile_name:
            lines.append((f"Profile: {profile_name}", self.getFont("medium", 50), self.subtleColor))
        if version_text:
            lines.append((version_text, self.getFont("medium", 40), self.subtleColor))

        total_h = sum((f.getmetrics()[0] + 14) for _, f, _ in lines) - 14
        ty = y0 + (bannerH - total_h) // 2
        for text, f, col in lines:
            bbox = self.draw.textbbox((0, 0), text, font=f)
            tw = bbox[2] - bbox[0]
            self.draw.text((textRight - tw, ty), text, font=f, fill=col)
            ty += f.getmetrics()[0] + 14

        return y1

    def _drawBuffRow(self, x, y, colW, rowH, buff_key, uptimeBuffsValues, getAverageBuff, xLabelFunc=None):
        """Draw a single buff uptime cell: icon + name on the left, mini graph filling the rest."""
        cfg = BUFF_RENDER_CONFIG.get(buff_key)
        if not cfg:
            return
        chart_type, max_y, color_info, asset = cfg

        iconDim = 150
        iconX = x + 10
        iconY = y + (rowH - iconDim) // 2 - 30
        try:
            img = Image.open(f"{self.assetPath}/{asset}.png").convert("RGBA").resize((iconDim, iconDim))
            self.canvas.paste(img, (iconX, iconY), img)
        except FileNotFoundError:
            pass
        # buff name under the icon
        name = buff_key.replace("_", " ").title()
        self.draw.text((iconX - 10, iconY + iconDim + 8), name, font=self.getFont("medium", 40), fill=self.subtleColor)

        graphX = x + iconDim + 90
        graphW = colW - iconDim - 110
        graphH = rowH - 150
        baseline = y + rowH - 70

        if chart_type == "multi":
            datasets, avgs = [], []
            for dk, rgb in color_info:
                data = uptimeBuffsValues.get(dk, [0] * 600)
                r, g, b = rgb
                datasets.append({"data": data, "lineColor": rgb, "gradientFill": {0: (r, g, b, 10), 1: (r, g, b, 120)}})
                avgs.append((getAverageBuff(data), rgb))
            my = max_y
        elif chart_type == "stackable":
            r, g, b = color_info
            data = uptimeBuffsValues.get(buff_key, [0] * 600)
            datasets = [{"data": data, "lineColor": color_info, "gradientFill": {0: (r, g, b, 10), 1: (r, g, b, 120)}}]
            avgs = [(getAverageBuff(data), color_info)]
            my = max_y
        else:  # binary
            r, g, b = color_info
            data = uptimeBuffsValues.get(buff_key, [0] * 600)
            datasets = [{"data": data, "lineColor": color_info, "gradientFill": {0: (r, g, b, 255), 1: (r, g, b, 255)}}]
            avgs = [(getAverageBuff(data), color_info)]
            my = 1

        xData = list(range(max((len(d["data"]) for d in datasets), default=1)))
        self.drawGraph(graphX, baseline, graphW, graphH, xData, datasets, maxY=my,
                       showXAxisLabels=bool(xLabelFunc), showYAxisLabels=False, ticks=2, xLabelFunc=xLabelFunc)

        # average values (top-right of graph)
        ay = y + 18
        avgFont = self.getFont("semibold", 46)
        for avgText, col in avgs:
            bbox = self.draw.textbbox((0, 0), avgText, font=avgFont)
            tw = bbox[2] - bbox[0]
            self.draw.text((graphX + graphW - tw, ay), avgText, font=avgFont, fill=col)
            ay += 54

    def _drawBuffGrid(self, x, y, totalWidth, buffList, uptimeBuffsValues, getAverageBuff, columns=2, colGap=110, rowH=400, xLabelFunc=None):
        """Lay out buff uptime cells in a row-major grid (main buffs fill the top rows). Returns bottom y."""
        buffList = [b for b in buffList if b in BUFF_RENDER_CONFIG]
        n = len(buffList)
        if not n:
            return y
        colW = (totalWidth - colGap * (columns - 1)) / columns
        # bottom-most cell of each column gets the x-axis time labels
        bottomCells = set()
        for c in range(columns):
            idxs = [i for i in range(n) if i % columns == c]
            if idxs:
                bottomCells.add(idxs[-1])
        bottom = y
        for idx, buff_key in enumerate(buffList):
            row = idx // columns
            col = idx % columns
            cx = int(x + col * (colW + colGap))
            cy = y + row * rowH
            self._drawBuffRow(cx, cy, int(colW), rowH - 20, buff_key, uptimeBuffsValues, getAverageBuff,
                              xLabelFunc if idx in bottomCells else None)
            bottom = max(bottom, cy + rowH)
        return bottom

    def _drawFieldsSection(self, y, enabled_fields, field_patterns, draw=True):
        """Draw a compact Fields card. Returns the new bottom y."""
        if not enabled_fields:
            return y
        padding = 45
        header_height = 105
        column_gap = 35
        row_gap = 30
        columns = 2 if len(enabled_fields) > 1 else 1
        container_x = self.sidebarX - 30
        container_right = self.canvasSize[0] - self.sidebarPadding + 30
        inner_x = container_x + padding
        inner_right = container_right - padding
        tile_width = (inner_right - inner_x - column_gap * (columns - 1)) // columns
        tile_height = 180
        rows = math.ceil(len(enabled_fields) / columns)
        total_height = padding + header_height + rows * tile_height + max(0, rows - 1) * row_gap + padding
        if draw:
            self.draw.rounded_rectangle((container_x, y, container_right, y + total_height), radius=40, fill=self.cardBackground)
            self.draw.rounded_rectangle((container_x, y, container_x + 18, y + total_height), radius=9, fill=self.accentColor)
            header_y = y + padding - 5
            self.draw.text((inner_x, header_y), "Fields", font=self.getFont("semibold", 85), fill=self.bodyColor)
            count_text = f"{len(enabled_fields)} active"
            count_font = self.getFont("medium", 46)
            bbox = self.draw.textbbox((0, 0), count_text, font=count_font)
            self.draw.text((inner_right - (bbox[2] - bbox[0]), header_y + 22), count_text, font=count_font, fill=self.subtleColor)

            field_font = self.getFont("semibold", 54)
            pattern_font = self.getFont("medium", 38)
            for idx, fname in enumerate(enabled_fields):
                pattern = field_patterns.get(fname, "unknown")
                col = idx % columns
                row = idx // columns
                tile_x = int(inner_x + col * (tile_width + column_gap))
                tile_y = int(y + padding + header_height + row * (tile_height + row_gap))
                self.draw.rounded_rectangle((tile_x, tile_y, tile_x + tile_width, tile_y + tile_height), radius=28, fill=self.sideBarBackground)
                self.draw.rounded_rectangle((tile_x + 24, tile_y + 36, tile_x + 44, tile_y + tile_height - 36), radius=10, fill=self.accentColorDim)
                self.draw.text((tile_x + 70, tile_y + 34), fname.title(), font=field_font, fill=self.bodyColor)
                pattern_text = pattern.replace("_", " ").title()
                bbox = self.draw.textbbox((0, 0), pattern_text, font=pattern_font)
                pill_w = min(tile_width - 90, (bbox[2] - bbox[0]) + 48)
                pill_x = tile_x + 70
                pill_y = tile_y + 110
                self.draw.rounded_rectangle((pill_x, pill_y, pill_x + pill_w, pill_y + 48), radius=18, fill=self.backgroundColor)
                self.draw.text((pill_x + 24, pill_y + 5), pattern_text, font=pattern_font, fill=self.subtleColor)
        return y + total_height + 100

    def _drawHourlySidebar(self, top, sessionTime, onlyValidHourlyHoney, sessionHoney, hourlyReportStats,
                           planterNames, planterTimes, planterFields, buffQuantity, hourlyBuff_list,
                           nectarQuantity, enabled_fields, field_patterns, draw=True):
        """Draw (or measure, when draw=False) the right sidebar. Returns the bottom y."""
        y2 = top

        # planters (top)
        if planterNames:
            if draw:
                self.draw.text((self.sidebarX, y2), "Planters", font=self.getFont("semibold", 85), fill=self.bodyColor)
            y2 += 250
            if draw:
                self.drawPlanters(y2, planterNames, planterTimes, planterFields)
            y2 += 650

        # fields (beneath planters)
        y2 = self._drawFieldsSection(y2, enabled_fields, field_patterns, draw=draw)

        # snapshot buffs
        if draw:
            self.draw.text((self.sidebarX, y2), "Buffs", font=self.getFont("semibold", 85), fill=self.bodyColor)
        y2 += 250
        if draw:
            self.drawBuffs(y2, buffQuantity, hourlyBuff_list)
        buffRows = math.ceil(len(hourlyBuff_list) / 4) if hourlyBuff_list else 1
        y2 += 300 * max(1, buffRows)

        # nectars
        y2 += 200
        if draw:
            self.draw.text((self.sidebarX, y2), "Nectars", font=self.getFont("semibold", 85), fill=self.bodyColor)
        y2 += 250
        if draw:
            self.drawNectars(y2, nectarQuantity)
        y2 += 500

        # task times
        y2 += 100
        if draw:
            self.draw.text((self.sidebarX, y2), "Task Times", font=self.getFont("semibold", 85), fill=self.bodyColor)
        y2 += 250
        if draw:
            self.drawTaskTimes(y2, [
                {"label": "Gathering",  "data": hourlyReportStats["gathering_time"],  "color": self.gatherColor},
                {"label": "Converting", "data": hourlyReportStats["converting_time"], "color": self.convertColor},
                {"label": "Bug Run",    "data": hourlyReportStats["bug_run_time"],    "color": self.otherColor},
                {"label": "Other",      "data": hourlyReportStats["misc_time"],       "color": self.subtleColor},
            ])
        y2 += 1500

        # session stats (bottom)
        y2 += 100
        if draw:
            self.draw.text((self.sidebarX, y2), "Session", font=self.getFont("semibold", 85), fill=self.bodyColor)
        y2 += 250
        if draw:
            self.drawSessionStat(y2, "time_icon", "Session Time", self.displayTime(sessionTime, ['d', 'h', 'm']), self.bodyColor)
        y2 += 300
        if draw:
            self.drawSessionStat(y2, "honey_icon", "Current Honey", self.millify(onlyValidHourlyHoney[-1]), self.honeyColor)
        y2 += 300
        if draw:
            self.drawSessionStat(y2, "session_honey_icon", "Session Honey", self.millify(sessionHoney), (253, 227, 149))
        y2 += 300

        return y2

    def drawHourlyReport(self, hourlyReportStats, sessionTime, honeyPerMin, sessionHoney, honeyThisHour, onlyValidHourlyHoney, buffQuantity, nectarQuantity, planterData, uptimeBuffsValues, buffGatherIntervals, enabled_fields=None, field_patterns=None, configuredUptimeBuffs=None, configuredHourlyBuffs=None):

        def getAverageBuff(buffValues):
            count = 0
            total = 0
            for i, e in enumerate(buffGatherIntervals):
                if e and i < len(buffValues):
                    total += buffValues[i]
                    count += 1
            res = total / count if count else 0
            return f"x{res:.2f}"

        uptimeBuff_list = configuredUptimeBuffs if configuredUptimeBuffs is not None else DEFAULT_UPTIME_BUFFS
        hourlyBuff_list = configuredHourlyBuffs if configuredHourlyBuffs is not None else DEFAULT_HOURLY_BUFFS
        if enabled_fields is None:
            enabled_fields = []
        if field_patterns is None:
            field_patterns = {}

        return self._drawStatMonitorReport(
            "Hourly Report", hourlyReportStats, sessionTime, honeyPerMin, sessionHoney,
            honeyThisHour, onlyValidHourlyHoney, buffQuantity, nectarQuantity, planterData,
            uptimeBuffsValues, buffGatherIntervals,
            configuredUptimeBuffs=uptimeBuff_list,
            configuredHourlyBuffs=hourlyBuff_list,
        )

        self.sidebarX = self.canvasW - self.sidebarWidth + self.sidebarPadding
        mins = list(range(61))

        # working canvas (cropped to content height at the end)
        self.canvas = Image.new('RGBA', self.canvasSize, (*self.backgroundColor, 255))
        self.draw = ImageDraw.Draw(self.canvas)

        # gather planter data for the sidebar
        planterNames, planterTimes, planterFields = [], [], []
        if planterData:
            for i in range(len(planterData["planters"])):
                if planterData["planters"][i]:
                    planterNames.append(planterData["planters"][i])
                    planterTimes.append(planterData["harvestTimes"][i] - time.time())
                    planterFields.append(planterData["fields"][i])

        # ---- header banner (full width) ----
        headerBottom = self._drawHeaderBanner("Hourly Report", "Your stats for this hour")

        # ---- measure sidebar height so its background can be sized first ----
        sidebarTop = headerBottom + 80
        sidebarBottom = self._drawHourlySidebar(sidebarTop, sessionTime, onlyValidHourlyHoney, sessionHoney,
                                                hourlyReportStats, planterNames, planterTimes, planterFields,
                                                buffQuantity, hourlyBuff_list, nectarQuantity,
                                                enabled_fields, field_patterns, draw=False)

        # ---- left column: stat cards, charts, buff grid ----
        y = headerBottom + 80
        # stat cards (evenly fill the left region width)
        cardGap = 60
        cardW = (self.availableSpace - cardGap * 4) // 5
        avgHoneyPerHour = max(0, sessionHoney / (sessionTime / 3600)) if sessionTime > 0 else 0
        cards = [
            ("average_icon",     self.millify(avgHoneyPerHour),          "Average Honey\nPer Hour",     None,            None),
            ("honey_icon",       self.millify(honeyThisHour),            "Honey Made\nThis Hour",       self.honeyColor, None),
            ("kill_icon",        hourlyReportStats["bugs"],              "Bugs Killed\nThis Hour",      (254, 101, 99),  (254, 101, 99)),
            ("quest_icon",       hourlyReportStats["quests_completed"],  "Quests Completed\nThis Hour", (103, 253, 153), (103, 253, 153)),
            ("vicious_bee_icon", hourlyReportStats["vicious_bees"],      "Vicious Bees\nThis Hour",     (132, 233, 254), (132, 233, 254)),
        ]
        for i, (icon, val, label, fc, ic) in enumerate(cards):
            self.drawStatCard(self.leftPadding + i * (cardW + cardGap), y, icon, val, label, fc, ic, cardWidth=cardW)
        y += 750 + 150

        # buff uptime — two-column grid (moved to the top of the report)
        self.draw.text((self.leftPadding, y), "Buff Uptime", fill=self.bodyColor, font=self.getFont("semibold", 85))
        y += 250

        def gridTimeLabel(i, val):
            if i % 100:
                return
            m = val // 10
            hour = self.hour
            if m == 60:
                hour = (hour + 1) % 24
                m = 0
            return f"{str(hour).zfill(2)}:{str(int(m)).zfill(2)}"

        y = self._drawBuffGrid(self.leftPadding, y, self.availableSpace, uptimeBuff_list,
                               uptimeBuffsValues, getAverageBuff, columns=2, xLabelFunc=gridTimeLabel)

        chartContentWidth = self.canvasW - self.leftPadding * 2
        chartGraphX = self.leftPadding + 450
        chartGraphWidth = chartContentWidth - 570
        y = max(y, sidebarBottom + 180)

        # honey/sec — accent colored
        y += 150
        self.draw.text((self.leftPadding, y), "Honey / Sec", fill=self.bodyColor, font=self.getFont("semibold", 85))
        y += 950
        ar, ag, ab = self.accentColor
        self.drawGraph(chartGraphX, y, chartGraphWidth, 700, mins,
                       [{"data": honeyPerMin, "lineColor": self.accentColor,
                         "gradientFill": {0: (ar, ag, ab, 38), 1: (ar, ag, ab, 153)}}],
                       xLabelFunc=self.transformXLabelTime, yLabelFunc=lambda i, x: self.millify(x))

        # backpack
        y += 200
        self.draw.text((self.leftPadding, y), "Backpack", fill=self.bodyColor, font=self.getFont("semibold", 85))
        y += 950
        self.drawGraph(chartGraphX, y, chartGraphWidth, 700, mins,
                       [{"data": hourlyReportStats["backpack_per_min"], "lineColor": "gradient",
                         "gradientFill": {0: (65, 255, 128, 90), 0.6: (201, 163, 36, 90), 0.9: (255, 65, 84, 90), 1: (255, 65, 84, 90)}}],
                       maxY=100, xLabelFunc=self.transformXLabelTime, yLabelFunc=lambda i, x: f"{int(x)}%")

        leftBottom = y

        # ---- draw the sidebar (background ends at its own content, then content) ----
        finalContentBottom = max(leftBottom, sidebarBottom)
        self.draw.rectangle((self.canvasW - self.sidebarWidth, headerBottom + 40, self.canvasW, sidebarBottom + 60), fill=self.sideBarBackground)
        self._drawHourlySidebar(sidebarTop, sessionTime, onlyValidHourlyHoney, sessionHoney,
                                hourlyReportStats, planterNames, planterTimes, planterFields,
                                buffQuantity, hourlyBuff_list, nectarQuantity,
                                enabled_fields, field_patterns, draw=True)

        # ---- crop to actual content height ----
        finalH = min(self.canvasMaxH, int(finalContentBottom) + 120)
        self.canvas = self.canvas.crop((0, 0, self.canvasW, finalH))
        self.draw = ImageDraw.Draw(self.canvas)
        return self.canvas
