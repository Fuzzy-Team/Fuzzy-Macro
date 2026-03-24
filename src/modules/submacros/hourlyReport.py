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
        self.hourlyQuestCompletions = []
        self.sessionQuestCompletions = []
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

    def recordQuestCompletion(self, questTitle=None, questGiver=None):
        questTitle = str(questTitle or "").strip()
        questGiver = str(questGiver or "").strip()

        if questTitle and questGiver:
            label = f"{questGiver.title()}: {questTitle}"
        elif questTitle:
            label = questTitle
        elif questGiver:
            label = f"{questGiver.title()} Quest"
        else:
            label = "Quest Completed"

        self.hourlyQuestCompletions.append(label)
        self.sessionQuestCompletions.append(label)
        self.saveHourlyReportData()

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
                                                          getattr(self, "hourlyQuestCompletions", []),
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
        self.hourlyQuestCompletions = []

        self.saveHourlyReportData()
    
    def resetAllStats(self):
        self.hourlyReportStats["start_time"] = 0
        self.hourlyReportStats["start_honey"] = 0
        self.sessionReportStats = self._defaultSessionReportStats()
        self.sessionUptimeBuffsValues = self._defaultSessionUptimeBuffs()
        self.sessionBuffGatherIntervals = []
        self.hourlyQuestCompletions = []
        self.sessionQuestCompletions = []
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
                "hourlyQuestCompletions": self.hourlyQuestCompletions,
                "sessionQuestCompletions": self.sessionQuestCompletions,
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
            self.hourlyQuestCompletions = data.get("hourlyQuestCompletions", [])
            self.sessionQuestCompletions = data.get("sessionQuestCompletions", [])
            self.latestBuffQuantity = data.get("latestBuffQuantity", [])
            self.latestNectarQuantity = data.get("latestNectarQuantity", [])


