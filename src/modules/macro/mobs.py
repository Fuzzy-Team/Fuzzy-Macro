import threading
import traceback
import modules.controls.mouse as mouse
import modules.misc.settingsManager as settingsManager
from modules.controls.sleep import pause_aware_time as time, sleep
import modules.macro.pattern_environment as patternEnvironment
from modules.macro.game_data import (
    mobRespawnTimes,
    regularMobQuantitiesInFields,
    regularMobTypesInFields,
)
from modules.screen.imageSearch import locateImageOnScreen


class MobMixin:
    def hasMondoRespawned(self):
        #check if mondo can be collected (first 10mins)
        minute = self.getCurrentMinute()
        #set respawn time to 20mins
        #mostly just to prevent the macro from going to mondo over and over again for the 10mins
        return minute <= 10 and self.hasRespawned("mondo", 20*60)

    def collectMondoBuff(self, gatherInterrupt = False):
        self.set_task_status("mondo_buff", activity="mondo")
        self.logger.webhook("","Travelling: Mondo Buff","dark brown")
        #go to mondo buff
        if not self.travelViaCannon("Mondo Buff"):
            return False
        self.keyboard.press("e")
        sleep(2.5)
        self.logger.webhook("","Collecting: Mondo Buff","yellow", "screen")
        self.keyboard.walk("w",1)
        self.keyboard.walk("d",3) 
        if self.setdat["mondo_buff_loot"]: # If looting is enabled, wait until mondo is defeated
            self.logger.webhook("", "Waiting for Mondo to be defeated", "light green")
            self.keyboard.press("shift") #moves slightly up (or down) when hitting wall, so this reduces that
            while True:
                #defeat
                if self.blueTextImageSearch("defeated") and self.blueTextImageSearch("mondo"): 
                    self.saveTiming("mondo") 
                    break
                #died
                if self.blueTextImageSearch("died"):
                    self.died = True
                    self.keyboard.press("shift")
                    self.logger.webhook("", "Player Died", "red", "screen", ping_category="ping_character_deaths")
                    self.reset(convert=False)
                    #sev recursion here is pretty weird
                    #TODO: not make it recursive
                    self.collectMondoBuff()
                    return
                #time limit
                if self.getCurrentMinute() >= 15: #mondo despawns after 15 minutes if not defeated in time
                    self.keyboard.walk("s",1, False)
                    self.keyboard.press(",")
                    time.sleep(0.5)
                    self.logger.webhook("", "Time Limit (15 minutes)\n Mondo may have despawned. Resetting", "light green", "screen")
                    self.keyboard.press("shift")
                    self.saveTiming("mondo") 
                    self.reset(convert=True)
                    return False
                #collect tokens by bees
                if self.setdat["mondo_collect_token"]: 
                    self.keyboard.walk("a", 0.45)
                    for slowmove in range(9):
                        self.keyboard.walk("d", 0.048, False) #move JUST EVER SO SLIGHTLY, maybe bumps in to wall less
                        time.sleep(0.035)
                mouse.click()
                time.sleep(1.5)

            #loot
            mondo_loot_times = self.setdat["mondo_loot_times"] #how many loops based on what the user inputted
            time.sleep(0.1)
            self.keyboard.walk("d",1,False)
            time.sleep(0.1)
            self.keyboard.press("shift")
            self.keyboard.walk("s",3.15,False)
            self.logger.webhook("", "Looting: Mondo Chick", "yellow", "screen")
            if mondo_loot_times == 1:
                self.logger.webhook("", "Looping 1 time", "light green")
            else:
                self.logger.webhook("", f"Looping {mondo_loot_times} times", "light green")
            self.keyboard.walk("a",3.55)
            for loops in range(mondo_loot_times): 
                for looting in range(6):
                    self.keyboard.walk("w",0.20)
                    self.keyboard.walk("d",2.65)
                    self.keyboard.walk("w",0.20)
                    self.keyboard.walk("a",2.65)
                for looting in range(6):
                    self.keyboard.walk("s",0.20)
                    self.keyboard.walk("d",2.65)
                    self.keyboard.walk("s",0.20)
                    self.keyboard.walk("a",2.65)
        else: #if loot off, just idle
            mondo_buff_wait = self.setdat["mondo_buff_wait"]
            mondo_buff_wait_label = f"{mondo_buff_wait:g}" if isinstance(mondo_buff_wait, float) else str(mondo_buff_wait)
            end_time = time.perf_counter() + mondo_buff_wait * 60  
            self.logger.webhook("", f"Collecting for: {mondo_buff_wait_label} minutes", "yellow")
            # if collecting tokens produced by bees
            if self.setdat["mondo_collect_token"]:
                # enable shiftlock
                self.keyboard.press("shift")
                while time.perf_counter() < end_time: 
                    self.keyboard.walk("a", 0.45)
                    for slowmove in range(9):
                        self.keyboard.walk("d", 0.048, False) #move JUST EVER SO SLIGHTLY, maybe bumps in to wall less
                        time.sleep(0.035) 
                    time.sleep(3) #longer since we are not detecting anything
            else:
                time.sleep(mondo_buff_wait * 60)
            self.saveTiming("mondo") 
            self.logger.webhook("","Collected: Mondo Buff","light green", ping_category="ping_mondo_buff")
        #done
        self.reset(convert=True)
        return True

    #accept mob and field and return them in the format used for timings.txt file
    #mob_field, eg ladybug_strawberry
    #werewolf is an exception, just return "werewolf"
    def formatMobTimingName(self, mob, field):
        if mob == "werewolf": return mob
        return f"{mob}_{field}"

    def hasMobRespawned(self, mob, field, timing = None):
        return self.hasRespawned(self.formatMobTimingName(mob, field), mobRespawnTimes[mob], True, timing)

    #to be used by the mob run walk paths
    #returns true if there are mobs in the field to be killed (enabled + respawned)
    #returns a list of mobs that have respawned
    def getRespawnedMobs(self, field):
        mobs = regularMobTypesInFields[field]
        out = []
        for m in mobs:
            if self.setdat[m] and self.hasMobRespawned(m, field):
                out.append(m)
        return out

    #check which mobs have respawned in the field and reset their timings
    def setMobTimer(self, field):
        if not field in regularMobTypesInFields: return
        timings = self.getTiming()
        mobs = regularMobTypesInFields[field]
        for m in mobs:
            timingName = self.formatMobTimingName(m, field)
            if not timingName in timings:
                continue
            #check respawn
            if self.hasMobRespawned(m, field, timings[timingName]):
                timings[timingName] = time.time()
                self.hourlyReport.addHourlyStat("bugs", regularMobQuantitiesInFields[field][m])
        settingsManager.saveDict(settingsManager.getUserDataPath("timings.txt"), timings)

    #background thread function to determine if player has defeated the mob
    #time limit of 20s
    def mobRunAttackingBackground(self):
        st = time.time()
        if self.setdat["bees"] > 40:
            timeout = 20
        elif self.setdat["bees"] > 30:
            timeout = 30
        else:
            timeout = 40

        while True:
            if self.blueTextImageSearch("died"):
                self.mobRunStatus = "dead"
                break
            elif self.blueTextImageSearch("defeated"):
                self.mobRunStatus = "looting"
                break
            elif time.time() - st > timeout:
                self.mobRunStatus = "timeout"
                break

    #background thread to check if token link is collected or the macro runs out of time (max 15s)
    def mobRunLootingBackground(self):
        st = time.time()
        while time.time() - st < 20:
           if self.blueTextImageSearch("tokenlink", 0.8):
            time.sleep(0.5) 
            self.logger.webhook("","Collected Token Link", "white", "blue")
            break
        self.mobRunStatus = "done"

    def killMob(self, mob, field, walkPath = None):
        mobName = mob
        if mob == "rhinobeetle": mobName = "rhino beetle"
        self.set_task_status("bugrun", activity=mob, details=f"Attacking in {field.title()}")
        self.logger.webhook("","{}: {} ({})".format("Travelling" if walkPath is None else "Walking", mobName.title(),field.title()),"dark brown")
        self.mobRunStatus = "attacking"
        attackThread = threading.Thread(target=self.mobRunAttackingBackground)
        attackThread.daemon = True
        if walkPath is None:
            self.waitForBees()
            if not self.travelViaCannon(f"{mobName.title()}"):
                return
            self.goToField(field, "north")
            #attack the mob
            attackThread.start()
        else:
            #attack the mob
            #attack thread will start in the path
            self.canDetectNight = False
            exec(walkPath)
            self.canDetectNight = True
        self.location = field
        self.logger.webhook("","Attacking: {} ({})".format(mobName.title(),field.title()),"dark brown")
        
        st = time.time()
        def updateHourlyTime():
            self.hourlyReport.addHourlyStat("bug_run_time", time.time()-st)
        #move in squares to evade attacks
        #save the last entered side and front keys. This will be used for the looting pattern
        distance = 0.7
        lastSideKey = "d"
        lastFrontKey = "s"
        def dodgeWalk(k,t):
            nonlocal lastSideKey, lastFrontKey
            if k in ["w", "s"]: lastFrontKey = k
            elif k in ["a","d"]: lastSideKey = k
            self.keyboard.walk(k, t)
        while True:
            # Check if paused and wait
            if self.checkPauseAndWait():
                # Stop was requested while paused
                self.mobRunStatus = "done"
                break
            dodgeWalk("s", distance*1.2)
            if self.mobRunStatus != "attacking": break
            dodgeWalk("a", distance*1.8)
            if self.mobRunStatus != "attacking": break
            dodgeWalk("w", distance*1.2)
            if self.mobRunStatus != "attacking": break
            dodgeWalk("d", distance*1.8)
            if self.mobRunStatus != "attacking": break

        attackThread.join()
        if self.mobRunStatus == "dead":
            self.logger.webhook("","Player died", "dark brown","screen", ping_category="ping_character_deaths")
            updateHourlyTime()
            return
        elif self.mobRunStatus == "timeout":
            self.setMobTimer(field)
            self.logger.webhook("","Could not kill {} in time. Maybe it hasn't respawned?".format(mobName.title()), "dark brown", "screen")
            updateHourlyTime()
            return
        time.sleep(1.5)
        #loot
        self.logger.webhook("", "Looting: {}".format(mobName.title()), "bright green", "screen")
        #start another background thread to check for token link/time limit
        lootThread = threading.Thread(target=self.mobRunLootingBackground)
        lootThread.daemon = True
        lootThread.start()
        def lootPattern(f, s):
            if lastSideKey == "a":
                startSideKey = "d"
            elif lastSideKey == "d":
                startSideKey = "a"

            if lastFrontKey == "w":
                startFrontKey = "s"
            elif lastFrontKey == "s":
                startFrontKey = "w"

            while True:
                # Check if paused and wait
                if self.checkPauseAndWait():
                    return  # Stop was requested
                for _ in range(2):
                    self.keyboard.walk(startFrontKey, 0.72*f)
                    if self.mobRunStatus == "done": return
                    self.keyboard.walk(startSideKey, 0.1*s)
                    if self.mobRunStatus == "done": return
                    self.keyboard.walk(lastFrontKey, 0.72*f)
                    if self.mobRunStatus == "done": return
                    self.keyboard.walk(startSideKey, 0.1*s)
                    if self.mobRunStatus == "done": return
                for _ in range(2):
                    self.keyboard.walk(startFrontKey, 0.72*f)
                    if self.mobRunStatus == "done": return
                    self.keyboard.walk(lastSideKey, 0.1*s)
                    if self.mobRunStatus == "done": return
                    self.keyboard.walk(lastFrontKey, 0.72*f)
                    if self.mobRunStatus == "done": return
                    self.keyboard.walk(lastSideKey, 0.1*s)
                    if self.mobRunStatus == "done": return
        lootPattern(1.35, 2.5)
        self.setMobTimer(field)
        self.clear_task_status()
        lootThread.join()
        #check if there are paths for the macro to walk to other fields for mob runs
        #run a path in the field format
        updateHourlyTime()
        self.runPath(f"mob_runs/{field}", fileMustExist=False)

    def stingerHuntBackground(self):
        #find vic
        while not self.stopVic:
            #detect which field the vic is in
            if self.vicField is None:
                for field in self.vicFields:
                    if self.blueTextImageSearch(f"vic{field}", 0.75):
                        self.vicField = field
                        break
            else:
                if self.blueTextImageSearch("died"): self.died = True
            
            if self.blueTextImageSearch("vicdefeat"):
                self.vicStatus = "defeated"

    def stingerHunt(self):
        self.set_task_status("stinger_hunt", activity="vicious")

        class VicStopPathException(Exception):
            pass

        def vicSearchWalk(key, t):
            if self.vicField and currField != self.vicField:
                raise VicStopPathException()
            self.keyboard.walk(key, t)

        self.vicStatus = None
        self.vicField = None
        self.stopVic = False
        currField = None
        self.clear_task_status()

        stingerHuntThread = threading.Thread(target=self.stingerHuntBackground)
        stingerHuntThread.daemon = True
        stingerHuntThread.start()
        vicStartTime = time.time()
        def updateHourlyTime():
            self.hourlyReport.addHourlyStat("bug_run_time", time.time()-vicStartTime)

        for currField in self.vicFields:
            #go to field
            if not self.travelViaCannon("Stinger Hunt"):
                self.stopVic = True
                stingerHuntThread.join()
                updateHourlyTime()
                self.night = False
                return
            self.logger.webhook("",f"Travelling to {currField} (stinger hunt)","dark brown")
            self.goToField(currField, "south")
            time.sleep(0.8)
            try:
                exec(open(f"../paths/vic/find_vic/{currField}.py").read())
            except VicStopPathException:
                pass
            if self.vicField:
                self.logger.webhook("",f"Vicious Bee detected ({self.vicField})", "light blue", "screen") 
                break
            print(self.vicField)
            self.reset(convert=False)
        else: #unable to find vic
            self.stopVic = True
            stingerHuntThread.join()
            self.convert()
            updateHourlyTime()
            self.night = False
            return
        
        #kill vic
        def goToVicField(wait=False):
            self.reset(convert=False)
            if wait:
                time.sleep(10)
            self.logger.webhook("",f"Travelling to {self.vicField} (vicious bee)","dark brown")
            if not self.travelViaCannon("Vicious Bee", resetIfAway=False):
                return False
            self.goToField(self.vicField, "south")
            return True

        #first, check if vic is found in the same field as the player
        if currField != self.vicField: 
            if not goToVicField():
                self.night = False
                self.stopVic = True
                updateHourlyTime()
                stingerHuntThread.join()
                return
        
        #run the dodge pattern
        #similar to the search pattern, between each line of code, check if vic has been defeated/player died
        pathLines = open(f"../paths/vic/kill_vic/{self.vicField}.py").read().split("\n")
        loop = True
        self.died = False
        st = time.time() 
        while loop:
            # Check if paused and wait
            if self.checkPauseAndWait():
                # Stop was requested while paused
                self.night = False
                self.stopVic = True
                updateHourlyTime()
                return
            for code in pathLines:
                exec(code)
                #run checks
                if self.died or self.vicStatus is not None: break
            if self.vicStatus == "defeated":
                self.logger.webhook("","Vicious Bee Defeated","light green", "screen", ping_category="ping_vicious_bee")
                self.hourlyReport.addHourlyStat("vicious_bees", 1)
                break
            elif self.died:
                self.logger.webhook("","Player Died","dark brown", "screen", ping_category="ping_character_deaths")
                if not goToVicField(wait=True):
                    break
                self.died = False
            elif time.time()-st > 180: #max 3 mins to kill vic
                self.logger.webhook("","Took too long to kill Vicious Bee","red", "screen", ping_category="ping_critical_errors")
                break
        self.night = False
        updateHourlyTime()
        self.stopVic = True
        stingerHuntThread.join()
        self.reset()

    def stumpSnail(self):
        sideTaskIntervalMinutes = self.setdat.get("stump_snail_balloon_interval", 0)
        try:
            sideTaskInterval = max(0, int(sideTaskIntervalMinutes)) * 60
        except (TypeError, ValueError):
            sideTaskInterval = 0
        patternDuration = 120

        def goToStump():
            for _ in range(3):
                self.cannon()
                self.logger.webhook("", "Travelling: Stump Snail", "dark brown")
                self.goToField("stump")
                if self.placeSprinkler():
                    return True
                self.logger.webhook("", "Failed to land in stump field", "red", "screen", ping_category="ping_critical_errors")
                self.reset()
            return False

        def runGatherPattern(patternName, duration):
            st = time.time()
            mouse.moveBy(10, 5)
            self.keyboard.releaseMovement()
            nameSpace = {**locals(), **vars(patternEnvironment)}
            while time.time() - st < duration:
                if self.checkPauseAndWait():
                    break
                mouse.mouseDown()
                try:
                    exec(open(f"../settings/patterns/{patternName}.py").read(), nameSpace)
                except Exception:
                    print(traceback.format_exc())
                    break
                mouse.mouseUp()
            mouse.mouseUp()

        def runSideTask():
            self.logger.webhook("", "Stump Snail: Running periodic side task", "dark brown")
            self.reset(convert=False)
            self.runPath("cannon_to_field/pine")
            runGatherPattern("skillet", patternDuration)
            self.reset(convert=True)
            goToStump()

        goToStump()

        # Set status to attacking for hotbar logic
        self.set_task_status("attacking", activity="stump_snail")
        try:
            keepOldData = None
            while keepOldData is None:
                cycleStart = time.time()
                if self.checkPauseAndWait():
                    return
                while True:
                    if self.checkPauseAndWait():
                        return
                    mouse.click()
                    keepOldData = self.keepOldCheck()
                    if keepOldData is not None:
                        mouse.mouseUp()
                        break
                    if sideTaskInterval <= 0 or time.time() - cycleStart >= sideTaskInterval:
                        mouse.mouseUp()
                        break

                if keepOldData is None and sideTaskInterval > 0:
                    runSideTask()
        finally:
            self.set_task_status(None, update_presence=False)  # Reset status after attack
        #handle the other stump snail
        self.logger.webhook("","Stump Snail Killed","bright green", "screen", ping_category="ping_mob_events")
        self.saveTiming("stump_snail")
        def keepOld():
            time.sleep(0.5)
            mouse.moveTo(*keepOldData)
            mouse.click()

        def replace():
            replaceImg = self.adjustImage("./images/menu", "replace")
            x = self.robloxWindow.mx + self.robloxWindow.mw/2-300
            y = self.robloxWindow.my
            res = locateImageOnScreen(replaceImg, x, y, 650, self.robloxWindow.mh, 0.8)
            if res is not None:
                ix, iy = [j//self.robloxWindow.multi for j in res[1]]
                mouse.moveTo(x + ix + 5, y + iy + 5)
                mouse.click()
                return
            if keepOldData is not None:
                mouse.moveTo(keepOldData[0] + 170, keepOldData[1])
                mouse.click()
        amulet = self.setdat["stump_snail_amulet"]
        if amulet == "keep":
            keepOld()
        elif amulet == "replace":
            replace()
        elif amulet == "stop":
            while self.keepOldCheck(): mouse.click()
        elif amulet == "wait for command":
            self.set_task_status("amulet_wait", update_presence=False)
            #wait for user to send command to bot
            while self.status.value == "amulet_wait": mouse.click()
            if self.status.value == "amulet_keep":
                keepOld()
            elif self.status.value == "amulet_replace":
                replace()

        self.clear_task_status()

    #implementation of natro's nm_loot function
    def nmLoot(self, length, reps, dirKey):
        for _ in range(reps):
            self.keyboard.tileWalk("w", length)
            self.keyboard.tileWalk(dirKey, 1.5)
            self.keyboard.tileWalk("s", length)
            self.keyboard.tileWalk(dirKey, 1.5)

    def coconutCrabBackground(self):
        while self.bossStatus is None:
            if self.blueTextImageSearch("died"):
                self.died = True
            if self.blueTextImageSearch("coconutcrab_defeat", 0.8):
                self.bossStatus = "defeated"

    def coconutCrab(self):
        self.bossStatus = None
        self.set_task_status("coconut_crab", activity="coconut_crab")
        cocoThread = threading.Thread(target=self.coconutCrabBackground)
        cocoThread.daemon = True
        cocoThread.start()
        st = time.time()
        for _ in range(2):
            if not self.travelViaCannon("Coconut Crab"):
                self.bossStatus = "travel_failed"
                cocoThread.join()
                return
            self.logger.webhook("","Travelling: Coconut Crab","dark brown")
            self.goToField("coconut")
            self.keyboard.walk("s", 1)
            self.keyboard.walk("d", 3)
            self.died = False
            self.bossStatus = None
            st = time.time()
            while True:
                mouse.mouseDown()
                #simplified version of natro's coco crab pattern
                for i in range(2):
                    self.keyboard.walk("a",6, False)
                    self.keyboard.walk("d",6-i*1.8, False)
                self.keyboard.walk("s",2)
                time.sleep(4.5)
                self.keyboard.walk("w",1)
                mouse.mouseUp()
                # Respect user-configurable max kill time (minutes)
                max_kill_time = self.setdat.get("coconut_crab_max_kill_time", 15)
                if time.time() - st > max_kill_time * 60:
                    self.bossStatus = "timelimit"
                if self.died or self.bossStatus is not None: break
            
            if self.died:
                self.logger.webhook("", "Died to Coconut Crab", "dark brown", ping_category="ping_character_deaths")
                self.reset(convert=False)
                self.died = False
            elif self.bossStatus is not None:
                break
            
        if self.bossStatus == "timelimit":
            self.logger.webhook("", "Time Limit: Coconut Crab", "dark brown", ping_category="ping_critical_errors")
        elif self.bossStatus == "defeated":
            self.keyboard.walk("a", 2)
            self.logger.webhook("", "Defeated: Coconut Crab", "bright green", "screen", ping_category="ping_mob_events")
            self.nmLoot(9, 4, "d")
            self.nmLoot(9, 4, "a")
            self.nmLoot(9, 4, "d")
            self.nmLoot(9, 4, "a")
            self.nmLoot(9, 4, "d")
            self.nmLoot(9, 4, "a")
        cocoThread.join()
        self.hourlyReport.addHourlyStat("bug_run_time", time.time()-st)
        self.saveTiming("coconut_crab")
        self.clear_task_status()
        self.reset()

    def kingBeetle(self):
        st = time.time()
        for _ in range(2):
            if not self.travelViaCannon("King Beetle"):
                return
            self.logger.webhook("","Travelling: King Beetle","dark brown")
            self.goToField("blue_flower")
            self.died = False
            self.bossStatus = None
            self.runPath("boss/king_beetle")

            # Continue the movement pattern and check for defeat
            while self.bossStatus is None and not self.died:
                # Check if defeated
                if self.blueTextImageSearch("defeated"):
                    self.bossStatus = "defeated"
                    break
                # Check if died
                if self.blueTextImageSearch("died"):
                    self.died = True
                    break
                # Continue movement
                self.keyboard.walk("d", 0.25)
                sleep(0.75)

            # Collect rewards if defeated
            if self.bossStatus == "defeated":
                self.keyboard.walk("a", 1)
                self.keyboard.walk("w", 3)
                for i in range(3):
                    self.keyboard.walk("a", 0.25)
                    self.keyboard.walk("s", 2)
                    self.keyboard.walk("a", 0.25)
                    self.keyboard.walk("w", 2)
                sleep(1)

            if self.died or self.bossStatus is not None: break

        if self.died:
            self.logger.webhook("", "Died to King Beetle", "dark brown", ping_category="ping_character_deaths")
            self.reset(convert=False)
            self.died = False
        elif self.bossStatus == "defeated":
            self.logger.webhook("", "Defeated: King Beetle", "bright green", "screen", ping_category="ping_mob_events")
        self.hourlyReport.addHourlyStat("bug_run_time", time.time()-st)
        self.saveTiming("king_beetle")
        self.reset()

    def tunnelBear(self):
        st = time.time()
        for _ in range(2):
            if not self.travelViaCannon("Tunnel Bear"):
                return
            self.logger.webhook("","Travelling: Tunnel Bear","dark brown")
            self.goToField("pineapple")
            self.died = False
            self.bossStatus = None
            self.runPath("boss/tunnel_bear")
            
            # Continue the movement pattern and check for defeat
            while self.bossStatus is None and not self.died:
                # Check if defeated
                if self.blueTextImageSearch("defeated"):
                    self.bossStatus = "defeated"
                    break
                # Check if died
                if self.blueTextImageSearch("died"):
                    self.died = True
                    break
                # Continue movement
                self.keyboard.walk("d", 0.25)
                sleep(0.75)

            # Collect rewards if defeated
            if self.bossStatus == "defeated":
                self.keyboard.walk("d", 2.5)
                self.keyboard.walk("a", 5)
                sleep(1)
            if self.died or self.bossStatus is not None: break

        if self.died:
            self.logger.webhook("", "Died to Tunnel Bear", "dark brown", ping_category="ping_character_deaths")
            self.reset(convert=False)
            self.died = False
        elif self.bossStatus == "defeated":
            self.logger.webhook("", "Defeated: Tunnel Bear", "bright green", "screen", ping_category="ping_mob_events")
        self.hourlyReport.addHourlyStat("bug_run_time", time.time()-st)
        self.saveTiming("tunnel_bear")
        self.reset()
