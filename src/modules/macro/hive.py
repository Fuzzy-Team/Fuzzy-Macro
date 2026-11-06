import cv2
import numpy as np
import modules.controls.mouse as mouse
import modules.misc.settingsManager as settingsManager
from modules.controls.sleep import InterruptRequested, pause_aware_time as time
from modules.hive_acquisition import confirm_claim, DetectionAfterWalkError
from modules.macro.game_data import resetKernel, resetLower1, resetLower2, resetUpper1, resetUpper2
from modules.misc.imageManipulation import pillowToCv2
from modules.screen.imageSearch import locateImageOnScreen
from modules.screen.screenshot import mssScreenshot, mssScreenshotNP


def formatHoney(n):
    """1234567890 -> '1.235B'"""
    for size, suffix in ((10**15, "Qa"), (10**12, "T"), (10**9, "B"), (10**6, "M"), (10**3, "K")):
        if n >= size:
            return f"{n / size:.3f}".rstrip("0").rstrip(".") + suffix
    return str(n)


def hiveRedMask(hsv):
    """Bright pure red, the claim arrows' heads. Hive faces are more orange (hue 4-7) and avatar parts are dimmer."""
    return cv2.inRange(hsv, np.array([0, 130, 200]), np.array([3, 255, 255]))


class HiveMixin:
    def convert(self, bypass = False, forced_convert_balloon=None):
        self.location = "spawn"
        if not bypass:
            if not self.isMakeHoneyPrompt(): 
                self.alreadyConverted = False
                return False
        #start convert
        #check that the game has started converting
        for _ in range(3):  #must always be an odd number
            self.keyboard.press("e")
            time.sleep(1)
            if self.isBesideE(["stop", "making"], ["make"], log=True): 
                break

        self.set_task_status("converting", activity="converting")
        st = time.time()
        self.logger.webhook("", "Converting", "brown", "screen")
        self.alreadyConverted = True
        self.converting = True
        liveGatherReport = None
        if self.liveGatherReportEnabled():
            liveGatherReport = self.createLiveGatherReport("conversion_events")
            liveGatherReport.start("converting", "", lambda: time.time() - st, activity="Converting")

        #check if convert balloon
        conv_setting = str(self.setdat.get("convert_balloon", "")).lower().replace(" ", "_")
        convertBalloon = (conv_setting == "always") or \
                (conv_setting == "every" and self.hasRespawned("convert_balloon", int(self.setdat.get("convert_balloon_every", 30))*60)) or \
                (conv_setting == "every_gather" and forced_convert_balloon is True)
        
        if conv_setting == "balloon_blessing":
            convertBalloon = self.hasRespawned(
                "convert_balloon", int(self.setdat.get("convert_balloon_always_after", 50)) * 60
            )
            if not convertBalloon:
                blessing = self.buffDetector.getBuffsWithImage({"blessing": ["top", True, True]})[0]
                try:
                    convertBalloon = float(blessing) >= float(self.setdat.get("convert_balloon_min_blessing", 0))
                except (TypeError, ValueError):
                    # An unreadable stack leaves conversion to the timer.
                    convertBalloon = False

        convertedBackpack = False
        balloonStartHoney = 0
        balloonBlessing = "0"
        inactiveHoneyChecks = 0

        if self.enableNightDetection:
            self.keyboard.press(",")
        
        while True:
            # Check if paused and wait
            if self.checkPauseAndWait():
                # Stop was requested while paused
                self.clear_task_status()
                if liveGatherReport:
                    liveGatherReport.stop()
                self.converting = False
                return False
            
            #check if the macro is done converting/not converting
            text = self.getTextBesideE()
            #done converting
            doneConverting = False
            if not "stop" in text and not "making" in text:
                for i in ["pollen", "flower", "field"]:
                    if i in text:
                        doneConverting = True
                        break
            if doneConverting: 
                break
            #not converting
            if "make" in text and not "stop" in text:
                self.keyboard.press("e")
                time.sleep(2)

            if self.setdat.get("inactive_honey_reset", False) and time.time() - st > 60:
                if self.isInactiveHoneyResetPaused():
                    inactiveHoneyChecks = 0
                else:
                    inactiveHoneyChecks = 0 if self.isActiveHoney() else inactiveHoneyChecks + 1
                    if inactiveHoneyChecks > 30:
                        self.logger.webhook("Converting: interrupted", "Inactive Honey Reset (Beta)", "orange", "screen")
                        self.clear_task_status()
                        if liveGatherReport:
                            liveGatherReport.stop()
                        if self.enableNightDetection:
                            self.keyboard.press(".")
                        self.converting = False
                        self.reset(convert=False)
                        return False

            # Clicking during conversion keeps the equipped tool active. Allow users
            # to leave it idle while they are at their hive instead.
            if not self.setdat.get("disable_tool_at_hive", False):
                mouse.click()

            if (
                self.setdat.get("macro_mode", "normal") not in ("quest", "alt", "vic")
                and self.night
                and self.setdat["stinger_hunt"]
            ):
                self.hourlyReport.addHourlyStat("converting_time", time.time()-st)
                if liveGatherReport:
                    liveGatherReport.stop()
                self.keyboard.press(".")
                self.converting = False
                if self.confirmNight():
                    self.stingerHunt()
                else:
                    return self.convert(forced_convert_balloon=forced_convert_balloon)
                return
            
            #check if backpack is done
            if not convertedBackpack:
                for _ in range(4):
                    backpack = self.getBackpack()
                    if backpack: break #continue converting
                else:
                    #backpack is done converting, now convert balloon
                    convertedBackpack = True
                    if not convertBalloon: break
                    # Backpack honey is already counted, so the rise from here is the balloon's.
                    balloonStartHoney = self.getHoney()
                    balloonBlessing = self.buffDetector.getBuffsWithImage({"blessing": ["top", True, True]})[0]
                    self.logger.webhook("", "Converting Balloon", "light blue")

            # Check for conversion timeout
            max_convert_time = self.setdat.get("max_convert_time", 5)
            if time.time()-st > max_convert_time*60:
                timeout_msg = f"Converting timeout ({max_convert_time}mins max)"
                self.logger.webhook("", timeout_msg, "brown", "screen")
                
                behavior = self.setdat.get("convert_timeout_behavior", "move on").lower()
                if behavior == "rejoin":
                    self.rejoin(rejoinMsg=timeout_msg)
                
                # Default behavior is "move on"
                break

            #check for afb
            if self.setdat["Auto_Field_Boost"] and not self.AFBLIMIT and not self.afb:
                #glitter is not up, but dice is
                if self.hasAFBRespawned("AFB_dice_cd", self.setdat["AFB_rebuff"]*60) and not self.AFBglitter and not self.failed: 
                    self.afb = True
                    self.stop = True
                    self.cAFBDice = True
                    self.logger.webhook("Rebuffing","AFB", "brown")
                    time.sleep(1)
                    self.AFB()
                    self.cAFBDice = False
                    self.logger.webhook("", "Still converting", "brown")
                #glitter is up, g
                elif self.setdat["AFB_glitter"] and self.hasAFBRespawned("AFB_glitter_cd", self.setdat["AFB_rebuff"]*60+30) and self.AFBglitter and not self.failed and not self.afb: #if used dice before
                    self.clear_task_status()
                    self.afb = True
                    self.stop = True
                    self.cAFBglitter = True
                    self.logger.webhook("Converting: interrupted","AFB", "brown")
                    time.sleep(1)
                    self.AFB()
                    self.AFBglitter = False
                    self.cAFBglitter = False
                    self.logger.webhook("", "Continuing conversion", "brown")
                    self.set_task_status("converting", activity="converting")
                if not self.converting: break

        if convertBalloon: self.saveTiming("convert_balloon")
        self.clear_task_status()
        if liveGatherReport:
            liveGatherReport.stop()
        #deal with the extra delay
        balloonLines = []
        if convertBalloon and convertedBackpack:
            endHoney = self.getHoney()
            # getHoney returns 0 when OCR fails; leave the line out rather than report a wrong number.
            if balloonStartHoney and endHoney >= balloonStartHoney:
                balloonLines.append(f"Balloon Honey: {formatHoney(endHoney - balloonStartHoney)}")
            if balloonBlessing not in (None, "", "0"):
                balloonLines.append(f"Balloon Blessing x{balloonBlessing}")
        self.logger.webhook(f"Finished converting (Time: {self.convertSecsToMinsAndSecs(time.time()-st)})", "\n".join(balloonLines), "brown", "screen", ping_category="ping_conversion_events")
        wait = self.setdat["convert_wait"]
        if (wait):
            self.logger.webhook("", f'Waiting for an additional {wait} seconds', "light green")
        time.sleep(wait)

        if self.enableNightDetection:
            self.keyboard.press(".")
        self.converting = False
        self.hourlyReport.addHourlyStat("converting_time", time.time()-st)
        return True

    def reset(self, hiveCheck = False, convert = True, AFB = False):
        self.closeQuestMenu()
        self.alreadyConverted = False
        self.keyboard.releaseMovement()

        # Show that we're returning to hive while performing reset actions
        try:
            self.set_task_status("travelling_hive", activity="travelling", field="hive")
        except Exception:
            pass

        #reset until player is at hive
        for i in range(5):
            self.logger.webhook("", f"Resetting character, Attempt: {i+1}", "dark brown")
            #set mouse and execute hotkeys
            #mouse.teleport(self.robloxWindow.mw/(self.xsm*4.11)+40,(self.robloxWindow.mh/(9*self.ysm))+yOffset)
            self.canDetectNight = False
            st = time.time()
            closeImg = self.adjustImage("./images/menu", "close") #sticker printer
            print(f"adjusted sticker printer image: {time.time()-st}")
            if locateImageOnScreen(closeImg, self.robloxWindow.mx+(self.robloxWindow.mw/4), self.robloxWindow.my+(100), self.robloxWindow.mw/4, self.robloxWindow.mh/3.5, 0.7):
                self.keyboard.press("e")
            print(f"check sticker printer popup: {time.time()-st}")
            
            #memory match
            if self.findText("badge", self.robloxWindow.mx+(self.robloxWindow.mw/4), self.robloxWindow.my+(self.robloxWindow.mh/4), self.robloxWindow.mw/4, self.robloxWindow.mh/3.5):
                self.canDetectNight = False
                self.memoryMatch.solveMemoryMatch(self.latestMM, self.setdat.get("memory_match_rewards", []))
                self.canDetectNight = True
            print(f"checked memory match popup: {time.time()-st}")

            blenderImg = self.adjustImage("./images/menu", "blenderclose") #blender
            if locateImageOnScreen(blenderImg, self.robloxWindow.mx+(self.robloxWindow.mw/4), self.robloxWindow.my+(self.robloxWindow.mh/5), self.robloxWindow.mw/7, self.robloxWindow.mh/4, 0.8):
                self.closeBlenderGUI()
            print(f"checked blender popup: {time.time()-st}")
            
            self.clickdialog(mustFindDialog=True)
            print(f"checked dialog: {time.time()-st}")

            keepOld = self.keepOldCheck()
            if keepOld is not None:
                time.sleep(0.1)
                mouse.moveTo(*keepOld)
                time.sleep(0.2)
                mouse.click()

            #yes/no popup
            res = self.findText("no", self.robloxWindow.mx + self.robloxWindow.mw/2-300, self.robloxWindow.my, 650, self.robloxWindow.mh, exact=True)
            print(f"checked yes/no popup: {time.time()-st}")
            if res:
                mouse.moveTo(*res)
                time.sleep(0.08)
                mouse.moveBy(1,1)
                time.sleep(0.1)
                mouse.click()

            stickerBookImg = self.adjustImage("./images/menu", "stickerbookclose") #sticker book
            x = self.robloxWindow.mx+250
            y = self.robloxWindow.my+110
            res = locateImageOnScreen(stickerBookImg, x, y, 100, 80, 0.8)
            if res:
                x2, y2 = res[1]
                mouse.moveTo(x+x2, y+y2)
                time.sleep(0.08)
                mouse.moveBy(1,3)
                time.sleep(0.1)
                mouse.click()
            print(f"checked sticker book popup: {time.time()-st}")

            # ensure movement is released immediately before pressing reset keys
            self.keyboard.releaseMovement()
            time.sleep(0.15)
            for _ in range(2):
                self.keyboard.press('esc')
                time.sleep(0.3)
                self.keyboard.press('r')
                time.sleep(0.25)
                self.keyboard.press('w')
                time.sleep(0.25)
                self.keyboard.press('enter')
                time.sleep(0.4)
            self.moveMouseToDefault()
            
            emptyHealth = self.adjustImage("./images/menu", "emptyhealth_new")
            healthBar = False #check if the health bar appears when the player resets. For some reason, the empty health bar doesnt always appear
            st = time.time()
            #wait for empty health bar to appear
            while time.time() - st < 3: 
                if locateImageOnScreen(emptyHealth, self.robloxWindow.mx+(self.robloxWindow.mw-150), self.robloxWindow.my, 150, 60, 0.8):
                    healthBar = True
                    break
            if healthBar: #check if the health bar has b detected. If it hasnt, just wait for a flat time
                #if the empty health bar disappears, player has respawned
                st = time.time()
                while time.time() - st < 8:
                    if not locateImageOnScreen(emptyHealth, self.robloxWindow.mx+(self.robloxWindow.mw-150), self.robloxWindow.my, 150, 60, 0.6):
                        time.sleep(0.5)
                        break
            else:
                time.sleep(8-3)

            print(f"respawn complete: {time.time()-st}")
            self.keyboard.releaseMovement()

            if AFB: 
                self.logger.webhook("", f"AFB: Cooldown: {self.setdat['AFB_wait']} seconds", "brown")
                time.sleep(self.setdat["AFB_wait"])
                self.died = False

            if self.robloxWindow.contentYOffset == 0:
                self.robloxWindow.setRobloxWindowBounds()

            self.canDetectNight = True
            self.location = "spawn"
            #detect if player is at hive. Spin a max of 4 times
            atHive = self.spinToFaceHive()

            self.keyboard.releaseMovement()
            for _ in range(8):
                self.keyboard.press("o")
            if atHive:
                self.cannonFromHive = True
                if convert: 
                    self.convert()
                self.keyboard.releaseMovement()
                return True
            else:
                self.keyboard.walk("w", 5)
                if convert:
                    self.cannonFromHive = True
                    self.keyboard.walk("s", 0.55)
                    if self.setdat["hive_number"] < 3:
                        dir = "d"
                    else:
                        dir = "a"
                    self.walkHiveSlots(dir, abs(self.setdat["hive_number"]-3))
                    self.convert()
                else:
                    self.keyboard.walk("s", 0.15)
                    self.cannonFromHive = False
            self.keyboard.releaseMovement()
            return True
        
        else:
            self.logger.webhook("", "Unable to detect that player respawned at hive", "dark brown", "screen")

    def spinToFaceHive(self):
        """Spin the camera up to 4 times until the hive's respawn pad or balloon shows at the bottom of the screen."""
        for i in range(4):
            screen = pillowToCv2(mssScreenshot(self.robloxWindow.mx+(self.robloxWindow.mw//2-100), self.robloxWindow.my+(self.robloxWindow.mh-10), 200, 10))
            # Convert the image from BGR to HLS color space
            hsl = cv2.cvtColor(screen, cv2.COLOR_BGR2HLS)
            # Create a mask for the color range
            mask1 = cv2.inRange(hsl, resetLower1, resetUpper1)
            mask2 = cv2.inRange(hsl, resetLower2, resetUpper2)
            mask = cv2.bitwise_or(mask1, mask2)
            mask = cv2.erode(mask, resetKernel)
            #get contours. If contours exist, direction is correct
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            print(f"spin {i+1}")
            if contours:
                return True
            #failed to detect, spin
            for _ in range(4):
                self.keyboard.press(".")
            time.sleep(0.1)
        return False

    def walkHiveSlots(self, direction, slots):
        for _ in range(max(0, int(slots))):
            self.keyboard.tileWalk(direction, self.hiveSlotTiles)
            time.sleep(0.25)

    def _hiveAcquisitionControlStatus(self):
        return "stopped" if self.checkPauseAndWait() else "running"

    def stepBackOntoHivePad(self):
        self.keyboard.tileWalk("s", 1.7)
        time.sleep(0.1)

    # Hive path distances are in studs; 1 tile == 4 studs.
    _STUDS_PER_TILE = 4.0

    # Spawn → hive pad walks (overlap async+sync legs, then a short nudge).
    # Values: (async_key, async_studs, sync_key, sync_studs, nudge_key, nudge_studs)
    # hive_3 is a single Forward walk (async_key is None).
    _HIVE_SPAWN_PATHS = {
        1: ("w", 82, "d", 96, "d", 4),
        2: ("d", 50, "w", 75, "w", 4),
        3: (None, 0, "w", 58, "w", 4),
        4: ("a", 50, "w", 75, "w", 4),
        5: ("w", 82, "a", 100, "a", 4),
        6: ("w", 82, "a", 132, "a", 4),
    }

    def walkStuds(self, key, studs):
        studs = float(studs or 0)
        if studs <= 0 or not key:
            return
        self.keyboard.tileWalk(key, studs / self._STUDS_PER_TILE)

    def walkStudsAsyncThen(self, async_key, async_studs, sync_key, sync_studs):
        """Walk two keys at once for the shorter leg, then finish the longer leg alone."""
        async_studs = max(0.0, float(async_studs or 0))
        sync_studs = max(0.0, float(sync_studs or 0))
        if not async_key or async_studs <= 0:
            self.walkStuds(sync_key, sync_studs)
            return
        if not sync_key or sync_studs <= 0:
            self.walkStuds(async_key, async_studs)
            return

        overlap = min(async_studs, sync_studs)
        self.keyboard.keyDown(async_key, False)
        self.keyboard.keyDown(sync_key, False)
        self.keyboard.tileWait(overlap / self._STUDS_PER_TILE)
        if async_studs <= sync_studs:
            self.keyboard.keyUp(async_key, False)
            remaining = sync_studs - overlap
            if remaining > 0:
                self.keyboard.tileWait(remaining / self._STUDS_PER_TILE)
            self.keyboard.keyUp(sync_key, False)
        else:
            self.keyboard.keyUp(sync_key, False)
            remaining = async_studs - overlap
            if remaining > 0:
                self.keyboard.tileWait(remaining / self._STUDS_PER_TILE)
            self.keyboard.keyUp(async_key, False)

    def walkSpawnToHiveSlot(self, slot):
        """Walk from spawn to the given hive pad using _HIVE_SPAWN_PATHS."""
        path = self._HIVE_SPAWN_PATHS.get(int(slot))
        if not path:
            return False
        async_key, async_studs, sync_key, sync_studs, _, _ = path
        if async_key:
            self.walkStudsAsyncThen(async_key, async_studs, sync_key, sync_studs)
        else:
            self.walkStuds(sync_key, sync_studs)
        time.sleep(0.3)
        return True

    def nudgeHiveCheckpoint(self, slot):
        path = self._HIVE_SPAWN_PATHS.get(int(slot))
        if not path:
            return
        _, _, _, _, nudge_key, nudge_studs = path
        self.walkStuds(nudge_key, nudge_studs)
        time.sleep(0.25)

    def claimHivePromptVisible(self):
        return bool(self.isBesideE(["claim"], ["send", "trad", "trade"], log=True))

    def occupiedHivePromptVisible(self):
        return bool(self.isBesideE(["send", "trad", "trade"], ["claim"], log=True))

    def anyHivePromptVisible(self):
        return bool(self.hivePromptKind())

    def hivePromptKind(self):
        """Return the currently observed hive-prompt type, if any."""
        if self.claimHivePromptVisible():
            return "claim"
        if self.occupiedHivePromptVisible():
            return "occupied"
        return None

    def waitForHivePrompt(self, slot, max_attempts=3):
        """Wait for a hive prompt and return its type; nudge as needed."""
        time.sleep(0.2)
        for attempt in range(max(1, int(max_attempts))):
            if self._hiveAcquisitionControlStatus() == "stopped":
                return None
            prompt = self.hivePromptKind()
            if prompt:
                return prompt
            if attempt + 1 >= max_attempts:
                break
            self.nudgeHiveCheckpoint(slot)
        return self.hivePromptKind()

    def tryClaimHiveSlot(self, slot, excluded_slots=None, prompt_confirmed=False):
        """Claim ``slot`` when its Claim prompt has just been observed.

        Prompt recognition can flicker while the player is crossing a hive pad.
        Callers that have already seen the Claim prompt pass ``prompt_confirmed``
        so a missed second screenshot cannot make us walk away from an open hive.
        """
        excluded_slots = excluded_slots or set()
        self.keyboard.keyUp("a", False)
        self.keyboard.keyUp("d", False)
        if slot in excluded_slots:
            return 0
        if not prompt_confirmed and not self.claimHivePromptVisible():
            return 0
        accepted = confirm_claim(
            press_claim=lambda: self.keyboard.press("e"),
            claim_prompt_visible=self.claimHivePromptVisible,
            control_status=self._hiveAcquisitionControlStatus,
            wait=time.sleep,
        )
        return slot if accepted else 0

    def moveToNextHiveSlot(self, slot, direction, excluded_slots=None):
        """Leave the current pad and stop when the next hive prompt appears."""
        excluded_slots = excluded_slots or set()
        self.keyboard.keyDown(direction, False)
        # Wait until the current pad's prompt disappears.
        for _ in range(40):
            if self._hiveAcquisitionControlStatus() == "stopped":
                self.keyboard.keyUp(direction, False)
                return 0
            if not self.anyHivePromptVisible():
                break
            time.sleep(0.01)
        # Walk until the next pad's claim/occupied prompt appears.
        claimed = 0
        for _ in range(200):
            if self._hiveAcquisitionControlStatus() == "stopped":
                break
            if self.claimHivePromptVisible():
                self.keyboard.keyUp("a", False)
                self.keyboard.keyUp("d", False)
                self.logger.webhook("", f"Hive {slot} detected as available", "dark brown")
                claimed = self.tryClaimHiveSlot(
                    slot, excluded_slots, prompt_confirmed=True
                )
                break
            if self.occupiedHivePromptVisible():
                self.logger.webhook("", f"Hive {slot} occupied", "dark brown")
                break
            time.sleep(0.01)
        self.keyboard.keyUp("a", False)
        self.keyboard.keyUp("d", False)
        time.sleep(0.1)
        return claimed

    def scanHivesForClaim(self, start_slot, excluded_slots=None):
        """
        From start_slot, search toward hive 1 (red cannon), then reverse toward hive 6.
        Prefers the open slot closest to the red cannon when the preferred pad is taken.
        """
        excluded_slots = excluded_slots or set()
        start_slot = max(1, min(6, int(start_slot)))
        # Direction -1 walks Right (d) and decrements slot; +1 walks Left (a) and increments.
        check_direction = -1
        checking_hive = start_slot
        checked_hives = 1
        check_skip = 0

        while checked_hives < 6:
            if self._hiveAcquisitionControlStatus() == "stopped":
                return 0
            if checking_hive == 1 and check_direction == -1:
                check_direction = 1
                check_skip = checked_hives

            if check_direction == 1:
                direction = "a"
                checking_hive += 1
            else:
                direction = "d"
                checking_hive -= 1

            if checking_hive < 1 or checking_hive > 6:
                break

            claimed = self.moveToNextHiveSlot(checking_hive, direction, excluded_slots)
            if claimed:
                return claimed

            if check_skip == 0:
                checked_hives += 1
            else:
                check_skip -= 1

        return 0

    def claimHiveByCheckMethod(self, preferred_slot, excluded_slots=None):
        """Walk spawn → preferred hive, claim it, or scan neighboring pads if taken."""
        excluded_slots = set(excluded_slots or set())
        preferred_slot = max(1, min(6, int(preferred_slot)))
        self.logger.webhook("", f"Walking spawn → hive {preferred_slot} (check)", "dark brown")
        self.spinToFaceHive()
        self.walkSpawnToHiveSlot(preferred_slot)
        prompt = self.waitForHivePrompt(preferred_slot, max_attempts=3)
        if not prompt:
            for _ in range(3):
                self.stepBackOntoHivePad()
                time.sleep(0.35)
                prompt = self.hivePromptKind()
                if prompt:
                    break
            else:
                return 0

        claimed = self.tryClaimHiveSlot(
            preferred_slot, excluded_slots, prompt_confirmed=(prompt == "claim")
        )
        if claimed:
            self.logger.webhook("", f"Hive {claimed} detected as available", "dark brown")
            self.walkStuds("s", 4)
            return claimed

        if self.occupiedHivePromptVisible():
            self.logger.webhook("", f"Hive {preferred_slot} occupied", "dark brown")
        # Preferred taken/excluded, or prompt was ambiguous — scan toward cannon first.
        return self.scanHivesForClaim(preferred_slot, excluded_slots)

    def captureHiveBand(self):
        """BGR screenshot of the strip of the screen that holds the six hive pads, or None."""
        x = int(self.robloxWindow.mx + self.robloxWindow.mw * 0.01)
        y = int(self.robloxWindow.my + self.robloxWindow.mh * 0.12)
        w = int(self.robloxWindow.mw * 0.98)
        h = int(self.robloxWindow.mh * 0.32)
        if w < 60 or h < 40:
            return None
        try:
            return cv2.cvtColor(mssScreenshotNP(x, y, w, h), cv2.COLOR_BGRA2BGR)
        except Exception:
            return None

    def detectOpenHiveSlotsFromSpawn(self):
        """
        From spawn (zoomed out + pitched up), find unclaimed hive slots.

        Every open pad gets a red arrow from the player to the pad, with its head
        on the pad's disk. Screen left→right is slots 6..1, evenly spaced, so the
        slot is whichever pad the arrowhead (the top of a thin red stroke) is on.
        Returns [] when no arrow is seen, which makes the caller check slots instead.
        """
        bgr = self.captureHiveBand()
        if bgr is None:
            return []
        band_h, band_w = bgr.shape[:2]
        mask = hiveRedMask(cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))

        # Pad centers as a fraction of the band width (measured at 1920x1080).
        first_pad, pad_pitch = 0.0393, 0.1526
        min_area = 0.00004 * band_w ** 2  # small enough for a head half-covered by another player
        max_stroke = 0.013 * band_w  # arrows are ~12px at 1881px wide; hive faces and rims are far thicker

        num, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
        slots = set()
        for i in range(1, num):
            area = int(stats[i, cv2.CC_STAT_AREA])
            length = float(np.hypot(stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT]))
            if area < min_area or area / length > max_stroke:
                continue
            ys, xs = np.where(labels == i)
            top = int(np.argmin(ys))
            # the head sits on the disk row, which skips red hive faces at the top edge and stray red lower down
            if not 0.08 * band_h <= ys[top] <= 0.28 * band_h:
                continue
            pad = (xs[top] / band_w - first_pad) / pad_pitch
            if 0 <= round(pad) <= 5 and abs(pad - round(pad)) < 0.4:
                slots.add(6 - round(pad))
        return sorted(slots)

    def chooseDetectedHiveSlot(self, available_slots, preferred_slot, excluded_slots=None):
        excluded_slots = set(excluded_slots or set())
        open_slots = sorted(
            slot for slot in available_slots
            if 1 <= int(slot) <= 6 and int(slot) not in excluded_slots
        )
        if not open_slots:
            return 0
        preferred_slot = max(1, min(6, int(preferred_slot)))
        if preferred_slot in open_slots:
            return preferred_slot
        # Closest to red cannon = lowest hive number.
        return min(open_slots)

    def walkBetweenHiveSlotsForClaim(self, from_slot, to_slot, excluded_slots=None):
        """Walk pad-to-pad from from_slot toward to_slot; claim if an open prompt appears."""
        excluded_slots = set(excluded_slots or set())
        from_slot = max(1, min(6, int(from_slot)))
        to_slot = max(1, min(6, int(to_slot)))
        if from_slot == to_slot:
            return 0
        step = 1 if to_slot > from_slot else -1
        direction = "a" if step > 0 else "d"
        slot = from_slot
        while slot != to_slot:
            slot += step
            claimed = self.moveToNextHiveSlot(slot, direction, excluded_slots)
            if claimed:
                return claimed
        return 0

    def claimHiveByDetectMethod(self, preferred_slot=1, excluded_slots=None):
        """
        Zoom out and pitch up, find open hives from spawn, then walk to a
        detected pad and claim it. Returns the claimed slot, 0 if no pad on the
        row could be claimed, or None if nothing was detected from spawn.
        """
        excluded_slots = set(excluded_slots or set())
        preferred_slot = max(1, min(6, int(preferred_slot)))
        self.logger.webhook("", "Detecting Hive", "dark brown")

        # Face the hives before the camera changes, since the check reads the normal view.
        self.spinToFaceHive()

        # Zoom out so all six pads (and their claim arrows) fit on screen.
        zoom = pitch = 0
        try:
            zoom = self.setCameraZoom(5, 0)
            pitch = self.setCameraPitch(2, 0)
            time.sleep(0.35)

            available = self.detectOpenHiveSlotsFromSpawn()
            if available:
                self.logger.webhook(
                    "",
                    f"Open hives from spawn: {', '.join(str(s) for s in available)}",
                    "dark brown",
                )
                for slot in available:
                    self.logger.webhook("", f"Hive {slot} detected as available", "dark brown")
            else:
                self.logger.webhook("", "no open hives were detected from spawn", "dark brown")

            target = self.chooseDetectedHiveSlot(available, preferred_slot, excluded_slots)
        except BaseException:
            # leave the camera as the slot check expects it
            try:
                self.setCameraPitch(0, pitch)
                self.setCameraZoom(0, zoom)
            except Exception:
                pass
            raise
        if target:
            self.logger.webhook("", f"Selecting hive {target} from spawn detection", "dark brown")
            self.setCameraPitch(0, pitch)
            self.setCameraZoom(0, zoom)
            time.sleep(0.15)
            try:
                self.walkSpawnToHiveSlot(target)
                prompt = self.waitForHivePrompt(target, max_attempts=3)
                if not prompt:
                    for _ in range(3):
                        self.stepBackOntoHivePad()
                        time.sleep(0.35)
                        prompt = self.hivePromptKind()
                        if prompt:
                            break
                claimed = self.tryClaimHiveSlot(
                    target, excluded_slots, prompt_confirmed=(prompt == "claim")
                )
                if claimed:
                    self.walkStuds("s", 4)
                    return claimed

                # First pick was wrong/occupied — try other spawn-detected pads before a full scan.
                failed = {target}
                if self.occupiedHivePromptVisible():
                    self.logger.webhook("", f"Hive {target} occupied after walk", "dark brown")
                else:
                    self.logger.webhook("", f"Hive {target} prompt missing after walk", "dark brown")

                current = target
                while True:
                    nxt = self.chooseDetectedHiveSlot(
                        available, preferred_slot, excluded_slots | failed
                    )
                    if not nxt:
                        break
                    self.logger.webhook(
                        "",
                        f"Trying next detected hive {nxt} (from {current})",
                        "dark brown",
                    )
                    claimed = self.walkBetweenHiveSlotsForClaim(current, nxt, excluded_slots | failed)
                    if claimed:
                        self.walkStuds("s", 4)
                        return claimed
                    failed.add(nxt)
                    current = nxt

                # The player is on the hive row now, so check the remaining pads from here.
                self.logger.webhook("", "Scanning remaining hives", "dark brown")
                return self.scanHivesForClaim(current, excluded_slots | failed)
            except InterruptRequested:
                raise
            except Exception as exc:
                raise DetectionAfterWalkError(exc) from exc

        self.logger.webhook("", "Spawn detection found no claimable hive", "dark brown")
        self.setCameraPitch(0, pitch)
        self.setCameraZoom(0, zoom)
        return None  # still at spawn: Hive Acquisition falls back to checking slots

    def resyncHiveSlotFromHive(self):
        self.logger.webhook("", "Rechecking hive slot before rejoining", "dark brown", "screen")
        if not self.reset(convert=False):
            return False

        def alignWithCannonSideFromHive():
            self.setRobloxWindowInfo()
            self.keyboard.walk("w", 0.8)
            self.keyboard.walk("d", 1.2 * 6)

        def isHivePromptVisible():
            return self.isMakeHoneyPrompt(log=True) or self.isBesideE(["claim", "hive", "send", "trad", "trade", "has"], log=True)

        def stopAndCheckHiveSlot():
            time.sleep(0.4)
            for _ in range(3):
                if self.isMakeHoneyPrompt(log=True):
                    return True
                time.sleep(0.25)
            return False

        alignWithCannonSideFromHive()
        for _ in range(4):
            time.sleep(0.4)
            if isHivePromptVisible():
                break
            self.stepBackOntoHivePad()
        else:
            self.logger.webhook("", "Could not find hive prompts while rechecking hive slot", "dark brown", "screen")
            return False

        hiveNumber = 0
        for slot in range(1, 7):
            if slot > 1:
                self.walkHiveSlots("a", 1)
            if stopAndCheckHiveSlot():
                hiveNumber = slot
                break

        if hiveNumber == 0:
            self.logger.webhook("", "Could not find Make Honey while rechecking hive slot", "dark brown", "screen")
            return False

        self.setdat["hive_number"] = hiveNumber
        settingsManager.saveGeneralSetting("hive_number", hiveNumber)
        self.cannonFromHive = True
        self.logger.webhook("", f"Updated hive slot to {hiveNumber}; retrying cannon", "bright green", "screen")
        return True
