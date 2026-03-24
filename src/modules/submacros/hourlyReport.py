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
        # reduced canvas height to shrink overall report image
        self.canvasSize = (6400, 8000)
        self.sidebarWidth = 1820
        self.leftPadding = 136
        self.availableSpace = self.canvasSize[0] - self.sidebarWidth - self.leftPadding*2
        self.time_format = time_format
        self.fontScale = 1.1
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
        for y in range(self.canvasSize[1]):
            ratio = y / max(self.canvasSize[1] - 1, 1)
            color = self.blendColor(self.backgroundTopColor, self.backgroundBottomColor, ratio)
            gradientDraw.line((0, y, self.canvasSize[0], y), fill=self.withAlpha(color, 255))

        overlay = Image.new("RGBA", self.canvasSize, (0, 0, 0, 0))
        overlayDraw = ImageDraw.Draw(overlay)
        overlayDraw.ellipse((-900, -280, 2500, 2100), fill=self.withAlpha(self.primaryColor, 26))
        overlayDraw.ellipse((3320, -260, 7040, 1660), fill=self.withAlpha(self.honeyColor, 14))
        overlayDraw.ellipse((4180, 4700, 7600, 7920), fill=self.withAlpha(self.secondaryAccentColor, 12))
        overlayDraw.rectangle((0, 0, self.canvasSize[0], 360), fill=self.withAlpha((255, 255, 255), 8))
        overlay = overlay.filter(ImageFilter.GaussianBlur(190))

        self.canvas = Image.alpha_composite(base, overlay)
        self.draw = ImageDraw.Draw(self.canvas)

    def drawPanel(self, x, y, width, height, accent=None, fill=None, radius=64, shadowAlpha=78):
        accent = self.toRgb(accent or self.primaryColor)
        fill = self.toRgb(fill or self.surfaceColor)

        shadowBox = (x + 12, y + 16, x + width + 12, y + height + 16)
        self.draw.rounded_rectangle(shadowBox, radius=radius + 4, fill=(0, 0, 0, shadowAlpha))
        self.draw.rounded_rectangle(
            (x, y, x + width, y + height),
            radius=radius,
            fill=self.withAlpha(fill, 244),
            outline=self.withAlpha(self.borderColor, 204),
            width=3
        )
        self.draw.rounded_rectangle(
            (x + 18, y + 18, x + width - 18, y + height - 18),
            radius=max(18, radius - 18),
            outline=self.withAlpha(self.blendColor(fill, accent, 0.18), 74),
            width=2
        )
        self.draw.rounded_rectangle(
            (x + 34, y + 28, x + width - 34, y + 38),
            radius=5,
            fill=self.withAlpha(accent, 168)
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

        titleFont = self.getFont("semibold", 68)
        self.draw.text((x, cursorY), title, fill=self.bodyColor, font=titleFont)

        if meta:
            metaFont = self.getFont("medium", 40)
            metaBox = self.draw.textbbox((0, 0), meta, font=metaFont)
            metaWidth = metaBox[2] - metaBox[0]
            self.draw.text((x + width - metaWidth, cursorY + 10), meta, fill=accent, font=metaFont)

        if subtitle:
            self.draw.text((x, cursorY + 84), subtitle, fill=self.mutedColor, font=self.getFont("medium", 38))
            return cursorY + 150

        return cursorY + 82

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
        self.draw.text((textX, y + 74), "Fuzzy Macro", fill=self.bodyColor, font=self.getFont("bold", 82))
        self.draw.text((textX, y + 170), "report dashboard", fill=self.mutedColor, font=self.getFont("medium", 38))

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
        chipY = y + height - 118
        for label, value, chipAccent in chips or []:
            chipX += self.drawMetricChip(chipX, chipY, label, value, chipAccent) + 22

    def drawOverviewCards(self, x, y, width, items, columns=4, cardHeight=284):
        if not items:
            return 0

        gap = 28
        cardWidth = (width - gap * (columns - 1)) // columns
        labelFont = self.getFont("medium", 30)
        valueFont = self.getFont("bold", 62)
        metaFont = self.getFont("medium", 28)

        for i, item in enumerate(items[:columns]):
            accent = self.toRgb(item.get("color", self.primaryColor))
            cardX = x + i * (cardWidth + gap)
            iconName = item.get("icon")
            self.drawPanel(cardX, y, cardWidth, cardHeight, accent=accent, fill=self.tintedSurface(accent, 0.08), radius=44, shadowAlpha=48)

            self.draw.rounded_rectangle(
                (cardX + 28, y + 34, cardX + 144, y + 150),
                radius=30,
                fill=self.withAlpha(self.surfaceInsetColor, 235)
            )

            if iconName:
                try:
                    img = Image.open(f"{self.assetPath}/{iconName}.png").convert("RGBA")
                    widthRaw, heightRaw = img.size
                    imageHeight = 74
                    imageWidth = int(widthRaw * (imageHeight / max(heightRaw, 1)))
                    img = img.resize((imageWidth, imageHeight), Image.LANCZOS)
                    self.canvas.paste(
                        img,
                        (cardX + 86 - imageWidth // 2, y + 92 - imageHeight // 2),
                        img
                    )
                except Exception:
                    pass

            label = str(item.get("label", "")).upper()
            value = str(item.get("value", "0"))
            meta = str(item.get("meta", "")).strip()
            self.draw.text((cardX + 168, y + 40), label, fill=self.mutedColor, font=labelFont)
            self.draw.text((cardX + 28, y + 156), value, fill=self.bodyColor, font=valueFont)
            if meta:
                self.draw.text((cardX + 28, y + 234), meta, fill=accent, font=metaFont)

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
        font = self.getFont("medium", 40)
        fontColor = self.mutedColor
        gridColor = self.withAlpha(self.gridColor, 210)

        self.draw.rounded_rectangle(
            (graphX, graphY - height, graphX + width, graphY),
            radius=34,
            fill=self.withAlpha(self.surfaceInsetColor, 242),
            outline=self.withAlpha(self.innerBorderColor, 82),
            width=2
        )

        xDivisions = min(6, max(pointCount - 1, 1))
        for division in range(xDivisions + 1):
            x = graphX + width * division / max(xDivisions, 1)
            self.draw.line((x, graphY - height, x, graphY), fill=self.withAlpha(self.gridColor, 96), width=2)

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
                    self.draw.text((graphX - textWidth - 74, y - textHeight / 2), text, font=font, fill=fontColor)
            self.draw.line((graphX, y, graphX + width, y), fill=gridColor, width=2)

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
                self.draw.text((graphX + xInterval * idx - textWidth / 2, graphY + 22), labelText, font=font, fill=fontColor)

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
                        self.draw.line((int(subX0), int(subY0), int(subX1), int(subY1)), fill=(r, g, b), width=6)
            else:
                self.draw.line(points, fill=lineColor, width=6, joint="curve")

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
            labelX = graphXStart - 170
            labelY = y - graphHeight // 2 + 22 + i * 68
            self.drawChip(
                labelX,
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
        rowHeight = 234
        imgContainerDimension = 152
        accent = self.toRgb(valueColor)

        self.draw.rounded_rectangle(
            (sectionX, y, sectionX + sectionWidth, y + rowHeight),
            radius=42,
            fill=self.withAlpha(self.surfaceRaisedColor, 210),
            outline=self.withAlpha(self.borderColor, 110),
            width=3
        )
        self.draw.rounded_rectangle(
            (sectionX + 30, y + 41, sectionX + 30 + imgContainerDimension, y + 41 + imgContainerDimension),
            radius=36,
            fill=self.withAlpha(self.surfaceInsetColor, 235)
        )
        img = Image.open(f"{self.assetPath}/{imageName}.png").convert("RGBA")
        width, height = img.size
        imageWidth = 96
        imageHeight = int(height*(imageWidth/width))
        img = img.resize((imageWidth, imageHeight))
        self.canvas.paste(
            img,
            (sectionX + 30 + (imgContainerDimension-imageWidth)//2, y + 41 + (imgContainerDimension-imageHeight)//2),
            img
        )

        labelFont = self.getFont("medium", 50)
        valueFont = self.getFont("semibold", 66)
        textX = sectionX + 222
        self.draw.text((textX, y + 54), label, self.mutedColor, font=labelFont)
        bbox = self.draw.textbbox((0, 0), value, font=valueFont)
        textWidth = bbox[2] - bbox[0]
        self.draw.text((sectionX + sectionWidth - textWidth - 30, y + 132), str(value), accent, font=valueFont)

    def drawTaskTimes(self, y, datasets, totalTime=None):
        legendIconDimension = 102
        labelFont = self.getFont("medium", 58)
        valueFont = self.getFont("semibold", 60)
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
                (x, y, x + sectionWidth, y + 160),
                radius=38,
                fill=self.withAlpha(self.surfaceRaisedColor, 200),
                outline=self.withAlpha(color, 60),
                width=2
            )
            self.draw.rounded_rectangle((x + 26, y + 29, x + 26 + legendIconDimension, y + 29 + legendIconDimension), fill=color, radius=24)
            self.draw.text((x + legendIconDimension + 68, y + 30), dataset["label"], self.bodyColor, font=labelFont)

            percentBox = self.draw.textbbox((0, 0), percentText, font=valueFont)
            percentWidth = percentBox[2] - percentBox[0]
            percentX = x + sectionWidth - percentWidth - 30
            self.draw.text((percentX, y + 46), percentText, self.mutedColor, font=valueFont)

            timeBox = self.draw.textbbox((0, 0), timeText, font=valueFont)
            timeWidth = timeBox[2] - timeBox[0]
            timeX = percentX - timeWidth - 60
            self.draw.text((timeX, y + 46), timeText, color, font=valueFont)
            y += 190

        y += 156
        doughnutChartSize = 680
        chartX = x + (sectionWidth - doughnutChartSize) // 2
        self.drawDoughnutChart(chartX, y, doughnutChartSize, datasets, holeRatio=0.44)
        return (len(datasets) * 190) + 156 + doughnutChartSize

    def getTaskTimesPanelHeight(self, datasetCount, headerHeight=188, bottomPadding=70):
        rowsHeight = datasetCount * 190
        chartBlockHeight = 156 + 680
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
        fieldFont = self.getFont("semibold", 74)
        timeFont = self.getFont("semibold", 60)
        cardWidth = (sectionWidth - 32) // 2
        cardHeight = 600
        for i in range(len(planterNames)):
            if not planterNames[i]:
                continue
            col = i % 2
            row = i // 2
            cardX = planterX + col * (cardWidth + 32)
            cardY = y + row * (cardHeight + 40)
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
            imageHeight = 290
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
            self.canvas.paste(img, (cardX + (cardWidth-imageWidth)//2, cardY + 46), img)
            self.draw.text((cardX + (cardWidth - fieldAndNectarWidth)//2, cardY + 366), planterFields[i].title(), font=fieldFont, fill=self.bodyColor) 
            self.canvas.paste(nectarImg, (cardX + (cardWidth - fieldAndNectarWidth)//2 + fieldTextWidth + 30, cardY + 383), nectarImg)
            self.draw.text((cardX + (cardWidth - timeTextWidth)//2, cardY + 494), timeText, font=timeFont, fill=self.mutedColor)

        rows = max(1, math.ceil(len(planterNames) / 2)) if planterNames else 0
        return rows * cardHeight + max(0, rows - 1) * 40

    def drawBuffs(self, y, buffData):
        buffImages = ["tabby_love_buff", "polar_power_buff", "wealth_clock_buff", "blessing_buff", "bloat_buff"]

        font = self.getFont("bold", 64)
        baseX = self.sidebarX + getattr(self, "sidebarInnerInset", 0)
        sectionWidth = getattr(self, "sidebarContentWidth", self.sidebarWidth - self.sidebarPadding * 2)
        gap = 24
        cardWidth = (sectionWidth - gap * 4) // 5
        imageWidth = max(120, cardWidth - 24)
        for i in range(len(buffData)):
            buff = str(buffData[i]) #I cant make up my mind on if buffData should switch to ints or remain as string
            x = baseX + (cardWidth + gap) * i
            cardHeight = cardWidth + 92

            img = Image.open(f"{self.assetPath}/{buffImages[i]}.png").convert("RGBA")
            width, height = img.size
            imageHeight= int(width*(imageWidth/height))
            img = img.resize((imageWidth, imageHeight), Image.LANCZOS)

            if buff == "0":
                #dim the image
                overlay = Image.new("RGBA", img.size, (0, 0, 0, 100))
            else:
                overlay = Image.new("RGBA", img.size, (0, 0, 0, 20))
            img = Image.alpha_composite(img, overlay)
            self.draw.rounded_rectangle(
                (x, y, x + cardWidth, y + cardHeight),
                radius=32,
                fill=self.withAlpha(self.surfaceRaisedColor, 210),
                outline=self.withAlpha(self.borderColor, 110),
                width=2
            )
            imageX = x + (cardWidth - imageWidth) // 2
            imageY = y + 18
            self.canvas.paste(img, (imageX, imageY), img)

            if buff != "0":
                buffText = f"x{buff}"
                bbox = self.draw.textbbox((0, 0), buffText, font=font, stroke_width=4)
                textWidth = bbox[2] - bbox[0]
                textHeight = 64
                self.draw.text((x + cardWidth - textWidth - 12, imageY + imageHeight - textHeight + 6), buffText, fill=self.bodyColor, font=font, stroke_width=4, stroke_fill=(0,0,0))

    def drawNectars(self, y, nectarData):
        nectarColors = [(165, 207, 234), (235, 120, 108), (194, 166, 236), (162, 239, 163), (239, 205, 224)]
        nectarNames = ["comforting", "invigorating", "motivating", "refreshing", "satisfying"]
        baseX = self.sidebarX + getattr(self, "sidebarInnerInset", 0)
        sectionWidth = getattr(self, "sidebarContentWidth", self.sidebarWidth - self.sidebarPadding * 2)
        gap = 28
        cardWidth = (sectionWidth - gap * 4) // 5
        progressChartSize = min(240, cardWidth)
        imageHeight = 100
        for i in range(len(nectarData)):
            x = baseX + i * (cardWidth + gap)
            self.draw.rounded_rectangle(
                (x, y, x + cardWidth, y + progressChartSize + 172),
                radius=36,
                fill=self.withAlpha(self.surfaceRaisedColor, 210),
                outline=self.withAlpha(self.borderColor, 100),
                width=2
            )
            chartX = x + (cardWidth - progressChartSize) // 2
            self.drawProgressChart(chartX, y, progressChartSize, nectarData[i], nectarColors[i], 0.75)

            img = Image.open(f"{self.assetPath}/{nectarNames[i]}.png").convert("RGBA")
            width, height = img.size
            imageWidth = int(width*(imageHeight/height))
            img = img.resize((imageWidth, imageHeight), Image.LANCZOS)
            self.canvas.paste(img, (x + (cardWidth - imageWidth)//2, y + progressChartSize + 54), img)

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
        return 320 + rows * 194 + max(0, rows - 1) * 30

    def drawFields(self, y, enabled_fields, field_patterns):
        sectionX = self.sidebarX + getattr(self, "sidebarInnerInset", 0)
        sectionWidth = getattr(self, "sidebarContentWidth", self.sidebarWidth - self.sidebarPadding * 2)
        cardGap = 28
        cardWidth = (sectionWidth - cardGap) // 2
        cardHeight = 194
        labelFont = self.getFont("semibold", 40)
        metaFont = self.getFont("medium", 26)
        patternFont = self.getFont("semibold", 32)

        for i, fieldName in enumerate(enabled_fields):
            visuals = self.getFieldVisuals(fieldName)
            pattern = str(field_patterns.get(fieldName, "unknown")).replace("_", " ")
            cardX = sectionX + (i % 2) * (cardWidth + cardGap)
            cardY = y + (i // 2) * (cardHeight + 30)
            accent = self.toRgb(visuals["accent"])

            self.draw.rounded_rectangle(
                (cardX, cardY, cardX + cardWidth, cardY + cardHeight),
                radius=34,
                fill=self.withAlpha(self.surfaceRaisedColor, 215),
                outline=self.withAlpha(accent, 95),
                width=3
            )
            self.draw.rounded_rectangle(
                (cardX + 18, cardY + 18, cardX + cardWidth - 18, cardY + cardHeight - 18),
                radius=28,
                outline=self.withAlpha(self.blendColor(self.surfaceRaisedColor, accent, 0.25), 80),
                width=2
            )

            iconBox = (cardX + 24, cardY + 24, cardX + 118, cardY + 118)
            self.draw.rounded_rectangle(iconBox, radius=26, fill=self.withAlpha(accent, 220))
            initialBox = self.draw.textbbox((0, 0), visuals["initials"], font=self.getFont("bold", 38))
            initialWidth = initialBox[2] - initialBox[0]
            initialHeight = initialBox[3] - initialBox[1]
            self.draw.text(
                (cardX + 71 - initialWidth // 2, cardY + 69 - initialHeight // 2 - 4),
                visuals["initials"],
                fill=self.backgroundColor,
                font=self.getFont("bold", 38)
            )

            nectarIcon = visuals.get("nectar")
            if nectarIcon:
                try:
                    nectarImg = Image.open(f"{self.assetPath}/{nectarIcon}.png").convert("RGBA")
                    nectarImg = nectarImg.resize((40, 40), Image.LANCZOS)
                    self.canvas.paste(nectarImg, (cardX + 92, cardY + 88), nectarImg)
                except Exception:
                    pass

            textX = cardX + 138
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

    def getSidebarMetricPanelHeight(self, itemCount, columns=2, headerHeight=188, bottomPadding=64):
        rows = max(1, math.ceil(max(itemCount, 1) / columns))
        return headerHeight + rows * 308 + max(0, rows - 1) * 34 + bottomPadding

    def drawSidebarMetricGrid(self, y, items, columns=2):
        sectionX = self.sidebarX + getattr(self, "sidebarInnerInset", 0)
        sectionWidth = getattr(self, "sidebarContentWidth", self.sidebarWidth - self.sidebarPadding * 2)
        cardGap = 28
        rowGap = 34
        cardWidth = (sectionWidth - cardGap * (columns - 1)) // columns
        cardHeight = 274
        labelFont = self.getFont("medium", 34)
        valueFont = self.getFont("semibold", 60)

        for i, item in enumerate(items):
            accent = self.toRgb(item.get("color", self.primaryColor))
            cardX = sectionX + (i % columns) * (cardWidth + cardGap)
            cardY = y + (i // columns) * (cardHeight + rowGap)

            self.draw.rounded_rectangle(
                (cardX, cardY, cardX + cardWidth, cardY + cardHeight),
                radius=38,
                fill=self.withAlpha(self.surfaceRaisedColor, 210),
                outline=self.withAlpha(accent, 95),
                width=3
            )
            self.draw.rounded_rectangle(
                (cardX + 24, cardY + 24, cardX + 136, cardY + 136),
                radius=28,
                fill=self.withAlpha(self.surfaceInsetColor, 235)
            )

            img = Image.open(f"{self.assetPath}/{item['icon']}.png").convert("RGBA")
            width, height = img.size
            imageHeight = 78
            imageWidth = int(width * (imageHeight / height))
            img = img.resize((imageWidth, imageHeight), Image.LANCZOS)
            self.canvas.paste(
                img,
                (cardX + 80 - imageWidth // 2, cardY + 80 - imageHeight // 2),
                img
            )

            label = self.truncateText(item.get("label", ""), labelFont, cardWidth - 58)
            value = str(item.get("value", "0"))
            self.draw.text((cardX + 24, cardY + 162), label, fill=self.mutedColor, font=labelFont)
            self.draw.text((cardX + 24, cardY + 206), value, fill=accent, font=valueFont)

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

    def getQuestSummaryPanelHeight(self, groupCount, headerHeight=188, bottomPadding=64):
        visibleCount = max(1, max(groupCount, 0))
        summaryHeight = 228
        rowHeight = 154
        rowGap = 26
        return headerHeight + summaryHeight + 52 + visibleCount * rowHeight + max(0, visibleCount - 1) * rowGap + bottomPadding

    def drawQuestSummary(self, y, questGroups, accent=(103, 253, 153), emptyMessage="No quest turn-ins recorded yet."):
        sectionX = self.sidebarX + getattr(self, "sidebarInnerInset", 0)
        sectionWidth = getattr(self, "sidebarContentWidth", self.sidebarWidth - self.sidebarPadding * 2)
        accent = self.toRgb(accent)
        summaryHeight = 228

        self.draw.rounded_rectangle(
            (sectionX, y, sectionX + sectionWidth, y + summaryHeight),
            radius=40,
            fill=self.withAlpha(self.surfaceRaisedColor, 210),
            outline=self.withAlpha(accent, 100),
            width=3
        )
        self.draw.rounded_rectangle(
            (sectionX + 28, y + 38, sectionX + 156, y + 166),
            radius=30,
            fill=self.withAlpha(self.surfaceInsetColor, 235)
        )
        img = Image.open(f"{self.assetPath}/quest_icon.png").convert("RGBA").resize((90, 90), Image.LANCZOS)
        self.canvas.paste(img, (sectionX + 47, y + 57), img)

        labelFont = self.getFont("medium", 38)
        valueFont = self.getFont("semibold", 70)
        totalCount = sum(count for _, count in questGroups)
        self.draw.text((sectionX + 196, y + 52), "Quest Turn-Ins", fill=self.mutedColor, font=labelFont)
        self.draw.text((sectionX + 196, y + 104), str(totalCount), fill=accent, font=valueFont)

        rowFont = self.getFont("medium", 38)
        valueRowFont = self.getFont("semibold", 42)
        pillFont = self.getFont("semibold", 30)
        rowHeight = 154
        rowGap = 26
        contentY = y + summaryHeight + 52
        visibleGroups = list(questGroups)
        if not visibleGroups:
            visibleGroups = [(emptyMessage, 0)]

        for i, (owner, count) in enumerate(visibleGroups):
            rowY = contentY + i * (rowHeight + rowGap)
            self.draw.rounded_rectangle(
                (sectionX, rowY, sectionX + sectionWidth, rowY + rowHeight),
                radius=34,
                fill=self.withAlpha(self.surfaceRaisedColor, 205),
                outline=self.withAlpha(self.borderColor, 110),
                width=2
            )

            pillText = owner if count else "-"
            pillWidth, pillHeight = self.drawChip(
                sectionX + 24,
                rowY + 38,
                self.truncateText(pillText, pillFont, sectionWidth - 270),
                fill=self.withAlpha(self.tintedSurface(accent, 0.25), 235),
                textColor=accent,
                font=pillFont,
                paddingX=18,
                paddingY=10
            )

            if count:
                valueText = str(count)
                valueBox = self.draw.textbbox((0, 0), valueText, font=valueRowFont)
                valueWidth = valueBox[2] - valueBox[0]
                valueX = sectionX + sectionWidth - valueWidth - 28
                self.draw.text((valueX, rowY + 46), valueText, fill=self.bodyColor, font=valueRowFont)
                self.draw.text((valueX - 114, rowY + 54), "done", fill=self.mutedColor, font=rowFont)
            else:
                self.draw.text((sectionX + 24, rowY + pillHeight + 50), owner, fill=self.mutedColor, font=rowFont)

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

        self.sidebarPadding = 85
        self.sidebarX = self.canvasSize[0] - self.sidebarWidth + self.sidebarPadding
        self.sidebarPanelWidth = self.sidebarWidth - self.sidebarPadding * 2
        self.sidebarInnerInset = 46
        self.sidebarContentWidth = self.sidebarPanelWidth - self.sidebarInnerInset * 2

        currentHoney = onlyValidHourlyHoney[-1] if onlyValidHourlyHoney else 0
        headerY = 80
        headerHeight = 300
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

        overviewY = headerY + headerHeight + 46
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

        y = 780
        self.drawPanel(self.leftPadding, y, panelWidth, 980, accent=self.honeyColor, fill=self.tintedSurface(self.primaryColor, 0.1))
        headerBottom = self.drawSectionHeader(
            self.leftPadding + 60,
            y + 56,
            panelWidth - 120,
            "HONEY / SEC",
            "Full-session collection rate sampled across the run." if isFinalReport else "Per-minute collection rate across the last completed hour.",
            meta=f"Peak {self.millify(peakRate)}/s",
            accent=self.honeyColor
        )
        dataset = [{
            "data": primarySeries,
            "lineColor": self.primarySoftColor,
            "gradientFill": {
                0: (*self.primarySoftColor, 18),
                0.6: (*self.primaryColor, 70),
                1: (*self.honeyColor, 140)
            }
        }]
        graphTop = headerBottom + 46
        self.drawGraph(
            self.leftPadding + 430,
            graphTop + 620,
            self.availableSpace - 540,
            620,
            mins,
            dataset,
            xLabelFunc=sessionTimeLabel if isFinalReport else self.transformXLabelTime,
            yLabelFunc=lambda i, x: self.millify(x)
        )

        # Keep the main-column sections on a single vertical rhythm so later panels
        # cannot drift into the previous graph area when hourly/final variants diverge.
        y = 1810
        self.drawPanel(self.leftPadding, y, panelWidth, 980, accent=self.primaryColor, fill=self.tintedSurface(self.primaryColor, 0.08))
        headerBottom = self.drawSectionHeader(
            self.leftPadding + 60,
            y + 56,
            panelWidth - 120,
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
                0: (65, 255, 128, 90),
                0.6: (201, 163, 36, 90),
                0.9: (255, 65, 84, 90),
                1: (255, 65, 84, 90),
            }
        }]
        graphTop = headerBottom + 46
        self.drawGraph(
            self.leftPadding + 430,
            graphTop + 620,
            self.availableSpace - 540,
            620,
            mins,
            dataset,
            maxY=100,
            xLabelFunc=sessionTimeLabel if isFinalReport else self.transformXLabelTime,
            yLabelFunc=lambda i, x: f"{int(x)}%"
        )

        y = 2840
        self.drawPanel(self.leftPadding, y, panelWidth, 4320, accent=self.secondaryAccentColor, fill=self.tintedSurface(self.secondaryAccentColor, 0.06))
        headerBottom = self.drawSectionHeader(
            self.leftPadding + 60,
            y + 56,
            panelWidth - 120,
            "BUFF UPTIME",
            "Gathering-window averages first, then binary coverage charts." if isFinalReport else "Gathering-window averages first, then binary buff coverage.",
            meta="Session average" if isFinalReport else "Past hour",
            accent=self.secondaryAccentColor
        )
        y = headerBottom + 360

        dataset = [
            {
                "data": self._getBuffSeries(uptimeBuffsValues, "blue_boost"),
                "lineColor": (77, 147, 193),
                "average": self._getAverageBuff(self._getBuffSeries(uptimeBuffsValues, "blue_boost"), buffGatherIntervals),
                "gradientFill": {0: (77, 147, 193, 10), 1: (77, 147, 193, 120)}
            },
            {
                "data": self._getBuffSeries(uptimeBuffsValues, "red_boost"),
                "lineColor": (200, 90, 80),
                "average": self._getAverageBuff(self._getBuffSeries(uptimeBuffsValues, "red_boost"), buffGatherIntervals),
                "gradientFill": {0: (200, 90, 80, 10), 1: (200, 90, 80, 120)}
            },
            {
                "data": self._getBuffSeries(uptimeBuffsValues, "white_boost"),
                "lineColor": (220, 220, 220),
                "average": self._getAverageBuff(self._getBuffSeries(uptimeBuffsValues, "white_boost"), buffGatherIntervals),
                "gradientFill": {0: (220, 220, 220, 10), 1: (220, 220, 220, 120)}
            }
        ]
        self.drawBuffUptimeGraphStackableBuff(y, dataset, "boost_buff", xData=buffXAxis)

        y += 460
        dataset = [{
            "data": self._getBuffSeries(uptimeBuffsValues, "haste"),
            "lineColor": (210, 210, 210),
            "average": self._getAverageBuff(self._getBuffSeries(uptimeBuffsValues, "haste"), buffGatherIntervals),
            "gradientFill": {0: (210, 210, 210, 10), 1: (210, 210, 210, 120)}
        }]
        self.drawBuffUptimeGraphStackableBuff(y, dataset, "haste_buff", xData=buffXAxis)

        y += 460
        dataset = [{
            "data": self._getBuffSeries(uptimeBuffsValues, "focus"),
            "lineColor": (30, 191, 5),
            "average": self._getAverageBuff(self._getBuffSeries(uptimeBuffsValues, "focus"), buffGatherIntervals),
            "gradientFill": {0: (30, 191, 5, 10), 1: (30, 191, 5, 120)}
        }]
        self.drawBuffUptimeGraphStackableBuff(y, dataset, "focus_buff", xData=buffXAxis)

        y += 460
        dataset = [{
            "data": self._getBuffSeries(uptimeBuffsValues, "bomb_combo"),
            "lineColor": (160, 160, 160),
            "average": self._getAverageBuff(self._getBuffSeries(uptimeBuffsValues, "bomb_combo"), buffGatherIntervals),
            "gradientFill": {0: (160, 160, 160, 10), 1: (160, 160, 160, 120)}
        }]
        self.drawBuffUptimeGraphStackableBuff(y, dataset, "bomb_combo_buff", xData=buffXAxis)

        y += 460
        dataset = [{
            "data": self._getBuffSeries(uptimeBuffsValues, "balloon_aura"),
            "lineColor": (50, 80, 200),
            "average": self._getAverageBuff(self._getBuffSeries(uptimeBuffsValues, "balloon_aura"), buffGatherIntervals),
            "gradientFill": {0: (50, 80, 200, 10), 1: (50, 80, 200, 120)}
        }]
        self.drawBuffUptimeGraphStackableBuff(y, dataset, "balloon_aura_buff", xData=buffXAxis)

        y += 460
        dataset = [{
            "data": self._getBuffSeries(uptimeBuffsValues, "inspire"),
            "lineColor": (195, 191, 18),
            "average": self._getAverageBuff(self._getBuffSeries(uptimeBuffsValues, "inspire"), buffGatherIntervals),
            "gradientFill": {0: (195, 191, 18, 10), 1: (195, 191, 18, 120)}
        }]
        self.drawBuffUptimeGraphStackableBuff(y, dataset, "inspire_buff", xData=buffXAxis)

        y += 260
        dataset = [{
            "data": self._getBuffSeries(uptimeBuffsValues, "melody"),
            "lineColor": (200, 200, 200),
            "gradientFill": {0: (200, 200, 200, 255), 1: (200, 200, 200, 255)}
        }]
        self.drawBuffUptimeGraphUnstackableBuff(y, dataset, "melody_buff", xData=buffXAxis)

        y += 260
        dataset = [{
            "data": self._getBuffSeries(uptimeBuffsValues, "bear"),
            "lineColor": (115, 71, 40),
            "gradientFill": {0: (115, 71, 40, 255), 1: (115, 71, 40, 255)}
        }]
        self.drawBuffUptimeGraphUnstackableBuff(y, dataset, "bear_buff", xData=buffXAxis)

        y += 260
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

        y2 = overviewY
        sectionGap = 90
        if isFinalReport:
            totalSessionTime = sessionStats.get("total_session_time", 0)
            finalHoney = currentHoney
            snapshotPanelHeight = 1220
            self.drawPanel(self.sidebarX, y2, self.sidebarPanelWidth, snapshotPanelHeight, accent=self.primaryColor, fill=self.tintedSurface(self.primaryColor, 0.08))
            headerBottom = self.drawSectionHeader(self.sidebarX + 50, y2 + 44, self.sidebarPanelWidth - 100, "SESSION", "High-level totals for the completed run.", accent=self.primarySoftColor)
            statY = headerBottom + 18
            self.drawSessionStat(statY, "time_icon", "Total Runtime", self.displayTime(totalSessionTime, ['d', 'h', 'm']), self.bodyColor)
            statY += 238
            self.drawSessionStat(statY, "honey_icon", "Final Honey", self.millify(finalHoney), self.honeyColor)
            statY += 238
            self.drawSessionStat(statY, "session_honey_icon", "Total Gained", self.millify(totalHoney), "#FDE395")
            statY += 238
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
            self.drawPanel(self.sidebarX, y2, self.sidebarPanelWidth, glancePanelHeight, accent=self.primaryColor, fill=self.tintedSurface(self.primaryColor, 0.08))
            headerBottom = self.drawSectionHeader(self.sidebarX + 50, y2 + 44, self.sidebarPanelWidth - 100, "STATS", "Total honey, averages, bugs, and vicious bees.", accent=self.primarySoftColor)
            self.drawSidebarMetricGrid(headerBottom + 24, glanceItems)

            y2 += glancePanelHeight + sectionGap
            taskPanelHeight = self.getTaskTimesPanelHeight(4)
            self.drawPanel(self.sidebarX, y2, self.sidebarPanelWidth, taskPanelHeight, accent=self.secondaryAccentColor, fill=self.tintedSurface(self.secondaryAccentColor, 0.06))
            headerBottom = self.drawSectionHeader(self.sidebarX + 50, y2 + 44, self.sidebarPanelWidth - 100, "ACTIVITY", "Where the macro spent the session.", accent=self.secondaryAccentColor)
            self.drawTaskTimes(headerBottom + 18, [
                {"label": "Gathering", "data": sessionStats.get("gathering_time", 0), "color": self.primarySoftColor},
                {"label": "Converting", "data": sessionStats.get("converting_time", 0), "color": self.honeyColor},
                {"label": "Bug Runs", "data": sessionStats.get("bug_run_time", 0), "color": self.secondaryAccentColor},
                {"label": "Other", "data": sessionStats.get("misc_time", 0), "color": "#6C5B4E"},
            ], totalSessionTime)

            y2 += taskPanelHeight + sectionGap
            questGroups = self.summarizeQuestCompletions(questCompletions)
            questPanelHeight = self.getQuestSummaryPanelHeight(len(questGroups))
            self.drawPanel(self.sidebarX, y2, self.sidebarPanelWidth, questPanelHeight, accent=(103, 253, 153), fill=self.tintedSurface((103, 253, 153), 0.08))
            headerBottom = self.drawSectionHeader(self.sidebarX + 50, y2 + 44, self.sidebarPanelWidth - 100, "QUESTS", "Turn-ins grouped by bee or bear for the whole session.", accent=(103, 253, 153))
            self.drawQuestSummary(headerBottom + 24, questGroups, accent=(103, 253, 153), emptyMessage="No completed quests were recorded this session.")
            y2 += questPanelHeight + sectionGap
        else:
            sessionPanelHeight = 980
            self.drawPanel(self.sidebarX, y2, self.sidebarPanelWidth, sessionPanelHeight, accent=self.primaryColor, fill=self.tintedSurface(self.primaryColor, 0.08))
            headerBottom = self.drawSectionHeader(self.sidebarX + 50, y2 + 44, self.sidebarPanelWidth - 100, "SESSION", "Current run totals outside the hourly slice.", accent=self.primarySoftColor)
            statY = headerBottom + 18
            self.drawSessionStat(statY, "time_icon", "Session Time", self.displayTime(sessionTime, ['d', 'h', 'm']), self.bodyColor)
            statY += 238
            self.drawSessionStat(statY, "honey_icon", "Current Honey", self.millify(currentHoney), self.honeyColor)
            statY += 238
            self.drawSessionStat(statY, "session_honey_icon", "Session Honey", self.millify(sessionHoney), "#FDE395")

            y2 += sessionPanelHeight + sectionGap
            glanceItems = [
                {"icon": "average_icon", "label": "Average / Hour", "value": self.millify(avgHoneyPerHour), "color": self.primaryColor},
                {"icon": "honey_icon", "label": "Honey This Hour", "value": self.millify(honeyThisHour), "color": self.honeyColor},
                {"icon": "kill_icon", "label": "Bugs Killed", "value": hourlyReportStats["bugs"], "color": (254, 101, 99)},
                {"icon": "vicious_bee_icon", "label": "Vicious Bees", "value": hourlyReportStats["vicious_bees"], "color": (132, 233, 254)}
            ]
            glancePanelHeight = self.getSidebarMetricPanelHeight(len(glanceItems))
            self.drawPanel(self.sidebarX, y2, self.sidebarPanelWidth, glancePanelHeight, accent=self.primaryColor, fill=self.tintedSurface(self.primaryColor, 0.08))
            headerBottom = self.drawSectionHeader(self.sidebarX + 50, y2 + 44, self.sidebarPanelWidth - 100, "LAST HOUR", "Hourly totals, bugs, and averages.", accent=self.primarySoftColor)
            self.drawSidebarMetricGrid(headerBottom + 24, glanceItems)

            y2 += glancePanelHeight + sectionGap
            taskPanelHeight = self.getTaskTimesPanelHeight(4)
            self.drawPanel(self.sidebarX, y2, self.sidebarPanelWidth, taskPanelHeight, accent=self.secondaryAccentColor, fill=self.tintedSurface(self.secondaryAccentColor, 0.06))
            headerBottom = self.drawSectionHeader(self.sidebarX + 50, y2 + 44, self.sidebarPanelWidth - 100, "ACTIVITY", "How the macro spent the last hour.", accent=self.secondaryAccentColor)
            self.drawTaskTimes(headerBottom + 18, [
                {"label": "Gathering", "data": hourlyReportStats["gathering_time"], "color": self.primarySoftColor},
                {"label": "Converting", "data": hourlyReportStats["converting_time"], "color": self.honeyColor},
                {"label": "Bug Run", "data": hourlyReportStats["bug_run_time"], "color": self.secondaryAccentColor},
                {"label": "Other", "data": hourlyReportStats["misc_time"], "color": "#6C5B4E"},
            ])
            y2 += taskPanelHeight + sectionGap

            questGroups = self.summarizeQuestCompletions(questCompletions)
            questPanelHeight = self.getQuestSummaryPanelHeight(len(questGroups))
            self.drawPanel(self.sidebarX, y2, self.sidebarPanelWidth, questPanelHeight, accent=(103, 253, 153), fill=self.tintedSurface((103, 253, 153), 0.08))
            headerBottom = self.drawSectionHeader(self.sidebarX + 50, y2 + 44, self.sidebarPanelWidth - 100, "QUESTS", "All recorded turn-ins grouped by quest owner for the past hour.", accent=(103, 253, 153))
            self.drawQuestSummary(headerBottom + 24, questGroups, accent=(103, 253, 153), emptyMessage="No completed quests were recorded this hour.")
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
            planterHeight = planterRows * 600 + max(0, planterRows - 1) * 40
            self.drawPanel(self.sidebarX, y2, self.sidebarPanelWidth, planterHeight + 250, accent=self.primaryColor, fill=self.tintedSurface(self.primaryColor, 0.07))
            headerBottom = self.drawSectionHeader(
                self.sidebarX + 50,
                y2 + 44,
                self.sidebarPanelWidth - 100,
                "PLANTERS",
                "Current placements carried into the final snapshot." if isFinalReport else "Current placements and ready times.",
                accent=self.primaryColor
            )
            self.drawPlanters(headerBottom + 18, planterNames, planterTimes, planterFields)
            y2 += planterHeight + 250 + sectionGap

        buffPanelHeight = 860
        self.drawPanel(self.sidebarX, y2, self.sidebarPanelWidth, buffPanelHeight, accent=self.secondaryAccentColor, fill=self.tintedSurface(self.secondaryAccentColor, 0.05))
        headerBottom = self.drawSectionHeader(self.sidebarX + 50, y2 + 44, self.sidebarPanelWidth - 100, "BUFFS", "Final captured stack values." if isFinalReport else "Latest captured stack values.", accent=self.secondaryAccentColor)
        self.drawBuffs(headerBottom + 30, buffQuantity)

        y2 += buffPanelHeight + sectionGap
        nectarPanelHeight = 960
        self.drawPanel(self.sidebarX, y2, self.sidebarPanelWidth, nectarPanelHeight, accent=self.honeyColor, fill=self.tintedSurface(self.honeyColor, 0.05))
        headerBottom = self.drawSectionHeader(self.sidebarX + 50, y2 + 44, self.sidebarPanelWidth - 100, "NECTARS", "Session-end field nectar percentages." if isFinalReport else "Field nectar percentages at render time.", accent=self.honeyColor)
        self.drawNectars(headerBottom + 38, nectarQuantity)

        if not isFinalReport and enabled_fields:
            y2 += nectarPanelHeight + sectionGap
            fieldPanelHeight = self.getFieldsPanelHeight(len(enabled_fields))
            self.drawPanel(self.sidebarX, y2, self.sidebarPanelWidth, fieldPanelHeight, accent=self.primarySoftColor, fill=self.tintedSurface(self.primaryColor, 0.05))
            headerBottom = self.drawSectionHeader(self.sidebarX + 50, y2 + 44, self.sidebarPanelWidth - 100, "FIELDS", "Enabled fields and their active patterns.", accent=self.primarySoftColor)
            self.drawFields(headerBottom + 24, enabled_fields, field_patterns)

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
