from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter
import cv2
import math
import time
import ast
import numpy as np
import platform
from modules.misc.messageBox import msgBox
from modules.screen.imageSearch import locateTransparentImageOnScreen, locateTransparentImage
from modules.screen.screenshot import mssScreenshotNP, mssScreenshot
from modules.misc.imageManipulation import adjustImage
import time
import pyautogui as pag
from modules.screen.ocr import ocrRead, imToString
import copy
from datetime import datetime
from modules.screen.robloxWindow import RobloxWindowBounds
import pickle
import json
from modules.misc.settingsManager import getCurrentProfile, loadFields, getMacroVersion

ww, wh = pag.size()

def versionTuple(v):
    return tuple(map(int, (v.split("."))))
macVer = platform.mac_ver()[0]

# try:
#     hti = Html2Image(size=(1900, 850))
#     if hasattr(hti.browser, 'use_new_headless'):
#         hti.browser.use_new_headless = None

    
# except FileNotFoundError:
#     if versionTuple(macVer) >= versionTuple("10.15"):
#         msgBox(title = "error", text = "Google Chrome could not be found. Ensure that:\
#     \n1. Google Chrome is installed\nGoogle chrome is in the applications folder (open the google chrome dmg file. From the pop up, drag the icon into the folder)")
#     else:
#         hti = None

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
            pass
        
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

    def getBuffsWithImage(self, buffs, save=False, screen = None, threshold=0.7):
        buffQuantity = []
        buffs = buffs.items()

        if screen is None:
            screen = self.screenshotBuffArea()

        for buff,v in buffs:
            templatePosition, transform, stackable = v

            #find the buff
            buffTemplate = adjustImage("./images/buffs", buff, self.robloxWindow.display_type)
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

                #filter out everything but the text
                buffVal = self.getBuffQuantityFromImg(fullBuffImgBGR, transform, buff=buff)
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

    def getBuffWithColor(self, buffs):
        buffQuantity = []
        buffs = buffs.items()

        screen = self.screenshotBuffArea()
        hsv = cv2.cvtColor(screen, cv2.COLOR_BGR2HSV)

        for buff,v in buffs:
            colorRange, transform, stackable = v
            lower, upper = colorRange

            #find the buff
            mask = cv2.inRange(hsv, lower, upper)
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for cnt in contours:
                rect = cv2.boundingRect(cnt)
                x, y, w, h = rect

                #filter area to avoid noise
                if self.buffSize-5 < w < self.buffSize+5:
                     #buff is either present or not, non stackable (0 or 1)
                    if not stackable:
                        buffQuantity.append("1")
                        break

                    #crop out
                    y = min(0, y+self.buffSize-h)
                    buffImgBGR = screen[y:y+self.buffSize, x:x+self.buffSize]
                    out = self.getBuffQuantityFromImg(buffImgBGR, True)
                    buffQuantity.append(out)
                    break
                else:
                    buffQuantity.append("0")
        return buffQuantity
    
    def detectBuffColorInImage(self, screen, hex, minSize, x1=0, y1=0, x2=None, y2=None, variation=0, show=False, searchDirection=1, instances=1):
        
        #convert hex to bgr and setup the color range
        r = (hex >> 16) & 0xFF
        g = (hex >> 8) & 0xFF
        b = hex & 0xFF
        bgr = [b,g,r]
        lower = np.array([x-variation for x in bgr])
        upper = np.array([x+variation for x in bgr])

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
            #in this case, the nectar quantity might be so low it cant be detected or the player doesnt have the nectar at all
            #so, we get the confidence value of the match
            #if the value is high, its probably low nectar quantity
            #if its low, the player prob doesnt have the nectar
            max_val, _  = res
            return 2 if max_val > 0.8 else 0
        # return the bounding with the largest area
        _, _, _, buffH = cv2.boundingRect(max(contours, key=cv2.contourArea))
        quantity = max(min(100, (buffH/h*100)), 1)
        return quantity


    def getNectars(self):
        nectarQuantity = []
        for nectar in self.nectars:
            nectarQuantity.append(self.getNectar(nectar))
        return nectarQuantity


