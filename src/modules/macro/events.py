import cv2
import numpy as np
import re
from modules.controls.sleep import pause_aware_time as time
from modules.macro.game_data import startLocationDimensions
from modules.screen.imageSearch import findColorObjectRGB
from modules.screen.screenshot import mssScreenshotNP


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
            self.logger.webhook("","Night detected","dark brown", "screen")
            time.sleep(200) #wait for night to end
            self.night = False
            self.nightDetectStreaks = 0

    def scanBlueTextAnnouncements(self):
        """Read the blue text once and pass it to every enabled announcement detector."""
        if self.status.value == "rejoining":
            return
        detectors = []  # (detector, seconds between scans)
        if self.setdat.get("guiding_star_announcements", False):
            detectors.append((self.detectGuidingStarAnnouncement, 10))
        if self.setdat.get("ping_unusual_sprouts", False):
            detectors.append((self.detectUnusualSproutAnnouncement, 10))
        if self.setdat.get("ping_windy_bee", False):
            detectors.append((self.detectWindyBeeAnnouncement, 5))
        if self.setdat.get("sticker_sprout_watch", False) and self.setdat.get("macro_mode", "normal") != "alt":
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
