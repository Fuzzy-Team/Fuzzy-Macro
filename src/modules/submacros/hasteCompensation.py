import cv2
import base64
import pyautogui as pag
from modules.screen.screenshot import mssScreenshotNP
import numpy as np
import time
from PIL import Image
from io import BytesIO
from modules import bitmap_matcher
import mss
import mss.darwin
mss.darwin.IMAGE_OPTIONS = 0
from modules.screen.robloxWindow import RobloxWindowBounds
from modules.submacros.hourlyReport import NATRO_BUFF_CHARACTER_TEMPLATES

class HasteCompensationOptimized():
    mw, mh = pag.size() 
    BUFF_REGION = (0, 30, int(mw / 1.8), 70)

    def __init__(self, isRetina, baseMoveSpeed):
        self.isRetina = isRetina
        self.baseMoveSpeed = baseMoveSpeed
        self.buff_region = HasteCompensationOptimized.BUFF_REGION

        #load templates
        self.hasteStacks = []
        for i in range(10):
            img = self._loadTemplate(f"./images/buffs/haste{i+1}.png")
            self.hasteStacks.append(img)
        #store as (index, template) pairs
        self.hasteStacks = list(enumerate(self.hasteStacks))[::-1] 

        self.bearMorphs = []
        for i in range(5):
            # Prepare bear morph templates
            img = self._loadTemplate(f"./images/buffs/bearmorph{i+1}-retina.png")
            self.bearMorphs.append(img)

        #no gray, haste+ is color-dependent
        self.hastePlus = self._loadTemplate(f"./images/buffs/haste+.png", gray=False)

        self.prevHaste = 0
        self.prevHaste368 = 0
        self.hasteEnds = 0
        self.prevHasteEnds = 0

    def _loadTemplate(self, path, gray=True):
        try:
            img = Image.open(path)
            width, height = img.size
            #scale based on display type
            scaling = 1 if self.isRetina else 2
            img = img.resize((int(width / scaling), int(height / scaling)))
            #convert to cv2
            cv2Img = np.array(img)
            if gray:
                return cv2.cvtColor(cv2Img, cv2.COLOR_RGB2GRAY)
            else:
                return cv2.cvtColor(cv2Img, cv2.COLOR_RGB2BGR)

        except FileNotFoundError:
            print(f"Warning: Template image not found at {path}")
            return None # Handle missing files gracefully
        except Exception as e:
            print(f"Error processing template {path}: {e}")
            return None

    def _thresholdMatch(self, target_template, screen_grayscale, threshold=0.7):
        """Performs template matching on grayscale images."""
        if target_template is None: # Skip if template failed to load
             return (False, 0.0)
             
        res = cv2.matchTemplate(screen_grayscale, target_template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
        return (max_val > threshold, max_val)


    def getHaste(self):
        screenBGR = cv2.cvtColor(mssScreenshotNP(self.buff_region[0], self.buff_region[1], self.buff_region[2], self.buff_region[3]), cv2.COLOR_RGBA2BGR)

        screen_grayscale = cv2.cvtColor(screenBGR, cv2.COLOR_BGR2GRAY)

        bestHaste = 0
        bestHasteMaxVal = 0
        for i, template in self.hasteStacks:
            if template is None: continue
       
            res, val = self._thresholdMatch(template, screen_grayscale, 0.75) 
            if res and val > bestHasteMaxVal:
                bestHasteMaxVal = val
                bestHaste = i + 1 # i is the 0-based index


        #3, 6, 8 can be misrecognised as each other
        if bestHaste in [3, 6, 8]:
            if self.prevHaste368 == 2: 
                bestHaste = 3
            elif self.prevHaste368 == 5: 
                bestHaste = 6 
            elif self.prevHaste368 == 7:
                bestHaste = 8
        elif bestHaste:
            self.prevHaste368 = bestHaste 


        hasteOut = bestHaste

        #failed to detect haste, but the haste is still there (~7.5 secs remaining)
        if not hasteOut:
            currTime = time.time()
            if currTime > self.hasteEnds and self.prevHaste: #there is no ongoing hasteEnds
                self.prevHasteEnds = self.prevHaste #value to set for the time compensation
                #decrease the countdown for retina (detection is more accurate)
                if self.isRetina:
                    self.hasteEnds = currTime + (0 if hasteOut == 1 else 2)
                else:
                    self.hasteEnds = currTime + (4 if hasteOut == 1 else 7)
            #there is a hasteEnd ongoing
            if currTime < self.hasteEnds:
                hasteOut = self.prevHasteEnds

        self.prevHaste = bestHaste

        #match bear
        bearMorph = 0 
        bear_threshold = 0.75
        for template in self.bearMorphs:
            if template is None: continue
            if self._thresholdMatch(template, screen_grayscale, bear_threshold)[0]:
                bearMorph = 4
                break

        #match haste+
        haste_plus_threshold = 0.75
        if self._thresholdMatch(self.hastePlus, screenBGR, haste_plus_threshold)[0]:
            print("hastePlus")
            hasteOut += 10

        #print(f"Haste stacks: {hasteOut}, Bear: {bearMorph}")
        final_speed = (self.baseMoveSpeed + bearMorph) * (1 + (0.1 * hasteOut))

        # print(f"Calculation time: {time.perf_counter() - st:.4f}s") # Debug timing
        return final_speed
    
class HasteCompensationRevamped():
    def __init__(self, robloxWindow: RobloxWindowBounds, baseMoveSpeed):
        self.robloxWindow = robloxWindow
        self.baseMoveSpeed = baseMoveSpeed

        self.countBitmaps = self._loadCountBitmaps()
        self.bearMorphs = []
        self.hasteBitmap = Image.new('RGBA', (10, 1), '#f0f0f0ff')
        self.melodyBitmap = Image.new('RGBA', (3, 2), '#2b2b2bff')

        if self.robloxWindow.isRetina:
            for i in range(6):
                self.bearMorphs.append(Image.open(f"./images/buffs/bearmorph{i+1}-retina.png").convert('RGBA'))

            self.hastePlus = Image.open("./images/buffs/haste+-retina.png").convert('RGBA')
        else:
            #base64 images taken directly from natro macro
            #https://github.com/NatroTeam/NatroMacro/blob/main/lib/Walk.ahk

            self.bearMorphs.append(bitmap_matcher.create_bitmap_from_base64("iVBORw0KGgoAAAANSUhEUgAAAAwAAAABBAMAAAAYxVIKAAAAD1BMVEUwLi1STEihfVWzpZbQvKTt7OCuAAAAEklEQVR4AQEHAPj/ACJDEAE0IgLvAM1oKEJeAAAAAElFTkSuQmCC"))
            self.bearMorphs.append(bitmap_matcher.create_bitmap_from_base64("iVBORw0KGgoAAAANSUhEUgAAAA4AAAABBAMAAAAcMII3AAAAFVBMVEUwLi1TTD9lbHNmbXN5enW5oXHQuYJDhTsuAAAAE0lEQVR4AQEIAPf/ACNGUQAVZDIFbwFmjB55HwAAAABJRU5ErkJggg=="))
            self.bearMorphs.append(bitmap_matcher.create_bitmap_from_base64("iVBORw0KGgoAAAANSUhEUgAAABAAAAABBAMAAAAlVzNsAAAAGFBMVEUwLi1VU1G9u7m/vLXAvbbPzcXg3dfq6OXkYMPeAAAAFElEQVR4AQEJAPb/AENWchABJ2U0CO4B3TmcTKkAAAAASUVORK5CYII="))
            self.bearMorphs.append(bitmap_matcher.create_bitmap_from_base64("iVBORw0KGgoAAAANSUhEUgAAAA4AAAABBAMAAAAcMII3AAAAElBMVEUwLi1JSUqOlZy0vMbY2dnc3NtuftTJAAAAE0lEQVR4AQEIAPf/AFVDIQASNFUFhQFVdZ1AegAAAABJRU5ErkJggg=="))
            self.bearMorphs.append(bitmap_matcher.create_bitmap_from_base64("iVBORw0KGgoAAAANSUhEUgAAAA4AAAABBAMAAAAcMII3AAAAFVBMVEUwLi1TTD+zjUy0jky8l1W5oXHevny+g95vAAAAE0lEQVR4AQEIAPf/ACNGUQAVZDIFbwFmjB55HwAAAABJRU5ErkJggg=="))
            self.bearMorphs.append(bitmap_matcher.create_bitmap_from_base64("iVBORw0KGgoAAAANSUhEUgAAABAAAAABBAMAAAAlVzNsAAAAJFBMVEVBNRlDNxtTRid8b0avoG69r22+sG7Qw4PRw4Te0Jbk153m2Z5VNHxxAAAAFElEQVR4AQEJAPb/AFVouTECSnZVDPsCv+2QpmwAAAAASUVORK5CYII="))

            self.hastePlus = Image.new('RGBA', (20, 1), '#eddb4cff')

        self.prevHaste = 0
        self.endTime = 0

    def _loadCountBitmaps(self):
        if self.robloxWindow.isRetina:
            return [
                Image.open(f"images/buffs/counts/{value}.png").convert("RGBA")
                for value in range(2, 11)
            ]

        scale = max(1, int(round(getattr(self.robloxWindow, "multi", 1) or 1)))
        bitmaps = []
        for value in range(2, 11):
            templateDigit = 1 if value == 10 else value
            raw = base64.b64decode(NATRO_BUFF_CHARACTER_TEMPLATES[templateDigit])
            img = Image.open(BytesIO(raw)).convert("RGBA")
            if scale != 1:
                img = img.resize((img.width * scale, img.height * scale), Image.Resampling.NEAREST)
            bitmaps.append(img)
        return bitmaps

    def screenshotBuff(self):   
        with mss.mss() as sct:
            monitor = {"left": int(self.robloxWindow.mx), "top": int(self.robloxWindow.my+self.robloxWindow.yOffset+33), "width": int(self.robloxWindow.mw), "height": int(48)}
            sct_img = sct.grab(monitor)
            img = Image.frombytes("RGBA", sct_img.size, sct_img.bgra, "raw", "BGRA")
            #img.save(f"buff_area.png")
            return img

    #similar to natro's implementation for haste detection
    def getHaste(self):
        start_time = time.time()
        screen = self.screenshotBuff()
        haste = 0
        hasteX = None

        x = 0
        #locate haste. It shares the same color as melody
        for _ in range(3):
            res = bitmap_matcher.find_bitmap_cython(screen, self.hasteBitmap, x=x, variance=0)
            if not res:
                break
            x = res[0]
            #can't find melody, so its haste
            if not bitmap_matcher.find_bitmap_cython(screen, self.melodyBitmap, x=x+2, w=16*self.robloxWindow.multi, variance=2):
                hasteX = res[0]
                break
            #melody, skip this buff
            x+= 40*self.robloxWindow.multi

        #haste found, get count
        if hasteX:
            for i, img in enumerate(self.countBitmaps):
                res = bitmap_matcher.find_bitmap_cython(screen, img, x=hasteX, w=38*self.robloxWindow.multi, variance=0)
                if res:
                    haste = i+2
                    break
            else:
                haste = 1
            
        
        #search for bear morphs
        bearmorphSpeed = 0
        for img in self.bearMorphs:
            if bitmap_matcher.find_bitmap_cython(screen, img, variance=30):
                bearmorphSpeed = 4
                break
        end_time = time.time()

        #search for haste+
        if bitmap_matcher.find_bitmap_cython(screen, self.hastePlus, variance=20 if self.robloxWindow.isRetina else 2):
            haste += 10
            
        #print(end_time-start_time)
        #print(f"{(self.baseMoveSpeed + bearmorphSpeed) * (1 + (0.1 * haste))} --- {self.baseMoveSpeed}, {haste}")
        
        return (self.baseMoveSpeed + bearmorphSpeed) * (1 + (0.1 * haste))
