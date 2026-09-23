import base64
from PIL import Image
from io import BytesIO
from modules import bitmap_matcher
import mss
import mss.darwin
mss.darwin.IMAGE_OPTIONS = 0
from modules.screen.robloxWindow import RobloxWindowBounds
from modules.reports.buffs import NATRO_BUFF_CHARACTER_TEMPLATES

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

        #search for haste+
        if bitmap_matcher.find_bitmap_cython(screen, self.hastePlus, variance=20 if self.robloxWindow.isRetina else 2):
            haste += 10
            
        #print(end_time-start_time)
        #print(f"{(self.baseMoveSpeed + bearmorphSpeed) * (1 + (0.1 * haste))} --- {self.baseMoveSpeed}, {haste}")
        
        return (self.baseMoveSpeed + bearmorphSpeed) * (1 + (0.1 * haste))