class HourlyReport():
    def __init__(self, buffDetector: BuffDetector = None, time_format=24):
        #key: name of buff
        #value: [template for template matching is the buff's top, bottom or middle, if buff image should be transformed, if buff is stackable]
        self.hourBuffs = {
            "tabby_love": ["top", True, True],
            "polar_power": ["top", True, True],
            "wealth_clock": ["top", True, True],
            "blessing": ["middle", True, True],
            "bloat": ["top", True, True],
        }
        self.uptimeBearBuffs = {
            "bearmorph1": ["top", True, False],
            "bearmorph2": ["top", True, False],
            "bearmorph3": ["top", True, False],
            "bearmorph4": ["top", True, False],
            "bearmorph5": ["top", True, False],
            "bearmorph6": ["top", True, False],
        }

        self.uptimeBuffsColors = {
            # "focus": [[np.array([50, 180, 180]), np.array([80, 255, 255])], True, True],
            "baby_love": [0xff8de4f3, (5, 1)],
            "haste": [0xfff0f0f0, (5, 1)],
            "melody": [0xff242424, (3,2)],
            "focus": [0xff22ff06, (5,1)],
            "bomb_combo": [0xff272727, (5,1)],
            "balloon_aura": [0xfffafd38, (5,1)],
            "boost": [0xff90ff8e, (5,1)],
            "blue_boost": [0xff56a4e4, (4,2)],
            "red_boost": [0xffe46156, (4,2)],
            "inspire": [0xfff4ef14, (5,1)]
        }

        self.buffDetector = buffDetector
        self.hourlyReportDrawer = HourlyReportDrawer(time_format)

        #setup stats
        self.hourlyReportStats = {}
        self.sessionReportStats = {}
        self.sessionUptimeBuffsValues = {}
        self.sessionBuffGatherIntervals = []
        self.latestBuffQuantity = []
        self.latestNectarQuantity = []

    def _defaultSessionReportStats(self):
        return {
            "honey_per_min": [],
            "backpack_per_min": [],
            "bugs": 0,
            "quests_completed": 0,
            "vicious_bees": 0,
            "gathering_time": 0,
            "converting_time": 0,
            "bug_run_time": 0,
            "misc_time": 0,
        }

    def _defaultHourlyUptimeBuffs(self):
        uptimeBuffs = {k:[0]*600 for k in self.uptimeBuffsColors.keys()}
        for k in ["bear", "white_boost"]:
            uptimeBuffs[k] = [0]*600
        return uptimeBuffs

    def _defaultSessionUptimeBuffs(self):
        sessionUptimeBuffs = {k:[] for k in self.uptimeBuffsColors.keys()}
        for k in ["bear", "white_boost"]:
            sessionUptimeBuffs[k] = []
        return sessionUptimeBuffs

    def recordUptimeSample(self, index, sampleValues, isGathering=False):
        for buffName in self._defaultSessionUptimeBuffs():
            value = int(sampleValues.get(buffName, 0) or 0)
            if buffName not in self.uptimeBuffsValues:
                self.uptimeBuffsValues[buffName] = [0] * 600
            if 0 <= index < len(self.uptimeBuffsValues[buffName]):
                self.uptimeBuffsValues[buffName][index] = value

            if buffName not in self.sessionUptimeBuffsValues:
                self.sessionUptimeBuffsValues[buffName] = []
            self.sessionUptimeBuffsValues[buffName].append(value)

        if not hasattr(self, "buffGatherIntervals") or self.buffGatherIntervals is None:
            self.buffGatherIntervals = [0] * 600
        if 0 <= index < len(self.buffGatherIntervals):
            self.buffGatherIntervals[index] = 1 if isGathering else 0

        if not hasattr(self, "sessionBuffGatherIntervals") or self.sessionBuffGatherIntervals is None:
            self.sessionBuffGatherIntervals = []
        self.sessionBuffGatherIntervals.append(1 if isGathering else 0)

    def filterOutliers(self, values, threshold=3):
        nonZeroValues = [x for x in values if x]
        
        # If no non-zero values or insufficient data, return original values
        if len(nonZeroValues) < 2:
            return values
        
        # Calculate the mean and standard deviation
        mean = np.mean(nonZeroValues)
        std_dev = np.std(nonZeroValues)

        #standard deviation is 0, no outliers, prevent division by zero
        if std_dev == 0:
            return values 
        
        # Calculate Z-scores
        z_scores = [(x - mean) / std_dev for x in values]
        
        # Filter out values with Z-scores greater than the threshold
        filtered_values = [x for x, z in zip(values, z_scores) if abs(z) < threshold or not x]
        
        return filtered_values

    def generateHourlyReport(self, setdat):
        buffQuantity = self.buffDetector.getBuffsWithImage(self.hourBuffs)
        nectarQuantity = self.buffDetector.getNectars()
        self.latestBuffQuantity = list(buffQuantity)
        self.latestNectarQuantity = list(nectarQuantity)
        #mssScreenshot(save=True)

        #get the hourly report data

        planterData = ""
        #get planter data
        if setdat["planters_mode"] == 1:
            with open("./data/user/manualplanters.txt", "r") as f:
                planterData = f.read()
            f.close()

            if planterData:
                planterData = ast.literal_eval(planterData)
        elif setdat["planters_mode"] == 2:
            with open("./data/user/auto_planters.json", "r") as f:
                planterData = json.load(f)["planters"]
            f.close()
            planterData = {
                "planters": [p["planter"] for p in planterData],
                "harvestTimes": [p["harvest_time"] for p in planterData],
                "fields": [p["field"] for p in planterData],
            }
            if all(not p for p in planterData["planters"]):
                planterData = ""


        #get history
        with open("data/user/hourly_report_history.txt", "r") as f:
            historyData = ast.literal_eval(f.read())
        f.close()
        
        if len(self.hourlyReportStats["honey_per_min"]) < 3:
            self.hourlyReportStats["honey_per_min"] = [0]*3 + self.hourlyReportStats["honey_per_min"]
        #filter out the honey/min
        print(self.hourlyReportStats["honey_per_min"])
        #self.hourlyReportStats["honey_per_min"] = [x for x in self.hourlyReportStats["honey_per_min"] if x]
        self.hourlyReportStats["honey_per_min"] = self.filterOutliers(self.hourlyReportStats["honey_per_min"])
        #calculate honey/min
        honeyPerMin = [0]
        prevHoney = self.hourlyReportStats["honey_per_min"][0]
        for x in self.hourlyReportStats["honey_per_min"][1:]:
            if x > prevHoney:
                honeyPerMin.append((x-prevHoney)/60)
            prevHoney = x
        
        #calculate some stats
        if len(set(self.hourlyReportStats["honey_per_min"])) <= 1:
            onlyValidHourlyHoney = self.hourlyReportStats["honey_per_min"].copy()
        else:
            onlyValidHourlyHoney = [x for x in self.hourlyReportStats["honey_per_min"] if x] #removes all zeroes
        sessionHoney = max(0, onlyValidHourlyHoney[-1]- self.hourlyReportStats["start_honey"])
        sessionTime = time.time()-self.hourlyReportStats["start_time"]
        honeyThisHour = max(0, onlyValidHourlyHoney[-1] - onlyValidHourlyHoney[0])

        hourlyReportStats = copy.deepcopy(self.hourlyReportStats)

        # determine enabled fields and their patterns from profile settings
        enabled_fields = []
        field_patterns = {}
        try:
            profile_fields_settings = loadFields()
        except Exception:
            profile_fields_settings = {}

        fields_list = setdat.get("fields", []) if isinstance(setdat, dict) else []
        fields_enabled = setdat.get("fields_enabled", []) if isinstance(setdat, dict) else []
        # normalize lengths
        if len(fields_enabled) < len(fields_list):
            fields_enabled += [False] * (len(fields_list) - len(fields_enabled))

        for i, fname in enumerate(fields_list):
            try:
                if fields_enabled[i]:
                    enabled_fields.append(fname)
                    pattern = profile_fields_settings.get(fname, {}).get("shape") if isinstance(profile_fields_settings, dict) else None
                    field_patterns[fname] = pattern or "unknown"
            except Exception:
                continue

        canvas = self.hourlyReportDrawer.drawHourlyReport(hourlyReportStats, sessionTime, honeyPerMin, 
                                                          sessionHoney, honeyThisHour, onlyValidHourlyHoney, 
                                                          buffQuantity, nectarQuantity, planterData, 
                                                          self.uptimeBuffsValues, self.buffGatherIntervals,
                                                          enabled_fields, field_patterns)
        w, h = canvas.size
        canvas = canvas.resize((int(w*1.2), int(h*1.2))) 
        canvas.save("hourlyReport.png")

        return hourlyReportStats

    def resetHourlyStats(self):
        self.hourlyReportStats["honey_per_min"] = []
        self.hourlyReportStats["backpack_per_min"] = []
        self.hourlyReportStats["bugs"] = 0
        self.hourlyReportStats["quests_completed"] = 0
        self.hourlyReportStats["vicious_bees"] = 0
        self.hourlyReportStats["gathering_time"] = 0
        self.hourlyReportStats["converting_time"] = 0
        self.hourlyReportStats["bug_run_time"] = 0
        self.hourlyReportStats["misc_time"] = 0

        self.uptimeBuffsValues = self._defaultHourlyUptimeBuffs()
        self.buffGatherIntervals = [0]*600

        self.saveHourlyReportData()
    
    def resetAllStats(self):
        self.hourlyReportStats["start_time"] = 0
        self.hourlyReportStats["start_honey"] = 0
        self.sessionReportStats = self._defaultSessionReportStats()
        self.sessionUptimeBuffsValues = self._defaultSessionUptimeBuffs()
        self.sessionBuffGatherIntervals = []
        self.latestBuffQuantity = []
        self.latestNectarQuantity = []
        self.resetHourlyStats()
    
    def addHourlyStat(self, stat, value):
        if isinstance(self.hourlyReportStats[stat], list):
            self.hourlyReportStats[stat].append(value)
        else:
            self.hourlyReportStats[stat] += value

        # Keep session totals independent from hourly resets.
        if stat in self.sessionReportStats:
            if isinstance(self.sessionReportStats[stat], list):
                self.sessionReportStats[stat].append(value)
            else:
                self.sessionReportStats[stat] += value
        self.saveHourlyReportData()
    
    def setSessionStats(self, start_honey, start_time):
        self.hourlyReportStats["start_honey"] = start_honey
        self.hourlyReportStats["start_time"] = start_time
        self.saveHourlyReportData()
    
    def saveHourlyReportData(self):
        with open("data/user/hourly_report_stats.pkl", "wb") as f:
            pickle.dump({
                "hourlyReportStats": self.hourlyReportStats,
                "sessionReportStats": self.sessionReportStats,
                "uptimeBuffsValues": self.uptimeBuffsValues,
                "buffGatherIntervals": self.buffGatherIntervals,
                "sessionUptimeBuffsValues": self.sessionUptimeBuffsValues,
                "sessionBuffGatherIntervals": self.sessionBuffGatherIntervals,
                "latestBuffQuantity": self.latestBuffQuantity,
                "latestNectarQuantity": self.latestNectarQuantity,
            }, f)
    
    def loadHourlyReportData(self):
        with open("data/user/hourly_report_stats.pkl", "rb") as f:
            data = pickle.load(f)
            self.hourlyReportStats = data["hourlyReportStats"]
            self.sessionReportStats = data.get("sessionReportStats", self._defaultSessionReportStats())
            self.uptimeBuffsValues = data.get("uptimeBuffsValues", self._defaultHourlyUptimeBuffs())
            self.buffGatherIntervals = data.get("buffGatherIntervals", [0]*600)
            self.sessionUptimeBuffsValues = data.get("sessionUptimeBuffsValues", self._defaultSessionUptimeBuffs())
            self.sessionBuffGatherIntervals = data.get("sessionBuffGatherIntervals", [])
            self.latestBuffQuantity = data.get("latestBuffQuantity", [])
            self.latestNectarQuantity = data.get("latestNectarQuantity", [])


