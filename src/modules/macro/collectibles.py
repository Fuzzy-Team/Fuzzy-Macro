from modules.misc.imageManipulation import average_hash
import math
import pyautogui as pag
import re
import threading
from datetime import timedelta
import modules.controls.mouse as mouse
import modules.misc.settingsManager as settingsManager
from modules.misc.settings_defaults import glitter_slot, glitter_slot_label
import modules.screen.ocr as ocr
from modules.controls.sleep import pause_aware_time as time, sleep
from modules.macro.game_data import (
    BLENDER_ITEM_SLOTS,
    blenderItems,
    fieldBoosterData,
    mergedCollectData,
    startLocationDimensions,
    windShrineDonationItems,
)
from modules.screen.imageSearch import locateImageOnScreen, locateTransparentImageOnScreen
from modules.screen.screenshot import mssScreenshot


class CollectiblesMixin:
    def collectWindShrine(self, reached):
        displayName = "Wind Shrine"
        cooldownSeconds = self.collectCooldowns["wind_shrine"]
        elapsed = time.time() - self.getTiming("wind_shrine")
        if elapsed < cooldownSeconds:
            remaining = int(cooldownSeconds - elapsed)
            self.logger.webhook("", f"{displayName} is on cooldown ({timedelta(seconds=remaining)} remaining)", "dark brown", "screen")
            return None

        def normalizeShrineItemName(value):
            text = self.convertCyrillic(str(value or "").replace("_", " ").lower())
            return ''.join(ch for ch in text if ch.isalnum())

        def getShrineItemAliases(value):
            normalizedValue = normalizeShrineItemName(value)
            aliases = {normalizedValue}
            for knownItem in windShrineDonationItems:
                if normalizeShrineItemName(knownItem) == normalizedValue:
                    aliases.add(normalizeShrineItemName(knownItem))
                    continue
                if normalizedValue and normalizedValue in normalizeShrineItemName(knownItem):
                    aliases.add(normalizeShrineItemName(knownItem))
            if normalizedValue.endswith("y"):
                aliases.add(normalizedValue[:-1] + "ies")
            elif normalizedValue.endswith("s"):
                aliases.add(normalizedValue[:-1])
            else:
                aliases.add(normalizedValue + "s")
            return [alias for alias in aliases if alias]

        def readSelectedShrineItem(nameX, nameY, nameW, nameH):
            itemTextImg = mssScreenshot(nameX, nameY, nameW, nameH)
            textParts = []
            for _bbox, (text, _conf) in ocr.ocrRead(itemTextImg):
                try:
                    textParts.append(text)
                except Exception:
                    continue
            return normalizeShrineItemName(" ".join(textParts))

        def shrineScaleX(value):
            return math.floor(value * (self.robloxWindow.mw / 1920))

        def shrineScaleY(value):
            return math.floor(value * (self.robloxWindow.mh / 1080))

        def clickWindShrineDialogsUntilGone():
            dialogImg = self.adjustImage("./images/menu", "dialog")
            searchX = self.robloxWindow.mx + math.floor(0.25 * self.robloxWindow.mw)
            searchY = self.robloxWindow.my + math.floor(0.55 * self.robloxWindow.mh)
            searchW = math.floor(0.5 * self.robloxWindow.mw)
            searchH = math.floor(0.4 * self.robloxWindow.mh)
            clickX = self.robloxWindow.mx + self.robloxWindow.mw // 2
            clickY = self.robloxWindow.my + math.floor(0.82 * self.robloxWindow.mh)
            consecutiveMisses = 0

            for _ in range(80):
                dialogVisible = False
                result = locateTransparentImageOnScreen(dialogImg, searchX, searchY, searchW, searchH, 0.65)
                if result:
                    dialogVisible = True
                    _score, loc = result
                    clickY = searchY + loc[1] + shrineScaleY(35)
                else:
                    try:
                        dialogText = ''.join([x[1][0] for x in ocr.ocrRead(mssScreenshot(searchX, searchY, searchW, searchH))]).lower()
                        dialogVisible = any(text in dialogText for text in ("wind shrine", "click to continue", "blown", "whirlwind"))
                    except Exception:
                        dialogVisible = False

                if not dialogVisible:
                    consecutiveMisses += 1
                    if consecutiveMisses >= 3:
                        break
                    time.sleep(0.15)
                    continue

                consecutiveMisses = 0
                mouse.moveTo(clickX, clickY)
                mouse.click()
                time.sleep(0.2)

            # One final generic dialog pass catches any follow-up line that appears
            # after the Wind Shrine-specific text has advanced.
            for _ in range(3):
                result = locateTransparentImageOnScreen(dialogImg, searchX, searchY, searchW, searchH, 0.65)
                if not result:
                    break
                _score, loc = result
                mouse.moveTo(clickX, searchY + loc[1] + shrineScaleY(35))
                mouse.click()
                time.sleep(0.2)

        def lootWindShrineTokens():
            self.keyboard.tileWalk("d", 11)
            self.keyboard.tileWalk("w", 4.5)
            for _ in range(4):
                self.keyboard.tileWalk("a", 5)
                self.keyboard.tileWalk("s", 1.5)
                self.keyboard.tileWalk("d", 5)
                self.keyboard.tileWalk("s", 1.5)
            for _ in range(2):
                self.keyboard.tileWalk("a", 15)
                self.keyboard.tileWalk("w", 1)
                self.keyboard.tileWalk("d", 15)
                self.keyboard.tileWalk("w", 1)
            self.keyboard.tileWalk("a", 17)
            for _ in range(4):
                self.keyboard.tileWalk("w", 1.5)
                self.keyboard.tileWalk("d", 5)
                self.keyboard.tileWalk("w", 1.5)
                self.keyboard.tileWalk("a", 5)


        item = str(self.setdat.get("wind_shrine_item", "field dice")).replace("_", " ").lower()
        itemAliases = getShrineItemAliases(item)
        quantity = max(1, int(self.setdat.get("wind_shrine_quantity", 1) or 1))
        time.sleep(2)

        # Open the shrine item selector from the initial dialog.
        mouse.moveTo(self.robloxWindow.mx + self.robloxWindow.mw // 2, self.robloxWindow.my + math.floor(0.74 * self.robloxWindow.mh) - 5)
        mouse.click()
        time.sleep(0.5)

        try:
            itemImg = self.adjustImage("./images/inventory", item)
        except Exception:
            itemImg = None

        foundItem = False
        selectorCenterX = self.robloxWindow.mx + math.floor(0.515 * self.robloxWindow.mw)
        selectorCenterY = self.robloxWindow.my + math.floor(0.535 * self.robloxWindow.mh)
        searchX = selectorCenterX - shrineScaleX(250)
        searchY = selectorCenterY - shrineScaleY(100)
        searchW = shrineScaleX(500)
        searchH = shrineScaleY(300)
        nameX = selectorCenterX - shrineScaleX(230)
        nameY = selectorCenterY - shrineScaleY(75)
        nameW = shrineScaleX(200)
        nameH = shrineScaleY(70)
        nextX = selectorCenterX + shrineScaleX(157)
        nextY = selectorCenterY - shrineScaleY(45)
        for _ in range(80):
            selectedItemText = readSelectedShrineItem(nameX, nameY, nameW, nameH)
            if len(selectedItemText) >= 3 and any(
                alias in selectedItemText or selectedItemText in alias for alias in itemAliases
            ):
                foundItem = True
                break
            if itemImg is not None:
                itemMatch = locateImageOnScreen(itemImg, searchX, searchY, searchW, searchH, 0.62)
                if itemMatch and itemMatch[0] > 0.62:
                    foundItem = True
                    break
            mouse.moveTo(nextX, nextY)
            mouse.click()
            time.sleep(0.15)

        if not foundItem:
            self.logger.webhook("", f"Wind Shrine offering failed: could not find {item.title()} in shrine selector", "red", "screen")
            self.keyboard.press("e")
            return None

        addX = selectorCenterX + shrineScaleX(157)
        addY = selectorCenterY + shrineScaleY(40)
        mouse.moveTo(addX, addY)
        for _ in range(max(0, quantity - 1)):
            mouse.click()
            time.sleep(0.04)

        donateX = selectorCenterX - shrineScaleX(72)
        donateY = selectorCenterY + shrineScaleY(116)
        mouse.moveTo(donateX, donateY)
        mouse.click()
        time.sleep(2)
        clickWindShrineDialogsUntilGone()
        self.logger.webhook("", f"Offered {item.title()} x{quantity} to Wind Shrine", "bright green", "screen")
        time.sleep(0.5)
        lootWindShrineTokens()
        self.logger.webhook("", "Collected loot from Wind Shrine", "bright green", "screen")
        return cooldownSeconds

    def scheduleFieldBoosterGlitterExtension(self):
        """Use Glitter at 14:55 of a detected field booster."""
        if not self.setdat.get("field_booster_glitter_extend_enabled", False):
            return

        glitterSlot = glitter_slot(self.setdat)
        with self._fieldBoosterGlitterLock:
            self._fieldBoosterGlitterGeneration += 1
            generation = self._fieldBoosterGlitterGeneration

        def useGlitter():
            # Field boosters last 15 minutes; Glitter needs to be used at 14:55.
            time.sleep(14 * 60 + 55)
            with self._fieldBoosterGlitterLock:
                if generation != self._fieldBoosterGlitterGeneration:
                    return
            if self.run is not None and self.run.value == 0:
                return
            try:
                self.useGlitterFromSlot(glitterSlot)
            except RuntimeError as error:
                self.logger.webhook("", f"Could not extend field booster: {error}", "red")
                return
            self.logger.webhook("", f"Used Glitter from {glitter_slot_label(glitterSlot)}; extending field booster", "bright green")

        threading.Thread(target=useGlitter, name="field-booster-glitter-extension", daemon=True).start()

    def useGlitterFromSlot(self, slot):
        """Use a Glitter hotbar slot, or locate Glitter in the inventory for slot 0.
        Raises RuntimeError if Glitter isn't in the inventory."""
        if int(slot) == 0:
            if not self.useItemInInventory("glitter"):
                raise RuntimeError("Glitter was not found in the inventory")
        else:
            self.keyboard.press(str(slot))


    def antChallenge(self):
        self.logger.webhook("","Travelling: Ant Challenge","dark brown")
        if not self.travelViaCannon("Ant Challenge"):
            return False
        self.runPath("boss/ant_challenge")
        time.sleep(0.5)

        # If the red box (where E would be) says 'need', fetch a free ant pass
        beside_text = self.getTextBesideE() or ""
        if "need" in beside_text.lower():
            self.logger.webhook("", "No ant passes detected — fetching free ant pass","dark brown")
            try:
                self.reset(convert=False)
                self.collect("ant_pass_dispenser")
            except Exception:
                self.logger.webhook("", "Failed to collect ant pass","red", "screen", ping_category="ping_critical_errors")
            time.sleep(1)

        if self.isBesideE(["spen","play"], ["need"]):
            self.logger.webhook("","Start Ant Challenge","bright green", "screen")
            self.keyboard.press("e")
            time.sleep(1)
            self.placeSprinkler()
            mouse.click()
            time.sleep(1)
            self.keyboard.walk("s",1.5)
            self.keyboard.walk("w",0.15)
            self.keyboard.walk("d",0.3)
            mouse.mouseDown()
            challengeStart = time.time()

            def clickKeepOld(keepOld=None):
                if keepOld is None:
                    keepOld = self.keepOldCheck()
                if keepOld is None:
                    keepOld = (
                        int(self.robloxWindow.mx + self.robloxWindow.mw/2),
                        int(self.robloxWindow.my + self.robloxWindow.mh*0.58),
                    )
                time.sleep(0.1)
                mouse.moveTo(*keepOld)
                time.sleep(0.2)
                mouse.click()

            while True:
                keepOld = self.keepOldCheck()
                if keepOld is not None:
                    mouse.mouseUp()
                    self.logger.webhook("","Ant Challenge Complete","bright green", "screen", ping_category="ping_ant_challenge")
                    clickKeepOld(keepOld)
                    return True
                if self.blueTextImageSearch("died", 0.8):
                    mouse.mouseUp()
                    self.logger.webhook("","Player died during Ant Challenge; resetting", "dark brown", "screen", ping_category="ping_character_deaths")
                    self.reset(convert=False)
                    return False
                if time.time() - challengeStart > 8*60:
                    mouse.mouseUp()
                    self.logger.webhook("","Ant Challenge timed out waiting for score popup; pressing Keep Old and resetting", "red", "screen", ping_category="ping_critical_errors")
                    clickKeepOld()
                    self.reset(convert=False)
                    return False

        self.logger.webhook("", "Cant start ant challenge", "red", "screen", ping_category="ping_critical_errors")
        return False

    def hasStickerStackRespawned(self):
        with open(settingsManager.ensureUserFile("sticker_stack.txt"), "r") as f:
            stickerStackCD = int(f.read())
        return self.hasRespawned("sticker_stack", stickerStackCD)

    def collectStickerPrinter(self):
        self.set_task_status("sticker_printer", activity="sticker_printer")
        reached = False
        for _ in range(2):
            self.logger.webhook("",f"Travelling: Sticker Printer","dark brown")
            if not self.travelViaCannon("Sticker Printer"):
                return
            self.runPath("collect/sticker_printer")
            self.location = "collect"
            for _ in range(6):
                self.keyboard.walk("w", 0.2)
                reached = self.isBesideE(["inspect", "stick", "print"])
                if reached: break
            if reached: break
            self.logger.webhook("", f"Failed to reach sticker printer", "dark brown", "screen")
            self.reset(convert=False)
        else: return

        self.keyboard.press("e")
        #claim sticker
        eggPosData = {
            "basic": -95, 
            "silver": -40,
            "gold": 15,
            "diamond": 70,
            "mythic": 125
        }
        #click egg
        time.sleep(2)
        eggPos = eggPosData[self.setdat["sticker_printer_egg"]]
        mouse.moveTo(self.robloxWindow.mx+(self.robloxWindow.mw//2+eggPos), self.robloxWindow.my+(4*self.robloxWindow.mh//10-20))
        time.sleep(0.2)
        mouse.click()
        time.sleep(1)
        confirmImg = self.adjustImage("./images/menu", "confirm")
        if not locateImageOnScreen(confirmImg, self.robloxWindow.mx+(self.robloxWindow.mw//2+150), self.robloxWindow.my+(4*self.robloxWindow.mh//10+160), 120, 60, 0.7):
            self.logger.webhook(f"", "Sticker printer on cooldown", "dark brown", "screen")
            self.keyboard.press("e")
            self.saveTiming("sticker_printer")
            return
        #confirm
        mouse.moveTo(self.robloxWindow.mx+(self.robloxWindow.mw//2+225), self.robloxWindow.my+(4*self.robloxWindow.mh//10+195))
        time.sleep(0.1)
        mouse.click()
        time.sleep(0.2)
        mouse.moveBy(0, 3)
        time.sleep(0.1)
        mouse.click()
        time.sleep(0.2)
        #click yes
        if not self.clickYes(detect=True):
            egg = self.setdat["sticker_printer_egg"]
            self.logger.webhook("", f"No {egg} eggs left, Sticker Printer has been disabled", "red", "screen", ping_category="ping_critical_errors")
            self.updateGUI.value = 1
            self.setdat["sticker_printer"] = False
            settingsManager.saveProfileSetting(f"sticker_printer", False)
            self.keyboard.press("e")
            return
        #wait for sticker to generate
        time.sleep(7)
        self.logger.webhook(f"", "Claimed sticker", "bright green", "sticker", ping_category="ping_sticker_events")
        self.saveTiming("sticker_printer")
        #close the inventory
        time.sleep(1)
        self.toggleInventory("close")

    def collect(self, objective):
        self.set_task_status(objective, activity=objective)
        reached = None
        objectiveData = mergedCollectData[objective]
        displayName = objective.replace("_"," ").title()
        st = time.time()
        def updateHourlyTime():
            self.hourlyReport.addHourlyStat("misc_time", time.time()-st)
        #go to collect and check that player has reached
        for i in range(3):
            self.logger.webhook("",f"Travelling: {displayName}","dark brown")
            if objective in ["honey_dispenser", "gingerbread"]:
                self.reset(convert=False)
            else:
                if not self.travelViaCannon(displayName):
                    updateHourlyTime()
                    return
            self.location = "collect"
            # Special-case: run a bespoke sequence for Honey Storm instead of the
            # default path/walk system.
            if objective == "honeystorm":
                self.runPath("collect/stockings")
                self.keyboard.walk("a",1.25, False)
                self.keyboard.walk("s",1.5)
                self.keyboard.walk("d",0.45)
                reached = self.isBesideE(objectiveData[0])
                for _ in range(10):
                    if reached or self.checkPauseAndWait():
                        break
                    self.keyboard.walk("s", 0.4)
                    reached = self.isBesideE(objectiveData[0])
                if not reached:
                    self.logger.webhook("", "Failed to reach Honey Storm summon point", "dark brown", "screen")
                    updateHourlyTime()
                    return
                if "(" in reached and ":" in reached:
                    cooldownSeconds = objectiveData[2]
                    cd = self.cdTextToSecs(reached, True, cooldownSeconds)
                    if cd:
                        cooldownFormat = timedelta(seconds=cd)
                        self.logger.webhook("", f"Honey Storm is on cooldown ({cooldownFormat} remaining)", "dark brown", "screen")
                        return
                # Execute honey storm actions
                self.keyboard.press("e")
                time.sleep(0.5)
                self.keyboard.walk("s", 3)
                self.keyboard.walk("d", 2)
                for i in range(4):
                    self.keyboard.walk("w", 2.25)
                    self.keyboard.walk("d", 0.25)
                    self.keyboard.walk("s", 2.25)
                    self.keyboard.walk("d", 0.25)
                self.saveTiming("honeystorm")
                self.logger.webhook("", "Honey storm collected", "bright green", "screen")
                self.reset(convert=True)
                return
            # Some collects (memory_match variants, sticker_stack) don't have
            # a path file — allow missing files and continue to per-objective handling.
            self.runPath(f"collect/{objective}", fileMustExist=False)
            if objectiveData[1] is None:
                reached = self.isBesideE(objectiveData[0])
            else:
                for _ in range(6):
                    self.keyboard.walk(objectiveData[1], 0.2)
                    reached = self.isBesideE(objectiveData[0])
                    if reached: break
            if reached: break
            self.logger.webhook("", f"Failed to reach {displayName}", "dark brown", "screen")
            if objective in ("ant_pass_dispenser", "buy_ant_pass"):
                self.logger.webhook("", "Maybe you have maxed out ant passes?", "dark brown")
            if i != 2: self.reset(convert=False)
        
        if not reached: 
            updateHourlyTime()
            return #player failed to reach objective
        if objective == "robo_pass_dispenser":
            reachedText = str(reached).lower()
            if (
                ("already" in reachedText and "robo" in reachedText and "pass" in reachedText)
                or ("10" in reachedText and "more" in reachedText and "robo" in reachedText)
            ):
                self.logger.webhook("", "Maybe you have maxed out robo passes?", "dark brown", "screen")
                updateHourlyTime()
                return
        if objective == "gummy_beacon":
            reachedText = str(reached).lower()
            if "siege" in reachedText and "progress" in reachedText:
                self.logger.webhook("", "Gummy Beacon is already active", "dark brown", "screen")
                updateHourlyTime()
                return
            if ("satellite" in reachedText or "satelite" in reachedText) and "vibes" in reachedText:
                self.logger.webhook("", "Gummy Beacon is not unlocked", "dark brown", "screen")
                updateHourlyTime()
                return
            if "(" in reachedText and ":" in reachedText:
                cd = self.cdTextToSecs(reachedText, True, self.collectCooldowns[objective])
                if cd:
                    cooldownFormat = timedelta(seconds=cd)
                    self.logger.webhook("", f"{displayName} is on cooldown ({cooldownFormat} remaining)", "dark brown", "screen")
                    updateHourlyTime()
                    return
        #player has reached, get cooldown info
        #check if on cooldown
        cooldownSeconds = objectiveData[2]
        returnVal = None #a return value
        if "(" in reached and ":" in reached:
            cd = self.cdTextToSecs(reached, True, self.collectCooldowns[objective])
            if cd: cooldownSeconds = cd
            cooldownFormat = timedelta(seconds=cooldownSeconds)
            self.logger.webhook("", f"{displayName} is on cooldown ({cooldownFormat} remaining)", "dark brown", "screen")
        else: #not on cooldown
            for _ in range(1 if objective == "sticker_stack" else 2):
                self.keyboard.press("e")
            #run the claim path (if it exists)
            self.runPath(f"collect/claim/{objective}", fileMustExist=False)
            #memory match
            if "memory_match" in objective:
                if objective == "memory_match":
                    mmType = "normal"
                else:
                    mmType = objective.split("_")[0]
                self.latestMM = mmType
                time.sleep(2)
                self.logger.webhook("", f"Solving: {displayName}", "dark brown", "screen")
                self.canDetectNight = False
                self.memoryMatch.solveMemoryMatch(mmType, self.setdat.get("memory_match_rewards", []))
                self.canDetectNight = True
                time.sleep(2)
                self.logger.webhook("", f"Completed: {displayName}", "bright green", "blue")
            elif objective in fieldBoosterData:
                sleep(3)
                bluetexts = ""
                #get the blue texts 4 times to avoid missing the field
                for _ in range(4):
                    bluetexts += ocr.readBlueText().lower()
                # Reuse AFB parsing logic to robustly detect boosted field names.
                allCandidateFields = list(startLocationDimensions.keys())
                detectedBoostedFields = self._extractAFBBoostedFields(bluetexts, allCandidateFields)
                boostedField = detectedBoostedFields[-1] if detectedBoostedFields else ""
                returnVal = boostedField
                self.logger.webhook("", f"Collected: {displayName}, Boosted Field: {boostedField.title()}", "bright green", "screen")
                if boostedField:
                    extendFieldBooster = self.setdat.get("field_booster_glitter_extend_enabled", False)
                    self.tadAltSync.sync_to_boost(
                        boostedField,
                        extend_with_glitter=False if extendFieldBooster else None,
                        extension_duration=15 * 60 if extendFieldBooster else 0,
                    )
                    if extendFieldBooster:
                        self.scheduleFieldBoosterGlitterExtension()
                else:
                    self.tadAltSync.initialize_alts()
                self.saveTiming("last_booster")
            elif objective == "sticker_stack":
                if "your" in reached or "activated" in reached:
                    self.logger.webhook("", "Sticker Stack on cooldown", "dark brown", "screen")
                    return
                if not self.claimStickerStack():
                    updateHourlyTime()
                    return
            elif objective == "wind_shrine":
                detectedCooldown = self.collectWindShrine(reached)
                if detectedCooldown is None:
                    updateHourlyTime()
                    return
                cooldownSeconds = detectedCooldown
            else:
                time.sleep(0.1)
                self.logger.webhook("", f"Collected: {displayName}", "bright green", "screen")
        #update the internal cooldown
        self.saveTiming(objective)
        self.collectCooldowns[objective] = cooldownSeconds
        updateHourlyTime()
        return returnVal

    def closeBlenderGUI(self):
        mouse.moveTo(self.robloxWindow.mx+(self.robloxWindow.mw/2-250), self.robloxWindow.my+(math.floor(self.robloxWindow.mh*0.48))-200)
        time.sleep(0.1)
        mouse.click()

    def blender(self, blenderData):
        self.set_task_status("blender", activity="blender")
        itemNo = blenderData["item"]
        st = time.time()
        def updateHourlyTime():
            self.hourlyReport.addHourlyStat("misc_time", time.time()-st)

        def saveBlenderData():
            with open(settingsManager.ensureUserFile("blender.txt"), "w") as f:
                f.write(str(blenderData))
            f.close()
            updateHourlyTime()
        
        def getNextItem():
            nextItem = itemNo
            for _ in range(BLENDER_ITEM_SLOTS + 1):
                nextItem += 1
                if nextItem > BLENDER_ITEM_SLOTS:
                    nextItem = 1
                #item must be set and have repeats
                if (self.setdat[f"blender_item_{nextItem}"] != "none") and (self.setdat[f"blender_repeat_{nextItem}"] > 0 or self.setdat[f"blender_repeat_inf_{nextItem}"]):
                    return nextItem
            else:
                return 0 #no items to craft

        #check if item is none (settings got changed but user did not reset the blender data)
        #or first blender of the reset
        if blenderData["collectTime"] == 0 or (itemNo and self.setdat[f"blender_item_{itemNo}"] == "none"): 
            itemNo = getNextItem() #get the first item
            if not itemNo: #no items available
                blenderData["item"] = itemNo
                blenderData["collectTime"] = -1
                saveBlenderData()
                return

        for _ in range(2):
            self.logger.webhook("","Travelling: Blender","dark brown")
            if not self.travelViaCannon("Blender"):
                updateHourlyTime()
                return
            self.runPath("collect/blender")
            self.location = "collect"
            for _ in range(6):
                self.keyboard.walk("d", 0.2)
                reached = self.isBesideE(["open"])
                if reached: break
            if reached: break
        else:
            self.logger.webhook("","Failed to reach Blender", "dark brown", "screen")
            updateHourlyTime()
            return
        
        x = self.robloxWindow.mx + self.robloxWindow.mw//2 - 280
        y = self.robloxWindow.my + self.robloxWindow.mh//2 - 240

        def clickOnBlenderElement(cx, cy):
            cx //= self.robloxWindow.multi
            cy //= self.robloxWindow.multi
            mouse.moveTo(cx+x, cy+y)
            time.sleep(0.1)
            mouse.click()
            mouse.moveBy(2,2)
            time.sleep(0.1)
            mouse.click()
            #close and reopen gui
            time.sleep(0.1)
            self.closeBlenderGUI()
            time.sleep(0.3)
            self.keyboard.press("e")

        self.keyboard.press("e")
        time.sleep(1)
        #check if blender is done and click on end crafting
        doneImg = self.adjustImage("images/menu", "blenderdone")
        res = locateImageOnScreen(doneImg, x, self.robloxWindow.my+(y), 560, 480, 0.75)
        if res:
            print("done")
            clickOnBlenderElement(*res[1])
        
        #check for cancel button
        cancelImg = self.adjustImage("images/menu", "blendercancel")
        res = locateImageOnScreen(cancelImg, x, self.robloxWindow.my+(y), 560, 480, 0.75)
        if res:
            print("cancel")
            clickOnBlenderElement(*res[1])

        #check if still crafting and get cd
        notDoneImg = self.adjustImage("images/menu", "blenderend")
        res = locateImageOnScreen(notDoneImg, x, self.robloxWindow.my+(y), 560, 480, 0.75)

        def cancelCraft():
            self.logger.webhook("", "Unable to detect remaining crafting time, ending craft", "dark brown", "screen")
            #mouse.moveTo(self.robloxWindow.mx+(self.robloxWindow.mw/2-120), self.robloxWindow.my+(math.floor(self.robloxWindow.mh*0.48))+120)
            clickOnBlenderElement(*res[1])

        if res:
            cdImg = mssScreenshot(self.robloxWindow.mx+(self.robloxWindow.mw/2-130),self.robloxWindow.my+(math.floor(self.robloxWindow.mh*0.48)-70), 400, 65)
            cdRaw = ocr.ocrRead(cdImg)
            cdRaw = ''.join([x[1][0] for x in cdRaw])
            cd = self.cdTextToSecs(cdRaw, False, 3600) #1 hour cd
            if cd:
                cooldownFormat = timedelta(seconds=cd)
                self.logger.webhook("", f"Blender is currently crafting an item ({cooldownFormat} remaining)", "dark brown", "screen")
                #set the target time and quit
                self.closeBlenderGUI()
                blenderData["collectTime"] = time.time() + cd
                saveBlenderData()
                return
            else: #cant detect cd, just cancel craft
                cancelCraft()
        
        #time to craft
        if not itemNo: #if itemNo is 0, there are no items to craft. The macro has collected the last item to craft
            self.closeBlenderGUI()
            blenderData["collectTime"] = -1 #set collectTime to -1 (disable blender)
            saveBlenderData()
            return
        item = self.setdat[f"blender_item_{itemNo}"]
        #click to the item
        itemDisplay = item.title()
        mouse.moveTo(self.robloxWindow.mx+(self.robloxWindow.mw/2+240), self.robloxWindow.my+(math.floor(self.robloxWindow.mh*0.48))+128)
        for _ in range(blenderItems.index(item)):
            mouse.click()
            sleep(0.06)
        #check if the item can be crafted
        canMake = self.adjustImage("images/menu", "blendermake")
        if not locateImageOnScreen(canMake, self.robloxWindow.mx+(x), self.robloxWindow.my+(y), 560, 480, 0.8):
            self.logger.webhook("", f"Unable to craft {itemDisplay}", "dark brown", "screen")
        #open the crafting menu
        mouse.moveTo(self.robloxWindow.mx+(self.robloxWindow.mw/2), self.robloxWindow.my+(math.floor(self.robloxWindow.mh*0.48))+130)
        time.sleep(0.1)
        mouse.click()
        #set the quantity
        mouse.moveTo(self.robloxWindow.mx+(self.robloxWindow.mw/2-60), self.robloxWindow.my+(math.floor(self.robloxWindow.mh*0.48))+140)
        #check if max
        if self.setdat[f"blender_quantity_max_{itemNo}"]:
            #get a screenshot of the quantity
            #add more
            #get another screenshot
            #if both screenshots are the same, break

            def quantityScreenshot(save = False):
                return average_hash(mssScreenshot(self.robloxWindow.mx+(self.robloxWindow.mw/2-60-140), self.robloxWindow.my+(math.floor(self.robloxWindow.mh*0.48)+140-20), 110, 20*2, save))
            quantity1Img = quantityScreenshot()
            while True:
                for _ in range(5): #add 5 quantity
                    mouse.click()
                    sleep(0.03)
                quantity2Img = quantityScreenshot()
                if quantity2Img == quantity1Img: #check if screenshots are similar
                    break
                #update the quantity
                quantity1Img = quantity2Img
            quantity = ''.join([x[1][0] for x in ocr.ocrRead(mssScreenshot(self.robloxWindow.mx+(self.robloxWindow.mw/2-60-140), self.robloxWindow.my+(math.floor(self.robloxWindow.mh*0.48)+140-20), 110, 23*2))])
            quantity = ''.join([x for x in quantity if x.isdigit()])
            if quantity:
                quantity = int(quantity)
            else:
                self.logger.webhook("", "Failed to detect the quantity of items crafted. The macro will get the crafting time on the next visit", "dark brown")
                quantity = 0
        else: 
            #normal quantity
            quantity = self.setdat[f"blender_quantity_{itemNo}"]
            for _ in range(quantity-1): #-1 because the quantity starts from 1
                mouse.click()
                sleep(0.03)
        #confirm
        mouse.moveTo(self.robloxWindow.mx+(self.robloxWindow.mw/2 + 70), self.robloxWindow.my+(math.floor(self.robloxWindow.mh*0.48))+130)
        time.sleep(0.1)
        mouse.click()
        #go to next item
        #decrement the repeat count
        if not self.setdat[f"blender_repeat_inf_{itemNo}"]:
            self.setdat = {**self.setdat, **settingsManager.incrementProfileSetting(f"blender_repeat_{itemNo}", -1)}
            self.updateGUI.value = 1
        blenderData["item"] = getNextItem()
        #calculate the time to collect the blender
        craftTime = quantity*5*60 #5mins per item
        blenderData["collectTime"] = time.time() + craftTime
        time.sleep(1) #add a delay here before taking a screenshot, since bss displays the crafting screen with default values for a bit
        self.logger.webhook("", f"Crafted: {itemDisplay} x{quantity}, Ready in: {timedelta(seconds=craftTime)}", "bright green", "screen", ping_category="ping_conversion_events")
        #store the data
        saveBlenderData()
        self.closeBlenderGUI()

    def claimStickerStack(self):
        time.sleep(1)
        x = self.robloxWindow.mw//2-275
        y = 4*self.robloxWindow.mh//10

        #detect sticker stack boost time
        screen = mssScreenshot(self.robloxWindow.mx+(x+550/2),self.robloxWindow.my+y,550/2,40)
        ocrRes = ''.join([x[1][0] for x in ocr.ocrRead(screen)])
        ocrRes = re.findall(r"\(.*?\)", ocrRes) #get text between brackets
        finalTime = None
        def cantDetectTime():
            self.logger.webhook("", "Failed to detect sticker stack buff duration", "red", "screen", ping_category="ping_critical_errors")
        if ocrRes:
            times = []
            if "x" in ocrRes[0]: #number of stickers
                stickerCount = int(''.join([x for x in ocrRes[0] if x.isdigit()]))
                times.append(15*60 + 10*stickerCount)
                ocrRes.pop(0)
            if ":" in ocrRes[0]: #direct
                times.append(self.cdTextToSecs(ocrRes[0], True, 0))
            if times:
                finalTime = max(times)
            else:
                cantDetectTime()
        else:
            cantDetectTime()
        stickerUsed = False
        #use sticker
        if "sticker" in self.setdat["sticker_stack_item"]:
            regularSticker = self.adjustImage("images/sticker_stack", "regularsticker")
            hiveSticker = self.adjustImage("images/sticker_stack", "hivesticker")
            stickerLoc = locateTransparentImageOnScreen(regularSticker, self.robloxWindow.mx+(x), self.robloxWindow.my+(y), 550, 220, 0.7)
            if self.setdat["hive_skin"] and stickerLoc is None: #cant find regular sticker, use hive skin
                stickerLoc = locateTransparentImageOnScreen(hiveSticker, self.robloxWindow.mx+(x), self.robloxWindow.my+(y), 550, 220, 0.7)
            if stickerLoc: #found a available sticker
                xr, yr = [j//self.robloxWindow.multi for j in stickerLoc[1]]

                mouse.moveTo(self.robloxWindow.mx+(x+xr), self.robloxWindow.my+(y+yr))
                time.sleep(0.1)
                mouse.moveBy(3,-3)
                time.sleep(0.2)
                mouse.click()
                stickerUsed = True
            elif not "/" in self.setdat["sticker_stack_item"]:
                self.logger.webhook("", "No Stickers left to stack, Sticker Stack has been disabled", "red", "screen", ping_category="ping_critical_errors")
                self.updateGUI.value = 1
                self.setdat["sticker_stack"] = False
                settingsManager.saveProfileSetting("sticker_stack", False)
                self.keyboard.press("e")
                return False
        if "ticket" in self.setdat["sticker_stack_item"] and not stickerUsed:
                mouse.moveTo(self.robloxWindow.mx+(self.robloxWindow.mw//2+105), self.robloxWindow.my+(4*self.robloxWindow.mh//10-78))
                time.sleep(0.1)
                mouse.click()
                time.sleep(0.1)
                mouse.moveBy(2,2)
                mouse.click()

        #click yes (regular stickers have 2 confirms; cub/hive skins can have 4)
        yesPopup = False
        for _ in range(4):
            if not self.clickYes(detect=True, clickOnce=True):
                break
            yesPopup = True
            # Second confirm can take a beat to replace the first; wait before re-scanning
            time.sleep(0.7)
        else: #4 yes/no popups, either cub/hive skin
            if not self.setdat["hive_skin"] and not self.setdat["cub_skin"]: #do not use cub and hive stickers
                self.logger.webhook("", "A hive/cub sticker has been wrongly selected, aborting", "red", "screen", ping_category="ping_critical_errors")
                self.keyboard.press("e")
                return False
        
        if "ticket" in self.setdat["sticker_stack_item"] and not yesPopup: #if no popup appears, ran out of tickets
            self.logger.webhook("", "No Tickets left, Sticker Stack has been disabled", "red", "screen", ping_category="ping_critical_errors")
            self.setdat["sticker_stack"] = False
            settingsManager.saveProfileSetting("sticker_stack", False)
            self.updateGUI.value = 1
            self.keyboard.press("e")
            return False
        if finalTime is not None:
            if stickerUsed: finalTime += 10
            self.logger.webhook("", f"Activated Sticker Stack, Buff Duration: {timedelta(seconds=finalTime)}", "bright green")
        else:
            with open(settingsManager.ensureUserFile("sticker_stack.txt"), "r") as f: #get the cooldown from the prev detection
                stickerStackCD = int(f.read())
            f.close()
            if stickerStackCD > 15*60: #make sure the time is valid
                finalTime = stickerStackCD + 10
            else:
                finalTime = 60*60 #default to 1hr
            self.logger.webhook("", f"Activated Sticker Stack, Buff Duration: {timedelta(seconds=finalTime)} (Defaulted to 1hr)", "bright green")
        self.keyboard.press("e")
        with open(settingsManager.ensureUserFile("sticker_stack.txt"), "w") as f:
            f.write(str(finalTime))
        f.close()
        return True

    def feedBee(self, item, quantity):
        res = self.findItemInInventory(item)
        if not res: 
            return
        
        x, y = res
        #re-adjust camera
        for _ in range(10):
            self.keyboard.press("pageup")
        for _ in range(4):
            self.keyboard.press("pagedown")

        for _ in range(2):
            # start slightly lower to avoid being barely too high
            mouse.moveTo(self.robloxWindow.mx+(x), self.robloxWindow.my+(y+25))
            time.sleep(0.3)
            pag.dragTo(self.robloxWindow.mx + self.robloxWindow.mw//2, self.robloxWindow.my + self.robloxWindow.mh//2-80, 0.6, button='left')

        #interact with feed menu
        time.sleep(1)
        feedButtonImg = self.adjustImage("./images/menu", "feed")
        fx = self.robloxWindow.mx + (54*self.robloxWindow.mw)//100-300
        fy = self.robloxWindow.my + self.robloxWindow.yOffset + (46*self.robloxWindow.mh)//100-59
        fres = locateImageOnScreen(feedButtonImg, fx, fy, 300, 120, 0.75)
        if not fres:         
            self.moveMouseToDefault()
            return

        frx, fry = [x//self.robloxWindow.multi for x in fres[1]]

        #change quantity
        mouse.moveTo(fx+frx+150, fy+fry+8)
        time.sleep(0.1)
        for _ in range(2):
            mouse.click()
            time.sleep(0.02)
        self.keyboard.write(str(quantity))

        #click feed button
        mouse.moveTo(fx+frx, fy+fry)
        time.sleep(0.1)
        for _ in range(2):
            mouse.click()
            time.sleep(0.02)
        
        self.logger.webhook("",f"Fed {quantity} {item}", "bright green")

        self.moveMouseToDefault()