class HourlyReportDrawer:
    def __init__(self, time_format=24):
        # New modern color scheme - warmer, more vibrant with better contrast
        self.backgroundColor = (18, 16, 14, 255)
        self.backgroundTopColor = (22, 19, 17)
        self.backgroundBottomColor = (32, 27, 24)
        self.surfaceColor = (38, 32, 28)
        self.surfaceRaisedColor = (52, 44, 38)
        self.surfaceInsetColor = (26, 22, 19)
        self.borderColor = (95, 78, 65)
        self.innerBorderColor = (145, 118, 95)
        self.primaryColor = (195, 145, 110)
        self.primarySoftColor = (225, 175, 135)
        self.honeyColor = (255, 215, 125)
        self.secondaryAccentColor = (175, 155, 210)
        self.bodyColor = (250, 245, 238)
        self.mutedColor = (175, 160, 145)
        self.subtleColor = (130, 115, 102)
        self.gridColor = (75, 62, 52)
        
        # New canvas dimensions - wider aspect ratio for modern feel
        self.canvasSize = (6600, 7200)
        self.sidebarWidth = 1650
        self.leftPadding = 120
        self.availableSpace = self.canvasSize[0] - self.sidebarWidth - self.leftPadding*2
        self.time_format = time_format
        self.fontScale = 1.0
        self.hour = datetime.now().hour
        self.sideBarBackground = (28, 24, 21)
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
        scaledSize = max(1, int(round(fontSize * self.fontScale)))
        return ImageFont.truetype(f"hourly_report/Inter/static/Inter_18pt-{weight.title()}.ttf", scaledSize)

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
        
        # Smoother gradient with more steps
        for y in range(self.canvasSize[1]):
            ratio = y / max(self.canvasSize[1] - 1, 1)
            # Subtle noise texture simulation through slight color variation
            color = self.blendColor(self.backgroundTopColor, self.backgroundBottomColor, ratio)
            gradientDraw.line((0, y, self.canvasSize[0], y), fill=self.withAlpha(color, 255))

        # Modern geometric accent overlay
        overlay = Image.new("RGBA", self.canvasSize, (0, 0, 0, 0))
        overlayDraw = ImageDraw.Draw(overlay)
        
        # Top-left warm glow
        overlayDraw.ellipse((-800, -400, 2200, 1600), fill=self.withAlpha(self.honeyColor, 18))
        # Top-right subtle accent
        overlayDraw.ellipse((3800, -200, 6800, 1400), fill=self.withAlpha(self.primaryColor, 12))
        # Bottom-right secondary accent
        overlayDraw.ellipse((4200, 5200, 7200, 7800), fill=self.withAlpha(self.secondaryAccentColor, 10))
        # Bottom-left subtle honey glow
        overlayDraw.ellipse((-400, 4800, 1400, 7200), fill=self.withAlpha(self.honeyColor, 8))
        
        # Top highlight bar for depth
        overlayDraw.rectangle((0, 0, self.canvasSize[0], 280), fill=self.withAlpha((255, 255, 255), 6))
        
        overlay = overlay.filter(ImageFilter.GaussianBlur(220))

        self.canvas = Image.alpha_composite(base, overlay)
        self.draw = ImageDraw.Draw(self.canvas)

    def drawPanel(self, x, y, width, height, accent=None, fill=None, radius=48, shadowAlpha=60):
        accent = self.toRgb(accent or self.primaryColor)
        fill = self.toRgb(fill or self.surfaceColor)

        # Softer, more modern shadow
        shadowBox = (x + 8, y + 12, x + width + 8, y + height + 12)
        self.draw.rounded_rectangle(shadowBox, radius=radius + 2, fill=(0, 0, 0, shadowAlpha))
        
        # Main panel with refined border
        self.draw.rounded_rectangle(
            (x, y, x + width, y + height),
            radius=radius,
            fill=self.withAlpha(fill, 248),
            outline=self.withAlpha(self.borderColor, 180),
            width=2
        )
        
        # Inner subtle glow border
        self.draw.rounded_rectangle(
            (x + 12, y + 12, x + width - 12, y + height - 12),
            radius=max(16, radius - 12),
            outline=self.withAlpha(self.blendColor(fill, accent, 0.22), 60),
            width=2
        )
        
        # Modern accent line at top
        self.draw.rounded_rectangle(
            (x + 30, y + 24, x + width - 30, y + 32),
            radius=4,
            fill=self.withAlpha(accent, 200)
        )

    def drawChip(self, x, y, text, fill=None, textColor=None, font=None, paddingX=24, paddingY=14):
        font = font or self.getFont("semibold", 32)
        fill = fill or self.withAlpha(self.surfaceRaisedColor, 230)
        textColor = textColor or self.bodyColor
        bbox = self.draw.textbbox((0, 0), text, font=font)
        width = bbox[2] - bbox[0] + paddingX * 2
        height = bbox[3] - bbox[1] + paddingY * 2
        self.draw.rounded_rectangle(
            (x, y, x + width, y + height),
            radius=height // 2,
            fill=fill,
            outline=self.withAlpha(textColor, 55),
            width=1
        )
        self.draw.text((x + paddingX, y + paddingY - 2), text, fill=textColor, font=font)
        return width, height

    def drawMetricChip(self, x, y, label, value, accent=None):
        accent = self.toRgb(accent or self.primarySoftColor)
        labelFont = self.getFont("semibold", 26)
        valueFont = self.getFont("semibold", 40)
        label = str(label).upper()
        value = str(value)

        labelBox = self.draw.textbbox((0, 0), label, font=labelFont)
        valueBox = self.draw.textbbox((0, 0), value, font=valueFont)
        width = max(labelBox[2] - labelBox[0], valueBox[2] - valueBox[0]) + 64
        height = 108

        self.draw.rounded_rectangle(
            (x, y, x + width, y + height),
            radius=32,
            fill=self.withAlpha(self.surfaceRaisedColor, 235),
            outline=self.withAlpha(accent, 100),
            width=2
        )
        self.draw.text((x + 28, y + 16), label, fill=accent, font=labelFont)
        self.draw.text((x + 28, y + 52), value, fill=self.bodyColor, font=valueFont)
        return width

    def drawSectionHeader(self, x, y, width, title, subtitle=None, meta=None, accent=None, eyebrow=None):
        accent = self.toRgb(accent or self.primaryColor)
        cursorY = y

        if eyebrow:
            _, chipHeight = self.drawChip(
                x,
                cursorY,
                eyebrow,
                fill=self.withAlpha(self.tintedSurface(accent, 0.15), 220),
                textColor=accent,
                font=self.getFont("semibold", 28),
                paddingX=18,
                paddingY=10
            )
            cursorY += chipHeight + 24

        titleFont = self.getFont("semibold", 62)
        self.draw.text((x, cursorY), title, fill=self.bodyColor, font=titleFont)

        if meta:
            metaFont = self.getFont("medium", 36)
            metaBox = self.draw.textbbox((0, 0), meta, font=metaFont)
            metaWidth = metaBox[2] - metaBox[0]
            self.draw.text((x + width - metaWidth, cursorY + 8), meta, fill=accent, font=metaFont)

        if subtitle:
            self.draw.text((x, cursorY + 78), subtitle, fill=self.mutedColor, font=self.getFont("medium", 34))
            return cursorY + 140

        return cursorY + 76

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
        self.drawPanel(x, y, width, height, accent=self.primaryColor, fill=self.tintedSurface(self.primaryColor, 0.06))

        iconBox = (x + 42, y + 54, x + 198, y + 210)
        self.draw.rounded_rectangle(iconBox, radius=48, fill=self.withAlpha(self.surfaceInsetColor, 240))
        macroIcon = Image.open(f"{self.assetPath}/macro_icon.png").convert("RGBA").resize((130, 130), Image.LANCZOS)
        self.canvas.paste(macroIcon, (x + 55, y + 67), macroIcon)

        textX = x + 230
        self.draw.text((textX, y + 62), "Fuzzy Macro", fill=self.bodyColor, font=self.getFont("bold", 72))
        self.draw.text((textX, y + 148), "report dashboard", fill=self.mutedColor, font=self.getFont("medium", 34))

        profileName, macroVersion = self.getBrandInfo()
        chipY = y + height - 95
        chipX = textX
        if profileName:
            chipWidth, _ = self.drawChip(
                chipX,
                chipY,
                f"Profile {profileName}",
                fill=self.withAlpha(self.surfaceInsetColor, 230),
                textColor=self.bodyColor,
                font=self.getFont("semibold", 26),
                paddingX=18,
                paddingY=10
            )
            chipX += chipWidth + 16
        if macroVersion:
            self.drawChip(
                chipX,
                chipY,
                f"v{macroVersion}",
                fill=self.withAlpha(self.surfaceInsetColor, 230),
                textColor=self.primarySoftColor,
                font=self.getFont("semibold", 26),
                paddingX=18,
                paddingY=10
            )

    def drawHeroCard(self, x, y, width, height, eyebrow, title, subtitle, chips=None, accent=None):
        accent = self.toRgb(accent or self.primaryColor)
        self.drawPanel(x, y, width, height, accent=accent, fill=self.tintedSurface(accent, 0.05), radius=52)
        contentX = x + 56
        contentY = y + 46
        self.drawSectionHeader(contentX, contentY, width - 112, title, subtitle, accent=accent, eyebrow=eyebrow)

        chipX = contentX
        chipY = y + height - 108
        for label, value, chipAccent in chips or []:
            chipX += self.drawMetricChip(chipX, chipY, label, value, chipAccent) + 20

    def drawOverviewCards(self, x, y, width, items, columns=4, cardHeight=260):
        if not items:
            return 0

        gap = 24
        cardWidth = (width - gap * (columns - 1)) // columns
        labelFont = self.getFont("medium", 28)
        valueFont = self.getFont("bold", 56)
        metaFont = self.getFont("medium", 26)

        for i, item in enumerate(items[:columns]):
            accent = self.toRgb(item.get("color", self.primaryColor))
            cardX = x + i * (cardWidth + gap)
            iconName = item.get("icon")
            self.drawPanel(cardX, y, cardWidth, cardHeight, accent=accent, fill=self.tintedSurface(accent, 0.06), radius=40, shadowAlpha=40)

            # Modern icon container
            self.draw.rounded_rectangle(
                (cardX + 24, y + 28, cardX + 128, y + 132),
                radius=26,
                fill=self.withAlpha(self.surfaceInsetColor, 240)
            )

            if iconName:
                try:
                    img = Image.open(f"{self.assetPath}/{iconName}.png").convert("RGBA")
                    widthRaw, heightRaw = img.size
                    imageHeight = 68
                    imageWidth = int(widthRaw * (imageHeight / max(heightRaw, 1)))
                    img = img.resize((imageWidth, imageHeight), Image.LANCZOS)
                    self.canvas.paste(
                        img,
                        (cardX + 76 - imageWidth // 2, y + 80 - imageHeight // 2),
                        img
                    )
                except Exception:
                    pass

            label = str(item.get("label", "")).upper()
            value = str(item.get("value", "0"))
            meta = str(item.get("meta", "")).strip()
            self.draw.text((cardX + 148, y + 36), label, fill=self.mutedColor, font=labelFont)
            self.draw.text((cardX + 24, y + 142), value, fill=self.bodyColor, font=valueFont)
            if meta:
                self.draw.text((cardX + 24, y + 212), meta, fill=accent, font=metaFont)

        return cardHeight

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
        pointCount = len(xData) if xData else max((len(dataset.get("data", [])) for dataset in datasets), default=1)
        pointCount = max(pointCount, 1)
        if not xData:
            xData = list(range(pointCount))

        normalizedDatasets = []
        derivedMaxY = 0
        for dataset in datasets:
            data = list(dataset.get("data", []))
            if len(data) < pointCount:
                data = [0] * (pointCount - len(data)) + data
            elif len(data) > pointCount:
                data = data[-pointCount:]
            derivedMaxY = max(derivedMaxY, max(data) if data else 0)
            normalized = dataset.copy()
            normalized["data"] = data
            normalizedDatasets.append(normalized)

        if maxY is None:
            maxY = derivedMaxY or 1
        else:
            maxY = max(maxY, 1)
            for dataset in normalizedDatasets:
                dataset["data"] = [min(maxY, value) for value in dataset["data"]]

        xInterval = width / max(pointCount - 1, 1)
        font = self.getFont("medium", 36)
        fontColor = self.mutedColor
        gridColor = self.withAlpha(self.gridColor, 160)

        # Modern graph container with softer styling
        self.draw.rounded_rectangle(
            (graphX, graphY - height, graphX + width, graphY),
            radius=28,
            fill=self.withAlpha(self.surfaceInsetColor, 250),
            outline=self.withAlpha(self.borderColor, 70),
            width=1
        )

        xDivisions = min(6, max(pointCount - 1, 1))
        for division in range(xDivisions + 1):
            x = graphX + width * division / max(xDivisions, 1)
            self.draw.line((x, graphY - height, x, graphY), fill=self.withAlpha(self.gridColor, 70), width=1)

        yInterval = height / max(ticks - 1, 1)
        yValInterval = maxY / max(ticks - 1, 1)
        for i in range(ticks):
            y = graphY - yInterval * i
            if showYAxisLabels:
                text = yValInterval * i
                text = yLabelFunc(i, text) if yLabelFunc else text
                if text is not None:
                    text = str(text)
                    bbox = self.draw.textbbox((0, 0), text, font=font)
                    textWidth = bbox[2] - bbox[0]
                    textHeight = bbox[3] - bbox[1]
                    self.draw.text((graphX - textWidth - 60, y - textHeight / 2), text, font=font, fill=fontColor)
            self.draw.line((graphX, y, graphX + width, y), fill=gridColor, width=1)

        if showXAxisLabels:
            labelIndices = []
            for division in range(xDivisions + 1):
                idx = round((pointCount - 1) * division / max(xDivisions, 1))
                if idx not in labelIndices:
                    labelIndices.append(idx)
            for idx in labelIndices:
                labelValue = xData[idx] if idx < len(xData) else idx
                labelText = xLabelFunc(idx, labelValue) if xLabelFunc else labelValue
                if labelText is None:
                    continue
                labelText = str(labelText)
                bbox = self.draw.textbbox((0, 0), labelText, font=font)
                textWidth = bbox[2] - bbox[0]
                self.draw.text((graphX + xInterval * idx - textWidth / 2, graphY + 18), labelText, font=font, fill=fontColor)

        for dataset in normalizedDatasets:
            data = dataset["data"]
            points = []
            for i, val in enumerate(data):
                px = graphX + i * xInterval
                py = graphY - (val / maxY * height)
                points.append((px, py))

            polygonPoints = points + [
                (graphX + (pointCount - 1) * xInterval, graphY),
                (graphX, graphY)
            ]

            gradientSpec = dataset.get("gradientFill", None)
            if gradientSpec:
                gradient = Image.new('RGBA', (int(width), int(height)), (0, 0, 0, 0))
                gradDraw = ImageDraw.Draw(gradient)
                sortedStops = sorted(gradientSpec.items())

                for i in range(height):
                    ratio = i / float(max(height - 1, 1))
                    for j in range(len(sortedStops) - 1):
                        pos1, col1 = sortedStops[j]
                        pos2, col2 = sortedStops[j + 1]
                        if pos1 <= ratio <= pos2:
                            localRatio = (ratio - pos1) / max(pos2 - pos1, 1e-9)
                            r = int(col1[0] + (col2[0] - col1[0]) * localRatio)
                            g = int(col1[1] + (col2[1] - col1[1]) * localRatio)
                            b = int(col1[2] + (col2[2] - col1[2]) * localRatio)
                            a = int(col1[3] + (col2[3] - col1[3]) * localRatio)
                            gradDraw.line([(0, height - i), (width, height - i)], fill=(r, g, b, a))
                            break

                mask = Image.new('L', (int(width), int(height)), 0)
                maskDraw = ImageDraw.Draw(mask)
                relativePoints = [(px - graphX, py - (graphY - height)) for px, py in polygonPoints]
                maskDraw.polygon(relativePoints, fill=255)
                self.canvas.paste(gradient, (graphX, graphY - height), mask)

            lineColor = dataset["lineColor"]
            if gradientSpec and lineColor == "gradient":
                for i in range(len(points) - 1):
                    x0, y0 = points[i]
                    x1, y1 = points[i + 1]
                    dx = x1 - x0
                    dy = y1 - y0
                    length = math.sqrt(dx * dx + dy * dy)
                    if length == 0:
                        continue

                    segmentCount = max(1, int(length / 10))
                    for k in range(segmentCount):
                        t0 = k / segmentCount
                        t1 = (k + 1) / segmentCount
                        subX0 = x0 + dx * t0
                        subY0 = y0 + dy * t0
                        subX1 = x0 + dx * t1
                        subY1 = y0 + dy * t1
                        midY = (subY0 + subY1) / 2.0
                        midYRatio = (graphY - midY) / height if height > 0 else 0.0
                        r, g, b, _ = self.getGradientColorAtRatio(midYRatio, gradientSpec)
                        self.draw.line((int(subX0), int(subY0), int(subX1), int(subY1)), fill=(r, g, b), width=5)
            else:
                self.draw.line(points, fill=lineColor, width=5, joint="curve")

    def drawDoughnutChart(self, x, y, size, datasets, holeRatio = 0.58):

        total = sum([x["data"] for x in datasets])
        if not total:
            total = 1
        angleStart = -90
        chartArea = (x, y, x+size, y+size)

        # Draw the sections with smoother edges
        for dataset in datasets:
            angleEnd = angleStart + (dataset["data"] / total) * 360
            self.draw.pieslice(chartArea, angleStart, angleEnd, fill=dataset["color"])
            angleStart = angleEnd

        # Draw the hole with subtle border
        if holeRatio > 0:
            hole_size = int(size * holeRatio)
            offset = (size - hole_size) // 2
            hole_bbox = (x+offset, y+offset, x+offset + hole_size, y+offset + hole_size)
            self.draw.ellipse(hole_bbox, fill=self.withAlpha(self.surfaceInsetColor, 255))
            # Inner ring accent
            inner_ring_bbox = (x+offset+4, y+offset+4, x+offset + hole_size-4, y+offset + hole_size-4)
            self.draw.ellipse(inner_ring_bbox, outline=self.withAlpha(self.borderColor, 50), width=1)

    def drawProgressChart(self, x, y, size, percentage, color, holeRatio = 0.58):
        chartArea = (x, y, x+size, y+size)
        color = self.toRgb(color)

        # Draw background ring with softer opacity
        self.draw.pieslice(chartArea, -90, 360, fill=self.withAlpha(color, 55))
        # Draw progress with slightly rounded feel via antialiasing effect
        self.draw.pieslice(chartArea, -90, (int(percentage) / 100) * 360 - 90, fill=color)

        # Draw the hole
        if holeRatio > 0:
            hole_size = int(size * holeRatio)
            offset = (size - hole_size) // 2
            hole_bbox = (x+offset, y+offset, x+offset + hole_size, y+offset + hole_size)
            self.draw.ellipse(hole_bbox, fill=self.withAlpha(self.surfaceInsetColor, 255))

        font = self.getFont("semibold", 52)
        text = f"{int(percentage)}%"
        text_bbox = self.draw.textbbox((0, 0), text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        self.draw.text((x + (size - text_width) // 2, y + (size - text_height) // 2 - 8), text, fill=self.bodyColor, font=font)

    def drawStatCard(self, x, y, statImage, statValue, statTitle, fontColor = None, imageColor = None, cardWidth=720, cardHeight=390):
        accent = self.toRgb(imageColor or fontColor or self.primaryColor)
        valueColor = self.toRgb(fontColor or self.bodyColor)
        self.drawPanel(x, y, cardWidth, cardHeight, accent=accent, fill=self.tintedSurface(accent, 0.06), radius=44, shadowAlpha=45)

        iconBox = (x + 38, y + 36, x + 156, y + 154)
        self.draw.rounded_rectangle(iconBox, radius=32, fill=self.withAlpha(self.surfaceInsetColor, 235))
        #load the image 
        img = Image.open(f"{self.assetPath}/{statImage}.png").convert("RGBA")
        width, height = img.size
        imageHeight = 88
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

        self.canvas.paste(img, (x + 38 + (118 - imageWidth)//2, y + 36 + (118 - imageHeight)//2), img)

        valueFont = self.getFont("semibold", 68)
        titleFont = self.getFont("medium", 38)
        self.draw.text((x + 42, y + 186), str(statValue), font=valueFont, fill=valueColor)
        self.draw.text((x + 42, y + 282), statTitle, font=titleFont, fill=self.mutedColor, spacing=7)

    def drawBuffUptimeGraphStackableBuff(self, y, datasets, imageName, xData=None, xLabelFunc=None):
        # Modern graph styling
        graphHeight = 380
        graphXStart = self.leftPadding + 380
        if xData is None:
            maxLen = max((len(dataset.get("data", [])) for dataset in datasets), default=0)
            xData = list(range(maxLen if maxLen else 1))
        self.drawGraph(graphXStart, y, self.availableSpace-500, graphHeight, xData, datasets, maxY=10, showXAxisLabels=bool(xLabelFunc), showYAxisLabels=False, ticks=3, xLabelFunc=xLabelFunc)

        # Modern icon container
        imageDimension = 118
        imageX = graphXStart - 200 - imageDimension
        imageY = y - graphHeight//2 - imageDimension//2 + 24
        self.draw.rounded_rectangle(
            (imageX - 18, imageY - 18, imageX + imageDimension + 18, imageY + imageDimension + 18),
            radius=32,
            fill=self.withAlpha(self.surfaceRaisedColor, 225),
            outline=self.withAlpha(self.borderColor, 100),
            width=2
        )
        
        # Inner glow
        self.draw.rounded_rectangle(
            (imageX - 8, imageY - 8, imageX + imageDimension + 8, imageY + imageDimension + 8),
            radius=26,
            outline=self.withAlpha(self.borderColor, 40),
            width=1
        )
        
        img = Image.open(f"{self.assetPath}/{imageName}.png").convert("RGBA")
        img = img.resize((imageDimension, imageDimension))
        self.canvas.paste(img, (imageX, imageY), img)

        self.draw.text((imageX - 6, imageY + imageDimension + 26), "x0-10", font=self.getFont("semibold", 38), fill=self.subtleColor)

        # Modern average chips
        for i, dataset in enumerate(datasets):
            labelX = graphXStart - 150
            labelY = y - graphHeight // 2 + 18 + i * 62
            self.drawChip(
                labelX,
                labelY,
                dataset["average"],
                fill=self.withAlpha(dataset["lineColor"], 28),
                textColor=dataset["lineColor"],
                font=self.getFont("semibold", 26),
                paddingX=14,
                paddingY=8
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

        # Modern graph styling
        graphHeight = 200
        graphXStart = self.leftPadding + 380
        if xData is None:
            maxLen = max((len(dataset.get("data", [])) for dataset in datasets), default=0)
            xData = list(range(maxLen if maxLen else 1))
        labelFunc = xLabelFunc if xLabelFunc else transformXLabel
        self.drawGraph(graphXStart, y, self.availableSpace-500, graphHeight, xData, datasets, maxY=1, showXAxisLabels=renderTime or bool(xLabelFunc), showYAxisLabels=False, ticks=2, xLabelFunc=labelFunc)

        # Modern icon container
        imageDimension = 106
        imageX = graphXStart - 190 - imageDimension
        imageY = y - graphHeight//2 - imageDimension//2 + 16
        self.draw.rounded_rectangle(
            (imageX - 18, imageY - 18, imageX + imageDimension + 18, imageY + imageDimension + 18),
            radius=30,
            fill=self.withAlpha(self.surfaceRaisedColor, 225),
            outline=self.withAlpha(self.borderColor, 100),
            width=2
        )
        
        # Inner glow
        self.draw.rounded_rectangle(
            (imageX - 8, imageY - 8, imageX + imageDimension + 8, imageY + imageDimension + 8),
            radius=24,
            outline=self.withAlpha(self.borderColor, 40),
            width=1
        )
        
        img = Image.open(f"{self.assetPath}/{imageName}.png").convert("RGBA")
        img = img.resize((imageDimension, imageDimension))
        self.canvas.paste(img, (imageX, imageY), img)

    def drawSessionStat(self, y, imageName, label, value, valueColor):
        sectionX = self.sidebarX + getattr(self, "sidebarInnerInset", 0)
        sectionWidth = getattr(self, "sidebarContentWidth", self.sidebarWidth - self.sidebarPadding * 2)
        rowHeight = 210
        imgContainerDimension = 136
        accent = self.toRgb(valueColor)

        # Modern row styling
        self.draw.rounded_rectangle(
            (sectionX, y, sectionX + sectionWidth, y + rowHeight),
            radius=38,
            fill=self.withAlpha(self.surfaceRaisedColor, 215),
            outline=self.withAlpha(self.borderColor, 90),
            width=2
        )
        
        # Inner glow for icon container
        self.draw.rounded_rectangle(
            (sectionX + 26, y + 37, sectionX + 26 + imgContainerDimension, y + 37 + imgContainerDimension),
            radius=32,
            fill=self.withAlpha(self.surfaceInsetColor, 240)
        )
        
        img = Image.open(f"{self.assetPath}/{imageName}.png").convert("RGBA")
        width, height = img.size
        imageWidth = 86
        imageHeight = int(height*(imageWidth/width))
        img = img.resize((imageWidth, imageHeight))
        self.canvas.paste(
            img,
            (sectionX + 26 + (imgContainerDimension-imageWidth)//2, y + 37 + (imgContainerDimension-imageHeight)//2),
            img
        )

        labelFont = self.getFont("medium", 44)
        valueFont = self.getFont("semibold", 58)
        textX = sectionX + 190
        self.draw.text((textX, y + 48), label, self.mutedColor, font=labelFont)
        bbox = self.draw.textbbox((0, 0), value, font=valueFont)
        textWidth = bbox[2] - bbox[0]
        self.draw.text((sectionX + sectionWidth - textWidth - 26, y + 118), str(value), accent, font=valueFont)

    def drawTaskTimes(self, y, datasets, totalTime=None):
        legendIconDimension = 92
        labelFont = self.getFont("medium", 52)
        valueFont = self.getFont("semibold", 54)
        x = self.sidebarX + getattr(self, "sidebarInnerInset", 0)
        sectionWidth = getattr(self, "sidebarContentWidth", self.sidebarWidth - self.sidebarPadding * 2)
        totalData = totalTime if totalTime is not None else sum([x["data"] for x in datasets])
        if not totalData:
            totalData = 1

        for dataset in datasets:
            color = self.toRgb(dataset["color"])
            percentText = f"{round(dataset['data']/totalData*100, 1)}%"
            timeText = self.displayTime(dataset["data"])

            # Modern row styling
            self.draw.rounded_rectangle(
                (x, y, x + sectionWidth, y + 144),
                radius=34,
                fill=self.withAlpha(self.surfaceRaisedColor, 210),
                outline=self.withAlpha(color, 50),
                width=1
            )
            
            # Color indicator pill
            self.draw.rounded_rectangle(
                (x + 22, y + 26, x + 22 + legendIconDimension, y + 26 + legendIconDimension), 
                fill=color, 
                radius=22
            )
            
            self.draw.text((x + legendIconDimension + 58, y + 28), dataset["label"], self.bodyColor, font=labelFont)

            percentBox = self.draw.textbbox((0, 0), percentText, font=valueFont)
            percentWidth = percentBox[2] - percentBox[0]
            percentX = x + sectionWidth - percentWidth - 26
            self.draw.text((percentX, y + 42), percentText, self.mutedColor, font=valueFont)

            timeBox = self.draw.textbbox((0, 0), timeText, font=valueFont)
            timeWidth = timeBox[2] - timeBox[0]
            timeX = percentX - timeWidth - 50
            self.draw.text((timeX, y + 42), timeText, color, font=valueFont)
            y += 170

        y += 140
        doughnutChartSize = 620
        chartX = x + (sectionWidth - doughnutChartSize) // 2
        self.drawDoughnutChart(chartX, y, doughnutChartSize, datasets, holeRatio=0.42)
        return (len(datasets) * 170) + 140 + doughnutChartSize

    def getTaskTimesPanelHeight(self, datasetCount, headerHeight=175, bottomPadding=60):
        rowsHeight = datasetCount * 170
        chartBlockHeight = 140 + 620
        return headerHeight + rowsHeight + chartBlockHeight + bottomPadding

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
        fieldFont = self.getFont("semibold", 66)
        timeFont = self.getFont("semibold", 54)
        cardWidth = (sectionWidth - 28) // 2
        cardHeight = 540
        
        for i in range(len(planterNames)):
            if not planterNames[i]:
                continue
            col = i % 2
            row = i // 2
            cardX = planterX + col * (cardWidth + 28)
            cardY = y + row * (cardHeight + 36)
            bbox = self.draw.textbbox((0, 0), planterFields[i].title(), font=fieldFont)
            fieldTextWidth = bbox[2] - bbox[0]

            nectarImg = Image.open(f'{self.assetPath}/{fieldNectarIcons[planterFields[i]]}.png')
            width, height = nectarImg.size
            nectarImageHeight = bbox[3] - bbox[1]
            nectarImageWidth = int(width*(nectarImageHeight/height))
            nectarImg = nectarImg.resize((nectarImageWidth, nectarImageHeight))

            fieldAndNectarWidth = fieldTextWidth + nectarImageWidth + 26

            img = Image.open(f'{self.assetPath}/{planterNames[i].replace(" ","_")}_planter.png')
            width, height = img.size
            imageHeight = 260
            imageWidth = int(width*(imageHeight/height))
            img = img.resize((imageWidth, imageHeight))

            timeText = self.displayTime(planterTimes[i], ["h", "m"]) if planterTimes[i] > 0 else "Ready!"
            bbox = self.draw.textbbox((0, 0), timeText, font=timeFont)
            timeTextWidth = bbox[2] - bbox[0]

            # Modern card styling
            self.draw.rounded_rectangle(
                (cardX, cardY, cardX + cardWidth, cardY + cardHeight),
                radius=38,
                fill=self.withAlpha(self.surfaceRaisedColor, 215),
                outline=self.withAlpha(self.borderColor, 90),
                width=2
            )
            
            # Inner highlight
            self.draw.rounded_rectangle(
                (cardX + 12, cardY + 12, cardX + cardWidth - 12, cardY + cardHeight - 12),
                radius=30,
                outline=self.withAlpha(self.borderColor, 35),
                width=1
            )
            
            self.canvas.paste(img, (cardX + (cardWidth-imageWidth)//2, cardY + 42), img)
            self.draw.text((cardX + (cardWidth - fieldAndNectarWidth)//2, cardY + 330), planterFields[i].title(), font=fieldFont, fill=self.bodyColor) 
            self.canvas.paste(nectarImg, (cardX + (cardWidth - fieldAndNectarWidth)//2 + fieldTextWidth + 26, cardY + 345), nectarImg)
            self.draw.text((cardX + (cardWidth - timeTextWidth)//2, cardY + 448), timeText, font=timeFont, fill=self.mutedColor)

        rows = max(1, math.ceil(len(planterNames) / 2)) if planterNames else 0
        return rows * cardHeight + max(0, rows - 1) * 36

    def drawBuffs(self, y, buffData):
        buffImages = ["tabby_love_buff", "polar_power_buff", "wealth_clock_buff", "blessing_buff", "bloat_buff"]

        font = self.getFont("bold", 58)
        baseX = self.sidebarX + getattr(self, "sidebarInnerInset", 0)
        sectionWidth = getattr(self, "sidebarContentWidth", self.sidebarWidth - self.sidebarPadding * 2)
        gap = 22
        cardWidth = (sectionWidth - gap * 4) // 5
        imageWidth = max(110, cardWidth - 20)
        
        for i in range(len(buffData)):
            buff = str(buffData[i])
            x = baseX + (cardWidth + gap) * i
            cardHeight = cardWidth + 84

            img = Image.open(f"{self.assetPath}/{buffImages[i]}.png").convert("RGBA")
            width, height = img.size
            imageHeight= int(width*(imageWidth/height))
            img = img.resize((imageWidth, imageHeight), Image.LANCZOS)

            if buff == "0":
                # Dim the image
                overlay = Image.new("RGBA", img.size, (0, 0, 0, 120))
            else:
                overlay = Image.new("RGBA", img.size, (0, 0, 0, 15))
            img = Image.alpha_composite(img, overlay)
            
            # Modern card styling
            self.draw.rounded_rectangle(
                (x, y, x + cardWidth, y + cardHeight),
                radius=28,
                fill=self.withAlpha(self.surfaceRaisedColor, 215),
                outline=self.withAlpha(self.borderColor, 85),
                width=2
            )
            
            # Inner highlight
            self.draw.rounded_rectangle(
                (x + 8, y + 8, x + cardWidth - 8, y + cardHeight - 8),
                radius=22,
                outline=self.withAlpha(self.borderColor, 30),
                width=1
            )
            
            imageX = x + (cardWidth - imageWidth) // 2
            imageY = y + 16
            self.canvas.paste(img, (imageX, imageY), img)

            if buff != "0":
                buffText = f"x{buff}"
                bbox = self.draw.textbbox((0, 0), buffText, font=font, stroke_width=3)
                textWidth = bbox[2] - bbox[0]
                textHeight = 58
                self.draw.text((x + cardWidth - textWidth - 10, imageY + imageHeight - textHeight + 4), buffText, fill=self.bodyColor, font=font, stroke_width=3, stroke_fill=(0,0,0))

    def drawNectars(self, y, nectarData):
        nectarColors = [(165, 207, 234), (235, 120, 108), (194, 166, 236), (162, 239, 163), (239, 205, 224)]
        nectarNames = ["comforting", "invigorating", "motivating", "refreshing", "satisfying"]
        baseX = self.sidebarX + getattr(self, "sidebarInnerInset", 0)
        sectionWidth = getattr(self, "sidebarContentWidth", self.sidebarWidth - self.sidebarPadding * 2)
        gap = 24
        cardWidth = (sectionWidth - gap * 4) // 5
        progressChartSize = min(220, cardWidth)
        imageHeight = 92
        
        for i in range(len(nectarData)):
            x = baseX + i * (cardWidth + gap)
            
            # Modern card styling
            self.draw.rounded_rectangle(
                (x, y, x + cardWidth, y + progressChartSize + 156),
                radius=32,
                fill=self.withAlpha(self.surfaceRaisedColor, 215),
                outline=self.withAlpha(self.borderColor, 80),
                width=2
            )
            
            # Inner highlight
            self.draw.rounded_rectangle(
                (x + 10, y + 10, x + cardWidth - 10, y + progressChartSize + 156 - 10),
                radius=26,
                outline=self.withAlpha(self.borderColor, 30),
                width=1
            )
            
            chartX = x + (cardWidth - progressChartSize) // 2
            self.drawProgressChart(chartX, y + 8, progressChartSize, nectarData[i], nectarColors[i], 0.72)

            img = Image.open(f"{self.assetPath}/{nectarNames[i]}.png").convert("RGBA")
            width, height = img.size
            imageWidth = int(width*(imageHeight/height))
            img = img.resize((imageWidth, imageHeight), Image.LANCZOS)
            self.canvas.paste(img, (x + (cardWidth - imageWidth)//2, y + progressChartSize + 48), img)

    def getFieldVisuals(self, fieldName):
        normalized = str(fieldName or "").strip().lower()
        fieldAccents = {
            "sunflower": (238, 205, 92),
            "dandelion": (222, 193, 116),
            "mushroom": (202, 92, 92),
            "blue flower": (109, 168, 236),
            "clover": (122, 210, 122),
            "strawberry": (236, 110, 118),
            "spider": (166, 154, 185),
            "bamboo": (117, 201, 160),
            "pineapple": (240, 198, 86),
            "stump": (160, 136, 108),
            "cactus": (112, 199, 135),
            "pumpkin": (228, 138, 82),
            "pine tree": (90, 154, 117),
            "rose": (219, 108, 138),
            "mountain top": (150, 170, 214),
            "pepper": (226, 96, 84),
            "coconut": (184, 174, 156),
        }
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
        parts = [part for part in normalized.replace("-", " ").split() if part]
        initials = ''.join(part[0].upper() for part in parts[:2]) or "F"
        return {
            "accent": fieldAccents.get(normalized, self.primarySoftColor),
            "nectar": fieldNectarIcons.get(normalized),
            "initials": initials,
            "title": normalized.title() if normalized else "Unknown"
        }

    def getFieldsPanelHeight(self, fieldCount):
        rows = max(1, math.ceil(max(fieldCount, 1) / 2))
        return 300 + rows * 180 + max(0, rows - 1) * 26

    def drawFields(self, y, enabled_fields, field_patterns):
        sectionX = self.sidebarX + getattr(self, "sidebarInnerInset", 0)
        sectionWidth = getattr(self, "sidebarContentWidth", self.sidebarWidth - self.sidebarPadding * 2)
        cardGap = 24
        cardWidth = (sectionWidth - cardGap) // 2
        cardHeight = 178
        labelFont = self.getFont("semibold", 36)
        metaFont = self.getFont("medium", 24)
        patternFont = self.getFont("semibold", 28)

        for i, fieldName in enumerate(enabled_fields):
            visuals = self.getFieldVisuals(fieldName)
            pattern = str(field_patterns.get(fieldName, "unknown")).replace("_", " ")
            cardX = sectionX + (i % 2) * (cardWidth + cardGap)
            cardY = y + (i // 2) * (cardHeight + 26)
            accent = self.toRgb(visuals["accent"])

            # Modern field card
            self.draw.rounded_rectangle(
                (cardX, cardY, cardX + cardWidth, cardY + cardHeight),
                radius=30,
                fill=self.withAlpha(self.surfaceRaisedColor, 220),
                outline=self.withAlpha(accent, 80),
                width=2
            )
            
            # Inner glow
            self.draw.rounded_rectangle(
                (cardX + 14, cardY + 14, cardX + cardWidth - 14, cardY + cardHeight - 14),
                radius=24,
                outline=self.withAlpha(self.blendColor(self.surfaceRaisedColor, accent, 0.22), 65),
                width=2
            )

            # Modern icon container
            iconBox = (cardX + 22, cardY + 22, cardX + 108, cardY + 108)
            self.draw.rounded_rectangle(iconBox, radius=24, fill=self.withAlpha(accent, 215))
            initialBox = self.draw.textbbox((0, 0), visuals["initials"], font=self.getFont("bold", 34))
            initialWidth = initialBox[2] - initialBox[0]
            initialHeight = initialBox[3] - initialBox[1]
            self.draw.text(
                (cardX + 65 - initialWidth // 2, cardY + 63 - initialHeight // 2 - 4),
                visuals["initials"],
                fill=self.backgroundColor,
                font=self.getFont("bold", 34)
            )

            nectarIcon = visuals.get("nectar")
            if nectarIcon:
                try:
                    nectarImg = Image.open(f"{self.assetPath}/{nectarIcon}.png").convert("RGBA")
                    nectarImg = nectarImg.resize((36, 36), Image.LANCZOS)
                    self.canvas.paste(nectarImg, (cardX + 84, cardY + 82), nectarImg)
                except Exception:
                    pass

            textX = cardX + 126
            rightInset = 22
            self.draw.text((textX, cardY + 34), visuals["title"], fill=self.bodyColor, font=labelFont)
            patternLabel = "Pattern"
            patternLabelBox = self.draw.textbbox((0, 0), patternLabel, font=metaFont)
            patternLabelWidth = patternLabelBox[2] - patternLabelBox[0]
            self.draw.text((cardX + cardWidth - rightInset - patternLabelWidth, cardY + 40), patternLabel, fill=self.subtleColor, font=metaFont)

            chipText = pattern.title()
            maxChipWidth = cardWidth - 154
            while chipText:
                chipBox = self.draw.textbbox((0, 0), chipText, font=patternFont)
                chipWidth = chipBox[2] - chipBox[0] + 36
                if chipWidth <= maxChipWidth or len(chipText) <= 6:
                    break
                chipText = chipText[:-4].rstrip() + "..."

            chipBox = self.draw.textbbox((0, 0), chipText, font=patternFont)
            chipWidth = chipBox[2] - chipBox[0] + 36
            chipX = cardX + cardWidth - rightInset - chipWidth
            self.drawChip(
                chipX,
                cardY + 108,
                chipText,
                fill=self.withAlpha(self.tintedSurface(accent, 0.22), 232),
                textColor=accent,
                font=patternFont,
                paddingX=18,
                paddingY=10
            )

        rows = max(1, math.ceil(max(len(enabled_fields), 1) / 2))
        return rows * cardHeight + max(0, rows - 1) * 30

    def truncateText(self, text, font, maxWidth):
        text = str(text or "")
        if not text:
            return text
        if self.draw.textbbox((0, 0), text, font=font)[2] <= maxWidth:
            return text

        ellipsis = "..."
        trimmed = text
        while trimmed:
            candidate = trimmed.rstrip() + ellipsis
            if self.draw.textbbox((0, 0), candidate, font=font)[2] <= maxWidth:
                return candidate
            trimmed = trimmed[:-1]
        return ellipsis

    def getSidebarMetricPanelHeight(self, itemCount, columns=2, headerHeight=175, bottomPadding=56):
        rows = max(1, math.ceil(max(itemCount, 1) / columns))
        return headerHeight + rows * 280 + max(0, rows - 1) * 28 + bottomPadding

    def drawSidebarMetricGrid(self, y, items, columns=2):
        sectionX = self.sidebarX + getattr(self, "sidebarInnerInset", 0)
        sectionWidth = getattr(self, "sidebarContentWidth", self.sidebarWidth - self.sidebarPadding * 2)
        cardGap = 24
        rowGap = 28
        cardWidth = (sectionWidth - cardGap * (columns - 1)) // columns
        cardHeight = 252
        labelFont = self.getFont("medium", 32)
        valueFont = self.getFont("semibold", 54)

        for i, item in enumerate(items):
            accent = self.toRgb(item.get("color", self.primaryColor))
            cardX = sectionX + (i % columns) * (cardWidth + cardGap)
            cardY = y + (i // columns) * (cardHeight + rowGap)

            # Modern card with subtler styling
            self.draw.rounded_rectangle(
                (cardX, cardY, cardX + cardWidth, cardY + cardHeight),
                radius=32,
                fill=self.withAlpha(self.surfaceRaisedColor, 220),
                outline=self.withAlpha(accent, 80),
                width=2
            )
            
            # Inner highlight for depth
            self.draw.rounded_rectangle(
                (cardX + 20, cardY + 20, cardX + 120, cardY + 120),
                radius=24,
                fill=self.withAlpha(self.surfaceInsetColor, 240)
            )

            img = Image.open(f"{self.assetPath}/{item['icon']}.png").convert("RGBA")
            width, height = img.size
            imageHeight = 72
            imageWidth = int(width * (imageHeight / height))
            img = img.resize((imageWidth, imageHeight), Image.LANCZOS)
            self.canvas.paste(
                img,
                (cardX + 70 - imageWidth // 2, cardY + 70 - imageHeight // 2),
                img
            )

            label = self.truncateText(item.get("label", ""), labelFont, cardWidth - 50)
            value = str(item.get("value", "0"))
            self.draw.text((cardX + 22, cardY + 148), label, fill=self.mutedColor, font=labelFont)
            self.draw.text((cardX + 22, cardY + 190), value, fill=accent, font=valueFont)

    def getQuestPanelHeight(self, questCount, headerHeight=188, bottomPadding=56):
        visibleCount = max(1, max(questCount, 0))
        summaryHeight = 180
        rowHeight = 124
        rowGap = 20
        return headerHeight + summaryHeight + 44 + visibleCount * rowHeight + max(0, visibleCount - 1) * rowGap + bottomPadding

    def drawQuestList(self, y, quests, accent=(103, 253, 153), emptyMessage="No quest turn-ins recorded yet."):
        sectionX = self.sidebarX + getattr(self, "sidebarInnerInset", 0)
        sectionWidth = getattr(self, "sidebarContentWidth", self.sidebarWidth - self.sidebarPadding * 2)
        accent = self.toRgb(accent)
        summaryHeight = 180

        self.draw.rounded_rectangle(
            (sectionX, y, sectionX + sectionWidth, y + summaryHeight),
            radius=40,
            fill=self.withAlpha(self.surfaceRaisedColor, 210),
            outline=self.withAlpha(accent, 100),
            width=3
        )
        self.draw.rounded_rectangle(
            (sectionX + 28, y + 30, sectionX + 138, y + 140),
            radius=30,
            fill=self.withAlpha(self.surfaceInsetColor, 235)
        )
        img = Image.open(f"{self.assetPath}/quest_icon.png").convert("RGBA").resize((74, 74), Image.LANCZOS)
        self.canvas.paste(img, (sectionX + 46, y + 48), img)

        labelFont = self.getFont("medium", 32)
        valueFont = self.getFont("semibold", 58)
        countLabel = "Quest Turn-Ins"
        countValue = str(len(quests))
        self.draw.text((sectionX + 170, y + 40), countLabel, fill=self.mutedColor, font=labelFont)
        self.draw.text((sectionX + 170, y + 84), countValue, fill=accent, font=valueFont)

        rowFont = self.getFont("medium", 32)
        badgeFont = self.getFont("semibold", 28)
        rowHeight = 124
        rowGap = 20
        contentY = y + summaryHeight + 44
        visibleQuests = list(quests)[::-1]
        if not visibleQuests:
            visibleQuests = [emptyMessage]

        for i, quest in enumerate(visibleQuests):
            rowY = contentY + i * (rowHeight + rowGap)
            self.draw.rounded_rectangle(
                (sectionX, rowY, sectionX + sectionWidth, rowY + rowHeight),
                radius=34,
                fill=self.withAlpha(self.surfaceRaisedColor, 205),
                outline=self.withAlpha(self.borderColor, 110),
                width=2
            )

            badgeRight = sectionX + 88
            self.draw.rounded_rectangle(
                (sectionX + 20, rowY + 22, badgeRight, rowY + 102),
                radius=24,
                fill=self.withAlpha(self.tintedSurface(accent, 0.25), 235)
            )
            badgeText = str(i + 1) if quests else "-"
            badgeBox = self.draw.textbbox((0, 0), badgeText, font=badgeFont)
            badgeWidth = badgeBox[2] - badgeBox[0]
            badgeHeight = badgeBox[3] - badgeBox[1]
            self.draw.text(
                (sectionX + 54 - badgeWidth / 2, rowY + 62 - badgeHeight / 2 - 4),
                badgeText,
                fill=self.backgroundColor,
                font=badgeFont
            )

            rowText = self.truncateText(quest, rowFont, sectionWidth - 138)
            self.draw.text((sectionX + 112, rowY + 42), rowText, fill=self.bodyColor, font=rowFont)

    def summarizeQuestCompletions(self, quests):
        summary = {}
        for quest in quests or []:
            label = str(quest or "").strip()
            if not label:
                continue

            owner = "Unknown"
            if ":" in label:
                owner = label.split(":", 1)[0].strip()
            elif label.lower().endswith(" quest"):
                owner = label[:-6].strip()

            owner = owner.title() if owner else "Unknown"
            summary[owner] = summary.get(owner, 0) + 1

        preferredOrder = [
            "Brown Bear",
            "Black Bear",
            "Polar Bear",
            "Bucko Bee",
            "Riley Bee",
            "Honey Bee",
        ]
        ordered = []
        for owner in preferredOrder:
            if owner in summary:
                ordered.append((owner, summary.pop(owner)))
        ordered.extend(sorted(summary.items()))
        return ordered

    def getQuestSummaryPanelHeight(self, groupCount, headerHeight=175, bottomPadding=56):
        visibleCount = max(1, max(groupCount, 0))
        summaryHeight = 210
        rowHeight = 140
        rowGap = 22
        return headerHeight + summaryHeight + 46 + visibleCount * rowHeight + max(0, visibleCount - 1) * rowGap + bottomPadding

    def drawQuestSummary(self, y, questGroups, accent=(103, 253, 153), emptyMessage="No quest turn-ins recorded yet."):
        sectionX = self.sidebarX + getattr(self, "sidebarInnerInset", 0)
        sectionWidth = getattr(self, "sidebarContentWidth", self.sidebarWidth - self.sidebarPadding * 2)
        accent = self.toRgb(accent)
        summaryHeight = 210

        # Modern summary card
        self.draw.rounded_rectangle(
            (sectionX, y, sectionX + sectionWidth, y + summaryHeight),
            radius=36,
            fill=self.withAlpha(self.surfaceRaisedColor, 215),
            outline=self.withAlpha(accent, 85),
            width=2
        )
        
        # Inner highlight
        self.draw.rounded_rectangle(
            (sectionX + 24, y + 34, sectionX + 140, y + 150),
            radius=26,
            fill=self.withAlpha(self.surfaceInsetColor, 240)
        )
        
        img = Image.open(f"{self.assetPath}/quest_icon.png").convert("RGBA").resize((82, 82), Image.LANCZOS)
        self.canvas.paste(img, (sectionX + 41, y + 51), img)

        labelFont = self.getFont("medium", 34)
        valueFont = self.getFont("semibold", 64)
        totalCount = sum(count for _, count in questGroups)
        self.draw.text((sectionX + 178, y + 48), "Quest Turn-Ins", fill=self.mutedColor, font=labelFont)
        self.draw.text((sectionX + 178, y + 96), str(totalCount), fill=accent, font=valueFont)

        rowFont = self.getFont("medium", 34)
        valueRowFont = self.getFont("semibold", 38)
        pillFont = self.getFont("semibold", 28)
        rowHeight = 140
        rowGap = 22
        contentY = y + summaryHeight + 46
        visibleGroups = list(questGroups)
        if not visibleGroups:
            visibleGroups = [(emptyMessage, 0)]

        for i, (owner, count) in enumerate(visibleGroups):
            rowY = contentY + i * (rowHeight + rowGap)
            
            # Modern row styling
            self.draw.rounded_rectangle(
                (sectionX, rowY, sectionX + sectionWidth, rowY + rowHeight),
                radius=30,
                fill=self.withAlpha(self.surfaceRaisedColor, 210),
                outline=self.withAlpha(self.borderColor, 90),
                width=1
            )

            pillText = owner if count else "-"
            pillWidth, pillHeight = self.drawChip(
                sectionX + 22,
                rowY + 34,
                self.truncateText(pillText, pillFont, sectionWidth - 250),
                fill=self.withAlpha(self.tintedSurface(accent, 0.22), 240),
                textColor=accent,
                font=pillFont,
                paddingX=16,
                paddingY=9
            )

            if count:
                valueText = str(count)
                valueBox = self.draw.textbbox((0, 0), valueText, font=valueRowFont)
                valueWidth = valueBox[2] - valueBox[0]
                valueX = sectionX + sectionWidth - valueWidth - 26
                self.draw.text((valueX, rowY + 42), valueText, fill=self.bodyColor, font=valueRowFont)
                self.draw.text((valueX - 108, rowY + 50), "done", fill=self.mutedColor, font=rowFont)
            else:
                self.draw.text((sectionX + 22, rowY + pillHeight + 44), owner, fill=self.mutedColor, font=rowFont)

    def _getAverageBuff(self, buffValues, buffGatherIntervals):
        count = 0
        total = 0
        for gatherFlag, buffValue in zip(buffGatherIntervals, buffValues):
            if gatherFlag:
                total += buffValue
                count += 1

        res = total / count if count else 0
        return f"x{res:.2f}"

    def _getBuffSeries(self, uptimeBuffsValues, buffName, defaultLength=600):
        return uptimeBuffsValues.get(buffName, [0] * defaultLength)

    def _drawReportTemplate(self, reportType, hourlyReportStats, primarySeries, sessionHoney, onlyValidHourlyHoney, buffQuantity, nectarQuantity, planterData, uptimeBuffsValues, buffGatherIntervals, questCompletions=None, enabled_fields=None, field_patterns=None, sessionTime=0, honeyThisHour=0, sessionStats=None):
        self.beginReportCanvas()

        questCompletions = questCompletions or []
        enabled_fields = enabled_fields or []
        field_patterns = field_patterns or {}
        sessionStats = sessionStats or {}
        isFinalReport = reportType == "final"

        if isFinalReport:
            sessionTime = sessionStats.get("total_session_time", 0)
            totalHoney = sessionStats.get("total_honey", 0)
            avgHoneyPerHour = sessionStats.get("avg_honey_per_hour", 0)
            peakRate = sessionStats.get("peak_honey_rate", 0)
            dataPoints = len(primarySeries) if primarySeries else 1
            if sessionTime > 0:
                timeInterval = sessionTime / max(dataPoints - 1, 1) if dataPoints > 1 else 60
                mins = [i * timeInterval / 60 for i in range(dataPoints)]
            else:
                mins = list(range(dataPoints))
        else:
            totalHoney = sessionHoney
            avgHoneyPerHour = max(0, sessionHoney / (sessionTime / 3600)) if sessionTime > 0 else 0
            peakRate = max(primarySeries) if primarySeries else 0
            mins = list(range(61))

        buffSampleCount = max(
            max((len(values) for values in uptimeBuffsValues.values()), default=0),
            len(buffGatherIntervals),
            1
        )
        if isFinalReport and sessionTime > 0:
            buffXAxis = [i * sessionTime / max(buffSampleCount - 1, 1) / 60 for i in range(buffSampleCount)]
        else:
            buffXAxis = None

        # Updated sidebar spacing for modern design
        self.sidebarPadding = 70
        self.sidebarX = self.canvasSize[0] - self.sidebarWidth + self.sidebarPadding
        self.sidebarPanelWidth = self.sidebarWidth - self.sidebarPadding * 2
        self.sidebarInnerInset = 40
        self.sidebarContentWidth = self.sidebarPanelWidth - self.sidebarInnerInset * 2

        currentHoney = onlyValidHourlyHoney[-1] if onlyValidHourlyHoney else 0
        headerY = 70
        headerHeight = 270
        self.drawHeroCard(
            self.leftPadding,
            headerY,
            self.availableSpace,
            headerHeight,
            "FINAL REPORT" if isFinalReport else "HOURLY REPORT",
            "Session Dashboard" if isFinalReport else "Hourly Dashboard",
            "Dense session snapshot built for fast scanning." if isFinalReport else "Condensed performance snapshot for the last completed hour.",
            accent=self.primaryColor
        )
        self.drawBrandCard(self.sidebarX, headerY, self.sidebarPanelWidth, headerHeight)

        overviewY = headerY + headerHeight + 40
        if isFinalReport:
            overviewItems = [
                {"icon": "session_honey_icon", "label": "Total Honey", "value": self.millify(totalHoney), "meta": "Session gain", "color": self.honeyColor},
                {"icon": "average_icon", "label": "Average / Hour", "value": self.millify(avgHoneyPerHour), "meta": "Normalized over runtime", "color": self.primaryColor},
                {"icon": "time_icon", "label": "Total Runtime", "value": self.displayTime(sessionTime, ['d', 'h', 'm']), "meta": "Tracked session length", "color": self.bodyColor},
                {"icon": "history_icon", "label": "Peak Honey / Sec", "value": f"{self.millify(peakRate)}/s", "meta": "Recorded peak", "color": self.secondaryAccentColor},
            ]
        else:
            overviewItems = [
                {"icon": "session_honey_icon", "label": "Honey This Hour", "value": self.millify(honeyThisHour), "meta": "Hourly slice", "color": self.honeyColor},
                {"icon": "average_icon", "label": "Average / Hour", "value": self.millify(avgHoneyPerHour), "meta": "Current session pace", "color": self.primaryColor},
                {"icon": "time_icon", "label": "Session Time", "value": self.displayTime(sessionTime, ['d', 'h', 'm']), "meta": "Current run length", "color": self.bodyColor},
                {"icon": "honey_icon", "label": "Current Honey", "value": self.millify(currentHoney), "meta": "Latest total", "color": self.secondaryAccentColor},
            ]
        self.drawOverviewCards(self.leftPadding, overviewY, self.availableSpace, overviewItems)

        def sessionTimeLabel(i, val):
            if val == 0:
                return "0m"
            if sessionTime < 3600:
                return f"{int(val)}m"
            if sessionTime < 86400:
                return f"{int(val/60)}h"
            return f"{int(val/1440)}d"

        def buffTimeLabel(i, val):
            if buffSampleCount <= 1:
                return "0m" if i == 0 else None

            labelCount = 6 if sessionTime >= 3600 else 5
            step = max(1, (buffSampleCount - 1) // labelCount)
            if i not in (0, buffSampleCount - 1) and i % step:
                return None
            return sessionTimeLabel(i, val)

        panelWidth = self.availableSpace

        # Honey/sec graph - more compact modern layout
        y = 680
        self.drawPanel(self.leftPadding, y, panelWidth, 880, accent=self.honeyColor, fill=self.tintedSurface(self.primaryColor, 0.08))
        headerBottom = self.drawSectionHeader(
            self.leftPadding + 50,
            y + 48,
            panelWidth - 100,
            "HONEY / SEC",
            "Full-session collection rate sampled across the run." if isFinalReport else "Per-minute collection rate across the last completed hour.",
            meta=f"Peak {self.millify(peakRate)}/s",
            accent=self.honeyColor
        )
        dataset = [{
            "data": primarySeries,
            "lineColor": self.primarySoftColor,
            "gradientFill": {
                0: (*self.primarySoftColor, 16),
                0.6: (*self.primaryColor, 60),
                1: (*self.honeyColor, 120)
            }
        }]
        graphTop = headerBottom + 40
        self.drawGraph(
            self.leftPadding + 380,
            graphTop + 560,
            self.availableSpace - 480,
            560,
            mins,
            dataset,
            xLabelFunc=sessionTimeLabel if isFinalReport else self.transformXLabelTime,
            yLabelFunc=lambda i, x: self.millify(x)
        )

        # Backpack graph - compact modern layout
        y = 1600
        self.drawPanel(self.leftPadding, y, panelWidth, 880, accent=self.primaryColor, fill=self.tintedSurface(self.primaryColor, 0.06))
        headerBottom = self.drawSectionHeader(
            self.leftPadding + 50,
            y + 48,
            panelWidth - 100,
            "BACKPACK",
            "Capacity pressure over the full run." if isFinalReport else "Storage pressure over the last hour.",
            meta="0-100%",
            accent=self.primarySoftColor
        )
        backpackData = hourlyReportStats.get("backpack_per_min", [])
        if isFinalReport:
            if not backpackData:
                backpackData = [0] * len(mins)
            elif len(backpackData) < len(mins):
                backpackData = backpackData + [0] * (len(mins) - len(backpackData))
            elif len(backpackData) > len(mins):
                backpackData = backpackData[:len(mins)]
        dataset = [{
            "data": backpackData,
            "lineColor": "gradient",
            "gradientFill": {
                0: (65, 255, 128, 80),
                0.6: (201, 163, 36, 80),
                0.9: (255, 65, 84, 80),
                1: (255, 65, 84, 80),
            }
        }]
        graphTop = headerBottom + 40
        self.drawGraph(
            self.leftPadding + 380,
            graphTop + 560,
            self.availableSpace - 480,
            560,
            mins,
            dataset,
            maxY=100,
            xLabelFunc=sessionTimeLabel if isFinalReport else self.transformXLabelTime,
            yLabelFunc=lambda i, x: f"{int(x)}%"
        )

        # Buff uptime section - more compact modern layout
        y = 2520
        self.drawPanel(self.leftPadding, y, panelWidth, 3920, accent=self.secondaryAccentColor, fill=self.tintedSurface(self.secondaryAccentColor, 0.05))
        headerBottom = self.drawSectionHeader(
            self.leftPadding + 50,
            y + 48,
            panelWidth - 100,
            "BUFF UPTIME",
            "Gathering-window averages first, then binary coverage charts." if isFinalReport else "Gathering-window averages first, then binary buff coverage.",
            meta="Session average" if isFinalReport else "Past hour",
            accent=self.secondaryAccentColor
        )
        y = headerBottom + 320

        dataset = [
            {
                "data": self._getBuffSeries(uptimeBuffsValues, "blue_boost"),
                "lineColor": (77, 147, 193),
                "average": self._getAverageBuff(self._getBuffSeries(uptimeBuffsValues, "blue_boost"), buffGatherIntervals),
                "gradientFill": {0: (77, 147, 193, 8), 1: (77, 147, 193, 100)}
            },
            {
                "data": self._getBuffSeries(uptimeBuffsValues, "red_boost"),
                "lineColor": (200, 90, 80),
                "average": self._getAverageBuff(self._getBuffSeries(uptimeBuffsValues, "red_boost"), buffGatherIntervals),
                "gradientFill": {0: (200, 90, 80, 8), 1: (200, 90, 80, 100)}
            },
            {
                "data": self._getBuffSeries(uptimeBuffsValues, "white_boost"),
                "lineColor": (220, 220, 220),
                "average": self._getAverageBuff(self._getBuffSeries(uptimeBuffsValues, "white_boost"), buffGatherIntervals),
                "gradientFill": {0: (220, 220, 220, 8), 1: (220, 220, 220, 100)}
            }
        ]
        self.drawBuffUptimeGraphStackableBuff(y, dataset, "boost_buff", xData=buffXAxis)

        y += 420
        dataset = [{
            "data": self._getBuffSeries(uptimeBuffsValues, "haste"),
            "lineColor": (210, 210, 210),
            "average": self._getAverageBuff(self._getBuffSeries(uptimeBuffsValues, "haste"), buffGatherIntervals),
            "gradientFill": {0: (210, 210, 210, 8), 1: (210, 210, 210, 100)}
        }]
        self.drawBuffUptimeGraphStackableBuff(y, dataset, "haste_buff", xData=buffXAxis)

        y += 420
        dataset = [{
            "data": self._getBuffSeries(uptimeBuffsValues, "focus"),
            "lineColor": (30, 191, 5),
            "average": self._getAverageBuff(self._getBuffSeries(uptimeBuffsValues, "focus"), buffGatherIntervals),
            "gradientFill": {0: (30, 191, 5, 8), 1: (30, 191, 5, 100)}
        }]
        self.drawBuffUptimeGraphStackableBuff(y, dataset, "focus_buff", xData=buffXAxis)

        y += 420
        dataset = [{
            "data": self._getBuffSeries(uptimeBuffsValues, "bomb_combo"),
            "lineColor": (160, 160, 160),
            "average": self._getAverageBuff(self._getBuffSeries(uptimeBuffsValues, "bomb_combo"), buffGatherIntervals),
            "gradientFill": {0: (160, 160, 160, 8), 1: (160, 160, 160, 100)}
        }]
        self.drawBuffUptimeGraphStackableBuff(y, dataset, "bomb_combo_buff", xData=buffXAxis)

        y += 420
        dataset = [{
            "data": self._getBuffSeries(uptimeBuffsValues, "balloon_aura"),
            "lineColor": (50, 80, 200),
            "average": self._getAverageBuff(self._getBuffSeries(uptimeBuffsValues, "balloon_aura"), buffGatherIntervals),
            "gradientFill": {0: (50, 80, 200, 8), 1: (50, 80, 200, 100)}
        }]
        self.drawBuffUptimeGraphStackableBuff(y, dataset, "balloon_aura_buff", xData=buffXAxis)

        y += 420
        dataset = [{
            "data": self._getBuffSeries(uptimeBuffsValues, "inspire"),
            "lineColor": (195, 191, 18),
            "average": self._getAverageBuff(self._getBuffSeries(uptimeBuffsValues, "inspire"), buffGatherIntervals),
            "gradientFill": {0: (195, 191, 18, 8), 1: (195, 191, 18, 100)}
        }]
        self.drawBuffUptimeGraphStackableBuff(y, dataset, "inspire_buff", xData=buffXAxis)

        y += 240
        dataset = [{
            "data": self._getBuffSeries(uptimeBuffsValues, "melody"),
            "lineColor": (200, 200, 200),
            "gradientFill": {0: (200, 200, 200, 255), 1: (200, 200, 200, 255)}
        }]
        self.drawBuffUptimeGraphUnstackableBuff(y, dataset, "melody_buff", xData=buffXAxis)

        y += 240
        dataset = [{
            "data": self._getBuffSeries(uptimeBuffsValues, "bear"),
            "lineColor": (115, 71, 40),
            "gradientFill": {0: (115, 71, 40, 255), 1: (115, 71, 40, 255)}
        }]
        self.drawBuffUptimeGraphUnstackableBuff(y, dataset, "bear_buff", xData=buffXAxis)

        y += 240
        dataset = [{
            "data": self._getBuffSeries(uptimeBuffsValues, "baby_love"),
            "lineColor": (112, 181, 195),
            "gradientFill": {0: (112, 181, 195, 255), 1: (112, 181, 195, 255)}
        }]
        self.drawBuffUptimeGraphUnstackableBuff(
            y,
            dataset,
            "baby_love_buff",
            renderTime=not isFinalReport,
            xData=buffXAxis,
            xLabelFunc=buffTimeLabel if isFinalReport else None
        )

        # Sidebar layout - modern compact design
        y2 = overviewY
        sectionGap = 75
        if isFinalReport:
            totalSessionTime = sessionStats.get("total_session_time", 0)
            finalHoney = currentHoney
            # Updated for modern session stats panel with 4 rows
            snapshotPanelHeight = 1080
            self.drawPanel(self.sidebarX, y2, self.sidebarPanelWidth, snapshotPanelHeight, accent=self.primaryColor, fill=self.tintedSurface(self.primaryColor, 0.06))
            headerBottom = self.drawSectionHeader(self.sidebarX + 46, y2 + 40, self.sidebarPanelWidth - 92, "SESSION", "High-level totals for the completed run.", accent=self.primarySoftColor)
            statY = headerBottom + 16
            self.drawSessionStat(statY, "time_icon", "Total Runtime", self.displayTime(totalSessionTime, ['d', 'h', 'm']), self.bodyColor)
            statY += 214
            self.drawSessionStat(statY, "honey_icon", "Final Honey", self.millify(finalHoney), self.honeyColor)
            statY += 214
            self.drawSessionStat(statY, "session_honey_icon", "Total Gained", self.millify(totalHoney), "#FDE395")
            statY += 214
            avgSidebarLabel = "Est. Avg/Hour" if totalSessionTime < 3600 else "Avg/Hour"
            self.drawSessionStat(statY, "average_icon", avgSidebarLabel, self.millify(avgHoneyPerHour), self.secondaryAccentColor)

            y2 += snapshotPanelHeight + sectionGap
            glanceItems = [
                {"icon": "honey_icon", "label": "Total Honey", "value": self.millify(totalHoney), "color": self.honeyColor},
                {"icon": "average_icon", "label": "Average / Hour", "value": self.millify(avgHoneyPerHour), "color": self.secondaryAccentColor},
                {"icon": "kill_icon", "label": "Bugs Killed", "value": sessionStats.get("total_bugs", 0), "color": (254, 101, 99)},
                {"icon": "vicious_bee_icon", "label": "Vicious Bees", "value": sessionStats.get("total_vicious_bees", 0), "color": (132, 233, 254)}
            ]
            glancePanelHeight = self.getSidebarMetricPanelHeight(len(glanceItems))
            self.drawPanel(self.sidebarX, y2, self.sidebarPanelWidth, glancePanelHeight, accent=self.primaryColor, fill=self.tintedSurface(self.primaryColor, 0.06))
            headerBottom = self.drawSectionHeader(self.sidebarX + 46, y2 + 40, self.sidebarPanelWidth - 92, "STATS", "Total honey, averages, bugs, and vicious bees.", accent=self.primarySoftColor)
            self.drawSidebarMetricGrid(headerBottom + 20, glanceItems)

            y2 += glancePanelHeight + sectionGap
            taskPanelHeight = self.getTaskTimesPanelHeight(4)
            self.drawPanel(self.sidebarX, y2, self.sidebarPanelWidth, taskPanelHeight, accent=self.secondaryAccentColor, fill=self.tintedSurface(self.secondaryAccentColor, 0.05))
            headerBottom = self.drawSectionHeader(self.sidebarX + 46, y2 + 40, self.sidebarPanelWidth - 92, "ACTIVITY", "Where the macro spent the session.", accent=self.secondaryAccentColor)
            self.drawTaskTimes(headerBottom + 16, [
                {"label": "Gathering", "data": sessionStats.get("gathering_time", 0), "color": self.primarySoftColor},
                {"label": "Converting", "data": sessionStats.get("converting_time", 0), "color": self.honeyColor},
                {"label": "Bug Runs", "data": sessionStats.get("bug_run_time", 0), "color": self.secondaryAccentColor},
                {"label": "Other", "data": sessionStats.get("misc_time", 0), "color": "#6C5B4E"},
            ], totalSessionTime)

            y2 += taskPanelHeight + sectionGap
            questGroups = self.summarizeQuestCompletions(questCompletions)
            questPanelHeight = self.getQuestSummaryPanelHeight(len(questGroups))
            self.drawPanel(self.sidebarX, y2, self.sidebarPanelWidth, questPanelHeight, accent=(103, 253, 153), fill=self.tintedSurface((103, 253, 153), 0.06))
            headerBottom = self.drawSectionHeader(self.sidebarX + 46, y2 + 40, self.sidebarPanelWidth - 92, "QUESTS", "Turn-ins grouped by bee or bear for the whole session.", accent=(103, 253, 153))
            self.drawQuestSummary(headerBottom + 20, questGroups, accent=(103, 253, 153), emptyMessage="No completed quests were recorded this session.")
            y2 += questPanelHeight + sectionGap
        else:
            # Hourly report - 3 rows
            sessionPanelHeight = 880
            self.drawPanel(self.sidebarX, y2, self.sidebarPanelWidth, sessionPanelHeight, accent=self.primaryColor, fill=self.tintedSurface(self.primaryColor, 0.06))
            headerBottom = self.drawSectionHeader(self.sidebarX + 46, y2 + 40, self.sidebarPanelWidth - 92, "SESSION", "Current run totals outside the hourly slice.", accent=self.primarySoftColor)
            statY = headerBottom + 16
            self.drawSessionStat(statY, "time_icon", "Session Time", self.displayTime(sessionTime, ['d', 'h', 'm']), self.bodyColor)
            statY += 214
            self.drawSessionStat(statY, "honey_icon", "Current Honey", self.millify(currentHoney), self.honeyColor)
            statY += 214
            self.drawSessionStat(statY, "session_honey_icon", "Session Honey", self.millify(sessionHoney), "#FDE395")

            y2 += sessionPanelHeight + sectionGap
            glanceItems = [
                {"icon": "average_icon", "label": "Average / Hour", "value": self.millify(avgHoneyPerHour), "color": self.primaryColor},
                {"icon": "honey_icon", "label": "Honey This Hour", "value": self.millify(honeyThisHour), "color": self.honeyColor},
                {"icon": "kill_icon", "label": "Bugs Killed", "value": hourlyReportStats["bugs"], "color": (254, 101, 99)},
                {"icon": "vicious_bee_icon", "label": "Vicious Bees", "value": hourlyReportStats["vicious_bees"], "color": (132, 233, 254)}
            ]
            glancePanelHeight = self.getSidebarMetricPanelHeight(len(glanceItems))
            self.drawPanel(self.sidebarX, y2, self.sidebarPanelWidth, glancePanelHeight, accent=self.primaryColor, fill=self.tintedSurface(self.primaryColor, 0.06))
            headerBottom = self.drawSectionHeader(self.sidebarX + 46, y2 + 40, self.sidebarPanelWidth - 92, "LAST HOUR", "Hourly totals, bugs, and averages.", accent=self.primarySoftColor)
            self.drawSidebarMetricGrid(headerBottom + 20, glanceItems)

            y2 += glancePanelHeight + sectionGap
            taskPanelHeight = self.getTaskTimesPanelHeight(4)
            self.drawPanel(self.sidebarX, y2, self.sidebarPanelWidth, taskPanelHeight, accent=self.secondaryAccentColor, fill=self.tintedSurface(self.secondaryAccentColor, 0.05))
            headerBottom = self.drawSectionHeader(self.sidebarX + 46, y2 + 40, self.sidebarPanelWidth - 92, "ACTIVITY", "How the macro spent the last hour.", accent=self.secondaryAccentColor)
            self.drawTaskTimes(headerBottom + 16, [
                {"label": "Gathering", "data": hourlyReportStats["gathering_time"], "color": self.primarySoftColor},
                {"label": "Converting", "data": hourlyReportStats["converting_time"], "color": self.honeyColor},
                {"label": "Bug Run", "data": hourlyReportStats["bug_run_time"], "color": self.secondaryAccentColor},
                {"label": "Other", "data": hourlyReportStats["misc_time"], "color": "#6C5B4E"},
            ])
            y2 += taskPanelHeight + sectionGap

            questGroups = self.summarizeQuestCompletions(questCompletions)
            questPanelHeight = self.getQuestSummaryPanelHeight(len(questGroups))
            self.drawPanel(self.sidebarX, y2, self.sidebarPanelWidth, questPanelHeight, accent=(103, 253, 153), fill=self.tintedSurface((103, 253, 153), 0.06))
            headerBottom = self.drawSectionHeader(self.sidebarX + 46, y2 + 40, self.sidebarPanelWidth - 92, "QUESTS", "All recorded turn-ins grouped by quest owner for the past hour.", accent=(103, 253, 153))
            self.drawQuestSummary(headerBottom + 20, questGroups, accent=(103, 253, 153), emptyMessage="No completed quests were recorded this hour.")
            y2 += questPanelHeight + sectionGap

        planterNames = []
        planterTimes = []
        planterFields = []
        if planterData:
            for i in range(len(planterData["planters"])):
                if planterData["planters"][i]:
                    planterNames.append(planterData["planters"][i])
                    planterTimes.append(planterData["harvestTimes"][i] - time.time())
                    planterFields.append(planterData["fields"][i])
        if planterNames:
            planterRows = max(1, math.ceil(len(planterNames) / 2))
            planterHeight = planterRows * 540 + max(0, planterRows - 1) * 36
            self.drawPanel(self.sidebarX, y2, self.sidebarPanelWidth, planterHeight + 230, accent=self.primaryColor, fill=self.tintedSurface(self.primaryColor, 0.06))
            headerBottom = self.drawSectionHeader(
                self.sidebarX + 46,
                y2 + 40,
                self.sidebarPanelWidth - 92,
                "PLANTERS",
                "Current placements carried into the final snapshot." if isFinalReport else "Current placements and ready times.",
                accent=self.primaryColor
            )
            self.drawPlanters(headerBottom + 16, planterNames, planterTimes, planterFields)
            y2 += planterHeight + 230 + sectionGap

        # Modern buffs panel - more compact
        buffPanelHeight = 780
        self.drawPanel(self.sidebarX, y2, self.sidebarPanelWidth, buffPanelHeight, accent=self.secondaryAccentColor, fill=self.tintedSurface(self.secondaryAccentColor, 0.04))
        headerBottom = self.drawSectionHeader(self.sidebarX + 46, y2 + 40, self.sidebarPanelWidth - 92, "BUFFS", "Final captured stack values." if isFinalReport else "Latest captured stack values.", accent=self.secondaryAccentColor)
        self.drawBuffs(headerBottom + 26, buffQuantity)

        y2 += buffPanelHeight + sectionGap
        nectarPanelHeight = 860
        self.drawPanel(self.sidebarX, y2, self.sidebarPanelWidth, nectarPanelHeight, accent=self.honeyColor, fill=self.tintedSurface(self.honeyColor, 0.04))
        headerBottom = self.drawSectionHeader(self.sidebarX + 46, y2 + 40, self.sidebarPanelWidth - 92, "NECTARS", "Session-end field nectar percentages." if isFinalReport else "Field nectar percentages at render time.", accent=self.honeyColor)
        self.drawNectars(headerBottom + 32, nectarQuantity)

        if not isFinalReport and enabled_fields:
            y2 += nectarPanelHeight + sectionGap
            fieldPanelHeight = self.getFieldsPanelHeight(len(enabled_fields))
            self.drawPanel(self.sidebarX, y2, self.sidebarPanelWidth, fieldPanelHeight, accent=self.primarySoftColor, fill=self.tintedSurface(self.primaryColor, 0.04))
            headerBottom = self.drawSectionHeader(self.sidebarX + 46, y2 + 40, self.sidebarPanelWidth - 92, "FIELDS", "Enabled fields and their active patterns.", accent=self.primarySoftColor)
            self.drawFields(headerBottom + 20, enabled_fields, field_patterns)

        return self.canvas

    def drawHourlyReport(self, hourlyReportStats, sessionTime, honeyPerMin, sessionHoney, honeyThisHour, onlyValidHourlyHoney, buffQuantity, nectarQuantity, planterData, uptimeBuffsValues, buffGatherIntervals, questCompletions=None, enabled_fields=None, field_patterns=None):
        return self._drawReportTemplate(
            "hourly",
            hourlyReportStats,
            honeyPerMin,
            sessionHoney,
            onlyValidHourlyHoney,
            buffQuantity,
            nectarQuantity,
            planterData,
            uptimeBuffsValues,
            buffGatherIntervals,
            questCompletions=questCompletions,
            enabled_fields=enabled_fields,
            field_patterns=field_patterns,
            sessionTime=sessionTime,
            honeyThisHour=honeyThisHour
        )

    def drawFinalReport(self, hourlyReportStats, sessionStats, honeyPerSec, sessionHoney, onlyValidHourlyHoney, buffQuantity, nectarQuantity, planterData, uptimeBuffsValues, buffGatherIntervals, questCompletions=None, enabled_fields=None, field_patterns=None):
        return self._drawReportTemplate(
            "final",
            hourlyReportStats,
            honeyPerSec,
            sessionHoney,
            onlyValidHourlyHoney,
            buffQuantity,
            nectarQuantity,
            planterData,
            uptimeBuffsValues,
            buffGatherIntervals,
            questCompletions=questCompletions,
            enabled_fields=enabled_fields,
            field_patterns=field_patterns,
            sessionStats=sessionStats
        )
