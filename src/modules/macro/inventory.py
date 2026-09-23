import cv2
import imagehash
from PIL import Image
from difflib import SequenceMatcher
import modules.controls.mouse as mouse
import modules.screen.ocr as ocr
from modules.controls.sleep import pause_aware_time as time, sleep
from modules.screen.imageSearch import locateImageOnScreen
from modules.screen.screenshot import mssScreenshot, mssScreenshotNP


class InventoryMixin:
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
        
        def scrollToTop():
            prevHash = None
            for i in range(9):
                mouse.scroll(100)
                sleep(0.05)
                if i > 10:
                    screen = cv2.cvtColor(mssScreenshotNP(self.robloxWindow.mx, self.robloxWindow.my+120, 100, 200), cv2.COLOR_BGRA2RGB)
                    hash = imagehash.average_hash(Image.fromarray(screen))
                    if not prevHash is None and prevHash == hash:
                        break
                    prevHash = hash
        #for retina, just a regular image search
        #for built-in, a transparency search
        itemImg = self.adjustImage("./images/inventory/old", itemName)
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
        scrollToTop()
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
            hash = imagehash.average_hash(Image.fromarray(screen))
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
        if x is None or y is None:
            if itemName is None: raise Exception("tried searching for item but no item name is provided")
            res = self.findItemInInventory(itemName)
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
