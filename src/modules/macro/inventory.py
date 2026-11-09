import cv2
import queue
import threading
import time as raw_time
from contextlib import contextmanager
from types import SimpleNamespace
from modules.misc.imageManipulation import average_hash
from PIL import Image
from difflib import SequenceMatcher
import modules.controls.mouse as mouse
import modules.misc.appManager as appManager
import modules.screen.ocr as ocr
from modules.controls.sleep import is_paused, pause_aware_time as time, sleep
from modules.screen.imageSearch import locateImageOnScreen
from modules.screen.screenshot import mssScreenshot, mssScreenshotNP


class InventoryMixin:
    @contextmanager
    def inventoryInteraction(self):
        """Release the gather click and shift lock while the inventory is in use."""
        with self._inventoryInteractionLock:
            with self._gatherInputLock:
                wasGathering = self.isGathering
                if wasGathering:
                    mouse.mouseUp()
            restoreShiftLock = False
            try:
                if wasGathering:
                    # Detection can sleep. Recheck gathering before changing Shift.
                    try:
                        detection = self._detect_shift_lock_state_with_retries()
                    except Exception:
                        detection = None
                    with self._inventoryGatherInput() as active:
                        if active and detection and detection.get("state") is not None:
                            self._gatherShiftLockEnabled = bool(detection["state"])
                            if self._gatherShiftLockEnabled:
                                self.keyboard.press("shift")
                                self._gatherShiftLockEnabled = False
                                restoreShiftLock = True
                    if restoreShiftLock:
                        self.logger.webhook("", "Shift Lock detected during inventory access, turning it off", "dark brown")
                        time.sleep(0.35)
                yield
            finally:
                if wasGathering:
                    with self._inventoryGatherInput() as active:
                        if active and restoreShiftLock:
                            self.enableShiftLock()
                            self._gatherShiftLockEnabled = True
                    if active and restoreShiftLock:
                        time.sleep(0.35)
                    with self._inventoryGatherInput() as active:
                        if active:
                            self.moveMouseToDefault()
                            mouse.mouseDown()

    @contextmanager
    def _inventoryGatherInput(self):
        # Wait outside the state lock so shutdown can finish even during a pause.
        while True:
            self._gatherInputLock.acquire()
            active = (self.isGathering
                      and (self.run is None or self.run.value != 0))
            if not active or self.run is None or not is_paused():
                break
            self._gatherInputLock.release()
            raw_time.sleep(0.1)
        try:
            yield active
        finally:
            self._gatherInputLock.release()

    def acquireInventoryForGather(self):
        """Acquire inventory access without hiding pause, stop, or skip requests."""
        while not self._inventoryInteractionLock.acquire(timeout=0.1):
            if self.checkPauseAndWait():
                return False
        try:
            if not self.checkPauseAndWait():
                return True
        except BaseException:
            self._inventoryInteractionLock.release()
            raise
        self._inventoryInteractionLock.release()
        return False

    def toggleInventory(self, mode):
        def clickInv():
            mouse.moveTo(self.robloxWindow.mx+30, self.robloxWindow.my+113)
            time.sleep(0.1)
            mouse.moveBy(0,3)
            time.sleep(0.1)
            mouse.click()
            time.sleep(0.1)

        if mode == "open": #already open
            #click the system settings
            mouse.moveTo(self.robloxWindow.mx+245, self.robloxWindow.my+113)
            time.sleep(0.1)
            mouse.moveBy(0,3)
            time.sleep(0.1)
            mouse.click()
            clickInv()
            time.sleep(0.1)
        else:
            clickInv()
        self.moveMouseToDefault()
        time.sleep(0.3)
        # Cleared only once every pause is done, so an interrupt mid-close still lets reset close the panel.
        self.questMenuOpen = False
        '''
        self.keyboard.press("\\")
        #align with first buff
        for _ in range(7):
            self.keyboard.press("w")
        for _ in range(20):
            self.keyboard.press("a")
        #open inventory
        if sys.platform == "darwin":
            for _ in range(5):
                self.keyboard.press("w")
                time.sleep(0.1)
            self.keyboard.press("s")
            self.keyboard.press("a")
            time.sleep(0.1)
            self.keyboard.press("enter")
        else:
            self.keyboard.press("s")
            self.keyboard.press("enter")
        '''

    #scroll to an item in the inventory and return the x,y coordinates
    def getStringSimilarity(self, str1, str2):
        return SequenceMatcher(None, str1, str2).ratio()

    def findItemInInventory(self, itemName):
        with self.inventoryInteraction():
            return self._findItemInInventory(itemName)

    def _scrollInventoryToTop(self):
        hashes = []
        for _ in range(9):
            mouse.scroll(100)
            sleep(0.05)
            screen = cv2.cvtColor(mssScreenshotNP(self.robloxWindow.mx, self.robloxWindow.my+120, 100, 200), cv2.COLOR_BGRA2RGB)
            hashes.append(average_hash(Image.fromarray(screen)))
            #stop once the list hasn't moved over the last 3 scrolls (150ms+), so a frame
            #that lags behind a scroll can't be mistaken for the top
            if len(hashes) >= 4 and all(h == hashes[-1] for h in hashes[-4:]):
                break

    def findItemReport(self, query):
        """findItemByName as (message, screenshot of the row or None)."""
        result = self.findItemByName(query)
        if result is None:
            return f"Could not find an item matching \"{query}\" in the inventory", None
        return f"Found {result[0]}", result[1]

    def findItemByName(self, query):
        """Read every row of the inventory with OCR and return (row text, screenshot of the row)
        for the closest match to a possibly misspelled name, or None if nothing is close."""
        def key(text):
            return ''.join(c for c in text.lower() if c.isalnum())

        query = key(query)
        if not query:
            return None
        multi = self.robloxWindow.multi
        best = (0, None, None)
        with self.inventoryInteraction():
            self.toggleInventory("open")
            try:
                time.sleep(0.3)
                mouse.moveTo(self.robloxWindow.mx+312, self.robloxWindow.my+200)
                mouse.click()
                self._scrollInventoryToTop()
                time.sleep(0.3)
                prevHash = None
                unchanged = 0
                for _ in range(180):
                    page = mssScreenshot(self.robloxWindow.mx, self.robloxWindow.my+90, 310, self.robloxWindow.mh-180)
                    for bbox, (text, _conf) in ocr.ocrRead(page):
                        name = key(text)
                        if not name:
                            continue
                        score = 1.0 if query in name else self.getStringSimilarity(query, name)
                        if score > best[0]:
                            top = int(min(point[1] for point in bbox))
                            row = page.crop((0, max(0, top-30*multi), page.width, min(page.height, top+70*multi)))
                            best = (score, text.strip(), row)
                    if best[0] == 1.0:
                        break
                    #stop after the list hasn't moved for 3 pages in a row
                    hash = average_hash(page)
                    unchanged = unchanged + 1 if hash == prevHash else 0
                    if unchanged >= 3:
                        break
                    prevHash = hash
                    mouse.scroll(-2, True)
                    time.sleep(0.15)
            finally:
                self.toggleInventory("close")
        if best[0] < 0.7:
            return None
        return best[1], best[2]

    def _findItemInInventory(self, itemName):
        #for retina, just a regular image search
        #for built-in, a transparency search
        itemImg = self.adjustImage("./images/inventory", itemName)
        #itemImg = cv2.cvtColor(itemImg, cv2.COLOR_RGB2GRAY)

        itemOCRName = itemName.lower().replace("planter", "") #the name of the item used to check with the ocr to verify its correct
        itemH, itemW, *_ = itemImg.shape
        itemW //= self.robloxWindow.multi
        itemH //= self.robloxWindow.multi

        #open inventory
        self.toggleInventory("open")
        time.sleep(0.3)
        mouse.moveTo(self.robloxWindow.mx+312, self.robloxWindow.my+200)
        mouse.click()
        #scroll to top
        self._scrollInventoryToTop()
        #scroll down until the item is found
        bestY = None

        prevHash = None
        time.sleep(0.3)
        for _ in range(180):
            max_val, max_loc = locateImageOnScreen(itemImg, self.robloxWindow.mx, self.robloxWindow.my+90, 100, self.robloxWindow.mh-180)
            #most likely the correct item, stop searching
            if max_val > 0.7:
                itemScreenshot = mssScreenshot(self.robloxWindow.mx+90, self.robloxWindow.my+(max_loc[1]//self.robloxWindow.multi)+60, 220, 60)
                itemOCRText = ''.join([x[1][0] for x in ocr.ocrRead(itemScreenshot)]).replace(" ","").replace("-","").lower()
                if itemOCRName in itemOCRText or self.getStringSimilarity(itemOCRName, itemOCRText) > 0.7:
                    print(itemOCRText)
                    bestY = max_loc[1]
                    break

            mouse.scroll(-2, True)
            time.sleep(0.06)

            screen = cv2.cvtColor(mssScreenshotNP(self.robloxWindow.mx, self.robloxWindow.my+100, 100, 200), cv2.COLOR_BGRA2RGB)
            hash = average_hash(Image.fromarray(screen))
            if not prevHash is None and prevHash == hash:
                break
            prevHash = hash

        if bestY is None:
            self.logger.webhook("", f"Could not find {itemName} in inventory", "dark brown")
            return
        bestY //= self.robloxWindow.multi
        return (40, bestY+80)

    #click at the specified coordinates to use an item in the inventory
    #if x/y is not provided, find the item in inventory
    def useItemInInventory(self, itemName = None, x = None, y = None, closeInventoryAfter=True):
        with self.inventoryInteraction():
            if x is None or y is None:
                if itemName is None: raise Exception("tried searching for item but no item name is provided")
                res = self._findItemInInventory(itemName)
                if res is None:
                    return False
                x, y = res

            mouse.moveTo(self.robloxWindow.mx+x, self.robloxWindow.my+y)
            mouse.moveBy(10,15)
            for _ in range(3):
                mouse.click()
                mouse.moveBy(0,15, pause=False)
                time.sleep(0.03)
            self.clickYes()
            #close inventory
            if closeInventoryAfter:
                self.toggleInventory("close")
            return True


_standaloneSearchLock = threading.Lock()

def findItemWithoutMacro(query, discordMessageQueue=None):
    """/finditem while the macro is stopped or paused, run in the Discord bot process.
    Focuses Roblox, or joins Bee Swarm with the macro's own rejoin (private servers, failover, join errors)
    if it isn't open, then searches. Returns (message, image or None)."""
    if not _standaloneSearchLock.acquire(blocking=False):
        return "Already searching the inventory", None
    try:
        from modules.macro.core import macro
        # No run state or interrupt, so nothing in this macro waits on a pause. Status and logs stay local
        # so they don't overwrite a paused macro's, but its messages still reach Discord.
        host = macro(SimpleNamespace(value=""), queue.Queue(), SimpleNamespace(value=0), discordMessageQueue=discordMessageQueue)
        if appManager.isAppOpen("roblox"):
            appManager.openApp("Roblox")
            raw_time.sleep(0.5)
            host.setRobloxWindowInfo()
        elif not host.rejoin("Opening Roblox for /finditem", claimHive=False):
            return "Could not join Bee Swarm", None
        return host.findItemReport(query)
    finally:
        _standaloneSearchLock.release()
