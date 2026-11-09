import cv2
import numpy as np
import re
import threading
from pathlib import Path
from functools import lru_cache


@lru_cache(maxsize=9)
def _vicious_bitmap(name):
    path = Path(__file__).resolve().parents[2] / "images" / "vicious" / (name + ".png")
    bitmap = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if bitmap is None:
        raise FileNotFoundError(path)
    return bitmap


def vicious_bitmap_position(bgr, name, tolerance):
    """Match opaque source pixels with per-channel colour tolerance."""
    bitmap = _vicious_bitmap(name)
    h, w = bitmap.shape[:2]
    if bgr.shape[0] < h or bgr.shape[1] < w:
        return None
    mask = bitmap[:, :, 3] == 255 if bitmap.shape[2] == 4 else np.ones((h, w), bool)
    colors = bitmap[:, :, :3]
    if mask.all() and np.all(colors == colors[0, 0]):
        color = colors[0, 0].astype(np.int16)
        pixels = cv2.inRange(bgr[:, :, :3], np.maximum(color - tolerance, 0).astype(np.uint8),
                             np.minimum(color + tolerance, 255).astype(np.uint8))
        candidates = cv2.erode(pixels, np.ones((h, w), np.uint8), anchor=(0, 0),
                               borderType=cv2.BORDER_CONSTANT, borderValue=0)
        matches = np.argwhere(candidates[:bgr.shape[0] - h + 1, :bgr.shape[1] - w + 1])
    else:
        ys, xs = np.nonzero(mask)
        if not len(ys):
            return None
        ch, cw = bgr.shape[0] - h + 1, bgr.shape[1] - w + 1
        y, x = ys[0], xs[0]
        color = colors[y, x].astype(np.int16)
        seed = cv2.inRange(bgr[y:y + ch, x:x + cw, :3],
                           np.maximum(color - tolerance, 0).astype(np.uint8),
                           np.minimum(color + tolerance, 255).astype(np.uint8))
        matches = np.argwhere(seed)
        for y, x in zip(ys[1:], xs[1:]):
            if not len(matches):
                return None
            pixels = bgr[matches[:, 0] + y, matches[:, 1] + x, :3].astype(np.int16)
            matches = matches[np.all(np.abs(pixels - colors[y, x].astype(np.int16)) <= tolerance, axis=1)]
    if not len(matches):
        return None
    y, x = matches[0]
    return int(x + w // 2), int(y + h // 2)


def vicious_bitmap_matches(bgr, name, tolerance):
    return vicious_bitmap_position(bgr, name, tolerance) is not None


def vicious_ground_is_night(bgr):
    return (vicious_bitmap_matches(bgr, "nightground", 6)
            and not vicious_bitmap_matches(bgr, "ground", 6)
            and not vicious_bitmap_matches(bgr, "ground2", 6))


from modules.controls.sleep import pause_aware_time as time
from modules.macro.game_data import startLocationDimensions
from modules.screen.imageSearch import captureRegionBGR, findColorObjectRGB, locateImageInScreen
from modules.screen.screenshot import mssScreenshotNP


# The buff row sits inside the top 100px of the window.
# The buff must stay unseen for 16 seconds (one background tick per second) before it can ping again.
BUFF_BAND_HEIGHT = 100
GUMMYBALL_HOLD_SECONDS = 16
GUMMYBALL_THRESHOLD = 0.8

# Field boost icons on the buff bar, checked in this order (first match wins).
# One colour is followed at a time, and an icon matches when every pixel is within +-30 per channel.
# The icons were captured on Windows.
BUFF_BAR_BOOST_FIELDS = {
    "blue": ("blue flower", "bamboo", "pine tree"),
    "white": ("dandelion", "sunflower", "pumpkin"),
    "red": ("strawberry", "rose", "pepper"),
}
BUFF_BAR_BOOST_TOLERANCE = 30
BUFF_BAR_BOOST_HOLD_SECONDS = 16 #the icon must stay unseen this long before the same boost can sync again


class EventDetectionMixin:
    #thread to detect night
    #night detection is done by converting the screenshot to hsv and checking the average brightness
    #TODO:
    # MAYBE this doesnt actually need to be a thread? Check for night after each reset, when converting and when gathering
    def detectNight(self):

        def isNightSky(bgr):
            y = 30*self.robloxWindow.multi
            #crop the image to only the area above buff
            bgr = bgr[0:y, 180*self.robloxWindow.multi:int(self.robloxWindow.mw)]
            rows, cols = bgr.shape[:2]
            if rows <= 15 or cols <= 15:
                return False
            black = np.all(bgr == 0, axis=2).astype(np.uint8)
            sums = cv2.integral(black)
            windows = sums[15:rows, 15:cols] - sums[:rows-15, 15:cols] - sums[15:rows, :cols-15] + sums[:rows-15, :cols-15]
            return bool((windows == 225).any())
        
        #detect the color of the grass in fields
        #useful when gathering
        def isGrassNight(bgr):       
            dayColors = [
                [(47, 117, 57), cv2.getStructuringElement(cv2.MORPH_RECT, (6, 6))], #ground
                [(46, 117, 58), cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9))], #dande
                [(60, 156, 74), cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9))], #stump
                [(38, 114, 51), cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9))], #pa
                [(66, 123, 40), cv2.getStructuringElement(cv2.MORPH_RECT, (6, 6))], #clov
                [(32, 211, 22), cv2.getStructuringElement(cv2.MORPH_RECT, (9, 9))], #ant
            ]

            nightColors = [
                [(23, 72, 30), cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))], #a
                [(17, 71, 28), cv2.getStructuringElement(cv2.MORPH_RECT, (6, 6))], #dande
            ]

            bgr = bgr[0:bgr.shape[0]- (100*self.robloxWindow.multi)]
            dayScreen = bgr[int(bgr.shape[0]*2/5):bgr.shape[0]].copy()
            #detect day
            for color, kernel in dayColors:
                if findColorObjectRGB(dayScreen, color, variance=6, kernel=kernel, mode="box"):
                    return False
            #day not found, detect Night
            nightScreen = bgr[int(bgr.shape[0]/2):bgr.shape[0]].copy()
            for color, kernel in nightColors:
                if findColorObjectRGB(nightScreen, color, variance=6, kernel=kernel, mode="box"):
                    return True
                
            return False

        def isNight():
            screen = mssScreenshotNP(self.robloxWindow.mx,self.robloxWindow.my, self.robloxWindow.mw, self.robloxWindow.mh)
            bgr = cv2.cvtColor(screen, cv2.COLOR_BGRA2BGR)

            if self.converting:
                nightDetected = isNightSky(bgr)
            else:
                nightDetected = isGrassNight(bgr)

            #night detected
            if nightDetected:
                self.nightDetectStreaks += 1
            else: 
                #failed to detect night, reset streak counter
                self.nightDetectStreaks = 0

            #detected night consecutively for 5 times or more
            if self.nightDetectStreaks >= 5:
                return True
            
            return False
        
        if self.canDetectNight and isNight():
            self.night = True
            self.logger.webhook("","Night detected","dark brown", "screen", ping_category="ping_night")
            time.sleep(200) #wait for night to end
            self.night = False
            self.nightDetectStreaks = 0

    def viciousSkyIsNight(self):
        """Check the sky at spawn without resetting or claiming a hive."""
        win = self.robloxWindow
        self.ensure_shift_lock_off(reason="Vic Hop sky check")
        # Check the sky with one PageDown and five zoom-out taps.
        self.keyboard.press("pagedown")
        for _ in range(5):
            self.keyboard.press("o")
            time.sleep(0.03)
        sky = mssScreenshotNP(win.mx + win.mw // 2 - 15, win.my, 30, 20)
        sky = cv2.resize(sky[:, :, :3], (30, 20), interpolation=cv2.INTER_AREA)
        isNight = vicious_bitmap_matches(sky, "nightvic", 25)
        if isNight:
            self.keyboard.press("pageup")
        return isNight

    #ported from Natro's nm_confirmNight. Shaded grass beside a wall can look like night to detectNight,
    #so before a night task, reset and look down at the open ground in front of the hive
    def confirmNight(self):
        self.reset(convert=False)
        for _ in range(10):
            self.keyboard.press("pageup")
        for _ in range(7):
            self.keyboard.press("o")
            time.sleep(0.025)

        win = self.robloxWindow
        # Search the central 400 client pixels for ground bitmaps.
        width = min(400, win.mw)
        screen = mssScreenshotNP(win.mx + win.mw // 2 - width // 2,
                                 win.my, width, win.mh)
        bgr = cv2.cvtColor(screen, cv2.COLOR_BGRA2BGR)
        bgr = cv2.resize(bgr, (width, win.mh), interpolation=cv2.INTER_AREA)
        isNight = vicious_ground_is_night(bgr)

        if not isNight:
            self.keyboard.press("pagedown")
            for _ in range(5):
                self.keyboard.press("o")
                time.sleep(0.03)
            sky = mssScreenshotNP(win.mx + win.mw // 2 - 15, win.my, 30, 20)
            sky = cv2.resize(sky[:, :, :3], (30, 20), interpolation=cv2.INTER_AREA)
            isNight = vicious_bitmap_matches(sky, "nightvic", 25)
            self.keyboard.press("pageup")

        for _ in range(4):
            self.keyboard.press("pagedown")
        if isNight:
            self.logger.webhook("", "Confirmed night", "dark brown", "screen")
        else:
            self.logger.webhook("", "Not night, skipping the night tasks", "dark brown", "screen")
            self.night = False
        return isNight

    def scanBlueTextAnnouncements(self):
        """Read the blue text once and pass it to every enabled announcement detector."""
        if self.status.value == "rejoining":
            return
        detectors = []  # (detector, seconds between scans)
        if self.setdat.get("macro_mode", "normal") == "vic" or self.setdat.get("stinger_hunt", False):
            detectors.append((self.detectViciousAnnouncement, 1))
        if self.setdat.get("ping_guiding_star", False):
            detectors.append((self.detectGuidingStarAnnouncement, 10))
        if self.setdat.get("ping_unusual_sprouts", False):
            detectors.append((self.detectUnusualSproutAnnouncement, 10))
        if self.setdat.get("ping_windy_bee", False):
            detectors.append((self.detectWindyBeeAnnouncement, 5))
        if self.setdat.get("sticker_sprout_watch", False) and self.setdat.get("macro_mode", "normal") not in ("alt", "vic"):
            detectors.append((self.detectStickerSproutAnnouncement, 5))
        if not detectors:
            return
        now = time.time()
        if now - self.lastBlueTextScan < min(interval for _, interval in detectors):
            return
        self.lastBlueTextScan = now

        text = self.readBlueText()
        for detect, _ in detectors:
            detect(text, now)

    def scanGummyballBuff(self):
        """Ping once when the 8x or 9x Gummyball buff shows up, and again if it changes between 8x and 9x."""
        if not self.setdat.get("ping_gummyball", False) or self.status.value == "rejoining":
            return
        w = self.robloxWindow
        screen = captureRegionBGR(w.mx, w.my, w.mw, BUFF_BAND_HEIGHT)
        level = self.detectGummyballLevel(screen)
        now = time.time()
        if level:
            self.gummyballLastSeen = now
            if level != self.gummyballLevel:
                self.gummyballLevel = level
                self.logger.webhook("Gummyball", f"{level} Gummyball buff detected", "purple", "screen", ping_category="ping_gummyball")
        elif self.gummyballLevel and now - self.gummyballLastSeen >= GUMMYBALL_HOLD_SECONDS:
            self.gummyballLevel = None

    def detectGummyballLevel(self, screen):
        """Returns "9x", "8x" or None. 9x is checked first."""
        for level in ("9x", "8x"):
            template = self.adjustImage("./images/buffs", f"gummy{level}")
            if locateImageInScreen(template, screen, GUMMYBALL_THRESHOLD, scales=[1.0]):
                return level
        return None

    def scanBuffBarBoost(self):
        """Move the TAD alts to a field boost that shows up on the buff bar.
        The boost is handled once; it can trigger again after its icon has been gone for a while."""
        color = str(self.setdat.get("tad_alt_buff_bar_boost", "off")).lower()
        if color not in BUFF_BAR_BOOST_FIELDS or not self.setdat.get("tad_alt_sync_enabled", False) or self.status.value == "rejoining":
            return
        if self.setdat.get("macro_mode", "normal") == "alt":
            return #alt instances don't drive the TAD alts, same as at start
        if time.time() < self.buffBarBoostPausedUntil:
            return #the macro is claiming a booster and will move the alts itself
        w = self.robloxWindow
        screen = captureRegionBGR(w.mx, w.my, w.mw, BUFF_BAND_HEIGHT)
        # A boost on the default field is ignored because the alts are already there.
        defaultField = str(self.setdat.get("tad_alt_default_field", "pine tree")).strip().lower()
        field = next((f for f in BUFF_BAR_BOOST_FIELDS[color] if f != defaultField and self.boostIconVisible(screen, f)), None)
        now = time.time()
        if field:
            self.buffBarBoostLastSeen = now
            if field != self.buffBarBoostField:
                self.buffBarBoostField = field
                self.logger.webhook("", f"{field.title()} boost found on the buff bar", "light blue", "screen")
                #on a thread because moving the alts waits over 10s, which would stall the rest of the background tick.
                #The time left on the boost is unknown, so no Glitter extending.
                threading.Thread(target=self.tadAltSync.sync_to_boost, args=(field,), kwargs={"extend_with_glitter": False}, daemon=True).start()
        elif self.buffBarBoostField and now - self.buffBarBoostLastSeen >= BUFF_BAR_BOOST_HOLD_SECONDS:
            self.buffBarBoostField = None

    def boostIconVisible(self, screen, field):
        """True if every pixel of the field's boost icon matches somewhere in the screen within the colour tolerance."""
        icon = self.adjustImage("./images/buffs", f"boost_{field.replace(' ', '_')}")[:, :, :3].astype(np.int16)
        iconH, iconW = icon.shape[:2]
        screen = screen[:, :, :3].astype(np.int16)
        if screen.shape[0] < iconH or screen.shape[1] < iconW:
            return False
        # Start from the pixels matching the icon's first pixel, then drop positions as the other icon pixels disagree.
        candidates = np.argwhere(np.all(np.abs(screen[:screen.shape[0] - iconH + 1, :screen.shape[1] - iconW + 1] - icon[0, 0]) <= BUFF_BAR_BOOST_TOLERANCE, axis=2))
        for dy in range(iconH):
            for dx in range(iconW):
                if not len(candidates):
                    return False
                ys, xs = candidates[:, 0] + dy, candidates[:, 1] + dx
                candidates = candidates[np.all(np.abs(screen[ys, xs] - icon[dy, dx]) <= BUFF_BAR_BOOST_TOLERANCE, axis=1)]
        return len(candidates) > 0

    def detectGuidingStarAnnouncement(self, text, now):
        if "guiding" not in text or "star" not in text:
            return

        allFields = list(startLocationDimensions.keys())
        detectedFields = self._extractAFBBoostedFields(text, allFields)
        if not detectedFields:
            normalized = self._normalizeAFBText(text)
            detectedFields = [field for field in allFields if self._normalizeAFBText(field) in normalized]
        if not detectedFields:
            return

        field = detectedFields[-1]
        if now - self.guidingStarLastAnnounced.get(field, 0) < 10 * 60:
            return
        self.guidingStarLastAnnounced[field] = now
        self.logger.webhook("Guiding Star", f"Detected in {field.title()}", "light blue", "screen", ping_category="ping_guiding_star")

    def detectUnusualSproutAnnouncement(self, text, now):
        if "sprout" not in text:
            return

        rarity = self.extractPlantedSproutRarity(text)
        unusualRarities = {"epic", "legendary", "supreme", "gummy", "festive", "moon", "sticker", "debug"}
        if rarity not in unusualRarities:
            return

        rarity = rarity.title()
        if not rarity:
            return

        if now - self.unusualSproutLastAnnounced.get(rarity, 0) < 10 * 60:
            return
        self.unusualSproutLastAnnounced[rarity] = now
        message = f"{rarity} Sprout"
        self.logger.webhook(
            "Unusual Sprout",
            message,
            "light blue",
            "screen",
            ping_category="ping_unusual_sprouts",
            route_category="activities",
        )

    def detectWindyBeeAnnouncement(self, text, now):
        match = re.search(r"\bfound\s+windy\s+bee\s+in\s+the\s+(.+?)\s+field\b", text)
        if not match:
            return

        field = match.group(1).strip()
        if field not in startLocationDimensions:
            return
        if now - self.windyBeeLastAnnounced.get(field, 0) < 10 * 60:
            return
        self.windyBeeLastAnnounced[field] = now
        self.logger.webhook(
            "Windy Bee",
            f"Spawn detected in {field.title()} Field",
            "light blue",
            "screen",
            ping_category="ping_windy_bee",
            route_category="activities",
        )
