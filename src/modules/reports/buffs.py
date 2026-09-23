"""Read buff stacks and nectar levels from the screen, plus the buff lists reports track."""
import ast
import cv2
import numpy as np
import time
from PIL import Image, ImageOps
from modules.misc.imageManipulation import adjustImage
from modules.screen.imageSearch import locateTransparentImage
from modules.screen.ocr import ocrRead
from modules.screen.robloxWindow import RobloxWindowBounds
from modules.screen.screenshot import mssScreenshotNP


NATRO_BUFF_CHARACTER_TEMPLATES = {
    0: "iVBORw0KGgoAAAANSUhEUgAAAAQAAAAKCAAAAAC2kKDSAAAAAnRSTlMAAHaTzTgAAAA9SURBVHgBATIAzf8BAADzAAAA8wAAAAAAAAAA8wAAAAIAAAAAAgAAAAACAAAAAAAAAAAAAADzAAABAADzAIAxBMg7bpCUAAAAAElFTkSuQmCC",
    1: "iVBORw0KGgoAAAANSUhEUgAAAAIAAAAMCAAAAABt1zOIAAAAAnRSTlMAAHaTzTgAAAACYktHRAD/h4/MvwAAABZJREFUeAFjYPjM+JmBgeEzEwMDLgQAWo0C7U3u8hAAAAAASUVORK5CYII=",
    2: "iVBORw0KGgoAAAANSUhEUgAAAAQAAAALCAAAAAB9zHN3AAAAAnRSTlMAAHaTzTgAAABCSURBVHgBATcAyP8BAPMAAADzAAAAAAAAAAAAAAAAAAAAAAAAAAAAAPMAAADzAAAA8wAAAPMAAAAB8wAAAAIAAAAAtc8GqohTl5oAAAAASUVORK5CYII=",
    3: "iVBORw0KGgoAAAANSUhEUgAAAAQAAAAKCAAAAAC2kKDSAAAAAnRSTlMAAHaTzTgAAAA9SURBVHgBATIAzf8BAPMAAAAAAAAAAAAAAAAAAAAAAAAAAADzAAAAAAAAAAAAAAAAAAAAAPMAAAABAPMAAFILA8/B68+8AAAAAElFTkSuQmCC",
    4: "iVBORw0KGgoAAAANSUhEUgAAAAQAAAAGCAAAAADBUmCpAAAAAnRSTlMAAHaTzTgAAAApSURBVHgBAR4A4f8AAAAA8wAAAAAAAAAA8wAAAPMAAALzAAAAAfMAAABBtgTDARckPAAAAABJRU5ErkJggg==",
    5: "iVBORw0KGgoAAAANSUhEUgAAAAQAAAALCAAAAAB9zHN3AAAAAnRSTlMAAHaTzTgAAABCSURBVHgBATcAyP8B8wAAAAIAAAAAAPMAAAACAAAAAAHzAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAHzAAAAgmID1KbRt+YAAAAASUVORK5CYII=",
    6: "iVBORw0KGgoAAAANSUhEUgAAAAQAAAAJCAAAAAAwBNJ8AAAAAnRSTlMAAHaTzTgAAAA4SURBVHgBAS0A0v8AAAAA8wAAAPMAAADzAAACAAAAAAEA8wAAAPPzAAAA8wAAAAAA8wAAAQAA8wC5oAiQ09KYngAAAABJRU5ErkJggg==",
    7: "iVBORw0KGgoAAAANSUhEUgAAAAQAAAAMCAAAAABgyUPPAAAAAnRSTlMAAHaTzTgAAABHSURBVHgBATwAw/8B8wAAAAIAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA8wIAAAAAAgAAAABDdgHu70cIeQAAAABJRU5ErkJggg==",
    8: "iVBORw0KGgoAAAANSUhEUgAAAAQAAAAKCAAAAAC2kKDSAAAAAnRSTlMAAHaTzTgAAAA9SURBVHgBATIAzf8BAADzAAAA8wAAAgAAAAABAPMAAAEAAPMAAADzAAAAAAAAAADzAAAAAADzAAABAADzALv5B59oKTe0AAAAAElFTkSuQmCC",
    9: "iVBORw0KGgoAAAANSUhEUgAAAAQAAAAKCAAAAAC2kKDSAAAAAnRSTlMAAHaTzTgAAAA9SURBVHgBATIAzf8BAADzAAAA8wAAAPMAAAAAAPMAAAEAAPMAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA87TcBbXcfy3eAAAAAElFTkSuQmCC",
}


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
    "bloat":         ("stackable", 6,   (208, 208, 208), "bloat_buff"),
    "honey_mark":    ("stackable", 3,   (255, 209, 25),  "honey_mark_buff"),
    "pollen_mark":   ("stackable", 3,   (255, 233, 148), "pollen_mark_buff"),
    "melody":        ("binary",    1,   (200, 200, 200), "melody_buff"),
    "bear":          ("binary",    1,   (115, 71,  40),  "bear_buff"),
    "baby_love":     ("binary",    1,   (112, 181, 195), "baby_love_buff"),
    "jb_share":      ("binary",    1,   (249, 204, 255), "jb_share_buff"),
    "festive_mark":  ("binary",    1,   (200, 67,  53),  "festive_mark_buff"),
    "popstar":       ("binary",    1,   (0,   150, 255), "popstar_buff"),
    "scorching_star": ("binary",   1,   (255, 52,  0),   "scorching_star_buff"),
    "gummy_star":    ("binary",    1,   (241, 145, 255), "gummy_star_buff"),
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


