import cv2
import fuzzywuzzy
import fuzzywuzzy.process
from modules.misc.imageManipulation import average_hash
import numpy as np
import traceback
from PIL import Image
from difflib import SequenceMatcher
import modules.controls.mouse as mouse
import modules.misc.settingsManager as settingsManager
import modules.screen.ocr as ocr
from modules import bitmap_matcher
from modules.controls.sleep import pause_aware_time as time, sleep
from modules.macro.game_data import quest_data
from modules.screen.imageSearch import locateImageOnScreen
from modules.screen.screenshot import mssScreenshot, mssScreenshotNP, mssScreenshotPillowRGBA


class QuestMixin:
    def startQuestTaskWatch(self, taskKey):
        """Open and publish the quest tied to a non-gather quest task."""
        if not self.setdat.get("quest_progress_watch", False):
            return None

        normalizedTask = str(taskKey).replace("-", "_").replace(" ", "_").strip().lower()
        watchers = (getattr(self, "questTaskWatchers", {}) or {}).get(normalizedTask, [])
        if not watchers:
            return None

        completedObjectives = getattr(self, "completedQuestWatchObjectives", set())
        for questGiver, objective in watchers:
            identity = (normalizedTask, questGiver, objective)
            if identity in completedObjectives:
                continue

            menuOpen = False
            try:
                menuOpen = True
                visibleObjectives = self.findQuest(
                    questGiver,
                    keepQuestMenuOpen=True,
                    logDetection=False,
                )
                if visibleObjectives is None:
                    # findQuest closes the menu when the quest cannot be located.
                    return None
                if objective not in visibleObjectives:
                    self.toggleQuest()
                    self.moveMouseToDefault()
                    completedObjectives.add(identity)
                    continue

                startedAt = time.time()
                report = self.createLiveQuestProgressReport()
                report.start(
                    questGiver,
                    objective,
                    lambda: time.time() - startedAt,
                    lambda: self.run is not None and self.run.value == 6,
                    activity="Quest Progress",
                )
                self.moveMouseToDefault()
                self.logger.webhook(
                    "Live Quest Progress",
                    f"Watching {questGiver.title()}: {objective.replace('_', ' ').title()}",
                    "light blue",
                )
                return {
                    "task": normalizedTask,
                    "quest_giver": questGiver,
                    "objective": objective,
                    "report": report,
                    "menu_open": True,
                }
            except Exception:
                print(traceback.format_exc())
                if menuOpen:
                    self.toggleQuest()
                    self.moveMouseToDefault()
                return None

        self.completedQuestWatchTasks.add(normalizedTask)
        return {"skip_task": True, "task": normalizedTask}

    def markQuestTaskWatchCompleted(self, context):
        """Mark one objective done and skip the task only when no quest still needs it."""
        taskKey = context["task"]
        identity = (taskKey, context["quest_giver"], context["objective"])
        self.completedQuestWatchObjectives.add(identity)
        watchers = (getattr(self, "questTaskWatchers", {}) or {}).get(taskKey, [])
        allComplete = all(
            (taskKey, questGiver, objective) in self.completedQuestWatchObjectives
            for questGiver, objective in watchers
        )
        if allComplete:
            self.completedQuestWatchTasks.add(taskKey)
            self.logger.webhook(
                "Quest Task Complete",
                f"Skipping remaining {taskKey.replace('_', ' ').title()} runs; no watched quest still needs them.",
                "light green",
                "screen",
                route_category="quests",
            )
        else:
            self.logger.webhook(
                "Quest Objective Complete",
                f"{context['quest_giver'].title()} no longer needs {taskKey.replace('_', ' ').title()}; continuing for another active quest.",
                "light green",
                route_category="quests",
            )

    def finishQuestTaskWatch(self, context, checkCompletion=True):
        """Close a task watcher and report whether its objective just completed."""
        if not context:
            return False

        report = context.get("report")
        if report:
            report.stop()

        completed = False
        try:
            if checkCompletion and context.get("menu_open"):
                time.sleep(0.5)
                visibleObjectives = self.findQuest(
                    context["quest_giver"],
                    questScreens=[self.captureQuestWatchScreen()],
                    logDetection=False,
                )
                completed = (
                    visibleObjectives is not None
                    and context["objective"] not in visibleObjectives
                )
        except Exception:
            print(traceback.format_exc())
        finally:
            if context.get("menu_open"):
                self.toggleQuest()
            self.moveMouseToDefault()

        return completed

    def toggleQuest(self):
        #click quest icon
        mouse.moveTo(self.robloxWindow.mx+(80), self.robloxWindow.my+(113))
        time.sleep(0.1)
        mouse.moveBy(0,3)
        time.sleep(0.1)
        mouse.click()
        time.sleep(0.3)
        mouse.moveTo(self.robloxWindow.mx+(312), self.robloxWindow.my+(200))
        mouse.click()

    def captureQuestScreenshots(self, maxScreens=150):
        """
        Capture the quest list from top to bottom once.
        Returned RGBA screenshots can be reused by findQuest for multiple
        quest givers without reopening and rescrolling the quest UI.
        """
        def screenshotQuest(screenshotHeight, mode="gray"):
            mode = mode.lower()
            if mode == "rgba":
                screenshotFunction = mssScreenshotPillowRGBA
            else:
                screenshotFunction = mssScreenshotNP
            screen = screenshotFunction(self.robloxWindow.mx, self.robloxWindow.my+150, 300, min(screenshotHeight, self.robloxWindow.mh-(self.robloxWindow.my+150)))
            if mode == "gray":
                screen = cv2.cvtColor(screen, cv2.COLOR_BGRA2GRAY)
            return screen

        self.toggleInventory("close")
        self.toggleQuest()

        prevHash = None
        for _ in range(200):
            mouse.scroll(100)
            sleep(0.08)
            currentHash = average_hash(Image.fromarray(screenshotQuest(100)))
            if prevHash is not None and prevHash == currentHash:
                break
            prevHash = currentHash

        sleep(0.4)
        screens = []
        prevHash = None
        for _ in range(maxScreens):
            screens.append(screenshotQuest(800, mode="RGBA"))
            mouse.scroll(-1, True)
            time.sleep(0.06)
            currentHash = average_hash(Image.fromarray(screenshotQuest(100)))
            if prevHash is not None and prevHash == currentHash:
                break
            prevHash = currentHash

        self.toggleQuest()
        self.moveMouseToDefault()
        return screens

    def captureQuestWatchScreen(self):
        """Capture the visible quest section without scrolling or toggling its UI."""
        screenshotHeight = max(1, min(800, self.robloxWindow.mh - 150))
        return mssScreenshotPillowRGBA(
            self.robloxWindow.mx,
            self.robloxWindow.my + 150,
            300,
            screenshotHeight,
        )

    def findQuest(self, questGiver, questScreens=None, keepQuestMenuOpen=False, logDetection=True):
        #map quest giver to a shorthand form for ocr searching
        questGiverShort = {
            "polar bear": "polar",
            "bucko bee": "bucko",
            "riley bee": "riley",
            "honey bee": "honey",
            "brown bear": "brown",
            "black bear": "black"
        }

        #prevent the macro from false detecting beesmas quests
        questTitleBlacklistedPhrases = {
            "polar bear": ["beesmas", "feast", "beesmas feast"],
            "bucko bee": ["snow machine"],
            "riley bee": ["honeyday", "honeyday candles"],
            "honey bee": ["honey wreath"],
            "brown bear": ["stockings"],
            "black bear": ["honey wreath"]
        }

        def parseBrownBearTitleObjectives(titleText):
            import re

            text = self.convertCyrillic(titleText.lower())
            text = re.sub(r"^.*brown\s+bear[:\-\s]*", "", text).strip()

            abbrevToField = {
                "sun": "sunflower",
                "dand": "dandelion",
                "mush": "mushroom",
                "bluf": "blue flower",
                "clove": "clover",
                "bamb": "bamboo",
                "spide": "spider",
                "straw": "strawberry",
                "pinap": "pineapple",
                "stump": "stump",
                "cact": "cactus",
                "pump": "pumpkin",
                "pine": "pine tree",
                "rose": "rose",
                "mount": "mountain top",
                "coco": "coconut",
                "pepp": "pepper"
            }
            colorTokens = {"white", "blue", "red"}

            objectives = []
            for token in [t for t in re.split(r"[^a-z]+", text) if t]:
                if token in colorTokens:
                    objective = f"pollen_{token}"
                else:
                    field = abbrevToField.get(token)
                    if not field:
                        continue
                    objective = f"gather_{field}"
                if objective not in objectives:
                    objectives.append(objective)

            return objectives

        def findQuestSectionEnd(scanScreen, minOffset=0):
            """
            Return the y offset where the current quest card ends.
            The quest menu uses a full-width blue-gray divider before the next
            quest, followed by the pale title bar. Treat either as a hard stop
            so objective OCR cannot bleed into the next quest.
            """
            if scanScreen is None or scanScreen.size == 0:
                return None

            height = scanScreen.shape[0]
            minOffset = max(0, min(int(minOffset), height))
            minBandHeight = max(6, int(8*self.robloxWindow.multi))
            titleTargetColor = np.array([247, 240, 229], dtype=np.int16)
            titleTolerance = 5
            rows = scanScreen[minOffset:, :, :3].astype(np.int16)
            if rows.size == 0:
                return None

            titleMask = np.all(np.abs(rows - titleTargetColor) <= titleTolerance, axis=2)
            titleFractions = np.mean(titleMask, axis=1)

            rowMeans = np.mean(rows, axis=1)
            rowStds = np.mean(np.std(rows, axis=1), axis=1)
            rowChannelSpread = np.max(rowMeans, axis=1) - np.min(rowMeans, axis=1)
            rowBrightness = np.mean(rowMeans, axis=1)
            rowMax = np.max(rowMeans, axis=1)
            rowMin = np.min(rowMeans, axis=1)

            # Blue-gray separator bars are broad, fairly flat rows. Objective
            # backgrounds are also broad rows, so exclude strongly red/green
            # regions before accepting a gray divider.
            blue, green, red = rowMeans[:, 0], rowMeans[:, 1], rowMeans[:, 2]
            stronglyGreen = (green > red + 35) & (green > blue + 35)
            stronglyRed = (red > green + 35) & (red > blue + 35)
            grayBarRows = (
                (rowStds < 28) &
                (rowChannelSpread < 75) &
                (rowBrightness > 75) &
                (rowBrightness < 230) &
                (rowMax - rowMin > 8) &
                ~stronglyGreen &
                ~stronglyRed
            )
            titleRows = titleFractions > 0.45

            def findRuns(mask):
                runs = []
                runStart = None
                for idx, value in enumerate(mask):
                    if value and runStart is None:
                        runStart = idx
                    elif not value and runStart is not None:
                        if idx - runStart >= minBandHeight:
                            runs.append((runStart, idx))
                        runStart = None
                if runStart is not None and len(mask) - runStart >= minBandHeight:
                    runs.append((runStart, len(mask)))
                return runs

            titleRuns = findRuns(titleRows)
            directTitleBoundary = titleRuns[0][0] if titleRuns else None

            grayBoundary = None
            titleLookahead = max(minBandHeight, int(80*self.robloxWindow.multi))
            for grayStart, grayEnd in findRuns(grayBarRows):
                lookaheadEnd = min(len(titleRows), grayEnd + titleLookahead)
                titleRunsAfterGray = findRuns(titleRows[grayEnd:lookaheadEnd])
                if not titleRunsAfterGray:
                    continue

                titleStart = grayEnd + titleRunsAfterGray[0][0]
                betweenRows = rows[grayEnd:titleStart, :, :]
                if betweenRows.size:
                    blue, green, red = betweenRows[:, :, 0], betweenRows[:, :, 1], betweenRows[:, :, 2]
                    objectiveMask = (
                        ((green > 120) & (green > red + 20) & (green > blue + 20)) |
                        ((red > 120) & (red > green + 20) & (red > blue + 20))
                    )
                    objectiveRowsBetween = np.mean(objectiveMask, axis=1) > 0.30
                    if np.any(objectiveRowsBetween):
                        continue

                if titleRunsAfterGray:
                    grayBoundary = grayStart
                    break

            candidates = [x for x in (grayBoundary, directTitleBoundary) if x is not None]
            return minOffset + min(candidates) if candidates else None

        def regionHasIncompleteRed(region):
            if region is None or region.size == 0:
                return False

            rows = region[:, :, :3].astype(np.int16)
            blue, green, red = rows[:, :, 0], rows[:, :, 1], rows[:, :, 2]
            redMask = (red > 120) & (red > green + 20) & (red > blue + 20)
            if redMask.size == 0:
                return False

            redScore = float(np.mean(redMask))
            redRows = np.mean(redMask, axis=1)
            redCols = np.mean(redMask, axis=0)

            edgeWidth = max(8, int(24*self.robloxWindow.multi))
            leftEdge = redMask[:, :edgeWidth]
            rightEdge = redMask[:, max(0, redMask.shape[1] - edgeWidth):]
            edgeScore = max(
                float(np.mean(leftEdge)) if leftEdge.size else 0.0,
                float(np.mean(rightEdge)) if rightEdge.size else 0.0,
            )

            return (
                redScore > 0.012 or
                np.any(redRows > 0.06) or
                np.any(redCols > 0.35) or
                edgeScore > 0.015
            )

        def detectObjectivePanels(scanScreen):
            """Find objective rows by their red/green background panels."""
            if scanScreen is None or scanScreen.size == 0:
                return []

            rows = scanScreen[:, :, :3].astype(np.int16)
            blue, green, red = rows[:, :, 0], rows[:, :, 1], rows[:, :, 2]
            greenMask = (green > 120) & (green > red + 20) & (green > blue + 20)
            redMask = (red > 120) & (red > green + 20) & (red > blue + 20)
            greenFractions = np.mean(greenMask, axis=1)
            redFractions = np.mean(redMask, axis=1)

            panelRows = (greenFractions > 0.30) | (redFractions > 0.30)
            minPanelHeight = max(18, int(28*self.robloxWindow.multi))
            maxGap = 1

            runs = []
            runStart = None
            gap = 0
            for row, isPanel in enumerate(panelRows):
                if isPanel:
                    if runStart is None:
                        runStart = row
                    gap = 0
                elif runStart is not None:
                    gap += 1
                    if gap > maxGap:
                        runEnd = row - gap + 1
                        if runEnd - runStart >= minPanelHeight:
                            runs.append((runStart, runEnd))
                        runStart = None
                        gap = 0
            if runStart is not None and len(panelRows) - runStart >= minPanelHeight:
                runs.append((runStart, len(panelRows)))

            panels = []
            for y1, y2 in runs:
                region = scanScreen[y1:y2, :, :3]
                status = "incomplete" if regionHasIncompleteRed(region) else "complete"
                panels.append({
                    "y": y1,
                    "bbox": (0, y1, scanScreen.shape[1], y2 - y1),
                    "status": status,
                })
            return panels

        def extractQuestObjectiveChunks(screen, questTitleYPos):
            screenBgr = cv2.cvtColor(np.array(screen), cv2.COLOR_RGBA2BGR)
            screenCropped = screenBgr[questTitleYPos:, :]

            def findTitleBarColor(scanScreen, maxHeight):
                scan = scanScreen[:maxHeight, :]
                if scan.size == 0:
                    return None
                bestStd = None
                bestMean = None
                for row in range(scan.shape[0]):
                    rowPixels = scan[row]
                    rowStd = float(np.std(rowPixels, axis=0).mean())
                    if bestStd is None or rowStd < bestStd:
                        bestStd = rowStd
                        bestMean = np.mean(rowPixels, axis=0)
                if bestMean is None:
                    return None
                return [int(c) for c in bestMean]

            cropTargetColor = [247, 240, 229]
            cropColorTolerance = 3
            lower = np.array([c - cropColorTolerance for c in cropTargetColor], dtype=np.uint8)
            upper = np.array([c + cropColorTolerance for c in cropTargetColor], dtype=np.uint8)

            cropMask = cv2.inRange(screenCropped, lower, upper)
            cropRows = np.any(cropMask > 0, axis=1)
            startIndex = None
            endIndex = 0

            maxHeight = 20*self.robloxWindow.multi
            for i, hasColor in enumerate(cropRows):
                if i > maxHeight and startIndex is None:
                    break
                if hasColor and startIndex is None:
                    startIndex = i
                elif not hasColor and startIndex is not None:
                    endIndex = i
                    break

            if startIndex is None:
                # Fallback to a dynamically sampled title bar color.
                dynamicColor = findTitleBarColor(screenCropped, int(40*self.robloxWindow.multi))
                if dynamicColor:
                    cropColorTolerance = 6
                    lower = np.array([c - cropColorTolerance for c in dynamicColor], dtype=np.uint8)
                    upper = np.array([c + cropColorTolerance for c in dynamicColor], dtype=np.uint8)
                    cropMask = cv2.inRange(screenCropped, lower, upper)
                    cropRows = np.any(cropMask > 0, axis=1)
                    for i, hasColor in enumerate(cropRows):
                        if i > maxHeight and startIndex is None:
                            break
                        if hasColor and startIndex is None:
                            startIndex = i
                        elif not hasColor and startIndex is not None:
                            endIndex = i
                            break

            if endIndex:
                screenCropped = screenCropped[endIndex:, :]

            titleHeight = endIndex if endIndex else int(40*self.robloxWindow.multi)
            titleScreen = screenBgr[questTitleYPos:questTitleYPos+titleHeight, :]

            parseScreen = screenCropped
            displayScreen = screenCropped
            sectionEnd = findQuestSectionEnd(screenCropped, 20*self.robloxWindow.multi)
            if sectionEnd:
                parseScreen = screenCropped[:sectionEnd, :]

            screenGray = cv2.cvtColor(parseScreen, cv2.COLOR_BGR2GRAY)
            img = cv2.inRange(screenGray, 0, 50)
            img = cv2.GaussianBlur(img, (5, 5), 0)

            kernelSize = 10 if self.robloxWindow.isRetina else 7
            kernel = np.ones((kernelSize, kernelSize), np.uint8)
            img = cv2.dilate(img, kernel, iterations=1)

            contours, _ = cv2.findContours(img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            minArea = 4000*self.robloxWindow.multi
            maxArea = 40000*self.robloxWindow.multi
            maxHeight = 75*self.robloxWindow.multi

            chunks = []
            for contour in contours:
                x, y, w, h = cv2.boundingRect(contour)
                area = w*h
                if area < minArea or area > maxArea or h > maxHeight:
                    continue

                textImg = Image.fromarray(parseScreen[y:y+h, x:x+w])
                textChunk = []
                for line in ocr.ocrRead(textImg):
                    textChunk.append(self.convertCyrillic(line[1][0].strip().lower()))
                textChunk = ''.join(textChunk).strip()
                if textChunk:
                    chunks.append({"y": y, "text": textChunk, "bbox": (x, y, w, h)})

            chunks.sort(key=lambda item: item["y"])
            return titleScreen, displayScreen, parseScreen, chunks

        #sanity check
        if not questGiver in questGiverShort:
            raise Exception(f"Unknown Quest Giver: {questGiver}")
        
        def screenshotQuest(screenshotHeight, mode = "gray"):
            #Take a screenshot of the quest page
            mode = mode.lower()
            if mode == "rgba":
                screenshotFunction = mssScreenshotPillowRGBA
            else:
                screenshotFunction = mssScreenshotNP
            screen = screenshotFunction(self.robloxWindow.mx, self.robloxWindow.my+150, 300, min(screenshotHeight, self.robloxWindow.mh-(self.robloxWindow.my+150)))
            if mode == "gray":
                screen = cv2.cvtColor(screen, cv2.COLOR_BGRA2GRAY)
            return screen

        def ocrQuestTitleFromScreen(screen):
            cropHeight = min(300, screen.height)
            crop = screen.crop((0, 0, screen.width, cropHeight))
            bestMatch = None
            questTitleNoise = ["talk", "complete", "compete", "competer", "collect", "field", "pollen", "tokens", "defeat", "catch"]
            for bbox, (text, _conf) in ocr.ocrRead(crop):
                line = self.convertCyrillic(text.lower().strip())
                if not line:
                    continue
                if any(phrase in line for phrase in questTitleBlacklistedPhrases.get(questGiver, [])):
                    continue
                hasColon = ":" in line
                if any(noise in line for noise in questTitleNoise) and not hasColon:
                    continue
                if questGiver in line:
                    if not hasColon and not line.startswith(questGiver):
                        continue
                    score = 1.0 if hasColon else 0.7
                else:
                    score = SequenceMatcher(None, questGiver, line).ratio()
                if score < 0.65:
                    continue
                yPos = int(min(point[1] for point in bbox))
                if bestMatch is None or score > bestMatch[0]:
                    bestMatch = (score, line, yPos)
            return bestMatch
        
        manageQuestUi = questScreens is None
        #open inventory to ensure quest page is closed
        if manageQuestUi:
            self.toggleInventory("close")
            self.toggleQuest()
            #scroll to top
            #stop scrolling when the quest page remains unchanged
            prevHash = None
            for _ in range(200):
                mouse.scroll(100)
                sleep(0.08)
                hash = average_hash(Image.fromarray(screenshotQuest(100)))
                if not prevHash is None and prevHash == hash:
                    break
                prevHash = hash
        #scroll down, note the best match
        if manageQuestUi:
            sleep(0.4)
        questTitle = None
        questTitleYPos = None

        def buildScaledTemplates(image, scales, label):
            templates = []
            for scale in scales:
                if scale == 1.0:
                    templates.append((scale, image, label))
                    continue
                width = max(1, int(image.size[0] * scale))
                height = max(1, int(image.size[1] * scale))
                templates.append((scale, image.resize((width, height), Image.LANCZOS), label))
            return templates

        primaryScales = [1.0, 1.2, 1.1, 0.9, 0.8, 0.7, 1.3]

        questGiverTemplates = []
        questGiverImg = Image.open(f"./images/quest/{questGiver}-{self.robloxWindow.display_type}.png").convert('RGBA')
        questGiverTemplates.extend(buildScaledTemplates(questGiverImg, primaryScales, self.robloxWindow.display_type))

        fallbackDisplayType = "built-in" if self.robloxWindow.display_type == "retina" else "retina"
        fallbackScales = primaryScales if fallbackDisplayType == "built-in" else [0.7]
        try:
            fallbackImg = Image.open(f"./images/quest/{questGiver}-{fallbackDisplayType}.png").convert('RGBA')
            questGiverTemplates.extend(buildScaledTemplates(fallbackImg, fallbackScales, fallbackDisplayType))
        except Exception:
            pass
        prevHash = None
        screenSource = questScreens if questScreens is not None else range(150)
        for i, screenEntry in enumerate(screenSource):
            screen = screenEntry if questScreens is not None else screenshotQuest(800, mode="RGBA")

            ocrMatch = ocrQuestTitleFromScreen(screen)
            if ocrMatch:
                _score, questTitleRaw, questTitleYPos = ocrMatch
                if ":" in questTitleRaw:
                    questTitleRaw = questTitleRaw.split(":", 1)[1].strip()
                if questGiver == "brown bear":
                    questTitle = questTitleRaw
                else:
                    questTitle, _ = fuzzywuzzy.process.extractOne(questTitleRaw, quest_data[questGiver].keys())
                if logDetection:
                    self.logger.webhook("", f"Quest Title: {questTitle}", "dark brown")
                break

            res = None
            matchedTemplate = None
            for scale, template, label in questGiverTemplates:
                res = bitmap_matcher.find_bitmap_cython(screen, template, variance=7, h=300, w=template.size[0]) #searching only the top 250 pixels to avoid false matches in the quest description, since the quest giver is always above that. variance is set to 5 to allow for some minor color differences but not too much to cause false positives, since the template is a solid color image of the quest giver's name.
                if res:
                    matchedTemplate = template
                    break
            if res:
                rx, ry = res
                rw, rh = matchedTemplate.size
                img = cv2.cvtColor(np.array(screen), cv2.COLOR_RGBA2GRAY) 
                img = img[ry-10:ry+rh+20, rx-5:] 
                img = cv2.threshold(img, 150, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
                img = cv2.GaussianBlur(img, (5, 5), 0)
                img = Image.fromarray(img)
                
                ocrRes = ocr.ocrRead(img)
                text = self.convertCyrillic(''.join([x[1][0].strip().lower() for x in ocrRes]))
                for word in questTitleBlacklistedPhrases.get(questGiver, []):
                    if word in text:
                        break
                else:
                    questTitleYPos = ry
                    if logDetection:
                        print(questTitleYPos)
                    if questGiver == "brown bear":
                        questTitle = text
                    else:
                        questTitle, _ = fuzzywuzzy.process.extractOne(text, quest_data[questGiver].keys())
                    if logDetection:
                        self.logger.webhook("", f"Quest Title: {questTitle}", "dark brown")
                    break
                
            if manageQuestUi:
                mouse.scroll(-1, True)
                time.sleep(0.06)
                hash = average_hash(Image.fromarray(screenshotQuest(100)))
                if not prevHash is None and prevHash == hash:
                    break
                prevHash = hash

        if questTitle is None:
            if logDetection:
                self.logger.webhook("", f"Could not find {questGiver} quest", "dark brown")
            if manageQuestUi:
                self.toggleQuest()
                self.moveMouseToDefault()
            return None

        def objectiveTextShowsIncompleteProgress(textChunk):
            import re

            normalized = textChunk.replace(",", "").replace(" ", "")
            for currentRaw, totalRaw in re.findall(r"(\d+)\s*/\s*(\d+)", normalized):
                try:
                    if int(currentRaw) < int(totalRaw):
                        return True
                except ValueError:
                    continue
            return False
        
        if questGiver == "brown bear":
            titleScreen, objectiveScreen, parseScreen, objectiveChunks = extractQuestObjectiveChunks(screen, questTitleYPos)
            incompleteObjectives = []
            completedObjectives = []

            annotatedScreen = np.copy(objectiveScreen)

            def cleanBrownObjectiveText(textChunk):
                import re

                # Brown Bear objectives are detected from title-like bitmaps in
                # Natro. For OCR, remove status words before mapping the action.
                return re.split(r'\bcomplete\b', textChunk, maxsplit=1, flags=re.IGNORECASE)[0].strip()

            def brownObjectivesNamedInText(textChunk):
                """Return title objectives explicitly identified by an OCR row.

                Brown Bear quest titles encode the exact objectives in order. OCR
                can miss an entire panel, so a shortened detection list must not
                be used to shift later panels onto earlier title objectives.
                """
                import re

                normalized = self.convertCyrillic(textChunk.lower())
                words = set(re.sub(r"[^a-z]+", " ", normalized).split())
                matches = []
                for objective in titleObjectives:
                    kind, target = objective.split("_", 1)
                    if kind == "pollen":
                        if target in words and "pollen" in words:
                            matches.append(objective)
                    elif kind == "gather" and all(word in words for word in target.replace("_", " ").split()):
                        matches.append(objective)
                return matches

            def getBrownPanelStatus(panel, textChunk):
                if objectiveTextShowsIncompleteProgress(textChunk):
                    return "incomplete"

                x, y, w, h = panel["bbox"]
                region = parseScreen[y:y+h, x:x+w, :3]
                if region.size:
                    if regionHasIncompleteRed(region):
                        return "incomplete"
                    rows = region.astype(np.int16)
                    blue, green, red = rows[:, :, 0], rows[:, :, 1], rows[:, :, 2]
                    greenMask = (green > 120) & (green > red + 20) & (green > blue + 20)
                    greenScore = float(np.mean(greenMask))
                    if greenScore > 0.25:
                        return "complete"

                if "complete" in textChunk.lower():
                    return "complete"
                return panel["status"]

            brownPanels = detectObjectivePanels(parseScreen)
            brownItems = []

            titleObjectives = parseBrownBearTitleObjectives(questTitle)

            if brownPanels:
                for panel in brownPanels[:4]:
                    x, y, w, h = panel["bbox"]
                    textImg = Image.fromarray(parseScreen[y:y+h, x:x+w])
                    textChunk = []
                    for line in ocr.ocrRead(textImg):
                        textChunk.append(self.convertCyrillic(line[1][0].strip().lower()))
                    textChunk = ''.join(textChunk).strip()
                    brownItems.append({
                        "text": textChunk,
                        "bbox": panel["bbox"],
                        "status": getBrownPanelStatus(panel, textChunk),
                    })
            else:
                # Fallback for unusual themes or OCR captures where colored
                # panels were not found.
                for chunk in objectiveChunks:
                    textChunk = chunk["text"]
                    x, y, w, h = chunk["bbox"]
                    padY = max(8, int(12*self.robloxWindow.multi))
                    y1 = max(0, y - padY)
                    y2 = min(parseScreen.shape[0], y + h + padY)
                    region = parseScreen[y1:y2, :, :3]
                    status = "incomplete"
                    if objectiveTextShowsIncompleteProgress(textChunk):
                        status = "incomplete"
                    elif region.size:
                        if regionHasIncompleteRed(region):
                            status = "incomplete"
                        else:
                            rows = region.astype(np.int16)
                            blue, green, red = rows[:, :, 0], rows[:, :, 1], rows[:, :, 2]
                            greenMask = (green > 120) & (green > red + 20) & (green > blue + 20)
                            if float(np.mean(greenMask)) > 0.25 or "complete" in textChunk.lower():
                                status = "complete"
                    brownItems.append({
                        "text": textChunk,
                        "bbox": chunk["bbox"],
                        "status": status,
                    })

            for item in brownItems:
                textChunk = item["text"]
                x, y, w, h = item["bbox"]
                isComplete = item["status"] == "complete"
                itemIndex = len(incompleteObjectives) + len(completedObjectives)

                # Skip standalone completion labels so they don't register as objectives.
                if itemIndex >= len(titleObjectives) and isComplete and len(textChunk.split()) < 5:
                    continue

                # Identify the objective by the field/color named in its own
                # panel.  Position is only a safe fallback when no panels were
                # missed, otherwise a missing middle row shifts every later row.
                mappedObjectives = brownObjectivesNamedInText(textChunk)
                if not mappedObjectives and len(brownItems) == len(titleObjectives):
                    mappedObjectives = [titleObjectives[itemIndex]]
                elif not mappedObjectives and len(brownItems) != len(titleObjectives):
                    parseText = cleanBrownObjectiveText(textChunk)
                    parsedObjective = self.parseQuestObjective(parseText)
                    mappedObjectives = [
                        objective for objective in self.mapObjectiveToMacroAction(parsedObjective, parseText)
                        if objective in titleObjectives
                    ]

                if not isComplete:
                    for objective in mappedObjectives:
                        if objective not in incompleteObjectives:
                            incompleteObjectives.append(objective)
                else:
                    for objective in mappedObjectives:
                        if objective not in completedObjectives:
                            completedObjectives.append(objective)

                label = ", ".join(mappedObjectives) if mappedObjectives else textChunk
                color = (0, 255, 0) if isComplete else (0, 0, 255)
                cv2.rectangle(annotatedScreen, (x, y), (x+w, y+h), color, 2)
                cv2.putText(annotatedScreen, label, (x, max(0, y-5)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

            # A title objective with no positively identified panel is treated as
            # incomplete. This is conservative, but it prevents OCR loss from
            # assigning another row's completion state to it.
            for objective in titleObjectives:
                if objective not in incompleteObjectives and objective not in completedObjectives:
                    incompleteObjectives.append(objective)

            questImgPath = "latest-quest.png"
            screenshotStack = annotatedScreen
            if titleScreen is not None and titleScreen.size:
                screenshotStack = np.vstack([titleScreen, annotatedScreen])
            if logDetection:
                cv2.imwrite(questImgPath, screenshotStack)
                self.logger.webhook(
                    f"Detected Brown Bear Quest: {questTitle.title()}",
                    "**Completed Objectives:**\n{}\n\n**Incomplete Objectives:**\n{}".format(
                        '\n'.join(completedObjectives) if completedObjectives else "None",
                        '\n'.join(incompleteObjectives) if incompleteObjectives else "None"
                    ),
                    "light blue",
                    imagePath=questImgPath
                )
            # record the detected quest title for external callers
            try:
                if not hasattr(self, '_last_quest_title'):
                    self._last_quest_title = {}
                self._last_quest_title[questGiver] = questTitle
            except Exception:
                pass

            if manageQuestUi and not keepQuestMenuOpen:
                self.toggleQuest()
                self.moveMouseToDefault()
            return incompleteObjectives

        #quest title found, now find the objectives
        # record the detected quest title for external callers
        try:
            if not hasattr(self, '_last_quest_title'):
                self._last_quest_title = {}
            self._last_quest_title[questGiver] = questTitle
        except Exception:
            pass

        objectives = list(quest_data[questGiver][questTitle])
        maxObjectiveScanHeight = int(((len(objectives) * 110) + 60) * self.robloxWindow.multi)

        #merge the texts into chunks. Using those chunks, compare it with the known objectives
        #assume that the merging is done properly, so 1st chunk = 1st objective
        screen = cv2.cvtColor(np.array(screen), cv2.COLOR_RGBA2BGR)
        #crop it just above the quest title
        screen = screen[questTitleYPos: , : ]
        screenOriginal = np.copy(screen)

        #crop it below the quest title, to the first objective
        #this is done by detecting the color of the title bar, since relying on ocr's bounding box can cause it to overcrop
        cropTargetColor = [247, 240, 229]
        cropColorTolerance = 3
        lower = np.array([c - cropColorTolerance for c in cropTargetColor], dtype=np.uint8)
        upper = np.array([c + cropColorTolerance for c in cropTargetColor], dtype=np.uint8)

        #create a mask for the target color
        cropMask = cv2.inRange(screen, lower, upper)
        cropRows = np.any(cropMask > 0, axis=1)
        startIndex = None
        endIndex = 0

        #start searching for the start and end y points of the quest title
        #if it can't find the title bar in the first y pixels, stop the search
        #in some cases, the questTitleYPos already crops below the quest title
        maxHeight = 20*self.robloxWindow.multi
        for i, hasColor in enumerate(cropRows):
            if i > maxHeight and startIndex is None:
                break
            if hasColor and startIndex is None:
                #found the starting point of the first quest title area
                startIndex = i
            elif not hasColor and startIndex is not None:
                #found the ending point of the quest title area
                endIndex = i
                break
        
        #crop
        if endIndex:
            screen = screen[endIndex:, :]
        sectionEnd = findQuestSectionEnd(screen, 60*self.robloxWindow.multi)
        if sectionEnd:
            screen = screen[:sectionEnd, :]
        screen = screen[:min(screen.shape[0], maxObjectiveScanHeight), :]

        #convert to grayscale
        screenGray = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY)
        img = cv2.inRange(screenGray, 0, 50)
        img = cv2.GaussianBlur(img, (5, 5), 0)
        #dilute the image so that texts can be merged into chunks
        kernelSize = 10 if self.robloxWindow.isRetina else 7
        kernel = np.ones((kernelSize, kernelSize), np.uint8) 
        img = cv2.dilate(img, kernel, iterations=1)

        contours, _ = cv2.findContours(img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        #filter out the contour sizes
        minArea = 4000*self.robloxWindow.multi       #too small = noise
        maxArea = 40000*self.robloxWindow.multi     #too big = background or large UI elements
        maxHeight = 75*self.robloxWindow.multi       #cap height to filter out title bar

        indexedContours = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            indexedContours.append((y, contour))
        indexedContours.sort(key=lambda item: item[0])

        objectiveTextChunks = []
        for _, contour in indexedContours:
            x, y, w, h = cv2.boundingRect(contour)
            area = w*h
            if area < minArea or area > maxArea or h > maxHeight:
                continue
            textImg = Image.fromarray(screen[y:y+h, x:x+w])
            textChunk = []
            for line in ocr.ocrRead(textImg):
                textChunk.append(self.convertCyrillic(line[1][0].strip().lower()))
            textChunk = ''.join(textChunk)
            if textChunk:
                objectiveTextChunks.append(textChunk)

        completedObjectives = []
        incompleteObjectives = []
        objectivePanels = detectObjectivePanels(screen)

        def getPanelStatusFromRegion(y1, y2):
            y1 = max(0, min(int(y1), screen.shape[0]))
            y2 = max(y1, min(int(y2), screen.shape[0]))
            if y2 <= y1:
                return None

            region = screen[y1:y2, :]
            rows = region[:, :, :3].astype(np.int16)
            if rows.size == 0:
                return None
            if regionHasIncompleteRed(region):
                return "incomplete"
            blue, green, red = rows[:, :, 0], rows[:, :, 1], rows[:, :, 2]
            greenMask = (green > 120) & (green > red + 20) & (green > blue + 20)
            greenScore = float(np.mean(greenMask))
            if greenScore > 0.25:
                return "complete"
            return None

        if objectivePanels:
            for i, panel in enumerate(objectivePanels[:len(objectives)]):
                x, y, w, h = panel["bbox"]
                textImg = Image.fromarray(screen[y:y+h, x:x+w])
                textChunk = []
                for line in ocr.ocrRead(textImg):
                    textChunk.append(self.convertCyrillic(line[1][0].strip().lower()))
                textChunk = ''.join(textChunk)
                if logDetection:
                    print(textChunk)

                objectiveData = objectives[i].split("_")
                if objectiveData[0] == "feed":
                    amount = 0
                    if "/" in textChunk:
                        split = textChunk.split("/")[1].replace(",", "").replace(".", "")
                        amount = int(split) if split.isdigit() else 0
                    if not amount:
                        words = textChunk.split(" ")
                        for word in words:
                            if word.isdigit():
                                amount = int(word)
                                break
                    if amount:
                        objectiveData[1] = str(min(int(amount), 50))
                        objectives[i] = "_".join(objectiveData)

                if "complete" in textChunk:
                    panel["status"] = "complete"
                if objectiveTextShowsIncompleteProgress(textChunk):
                    panel["status"] = "incomplete"

                if panel["status"] == "complete":
                    completedObjectives.append(objectives[i])
                    color = (0, 255, 0)
                else:
                    incompleteObjectives.append(objectives[i])
                    color = (0, 0, 255)

                drawY = y+endIndex
                cv2.rectangle(screenOriginal, (x, drawY), (x+w, drawY+h), color, 2)
                cv2.putText(screenOriginal, objectives[i], (x, max(0, drawY-10)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

            # If the bottom row is clipped or visually missed, still preserve the
            # known quest objective instead of dropping it from the task list.
            for missingIndex, missingObjective in enumerate(objectives[len(objectivePanels):], start=len(objectivePanels)):
                if missingObjective not in completedObjectives and missingObjective not in incompleteObjectives:
                    if missingIndex < len(objectiveTextChunks) and "complete" in objectiveTextChunks[missingIndex]:
                        completedObjectives.append(missingObjective)
                    else:
                        status = None
                        if objectivePanels:
                            panelHeights = [panel["bbox"][3] for panel in objectivePanels]
                            estimatedHeight = int(np.median(panelHeights))
                            if len(objectivePanels) >= 2:
                                panelStarts = [panel["bbox"][1] for panel in objectivePanels]
                                estimatedSpacing = int(np.median(np.diff(panelStarts)))
                                estimatedY = objectivePanels[-1]["bbox"][1] + estimatedSpacing * (missingIndex - len(objectivePanels) + 1)
                            else:
                                estimatedGap = max(8, int(14*self.robloxWindow.multi))
                                estimatedY = objectivePanels[-1]["bbox"][1] + objectivePanels[-1]["bbox"][3] + estimatedGap
                            status = getPanelStatusFromRegion(estimatedY, estimatedY + estimatedHeight)

                        if status == "complete":
                            completedObjectives.append(missingObjective)
                        else:
                            incompleteObjectives.append(missingObjective)
        else:
            i = 0
            for _, contour in indexedContours:
                x, y, w, h = cv2.boundingRect(contour)
                #check if contour meets size requirements
                area = w*h
                if area < minArea or area > maxArea or h > maxHeight:
                    cv2.rectangle(screen, (x, y), (x+w, y+h), (0, 255, 255), 1) #draw a yellow bounding box
                    continue
                textImg =  Image.fromarray(screen[y:y+h, x:x+w])
                textChunk = []
                for line in ocr.ocrRead(textImg):
                    textChunk.append(self.convertCyrillic(line[1][0].strip().lower()))
                textChunk = ''.join(textChunk)
                if logDetection:
                    print(textChunk)

                #detect amount of items to feed
                objectiveData = objectives[i].split("_")
                if objectiveData[0] == "feed":
                    amount = 0
                    #start by trying to get the text from the progression, ie 0/x
                    if "/" in textChunk: 
                        split = textChunk.split("/")[1].replace(",","").replace(".", "")
                        amount = int(split) if split.isdigit() else 0
                    #find it via words, ie feed x bluberries
                    if not amount:
                        words = textChunk.split(" ")
                        for word in words:
                            if word.isdigit():
                                amount = int(word)
                                break
                    if amount:
                        objectiveData[1] = str(min(int(amount), 50))
                        objectives[i] = "_".join(objectiveData)

                if "complete" in textChunk:
                    completedObjectives.append(objectives[i])
                    color = (0, 255, 0)  #green
                elif objectiveTextShowsIncompleteProgress(textChunk):
                    incompleteObjectives.append(objectives[i])
                    color = (0, 0, 255)  #red
                else:
                    incompleteObjectives.append(objectives[i])
                    color = (0, 0, 255)  #red
                
                #draw bounding boxes and add the quest text
                drawY = y+endIndex
                if logDetection:
                    print(drawY)
                cv2.rectangle(screenOriginal, (x, drawY), (x+w, drawY+h), color, 2)
                cv2.putText(screenOriginal, objectives[i], (x, drawY-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

                i += 1

                if i == len(objectives):
                    break

        for objective in objectives:
            if objective not in completedObjectives and objective not in incompleteObjectives:
                incompleteObjectives.append(objective)
        
        questImgPath = "latest-quest.png"
        if logDetection:
            cv2.imwrite(questImgPath, screenOriginal)
            print(completedObjectives)
            print(incompleteObjectives)
            self.logger.webhook(f"Detected {questGiver.title()} Quest: {questTitle.title()}",
                                "**Completed Objectives:**\n{}\n\n**Incomplete Objectives:**\n{}".format(
                                    '\n'.join(completedObjectives) if completedObjectives else "None",
                                    '\n'.join(incompleteObjectives) if incompleteObjectives else "None"),
                                "light blue", imagePath=questImgPath)
        if manageQuestUi and not keepQuestMenuOpen:
            self.toggleQuest()
            self.moveMouseToDefault()
        return incompleteObjectives

    def goToQuestGiver(self, questGiver, reason):
        for _ in range(3):
            if not self.travelViaCannon(questGiver.title()):
                return False
            self.logger.webhook("",f"Travelling: {questGiver} ({reason}) ","brown")
            self.runPath(f"quests/{questGiver}")
            self.location = "quest"
            time.sleep(0.5)

            #check if player reached the quest giver
            if self.isBesideE(["talk"] + questGiver.lower().split(" "), log=True):
                self.logger.webhook("",f"Reached {questGiver}","brown", "screen")
                self.keyboard.press("e")
                sleep(0.2)
                self.keyboard.press("e")
                return True
            else:
                self.logger.webhook("",f"Failed to reach {questGiver}","brown", "screen")
                self.reset()
        return False

    def clickdialog(self, mustFindDialog=False):
        # Find dialog image and compute a click/sample location
        dialogImgRef = self.adjustImage("./images/menu", "dialog")
        x = self.robloxWindow.mw // 2
        y = int(self.robloxWindow.mh * 2 / 3)
        a = locateImageOnScreen(dialogImgRef, self.robloxWindow.mx + (x), self.robloxWindow.my + (y), 300, self.robloxWindow.mh // 3, 0.8 if mustFindDialog else 0.5)
        if a:
            _, loc = a
            xr, yr = [j // self.robloxWindow.multi for j in loc]
        else:
            xr = 0
            yr = 0
            if mustFindDialog:
                return
            print("unable to locate dialog position")

        # Adaptive sample size based on window size (try both small and larger samples)
        sample_w = max(40, min(160, int(self.robloxWindow.mw * 0.06)))
        sample_h = max(40, min(160, int(self.robloxWindow.mh * 0.06)))

        sx = self.robloxWindow.mx + x + xr - sample_w // 2
        sy = self.robloxWindow.my + y + yr - sample_h // 2

        def clamp_region(px, py, w, h):
            px = max(self.robloxWindow.mx, min(px, self.robloxWindow.mx + self.robloxWindow.mw - w))
            py = max(self.robloxWindow.my, min(py, self.robloxWindow.my + self.robloxWindow.mh - h))
            return px, py, w, h

        def screenshotDialog():
            px, py, w, h = clamp_region(sx, sy, sample_w, sample_h)
            try:
                return average_hash(mssScreenshot(px, py, w, h))
            except Exception:
                # fallback to a very small safe capture
                try:
                    return average_hash(mssScreenshot(self.robloxWindow.mx + self.robloxWindow.mw // 2, self.robloxWindow.my + self.robloxWindow.mh // 2, 10, 10))
                except Exception:
                    return average_hash(mssScreenshot(self.robloxWindow.mx, self.robloxWindow.my, 1, 1))

        # Move cursor away before taking baseline to avoid cursor overlay affecting the hash
        mouse.moveTo(self.robloxWindow.mx + 10, self.robloxWindow.my + 10)
        time.sleep(0.12)
        baseline = screenshotDialog()

        # Move to dialog click point and click repeatedly until a stable visible change is detected
        mouse.moveTo(self.robloxWindow.mx + (self.robloxWindow.mw // 2), self.robloxWindow.my + (y + yr - 20))
        change_threshold = 30
        for _ in range(80):
            mouse.click()
            time.sleep(0.12)
            img = screenshotDialog()
            diff = abs(img - baseline)
            if diff > change_threshold:
                # confirm the change with a second sample to avoid transient false positives
                time.sleep(0.05)
                if abs(screenshotDialog() - baseline) > change_threshold:
                    break

    def getNewQuest(self, questGiver, submitQuest):
        if not self.goToQuestGiver(questGiver, "Submit Quest" if submitQuest else "Get New Quest"): return
        self.clickdialog()
        #player submitted a quest, then get a new one
        if True: #submitQuest:
            sleep(1)
            self.keyboard.press("e")
            sleep(0.2)
            self.keyboard.press("e")
            self.clickdialog()
        self.reset()
        questObjective = self.findQuest(questGiver)
        # Timed bear quest handling: only start the 1-hour timer when the player
        # submitted a quest and there is NOT a new quest shown in the menu.
        if questGiver in ["brown bear", "black bear"]:
            state_key = f"{questGiver.replace(' ', '_')}_quest_state"
            timing_key = f"{questGiver.replace(' ', '_')}_quest_cd"
            try:
                # If we were submitting a quest (submitQuest True), and after submit
                # there's no new quest shown, start the timer and set state to 1
                if submitQuest:
                    if questObjective is None:
                        self.saveTiming(timing_key)
                        settingsManager.saveSettingFile(state_key, 1, settingsManager.getUserDataPath("timings.txt"))
                    else:
                        # A new quest appeared immediately after submitting - remain in state 0
                        settingsManager.saveSettingFile(state_key, 0, settingsManager.getUserDataPath("timings.txt"))
                else:
                    # When simply getting a new quest, ensure state is 0
                    if questObjective is not None:
                        settingsManager.saveSettingFile(state_key, 0, settingsManager.getUserDataPath("timings.txt"))
            except Exception:
                pass
        return questObjective
