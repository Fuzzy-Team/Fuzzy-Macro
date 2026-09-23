import cv2
import os
import threading
from modules.controls.keyboard import keyboard
# path files run by goToPlanter use time and sleep
from modules.controls.sleep import pause_aware_time as time, sleep
from modules.macro.game_data import planterGrowthData
from modules.screen.imageSearch import findColorObjectRGB
from modules.screen.screenshot import mssScreenshotNP


class PlanterMixin:
    def goToPlanter(self, planter, field, method):
        global finalKey
        if not self.travelViaCannon("Planters"):
            return False
        self.logger.webhook("", f"Travelling: {planter.title()} Planter ({field.title()}), {method.title()}", "dark brown")
        self.goToField(field, "north")
        #move from center of field to planter spot
        finalKey = None
        path = f"../paths/planters/{field}.py"
        if os.path.isfile(path): #not all fields have a planter path
            exec(open(path).read())
        #go to the planter
        if method == "collect": #return true if the planter can be found
            time.sleep(1)
            if finalKey is not None:
                st = time.time()
                while time.time()-st < (finalKey[1]+1):
                    self.keyboard.walk(finalKey[0],0.25)
                    if self.isBesideEImage("ebutton"): 
                        return True
            else:
                time.sleep(1)
                if self.isBesideEImage("ebutton"): 
                    return True
            #can't find it, try detecting and moving to it
            self.moveToPlanter()
            if self.isBesideE(["harvest", "planter"]):
                return True
            return False
                
        else: #place, just walk there
            if finalKey is not None: self.keyboard.walk(finalKey[0], finalKey[1])
            return True

    def findPlanterInInventory(self, name):
        # Always invalidate cached planter coordinates before searching
        self.planterCoords = None
        for attempt in range(2):
            res = self.findItemInInventory(f"{name}planter")
            if res:
                self.planterCoords = res
                return
            else:
                self.logger.webhook("", f"Could not find {name}planter in inventory (attempt {attempt+1}) - retrying", "red")
                self.planterCoords = None
                time.sleep(1)

    def getPlanterHotbarSlot(self, planter):
        settingName = planter.lower().replace(" ", "_")
        try:
            slot = int(self.setdat.get(f"planter_hotbar_{settingName}_slot", 0) or 0)
        except Exception:
            return 0
        if slot < 1 or slot > 7:
            return 0
        return slot

    #place the planter and return true if successfully placed
    def placePlanter(self, planter, field, glitter):
        st = time.time()
        self.lastPlanterPlacementFailure = None
        name = planter.lower().replace(" ","").replace("-","")
        hotbarSlot = self.getPlanterHotbarSlot(planter)

        def updateHourlyTime():
            self.hourlyReport.addHourlyStat("misc_time", time.time()-st)

        def recoverAlreadyPlacedPlanterState():
            try:
                promptText = self.getTextBesideE()
                if self.isSpecificPlanterPrompt(planter, promptText):
                    return True
                self.moveToPlanter()
                promptText = self.getTextBesideE()
                return self.isSpecificPlanterPrompt(planter, promptText)
            except Exception:
                return False

        max_attempts = 2
        cooldown_seconds = 3  # Wait 3 seconds before retrying if planter is missing
        for attempt in range(max_attempts):
            findPlanterInventoryThread = None
            if hotbarSlot:
                self.planterCoords = None
            else:
                # Invalidate cached planter coordinates before each attempt
                self.planterCoords = None
                findPlanterInventoryThread = threading.Thread(target=self.findPlanterInInventory, args=(name,))
                findPlanterInventoryThread.daemon = True
                findPlanterInventoryThread.start()

            if not self.goToPlanter(planter, field, "place"):
                updateHourlyTime()
                return False
            if hotbarSlot:
                self.logger.webhook("", f"Placing {planter.title()} (slot {hotbarSlot})", "dark brown")
                self.keyboard.press(str(hotbarSlot))
            else:
                #wait for thread to finish
                findPlanterInventoryThread.join()

            #Couldn't find planter
            if not hotbarSlot and self.planterCoords is None:
                # If not found: retry only if we haven't exhausted attempts.
                if attempt < max_attempts - 1:
                    self.logger.webhook("", f"Couldn't find {planter.title()} in inventory, retrying", "red", "screen", ping_category="ping_critical_errors")
                    updateHourlyTime()
                    time.sleep(cooldown_seconds)
                    continue
                else:
                    # Final attempt failed — give up immediately.
                    if recoverAlreadyPlacedPlanterState():
                        self.logger.webhook("", f"{planter.title()} is already in {field.title()}", "orange", "screen")
                        updateHourlyTime()
                        return True
                    self.logger.webhook("", f"Couldn't find {planter.title()} in inventory", "red", "screen", ping_category="ping_critical_errors")
                    # Do not auto-disable planter settings here.
                    # A temporary state desync (already placed / stale planter data)
                    # can also make the planter unavailable in inventory.
                    self.lastPlanterPlacementFailure = "missing_inventory"
                    updateHourlyTime()
                    return False
            #place planter
            if not hotbarSlot:
                self.useItemInInventory(x=self.planterCoords[0], y=self.planterCoords[1])

            #check if planter is placed
            time.sleep(0.5)
            placedPlanter = True
            placementError = None
            for _ in range(7):
                if self.blueTextImageSearch("notinfield"):
                    placementError = "notinfield"
                    placedPlanter = False
                    break
                if self.blueTextImageSearch("maxplanters"):
                    placementError = "maxplanters"
                    placedPlanter = False
                    break
                time.sleep(0.3)
            if hotbarSlot and placedPlanter and not recoverAlreadyPlacedPlanterState():
                self.logger.webhook("", f"[Planter Placement] Hotbar slot {hotbarSlot} did not confirm {planter.title()} placement. Trying inventory fallback.", "orange", "screen")
                self.planterCoords = None
                self.findPlanterInInventory(name)
                if self.planterCoords is None:
                    placedPlanter = False
                else:
                    if not self.goToPlanter(planter, field, "place"):
                        updateHourlyTime()
                        return False
                    self.useItemInInventory(x=self.planterCoords[0], y=self.planterCoords[1])
                    time.sleep(0.5)
                    placementError = None
                    for _ in range(7):
                        if self.blueTextImageSearch("notinfield"):
                            placementError = "notinfield"
                            placedPlanter = False
                            break
                        if self.blueTextImageSearch("maxplanters"):
                            placementError = "maxplanters"
                            placedPlanter = False
                            break
                        time.sleep(0.3)
                    if placedPlanter:
                        placedPlanter = recoverAlreadyPlacedPlanterState()
            if placedPlanter: 
                self.logger.webhook("",f"Placed {planter.title()} Planter", "dark brown", "screen")
                #use glitter
                if glitter: 
                    self.useItemInInventory("glitter")
                updateHourlyTime()
                return True
            if placementError == "maxplanters" and recoverAlreadyPlacedPlanterState():
                self.logger.webhook("", f"{planter.title()} is already in {field.title()}", "orange", "screen")
                updateHourlyTime()
                return True
            if placementError == "notinfield":
                failMsg = f"Not in a field, couldn't place {planter.title()}"
            elif placementError == "maxplanters":
                failMsg = f"Already at max planters, couldn't place {planter.title()}"
            else:
                failMsg = f"Failed to place {planter.title()}"
            self.logger.webhook("", failMsg, "red", "screen", ping_category="ping_critical_errors")
            self.lastPlanterPlacementFailure = placementError or "placement_failed"
            self.reset()
            # If failed to place, wait before next attempt
            if attempt < max_attempts - 1:
                time.sleep(cooldown_seconds)
        updateHourlyTime()
        return False

    #locate the planter's growth bar and move there
    def moveToPlanter(self):
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT,(2,2))
        def getPlanterLocation():
            screen = mssScreenshotNP(self.robloxWindow.mx,self.robloxWindow.my,self.robloxWindow.mw,self.robloxWindow.mh)
            screen = cv2.cvtColor(screen, cv2.COLOR_BGRA2BGR)
            # #screen = cv2.cvtColor(screen, cv2.COLOR_BGR2HLS)
            #screen = cv2.imread("b.png")
            point = findColorObjectRGB(screen, (134, 213, 112), kernel=kernel, variance=2, draw=False)
            if not point:
                point = findColorObjectRGB(screen, (31, 231, 68), kernel=kernel, variance=2)
            
            if point:
                point = [x//self.robloxWindow.multi for x in point] 
            return point

        winUp, winDown = self.robloxWindow.mh/3.1, self.robloxWindow.mh/2.9
        winLeft, winRight = self.robloxWindow.mw/2.14, self.robloxWindow.mw/1.88

        hmove, vmove = "", ""
        for _ in range(10):
            location = getPlanterLocation()
            if location:
                break
        else:
            return
        
        x,y = location

        #move towards saturator
        if x >= winLeft and x <= winRight and y >= winUp and y <= winDown: 
            return
        if x < winLeft:
            keyboard.keyDown("a", False)
            hmove = "a"
        elif x > winRight:
            keyboard.keyDown("d", False)
            hmove = "d"
        if y < winUp:
            keyboard.keyDown("w", False)
            vmove = "w"
        elif y > winDown:
            keyboard.keyDown("s", False)
            vmove = "s"

        i = 0
        while hmove or vmove:
            #check if reached saturator
            if (hmove == "a" and x >= winLeft) or (hmove == "d" and x <= winRight):
                keyboard.keyUp(hmove, False)
                hmove = ""
                
            if (vmove == "w" and y >= winUp) or (vmove == "s" and y <= winDown):
                keyboard.keyUp(vmove, False)
                vmove = ""
            
            time.sleep(0.02)
            #taking too long, just give up
            if i >= 100:
                print("give up")
                keyboard.releaseMovement()
                break
            #update planter location
            location = getPlanterLocation()
            if location:
                x,y = location

            else: #cant find planter, pause
                keyboard.releaseMovement()
                #try to find planter
                for _ in range(10):
                    time.sleep(0.02)
                    location = getPlanterLocation()
                    #planter found
                    if location:
                        #move towards planter
                        if hmove:
                            keyboard.keyDown(hmove)
                        if vmove:
                            keyboard.keyDown(vmove)
                        x,y = location
                        break
                else: #still cant find it, give up
                    return
            i += 1

    def collectPlanter(self, planter, field, returnToHive=True):
        field_key = field.replace(" ", "_")
        self.set_task_status(f"planter_{field_key}", task="planter", field=field)
        st = time.time()
        def updateHourlyTime():
            self.hourlyReport.addHourlyStat("misc_time", time.time()-st)

        def finishCollected():
            updateHourlyTime()
            if returnToHive:
                self.reset()
            return True
        # Determine whether planter-check retry behavior is enabled for current mode
        try:
            mode = int(self.setdat.get("planters_mode", 0))
        except Exception:
            mode = 0

        if mode == 1:
            check_enabled = bool(self.setdat.get("manual_planters_check", False))
        elif mode == 2:
            check_enabled = bool(self.setdat.get("auto_planters_check", False))
        else:
            check_enabled = False

        attempts = 3 if check_enabled else 1
        collect_loot_enabled = bool(self.setdat.get("planters_collect_loot", True))

        # normalize planter name for inventory lookup
        name = planter.lower().replace(" ", "").replace("-", "")

        for attempt in range(attempts):
            if not self.goToPlanter(planter, field, "collect"):
                # If we cannot find the planter in-field, verify inventory before failing.
                # If it is already in inventory, treat this as collected so callers reset timers/state.
                self.planterCoords = None
                self.findPlanterInInventory(name)
                if self.planterCoords is not None:
                    self.logger.webhook("", f"{planter.title()} not found in field, but found in inventory. Marking as collected.", "orange", "screen")
                    return finishCollected()
                self.logger.webhook("", f"Unable to find Planter: {planter.title()}", "dark brown", "screen")
                self.reset()
                # if this was the last attempt, update time and return False
                if attempt == attempts - 1:
                    updateHourlyTime()
                    return False
                continue

            # Loot the planter
            self.keyboard.press("e")
            self.clickYes()
            self.logger.webhook("", f"Looting: {planter.title()} planter", "bright green", "screen", ping_category="ping_conversion_events")
            if collect_loot_enabled:
                self.keyboard.multiWalk(["s","d"], 0.87)
                self.nmLoot(9, 5, "a")
            else:
                self.logger.webhook("", f"Skipping loot collection for {planter.title()} planter", "orange")
            self.setMobTimer(field)

            # If planter-check not enabled, we're done
            if not check_enabled:
                return finishCollected()

            # Planter-check enabled: verify the planter is now in inventory
            # findPlanterInInventory will set self.planterCoords if found
            self.planterCoords = None
            self.findPlanterInInventory(name)
            if self.planterCoords is not None:
                # found the planter in inventory — success
                self.logger.webhook("", f"Found {planter.title()} in inventory after collect", "bright green", "screen", ping_category="ping_conversion_events")
                return finishCollected()

            # Not found: log and retry (if attempts remain)
            self.logger.webhook("", f"Planter {planter.title()} not found in inventory after looting (attempt {attempt+1}/{attempts}), retrying.", "red", "screen")
            self.reset()
            time.sleep(1)

        # Exhausted attempts — move on but warn the user
        self.logger.webhook("", f"Planter {planter.title()} still not found in inventory after {attempts} attempts. Keeping planter state and retrying later.", "orange", "screen")
        return False

    def placePlanterInCycle(self, slot, cycle):
        '''
        Returns planter, field, time planter is finish, if gather in field
        Returns none if placing it failed
        '''
        planter = self.setdat[f"cycle{cycle}_{slot+1}_planter"]
        field = self.setdat[f"cycle{cycle}_{slot+1}_field"]
        glitter = self.setdat[f"cycle{cycle}_{slot+1}_glitter"]
        gather = self.setdat[f"cycle{cycle}_{slot+1}_gather"]
        field_key = field.replace(" ", "_")
        self.set_task_status(f"planter_{field_key}", task="planter", field=field)
        #set the cooldown for planters and place them
        if not self.placePlanter(planter,field, glitter): #make sure the planter was placed
            return
        
        if self.setdat["manual_planters_collect_full"]:
            baseGrowthTime, bonusFields, fieldGrowthBonus = planterGrowthData[planter]
            bonusTime = 0
            if glitter: bonusTime += 0.25
            if field in bonusFields: bonusTime += fieldGrowthBonus
            planterGrowthTime = (baseGrowthTime/(1+bonusTime))

        else:
            planterGrowthTime = self.setdat["manual_planters_collect_every"]*60*60 
        
        planterReady = time.strftime("%H:%M:%S", time.gmtime(planterGrowthTime))
        self.logger.webhook("", f"Planter will be ready in: {planterReady}", "light blue")

        planterCompleteTime = time.time() + planterGrowthTime

        self.reset()

        return (planter, field, planterCompleteTime, gather)