class HourlyReportDrawer:
    def __init__(self, time_format=24):
        self.backgroundColor = (13, 11, 10, 255)
        self.backgroundTopColor = (17, 14, 13)
        self.backgroundBottomColor = (28, 23, 20)
        self.surfaceColor = (33, 27, 24)
        self.surfaceRaisedColor = (45, 37, 32)
        self.surfaceInsetColor = (22, 18, 16)
        self.borderColor = (88, 70, 56)
        self.innerBorderColor = (132, 106, 84)
        self.primaryColor = (171, 128, 98)
        self.primarySoftColor = (205, 153, 117)
        self.honeyColor = (239, 218, 152)
        self.secondaryAccentColor = (157, 142, 195)
        self.bodyColor = (246, 239, 230)
        self.mutedColor = (194, 179, 164)
        self.subtleColor = (152, 138, 124)
        self.gridColor = (88, 72, 60)
        self.canvasSize = (6400, 8000)
        self.sidebarWidth = 1900
        self.leftPadding = 150
        self.availableSpace = self.canvasSize[0] - self.sidebarWidth - self.leftPadding*2
        self.time_format = time_format
        self.hour = datetime.now().hour
        self.sideBarBackground = (25, 21, 19)
        if self.hour == 0:
            self.hour = 23
        else:
            self.hour -= 1
        self.assetPath = "hourly_report/assets"

    def transformXLabelTime(self, i, val):
        if i%10:
            return
        hour = self.hour
        if val == 60:
            hour += 1
            if hour == 24:
                hour = 0
            val = 0

        time_str = f"{str(hour).zfill(2)}:{str(val).zfill(2)}"
        if self.time_format == 12:
            # Convert to 12-hour format
            hour_12 = hour % 12
            if hour_12 == 0:
                hour_12 = 12
            am_pm = "AM" if hour < 12 else "PM"
            time_str = f"{str(hour_12).zfill(2)}:{str(val).zfill(2)} {am_pm}"

        return time_str

    def millify(self, n):
        if not n: return "0"
        millnames = ['',' K',' M',' B',' T', 'Qd']
        n = float(n)
        millidx = max(0,min(len(millnames)-1,
                            int(math.floor(0 if n == 0 else math.log10(abs(n))/3))))

        return '{:.2f} {}'.format(n / 10**(3 * millidx), millnames[millidx])

    def displayTime(self, seconds, units = ['w','d','h','m','s']):
        intervals = (
            ('w', 604800),  # 60 * 60 * 24 * 7
            ('d', 86400),    # 60 * 60 * 24
            ('h', 3600),    # 60 * 60
            ('m', 60),
            ('s', 1),
        )
        result = []

        for name, count in intervals:
            value = seconds // count
            if value:
                seconds -= value * count
                if value == 1:
                    name = name.rstrip('s')
                if name in units:
                    value = int(value)
                    if value < 10:
                        value = "0"+str(value)
                    result.append("{}{}".format(value, name))
        if not result:
            return "0s"
        return ' '.join(result)
        
    def getFont(self, weight, fontSize):
        return ImageFont.truetype(f"hourly_report/Inter/static/Inter_18pt-{weight.title()}.ttf", fontSize)

    def toRgb(self, color):
        if isinstance(color, tuple):
            return tuple(int(c) for c in color[:3])
        if isinstance(color, str):
            color = color.lstrip("#")
            if len(color) >= 6:
                return tuple(int(color[i:i+2], 16) for i in (0, 2, 4))
        return (255, 255, 255)

    def withAlpha(self, color, alpha):
        rgb = self.toRgb(color)
        return (*rgb, max(0, min(255, int(alpha))))

    def blendColor(self, start, end, ratio):
        start = self.toRgb(start)
        end = self.toRgb(end)
        ratio = max(0.0, min(1.0, float(ratio)))
        return tuple(int(start[i] + (end[i] - start[i]) * ratio) for i in range(3))

    def tintedSurface(self, accent, amount=0.1):
        return self.blendColor(self.surfaceColor, accent, amount)

    def beginReportCanvas(self):
        base = Image.new("RGBA", self.canvasSize, self.backgroundColor)
        gradientDraw = ImageDraw.Draw(base)
        for y in range(self.canvasSize[1]):
            ratio = y / max(self.canvasSize[1] - 1, 1)
            color = self.blendColor(self.backgroundTopColor, self.backgroundBottomColor, ratio)
            gradientDraw.line((0, y, self.canvasSize[0], y), fill=self.withAlpha(color, 255))

        overlay = Image.new("RGBA", self.canvasSize, (0, 0, 0, 0))
        overlayDraw = ImageDraw.Draw(overlay)
        overlayDraw.ellipse((-800, -200, 2600, 2200), fill=self.withAlpha(self.primaryColor, 44))
        overlayDraw.ellipse((3450, -200, 7000, 1800), fill=self.withAlpha(self.honeyColor, 18))
        overlayDraw.ellipse((4200, 4600, 7600, 7900), fill=self.withAlpha(self.secondaryAccentColor, 18))
        overlayDraw.rectangle((0, 0, self.canvasSize[0], 480), fill=self.withAlpha(self.primaryColor, 12))
        overlay = overlay.filter(ImageFilter.GaussianBlur(160))

        self.canvas = Image.alpha_composite(base, overlay)
        self.draw = ImageDraw.Draw(self.canvas)

    def drawPanel(self, x, y, width, height, accent=None, fill=None, radius=64, shadowAlpha=78):
        accent = self.toRgb(accent or self.primaryColor)
        fill = self.toRgb(fill or self.surfaceColor)

        shadowBox = (x + 14, y + 18, x + width + 14, y + height + 18)
        self.draw.rounded_rectangle(shadowBox, radius=radius + 4, fill=(0, 0, 0, shadowAlpha))
        self.draw.rounded_rectangle(
            (x, y, x + width, y + height),
            radius=radius,
            fill=self.withAlpha(fill, 245),
            outline=self.withAlpha(self.borderColor, 220),
            width=4
        )
        self.draw.rounded_rectangle(
            (x + 18, y + 18, x + width - 18, y + height - 18),
            radius=max(18, radius - 18),
            outline=self.withAlpha(self.blendColor(fill, accent, 0.3), 90),
            width=2
        )
        self.draw.rounded_rectangle(
            (x + 32, y + 26, x + width - 32, y + 44),
            radius=9,
            fill=self.withAlpha(accent, 185)
        )

    def drawChip(self, x, y, text, fill=None, textColor=None, font=None, paddingX=26, paddingY=16):
        font = font or self.getFont("semibold", 34)
        fill = fill or self.withAlpha(self.surfaceRaisedColor, 220)
        textColor = textColor or self.bodyColor
        bbox = self.draw.textbbox((0, 0), text, font=font)
        width = bbox[2] - bbox[0] + paddingX * 2
        height = bbox[3] - bbox[1] + paddingY * 2
        self.draw.rounded_rectangle(
            (x, y, x + width, y + height),
            radius=height // 2,
            fill=fill,
            outline=self.withAlpha(textColor, 70),
            width=2
        )
        self.draw.text((x + paddingX, y + paddingY - 2), text, fill=textColor, font=font)
        return width, height

    def drawMetricChip(self, x, y, label, value, accent=None):
        accent = self.toRgb(accent or self.primarySoftColor)
        labelFont = self.getFont("semibold", 28)
        valueFont = self.getFont("semibold", 42)
        label = str(label).upper()
        value = str(value)

        labelBox = self.draw.textbbox((0, 0), label, font=labelFont)
        valueBox = self.draw.textbbox((0, 0), value, font=valueFont)
        width = max(labelBox[2] - labelBox[0], valueBox[2] - valueBox[0]) + 72
        height = 120

        self.draw.rounded_rectangle(
            (x, y, x + width, y + height),
            radius=36,
            fill=self.withAlpha(self.surfaceRaisedColor, 220),
            outline=self.withAlpha(accent, 120),
            width=3
        )
        self.draw.text((x + 30, y + 18), label, fill=accent, font=labelFont)
        self.draw.text((x + 30, y + 56), value, fill=self.bodyColor, font=valueFont)
        return width

    def drawSectionHeader(self, x, y, width, title, subtitle=None, meta=None, accent=None, eyebrow=None):
        accent = self.toRgb(accent or self.primaryColor)
        cursorY = y

        if eyebrow:
            _, chipHeight = self.drawChip(
                x,
                cursorY,
                eyebrow,
                fill=self.withAlpha(self.tintedSurface(accent, 0.12), 210),
                textColor=accent,
                font=self.getFont("semibold", 30),
                paddingX=20,
                paddingY=12
            )
            cursorY += chipHeight + 28

        titleFont = self.getFont("semibold", 84)
        self.draw.text((x, cursorY), title, fill=self.bodyColor, font=titleFont)

        if meta:
            metaFont = self.getFont("medium", 48)
            metaBox = self.draw.textbbox((0, 0), meta, font=metaFont)
            metaWidth = metaBox[2] - metaBox[0]
            self.draw.text((x + width - metaWidth, cursorY + 18), meta, fill=accent, font=metaFont)

        if subtitle:
            self.draw.text((x, cursorY + 108), subtitle, fill=self.mutedColor, font=self.getFont("medium", 48))
            return cursorY + 188

        return cursorY + 108

    def getBrandInfo(self):
        try:
            profileName = getCurrentProfile()
        except Exception:
            profileName = None

        try:
            macroVersion = getMacroVersion()
        except Exception:
            macroVersion = None

        return profileName, macroVersion

    def drawBrandCard(self, x, y, width, height):
        self.drawPanel(x, y, width, height, accent=self.primaryColor, fill=self.tintedSurface(self.primaryColor, 0.08))

        iconBox = (x + 48, y + 66, x + 236, y + 254)
        self.draw.rounded_rectangle(iconBox, radius=56, fill=self.withAlpha(self.surfaceInsetColor, 235))
        macroIcon = Image.open(f"{self.assetPath}/macro_icon.png").convert("RGBA").resize((150, 150), Image.LANCZOS)
        self.canvas.paste(macroIcon, (x + 67, y + 85), macroIcon)

        textX = x + 280
        self.draw.text((textX, y + 74), "Fuzzy Macro", fill=self.bodyColor, font=self.getFont("bold", 88))
        self.draw.text((textX, y + 176), "macro analytics", fill=self.mutedColor, font=self.getFont("medium", 44))

        profileName, macroVersion = self.getBrandInfo()
        chipY = y + height - 110
        chipX = textX
        if profileName:
            chipWidth, _ = self.drawChip(
                chipX,
                chipY,
                f"Profile {profileName}",
                fill=self.withAlpha(self.surfaceInsetColor, 220),
                textColor=self.bodyColor,
                font=self.getFont("semibold", 28),
                paddingX=20,
                paddingY=12
            )
            chipX += chipWidth + 18
        if macroVersion:
            self.drawChip(
                chipX,
                chipY,
                f"v{macroVersion}",
                fill=self.withAlpha(self.surfaceInsetColor, 220),
                textColor=self.primarySoftColor,
                font=self.getFont("semibold", 28),
                paddingX=20,
                paddingY=12
            )

    def drawHeroCard(self, x, y, width, height, eyebrow, title, subtitle, chips=None, accent=None):
        accent = self.toRgb(accent or self.primaryColor)
        self.drawPanel(x, y, width, height, accent=accent, fill=self.tintedSurface(accent, 0.08))
        contentX = x + 64
        contentY = y + 52
        self.drawSectionHeader(contentX, contentY, width - 128, title, subtitle, accent=accent, eyebrow=eyebrow)

        chipX = contentX
        chipY = y + height - 140
        for label, value, chipAccent in chips or []:
            chipX += self.drawMetricChip(chipX, chipY, label, value, chipAccent) + 22

    def getGradientColorAtRatio(self, ratio, gradientSpec):
        #calculates the RGBA color from gradientSpec at a given vertical ratio (0=bottom, 1=top)
        if not gradientSpec:
            return (0, 0, 0, 0) # Default transparent black if no spec

        sorted_stops = sorted(gradientSpec.items()) # list of (position_ratio, color_tuple)

        # Clamp ratio
        ratio = max(0.0, min(1.0, ratio))

        # Find which two stops this ratio is between
        for j in range(len(sorted_stops) - 1):
            pos1, col1 = sorted_stops[j]
            pos2, col2 = sorted_stops[j + 1]
            if pos1 <= ratio <= pos2:
                if pos2 - pos1 == 0:
                    local_ratio = 0
                else:
                    local_ratio = (ratio - pos1) / (pos2 - pos1)

                #interpolate RGBA values
                try:
                    r = int(col1[0] + (col2[0] - col1[0]) * local_ratio)
                    g = int(col1[1] + (col2[1] - col1[1]) * local_ratio)
                    b = int(col1[2] + (col2[2] - col1[2]) * local_ratio)
                    #handle alpha
                    a = 255 
                    if len(col1) > 3 and len(col2) > 3:
                            a = int(col1[3] + (col2[3] - col1[3]) * local_ratio)
                    elif len(col1) > 3:
                        a = col1[3]
                    elif len(col2) > 3:
                        a = col2[3]

                    return (r, g, b, a)
                except IndexError:
                    print(f"Warning: Color tuple length mismatch in gradientSpec between {col1} and {col2}")
                    return (0,0,0,255)

        # If ratio is below the first stop or above the last stop (should not happen with clamping)
        if ratio < sorted_stops[0][0]:
            return sorted_stops[0][1] # Return first color
        else:
            return sorted_stops[-1][1] # Return last color


    def drawGraph(self, graphX, graphY, width, height, xData, datasets, maxY = None, showXAxisLabels=True, showYAxisLabels=True, ticks=5, yLabelFunc=None, xLabelFunc=None):
        # Validate data lengths
        for dataset in datasets:
            data = dataset["data"]
            #pad the data
            data = [0]*(len(xData) - len(data)) + data
        
            # Prevent division by zero with minimal data
            xInterval = width / max(len(data) - 1, 1)
            if not maxY:
                maxY = max(data) if data else 1
                if not maxY:
                    maxY = 1
            else:
                data = [maxY if y > maxY else y for y in data]

            font = self.getFont("medium", 48)
            fontColor = self.mutedColor
            gridColor = self.gridColor
            #draw xaxis
            if showXAxisLabels:
                for i, val in enumerate(xData):
                    val = xLabelFunc(i, val) if xLabelFunc else val
                    if val:
                        val = str(val)
                        #get the text width, so the text can be centered with the x axis point
                        bbox = self.draw.textbbox((0, 0), val, font=font)
                        textWidth = bbox[2] - bbox[0]
                        self.draw.text((graphX+xInterval*i - textWidth/2, graphY+24), val, font=font, fill= fontColor)
            
            #draw y labels and y grid
            #calculating ticks
            yInterval = height/max(ticks-1, 1)
            yValInterval = maxY/max(ticks-1, 1)

            for i in range(ticks):
                y = graphY - yInterval*i
                if showYAxisLabels:
                    text = yValInterval*i
                    text = yLabelFunc(i, text) if yLabelFunc else text
                    if text:
                        text = str(text)
                        bbox = self.draw.textbbox((0, 0), text, font=font)
                        textWidth = bbox[2] - bbox[0]
                        textHeight = bbox[3] - bbox[1]
                        self.draw.text((graphX - textWidth - 90, y - textHeight/2), text, font=font, fill= fontColor)
                self.draw.line((graphX-24, y, graphX+24+width, y), fill=gridColor, width=3)


            # Collect curve points
            points = []
            for i, val in enumerate(data):
                px = graphX + i * xInterval
                py = graphY - (val / maxY * height)
                points.append((px, py))
            # Close polygon at bottom
            points.append((graphX + (len(xData) - 1) * xInterval, graphY))
            points.append((graphX, graphY))

            #make gradient
            gradientSpec = dataset.get("gradientFill", None)
            gradient = Image.new('RGBA', (int(width), int(height)), (0, 0, 0, 0))
            if gradientSpec:
                gradient = Image.new('RGBA', (int(width), int(height)), (0, 0, 0, 0))
                grad_draw = ImageDraw.Draw(gradient)
                sorted_stops = sorted(gradientSpec.items())  # list of (position, color)

                for i in range(height):
                    # Normalize position (0 to 1)
                    ratio = i / float(max(height - 1, 1))

                    # Find which two stops this ratio is between
                    for j in range(len(sorted_stops) - 1):
                        pos1, col1 = sorted_stops[j]
                        pos2, col2 = sorted_stops[j + 1]
                        if pos1 <= ratio <= pos2:
                            local_ratio = (ratio - pos1) / (pos2 - pos1)
                            r = int(col1[0] + (col2[0] - col1[0]) * local_ratio)
                            g = int(col1[1] + (col2[1] - col1[1]) * local_ratio)
                            b = int(col1[2] + (col2[2] - col1[2]) * local_ratio)
                            a = int(col1[3] + (col2[3] - col1[3]) * local_ratio)
                            grad_draw.line([(0, height - i), (width, height - i)], fill=(r, g, b, a))
                            break
                

            #create a mask with polygon in the shape of the graph
            mask = Image.new('L', (int(width), int(height)), 0)
            mask_draw = ImageDraw.Draw(mask)
            rel_pts = [(px - graphX, py - (graphY - height)) for px, py in points]
            mask_draw.polygon(rel_pts, fill=255)

            #paste the gradient and mask onto the canvas
            self.canvas.paste(gradient, (graphX, graphY - height), mask)

            lineColor = dataset["lineColor"]
            #gradient color.
            if gradientSpec and lineColor == "gradient":
                #draw the line
                for i in range(len(points) - 3):
                    #Since line doesnt accept gradients, we will break the line down into segments, 
                    #and assign each segment a color
                    x0, y0 = points[i]
                    x1, y1 = points[i+1]

                    #calculate length of the line
                    dx = x1 - x0
                    dy = y1 - y0
                    length = math.sqrt(dx*dx + dy*dy)

                    if length == 0: continue # Skip zero-length segments

                    #get the number of segments
                    segmentCount = max(1, int(length / 10))

                    for k in range(segmentCount):
                        t0 = k / segmentCount
                        t1 = (k + 1) / segmentCount

                        sub_x0 = x0 + dx * t0
                        sub_y0 = y0 + dy * t0
                        sub_x1 = x0 + dx * t1
                        sub_y1 = y0 + dy * t1
                        mid_y = (sub_y0 + sub_y1) / 2.0
                        # Convert Y coord to ratio (0=bottom, 1=top)
                        mid_yRatio = (graphY - mid_y) / height if height > 0 else 0.0

                        # Get color for this ratio
                        r, g, b, a = self.getGradientColorAtRatio(mid_yRatio, gradientSpec)

                        self.draw.line(
                            (int(sub_x0), int(sub_y0), int(sub_x1), int(sub_y1)),
                            fill=(r, g, b), # Use opaque RGB for line
                            width=8
                        )

            else:
                # Draw the entire line with a solid color
                # Use points[:len(data)] to only draw line over actual data points, not polygon closing points
                self.draw.line(points[:len(data)], fill=lineColor, width=8, joint="curve")

    def drawDoughnutChart(self, x, y, size, datasets, holeRatio = 0.6):

        total = sum([x["data"] for x in datasets])
        if not total:
            total = 1
        angleStart = -90
        chartArea = (x, y, x+size, y+size)

        #draw the section
        for dataset in datasets:
            angleEnd = angleStart + (dataset["data"] / total) * 360
            self.draw.pieslice(chartArea, angleStart, angleEnd, fill=dataset["color"])
            angleStart = angleEnd

        #draw the hole
        if holeRatio > 0:
            hole_size = int(size * holeRatio)
            offset = (size - hole_size) // 2
            hole_bbox = (x+offset, y+offset, x+offset + hole_size, y+offset + hole_size)
            self.draw.ellipse(hole_bbox, fill=self.withAlpha(self.surfaceInsetColor, 255))

    def drawProgressChart(self, x, y, size, percentage, color, holeRatio = 0.6,):
        chartArea = (x, y, x+size, y+size)
        color = self.toRgb(color)

        #draw the section
        self.draw.pieslice(chartArea, -90, 360, fill=self.withAlpha(color, 72))
        self.draw.pieslice(chartArea, -90, (int(percentage) / 100) * 360 - 90, fill=color)

        #draw the hole
        if holeRatio > 0:
            hole_size = int(size * holeRatio)
            offset = (size - hole_size) // 2
            hole_bbox = (x+offset, y+offset, x+offset + hole_size, y+offset + hole_size)
            self.draw.ellipse(hole_bbox, fill=self.withAlpha(self.surfaceInsetColor, 255))

        font = self.getFont("semibold", 56)
        text = f"{int(percentage)}%"
        text_bbox = self.draw.textbbox((0, 0), text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        self.draw.text((x + (size - text_width) // 2, y + (size - text_height) // 2 - 10), text, fill=self.bodyColor, font=font)

    def drawStatCard(self, x, y, statImage, statValue, statTitle, fontColor = None, imageColor = None, cardWidth=780, cardHeight=430):
        accent = self.toRgb(imageColor or fontColor or self.primaryColor)
        valueColor = self.toRgb(fontColor or self.bodyColor)
        self.drawPanel(x, y, cardWidth, cardHeight, accent=accent, fill=self.tintedSurface(accent, 0.08), radius=52, shadowAlpha=58)

        iconBox = (x + 44, y + 42, x + 176, y + 174)
        self.draw.rounded_rectangle(iconBox, radius=38, fill=self.withAlpha(self.surfaceInsetColor, 225))
        #load the image 
        img = Image.open(f"{self.assetPath}/{statImage}.png").convert("RGBA")
        width, height = img.size
        imageHeight = 96
        imageWidth = int(width*(imageHeight/height))
        img = img.resize((imageWidth, imageHeight))
        
        #recolor the image
        if accent:
            r, g, b = accent
            pixels = img.load()
            for i in range(img.width):
                for j in range(img.height):
                    _, _, _, a = pixels[i, j]
                    if a > 0:  #only recolor non-transparent pixels
                        pixels[i, j] = (r,g,b, a)

        self.canvas.paste(img, (x + 44 + (132 - imageWidth)//2, y + 42 + (132 - imageHeight)//2), img)

        valueFont = self.getFont("semibold", 76)
        titleFont = self.getFont("medium", 42)
        self.draw.text((x + 48, y + 206), str(statValue), font=valueFont, fill=valueColor)
        self.draw.text((x + 48, y + 312), statTitle, font=titleFont, fill=self.mutedColor, spacing=8)

    def drawBuffUptimeGraphStackableBuff(self, y, datasets, imageName, xData=None, xLabelFunc=None):
        #draw the graph
        graphHeight = 420
        graphXStart = self.leftPadding + 430
        if xData is None:
            maxLen = max((len(dataset.get("data", [])) for dataset in datasets), default=0)
            xData = list(range(maxLen if maxLen else 1))
        self.drawGraph(graphXStart, y, self.availableSpace-570, graphHeight, xData, datasets, maxY=10, showXAxisLabels=bool(xLabelFunc), showYAxisLabels=False, ticks=3, xLabelFunc=xLabelFunc)

        #load the icon
        imageDimension = 132
        imageX = graphXStart - 228 - imageDimension
        imageY = y - graphHeight//2 - imageDimension//2 + 28
        self.draw.rounded_rectangle(
            (imageX - 22, imageY - 22, imageX + imageDimension + 22, imageY + imageDimension + 22),
            radius=36,
            fill=self.withAlpha(self.surfaceRaisedColor, 220),
            outline=self.withAlpha(self.borderColor, 120),
            width=3
        )
        img = Image.open(f"{self.assetPath}/{imageName}.png").convert("RGBA")
        img = img.resize((imageDimension, imageDimension))
        self.canvas.paste(img, (imageX, imageY), img)

        self.draw.text((imageX - 8, imageY + imageDimension + 32), "x0-10", font=self.getFont("semibold", 42), fill=self.subtleColor)

        for i, dataset in enumerate(datasets):
            labelY = imageY - (92 + 74*i)
            self.drawChip(
                imageX - 10,
                labelY,
                dataset["average"],
                fill=self.withAlpha(dataset["lineColor"], 34),
                textColor=dataset["lineColor"],
                font=self.getFont("semibold", 30),
                paddingX=16,
                paddingY=10
            )

    def drawBuffUptimeGraphUnstackableBuff(self, y, datasets, imageName, renderTime = False, xData=None, xLabelFunc=None):

        def transformXLabel(i, val):
            if i%100:
                return
            val //= 10
            hour = self.hour
            if val == 60:
                hour += 1
                if hour == 24:
                    hour = 0
                val = 0
            return f"{str(hour).zfill(2)}:{str(val).zfill(2)}"

        #draw the graph
        graphHeight = 220
        graphXStart = self.leftPadding + 430
        if xData is None:
            maxLen = max((len(dataset.get("data", [])) for dataset in datasets), default=0)
            xData = list(range(maxLen if maxLen else 1))
        labelFunc = xLabelFunc if xLabelFunc else transformXLabel
        self.drawGraph(graphXStart, y, self.availableSpace-570, graphHeight, xData, datasets, maxY=1, showXAxisLabels=renderTime or bool(xLabelFunc), showYAxisLabels=False, ticks=2, xLabelFunc=labelFunc)

        #load the icon
        imageDimension = 118
        imageX = graphXStart - 220 - imageDimension
        imageY = y - graphHeight//2 - imageDimension//2 + 18
        self.draw.rounded_rectangle(
            (imageX - 22, imageY - 22, imageX + imageDimension + 22, imageY + imageDimension + 22),
            radius=34,
            fill=self.withAlpha(self.surfaceRaisedColor, 220),
            outline=self.withAlpha(self.borderColor, 120),
            width=3
        )
        img = Image.open(f"{self.assetPath}/{imageName}.png").convert("RGBA")
        img = img.resize((imageDimension, imageDimension))
        self.canvas.paste(img, (imageX, imageY), img)

    def drawSessionStat(self, y, imageName, label, value, valueColor):
        sectionX = self.sidebarX + getattr(self, "sidebarInnerInset", 0)
        sectionWidth = getattr(self, "sidebarContentWidth", self.sidebarWidth - self.sidebarPadding * 2)
        rowHeight = 178
        imgContainerDimension = 120
        accent = self.toRgb(valueColor)

        self.draw.rounded_rectangle(
            (sectionX, y, sectionX + sectionWidth, y + rowHeight),
            radius=42,
            fill=self.withAlpha(self.surfaceRaisedColor, 210),
            outline=self.withAlpha(self.borderColor, 110),
            width=3
        )
        self.draw.rounded_rectangle(
            (sectionX + 28, y + 28, sectionX + 28 + imgContainerDimension, y + 28 + imgContainerDimension),
            radius=32,
            fill=self.withAlpha(self.surfaceInsetColor, 235)
        )
        img = Image.open(f"{self.assetPath}/{imageName}.png").convert("RGBA")
        width, height = img.size
        imageWidth = 76
        imageHeight = int(height*(imageWidth/width))
        img = img.resize((imageWidth, imageHeight))
        self.canvas.paste(
            img,
            (sectionX + 28 + (imgContainerDimension-imageWidth)//2, y + 28 + (imgContainerDimension-imageHeight)//2),
            img
        )

        labelFont = self.getFont("medium", 42)
        valueFont = self.getFont("semibold", 54)
        textX = sectionX + 180
        self.draw.text((textX, y + 40), label, self.mutedColor, font=labelFont)
        bbox = self.draw.textbbox((0, 0), value, font=valueFont)
        textWidth = bbox[2] - bbox[0]
        self.draw.text((sectionX + sectionWidth - textWidth - 30, y + 90), str(value), accent, font=valueFont)

    def drawTaskTimes(self, y, datasets, totalTime=None):
        legendIconDimension = 68
        labelFont = self.getFont("medium", 48)
        valueFont = self.getFont("semibold", 48)
        x = self.sidebarX + getattr(self, "sidebarInnerInset", 0)
        sectionWidth = getattr(self, "sidebarContentWidth", self.sidebarWidth - self.sidebarPadding * 2)
        totalData = totalTime if totalTime is not None else sum([x["data"] for x in datasets])
        if not totalData:
            totalData = 1

        for dataset in datasets:
            color = self.toRgb(dataset["color"])
            percentText = f"{round(dataset['data']/totalData*100, 1)}%"
            timeText = self.displayTime(dataset["data"])

            self.draw.rounded_rectangle(
                (x, y, x + sectionWidth, y + 112),
                radius=34,
                fill=self.withAlpha(self.surfaceRaisedColor, 200),
                outline=self.withAlpha(color, 60),
                width=2
            )
            self.draw.rounded_rectangle((x + 24, y + 22, x + 24 + legendIconDimension, y + 22 + legendIconDimension), fill=color, radius=22)
            self.draw.text((x + legendIconDimension + 54, y + 18), dataset["label"], self.bodyColor, font=labelFont)

            percentBox = self.draw.textbbox((0, 0), percentText, font=valueFont)
            percentWidth = percentBox[2] - percentBox[0]
            percentX = x + sectionWidth - percentWidth - 30
            self.draw.text((percentX, y + 30), percentText, self.mutedColor, font=valueFont)

            timeBox = self.draw.textbbox((0, 0), timeText, font=valueFont)
            timeWidth = timeBox[2] - timeBox[0]
            timeX = percentX - timeWidth - 60
            self.draw.text((timeX, y + 30), timeText, color, font=valueFont)
            y += 136

        y += 100
        doughnutChartSize = 500
        chartX = x + (sectionWidth - doughnutChartSize) // 2
        self.drawDoughnutChart(chartX, y, doughnutChartSize, datasets, holeRatio=0.44)

    def drawPlanters(self, y, planterNames, planterTimes, planterFields):
        fieldNectarIcons = {
            "sunflower": "satisfying",
            "dandelion": "comforting",
            "mushroom": "motivating",
            "blue flower": "refreshing",
            "clover": "invigorating",
            "strawberry": "refreshing",
            "spider": "motivating",
            "bamboo": "comforting",
            "pineapple": "satisfying",
            "stump": "motivating",
            "cactus": "invigorating",
            "pumpkin": "satisfying",
            "pine tree": "comforting",
            "rose": "motivating",
            "mountain top": "invigorating",
            "pepper": "invigorating",
            "coconut": "refreshing"
        }

        planterX = self.sidebarX + getattr(self, "sidebarInnerInset", 0)
        sectionWidth = getattr(self, "sidebarContentWidth", self.sidebarWidth - self.sidebarPadding * 2)
        fieldFont = self.getFont("semibold", 68)
        timeFont = self.getFont("semibold", 55)
        cardWidth = (sectionWidth - 40) // 2
        cardHeight = 520
        for i in range(len(planterNames)):
            if not planterNames[i]:
                continue
            col = i % 2
            row = i // 2
            cardX = planterX + col * (cardWidth + 40)
            cardY = y + row * (cardHeight + 36)
            bbox = self.draw.textbbox((0, 0), planterFields[i].title(), font=fieldFont)
            fieldTextWidth = bbox[2] - bbox[0]

            nectarImg = Image.open(f'{self.assetPath}/{fieldNectarIcons[planterFields[i]]}.png')
            width, height = nectarImg.size
            nectarImageHeight = bbox[3] - bbox[1]
            nectarImageWidth = int(width*(nectarImageHeight/height))
            nectarImg = nectarImg.resize((nectarImageWidth, nectarImageHeight))

            fieldAndNectarWidth = fieldTextWidth + nectarImageWidth + 30

            img = Image.open(f'{self.assetPath}/{planterNames[i].replace(" ","_")}_planter.png')
            width, height = img.size
            imageHeight = 250
            imageWidth = int(width*(imageHeight/height))
            img = img.resize((imageWidth, imageHeight))

            timeText = self.displayTime(planterTimes[i], ["h", "m"]) if planterTimes[i] > 0 else "Ready!"
            bbox = self.draw.textbbox((0, 0), timeText, font=timeFont)
            timeTextWidth = bbox[2] - bbox[0]

            maxWidth = max(fieldAndNectarWidth, imageWidth, timeTextWidth)
            self.draw.rounded_rectangle(
                (cardX, cardY, cardX + cardWidth, cardY + cardHeight),
                radius=42,
                fill=self.withAlpha(self.surfaceRaisedColor, 210),
                outline=self.withAlpha(self.borderColor, 110),
                width=3
            )
            self.canvas.paste(img, (cardX + (cardWidth-imageWidth)//2, cardY + 40), img)
            self.draw.text((cardX + (cardWidth - fieldAndNectarWidth)//2, cardY + 312), planterFields[i].title(), font=fieldFont, fill=self.bodyColor) 
            self.canvas.paste(nectarImg, (cardX + (cardWidth - fieldAndNectarWidth)//2 + fieldTextWidth + 30, cardY + 327), nectarImg)
            self.draw.text((cardX + (cardWidth - timeTextWidth)//2, cardY + 416), timeText, font=timeFont, fill=self.mutedColor)

        rows = max(1, math.ceil(len(planterNames) / 2)) if planterNames else 0
        return rows * cardHeight + max(0, rows - 1) * 36

    def drawBuffs(self, y, buffData):
        buffImages = ["tabby_love_buff", "polar_power_buff", "wealth_clock_buff", "blessing_buff", "bloat_buff"]

        font = self.getFont("bold", 58)
        baseX = self.sidebarX + getattr(self, "sidebarInnerInset", 0)
        sectionWidth = getattr(self, "sidebarContentWidth", self.sidebarWidth - self.sidebarPadding * 2)
        gap = 24
        imageWidth = (sectionWidth - gap * 4) // 5
        for i in range(len(buffData)):
            buff = str(buffData[i]) #I cant make up my mind on if buffData should switch to ints or remain as string
            x = baseX + (imageWidth + gap) * i
            cardHeight = imageWidth + 54

            img = Image.open(f"{self.assetPath}/{buffImages[i]}.png").convert("RGBA")
            width, height = img.size
            imageHeight= int(width*(imageWidth/height))
            img = img.resize((imageWidth, imageHeight))

            if buff == "0":
                #dim the image
                overlay = Image.new("RGBA", img.size, (0, 0, 0, 100))
            else:
                overlay = Image.new("RGBA", img.size, (0, 0, 0, 20))
            img = Image.alpha_composite(img, overlay)
            self.draw.rounded_rectangle(
                (x, y, x + imageWidth, y + cardHeight),
                radius=32,
                fill=self.withAlpha(self.surfaceRaisedColor, 210),
                outline=self.withAlpha(self.borderColor, 110),
                width=2
            )
            self.canvas.paste(img, (x, y + 8), img)

            if buff != "0":
                buffText = f"x{buff}"
                bbox = self.draw.textbbox((0, 0), buffText, font=font, stroke_width=4)
                textWidth = bbox[2] - bbox[0]
                textHeight = 58
                self.draw.text((x + imageWidth - textWidth - 12, y + imageHeight - textHeight - 10), buffText, fill=self.bodyColor, font=font, stroke_width=4, stroke_fill=(0,0,0))

    def drawNectars(self, y, nectarData):
        nectarColors = [(165, 207, 234), (235, 120, 108), (194, 166, 236), (162, 239, 163), (239, 205, 224)]
        nectarNames = ["comforting", "invigorating", "motivating", "refreshing", "satisfying"]
        progressChartSize = 228
        imageHeight = 92
        baseX = self.sidebarX + getattr(self, "sidebarInnerInset", 0)
        gap = 26
        for i in range(len(nectarData)):
            x = baseX + i*(progressChartSize+gap)
            self.draw.rounded_rectangle(
                (x, y, x + progressChartSize, y + progressChartSize + 180),
                radius=36,
                fill=self.withAlpha(self.surfaceRaisedColor, 210),
                outline=self.withAlpha(self.borderColor, 100),
                width=2
            )
            self.drawProgressChart(x, y, progressChartSize, nectarData[i], nectarColors[i], 0.75)

            img = Image.open(f"{self.assetPath}/{nectarNames[i]}.png").convert("RGBA")
            width, height = img.size
            imageWidth = int(width*(imageHeight/height))
            img = img.resize((imageWidth, imageHeight))
            self.canvas.paste(img, (x + (progressChartSize-imageWidth)//2, y+progressChartSize + 50), img)

    def drawHourlyReport(self, hourlyReportStats, sessionTime, honeyPerMin, sessionHoney, honeyThisHour, onlyValidHourlyHoney, buffQuantity, nectarQuantity, planterData, uptimeBuffsValues, buffGatherIntervals, enabled_fields=None, field_patterns=None):

        def getAverageBuff(buffValues):
            #get the buff average when gathering, rounded to 2p
            count = 0
            total = 0
            for i, e in enumerate(buffGatherIntervals):
                if e:
                    total += buffValues[i]
                    count += 1

            res = total/count if count else 0

            return f"x{res:.2f}"

        self.beginReportCanvas()

        mins = list(range(61))
        avgHoneyPerHour = max(0, sessionHoney/(sessionTime/3600)) if sessionTime > 0 else 0
        peakHourlyRate = max(honeyPerMin) if honeyPerMin else 0

        self.sidebarPadding = 85
        self.sidebarX = self.canvasSize[0] - self.sidebarWidth + self.sidebarPadding
        self.sidebarPanelWidth = self.sidebarWidth - self.sidebarPadding * 2
        self.sidebarInnerInset = 46
        self.sidebarContentWidth = self.sidebarPanelWidth - self.sidebarInnerInset * 2

        heroY = 80
        heroHeight = 350
        self.drawHeroCard(
            self.leftPadding,
            heroY,
            self.availableSpace,
            heroHeight,
            "HOURLY REPORT",
            "Past Hour In Focus",
            "Past hour performance, surfaced in the Fuzzy Macro palette.",
            [
                ("Avg / hr", self.millify(avgHoneyPerHour), self.primarySoftColor),
                ("Honey", self.millify(honeyThisHour), self.honeyColor),
                ("Peak", f"{self.millify(peakHourlyRate)}/s", self.secondaryAccentColor),
            ],
            accent=self.primaryColor
        )
        self.drawBrandCard(self.sidebarX, heroY, self.sidebarPanelWidth, heroHeight)

        #section 1: hourly stats
        y = 470
        cardGap = 28
        cardWidth = int((self.availableSpace - cardGap * 4) / 5)
        self.drawStatCard(self.leftPadding, y, "average_icon", self.millify(avgHoneyPerHour), "Average Honey\nPer Hour", cardWidth=cardWidth)
        self.drawStatCard(self.leftPadding + (cardWidth + cardGap) * 1, y, "honey_icon", self.millify(honeyThisHour), "Honey Made\nThis Hour", self.honeyColor, self.honeyColor, cardWidth=cardWidth)
        self.drawStatCard(self.leftPadding + (cardWidth + cardGap) * 2, y, "kill_icon", hourlyReportStats["bugs"], "Bugs Killed\nThis Hour", (254,101,99), (254,101,99), cardWidth=cardWidth)
        self.drawStatCard(self.leftPadding + (cardWidth + cardGap) * 3, y, "quest_icon", hourlyReportStats["quests_completed"], "Quests Completed\nThis Hour", (103,253,153), (103,253,153), cardWidth=cardWidth)
        self.drawStatCard(self.leftPadding + (cardWidth + cardGap) * 4, y, "vicious_bee_icon", hourlyReportStats["vicious_bees"], "Vicious Bees\nThis Hour", (132,233,254), (132,233,254), cardWidth=cardWidth)

        #section 2: honey/min
        y = 980
        panelWidth = self.availableSpace
        self.drawPanel(self.leftPadding, y, panelWidth, 1120, accent=self.honeyColor, fill=self.tintedSurface(self.primaryColor, 0.1))
        self.drawSectionHeader(
            self.leftPadding + 60,
            y + 56,
            panelWidth - 120,
            "Honey / Sec",
            "Minute-by-minute collection rate across the last completed hour.",
            meta=f"Peak {self.millify(peakHourlyRate)}/s",
            accent=self.honeyColor
        )
        dataset = [{
            "data": honeyPerMin,
            "lineColor": self.primarySoftColor,
            "gradientFill": {
                0: (*self.primarySoftColor, 18),
                0.6: (*self.primaryColor, 70),
                1: (*self.honeyColor, 140)
            }
        }]
        self.drawGraph(self.leftPadding + 430, y + 960, self.availableSpace - 540, 700, mins, dataset, xLabelFunc=self.transformXLabelTime, yLabelFunc=lambda i, x: self.millify(x))

        #section 3: backpack
        y = 2160
        self.drawPanel(self.leftPadding, y, panelWidth, 1120, accent=self.primaryColor, fill=self.tintedSurface(self.primaryColor, 0.08))
        self.drawSectionHeader(
            self.leftPadding + 60,
            y + 56,
            panelWidth - 120,
            "Backpack Utilization",
            "Storage pressure over the hour so spikes are easy to spot.",
            meta="0-100%",
            accent=self.primarySoftColor
        )
        dataset = [{
            "data": hourlyReportStats["backpack_per_min"],
            "lineColor": "gradient",
            "gradientFill": {
                0: (65, 255, 128, 90),
                0.6: (201, 163, 36, 90),
                0.9: (255, 65, 84, 90),
                1: (255, 65, 84, 90),
            }
        }]
        self.drawGraph(self.leftPadding + 430, y + 960, self.availableSpace - 540, 700, mins, dataset, maxY=100, xLabelFunc=self.transformXLabelTime, yLabelFunc=lambda i, x: f"{int(x)}%")

        #section 4: buff uptime
        y = 3340
        self.drawPanel(self.leftPadding, y, panelWidth, 4300, accent=self.secondaryAccentColor, fill=self.tintedSurface(self.secondaryAccentColor, 0.06))
        self.drawSectionHeader(
            self.leftPadding + 60,
            y + 56,
            panelWidth - 120,
            "Buff Uptime",
            "Stackable averages while gathering, followed by binary buff coverage.",
            meta="Past hour",
            accent=self.secondaryAccentColor
        )
        y += 620
        dataset = [
        {
            "data": uptimeBuffsValues["blue_boost"],
            "lineColor": (77,147,193),
            "average": getAverageBuff(uptimeBuffsValues["blue_boost"]),
            "gradientFill": {
                0: (77,147,193,10),
                1: (77,147,193,120),
            }
        },
        {
            "data": uptimeBuffsValues["red_boost"],
            "lineColor": (200,90,80),
            "average": getAverageBuff(uptimeBuffsValues["red_boost"]),
            "gradientFill": {
                0: (200,90,80,10),
                1: (200,90,80,120),
            }
        },
        {
            "data": uptimeBuffsValues["white_boost"],
            "lineColor": (220,220,220),
            "average": getAverageBuff(uptimeBuffsValues["white_boost"]),
            "gradientFill": {
                0: (220,220,220,10),
                1: (220,220,220,120),
            }
        }
        ]
        self.drawBuffUptimeGraphStackableBuff(y, dataset, "boost_buff")

        y += 460
        dataset = [
        {
            "data": uptimeBuffsValues["haste"],
            "lineColor": (210,210,210),
            "average": getAverageBuff(uptimeBuffsValues["haste"]),
            "gradientFill": {
                0: (210,210,210,10),
                1: (210,210,210,120),
            }
        }
        ]
        self.drawBuffUptimeGraphStackableBuff(y, dataset, "haste_buff")

        y += 460
        dataset = [
        {
            "data": uptimeBuffsValues["focus"],
            "lineColor": (30,191,5),
            "average": getAverageBuff(uptimeBuffsValues["focus"]),
            "gradientFill": {
                0: (30,191,5,10),
                1: (30,191,5,120),
            }
        }
        ]
        self.drawBuffUptimeGraphStackableBuff(y, dataset, "focus_buff")

        y += 460
        dataset = [
        {
            "data": uptimeBuffsValues["bomb_combo"],
            "lineColor": (160,160,160),
            "average": getAverageBuff(uptimeBuffsValues["bomb_combo"]),
            "gradientFill": {
                0: (160,160,160,10),
                1: (160,160,160,120),
            }
        }
        ]
        self.drawBuffUptimeGraphStackableBuff(y, dataset, "bomb_combo_buff")

        y += 460
        dataset = [
        {
            "data": uptimeBuffsValues["balloon_aura"],
            "lineColor": (50,80,200),
            "average": getAverageBuff(uptimeBuffsValues["balloon_aura"]),
            "gradientFill": {
                0: (50,80,200,10),
                1: (50,80,200,120),
            }
        }
        ]
        self.drawBuffUptimeGraphStackableBuff(y, dataset, "balloon_aura_buff")

        y += 460
        dataset = [
        {
            "data": uptimeBuffsValues["inspire"],
            "lineColor": (195,191,18),
            "average": getAverageBuff(uptimeBuffsValues["inspire"]),
            "gradientFill": {
                0: (195,191,18,10),
                1: (195,191,18,120),
            }
        }
        ]
        self.drawBuffUptimeGraphStackableBuff(y, dataset, "inspire_buff")

        y += 260
        dataset = [
        {
            "data": uptimeBuffsValues["melody"],
            "lineColor": (200,200,200),
            "gradientFill": {
                0: (200,200,200,255),
                1: (200,200,200,255),
            }
        }
        ]
        self.drawBuffUptimeGraphUnstackableBuff(y, dataset, "melody_buff")

        y += 260
        dataset = [
        {
            "data": uptimeBuffsValues["bear"],
            "lineColor": (115,71,40),
            "gradientFill": {
                0: (115,71,40,255),
                1: (115,71,40,255),
            }
        }
        ]
        self.drawBuffUptimeGraphUnstackableBuff(y, dataset, "bear_buff")

        y += 260
        dataset = [
        {
            "data": uptimeBuffsValues["baby_love"],
            "lineColor": (112,181,195),
            "gradientFill": {
                0: (112,181,195,255),
                1: (112,181,195,255),
            }
        }
        ]
        self.drawBuffUptimeGraphUnstackableBuff(y, dataset, "baby_love_buff", renderTime=True)

        #side bar 

        #session stats

        y2 = 470
        currentHoney = onlyValidHourlyHoney[-1] if onlyValidHourlyHoney else 0
        self.drawPanel(self.sidebarX, y2, self.sidebarPanelWidth, 860, accent=self.primaryColor, fill=self.tintedSurface(self.primaryColor, 0.08))
        self.drawSectionHeader(self.sidebarX + 50, y2 + 44, self.sidebarPanelWidth - 100, "Session Snapshot", "Current run totals outside the hourly slice.", accent=self.primarySoftColor)
        y2 += 198
        self.drawSessionStat(y2, "time_icon", "Session Time", self.displayTime(sessionTime, ['d','h','m']), self.bodyColor)
        y2 += 206
        self.drawSessionStat(y2, "honey_icon", "Current Honey", self.millify(currentHoney), self.honeyColor)
        y2 += 206
        self.drawSessionStat(y2, "session_honey_icon", "Session Honey", self.millify(sessionHoney), "#FDE395")

        #task times
        y2 += 300
        self.drawPanel(self.sidebarX, y2, self.sidebarPanelWidth, 1360, accent=self.secondaryAccentColor, fill=self.tintedSurface(self.secondaryAccentColor, 0.06))
        self.drawSectionHeader(self.sidebarX + 50, y2 + 44, self.sidebarPanelWidth - 100, "Task Breakdown", "How the macro spent the last hour.", accent=self.secondaryAccentColor)
        y2 += 194
        self.drawTaskTimes(y2, [
            {
                "label": "Gathering",
                "data": hourlyReportStats["gathering_time"],
                "color": self.primarySoftColor
            },
            {
                "label": "Converting",
                "data": hourlyReportStats["converting_time"],
                "color": self.honeyColor
            },
            {
                "label": "Bug Run",
                "data": hourlyReportStats["bug_run_time"],
                "color": self.secondaryAccentColor
            },
            {
                "label": "Other",
                "data": hourlyReportStats["misc_time"],
                "color": "#6C5B4E"
            },
            

        ])

        #planters
        y2 += 1220
        #check if there are planters
        planterNames = [] #planterData["planters"]
        planterTimes = [] #[x-time.time() for x in planterData["harvestTimes"]]
        planterFields = [] #planterData["fields"]
        if planterData:
            for i in range(len(planterData["planters"])):
                if planterData["planters"][i]:
                    planterNames.append(planterData["planters"][i])
                    planterTimes.append(planterData["harvestTimes"][i] - time.time())
                    planterFields.append(planterData["fields"][i])
        if planterNames:
            planterRows = max(1, math.ceil(len(planterNames) / 2))
            planterHeight = planterRows * 520 + max(0, planterRows - 1) * 36
            self.drawPanel(self.sidebarX, y2, self.sidebarPanelWidth, planterHeight + 250, accent=self.primaryColor, fill=self.tintedSurface(self.primaryColor, 0.07))
            self.drawSectionHeader(self.sidebarX + 50, y2 + 44, self.sidebarPanelWidth - 100, "Planters", "Current placements and ready times.", accent=self.primaryColor)
            self.drawPlanters(y2 + 188, planterNames, planterTimes, planterFields)
            y2 += planterHeight + 290
        
        #buffs
        self.drawPanel(self.sidebarX, y2, self.sidebarPanelWidth, 360, accent=self.secondaryAccentColor, fill=self.tintedSurface(self.secondaryAccentColor, 0.05))
        self.drawSectionHeader(self.sidebarX + 50, y2 + 44, self.sidebarPanelWidth - 100, "Buffs", "Latest captured stack values.", accent=self.secondaryAccentColor)
        self.drawBuffs(y2 + 150, buffQuantity)

        #nectars
        y2 += 430
        self.drawPanel(self.sidebarX, y2, self.sidebarPanelWidth, 520, accent=self.honeyColor, fill=self.tintedSurface(self.honeyColor, 0.05))
        self.drawSectionHeader(self.sidebarX + 50, y2 + 44, self.sidebarPanelWidth - 100, "Nectars", "Field nectar percentages at render time.", accent=self.honeyColor)
        self.drawNectars(y2 + 162, nectarQuantity)

        # Fields: show enabled fields and the pattern used
        if enabled_fields is None:
            enabled_fields = []
        if field_patterns is None:
            field_patterns = {}

        if enabled_fields:
            y2 += 590
            fieldPanelHeight = 210 + len(enabled_fields) * 112
            self.drawPanel(self.sidebarX, y2, self.sidebarPanelWidth, fieldPanelHeight, accent=self.primarySoftColor, fill=self.tintedSurface(self.primaryColor, 0.05))
            self.drawSectionHeader(self.sidebarX + 50, y2 + 44, self.sidebarPanelWidth - 100, "Fields", "Enabled fields and their active patterns.", accent=self.primarySoftColor)

            cur_y = y2 + 178
            field_font = self.getFont("medium", 44)
            pattern_font = self.getFont("regular", 36)
            rowX = self.sidebarX + self.sidebarInnerInset
            rowWidth = self.sidebarContentWidth
            for fname in enabled_fields:
                pattern = field_patterns.get(fname, "unknown")
                self.draw.rounded_rectangle(
                    (rowX, cur_y, rowX + rowWidth, cur_y + 86),
                    radius=28,
                    fill=self.withAlpha(self.surfaceRaisedColor, 205),
                    outline=self.withAlpha(self.borderColor, 100),
                    width=2
                )
                self.draw.text((rowX + 24, cur_y + 18), fname.title(), font=field_font, fill=self.bodyColor)
                bbox = self.draw.textbbox((0, 0), pattern, font=pattern_font)
                textWidth = bbox[2] - bbox[0]
                self.draw.text((rowX + rowWidth - 24 - textWidth, cur_y + 24), pattern, fill=self.mutedColor, font=pattern_font)
                cur_y += 100

        return self.canvas
