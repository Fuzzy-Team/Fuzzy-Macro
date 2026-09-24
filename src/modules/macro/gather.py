import threading
import traceback
import modules.controls.mouse as mouse
import modules.misc.settingsManager as settingsManager
from modules.controls.sleep import InterruptRequested, pause_aware_time as time, sleep
from modules.gather_session import GatherPatternRunner, GatherSession
import modules.macro.pattern_environment as patternEnvironment
from modules.macro.game_data import (
    collectData,
    MAIN_GAME_PLACE_ID,
    regularMobTypesInFields,
    startLocationDimensions,
)


class GatherMixin:
    #place sprinklers by jumping up and down and placing them middair
    def placeSprinkler(self):
        sprinklerCount = {
            "basic":1,
            "silver":2,
            "golden":3,
            "diamond":4,
            "saturator":1
        }
        sprinklerSlot = str(self.setdat['sprinkler_slot'])
        times = sprinklerCount[self.setdat["sprinkler_type"]]
        #place one sprinkler and check if its in field
        self.keyboard.press(sprinklerSlot)
        time.sleep(1)
        if self.blueTextImageSearch("notinfield"):
            return False
        #place the remaining sprinklers
        #hold jump and spam place sprinklers
        if times > 2:
            self.keyboard.keyDown("space")
            st = time.time()
            while time.time() - st < times*2:
                self.keyboard.press(sprinklerSlot)
            self.keyboard.keyUp("space")
        return True

    def waitForBees(self):
        if self.alreadyConverted:
            return
        bees = self.setdat["bees"]
        if bees > 45:
            time.sleep(4)
        elif bees > 40:
            time.sleep(8)
        elif bees > 35:
            time.sleep(13)
        else:
            time.sleep(20)

    #background thread for gather
    #check if mobs have been killed and reset their timings
    #check if player died

    def convertSecsToMinsAndSecs(self, n):
        m = n // 60
        s = n % 60
        return f"{int(m)}m {int(s):02d}s"

    def gather(self, field, settingsOverride = {}, questGumdrops=False):
        # Normalize field name to handle both space and underscore formats
        # Convert underscores to spaces for fieldSettings lookup
        normalized_field = field.replace('_', ' ')
        altMode = self.setdat.get("macro_mode", "normal") == "alt"
        isHiveHubField = normalized_field == "hive hub"
        fieldSetting = {**self.fieldSettings[normalized_field], **settingsOverride}
        isSproutGather = not altMode and bool(fieldSetting.get("plant_sprout", False))
        skipTravel = bool(fieldSetting.get("skip_travel", False)) and self.location == normalized_field and not isHiveHubField
        pattern = fieldSetting['shape']
        patternRunner = GatherPatternRunner(
            settingsManager.getProjectRoot(),
            pattern,
            alert=lambda failed_pattern, error: self.logger.webhook(
                "Gather Pattern Failed",
                f"{failed_pattern}: {error}. Using e_lol for the rest of this gather.",
                "red",
                "screen",
                ping_category="ping_critical_errors",
                route_category="gathering",
            ),
            fatal_exceptions=(InterruptRequested,),
        )
        aiPatternLabels = {
            "fuzzy_ai_gather": "Fuzzy AI Gather",
            "blooms_ai": "BloomsAI",
        }
        def shouldUseHoneyWreathReturn():
            if altMode:
                return False
            if not self.setdat.get("wreath", False):
                return False

            fields_enabled = list(self.setdat.get("fields_enabled", []))
            configured_fields = list(self.setdat.get("fields", []))
            for index, enabled in enumerate(fields_enabled[:5]):
                if not enabled or index >= len(configured_fields):
                    continue
                configured_field = str(configured_fields[index]).replace("_", " ").strip().lower()
                if configured_field == normalized_field.lower():
                    return True
            return False

        def isHoneyWreathReady():
            cooldown = self.collectCooldowns.get("wreath", collectData["wreath"][2])
            return self.hasRespawned("wreath", cooldown)

        def isHoneyWreathBackpackReady(backpack=None):
            if backpack is None:
                backpack = self.getBackpack()
            return backpack >= fieldSetting["backpack"]

        preloadedAIGatherNameSpace = None
        if pattern == "fuzzy_ai_gather":
            try:
                fuzzyAIRuntimeDefaults = settingsManager.FUZZY_AI_RUNTIME_DEFAULTS
                pattern_ai_gather_model = str(fieldSetting.get("ai_gather_model", self.setdat.get("ai_gather_model", "Standard")))
                fuzzyAITokenRanking = settingsManager.loadFuzzyAITokenRanking(field, pattern_ai_gather_model)
                pattern_capture_backend = fuzzyAIRuntimeDefaults["fuzzy_ai_capture_backend"]
                pattern_confidence_threshold = fuzzyAIRuntimeDefaults["fuzzy_ai_confidence_threshold"]
                pattern_sprinkler_confidence_threshold = fuzzyAIRuntimeDefaults["fuzzy_ai_sprinkler_confidence_threshold"]
                pattern_min_token_distance = fuzzyAIRuntimeDefaults["fuzzy_ai_min_token_distance"]
                pattern_idle_return_interval = fuzzyAIRuntimeDefaults["fuzzy_ai_idle_return_interval"]
                pattern_no_token_recalibration_timeout = fuzzyAIRuntimeDefaults["fuzzy_ai_no_token_recalibration_timeout"]
                pattern_movements_before_recalibration = fuzzyAIRuntimeDefaults["fuzzy_ai_movements_before_recalibration"]
                pattern_sprinkler_arrival_threshold = fuzzyAIRuntimeDefaults["fuzzy_ai_sprinkler_arrival_threshold"]
                pattern_max_sprinkler_distance = fuzzyAIRuntimeDefaults["fuzzy_ai_max_sprinkler_distance"]
                pattern_sprinkler_rescan_attempts = fuzzyAIRuntimeDefaults["fuzzy_ai_sprinkler_rescan_attempts"]
                pattern_sprinkler_rescan_delay = fuzzyAIRuntimeDefaults["fuzzy_ai_sprinkler_rescan_delay"]
                pattern_debug_mode = fuzzyAIRuntimeDefaults["fuzzy_ai_debug_mode"]
                pattern_record_video = fuzzyAIRuntimeDefaults["fuzzy_ai_record_video"]
                pattern_record_video_fps = fuzzyAIRuntimeDefaults["fuzzy_ai_record_video_fps"]
                pattern_ai_gather_model_file = str(fieldSetting.get("ai_gather_model_file", ""))
                pattern_field_drift_compensation = bool(fieldSetting.get("field_drift_compensation", False))
                pattern_field_dimensions = startLocationDimensions.get(normalized_field)
                pattern_use_sprinkler_model_for_drift_compensation = bool(
                    self.setdat.get("use_sprinkler_model_for_drift_compensation", False)
                )
                sprinklerLabelMap = {
                    "basic": "Sprinkler",
                    "silver": "Sprinkler",
                    "golden": "Sprinkler",
                    "gold": "Sprinkler",
                    "diamond": "Sprinkler",
                    "saturator": "Supreme",
                    "supreme": "Supreme",
                }
                pattern_target_sprinkler_label = sprinklerLabelMap.get(
                    str(self.setdat.get("sprinkler_type", "")).strip().lower(),
                    "",
                )
                pattern_preferred_tokens = fieldSetting.get("fuzzy_ai_preferred_tokens", fuzzyAITokenRanking.get("preferred_tokens", ""))
                pattern_ignored_tokens = fieldSetting.get("fuzzy_ai_ignored_tokens", fuzzyAITokenRanking.get("ignored_tokens", ""))
                pattern_sprout_idle_square = isSproutGather
                sizeData = {
                    "xs": 0.25,
                    "s": 0.5,
                    "m": 1,
                    "l": 1.5,
                    "xl": 2
                }
                sizeword = fieldSetting["size"]
                size = sizeData[sizeword]
                width = fieldSetting["width"]
                pattern_ai_warmup_only = True
                if isSproutGather and pattern == "fuzzy_ai_gather":
                    self._fuzzy_ai_gather_state = {}
                preloadedAIGatherNameSpace = {**locals(), **vars(patternEnvironment)}
                warmupResult = patternRunner.warmup(preloadedAIGatherNameSpace)
                pattern = warmupResult.pattern
            except InterruptRequested:
                raise
            except Exception as error:
                print(traceback.format_exc())
                patternRunner.mark_failed(error)
                pattern = patternRunner.active_pattern

        landedInField = False
        if skipTravel:
            landedInField = True
            self.logger.webhook("Sprouts", f"Planting next sprout from current position in {field.title()}", "light blue", "screen", route_category="activities")
        else:
            for i in range(3):
                self.waitForBees()
                #go to field
                try:
                    self.set_task_status(f"travelling_{field}", activity="travelling", field=field)
                except Exception:
                    pass
                if not isHiveHubField:
                    if not self.travelViaCannon("Gathering", resetIfAway=False):
                        return
                self.logger.webhook("",f"Travelling: {field.title()}, Attempt {i+1}", "dark brown")
                self.goToField(
                    field,
                    startLocation=fieldSetting.get("start_location", "center"),
                )
                if isHiveHubField:
                    landedInField = True
                    break
                #go to start location (match natro's)
                startLocation = fieldSetting["start_location"]
                moveSpeedFactor = 18/self.setdat["movespeed"]
                flen, fwid = [x*fieldSetting["distance"]/10 for x in startLocationDimensions[normalized_field]]
                if "upper" in startLocation or "top" in startLocation:
                    self.sleepMSMove("w", flen*moveSpeedFactor)
                elif "lower" in startLocation or "bottom" in startLocation:
                     self.sleepMSMove("s", flen*moveSpeedFactor)

                if "left" in startLocation:
                     self.sleepMSMove("a", fwid*moveSpeedFactor)
                elif "right" in startLocation:
                     self.sleepMSMove("d", fwid*moveSpeedFactor)

                time.sleep(0.4)
                #place sprinkler + check if in field
                if self.placeSprinkler():
                    landedInField = True
                    break
                self.logger.webhook("", f"Failed to land in field", "red", "screen", ping_category="ping_critical_errors")
                self.reset()
        if not landedInField: #failed too many times
            return
        pattern = fieldSetting['shape']
        #rotate camera
        if fieldSetting["turn"] == "left":
            for _ in range(fieldSetting["turn_times"]):
                self.keyboard.press(",")
        elif fieldSetting["turn"] == "right":
            for _ in range(fieldSetting["turn_times"]):
                self.keyboard.press(".")
        try:
            startingPatternYaw = int(fieldSetting.get("turn_times", 0) or 0)
        except (TypeError, ValueError):
            startingPatternYaw = 0
        if fieldSetting.get("turn") == "left":
            startingPatternYaw *= -1
        elif fieldSetting.get("turn") != "right":
            startingPatternYaw = 0
        patternYawApplied = False

        def setPatternYaw(targetYaw):
            """Set a pattern's yaw once, relative to this gather's start."""
            nonlocal patternYawApplied
            if patternYawApplied:
                return
            try:
                targetYaw = int(targetYaw)
            except (TypeError, ValueError):
                return
            targetYaw = max(-8, min(8, targetYaw))
            delta = targetYaw - startingPatternYaw
            rotationKey = "." if delta > 0 else ","
            for _ in range(abs(delta)):
                self.keyboard.press(rotationKey)
            patternYawApplied = True
        def configureAIGatherCamera():
            for _ in range(11):
                self.keyboard.keyDown("pageup", False)
                sleep(0.01)
                self.keyboard.keyUp("pageup", False)
                sleep(0.01)
            for _ in range(3):
                self.keyboard.keyDown("pagedown", False)
                sleep(0.01)
                self.keyboard.keyUp("pagedown", False)
                sleep(0.01)

        aiCameraConfigured = False
        if pattern in aiPatternLabels:
            configureAIGatherCamera()
            aiCameraConfigured = True
        sproutFinalLootStart = None
        sproutFinalLootSeconds = self._sproutFinalLootSeconds()
        sproutLimitLogged = False
        lastSproutPlantAttempt = 0
        currentSproutRarity = None
        sproutCompletionMessageSeen = False
        sproutBeansUsedThisGather = 0
        try:
            sproutGatherBeanLimit = max(1, min(500, int(fieldSetting.get("sprout_max_beans_per_gather", self._sproutGatherBeanLimit()) or 500)))
        except Exception:
            sproutGatherBeanLimit = self._sproutGatherBeanLimit()
        def plantSproutBean():
            nonlocal lastSproutPlantAttempt, currentSproutRarity, sproutCompletionMessageSeen, sproutBeansUsedThisGather
            sproutSlot = str(fieldSetting.get("sprout_magic_bean_slot", self.setdat.get("sprouts_magic_bean_slot", 1)))
            if sproutBeansUsedThisGather >= sproutGatherBeanLimit:
                return "gather_limit"
            if not self.canUseSproutBeanSlot(sproutSlot):
                return "limit"
            lastSproutPlantAttempt = time.time()
            previousSproutRarity = currentSproutRarity
            currentSproutRarity = None
            sproutCompletionMessageSeen = False
            self.logger.webhook("Sprouts", f"Planting sprout in {field.title()} ({self.sproutBeansUsed + 1}/{self._sproutBeanLimit()})", "light blue", "screen", route_category="activities")
            self.keyboard.press(sproutSlot)
            self.markSproutBeanUsed()
            sproutBeansUsedThisGather += 1
            time.sleep(0.6)
            for _ in range(5):
                sproutInfo = self.blueSproutMessageInfo()
                if sproutInfo and sproutInfo.get("rarity"):
                    currentSproutRarity = sproutInfo["rarity"]
                if sproutInfo and "already" in sproutInfo.get("text", "") and "field" in sproutInfo.get("text", ""):
                    self.unmarkSproutBeanUsed()
                    sproutBeansUsedThisGather = max(0, sproutBeansUsedThisGather - 1)
                    currentSproutRarity = previousSproutRarity
                    self.logger.webhook("Sprouts", "A sprout is already in this field; Magic Bean use was not counted. Continuing to collect.", "orange", "screen", route_category="activities")
                    return "already"
                time.sleep(0.4)
            return "planted"

        if not altMode and fieldSetting.get("plant_sprout", False):
            self.ensure_shift_lock_off("sprouts")
            if pattern in aiPatternLabels and not aiCameraConfigured:
                configureAIGatherCamera()
            initialSproutPlantResult = plantSproutBean()
            if initialSproutPlantResult == "limit":
                self.logger.webhook("", "Sprout bean limit reached before planting", "orange", route_category="activities")
                return
            if initialSproutPlantResult == "gather_limit":
                self.logger.webhook("", "Sprout gather limit reached before planting", "orange", route_category="activities")
                return
        #key variables
        #check invert L/R and invert B/R
        fwdkey = "w"
        leftkey = "a" 
        backkey = "s" 
        rightkey = "d"
        rotleft = ","
        rotright = "."
        rotup = "pageup"
        rotdown = "pagedown"
        zoomin = "i"
        zoomout = "o"
        sc_space = "space"
        tcfbkey = fwdkey
        afcfbkey = backkey
        tclrkey = leftkey
        afclrkey = rightkey
        if fieldSetting["invert_lr"]:
            tclrkey = rightkey
            afclrkey = leftkey
        if fieldSetting["invert_fb"]:
            tcfbkey = backkey
            afcfbkey = fwdkey
        facingcorner = 0
        sizeData = {
            "xs": 0.25,
            "s": 0.5,
            "m": 1,
            "l": 1.5,
            "xl": 2
        }
        sizeword = fieldSetting["size"]
        size = sizeData[sizeword]
        width = fieldSetting["width"]
        infiniteGather = altMode or bool(fieldSetting.get("infinite_gather", False))
        maxGatherTime = fieldSetting["mins"]*60
        gatherTimeLimit = "Infinite" if infiniteGather else self.convertSecsToMinsAndSecs(maxGatherTime)
        returnType = "rejoin" if isHiveHubField else fieldSetting["return"]
        fuzzyAIRuntimeDefaults = settingsManager.FUZZY_AI_RUNTIME_DEFAULTS
        pattern_blooms_ai_model = str(fieldSetting.get("blooms_ai_model", "Standard"))
        pattern_ai_gather_model = str(fieldSetting.get("ai_gather_model", self.setdat.get("ai_gather_model", "Standard")))
        fuzzyAITokenRanking = settingsManager.loadFuzzyAITokenRanking(field, pattern_ai_gather_model)
        pattern_capture_backend = fuzzyAIRuntimeDefaults["fuzzy_ai_capture_backend"]
        pattern_confidence_threshold = fuzzyAIRuntimeDefaults["fuzzy_ai_confidence_threshold"]
        pattern_sprinkler_confidence_threshold = fuzzyAIRuntimeDefaults["fuzzy_ai_sprinkler_confidence_threshold"]
        pattern_min_token_distance = fuzzyAIRuntimeDefaults["fuzzy_ai_min_token_distance"]
        pattern_idle_return_interval = fuzzyAIRuntimeDefaults["fuzzy_ai_idle_return_interval"]
        pattern_no_token_recalibration_timeout = fuzzyAIRuntimeDefaults["fuzzy_ai_no_token_recalibration_timeout"]
        pattern_movements_before_recalibration = fuzzyAIRuntimeDefaults["fuzzy_ai_movements_before_recalibration"]
        pattern_sprinkler_arrival_threshold = fuzzyAIRuntimeDefaults["fuzzy_ai_sprinkler_arrival_threshold"]
        pattern_max_sprinkler_distance = fuzzyAIRuntimeDefaults["fuzzy_ai_max_sprinkler_distance"]
        pattern_sprinkler_rescan_attempts = fuzzyAIRuntimeDefaults["fuzzy_ai_sprinkler_rescan_attempts"]
        pattern_sprinkler_rescan_delay = fuzzyAIRuntimeDefaults["fuzzy_ai_sprinkler_rescan_delay"]
        pattern_debug_mode = fuzzyAIRuntimeDefaults["fuzzy_ai_debug_mode"]
        pattern_record_video = fuzzyAIRuntimeDefaults["fuzzy_ai_record_video"]
        pattern_record_video_fps = fuzzyAIRuntimeDefaults["fuzzy_ai_record_video_fps"]
        pattern_ai_gather_model_file = str(fieldSetting.get("ai_gather_model_file", ""))
        pattern_field_drift_compensation = bool(fieldSetting.get("field_drift_compensation", False))
        pattern_field_dimensions = startLocationDimensions.get(normalized_field)
        pattern_use_sprinkler_model_for_drift_compensation = bool(
            self.setdat.get("use_sprinkler_model_for_drift_compensation", False)
        )
        pattern_ai_gather_model = str(fieldSetting.get("ai_gather_model", self.setdat.get("ai_gather_model", "Standard")))
        pattern_ai_gather_model_file = str(fieldSetting.get("ai_gather_model_file", ""))
        sprinklerLabelMap = {
            "basic": "Sprinkler",
            "silver": "Sprinkler",
            "golden": "Sprinkler",
            "gold": "Sprinkler",
            "diamond": "Sprinkler",
            "saturator": "Supreme",
            "supreme": "Supreme",
        }
        pattern_target_sprinkler_label = sprinklerLabelMap.get(
            str(self.setdat.get("sprinkler_type", "")).strip().lower(),
            "",
        )
        pattern_preferred_tokens = fieldSetting.get("fuzzy_ai_preferred_tokens", fuzzyAITokenRanking.get("preferred_tokens", ""))
        pattern_ignored_tokens = fieldSetting.get("fuzzy_ai_ignored_tokens", fuzzyAITokenRanking.get("ignored_tokens", ""))
        pattern_sprout_idle_square = isSproutGather
        st = time.time()
        gatherSession = GatherSession(patternRunner, time.time)
        gatherSession.start(st)
        keepGathering = True
        self.died = False
        #time to gather
        if preloadedAIGatherNameSpace is not None:
            preloadedAIGatherNameSpace.update({**locals(), **vars(patternEnvironment), "pattern_ai_warmup_only": False})
            preloadedAIGatherNameSpace["setPatternYaw"] = setPatternYaw
            gatherNameSpace = preloadedAIGatherNameSpace
        else:
            gatherNameSpace = {**locals(), **vars(patternEnvironment)}
            gatherNameSpace["setPatternYaw"] = setPatternYaw
        if isSproutGather:
            self.set_task_status("collect_sprouts", task="collect", field=field, activity="sprouts")
        else:
            self.set_task_status(f"gather_{field}", task="gather", field=field)

        questMenuKeptOpen = False
        questWatchGiver = None
        questWatchObjective = None
        lastQuestProgressCheck = 0
        if self.setdat.get("quest_progress_watch", False) and not isSproutGather:
            questWatchers = getattr(self, "questGatherWatchers", {}) or {}
            watcherCandidates = list(questWatchers.get(normalized_field.lower(), []))
            if normalized_field.lower() in {"blue flower", "bamboo", "pine tree", "stump"}:
                watcherCandidates.extend(questWatchers.get("__blue__", []))
            if normalized_field.lower() in {"mushroom", "strawberry", "rose", "pepper"}:
                watcherCandidates.extend(questWatchers.get("__red__", []))
            watcherCandidates.extend(questWatchers.get("__any__", []))

            if watcherCandidates:
                questWatchGiver, questWatchObjective = watcherCandidates[0]
                try:
                    # findQuest opens the menu before scanning. Mark it here so
                    # an OCR exception still closes the overlay safely.
                    questMenuKeptOpen = True
                    visibleObjectives = self.findQuest(
                        questWatchGiver,
                        keepQuestMenuOpen=True,
                        logDetection=False,
                    )
                    if visibleObjectives is not None and questWatchObjective in visibleObjectives:
                        lastQuestProgressCheck = time.time()
                        self.moveMouseToDefault()
                        self.logger.webhook(
                            "Live Quest Progress",
                            f"Watching {questWatchGiver.title()}: {questWatchObjective.replace('_', ' ').title()}",
                            "light blue",
                        )
                    elif visibleObjectives is not None:
                        # The menu was deliberately left open by findQuest, but the
                        # objective is no longer incomplete, so do not watch it.
                        self.toggleQuest()
                        self.moveMouseToDefault()
                        questMenuKeptOpen = False
                    else:
                        # findQuest closes the menu itself when it cannot locate
                        # the requested quest giver.
                        questMenuKeptOpen = False
                except Exception:
                    print(traceback.format_exc())
                    if questMenuKeptOpen:
                        self.toggleQuest()
                        self.moveMouseToDefault()
                    questMenuKeptOpen = False

        self.isGathering = True
        lastGooTime = 0  # Track when goo was last used
        gooTimerActive = True  # Flag to control goo timer thread
        honeyWreathReturnEnabled = shouldUseHoneyWreathReturn()
        honeyWreathPending = False
        honeyWreathWaitLogged = False
        inactiveHoneyResetEnabled = bool(self.setdat.get("inactive_honey_reset", False)) and not isHiveHubField
        inactiveHoneyTimerActive = True
        inactiveHoneyEvent = threading.Event()

        # Add goo status to webhook message
        gooStatus = " - Goo Enabled" if fieldSetting.get("goo", False) else ""
        backpackLimitLabel = "Ignored" if infiniteGather else f"{fieldSetting['backpack']}%"
        if isSproutGather:
            self.logger.webhook("Sprouts", f"Collecting drops in {field.title()} with AI Gathering", "light green", route_category="activities")
        else:
            self.logger.webhook(f"Gathering: {field.title()}", f"Limit: {gatherTimeLimit} - {fieldSetting['shape']} - Backpack: {backpackLimitLabel}{gooStatus}", "light green", route_category="gathering")

        # Goo timer thread: use gumdrops (which make goo) every 3s for goo quests,
        # otherwise at the field's goo interval when the field has goo enabled
        def gooTimerThread():
            nonlocal lastGooTime
            useGoo = questGumdrops or fieldSetting.get("goo", False)
            gooInterval = 3 if questGumdrops else int(fieldSetting.get("goo_interval", 3))
            while gooTimerActive:
                currentTime = time.time()
                if useGoo and (currentTime - lastGooTime) >= gooInterval:
                    self.keyboard.press(str(self.setdat["goo_slot"]))
                    time.sleep(0.05)
                    lastGooTime = currentTime
                time.sleep(0.5)

        def inactiveHoneyTimerThread():
            inactiveChecks = 0
            while inactiveHoneyTimerActive:
                try:
                    if self.isInactiveHoneyResetPaused():
                        inactiveChecks = 0
                        time.sleep(1)
                        continue
                    if self.getBackpack() < fieldSetting["backpack"]:
                        inactiveChecks = 0 if self.isActiveHoney() else inactiveChecks + 1
                        if inactiveChecks > 30:
                            inactiveHoneyEvent.set()
                            return
                    else:
                        inactiveChecks = 0
                except Exception:
                    inactiveChecks = 0
                time.sleep(1)

        gooThread = threading.Thread(target=gooTimerThread, daemon=True)
        gooThread.start()
        if inactiveHoneyResetEnabled:
            inactiveHoneyThread = threading.Thread(target=inactiveHoneyTimerThread, daemon=True)
            inactiveHoneyThread.start()
        mouse.moveBy(10,5)
        self.keyboard.releaseMovement()

        def isGatherPaused():
            return self.run is not None and self.run.value == 6

        def getGatherTime():
            return gatherSession.elapsed(isGatherPaused())

        liveGatherReport = None
        if self.liveGatherReportEnabled() and not isSproutGather:
            liveGatherReport = self.createLiveGatherReport()
            liveGatherReport.start(field, gatherTimeLimit, getGatherTime, isGatherPaused)
            gatherSession.add_cleanup(liveGatherReport.stop)

        liveQuestProgressReport = None
        if questMenuKeptOpen:
            liveQuestProgressReport = self.createLiveQuestProgressReport()
            liveQuestProgressReport.start(
                questWatchGiver,
                questWatchObjective,
                getGatherTime,
                isGatherPaused,
                activity="Quest Progress",
            )
            gatherSession.add_cleanup(liveQuestProgressReport.stop)
        
        def stopGather(reason="completed"):
            nonlocal gooTimerActive, inactiveHoneyTimerActive, questMenuKeptOpen
            gooTimerActive = False  # Stop the goo timer thread
            inactiveHoneyTimerActive = False
            # toggleQuest sleeps, which raises again while an interrupt is pending,
            # so the session cleanup must not depend on it finishing
            try:
                if fieldSetting["shift_lock"]:
                    self.keyboard.press('shift')
                if questMenuKeptOpen:
                    self.toggleQuest()
                    questMenuKeptOpen = False
                self.moveMouseToDefault()
                self.clear_task_status()
            finally:
                self.isGathering = False
                gatherSession.finish(gatherNameSpace, reason)

        if fieldSetting["shift_lock"]: 
            self.keyboard.press('shift')
        
        while keepGathering:
            # Check if paused and wait
            if self.checkPauseAndWait():
                # Stop was requested while paused
                stopGather("stopped")
                return
            
            try:
                self.raiseIfInterrupted()
            except InterruptRequested:
                stopGather("interrupted")
                raise

            patternStartTime = time.time()
            mouse.mouseDown()

            try:
                cycleResult = gatherSession.run_cycle(gatherNameSpace, owner=self)
            except Exception as error:
                # interrupts usually land inside a pattern's sleep, and e_lol failing ends the
                # gather too; either way stop the gather's threads and reports before leaving
                mouse.mouseUp()
                stopGather("interrupted" if isinstance(error, InterruptRequested) else "pattern_error")
                raise
            pattern = cycleResult.pattern

            #field drift compensation — AI patterns already manage sprinkler
            # anchoring / idle patrol themselves, so skip the post-cycle nudge
            # that would fight a continuous square walk around the sprinkler.
            if fieldSetting["field_drift_compensation"] and pattern not in aiPatternLabels:
                self.fieldDriftCompensation.run(startLocationDimensions.get(normalized_field))

            #cycle ends
            mouse.mouseUp()
            #add gather time stat
            if not isSproutGather:
                self.hourlyReport.addHourlyStat("gathering_time", time.time()-patternStartTime)
            gatherTime = self.convertSecsToMinsAndSecs(getGatherTime())

            if questMenuKeptOpen and time.time() - lastQuestProgressCheck >= 2:
                lastQuestProgressCheck = time.time()
                try:
                    visibleObjectives = self.findQuest(
                        questWatchGiver,
                        questScreens=[self.captureQuestWatchScreen()],
                        logDetection=False,
                    )
                    if visibleObjectives is not None and questWatchObjective not in visibleObjectives:
                        self.logger.webhook(
                            "Gathering: Ended",
                            f"{questWatchGiver.title()} objective completed: {questWatchObjective.replace('_', ' ').title()}",
                            "light green",
                            "screen",
                            route_category="gathering",
                        )
                        keepGathering = False
                        continue
                except Exception:
                    # A single bad OCR frame should never end a gather. The next
                    # pattern cycle will try the visible objective again.
                    print(traceback.format_exc())

            #check for AFB
            if inactiveHoneyEvent.is_set():
                stopGather()
                self.logger.webhook("Gathering: interrupted", "Inactive Honey Reset (Beta)", "orange", "screen")
                self.reset()
                return
            elif not altMode and fieldSetting.get("plant_sprout", False):
                sproutGatherLimitReached = sproutBeansUsedThisGather >= sproutGatherBeanLimit
                sproutSessionLimitReached = self.sproutBeansUsed >= self._sproutBeanLimit()
                if sproutFinalLootStart is None and not sproutGatherLimitReached and not sproutSessionLimitReached:
                    sproutInfo = self.blueSproutMessageInfo()
                    if sproutInfo:
                        if sproutInfo.get("rarity"):
                            currentSproutRarity = sproutInfo["rarity"]
                        if self.isSproutCompletionMessage(sproutInfo.get("text", "")):
                            sproutCompletionMessageSeen = True
                    if sproutCompletionMessageSeen and not self.blueSproutMessageVisible():
                        self.logger.webhook("Sprouts", f"Detected sprout pop message; planting next sprout ({self.sproutBeansUsed + 1}/{self._sproutBeanLimit()}).", "light blue", "screen", route_category="activities")
                        plantSproutBean()
                    else:
                        fallbackSeconds = self.sproutReplantFallbackSeconds(currentSproutRarity)
                        if time.time() - lastSproutPlantAttempt >= fallbackSeconds:
                            rarityLabel = currentSproutRarity.title() if currentSproutRarity else "unknown"
                            self.logger.webhook("Sprouts", f"No sprout pop message detected for {fallbackSeconds} seconds ({rarityLabel}); trying next sprout ({self.sproutBeansUsed + 1}/{self._sproutBeanLimit()}).", "light blue", "screen", route_category="activities")
                            plantSproutBean()
                sproutGatherLimitReached = sproutBeansUsedThisGather >= sproutGatherBeanLimit
                sproutSessionLimitReached = self.sproutBeansUsed >= self._sproutBeanLimit()
                if sproutFinalLootStart is None and (sproutSessionLimitReached or sproutGatherLimitReached):
                    sproutFinalLootStart = time.time()
                    if not sproutLimitLogged:
                        if sproutSessionLimitReached:
                            self.logSproutBeanLimitReached(f"Sprout session limit reached. Collecting remaining drops for {sproutFinalLootSeconds} seconds before resetting.")
                        else:
                            self.logger.webhook("Sprouts", f"Sprout gather limit reached ({sproutBeansUsedThisGather}/{sproutGatherBeanLimit}). Collecting remaining drops for {sproutFinalLootSeconds} seconds before moving on.", "light blue", "screen", route_category="activities")
                        sproutLimitLogged = True
                if sproutFinalLootStart is not None and time.time() - sproutFinalLootStart >= sproutFinalLootSeconds:
                    stopGather()
                    self.logger.webhook("Sprouts", "Final sprout loot collection finished. Resetting to hive.", "light green", route_category="activities")
                    self.reset()
                    return
            elif not altMode and self.setdat["Auto_Field_Boost"] and not self.AFBLIMIT and self.AFB(gatherInterrupt=True, turnOffShiftLock = fieldSetting["shift_lock"]):
                stopGather()
                return
            #check for gather interrupts
            elif (
                self.setdat.get("macro_mode", "normal") not in ("quest", "alt")
                and self.night
                and self.setdat["stinger_hunt"]
            ):
                #rely on task function in main to execute the stinger hunt
                stopGather()
                self.logger.webhook("Gathering: interrupted","Stinger Hunt","dark brown")
                self.reset(convert=False)
                break
            elif (
                self.setdat.get("macro_mode", "normal") not in ("quest", "alt")
                and self.setdat["mondo_buff"]
                and self.hasMondoRespawned()
                and self.setdat["mondo_buff_interrupt_gathering"]
            ):
                stopGather()
                self.logger.webhook("Gathering: interrupted","Mondo Buff","dark brown")
                self.reset(convert=False)
                self.collectMondoBuff()
                break
            elif (
                self.setdat.get("macro_mode", "normal") not in ("quest", "alt")
                and self.setdat["sticker_stack"]
                and self.setdat.get("sticker_stack_interrupt_gathering", False)
                and self.hasStickerStackRespawned()
            ):
                stopGather()
                self.logger.webhook("Gathering: interrupted", "Sticker Stack", "dark brown")
                self.reset(convert=False)
                self.collect("sticker_stack")
                break
            elif not altMode:
                questMobsByGiver = getattr(self, "questGatherInterruptMobs", {})
                questMobs = {
                    mob
                    for questGiver, mobs in questMobsByGiver.items()
                    if self.setdat.get(f"{questGiver.replace(' ', '_')}_quest_gather_interrupt", False)
                    for mob in mobs
                }
                respawnedQuestMobs = [
                    (mob, mobField)
                    for mob in questMobs
                    for mobField in regularMobTypesInFields
                    if mob in regularMobTypesInFields[mobField] and self.hasMobRespawned(mob, mobField)
                ]
                if respawnedQuestMobs:
                    stopGather()
                    mobNames = ", ".join(sorted({mob.replace("_", " ").title() for mob, _ in respawnedQuestMobs}))
                    self.logger.webhook("Gathering: interrupted", f"Quest mobs ready: {mobNames}", "dark brown")
                    self.reset(convert=False)
                    for mob, mobField in respawnedQuestMobs:
                        # Recheck because another field run can update shared mob timings.
                        if self.hasMobRespawned(mob, mobField):
                            self.killMob(mob, mobField)
                    break
            if self.died:
                self.clear_task_status()
                stopGather()
                self.logger.webhook("","Player died", "dark brown","screen", ping_category="ping_character_deaths")
                time.sleep(0.4)
                self.reset()
                break
            elif not infiniteGather and getGatherTime() > maxGatherTime:
                if honeyWreathReturnEnabled and isHoneyWreathReady():
                    backpack = self.getBackpack()
                    if isHoneyWreathBackpackReady(backpack):
                        self.logger.webhook(
                            "Gathering: Ended",
                            f"Time: {gatherTime} - Time Limit - Backpack Full - Return: Honey Wreath",
                            "light green",
                            "screen"
                        )
                        honeyWreathPending = True
                        keepGathering = False
                    elif not honeyWreathWaitLogged:
                        self.logger.webhook(
                            "Gathering: Extended",
                            "Time limit reached. Waiting for backpack to fill before claiming Honey Wreath",
                            "light green",
                            "screen"
                        )
                        honeyWreathWaitLogged = True
                else:
                    self.logger.webhook(f"Gathering: Ended", f"Time: {gatherTime} - Time Limit - Return: {returnType.title()}", "light green", "screen", route_category="gathering")
                    keepGathering = False
            #check backpack
            elif isHiveHubField or infiniteGather:
                continue
            else:
                backpack = self.getBackpack()
                if backpack >= fieldSetting["backpack"]:
                    if honeyWreathReturnEnabled and isHoneyWreathReady():
                        if isHoneyWreathBackpackReady(backpack):
                            self.logger.webhook(
                                "Gathering: Ended",
                                f"Time: {gatherTime} - Backpack Full - Return: Honey Wreath",
                                "light green",
                                "screen"
                            )
                            honeyWreathPending = True
                            keepGathering = False
                        elif not honeyWreathWaitLogged:
                            self.logger.webhook(
                                "Gathering: Extended",
                                f"Honey Wreath is ready. Waiting for the configured backpack limit ({fieldSetting['backpack']}%) before claiming",
                                "light green",
                                "screen"
                            )
                            honeyWreathWaitLogged = True
                    else:
                        self.logger.webhook(f"Gathering: Ended", f"Time: {gatherTime} - Backpack - Return: {returnType.title()}", "light green", "screen", route_category="gathering")
                        keepGathering = False

        #gathering was interrupted
        if keepGathering:
            return
        else:
            stopGather()

        #goo timer continues via background thread during return process

        #go back to hive
        def walkToHive(convertAtHive=True):
            #walk to hive
            #face correct direction (towards hive)
            if fieldSetting["turn"] == "left":
                for _ in range(fieldSetting["turn_times"]):
                    self.keyboard.press(".")
            elif fieldSetting["turn"] == "right":
                for _ in range(fieldSetting["turn_times"]):
                    self.keyboard.press(",")
            self.faceDirection(field, "south")
            #start walk
            self.canDetectNight = False
            try:
                self.set_task_status("travelling_hive", activity="travelling", field="hive")
            except Exception:
                pass
            self.logger.webhook("",f"Walking back to hive: {field.title()}", "dark brown")
            if field == "pine tree" and self.setdat.get("pine_tree_fast_return", False):
                self.runPath("field_to_hive/pine tree fast")
            else:
                self.runPath(f"field_to_hive/{field}")
            #find hive and convert
            #self.keyboard.walk("a", (self.setdat["hive_number"]-1)*0.8)
            self.keyboard.keyDown("a")
            st = time.time()
            self.canDetectNight = True
            while time.time()-st < 10:
                #goo timer continues via background thread during hive search
                if self.isBesideEImage("makehoney"):
                    break
            self.keyboard.keyUp("a")
            #in case we overrun
            time.sleep(0.4)
            if self.isBesideEImage("makehoney"):
                if not convertAtHive:
                    return True
            elif not convertAtHive:
                self.logger.webhook("","Can't find hive, resetting", "dark brown", "screen")
                self.reset()
                return False

            for _ in range(7):
                #goo timer continues via background thread during conversion attempts
                if self.convert(forced_convert_balloon=(str(self.setdat.get("convert_balloon","")).lower().replace(" ","_")=="every_gather")):
                    return True
                self.keyboard.walk("d",0.1)
                time.sleep(0.2) #add a delay so that the E can popup
            else:
                # If configured, attempt to use a whirligig before resetting
                if fieldSetting.get("use_whirlwig_fallback", False):
                    self.logger.webhook("","Can't find hive, attempting whirligig fallback", "dark brown", "screen")
                    self.useItemInInventory("whirligig")
                    time.sleep(1)
                    if not self.convert(forced_convert_balloon=(str(self.setdat.get("convert_balloon","")).lower().replace(" ","_")=="every_gather")):
                        self.logger.webhook("","Whirligig fallback failed, resetting", "dark brown", "screen")
                        self.reset()
                    else:
                        # whirligig succeeded — perform non-converting reset behavior
                        self.reset(convert=False)
                else:
                    self.logger.webhook("","Can't find hive, resetting", "dark brown", "screen")
                    self.reset()
                return False
            return True

        if honeyWreathPending:
            if walkToHive(convertAtHive=False):
                self.logger.webhook("", "Claiming Honey Wreath before converting", "dark brown", "screen")
                self.collect("wreath")
                self.reset(convert=True)
            gooTimerActive = False
            return

        if returnType == "reset":
            #goo timer continues via background thread during reset
            self.reset()
        elif returnType == "rejoin":
            #goo timer continues via background thread during rejoin
            self.rejoin(placeId=MAIN_GAME_PLACE_ID, claimHive=True)
        elif returnType == "whirligig":
            #goo timer continues via background thread during whirligig usage
            self.useItemInInventory("whirligig")
            time.sleep(1)
            if not self.convert(forced_convert_balloon=(str(self.setdat.get("convert_balloon","")).lower().replace(" ","_")=="every_gather")):
                self.logger.webhook("","Whirligigs failed, walking to hive", "dark brown", "screen")
                walkToHive()
                gooTimerActive = False
                return
            #whirligig sucessful
            #goo timer continues via background thread after whirligig success
            self.reset(convert=False)
        elif returnType == "walk":
            #goo timer continues via background thread during walk to hive
            walkToHive()
        
        # Stop the goo timer thread when gathering is completely finished
        gooTimerActive = False
