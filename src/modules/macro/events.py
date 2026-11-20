import cv2
import numpy as np
import re
import requests
import threading
from pathlib import Path
from functools import lru_cache
import modules.misc.settingsManager as settingsManager


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
from modules.submacros.tadAltSync import REVERT_ENDING, broadcast_to_field_alts
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

# Fields the macro taps, with the setting that turns each on. Stump is tapped for a Guiding Star, Pine after a booster.
GUIDING_STAR_TAP_FIELDS = {"stump": "stump_tap", "pine tree": "pine_tap"}
GUIDING_STAR_WINDOW = 10 * 60
# A tap visit is only started this long into a star, so the star still covers the arrival
GUIDING_STAR_TAP_VISIT_WINDOW = 9.98 * 60
TAP_GATHER_WINDOW = 15 * 60
PINE_TAP_INTERVAL = 14.98 * 60


# a one-word file on main ("true" or "false") that says whether Beesmas is running. It is read from
# GitHub each time the macro starts, so turning Beesmas on or off needs no macro update.
BEESMAS_URL = "https://raw.githubusercontent.com/Fuzzy-Team/Fuzzy-Macro/refs/heads/main/beesmas.txt"


class EventDetectionMixin:
    def checkBeesmas(self):
        """Set self.beesmas: the "Force Beesmas" setting, else the file on GitHub. Beesmas is
        off when the file can't be read."""
        self.beesmas = bool(self.setdat.get("beesmas_override", False))
        if self.beesmas:
            return
        try:
            response = requests.get(BEESMAS_URL, timeout=5,
                                    headers={"Cache-Control": "no-cache, no-store, must-revalidate"})
            response.raise_for_status()
            self.beesmas = response.text.strip().lower() == "true"
        except Exception as error:
            print(f"Could not check whether Beesmas is on ({error}); assuming it is off")

    #thread to detect night
    #night detection is done by converting the screenshot to hsv and checking the average brightness
    #TODO:
    # MAYBE this doesnt actually need to be a thread? Check for night after each reset, when converting and when gathering
    def detectNight(self):

        def isNightSky(bgr):
            y = 30*self.robloxWindow.multi
            #crop the image to only the area above buff
            bgr = bgr[0:y, 180*self.robloxWindow.multi:int(self.robloxWindow.mw * self.robloxWindow.multi)]
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
            self.moonSproutsStart = self.sproutBeansUsed
            self.logger.webhook("","Night detected","purple", "screen", ping_category="ping_night")
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
        # Taken before the rejoin check: a rejoin sets its status first, then bumps the generation
        self.scanGeneration = generation = self.serverGeneration
        if self.status.value == "rejoining":
            return
        detectors = []  # (detector, seconds between scans)
        if self.setdat.get("macro_mode", "normal") == "vic" or self.setdat.get("stinger_hunt", False):
            detectors.append((self.detectViciousAnnouncement, 1))
        if self.setdat.get("ping_guiding_star", False) or self.setdat.get("stump_tap", False):
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
        if generation != self.serverGeneration:
            return
        for detect, _ in detectors:
            detect(text, now)

    def captureBuffBand(self):
        """The buff bar band at the top of the window. backgroundOnce clears it each tick so the scans share one capture."""
        if self.buffBandScreen is None:
            w = self.robloxWindow
            self.buffBandScreen = captureRegionBGR(w.mx, w.my, w.mw, BUFF_BAND_HEIGHT)
        return self.buffBandScreen

    def scanGummyballBuff(self):
        """Ping once when the 8x or 9x Gummyball buff shows up, and again if it changes between 8x and 9x."""
        if not self.setdat.get("ping_gummyball", False) or self.status.value == "rejoining":
            return
        level = self.detectGummyballLevel(self.captureBuffBand())
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
        """Move the TAD alts to a field boost that shows up on the buff bar, unless they are already on that field."""
        color = str(self.setdat.get("tad_alt_buff_bar_boost", "off")).lower()
        if color not in BUFF_BAR_BOOST_FIELDS or not self.tadAltSync._enabled_webhooks() or self.status.value == "rejoining":
            return
        if self.setdat.get("macro_mode", "normal") == "alt":
            return #alt instances don't drive the TAD alts, same as at start
        if time.time() < self.buffBarBoostPausedUntil:
            return #the macro is claiming a booster and will move the alts itself
        screen = self.captureBuffBand()
        # A boost on the default field is ignored because the alts are already there.
        defaultField = str(self.setdat.get("tad_alt_default_field", "pine tree")).strip().lower()
        field = next((f for f in BUFF_BAR_BOOST_FIELDS[color] if f != defaultField and self.boostIconVisible(screen, f)), None)
        if field and field != self.tadAltSync.current_field:
            #on a thread because moving the alts waits over 10s, which would stall the rest of the background tick.
            #The time left on the boost is unknown, so no Glitter extending.
            threading.Thread(target=self.tadAltSync.sync_to_boost, args=(field,), kwargs={"extend_with_glitter": False}, daemon=True).start()

    def checkMainBoostEnd(self):
        """Near the end of the main's boost, send the field alts back to their fields if the main isn't gathering there.
        The boost lasts 15 minutes; this fires from 14 minutes, or 14.98 when Glitter extends it."""
        if not self.mainBoost or self.setdat.get("account_role") != "main":
            return
        field, start = self.mainBoost
        elapsed = time.time() - start
        notBefore = (14.98 if self.setdat.get("field_booster_glitter_extend_enabled", False) else 14) * 60
        if self.mainBoostEndSent == start or not notBefore <= elapsed < 15 * 60:
            return
        if self.isGathering and self.location == field:
            return
        self.mainBoostEndSent = start
        self.logger.webhook("", f"The {field.title()} boost is ending and I won't go back, telling the field alts to go back to their fields", "light blue")
        broadcast_to_field_alts(self.setdat, REVERT_ENDING)

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
        with self.serverLock:
            if self.scanGeneration != self.serverGeneration or now - self.guidingStarLastAnnounced.get(field, 0) < 10 * 60:
                return
            self.guidingStarLastAnnounced[field] = now
        if self.setdat.get("ping_guiding_star", False):
            self.logger.webhook("Guiding Star", f"Detected in {field.title()}", "light blue", "screen", ping_category="ping_guiding_star")

    def tapsAllowed(self):
        """Taps are off in Quest, Alt and Vic modes, and in modes that skip the task."""
        mode = self.setdat.get("macro_mode", "normal")
        return mode not in ("quest", "alt", "vic") and settingsManager.modeRunsTask(mode, "guiding_star_tap")

    def stumpTapDue(self):
        """Stump has a Guiding Star that hasn't been tapped or tried yet."""
        seenAt = self.guidingStarLastAnnounced.get("stump", 0)
        return bool(self.setdat.get("stump_tap", False) and self.tapsAllowed()
                    and time.time() - seenAt < GUIDING_STAR_TAP_VISIT_WINDOW
                    and max(self.tappedAt.get("stump", 0), self.tapTriedAt.get("stump", 0)) < seenAt)

    def pineTapDue(self, boostedField):
        """Pine is tapped right after a Blue Flower or Bamboo booster is collected, at most every 14.98 minutes, and not while a Stump tap is waiting."""
        return bool(self.setdat.get("pine_tap", False) and self.tapsAllowed() and not self.stumpTapDue()
                    and boostedField in ("blue flower", "bamboo")
                    and self.setdat.get("field_booster_glitter_extend_enabled", False)
                    and time.time() - max(self.tappedAt.values(), default=0) >= PINE_TAP_INTERVAL)

    def stampTap(self, field):
        """Record a tap: being in Stump under a live Guiding Star, or in Pine. Returns whether it counted."""
        if not self.tapsAllowed():
            return False
        if field == "pine tree" or (field == "stump" and time.time() - self.guidingStarLastAnnounced.get("stump", 0) < GUIDING_STAR_WINDOW):
            self.tappedAt[field] = time.time()
            return True
        return False

    def tapField(self, field):
        """Go to the field, record the tap and press the Tap hotbar slots. A failed trip isn't retried for the same star."""
        self.tapTriedAt[field] = time.time()
        self.set_task_status(f"travelling_{field}", activity="travelling", field=field)
        # The star can run out on the way (a rejoin clears it), and then there's nothing to tap
        if not self.travelViaCannon("Tapping") or not self.goToField(field) or not self.stampTap(field):
            return False
        self.useHotbar(tapping=True)
        self.logger.webhook("", f"Tapped {field.title()}", "light blue", route_category="gathering")
        return True

    def tapGatherFactor(self, gatherSecs):
        """How much longer a gather runs after a tap. It fades out over the 15 minutes after the tap, quadratically once less of that is left than the gather is long."""
        for field, setting in GUIDING_STAR_TAP_FIELDS.items():
            left = self.tappedAt.get(field, 0) + TAP_GATHER_WINDOW - time.time()
            if self.setdat.get(setting, False) and self.tapsAllowed() and left > 0:
                # An empty or zero box would shorten gathers, so anything under 1 counts as 1
                multiplier = max(1.0, float(self.setdat.get(f"{setting}_duration_mult", 1) or 1))
                return 1 + (multiplier - 1) * min(1, left / max(gatherSecs, 1)) ** 2
        return 1

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
