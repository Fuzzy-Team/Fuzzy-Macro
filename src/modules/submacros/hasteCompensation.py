import base64
import sys
import cv2
import numpy as np
from PIL import Image
from io import BytesIO
from modules import bitmap_matcher
from modules.screen.robloxWindow import RobloxWindowBounds
from modules.screen.screenshot import mssScreenshotPillowRGBA
from modules.reports.buffs import NATRO_BUFF_CHARACTER_TEMPLATES

class HasteCompensationRevamped():
    def __init__(self, robloxWindow: RobloxWindowBounds, baseMoveSpeed):
        self.robloxWindow = robloxWindow
        self.baseMoveSpeed = baseMoveSpeed

        self.countBitmaps = self._loadCountBitmaps()
        self.bearMorphs = []
        self.hasteBitmap = Image.new('RGBA', (10, 1), '#f0f0f0ff')
        self.melodyBitmap = Image.new('RGBA', (3, 2), '#2b2b2bff')
        #Natro's oil and super smoothie buff icons (one-pixel colour strips)
        self.oilBitmap = self._loadNatroBuffBitmap("iVBORw0KGgoAAAANSUhEUgAAABQAAAABBAMAAAAsvJMWAAAALVBMVEVKRDlNRjlXTTpgVDtwXjhzXzV5ZDaDaziefjutiT3Gm0LWp0XsuEv8xE/+xlCsCySdAAAAFklEQVR4AQELAPT/AO7bl1MQACRorO4cdQTqnFFEXAAAAABJRU5ErkJggg==")
        self.smoothieBitmap = self._loadNatroBuffBitmap("iVBORw0KGgoAAAANSUhEUgAAABgAAAABBAMAAAA2gHOYAAAAMFBMVEVKRDlKRTlYTjpjVjtvXjh1YDV2YTV5YzeNcjmkgzywiz3PokTotUr0vk36w0/+xlDRVtQJAAAAGElEQVR4AQENAPL/AP7JcxAAAAACRWir3x4xBISoIvpcAAAAAElFTkSuQmCC")

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

        # On Windows a plain white line also matches hive art, pads and name tags far from the buffs,
        # so haste is recognised by the running figure on its icon instead.
        self.hasteFigure = None
        if sys.platform == "win32" and not self.robloxWindow.isRetina:
            self.hasteFigure = self._loadHasteFigure()

        self.prevHaste = 0
        self.endTime = 0

    def _loadHasteFigure(self):
        icon = np.asarray(Image.open("./images/buffs/haste-icon-windows.png").convert("RGB"), dtype=np.int16)
        figure = ((icon.max(axis=2) - icon.min(axis=2) <= 8) & (icon.mean(axis=2) < 185)).astype(np.uint8)
        kernel = np.ones((3, 3), np.uint8)
        body = cv2.erode(figure, kernel)
        surround = cv2.dilate(figure, kernel, iterations=3) & (1 - cv2.dilate(figure, kernel))
        for mask in (body, surround):
            mask[18:, 12:] = 0  # the stack count is drawn over the lower right
            mask[[0, -1], :] = 0
            mask[:, [0, -1]] = 0
        bodyY, bodyX = np.nonzero(body)
        return bodyY, bodyX, icon[bodyY, bodyX].mean(axis=1), np.nonzero(surround)

    def findHasteIcons(self, screen):
        """Left edges of the haste icons in the buff strip, left to right."""
        strip = np.asarray(screen, dtype=np.int16)[:, :, :3]
        bodyY, bodyX, shade, (surroundY, surroundX) = self.hasteFigure

        # the white time-left bar ends sharply at the bottom of the icon (rows 37-46 as the icon pops in)
        white = np.zeros((strip.shape[0], strip.shape[1] + 1), np.int32)
        np.cumsum(np.abs(strip - 240).max(axis=2) <= 2, axis=1, out=white[:, 1:])
        share = (white[:, 36:] - white[:, 2:-34]) / 34
        xs = np.nonzero((share[37:47] - share[38:48]).max(axis=0) >= 0.5)[0]
        xs = xs[xs <= strip.shape[1] - 38]
        if not xs.size:
            return []

        tops = np.array([3, 4, 5])[:, None, None]
        columns = xs[None, :, None]
        pixels = strip[tops + bodyY, columns + bodyX]
        grey = pixels.mean(axis=3)
        neutral = np.ptp(pixels, axis=3) <= 14
        # the unfilled part of the icon is dimmed, which darkens the figure slightly
        dim = np.clip(np.median(grey - shade, axis=2, keepdims=True), -26, 8)
        bodyFit = (neutral & (np.abs(grey - shade - dim) <= 12)).mean(axis=2)
        level = np.median(grey, axis=2)[:, :, None, None]
        around = strip[tops + surroundY, columns + surroundX]
        outline = (np.abs(around - level).max(axis=3) > 18).mean(axis=2)
        # saved frames: haste scores at least 0.53 and 0.83; nothing else with the bar scores anywhere near
        score = np.where((bodyFit >= 0.45) & (outline >= 0.8), bodyFit + outline, 0).max(axis=0)

        icons = []
        for i in np.argsort(-score):
            if not score[i]:
                break
            if all(abs(int(xs[i]) - x) >= 20 for x in icons):
                icons.append(int(xs[i]))
        return sorted(icons)

    def _loadNatroBuffBitmap(self, encoded):
        bitmap = bitmap_matcher.create_bitmap_from_base64(encoded)
        scale = max(1, int(self.robloxWindow.multi)) if self.robloxWindow.isRetina else 1
        if scale != 1:
            bitmap = bitmap.resize(
                (bitmap.width * scale, bitmap.height * scale),
                Image.Resampling.NEAREST,
            )
        return bitmap

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
        return mssScreenshotPillowRGBA(
            self.robloxWindow.mx, self.robloxWindow.my + self.robloxWindow.yOffset + 33,
            self.robloxWindow.mw, 48,
        )

    #similar to natro's implementation for haste detection
    def getHaste(self):
        screen = self.screenshotBuff()
        haste = 0
        hasteX = None
        hasteIcons = 0

        if self.hasteFigure is not None:
            icons = self.findHasteIcons(screen)
            hasteIcons = len(icons)
            hasteX = icons[0] if icons else None

        x = 0
        #locate haste. It shares the same color as melody
        for _ in range(3 if self.hasteFigure is None else 0):
            res = bitmap_matcher.find_bitmap_cython(screen, self.hasteBitmap, x=x, variance=0)
            if not res:
                break
            x = res[0]
            #can't find melody, so its haste
            if not bitmap_matcher.find_bitmap_cython(screen, self.melodyBitmap, x=x+2, w=16*self.robloxWindow.multi, variance=2):
                if hasteX is None:
                    hasteX = res[0]
                hasteIcons += 1
            #skip this buff, whether it is melody or haste
            x+= 40*self.robloxWindow.multi

        #haste found, get count
        if hasteIcons:
            for i, img in enumerate(self.countBitmaps):
                res = bitmap_matcher.find_bitmap_cython(screen, img, x=hasteX, w=38*self.robloxWindow.multi, variance=0)
                if res:
                    haste = i+2
                    break
            else:
                haste = 1
            
        
        #search for bear morphs
        bearmorphSpeed = 0
        # on Windows these one-row bitmaps also match scenery; the buff is only ever on the icons' bottom row
        bearArea = screen if self.hasteFigure is None else screen.crop((0, 41, screen.width, 42))
        for img in self.bearMorphs:
            if bitmap_matcher.find_bitmap_cython(bearArea, img, variance=30):
                bearmorphSpeed = 4
                break

        #a second haste icon is Coconut Haste, which adds 10 flat movespeed
        coconutHasteSpeed = 10 if hasteIcons >= 2 else 0

        #search for haste+
        hastePlus = bool(bitmap_matcher.find_bitmap_cython(screen, self.hastePlus, variance=20 if self.robloxWindow.isRetina else 2))
        #haste+ doubles movespeed; it is not another 10 haste stacks
        speedMultiplier = 2 if hastePlus else 1

        #oil and super smoothie multiply movespeed on top of haste and bear morphs
        buffVariance = 20 if self.robloxWindow.isRetina else 4
        if bitmap_matcher.find_bitmap_cython(screen, self.oilBitmap, variance=buffVariance):
            speedMultiplier *= 1.2
        if bitmap_matcher.find_bitmap_cython(screen, self.smoothieBitmap, variance=buffVariance):
            speedMultiplier *= 1.25
            
        #print(end_time-start_time)
        #print(f"{(self.baseMoveSpeed + bearmorphSpeed) * (1 + (0.1 * haste))} --- {self.baseMoveSpeed}, {haste}")
        
        return (self.baseMoveSpeed + bearmorphSpeed + coconutHasteSpeed) * (1 + (0.1 * haste)) * speedMultiplier
