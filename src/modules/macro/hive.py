import cv2
import numpy as np
import sys
import modules.controls.mouse as mouse
import modules.misc.settingsManager as settingsManager
from modules.controls.sleep import pause_aware_time as time
from modules.hive_acquisition import confirm_claim
from modules.macro.game_data import resetKernel, resetLower1, resetLower2, resetUpper1, resetUpper2
from modules.misc.imageManipulation import pillowToCv2
from modules.screen.imageSearch import locateImageOnScreen, locateTransparentImageOnScreen
from modules.screen.screenshot import mssScreenshot, mssScreenshotNP


class HiveMixin:
    def convert(self, bypass = False, forced_convert_balloon=None):
        self.location = "spawn"
        if not bypass:
            if not self.isBesideEImage("makehoney"): 
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
        
        convertedBackpack = False
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
                self.setdat.get("macro_mode", "normal") not in ("quest", "alt")
                and self.night
                and self.setdat["stinger_hunt"]
            ):
                self.hourlyReport.addHourlyStat("converting_time", time.time()-st)
                if liveGatherReport:
                    liveGatherReport.stop()
                self.keyboard.press(".")
                self.converting = False
                self.stingerHunt()
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
        self.logger.webhook("", f"Finished converting (Time: {self.convertSecsToMinsAndSecs(time.time()-st)})", "brown", "screen", ping_category="ping_conversion_events")
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
            
            mmImg = self.adjustImage("./images/menu", "mmopen") #memory match
            if locateImageOnScreen(mmImg, self.robloxWindow.mx+(self.robloxWindow.mw/4), self.robloxWindow.my+(self.robloxWindow.mh/4), self.robloxWindow.mw/4, self.robloxWindow.mh/3.5, 0.8):
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

            performanceStatsImg = self.adjustImage("./images/menu", "performancestats")
            if locateTransparentImageOnScreen(performanceStatsImg, self.robloxWindow.mx, self.robloxWindow.my, self.robloxWindow.mw/3.5, 70, 0.7):
                if sys.platform == "darwin":
                    '''
                    #self.keyboard.keyDown("fn", False)
                    self.keyboard.keyDown("command", False)
                    self.keyboard.keyDown("option", False)
                    self.keyboard.keyDown("f7")
                    #self.keyboard.keyUp("fn")
                    self.keyboard.keyUp("command", False)
                    self.keyboard.keyUp("option", False)
                    self.keyboard.keyUp("f7", False)
                    '''
                else:
                    pass
            print(f"checked performance stats: {time.time()-st}")

            keepOld = self.keepOldCheck()
            if keepOld is not None:
                time.sleep(0.1)
                mouse.moveTo(*keepOld)
                time.sleep(0.2)
                mouse.click()

            noImg = self.adjustImage("./images/menu", "no") #yes/no popup
            x = self.robloxWindow.mx + self.robloxWindow.mw/2-300
            y = self.robloxWindow.my
            res = locateImageOnScreen(noImg, x, y, 650, self.robloxWindow.mh, 0.8)
            print(f"checked yes/no popup: {time.time()-st}")
            #mssScreenshot(x,y,self.robloxWindow.mw/2.5,self.robloxWindow.mh/3.4, True)
            if res:
                x2, y2 = [j//self.robloxWindow.multi for j in res[1]]
                mouse.moveTo(x+x2, y+y2)
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
            
            if self.newUI:
                emptyHealth = self.adjustImage("./images/menu", "emptyhealth_new")
            else:
                emptyHealth = self.adjustImage("./images/menu", "emptyhealth")
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
            atHive = False
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
                print(f"spin {i+1}: {time.time()-st}")
                if contours:
                    atHive = True
                    break
                #failed to detect, spin
                for _ in range(4):
                    self.keyboard.press(".")
                time.sleep(0.1)

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
        try:
            if self.isBesideEImage("claimhive"):
                return True
        except Exception:
            pass
        return bool(self.isBesideE(["claim"], ["send", "trad", "trade"], log=True))

    def occupiedHivePromptVisible(self):
        for name in ("sendtrade", "tradedisabled", "tradelocked"):
            try:
                if self.isBesideEImage(name):
                    return True
            except Exception:
                pass
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

    def detectOpenHiveSlotsFromSpawn(self):
        """
        From spawn (zoomed out + pitched up), find unclaimed hive slots.

        Screen left→right is slots 6..1.

        Signals (in priority order):
        1) Red claim arrows floating above pads — used when ≥2 tips map cleanly.
        2) White claim disks on the pad row, plus nearby empty faces (covers
           disks hidden under annotation/occlusion).
        3) Low bee-cell density on the hive face (ignores balloon/glare columns).

        Pad columns come from the bright pad/nametag row when spacing is even;
        otherwise an equal 6-way split of the yellow/white platform span.
        """
        x = int(self.robloxWindow.mx + self.robloxWindow.mw * 0.01)
        y = int(self.robloxWindow.my + self.robloxWindow.mh * 0.12)
        w = int(self.robloxWindow.mw * 0.98)
        h = int(self.robloxWindow.mh * 0.32)
        if w < 60 or h < 40:
            return []

        try:
            screen = mssScreenshotNP(x, y, w, h)
            bgr = cv2.cvtColor(screen, cv2.COLOR_BGRA2BGR)
            hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
        except Exception:
            return []

        red_mask = cv2.bitwise_or(
            cv2.inRange(hsv, np.array([0, 130, 130]), np.array([8, 255, 255])),
            cv2.inRange(hsv, np.array([172, 130, 130]), np.array([179, 255, 255])),
        )
        # Keep the unfiltered mask for identifying red/Festive hive faces. The
        # component cleanup below intentionally removes their large red panels.
        raw_red_mask = red_mask.copy()
        # Strip ultra-wide red strokes (hand-drawn arrows / UI, not claim chevrons).
        num_red, red_labels, red_stats, _ = cv2.connectedComponentsWithStats(red_mask, 8)
        for i in range(1, num_red):
            bw = int(red_stats[i, cv2.CC_STAT_WIDTH])
            bh = int(red_stats[i, cv2.CC_STAT_HEIGHT])
            area = int(red_stats[i, cv2.CC_STAT_AREA])
            if area > 400 and (bw > w * 0.12 or bh > h * 0.35):
                red_mask[red_labels == i] = 0

        kernel = np.ones((3, 3), np.uint8)
        red_mask = cv2.morphologyEx(red_mask, cv2.MORPH_OPEN, kernel, iterations=1)
        red_mask = cv2.morphologyEx(red_mask, cv2.MORPH_CLOSE, kernel, iterations=2)

        band_h, band_w = red_mask.shape[:2]
        min_area = max(140, int(200 * (band_w / 1024.0) ** 2))

        # --- 6 pad column centers ---
        pad_row = hsv[: max(1, int(band_h * 0.35))]
        bright = (
            (pad_row[:, :, 2] > 175) & (pad_row[:, :, 1] < 100)
        ).astype(np.uint8) * 255
        proj = bright.sum(axis=0).astype(np.float32)
        if float(proj.max()) <= 0:
            proj = np.ones(band_w, dtype=np.float32)
        k = max(9, (band_w // 90) | 1)
        proj_s = np.convolve(proj, np.ones(k, dtype=np.float32) / k, mode="same")
        min_dist = max(40, band_w // 14)
        height_thr = max(10.0, float(proj_s.max()) * 0.10)
        peaks = []
        for i in range(1, band_w - 1):
            if proj_s[i] < height_thr:
                continue
            if proj_s[i] >= proj_s[i - 1] and proj_s[i] >= proj_s[i + 1]:
                if band_w * 0.02 < i < band_w * 0.98:
                    peaks.append((float(proj_s[i]), i))
        peaks.sort(reverse=True)
        kept_peaks = []
        for _hgt, px in peaks:
            if any(abs(px - kx) < min_dist for kx in kept_peaks):
                continue
            kept_peaks.append(px)
            if len(kept_peaks) >= 6:
                break
        kept_peaks = sorted(kept_peaks)

        use_peaks = False
        if len(kept_peaks) == 6:
            diffs = np.diff(kept_peaks)
            spacing_ratio = float(np.max(diffs)) / max(float(np.min(diffs)), 1.0)
            # Uneven peaks remap slots (e.g. 5,6 → wrong columns); fall back.
            use_peaks = spacing_ratio < 2.2

        if use_peaks:
            centers = [float(p) for p in kept_peaks]
        else:
            white_mask = cv2.inRange(hsv, np.array([0, 0, 200]), np.array([179, 55, 255]))
            yellow_mask = cv2.inRange(hsv, np.array([16, 100, 140]), np.array([40, 255, 255]))
            plat = cv2.bitwise_or(white_mask, yellow_mask)
            pproj = plat.sum(axis=0).astype(np.float32)
            if float(pproj.max()) > 0:
                thr = max(float(pproj.max()) * 0.18, 1.0)
                xs = np.where(pproj >= thr)[0]
                if xs.size >= 2:
                    row_left, row_right = int(xs[0]), int(xs[-1])
                else:
                    row_left, row_right = int(band_w * 0.06), int(band_w * 0.94)
            else:
                row_left, row_right = int(band_w * 0.06), int(band_w * 0.94)
            if (row_right - row_left) > band_w * 0.92 or (row_right - row_left) < band_w * 0.30:
                row_left, row_right = int(band_w * 0.06), int(band_w * 0.94)
            span = max(1, row_right - row_left)
            centers = [row_left + (i + 0.5) * span / 6.0 for i in range(6)]

        slot_w = float(np.median(np.diff(centers))) if len(centers) > 1 else band_w / 6.0

        # --- Per-slot face / pad metrics ---
        bees_map = {}
        white_map = {}
        bright_mid_map = {}
        red_hive_map = {}
        for i, slot in enumerate((6, 5, 4, 3, 2, 1)):
            cx = centers[i]
            half = max(18.0, slot_w * 0.36)
            x0 = max(0, int(cx - half))
            x1 = min(band_w, int(cx + half))
            face = hsv[: max(1, int(band_h * 0.50)), x0:x1]
            face_red = red_mask[: max(1, int(band_h * 0.50)), x0:x1]
            if face.size == 0:
                bees_map[slot] = 1.0
                white_map[slot] = 0.0
                bright_mid_map[slot] = 0.0
                red_hive_map[slot] = 0.0
                continue
            fh, fs, fv = face[:, :, 0], face[:, :, 1], face[:, :, 2]
            colored_px = (fs > 110) & (fv > 100) & ~((fh >= 35) & (fh <= 85))
            # A claim arrow can overlap the lower face region, so red used to be
            # discarded here entirely.  That also discarded red/Festive hive
            # cells and made occupied hives (most noticeably slot 3) look empty.
            # Red in the upper hive-cell region is occupancy; keep excluding it
            # below that region where floating claim arrows appear.
            face_rows = np.arange(face.shape[0])[:, None]
            upper_hive = face_rows < int(band_h * 0.25)
            bee_px = colored_px & ((face_red == 0) | upper_hive)
            bees_map[slot] = float(bee_px.mean())
            upper_red = raw_red_mask[: max(1, int(band_h * 0.25)), x0:x1]
            red_hive_map[slot] = float((upper_red > 0).mean())
            pad = hsv[int(band_h * 0.40) :, x0:x1]
            if pad.size:
                white_map[slot] = float(
                    ((pad[:, :, 2] > 200) & (pad[:, :, 1] < 70)).mean()
                )
            else:
                white_map[slot] = 0.0
            mid = hsv[int(band_h * 0.25) : int(band_h * 0.55), x0:x1]
            if mid.size:
                # Balloons / bright glare falsely look "empty" on bee density alone.
                bright_mid_map[slot] = float(
                    ((mid[:, :, 2] > 210) & (mid[:, :, 1] < 80)).mean()
                )
            else:
                bright_mid_map[slot] = 0.0

        pad_slots = {
            slot
            for slot, bees in bees_map.items()
            if bees < 0.40 and bright_mid_map[slot] < 0.15
        }
        white_slots = {slot for slot, white in white_map.items() if white >= 0.08}

        # --- Floating red claim arrows ---
        num_labels, labels, stats, _centroids = cv2.connectedComponentsWithStats(
            red_mask, connectivity=8
        )
        # Tips in the top of the band are usually drawings/UI on the pad row,
        # not floating claim arrows.
        pad_row_y = int(band_h * 0.28)
        tips = []
        for i in range(1, num_labels):
            area = int(stats[i, cv2.CC_STAT_AREA])
            if area < 80:
                continue
            bw = int(stats[i, cv2.CC_STAT_WIDTH])
            bh = int(stats[i, cv2.CC_STAT_HEIGHT])
            if bw > slot_w * 0.95 and bh < bw * 0.35:
                continue
            if bw > slot_w * 1.55:
                continue
            ys, xs = np.where(labels == i)
            if ys.size == 0:
                continue
            ycut = float(np.quantile(ys, 0.80))
            tip_xs = xs[ys >= ycut]
            tip_ys = ys[ys >= ycut]
            if tip_xs.size == 0:
                continue
            tip_x = float(tip_xs.mean())
            tip_y = float(tip_ys.mean())
            if tip_y < pad_row_y:
                continue
            tips.append((area, tip_x, tip_y))

        tips.sort(key=lambda t: t[0], reverse=True)
        kept = []
        for area, tip_x, tip_y in tips:
            if area < min_area:
                continue
            if any(abs(tip_x - kx) < slot_w * 0.85 for _, kx, _ in kept):
                continue
            kept.append((area, tip_x, tip_y))

        tip_bias = 0.18 * slot_w
        arrow_slots = set()
        for area, tip_x, tip_y in kept:
            eff_x = tip_x - tip_bias
            dists = [abs(eff_x - c) for c in centers]
            idx = int(np.argmin(dists))
            if dists[idx] > slot_w * 0.55:
                continue
            slot = 6 - idx
            # A red/Festive hive panel can leave arrow-sized red components in
            # the lower face. Do not accept those as claim arrows when the same
            # slot has substantial red coverage across its upper hive face.
            if red_hive_map.get(slot, 0.0) >= 0.08:
                continue
            arrow_slots.add(slot)

        # Prefer multiple floating arrows; else white disks (+ empty companions);
        # else empty faces alone.
        if len(arrow_slots) >= 2:
            available = sorted(arrow_slots)
        elif len(white_slots) >= 2:
            companions = {slot for slot in pad_slots if bees_map[slot] < 0.32}
            available = sorted(white_slots | companions)
        elif pad_slots:
            available = sorted(pad_slots)
        else:
            available = sorted(arrow_slots | white_slots)

        return available

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
        detected pad and claim it. Hive Acquisition owns the check fallback.
        """
        excluded_slots = set(excluded_slots or set())
        preferred_slot = max(1, min(6, int(preferred_slot)))
        self.logger.webhook("", "Detecting Hive", "dark brown")

        # Zoom out so all six pads (and their claim arrows) fit on screen.
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
        if target:
            self.logger.webhook("", f"Selecting hive {target} from spawn detection", "dark brown")
            self.setCameraPitch(0, pitch)
            self.setCameraZoom(0, zoom)
            time.sleep(0.15)
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

            return 0

        self.logger.webhook("", "Spawn detection found no claimable hive", "dark brown")
        self.setCameraPitch(0, pitch)
        self.setCameraZoom(0, zoom)
        return 0

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