HOURLY_BUFF_OCR_MAX_VALUES = {
    "tabby_love": 1000,
    "wealth_clock": 5,
    "blessing": 100,
    "bloat": 6,
    "tide_blessing": 1.2,
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

    def getBuffQuantityFromImgTightDecimal(self, bgrImg, crop=True, show=False):
        img = bgrImg
        if crop:
            h, *_ = img.shape
            img = img[int(h * 0.50):, :]
        # Mask the white stack text. Keep the threshold loose enough to include the
        # anti-aliased edges of the tiny decimal point, and do NOT dilate: a kernel
        # large enough to thicken the digits also swallows the "." so a value like
        # x2.93 (bloat) would read as "293" and depend on a fragile repair guess.
        mask = cv2.inRange(img, np.array([200, 200, 200]), np.array([255, 255, 255]))
        # Black text on a white background OCRs more reliably; upscale generously so
        # the decimal point survives.
        img = Image.fromarray(255 - mask).resize((mask.shape[1] * 5, mask.shape[0] * 5), Image.LANCZOS)
        if show:
            img.show()
        ocrText = ''.join([x[1][0] for x in ocrRead(img)]).replace(":", ".").replace(",", ".")
        buffCount = ''.join([x for x in ocrText if x.isdigit() or x == "."]).strip(".")
        if not buffCount:
            return "1"
        parts = [part for part in buffCount.split(".") if part]
        if len(parts) > 1:
            buffCount = f"{parts[0]}.{parts[1]}"
        elif parts:
            buffCount = parts[0]
        else:
            return "1"
        try:
            return buffCount if float(buffCount) > 0 else "1"
        except ValueError:
            return "1"

    def getBuffQuantityFromImgOcrRobust(self, bgrImg, transform, buff=None):
        maxValue = HOURLY_BUFF_OCR_MAX_VALUES.get(buff)
        candidates = [
            self.getBuffQuantityFromImg(bgrImg, transform),
            self.getBuffQuantityFromImg(bgrImg, transform, crop=False),
            self.getBuffQuantityFromImgTightDecimal(bgrImg),
            self.getBuffQuantityFromImgTightDecimal(bgrImg, crop=False),
        ]
        best = "1"
        bestValue = 1.0
        for candidate in candidates:
            try:
                value = float(candidate)
            except (TypeError, ValueError):
                continue
            if maxValue is not None and value > maxValue and "." not in str(candidate):
                repaired = f"{str(candidate)[0]}.{str(candidate)[1:]}"
                try:
                    repairedValue = float(repaired)
                    if 0 < repairedValue <= maxValue:
                        candidate = repaired
                        value = repairedValue
                except ValueError:
                    pass
            if maxValue is not None and value > maxValue:
                continue
            if value > bestValue:
                best = candidate
                bestValue = value
        return best

    def _ensureBgrBuffScreen(self, screen):
        if screen is None:
            return screen
        if len(screen.shape) == 3 and screen.shape[2] == 4:
            return cv2.cvtColor(screen, cv2.COLOR_BGRA2BGR)
        return screen

    def getBuffQuantityFromDetectedRect(self, screen, buffRect, transform=True, xOffset=None, buff=None):
        """OCR a full buff tile from a detected icon/color rectangle."""
        bgrScreen = self._ensureBgrBuffScreen(screen)
        if bgrScreen is None or not buffRect:
            return "0"

        height, width = bgrScreen.shape[:2]
        scale = self.robloxWindow.multi
        x = int(buffRect[0])
        if xOffset is None:
            xOffset = -16 * scale
        cropX = int(np.clip(x + xOffset, 0, max(0, width - self.buffSize - 5)))
        cropY = 0
        tile = bgrScreen[cropY:cropY+self.buffSize+2, cropX:cropX+self.buffSize+5]
        if tile.size == 0:
            return "0"
        return self.getBuffQuantityFromImgOcrRobust(tile, transform, buff=buff)

    def getBuffQuantityFromColorOcr(self, screen, hexColor, minSize, variation=8, xOffset=None, transform=True, buff=None):
        bgrScreen = self._ensureBgrBuffScreen(screen)
        if bgrScreen is None:
            return "0"
        res = self.detectBuffColorInImage(
            bgrScreen,
            hexColor,
            minSize,
            y1=6*self.robloxWindow.multi,
            y2=44*self.robloxWindow.multi,
            variation=variation,
            searchDirection=7,
        )
        if not res:
            return "0"
        return self.getBuffQuantityFromDetectedRect(bgrScreen, res, transform=transform, xOffset=xOffset, buff=buff)

    def getTideBlessingOcr(self, screen):
        """Detect Tide Blessing by color, then OCR the visible stack text."""
        return self.getBuffQuantityFromColorOcr(screen, 0x91c2fd, (8, 1), variation=8, buff="tide_blessing")

    def getMondoOcr(self, screen):
        """Detect Mondo Chick Blessing by color, then OCR the visible stack text."""
        return self.getBuffQuantityFromColorOcr(screen, 0xbea2a3, (5, 1), variation=10, buff="mondo")

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
                    buffQuantity.append(self.getTideBlessingOcr(screen))
                elif buff == "mondo":
                    buffQuantity.append(self.getMondoOcr(screen))
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

                # Match the hourly report detector from the provided reference file:
                # crop the full buff tile and OCR the stack text from that tile.
                buffVal = self.getBuffQuantityFromImgOcrRobust(fullBuffImgBGR, transform, buff=buff)
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

    def detectBuffColorInImage(self, screen, hex, minSize, x1=0, y1=0, x2=None, y2=None, variation=0, show=False, searchDirection=1, instances=1):
        
        #convert hex to bgr and setup the color range
        r = (hex >> 16) & 0xFF
        g = (hex >> 8) & 0xFF
        b = hex & 0xFF
        bgr = [b,g,r]
        lower = np.array([max(0, x-variation) for x in bgr])
        upper = np.array([min(255, x+variation) for x in bgr])

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
