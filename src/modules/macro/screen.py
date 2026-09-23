import cv2
import numpy as np
import modules.controls.mouse as mouse
import modules.screen.ocr as ocr
from modules.controls.sleep import pause_aware_time as time
from modules.macro.game_data import cyrillicToLatin
from modules.misc.imageManipulation import adjustImage
from modules.screen.imageSearch import captureRegionBGR, locateImageInScreen, locateImageOnScreen, locateTransparentImageOnScreen
from modules.screen.screenshot import mssScreenshot, mssScreenshotNP
from modules.submacros.backpack import bpc


class ScreenMixin:
    def readBlueText(self):
        try:
            return ocr.imToString("blue").lower()
        except Exception:
            return ""

    def adjustImage(self, path, imageName):
        return adjustImage(path, imageName, self.robloxWindow.display_type)

    def getBackpack(self):
        return bpc(self.robloxWindow.mx+(self.robloxWindow.mw//2+59+3), self.robloxWindow.my+self.robloxWindow.yOffset+6)

    def isActiveHoney(self):
        try:
            x = int(self.robloxWindow.mx + self.robloxWindow.mw//2 - 90)
            y = int(self.robloxWindow.my + self.robloxWindow.yOffset)
            screen = mssScreenshotNP(x, y, 70, 34)
            target_bgr = np.array([128, 226, 255], dtype=np.int16)
            diff = np.abs(screen[:, :, :3].astype(np.int16) - target_bgr)
            if np.any(np.all(diff <= 20, axis=2)):
                return True

            if int(self.setdat.get("bees", 50)) < 25:
                x = int(self.robloxWindow.mx + self.robloxWindow.mw//2 + 210)
                screen = mssScreenshotNP(x, y, 70, 34)
                white_diff = np.abs(screen[:, :, :3].astype(np.int16) - 255)
                return bool(np.any(np.all(white_diff <= 20, axis=2)))
        except Exception:
            return False
        return False

    def convertCyrillic(self, original):
        out = ""
        for x in original:
            if x in cyrillicToLatin:
                x = cyrillicToLatin[x]
            out += x
        return out 

    def getTextBesideE(self):
        img = mssScreenshot(self.robloxWindow.mx+(self.robloxWindow.mw//2-200), self.robloxWindow.my+self.robloxWindow.yOffset+34, 400, 140)
        textRaw = ''.join([x[1][0] for x in ocr.ocrRead(img)]).lower()
        return self.convertCyrillic(textRaw)

    def isBesideE(self, includeList = [], excludeList = [], log=False):
        #get text
        text = self.getTextBesideE()

        #check if text is to be rejected
        if log: print(f"output text: {text}")
        for i in excludeList:
            if i in text: return False
        #check if its to be accepted
        for i in includeList:
            if i in text:  return text
        return False

    def _compactPromptText(self, text):
        return ''.join(ch for ch in str(text or "").lower() if ch.isalnum())

    def isSpecificPlanterPrompt(self, planter, promptText=None):
        promptText = self.getTextBesideE() if promptText is None else promptText
        compactPrompt = self._compactPromptText(promptText)
        compactPlanter = self._compactPromptText(planter)
        if not compactPrompt:
            return False
        if "harvest" not in compactPrompt or "planter" not in compactPrompt:
            return False
        if not compactPlanter:
            return True
        return compactPlanter in compactPrompt

    def isBesideEImage(self, name):
        template = self.adjustImage("./images/menu",name)
        return locateTransparentImageOnScreen(template, self.robloxWindow.mx+(self.robloxWindow.mw//2-200), self.robloxWindow.my+self.robloxWindow.yOffset+34, 400, 140, 0.75)

    def isMakeHoneyPrompt(self, log=False):
        text = self.getTextBesideE()
        if log: print(f"output text: {text}")
        return ("make" in text and "honey" in text) or self.isBesideEImage("makehoney")

    #click the yes popup
    #if detect is set to true, the macro will check if the yes button is there
    #if detectOnly is set to true, the macro will not click 
    def _clickYesByColor(self, detectOnly=False, clickOnce=False):
        """
        Fallback for Yes/No dialogs: click the green Yes button by color.
        Yes is always the left green button; No is red on the right.
        """
        x = self.robloxWindow.mx + self.robloxWindow.mw // 2 - 270
        y = self.robloxWindow.my + self.robloxWindow.mh // 2 - 60
        w, h = 580, 265
        screen = mssScreenshotNP(x, y, w, h)
        if screen is None:
            return False
        if screen.ndim == 3 and screen.shape[2] == 4:
            screen = cv2.cvtColor(screen, cv2.COLOR_BGRA2BGR)
        hsv = cv2.cvtColor(screen, cv2.COLOR_BGR2HSV)
        # BSS Yes button greens (covers both bright and darker confirmation shades)
        mask = cv2.inRange(hsv, (35, 60, 35), (95, 255, 255))
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        minArea = 800 * (self.robloxWindow.multi ** 2)
        candidates = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < minArea:
                continue
            bx, by, bw, bh = cv2.boundingRect(contour)
            # Button-like aspect: wider than tall
            if bw < bh:
                continue
            candidates.append((bx, by, bw, bh, area))
        if not candidates:
            return False
        # Prefer the leftmost green button (Yes), ignoring any larger background greens
        candidates.sort(key=lambda c: (c[0], -c[4]))
        bx, by, bw, bh, _ = candidates[0]
        # Must sit on the left half of the captured dialog region (Yes is always left of No)
        if (bx + bw // 2) > screen.shape[1] // 2:
            return False
        if detectOnly:
            return True
        clickX = x + (bx + bw // 2) // self.robloxWindow.multi
        clickY = y + (by + bh // 2) // self.robloxWindow.multi
        mouse.moveTo(clickX, clickY)
        time.sleep(0.2)
        mouse.moveBy(2, 2)
        time.sleep(0.1)
        for _ in range(1 if clickOnce else 2):
            mouse.click()
        return True

    def clickYes(self, detect = False, detectOnly = False, clickOnce=False):
        yesImg = self.adjustImage("./images/menu", "yes")
        x = self.robloxWindow.mx+self.robloxWindow.mw//2-270
        y = self.robloxWindow.my+self.robloxWindow.mh//2-60
        time.sleep(0.4)
        threshold = 0
        if detect or detectOnly: threshold = 0.75
        res = locateImageOnScreen(yesImg, x, y, 580, 265, threshold)
        # Template match can land on the No button under some Retina/scale mismatches.
        # Yes is always left of center in this search region — reject right-side hits.
        matchOk = False
        bestX = bestY = None
        if res is not None:
            bestX, bestY = [v // self.robloxWindow.multi for v in res[1]]
            if bestX <= 580 // 2:
                matchOk = True
        if not matchOk:
            return self._clickYesByColor(detectOnly=detectOnly, clickOnce=clickOnce)
        if detectOnly: return True
        mouse.moveTo(bestX+x, bestY+y)
        time.sleep(0.2)
        # Nudge into the Yes button body (template is only the "Y") without reaching No
        mouse.moveBy(15, 5)
        time.sleep(0.1)
        for _ in range(1 if clickOnce else 2):
            mouse.click()
        return True

    def blueTextScreen(self):
        """Screenshot the blue text area once, to check several messages against the same frame."""
        return captureRegionBGR(*self._blueTextRegion())

    def _blueTextRegion(self):
        w = self.robloxWindow
        return w.mx+(w.mw*3/4), w.my+(w.mh*3/5), w.mw/4, w.mh-w.mh*3/5

    def blueTextImageSearch(self, text, threshold=0.7, screen=None):
        target = self.adjustImage("./images/blue", text)
        if screen is None:
            return locateImageOnScreen(target, *self._blueTextRegion(), threshold)
        return locateImageInScreen(target, screen, threshold)

    #returns the coordinates of the keep old text
    def keepOldCheck(self):
        noImg = self.adjustImage("./images/menu", "keep") #yes/no popup
        x = self.robloxWindow.mx + self.robloxWindow.mw/2-300
        y = self.robloxWindow.my
        res = locateImageOnScreen(noImg, x, y, 650, self.robloxWindow.mh, 0.8)
        if res:
            ix, iy = [j//self.robloxWindow.multi for j in res[1]]
            return x+ix+5, y+iy+5

    #convert bss' cooldown text into seconds
    #brackets: account for brackets in the text, where the cooldown value is between said brackets
    def cdTextToSecs(self, rawText, brackets, defaultTime=0):
        if brackets:
            closePos = rawText.rfind(")")
            #get cooldown if close bracket is present or not
            if closePos >= 0:
                cooldownRaw = rawText[rawText.rfind("(")+1:closePos]
            elif "(" in rawText:
                cooldownRaw = rawText.split("(")[1]
            else:
                cooldownRaw = rawText
        else:
            cooldownRaw = rawText
        #clean it up, extract only valid characters
        cooldownRaw = ''.join([x for x in cooldownRaw if x.isdigit() or x == ":" or x == "s"])
        cooldownSeconds = None #cooldown in seconds

        def extractNumFromText(text):
            return ''.join(filter(str.isdigit, text))
        
        #convert time to seconds
        validTime = True
        if ":" in cooldownRaw:
            times = cooldownRaw.split(":")
            cooldownSeconds = 0
            #convert
            for i,e in enumerate(times[::-1]):
                num = extractNumFromText(e)
                if not num:
                    validTime = False
                    break
                cooldownSeconds += int(num) * 60**i

        elif cooldownRaw.count("s") == 1: #only seconds
            num = extractNumFromText(e)
            if not num:
                validTime = False
            cooldownSeconds = num
        else:
            validTime = False
        
        if not validTime or (defaultTime and cooldownSeconds > defaultTime):
            cooldownSeconds = defaultTime

        return cooldownSeconds
