import re
import threading
import modules.misc.settingsManager as settingsManager
import modules.screen.ocr as ocr
from modules.controls.sleep import pause_aware_time as time
from modules.macro.game_data import startLocationDimensions


class AFBMixin:
    def saveAFB(self, name):
        return settingsManager.saveSettingFile(name, time.time(), settingsManager.getUserDataPath("AFB.txt"))

    def resetAFBSessionTimings(self):
        try:
            data = settingsManager.readSettingsFile(settingsManager.getUserDataPath("AFB.txt"))
        except Exception:
            data = {}

        now = time.time()
        rebuffCooldown = max(0, float(self.setdat.get("AFB_rebuff", 0) or 0) * 60)

        # Start the AFB time-limit window fresh on each macro run.
        data["AFB_limit"] = now
        # Make startup behave as "ready after the configured rebuff interval"
        # instead of "just used right now", which can skew the dice/glitter order.
        data["AFB_dice_cd"] = now - rebuffCooldown
        data["AFB_glitter_cd"] = now - rebuffCooldown

        settingsManager.saveDict(settingsManager.getUserDataPath("AFB.txt"), data)

    def getAFBtiming(self,name = None):
        for _ in range(3):
            data = settingsManager.readSettingsFile(settingsManager.getUserDataPath("AFB.txt"))
            if data: break #most likely another process is writing to the file
            time.sleep(0.1)
        if name is not None:
            if not name in data:
                print(f"could not find timing for {name}, setting a new one")
                self.saveAFB(name)
                return time.time()
            return data[name]
        return data

    def hasAFBRespawned(self, name, cooldown, applyMobRespawnBonus = False, timing = None):
        if timing is None: timing = self.getAFBtiming(name)
        if not isinstance(timing, float) and not isinstance(timing, int):
            print(f"Timing is not a valid number? {timing}")
        mobRespawnBonus = 1
        if applyMobRespawnBonus:
            mobRespawnBonus -= 0.15 if self.setdat["gifted_vicious"] else 0
            mobRespawnBonus -= self.setdat["stick_bug_amulet"]/100 
            mobRespawnBonus -= self.setdat["icicles_beequip"]/100 

        return time.time() - timing >= cooldown*mobRespawnBonus

    def _AFBApplyGlitter(self, targetField, glitterslot):
        self.logger.webhook("", "Rebuffing: Glitter", "white")

        # slot 0 finds Glitter in the inventory. AFB always ends the gather before this, so it
        # never opens the inventory mid-pattern.
        glitterCoords = None
        if glitterslot == 0:
            try:
                glitterCoords = self.findItemInInventory("glitter")
            except Exception:
                glitterCoords = None

        if not self.travelViaCannon("Auto Field Boost"):
            return False

        if glitterslot == 0 and glitterCoords:
            self.useItemInInventory(x=glitterCoords[0], y=glitterCoords[1], closeInventoryAfter=False)
            self.goToField(targetField)
            self.clickYes()
            self.toggleInventory("close")
        elif glitterslot == 0:
            glitterThread = threading.Thread(target=self.useItemInInventory, args=("glitter",))
            fieldThread = threading.Thread(target=self.goToField, args=(targetField,))
            glitterThread.start()
            fieldThread.start()
            fieldThread.join()
            glitterThread.join()
            self.clickYes()
        else:
            self.goToField(targetField)
            time.sleep(0.5)
            self.keyboard.press(str(glitterslot))

        self.logger.webhook("", "Rebuffed: Glitter", "white")
        self.saveAFB("AFB_dice_cd")
        self.saveAFB("AFB_glitter_cd")
        self.AFBglitter = False
        self.cAFBglitter = False
        self.afb = False
        self.reset()

    def _normalizeAFBText(self, text):
        text = text.lower()
        text = re.sub(r"[^a-z\s]", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _removeAFBNonBoostText(self, text):
        # Coconut Belt kick messages share the blue-text feed with boost messages
        # and can otherwise be mistaken for a field dice result.
        text = re.sub(
            r"\bkicked\b.*?\bto\b.*?\b(?:forest|field)\b",
            " ",
            text,
            flags=re.IGNORECASE,
        )
        return text

    def _getAFBTargetFields(self):
        raw = str(self.setdat.get("AFB_field", "sunflower")).lower().replace("_", " ")
        chunks = [x.strip() for x in re.split(r"[,/|]", raw) if x.strip()]
        if not chunks:
            chunks = [raw.strip()] if raw.strip() else []
        if not chunks:
            chunks = ["sunflower"]
        return chunks

    def _extractAFBBoostedFields(self, rawBlueTexts, candidateFields):
        fields = {
            "rose": [["rose"]],
            "strawberry": [["strawberry"]],
            "mushroom": [["mushroom"]],
            "pepper": [["pepper"]],
            "sunflower": [["sunflower"]],
            "dandelion": [["dandelion"]],
            "spider": [["spider"]],
            "coconut": [["coconut"]],
            "pine tree": [["pine", "tree"]],
            "blue flower": [["blue", "flower"]],
            "bamboo": [["bamboo"]],
            "stump": [["stump"]],
            "clover": [["clover"]],
            "pineapple": [["pineapple"]],
            "pumpkin": [["pumpkin"]],
            "cactus": [["cactus"]],
            "mountain top": [["mountain", "top"]],
        }
        ignore = {
            "strawberry",
            "strawberries",
            "blueberry",
            "blueberries",
            "seed",
            "seeds",
            "pineapple",
            "pineapples",
            "honey",
            "from",
        }

        boostCandidateText = self._removeAFBNonBoostText(rawBlueTexts)
        normalized = self._normalizeAFBText(boostCandidateText)
        boostedLines = [line for line in boostCandidateText.split("\n") if "boosted" in line.lower()]
        latestBoostText = boostedLines[-1] if boostedLines else rawBlueTexts
        tokens = set(normalized.split()) if not boostedLines else set()
        if boostedLines:
            lineNormalized = self._normalizeAFBText(latestBoostText)
            orderedMatches = []
            for candidate in candidateFields:
                fieldPatterns = fields.get(candidate, [[x for x in candidate.split() if x]])
                for pattern in fieldPatterns:
                    phrasePattern = r"\b" + r"\s+".join(re.escape(word) for word in pattern) + r"\b"
                    match = re.search(phrasePattern, lineNormalized)
                    if match:
                        orderedMatches.append((match.start(), candidate))
                        break
            orderedMatches.sort(key=lambda x: x[0])
            return [candidate for _, candidate in orderedMatches]

        boostedFields = []
        for candidate in candidateFields:
            fieldPatterns = fields.get(candidate, [[x for x in candidate.split() if x]])
            candidateCompact = candidate.replace(" ", "")
            if any((word in tokens and word not in candidateCompact) for word in ignore):
                continue
            for pattern in fieldPatterns:
                if set(pattern).issubset(tokens):
                    boostedFields.append(candidate)
                    break
        return boostedFields

    def AFB(self, gatherInterrupt = False, turnOffShiftLock = False):  # Auto Field Boost - WOOHOO

        returnVal = None
        if self.AFBLIMIT:
            return True
        limitHours = float(self.setdat.get("AFB_limit", 0) or 0)
        if not self.AFBLIMIT and self.setdat["AFB_limit_on"] and limitHours > 0:
            limitTiming = self.getAFBtiming("AFB_limit")
            if not limitTiming or limitTiming <= 0:
                self.saveAFB("AFB_limit")
            elif self.hasAFBRespawned("AFB_limit", limitHours * 60 * 60, timing=limitTiming):
                self.logger.webhook("AFB", "Time limit reached: Skipping", "red")
                self.AFBLIMIT = True
                return True

        attempts = max(1, int(self.setdat.get("AFB_attempts", 10) or self.setdat.get("attempts", 10) or 10))
        targetFields = self._getAFBTargetFields()
        rebuff = self.setdat["AFB_rebuff"]
        dice = self.setdat["AFB_dice"]
        glitter = self.setdat["AFB_glitter"]
        diceslot = self.setdat["AFB_slotD"]
        glitterslot = self.setdat["AFB_slotG"]
        if not glitter:
            self.AFBglitter = False
            self.cAFBglitter = False
        diceReady = self.hasAFBRespawned("AFB_dice_cd", rebuff * 60)
        glitterReady = glitter and self.hasAFBRespawned("AFB_glitter_cd", rebuff * 60)

        if gatherInterrupt:
            canUseGlitter = glitterReady and self.AFBglitter
            canUseDice = diceReady and not self.AFBglitter
            if (canUseGlitter or canUseDice) and not self.failed:
                self.clear_task_status()
                self.afb = True
                if turnOffShiftLock:
                    self.keyboard.press("shift")
                self.logger.webhook("Gathering: interrupted", "Automatic Field Boost", "brown")
                if self.AFBglitter:
                    self.reset(convert=False)
                else:
                    self.reset(AFB=True)

        if diceReady or (glitterReady and self.AFBglitter):
            self.failed = False
            if self.setdat["Auto_Field_Boost"]:
                if self.AFBglitter and glitterReady:
                    if self._AFBApplyGlitter(targetFields[0], glitterslot) is False:
                        return
                    return targetFields

                if self.cAFBDice or (diceReady and not self.AFBglitter):
                    self.cAFBDice = False
                    self.logger.webhook("", "Auto Field Boost", "white")
                    for _ in range(2):
                        self.keyboard.press("i")
                    self.keyboard.press("pageup")

                    if "loaded" in dice:
                        if not self.travelViaCannon("Auto Field Boost"):
                            return
                        self.goToField(targetFields[0])

                    diceCoords = None
                    if diceslot == 0:
                        diceCoords = self.findItemInInventory(self.setdat['AFB_dice'])

                    for attempt in range(attempts):
                        bluetexts = ""
                        self.logger.webhook("", f"{str(dice).title()}, Attempt: {attempt+1}/{attempts}", "white")

                        if diceslot == 0:
                            if diceCoords:
                                self.useItemInInventory(x=diceCoords[0], y=diceCoords[1], closeInventoryAfter=False)
                        else:
                            self.keyboard.press(str(diceslot))

                        timeout = 0
                        for _ in range(300):
                            if self.blueTextImageSearch("boosted"):
                                time.sleep(2)
                                break
                            timeout += 1
                            if timeout == 300:
                                self.logger.webhook("", "Auto Field Boost: Timeout", "white")
                                self.toggleInventory("close")
                                self.saveAFB("AFB_dice_cd")
                                self.AFBglitter = False
                                return

                        for _ in range(8):
                            bluetexts += ocr.readBlueText() + "\n"

                        allCandidateFields = list(startLocationDimensions.keys())
                        detectedBoostedFields = self._extractAFBBoostedFields(bluetexts, allCandidateFields)
                        latestDetectedBoost = detectedBoostedFields[-1] if detectedBoostedFields else None
                        detectedBoostText = latestDetectedBoost if latestDetectedBoost else "None"
                        self.logger.webhook(
                            "",
                            f"{str(dice).title()}, Attempt: {attempt+1}/{attempts} - Detected: {detectedBoostText}",
                            "white"
                        )

                        if "field" in dice:
                            boostedField = latestDetectedBoost if latestDetectedBoost in targetFields else None

                            if boostedField is not None:
                                self.logger.webhook("", f"Boosted Field: {boostedField}", "bright green", "blue")
                                returnVal = targetFields
                                self.keyboard.press("pagedown")
                                for _ in range(3):
                                    self.keyboard.press("o")
                                if diceslot == 0:
                                    self.toggleInventory("close")
                                self.saveAFB("AFB_dice_cd")
                                if glitter:
                                    self.AFBglitter = True
                                    self.saveAFB("AFB_glitter_cd")
                                return returnVal
                            continue

                        boostedFields = detectedBoostedFields
                        targetBoostedFields = [field for field in boostedFields if field in targetFields]

                        if targetBoostedFields:
                            self.logger.webhook("", f"Boosted Fields: {', '.join(targetBoostedFields)}", "blue")
                            returnVal = targetFields
                            self.keyboard.press("pagedown")
                            for _ in range(3):
                                self.keyboard.press("o")
                            if diceslot == 0:
                                self.toggleInventory("close")
                            self.saveAFB("AFB_dice_cd")
                            if glitter:
                                self.AFBglitter = True
                                self.saveAFB("AFB_glitter_cd")
                            return returnVal

                        if boostedFields:
                            self.logger.webhook("", f"Boosted Fields: {', '.join(boostedFields)}", "red")
                        else:
                            self.logger.webhook("", "Boosted Fields: None", "red")

                            if glitter and not self.failed and self.hasAFBRespawned("AFB_glitter_cd", rebuff*60):
                                if self.AFBglitter:
                                    if self._AFBApplyGlitter(targetFields[0], glitterslot) is False:
                                        return
                                    return targetFields

            if returnVal is None:
                self.failed = True
                self.keyboard.press("pagedown")
                for _ in range(3):
                    self.keyboard.press("o")
                self.logger.webhook("", f"Failed to boost {', '.join(targetFields)}", "red")
                self.saveAFB("AFB_dice_cd")
                if glitter:
                    self.saveAFB("AFB_glitter_cd")
                    self.AFBglitter = False
                if diceslot == 0:
                    self.toggleInventory("close")
                return
