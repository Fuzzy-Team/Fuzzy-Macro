import ast
import json
import time
import modules.controls.mouse as mouse
import modules.misc.settingsManager as settingsManager
from modules.quest_planning import quest_giver_order, choose_quest_gather, is_gather_objective, allowed_fields, quest_uses_ant_challenge
from modules.controls.sleep import (
    InterruptRequested,
    INTERRUPT_NONE,
    INTERRUPT_SKIP,
    INTERRUPT_RESET,
    INTERRUPT_AFB_REROLL,
    INTERRUPT_COLLECT_PLANTER,
    INTERRUPT_STICKER_SPROUT,
)


# Quest titles that are primarily bloom-petal objectives and can be skipped by setting.
HARDCODED_PETAL_IGNORE_TITLES = {"petal tabbouleh", "petals", "mashed blooms"}


def canClaimTimedBearQuest(name):
    """Return True if the given quest giver can be claimed for timed bear quests.

    Brown and black bear quests are limited to one claim per hour. This checks
    the timestamp stored in `src/data/user/timings.txt` under the key
    `<bear>_quest_cd`. If no valid timestamp exists, allow claiming.
    """
    if name not in ["brown bear", "black bear"]:
        return True
    timing_key = f"{name.replace(' ', '_')}_quest_cd"
    state_key = f"{name.replace(' ', '_')}_quest_state"
    try:
        timings = settingsManager.readSettingsFile(settingsManager.getUserDataPath("timings.txt")) or {}
    except Exception:
        timings = {}
    # Ensure both bear quest state keys exist in the timings file with a default of 0
    try:
        for required_state in ("brown_bear_quest_state", "black_bear_quest_state"):
            if required_state not in timings:
                try:
                    settingsManager.saveSettingFile(required_state, 0, settingsManager.getUserDataPath("timings.txt"))
                except Exception:
                    pass
                timings[required_state] = 0
    except Exception:
        pass
    state = timings.get(state_key, 0)
    timing = timings.get(timing_key)
    # Debug info to help diagnose state issues
    try:
        print(f"canClaimTimedBearQuest: name={name}, state={state}, timing={timing}")
    except Exception:
        pass
    # If state is 1, we should not check until timer expires
    if state == 1:
        if not isinstance(timing, (float, int)):
            # Missing timestamp -> reset state to 0 to recover
            settingsManager.saveSettingFile(state_key, 0, settingsManager.getUserDataPath("timings.txt"))
            return True
        # If timer expired, reset state and allow claiming
        if time.time() - timing >= 60 * 60:
            settingsManager.saveSettingFile(state_key, 0, settingsManager.getUserDataPath("timings.txt"))
            return True
        return False
    # state == 0 -> allow claiming
    return True
    
# (set_enabled moved into RichPresenceManager class)
#controller for the macro
def macro(status, logQueue, updateGUI, run, skipTask, presence=None, discordMessageQueue=None, planterCommandQueue=None, skipServer=None):
    # imported here so the GUI process, which only passes this function to the macro
    # process, doesn't load the macro package (OCR, cv2, Vision, pyautogui)
    import modules.macro as macroModule
    macro = macroModule.macro(status, logQueue, updateGUI, run, skipTask, presence, discordMessageQueue, skipServer)
    altHostAuthorized = (
        macro.setdat.get("macro_mode", "normal") != "alt"
        or bool(macro.setdat.get("alt_mode_field_pending", False))
    )
    if macro.setdat.get("macro_mode", "normal") == "alt" and altHostAuthorized:
        settingsManager.saveProfileSetting("alt_mode_field_pending", False)
        macro.setdat["alt_mode_field_pending"] = False
    #invert the regularMobsInFields dict
    #instead of storing mobs in field, store the fields associated with each mob
    regularMobData = {}
    for k,v in macroModule.regularMobTypesInFields.items():
        for x in v:
            if x in regularMobData:
                regularMobData[x].append(k)
            else:
                regularMobData[x] = [k]
    #Limit werewolf to just pumpkin 
    regularMobData["werewolf"] = ["pumpkin"]
    bossCooldowns = {"coconut_crab": 36*60*60, "king_beetle": 24*60*60,
                     "tunnel_bear": 48*60*60, "stump_snail": 96*60*60}
    
    private_server_link = macro.setdat.get("private_server_link", "")
    # Accept share links — the rejoin deeplink handler now supports the newer share link format.

    taskCompleted = True
    questCache = {}
    questScanScreens = None
    macro.questGatherInterruptMobs = {}
    macro.questTaskWatchers = {}
    macro.deferredQuestObjectives = set()
    macro.completedQuestWatchTasks = set()
    macro.completedQuestWatchObjectives = set()
    
    macro.start()
    lastIdleClick = time.time()
    #macro.useItemInInventory("blueclayplanter")

    def emptyAutoPlanterSlot():
        return {
            "planter": "",
            "nectar": "",
            "field": "",
            "harvest_time": 0,
            "nectar_est_percent": 0,
            "placed_time": 0,
            "grow_duration": 0,
            "natural_grow_duration": 0,
        }

    def clearCollectedPlanterState(command):
        mode = int(command.get("mode", 0) or 0)
        index = command.get("index")
        index = -1 if index is None or index == "" else int(index)
        if index < 0:
            return

        if mode == 1:
            with open(settingsManager.ensureUserFile("manualplanters.txt"), "r") as f:
                raw = f.read().strip()
            planterData = ast.literal_eval(raw) if raw else {"planters": ["", "", ""], "fields": ["", "", ""], "gatherFields": ["", "", ""], "harvestTimes": [0, 0, 0], "cycles": [1, 1, 1]}
            for key, emptyValue in (("planters", ""), ("fields", ""), ("gatherFields", "")):
                if key in planterData and index < len(planterData[key]):
                    planterData[key][index] = emptyValue
            if "harvestTimes" in planterData and index < len(planterData["harvestTimes"]):
                planterData["harvestTimes"][index] = 0
            with open(settingsManager.ensureUserFile("manualplanters.txt"), "w") as f:
                f.write(str(planterData))
        elif mode == 2:
            with open(settingsManager.ensureUserFile("auto_planters.json"), "r") as f:
                autoData = json.load(f)
            planters = autoData.get("planters", [])
            if index < len(planters):
                planters[index] = emptyAutoPlanterSlot()
            autoData["planters"] = planters
            with open(settingsManager.ensureUserFile("auto_planters.json"), "w") as f:
                json.dump(autoData, f, indent=3)

    def processPlanterCommandQueue():
        if planterCommandQueue is None:
            return False
        handled = False
        while not planterCommandQueue.empty():
            command = planterCommandQueue.get()
            if command.get("action") != "collect":
                continue
            planter = command.get("planter", "")
            field = command.get("field", "")
            if not planter or not field:
                continue
            macro.logger.webhook("", f"Collect planter command received: {planter.title()} in {field.title()}", "orange")
            if runTask(macro.collectPlanter, args=(planter, field), resetAfter=True, allowAFB=False):
                clearCollectedPlanterState(command)
                macro.logger.webhook("", f"Collected {planter.title()} planter from {field.title()} and cleared its timer.", "bright green")
            handled = True
        return handled

    #function to run a task
    #makes it easy to do any checks after a task is complete (like stinger hunt, rejoin every, etc)
    def runTask(func = None, args = (), resetAfter = True, convertAfter = True, allowAFB = True):
        nonlocal taskCompleted

        def watchedTaskKey():
            if func is None:
                return None
            functionName = getattr(func, "__name__", "")
            if functionName == "killMob" and args:
                return f"kill_{str(args[0]).replace(' ', '_')}"
            if functionName == "collect" and args:
                return f"collect_{str(args[0]).replace('-', '_').replace(' ', '_')}"
            if functionName == "feedBee" and args:
                return f"feed_{str(args[0]).replace(' ', '_')}"
            taskKeys = {
                "antChallenge": "ant_challenge",
                "coconutCrab": "kill_coconut_crab",
                "kingBeetle": "kill_king_beetle",
                "tunnelBear": "kill_tunnel_bear",
                "stumpSnail": "kill_stump_snail",
                "stingerHunt": "stinger_hunt",
            }
            return taskKeys.get(functionName)

        def handle_interrupt(action):
            nonlocal taskCompleted
            skipTask.value = INTERRUPT_NONE
            macro.stickerSproutInterruptRequested = False
            macro.keyboard.releaseMovement()
            mouse.mouseUp()
            interrupted_status = status.value.replace('_', ' ').title() if status.value else "Current Task"
            macro.clear_task_status()
            taskCompleted = True
            if action == INTERRUPT_SKIP:
                if func == macro.gather and len(args) > 2 and args[2]:
                    macro.questGatherOutcome = "skipped"
                    macro.deferredQuestObjectives.add(args[2]["id"])
                else:
                    for giver, watchedAction in macro.questTaskWatchers.get(watchedTaskKey(), []):
                        objective = next((row for row in (macro.questObservations.get(giver) or [])
                                          if row["action"] == watchedAction and row["status"] != "complete"
                                          and row["id"] not in macro.deferredQuestObjectives), None)
                        if objective:
                            macro.deferredQuestObjectives.add(objective["id"])
                            break
                macro.logger.webhook("Task Skipped", f"Skipped: {interrupted_status}", "orange")
            elif action == INTERRUPT_RESET:
                macro.logger.webhook("Task Reset", f"Resetting and retrying: {interrupted_status}", "orange")
            elif action == INTERRUPT_AFB_REROLL:
                macro.logger.webhook("AFB Reroll", f"Reroll requested during: {interrupted_status}", "orange")
            elif action == INTERRUPT_COLLECT_PLANTER:
                macro.logger.webhook("Collect Planter", f"Collect planter requested during: {interrupted_status}", "orange")
            elif action == INTERRUPT_STICKER_SPROUT:
                macro.logger.webhook("Sticker Sprout", f"Interrupting {interrupted_status} to collect in Hive Hub", "orange")
            macro.reset(convert=True)
            if action == INTERRUPT_COLLECT_PLANTER:
                processPlanterCommandQueue()
                return None
            if action == INTERRUPT_STICKER_SPROUT:
                return runTask(macro.collectStickerSprout, resetAfter=False)
            if action == INTERRUPT_AFB_REROLL:
                macro.AFBLIMIT = False
                macro.AFBglitter = False
                macro.cAFBglitter = False
                macro.cAFBDice = True
                macro.failed = False
                rebuffCooldown = max(0, float(macro.setdat.get("AFB_rebuff", 0) or 0) * 60)
                settingsManager.saveSettingFile("AFB_dice_cd", time.time() - rebuffCooldown, settingsManager.getUserDataPath("AFB.txt"))
                settingsManager.saveSettingFile("AFB_glitter_cd", time.time(), settingsManager.getUserDataPath("AFB.txt"))
                macro.AFB(gatherInterrupt=False)
                macro.cAFBDice = False
                return None
            if action == INTERRUPT_RESET and func:
                return runTask(func, args=args, resetAfter=resetAfter, convertAfter=convertAfter, allowAFB=allowAFB)
            return None

        pending_action = int(skipTask.value)
        if pending_action != INTERRUPT_NONE:
            return handle_interrupt(pending_action)
        
        questWatchContext = None
        taskWatchKey = watchedTaskKey()
        if taskWatchKey and taskWatchKey in macro.completedQuestWatchTasks:
            return None
        watchers = macro.questTaskWatchers.get(taskWatchKey, [])
        if watchers:
            watchedRows = [row for giver, action in watchers for row in (macro.questObservations.get(giver) or [])
                           if row["action"] == action and row["status"] != "complete"]
            if watchedRows and all(row["id"] in macro.deferredQuestObjectives for row in watchedRows):
                return None

        try:
            if taskWatchKey:
                questWatchContext = macro.startQuestTaskWatch(taskWatchKey)
                if questWatchContext and questWatchContext.get("skip_task"):
                    questWatchContext = None
                    return None
            #execute the task
            if func:
                returnVal = func(*args) 
                taskCompleted = True
            else:
                returnVal = None
            if questWatchContext:
                if macro.finishQuestTaskWatch(questWatchContext):
                    macro.markQuestTaskWatchCompleted(questWatchContext)
                questWatchContext = None
            #task done
            if resetAfter: 
                macro.reset(convert=convertAfter)
            
            #do priority tasks
            # Quest and Alt modes stay isolated from priority tasks.
            if (
                macro.setdat.get("macro_mode", "normal") not in ("quest", "alt", "vic")
                and macro.setdat["stinger_hunt"]
                and ((getattr(macro, "_viciousAttackTarget", None)
                      and time.time() - macro._viciousAttackTarget[1] <= 180)
                     or (macro.night and macro.confirmNight()))
            ):
                macro.stingerHunt()
                taskCompleted = True
            if (
                macro.setdat.get("macro_mode", "normal") not in ("quest", "alt", "vic")
                and macro.setdat["mondo_buff"]
                and macro.hasMondoRespawned()
            ):
                macro.collectMondoBuff()
                taskCompleted = True
            if macro.setdat.get("macro_mode", "normal") not in ("alt", "vic") and macro.hasScheduledRejoinArrived():
                macro.rejoin("Rejoining (Scheduled)")
                macro.saveTiming("rejoin_every")
                taskCompleted = True
            
            #auto field boost (can be disabled per-call via allowAFB)
            if allowAFB and macro.setdat["Auto_Field_Boost"] and not macro.AFBLIMIT:
                if macro.hasAFBRespawned("AFB_dice_cd", macro.setdat["AFB_rebuff"]*60) or macro.hasAFBRespawned("AFB_glitter_cd", macro.setdat["AFB_rebuff"]*60-30):
                    macro.AFB(gatherInterrupt=False)
                    taskCompleted = True
        except InterruptRequested as interrupt:
            skipTask.value = INTERRUPT_NONE
            if questWatchContext:
                macro.finishQuestTaskWatch(questWatchContext, checkCompletion=False)
                questWatchContext = None
            return handle_interrupt(interrupt.action)
        finally:
            if questWatchContext:
                if macro.finishQuestTaskWatch(questWatchContext):
                    macro.markQuestTaskWatchCompleted(questWatchContext)

        macro.clear_task_status()
        return returnVal
    

    def isBackpackReadyForWreath():
        try:
            current_backpack = macro.getBackpack()
            fields = list(macro.setdat.get("fields", []))
            fields_enabled = list(macro.setdat.get("fields_enabled", []))
            for index, enabled in enumerate(fields_enabled[:5]):
                if not enabled or index >= len(fields):
                    continue
                field_name = str(fields[index]).replace("_", " ").strip()
                field_settings = macro.fieldSettings.get(field_name, {})
                threshold = field_settings.get("backpack", 100)
                try:
                    threshold = float(threshold)
                except Exception:
                    threshold = 100
                if current_backpack >= threshold:
                    return True
            return False
        except Exception:
            return False

    def handleQuest(questGiver, executeQuest=True, keepMenuOpen=False):
        nonlocal questCache, questScanScreens, taskCompleted
        cached = questGiver in questCache and questCache[questGiver] is not None and not taskCompleted
        if cached:
            objectives = questCache[questGiver]
        elif not executeQuest:
            if questScanScreens is None:
                questScanScreens = macro.captureQuestScreenshots(keepOpen=keepMenuOpen)
            objectives = macro.findQuest(questGiver, questScreens=questScanScreens)
        else:
            objectives = macro.findQuest(questGiver)
        questCache[questGiver] = objectives
        title = (getattr(macro, "_last_quest_title", {}) or {}).get(questGiver, "")
        if macro.setdat.get("ignore_petal_quests", False) and title in HARDCODED_PETAL_IGNORE_TITLES:
            macro.questObservations[questGiver] = None
            return [], []
        if executeQuest and (objectives is None or not objectives) and canClaimTimedBearQuest(questGiver):
            submitting = objectives == []
            taskCompleted = True
            objectives = macro.getNewQuest(questGiver, submitting)
            if submitting:
                macro.hourlyReport.addHourlyStat("quests_completed", 1)
            questCache.pop(questGiver, None)
            macro.completedQuestWatchTasks.clear()
            macro.completedQuestWatchObjectives.clear()
        requiredTasks, feeds = [], []
        macro.questGatherInterruptMobs.pop(questGiver, None)
        for task, watchers in macro.questTaskWatchers.items():
            macro.questTaskWatchers[task] = [watcher for watcher in watchers if watcher[0] != questGiver]
        for objective in objectives or []:
            kind, _, target = objective.partition("_")
            tasks = []
            if kind == "kill":
                mob = target.split("_", 1)[1] if target.split("_", 1)[0].isdigit() else target
                if "ant" in mob and mob != "mantis":
                    tasks = ["ant_challenge", "ant_pass_dispenser"]
                else:
                    tasks = [mob]
                    if mob in regularMobData:
                        macro.questGatherInterruptMobs.setdefault(questGiver, set()).add(mob)
                watchTask = "kill_" + mob
            elif kind == "collect":
                tasks = [target.replace("-", "_")]
                watchTask = "collect_" + tasks[0]
            elif kind == "feed":
                amount, item = target.split("_", 1)
                feeds.append((item, 25 if amount == "*" else int(amount)))
                watchTask = "feed_" + item
            elif quest_uses_ant_challenge(objective, macro.setdat):
                tasks = ["ant_challenge", "ant_pass_dispenser"]
                watchTask = objective
            elif kind == "token" and target == "honey":
                tasks = ["honeytoken"]
                watchTask = None
            else:
                continue
            requiredTasks.extend(tasks)
            if watchTask:
                macro.questTaskWatchers.setdefault(watchTask, []).append((questGiver, objective))
            if "ant_challenge" in tasks:
                for task in ("ant_challenge", "collect_ant_pass_dispenser"):
                    macro.questTaskWatchers.setdefault(task, []).append((questGiver, objective))
        return list(dict.fromkeys(requiredTasks)), feeds

    def runQuestSupportTasks(requiredTasks):
        """
        Run non-gather quest requirements directly. Quest-only mode bypasses the
        normal priority queue, so enabling these settings is not enough there.
        """
        nonlocal taskCompleted
        for taskName in dict.fromkeys(requiredTasks):
            if taskName == "ant_pass_dispenser":
                if taskName in macroModule.collectData and macro.hasRespawned(taskName, macro.collectCooldowns[taskName]):
                    runTask(macro.collect, args=(taskName,))
                    taskCompleted = True
                continue

            if taskName == "ant_challenge":
                runTask(macro.antChallenge, resetAfter=False)
                taskCompleted = True
                continue

            if taskName in macroModule.collectData or taskName in macroModule.fieldBoosterData:
                if taskName in macro.collectCooldowns and macro.hasRespawned(taskName, macro.collectCooldowns[taskName]):
                    runTask(macro.collect, args=(taskName,))
                    taskCompleted = True
                continue

            if taskName == "honeytoken":
                continue

            if taskName in regularMobData:
                killedInAnyField = False
                for field in regularMobData[taskName]:
                    if macro.hasMobRespawned(taskName, field):
                        runTask(macro.killMob, args=(taskName, field,), convertAfter=False)
                        killedInAnyField = True
                if killedInAnyField:
                    taskCompleted = True

    def runReadyQuestInterruptMobs():
        """Kill ready quest mobs before the normal task queue starts gathering."""
        readyMobs = []
        seenMobFields = set()
        for questGiver, mobs in macro.questGatherInterruptMobs.items():
            interruptKey = f"{questGiver.replace(' ', '_')}_quest_gather_interrupt"
            if not macro.setdat.get(interruptKey, False):
                continue
            for mob in mobs:
                for field in regularMobData.get(mob, []):
                    mobField = (mob, field)
                    if mobField in seenMobFields or not macro.hasMobRespawned(mob, field):
                        continue
                    seenMobFields.add(mobField)
                    readyMobs.append(mobField)

        if not readyMobs:
            return False

        mobNames = ", ".join(sorted({mob.replace("_", " ").title() for mob, _ in readyMobs}))
        macro.logger.webhook("Quest mobs ready", f"Running before quest gathering: {mobNames}", "dark brown")
        for mob, field in readyMobs:
            # Recheck because an earlier field run can update shared mob timings.
            if macro.hasMobRespawned(mob, field):
                runTask(macro.killMob, args=(mob, field), convertAfter=False)
        return True

    #macro.rejoin()
    def get_task_list_order(settings):
        task_list = settings.get("task_list", None)
        if isinstance(task_list, list):
            return task_list
        task_queue = settings.get("task_queue", None)
        if isinstance(task_queue, list):
            return task_queue
        return settings.get("task_priority_order", [])

    def completedQuestGivers():
        """Givers whose last quest-menu read showed every objective complete, in giver order."""
        return [giver for giver in quest_giver_order(macro.setdat)
                if canClaimTimedBearQuest(giver) and (rows := macro.questObservations.get(giver))
                and all(row["status"] == "complete" for row in rows)]

    def gatherObjectives():
        return [objective for giver in quest_giver_order(macro.setdat)
                for objective in (getattr(macro, "questObservations", {}).get(giver) or [])
                if is_gather_objective(objective, macro.setdat) and objective["status"] != "complete"
                and objective["id"] not in macro.deferredQuestObjectives]

    def runQuestGathers():
        nonlocal questScanScreens, taskCompleted
        if not gatherObjectives():
            return []
        attempted = set()
        gathered = []
        currentField = None
        # With the quest menu kept open, a scan leaves it open for the gather it picks.
        keepMenuOpen = macro.setdat.get("quest_progress_watch", False)
        # Support tasks and quest claims may have changed progress since the first scan.
        questCache.clear()
        questScanScreens = None
        taskCompleted = False
        def scanQuestProgress():
            for giver in quest_giver_order(macro.setdat):
                if canClaimTimedBearQuest(giver):
                    handleQuest(giver, executeQuest=False, keepMenuOpen=keepMenuOpen)

        runTask(scanQuestProgress, resetAfter=False, allowAFB=False)
        turnedIn = set()
        while run.value != 0:
            # A finished quest is handed in before more gathering, including for the quest it hands out.
            for giver in completedQuestGivers():
                if giver in turnedIn:
                    continue
                turnedIn.add(giver)
                requiredTasks, _ = handleQuest(giver)
                for task in requiredTasks:
                    macro.setdat[task] = True
                # The quest it handed out is new work: it keeps no skips and can be turned in later.
                for skipped in (attempted, macro.deferredQuestObjectives):
                    skipped.difference_update([objectiveId for objectiveId in skipped if objectiveId[0] == giver])
                if giver not in completedQuestGivers():
                    turnedIn.discard(giver)
            pending = [obj for obj in gatherObjectives() if obj["id"] not in attempted]
            selected = choose_quest_gather(pending, macro.setdat, macro.fieldSettings, currentField)
            if selected is None:
                break
            objective = selected["objective"]
            field = selected["field"]
            beforeGather = {giver: list(rows or []) for giver, rows in macro.questObservations.items()}
            macro.questGatherOutcome = None
            macro.logger.webhook("Quest gathering",
                f"{objective['giver'].title()}: {objective['action'].replace('_', ' ')} in {field.title()} "
                f"with {selected['settings']['shape']} ({macro.setdat.get('quest_scheduling', 'quest giver priority')})",
                "light blue", route_category="quests")
            runTask(macro.gather, args=(field, selected["settings"], objective), resetAfter=False)
            if run.value == 0:
                break
            currentField = field
            if field not in gathered:
                gathered.append(field)
            if macro.questGatherOutcome in ("complete", "skipped", "unreadable"):
                attempted.add(objective["id"])
            else:
                # A time/backpack limit finishes this shared attempt, never its objectives.
                attempted.update(obj["id"] for obj in selected["objectives"])
            affected = {obj["giver"] for obj in pending
                        if field in allowed_fields(obj, macro.setdat, macro.fieldSettings)}

            def refreshQuestProgress():
                screens = macro.captureQuestScreenshots(keepOpen=keepMenuOpen)
                for giver in affected:
                    previous = macro.questObservations.get(giver) or beforeGather.get(giver, [])
                    found = None
                    try:
                        found = macro.findQuest(giver, questScreens=screens, logDetection=False)
                        if found is None:
                            found = macro.findQuest(giver, logDetection=False)
                    finally:
                        if found is None:
                            macro.questObservations[giver] = [{**obj, "status": "unknown"} for obj in previous]
                            macro.logger.webhook("Quest progress unreadable",
                                f"Could not refresh {giver.title()}. Remaining objectives will retry before gathering.",
                                "orange", route_category="quests")

            if affected:
                runTask(refreshQuestProgress, resetAfter=False, allowAFB=False)
            questCache.clear()
            questScanScreens = None
        # Nothing was picked to use the menu a scan left open.
        macro.closeQuestMenu()
        return gathered

    def cooldownTaskReady():
        profile = settingsManager.loadMacroProfile()
        if (profile["profile"] != macro._loadedProfile["profile"]
                or profile["settings"] != macro._loadedProfile["settings"]
                or profile["fields"] != macro._loadedProfile["fields"]):
            return True
        if macro.hasScheduledRejoinArrived():
            return True
        mode = macro.setdat.get("macro_mode", "normal")
        if mode not in ("quest", "alt") and macro.setdat.get("mondo_buff", False) and macro.hasMondoRespawned():
            return True
        if mode != "bug" and any(giver not in questCache and canClaimTimedBearQuest(giver)
                                 for giver in quest_giver_order(macro.setdat)):
            return True
        tasks = macro.questTaskWatchers if mode == "quest" else get_task_list_order(macro.setdat)
        for task in tasks:
            if task.startswith("kill_"):
                mob = task[5:]
                if not macro.setdat.get(mob, False):
                    continue
                if mob in regularMobData:
                    if any(macro.hasMobRespawned(mob, field) for field in regularMobData[mob]):
                        return True
                elif mob in bossCooldowns and macro.hasRespawned(mob, bossCooldowns[mob], applyMobRespawnBonus=True):
                    return True
            elif task.startswith("collect_") and mode != "bug":
                item = task[8:]
                if not macro.setdat.get(item, False):
                    continue
                if item == "sticker_stack":
                    if macro.hasStickerStackRespawned():
                        return True
                elif item in macro.collectCooldowns and macro.hasRespawned(item, macro.collectCooldowns[item]):
                    if item in macroModule.fieldBoosterData and not macro.hasRespawned("last_booster", macro.setdat["boost_seperate"]*60):
                        continue
                    if item != "wreath" or isBackpackReadyForWreath():
                        return True
            elif task == "blender" and mode == "normal" and macro.setdat.get("blender_enable", False):
                blender = ast.literal_eval(settingsManager.loadUserText("blender.txt"))
                if blender["collectTime"] != -1 and time.time() > blender["collectTime"]:
                    return True
            elif task == "planters" and mode == "normal" and macro.setdat.get("planters_mode", 0):
                if macro.setdat["planters_mode"] == 1:
                    planters = settingsManager.loadUserLiteral("manualplanters.txt") or {"planters": [], "harvestTimes": []}
                    if any(planter and time.time() > harvest for planter, harvest
                           in zip(planters["planters"], planters["harvestTimes"])):
                        return True
                else:
                    planters = settingsManager.loadUserJson("auto_planters.json")["planters"]
                    if any(planter["planter"] and time.time() > planter["harvest_time"] for planter in planters):
                        return True
        return False

    def waitForReadyTask():
        nonlocal lastIdleClick
        if taskCompleted or run.value == 0:
            lastIdleClick = time.time()
            return
        field = macro.setdat.get("cooldown_field", "none")
        if field in macro.fieldSettings:
            macro.logger.webhook("Cooldown gathering", f"Waiting for tasks in {field.title()}.", "light blue", route_category="gathering")
            runTask(macro.gather, args=(field, {"infinite_gather": False, "plant_sprout": False}, None, cooldownTaskReady),
                    resetAfter=False, allowAFB=False)
            lastIdleClick = time.time()
            return
        if macro.location != "spawn":
            runTask(macro.reset, resetAfter=False, allowAFB=False)
        macro.set_task_status("waiting_for_task", activity="Waiting for next task")
        # Keep Roblox active during long cooldowns without reopening the quest menu.
        if time.time() - lastIdleClick >= 60:
            mouse.click()
            lastIdleClick = time.time()
        time.sleep(1)

    while True:
        # Check for pause - wait while paused
        while run.value == 6:  # 6 = paused
            time.sleep(0.1)  # Wait while paused
        # Check if stop was requested while paused
        if run.value == 0:
            break  # Exit macro loop if stop requested

        # Idle passes reuse the board until work or a settings change can affect it.
        settingsChanged = macro.checkAndReloadSettings()
        if taskCompleted or settingsChanged:
            questCache.clear()
            macro.questObservations = {}
        questScanScreens = None
        taskCompleted = False
        macro.questGatherInterruptMobs.clear()
        macro.questTaskWatchers.clear()
        macro.completedQuestWatchTasks.clear()
        macro.completedQuestWatchObjectives.clear()
        macro.deferredQuestObjectives.clear()

        # Migration from old boolean flags to macro_mode is now handled in settings loader

        if macro.setdat.get("macro_mode", "normal") == "vic":
            runTask(macro.viciousHop, resetAfter=False, allowAFB=False)
            continue

        if macro.setdat.get("macro_mode", "normal") == "alt":
            if not altHostAuthorized:
                status.value = "alt_waiting_for_host"
                updateGUI.value = 1
                time.sleep(1)
                continue
            # Webhook field changes are stored separately from the normal task
            # slots and only become active after a fresh host command.
            altField = str(macro.setdat.get("alt_mode_field") or "").strip().lower()
            if not altField:
                status.value = "alt_waiting_for_host"
                updateGUI.value = 1
                time.sleep(1)
                continue
            updateGUI.value = 1
            runTask(macro.gather, args=(altField,), resetAfter=False, allowAFB=False)
            continue

        #run empty task
        #this is in case no other settings are selected
        runTask(resetAfter=False)

        updateGUI.value = 1

        # Check if field-only mode is enabled
        if macro.setdat.get("macro_mode", "normal") == "field":
            # Field-only mode: skip all tasks except field gathering
            # Get priority order and filter to only include enabled field gathering tasks
            priorityOrder = get_task_list_order(macro.setdat)
            executedTasks = set()

            # Filter priority order to only include gather tasks for enabled fields
            fieldOnlyTasks = []
            for taskId in priorityOrder:
                if taskId.startswith("gather_"):
                    fieldName = taskId.replace("gather_", "").replace("_", " ")
                    # Check if this field is enabled
                    for i in range(len(macro.setdat["fields_enabled"])):
                        if macro.setdat["fields_enabled"][i] and macro.setdat["fields"][i] == fieldName:
                            fieldOnlyTasks.append(taskId)
                            break

            # If no gather tasks are in priority order, fall back to sequential order of enabled fields
            if not fieldOnlyTasks:
                for i in range(len(macro.setdat["fields_enabled"])):
                    if macro.setdat["fields_enabled"][i]:
                        field = macro.setdat["fields"][i]
                        fieldOnlyTasks.append(f"gather_{field.replace(' ', '_')}")

            # Execute field gathering tasks in priority order
            for taskId in fieldOnlyTasks:
                if taskId.startswith("gather_"):
                    fieldName = taskId.replace("gather_", "").replace("_", " ")
                    if taskId not in executedTasks:
                        runTask(macro.gather, args=(fieldName,), resetAfter=False)
                        executedTasks.add(taskId)

            # Skip to next iteration
            continue

        if macro.setdat.get("macro_mode", "normal") == "quest":
            # Hand in every finished quest before starting work on any quest, new or old.
            claimed = [handleQuest(giver) for giver in quest_giver_order(macro.setdat)
                       if canClaimTimedBearQuest(giver)]
            for requiredTasks, feeds in claimed:
                for task in requiredTasks:
                    macro.setdat[task] = True
                runQuestSupportTasks(requiredTasks)
                for item, quantity in feeds:
                    runTask(macro.feedBee, args=(item, quantity), resetAfter=False)
            runQuestGathers()
            waitForReadyTask()
            continue

        # Check if bug-run-only mode is enabled
        if macro.setdat.get("macro_mode", "normal") == "bug":
            # Bug-only mode: skip all tasks except kill tasks (including bosses)
            priorityOrder = get_task_list_order(macro.setdat)
            executedTasks = set()

            # Filter priority order to only include enabled kill tasks or ant challenge
            bugOnlyTasks = []
            for taskId in priorityOrder:
                if taskId == "ant_challenge":
                    if macro.setdat.get("ant_challenge", False):
                        bugOnlyTasks.append(taskId)
                elif taskId == "stinger_hunt":
                    if macro.setdat.get("stinger_hunt", False):
                        bugOnlyTasks.append(taskId)
                elif taskId.startswith("kill_"):
                    mob = taskId.replace("kill_", "")
                    if macro.setdat.get(mob, False):
                        bugOnlyTasks.append(taskId)
            # No fallback to auto-add mobs: only tasks present in priority order will run

            # Execute bug run tasks in priority order
            for taskId in bugOnlyTasks:
                if taskId in executedTasks:
                    continue

                if taskId == "ant_challenge":
                    if macro.setdat.get("ant_challenge", False):
                        runTask(macro.antChallenge, resetAfter=False)
                        executedTasks.add(taskId)
                    continue

                if taskId == "stinger_hunt":
                    if macro.setdat.get("stinger_hunt", False):
                        runTask(macro.stingerHunt, resetAfter=False)
                        executedTasks.add(taskId)
                    continue

                mob = taskId.replace("kill_", "")

                if mob == "coconut_crab":
                    if macro.setdat["coconut_crab"] and macro.hasRespawned(mob, bossCooldowns[mob], applyMobRespawnBonus=True):
                        runTask(macro.coconutCrab)
                        executedTasks.add(taskId)
                    continue

                if mob == "king_beetle":
                    if macro.setdat["king_beetle"] and macro.hasRespawned(mob, bossCooldowns[mob], applyMobRespawnBonus=True):
                        runTask(macro.kingBeetle)
                        executedTasks.add(taskId)
                    continue

                if mob == "tunnel_bear":
                    if macro.setdat["tunnel_bear"] and macro.hasRespawned(mob, bossCooldowns[mob], applyMobRespawnBonus=True):
                        runTask(macro.tunnelBear)
                        executedTasks.add(taskId)
                    continue

                if mob == "stump_snail":
                    if macro.setdat["stump_snail"] and macro.hasRespawned(mob, bossCooldowns[mob], applyMobRespawnBonus=True):
                        runTask(macro.stumpSnail)
                        executedTasks.add(taskId)
                    continue

                if mob in regularMobData and macro.setdat.get(mob, False):
                    killedInAnyField = False
                    for field in regularMobData[mob]:
                        if macro.hasMobRespawned(mob, field):
                            runTask(macro.killMob, args=(mob, field,), convertAfter=False)
                            killedInAnyField = True
                    if killedInAnyField:
                        executedTasks.add(taskId)

            waitForReadyTask()
            # Skip to next iteration
            continue

        # Discover support tasks without claiming quests out of priority order.
        for giver in quest_giver_order(macro.setdat):
            if canClaimTimedBearQuest(giver):
                requiredTasks, _ = handleQuest(giver, executeQuest=False)
                for task in requiredTasks:
                    macro.setdat[task] = True
        runReadyQuestInterruptMobs()

        # Helper function for manual planters
        def goToNextCycle(cycle, slot):
            #go to the next cycle
            for _ in range(8):
                cycle += 1
                if cycle > 5:
                    cycle = 1
                if macro.setdat[f"cycle{cycle}_{slot+1}_planter"] != "none" and macro.setdat[f"cycle{cycle}_{slot+1}_field"] != "none":
                    return cycle
            else: 
                return False

        def emptyManualPlanterData():
            return {
                "cycles": [1, 1, 1],
                "planters": ["", "", ""],
                "fields": ["", "", ""],
                "gatherFields": ["", "", ""],
                "harvestTimes": [0, 0, 0]
            }

        def normalizeManualPlanterData(rawData):
            normalized = emptyManualPlanterData()
            if not isinstance(rawData, dict):
                return normalized

            for key, defaultValues in normalized.items():
                values = rawData.get(key, defaultValues)
                if not isinstance(values, list):
                    values = defaultValues

                cleaned = list(values[:3])
                while len(cleaned) < 3:
                    cleaned.append(defaultValues[len(cleaned)])

                if key == "cycles":
                    normalized[key] = []
                    for value in cleaned:
                        try:
                            cycle = int(value)
                        except Exception:
                            cycle = 1
                        normalized[key].append(min(5, max(1, cycle)))
                elif key == "harvestTimes":
                    normalized[key] = []
                    for value in cleaned:
                        try:
                            harvestTime = float(value or 0)
                        except Exception:
                            harvestTime = 0
                        normalized[key].append(harvestTime)
                else:
                    normalized[key] = [str(value or "") for value in cleaned]

            return normalized

        def saveManualPlanterData(planterData):
            nonlocal planterDataRaw
            normalized = normalizeManualPlanterData(planterData)
            planterDataRaw = str(normalized)
            with open(settingsManager.ensureUserFile("manualplanters.txt"), "w") as f:
                f.write(planterDataRaw)
            return normalized
        
        # Get priority order from settings, or use empty list if not set
        priorityOrder = get_task_list_order(macro.setdat)
        
        # Track which tasks have been executed to avoid duplicates
        executedTasks = set()
        
        # Track planter data for gather fields
        planterDataRaw = None
        
        # Helper function to execute a task by its ID
        def executeTask(taskId):
            nonlocal planterDataRaw, executedTasks, taskCompleted
            
            # Skip if already executed
            if taskId in executedTasks:
                return False
            
            if taskId.startswith("quest_"):
                giver = taskId[6:].replace("_", " ")
                if giver not in quest_giver_order(macro.setdat) or not canClaimTimedBearQuest(giver):
                    return False
                # Other quests already known to be finished are handed in first, before any new quest's feeding.
                givers = list(dict.fromkeys([giver] + completedQuestGivers()))
                claimed = [handleQuest(claimGiver) for claimGiver in givers]
                for claimGiver in givers:
                    executedTasks.add("quest_" + claimGiver.replace(" ", "_"))
                for requiredTasks, feeds in claimed:
                    for task in requiredTasks:
                        macro.setdat[task] = True
                for _, feeds in claimed:
                    for item, quantity in feeds:
                        runTask(macro.feedBee, args=(item, quantity), resetAfter=False)
                return True

            # Handle collect tasks
            if taskId.startswith("collect_"):
                collectName = taskId.replace("collect_", "")

                # Special case: sprouts
                if collectName == "sprouts":
                    if macro.setdat.get("sprouts_enable", False):
                        if runTask(macro.collectSprouts, resetAfter=False):
                            executedTasks.add(taskId)
                            return True
                    return False

                # Special case: sticker_sprout
                if collectName == "sticker_sprout":
                    if macro.stickerSproutReady():
                        if runTask(macro.collectStickerSprout, resetAfter=False):
                            executedTasks.add(taskId)
                            return True
                    return False
                
                # Special case: sticker_printer
                if collectName == "sticker_printer":
                    if macro.setdat["sticker_printer"] and macro.hasRespawned("sticker_printer", macro.collectCooldowns["sticker_printer"]):
                        runTask(macro.collectStickerPrinter)
                        executedTasks.add(taskId)
                        return True
                    return False
                
                # Special case: sticker_stack
                if collectName == "sticker_stack":
                    if macro.setdat["sticker_stack"] and macro.hasStickerStackRespawned():
                        runTask(macro.collect, args=("sticker_stack",))
                        executedTasks.add(taskId)
                        return True
                    return False
                
                # Field boosters (handled separately due to gather logic)
                if collectName in ["blue_booster", "red_booster", "mountain_booster"]:
                    if collectName in macroModule.fieldBoosterData:
                        if macro.setdat[collectName] and macro.hasRespawned(collectName, macro.collectCooldowns[collectName]) and macro.hasRespawned("last_booster", macro.setdat["boost_seperate"]*60):
                            boostedField = runTask(macro.collect, args=(collectName,))
                            if macro.setdat["gather_boosted"] and boostedField:
                                # Gather in boosted field for 15 minutes
                                st = time.time()
                                while time.time() - st < 15*60:
                                    runTask(macro.gather, args=(boostedField,), resetAfter=False)
                            executedTasks.add(taskId)
                            return True
                    return False
                
                # Regular collect items
                if collectName in macroModule.collectData:
                    if macro.setdat[collectName] and macro.hasRespawned(collectName, macro.collectCooldowns[collectName]):
                        if collectName == "wreath" and not isBackpackReadyForWreath():
                            macro.logger.webhook("", "Honey Wreath ready, but backpack is not full yet. Deferring claim", "dark brown", "screen")
                            return False
                        runTask(macro.collect, args=(collectName,))
                        executedTasks.add(taskId)
                        return True
            
            # Handle kill tasks
            if taskId.startswith("kill_"):
                mob = taskId.replace("kill_", "")
                
                # Special cases: coconut_crab, king_beetle, tunnel_bear, and stump_snail
                if mob == "coconut_crab":
                    if macro.setdat["coconut_crab"] and macro.hasRespawned(mob, bossCooldowns[mob], applyMobRespawnBonus=True):
                        runTask(macro.coconutCrab)
                        executedTasks.add(taskId)
                        return True
                    return False
                

                # King Beetle respawns every 24 hours (20 hours 24 minutes with Gifted Vicious Bee)
                if mob == "king_beetle":
                    if macro.setdat["king_beetle"] and macro.hasRespawned(mob, bossCooldowns[mob], applyMobRespawnBonus=True):
                        runTask(macro.kingBeetle)
                        executedTasks.add(taskId)
                        return True
                    return False

                # Tunnel Bear respawns every 48 hours (40 hours 48 minutes with Gifted Vicious Bee)
                if mob == "tunnel_bear":
                    if macro.setdat["tunnel_bear"] and macro.hasRespawned(mob, bossCooldowns[mob], applyMobRespawnBonus=True):
                        runTask(macro.tunnelBear)
                        executedTasks.add(taskId)
                        return True
                    return False
                
                if mob == "stump_snail":
                    if macro.setdat["stump_snail"] and macro.hasRespawned(mob, bossCooldowns[mob], applyMobRespawnBonus=True):
                        runTask(macro.stumpSnail)
                        executedTasks.add(taskId)
                        return True
                    return False
                
                # Regular mobs
                if mob in regularMobData:
                    if macro.setdat[mob]:
                        # Check all fields for this mob and kill in each field where it has respawned
                        # We need to check ALL fields before moving to the next task
                        killedInAnyField = False
                        for f in regularMobData[mob]:
                            if macro.hasMobRespawned(mob, f):
                                runTask(macro.killMob, args=(mob, f,), convertAfter=False)
                                killedInAnyField = True
                                # After killing in one field, return True to trigger re-check
                                # This allows the outer loop to iterate again and check remaining fields
                                return True
                        # If we checked all fields and none had respawned mobs, return False
                        # This will allow the loop to move to the next task
                        return False
                return False
            
            # Handle gather tasks
            if taskId.startswith("gather_"):
                fieldName = taskId.replace("gather_", "").replace("_", " ")

                # When a field is needed for an active quest, let the quest resolver handle it
                # in quest order instead of the global gather priority queue.
                questObjectives = gatherObjectives()
                selectedQuestGather = choose_quest_gather(questObjectives, macro.setdat, macro.fieldSettings)
                if (any(obj["field"] == fieldName for obj in questObjectives)
                        or (selectedQuestGather and selectedQuestGather["field"] == fieldName)):
                    return False
                
                # Check if this field is enabled in gather tab
                for i in range(len(macro.setdat["fields_enabled"])):
                    if macro.setdat["fields_enabled"][i] and macro.setdat["fields"][i] == fieldName:
                        runTask(macro.gather, args=(fieldName,), resetAfter=False)
                        executedTasks.add(taskId)
                        return True
                
                return False

            # Handle special tasks
            if taskId == "blender":
                if macro.setdat["blender_enable"]:
                    with open(settingsManager.ensureUserFile("blender.txt"), "r") as f:
                        blenderData = ast.literal_eval(f.read())
                    f.close()
                    if blenderData["collectTime"] > -1 and time.time() > blenderData["collectTime"]:
                        runTask(macro.blender, args=(blenderData,))
                        executedTasks.add(taskId)
                        return True
                return False
            
            if taskId == "planters":
                if not macro.setdat["planters_mode"]:
                    return False
                
                # Manual planters
                if macro.setdat["planters_mode"] == 1:
                    if planterDataRaw is None:
                        with open(settingsManager.ensureUserFile("manualplanters.txt"), "r") as f:
                            planterDataRaw = f.read()
                        f.close()
                    
                    if not planterDataRaw.strip():
                        planterData = emptyManualPlanterData()
                        for i in range(3):
                            if macro.setdat[f"cycle1_{i+1}_planter"] == "none" or macro.setdat[f"cycle1_{i+1}_field"] == "none":
                                continue
                            planter = runTask(macro.placePlanterInCycle, args = (i, 1),resetAfter=False, allowAFB=False)
                            if planter:
                                planterData["planters"][i] = planter[0]
                                planterData["fields"][i] = planter[1]
                                planterData["harvestTimes"][i] = planter[2]
                                planterData["gatherFields"][i] = planter[1] if planter[3] else ""
                                planterData = saveManualPlanterData(planterData)
                        executedTasks.add(taskId)
                        return True
                    else:
                        try:
                            planterData = normalizeManualPlanterData(ast.literal_eval(planterDataRaw))
                        except Exception:
                            planterData = emptyManualPlanterData()
                            planterData = saveManualPlanterData(planterData)
                        for i in range(3):
                            cycle = planterData["cycles"][i]
                            if planterData["planters"][i] and time.time() > planterData["harvestTimes"][i]:
                                if runTask(macro.collectPlanter, args=(planterData["planters"][i], planterData["fields"][i])):
                                    planterData["harvestTimes"][i] = 0
                                    planterData["planters"][i] = ""
                                    planterData["fields"][i] = ""
                                    planterData["gatherFields"][i] = ""
                                    planterData = saveManualPlanterData(planterData)
                                    updateGUI.value = 1
                        
                        for i in range(3):
                            cycle = planterData["cycles"][i]
                            if planterData["planters"][i]:
                                continue
                            nextCycle = goToNextCycle(cycle, i)
                            if not nextCycle:
                                continue
                            
                            planterToPlace = macro.setdat[f"cycle{nextCycle}_{i+1}_planter"]
                            otherSlotPlanters = planterData["planters"][:i] + planterData["planters"][i+1:]
                            if planterToPlace in otherSlotPlanters:
                                continue
                            
                            fieldToPlace = macro.setdat[f"cycle{nextCycle}_{i+1}_field"]
                            otherSlotFields = planterData["fields"][:i] + planterData["fields"][i+1:]
                            if fieldToPlace in otherSlotFields:
                                continue
                            
                            planter = runTask(macro.placePlanterInCycle, args = (i, nextCycle),resetAfter=False, allowAFB=False)
                            if planter:
                                planterData["cycles"][i] = nextCycle
                                planterData["planters"][i] = planter[0]
                                planterData["fields"][i] = planter[1]
                                planterData["harvestTimes"][i] = planter[2]
                                planterData["gatherFields"][i] = planter[1] if planter[3] else ""
                                planterData = saveManualPlanterData(planterData)
                                updateGUI.value = 1
                        executedTasks.add(taskId)
                        return True
                
                # Auto planters
                elif macro.setdat["planters_mode"] == 2:
                    try:
                        with open(settingsManager.ensureUserFile("auto_planters.json"), "r") as f:
                            data = json.load(f)
                    except Exception:
                        data = {}

                    fieldToNectar = {}
                    for nectarName, nectarFields in macroModule.nectarFields.items():
                        for fieldName in nectarFields:
                            fieldToNectar[fieldName] = nectarName

                    planterData = data.get("planters", [])
                    nectarLastFields = data.get("nectar_last_field", {})
                    gatherFlag = data.get("gather", False)
                    fieldDegradation = data.get("field_degradation", {})

                    priorityMap = {}
                    for i in range(5):
                        nectar = macro.setdat[f"auto_priority_{i}_nectar"]
                        if nectar == "none":
                            continue
                        priorityMap[nectar] = {
                            "min": float(macro.setdat[f"auto_priority_{i}_min"]),
                            "index": i,
                            "weight": max(0.5, 1.35 - (i * 0.12))
                        }

                    def emptyFieldDegradationState():
                        return {
                            fieldName: {
                                "hours": 0.0,
                                "updated_at": 0.0
                            }
                            for fieldName in fieldToNectar
                        }

                    def getDecayedDegradationEntry(fieldName, defaultNow=None):
                        now = time.time() if defaultNow is None else defaultNow
                        rawEntry = fieldDegradation.get(fieldName, {})

                        if isinstance(rawEntry, dict):
                            hours = float(rawEntry.get("hours", rawEntry.get("value", 0) or 0))
                            updatedAt = float(rawEntry.get("updated_at", now) or now)
                        else:
                            hours = float(rawEntry or 0)
                            updatedAt = now

                        elapsedHours = max(0.0, (now - updatedAt) / 3600.0)
                        remainingHours = max(0.0, min(48.0, hours - elapsedHours))
                        return {
                            "hours": remainingHours,
                            "updated_at": now
                        }

                    def normalizeFieldDegradation():
                        nonlocal fieldDegradation
                        now = time.time()
                        normalized = emptyFieldDegradationState()
                        for fieldName in normalized:
                            normalized[fieldName] = getDecayedDegradationEntry(fieldName, defaultNow=now)
                        fieldDegradation = normalized

                    def saveAutoPlanterData():
                        data = {
                            "planters": planterData,
                            "nectar_last_field": nectarLastFields,
                            "gather": gatherFlag,
                            "field_degradation": fieldDegradation
                        }
                        with open(settingsManager.ensureUserFile("auto_planters.json"), "w") as f:
                            json.dump(data, f, indent=3)
                        f.close()
                        updateGUI.value = 1

                    def getPlanterRanking(field, planterName):
                        for planterObj in macroModule.autoPlanterRankings.get(field, []):
                            if planterObj["name"] == planterName:
                                return planterObj
                        return None

                    def estimateNectarGain(planterObj, growTimeSeconds):
                        growTimeSeconds = max(0, growTimeSeconds)
                        return min(100.0, round((growTimeSeconds * planterObj["nectar_bonus"] * planterObj["grow_bonus"] / 864), 1))

                    def getEffectiveNaturalGrowTimeSeconds(fieldName, planterObj):
                        return max(0.0, (planterObj["grow_time"] + getFieldDegradationHours(fieldName)) * 60 * 60)

                    def normalizeAutoPlanterSlot(slot):
                        normalized = emptyAutoPlanterSlot()
                        if isinstance(slot, dict):
                            for key in normalized:
                                normalized[key] = slot.get(key, normalized[key])

                        if normalized["field"]:
                            normalized["field"] = normalized["field"].replace("_", " ")
                        if normalized["planter"] and not normalized["nectar"]:
                            normalized["nectar"] = fieldToNectar.get(normalized["field"], "")

                        ranking = None
                        if normalized["planter"] and normalized["field"]:
                            ranking = getPlanterRanking(normalized["field"], normalized["planter"])

                        if normalized["planter"] and ranking:
                            if normalized["grow_duration"] <= 0:
                                normalized["grow_duration"] = ranking["grow_time"] * 60 * 60
                            if normalized["natural_grow_duration"] <= 0:
                                normalized["natural_grow_duration"] = ranking["grow_time"] * 60 * 60
                            if normalized["placed_time"] <= 0 and normalized["harvest_time"] > 0:
                                normalized["placed_time"] = max(0, normalized["harvest_time"] - normalized["grow_duration"])
                            if normalized["nectar_est_percent"] <= 0:
                                normalized["nectar_est_percent"] = estimateNectarGain(ranking, normalized["grow_duration"])

                        return normalized

                    normalizeFieldDegradation()
                    planterData = [normalizeAutoPlanterSlot(slot) for slot in planterData[:3]]
                    while len(planterData) < 3:
                        planterData.append(emptyAutoPlanterSlot())
                    for nectarName in macroModule.nectarNames:
                        nectarLastFields.setdefault(nectarName, "")

                    currentNectarCache = {}

                    def getCurrentNectarPercent(nectar):
                        if nectar not in currentNectarCache:
                            try:
                                currentNectarCache[nectar] = macro.buffDetector.getNectar(nectar)
                            except Exception:
                                currentNectarCache[nectar] = 0.0
                            print(f"Current {nectar} Nectar: {currentNectarCache[nectar]}%")
                        return currentNectarCache[nectar]

                    def getPriorityInfo(nectar):
                        return priorityMap.get(nectar, {"min": 100.0, "index": len(priorityMap), "weight": 0.35})

                    def getEstimateNectarPercent(nectar):
                        return sum(
                            max(0, planter.get("nectar_est_percent", 0))
                            for planter in planterData
                            if planter["planter"] and planter.get("nectar") == nectar
                        )

                    def getTotalNectarPercent(nectar):
                        return getCurrentNectarPercent(nectar) + getEstimateNectarPercent(nectar)

                    def calculatePlacementPlan(fieldName, planterObj, nectar, projectedNectarPercent):
                        now = time.time()
                        projectedNectarPercent = max(0.0, projectedNectarPercent)
                        minPercent = max(getPriorityInfo(nectar)["min"], projectedNectarPercent)
                        naturalGrowTimeSeconds = getEffectiveNaturalGrowTimeSeconds(fieldName, planterObj)
                        naturalGrowTimeHours = naturalGrowTimeSeconds / 3600.0

                        if macro.setdat["auto_planters_collect_auto"]:
                            nectarBonus = max(planterObj["nectar_bonus"], 0.1)
                            growBonus = max(planterObj["grow_bonus"], 0.1)
                            totalBonus = max(nectarBonus * growBonus, 0.1)
                            timeToCap = max(0.25, ((max(0, 100 - projectedNectarPercent) / nectarBonus) * 0.24) / growBonus)

                            if totalBonus < 1.2:
                                growTimeHours = min(timeToCap, 0.5)
                            elif minPercent > projectedNectarPercent and projectedNectarPercent <= 90:
                                if projectedNectarPercent > 20:
                                    bonusTime = (100 / projectedNectarPercent) * totalBonus
                                    growTimeHours = (((minPercent - projectedNectarPercent + bonusTime) / nectarBonus) * 0.24) / growBonus
                                elif projectedNectarPercent > 10:
                                    growTimeHours = min(naturalGrowTimeHours, 4)
                                else:
                                    growTimeHours = min(naturalGrowTimeHours, 2)
                            else:
                                growTimeHours = timeToCap

                            finalGrowTime = min(
                                naturalGrowTimeHours,
                                (growTimeHours + growTimeHours / totalBonus),
                                (timeToCap + timeToCap / totalBonus)
                            ) * 60 * 60
                            planterHarvestTime = now + finalGrowTime
                        elif macro.setdat["auto_planters_collect_full"]:
                            finalGrowTime = naturalGrowTimeSeconds
                            planterHarvestTime = now + finalGrowTime
                        else:
                            finalGrowTime = min(naturalGrowTimeHours, macro.setdat["auto_planters_collect_every"]) * 60 * 60
                            planterHarvestTime = now + finalGrowTime
                            for activePlanter in planterData:
                                harvestTime = activePlanter["harvest_time"]
                                if harvestTime > now and planterHarvestTime > harvestTime:
                                    planterHarvestTime = harvestTime
                            finalGrowTime = max(0, planterHarvestTime - now)

                        return {
                            "grow_duration": finalGrowTime,
                            "harvest_time": planterHarvestTime,
                            "placed_time": now,
                            "nectar_est_percent": estimateNectarGain(planterObj, finalGrowTime),
                            "natural_grow_duration": naturalGrowTimeSeconds
                        }

                    def sendNectarPercentageWebhook():
                        try:
                            nectarPercentages = []
                            for nectarName in macroModule.nectarNames:
                                try:
                                    totalPercent = macro.buffDetector.getNectar(nectarName)
                                except Exception:
                                    totalPercent = 0.0
                                nectarPercentages.append((nectarName, totalPercent))

                            menuLines = [f"**{name.title()}**: {round(percent,1)}%" for name, percent in nectarPercentages]
                            menuText = "\n".join(menuLines)

                            try:
                                from modules.screen.screenshot import screenshotRobloxWindow
                                img = screenshotRobloxWindow()
                                img_path = "webhook_nectar.png"
                                try:
                                    from PIL import ImageDraw, ImageFont
                                    draw = ImageDraw.Draw(img)
                                    try:
                                        font = ImageFont.truetype("/Library/Fonts/Arial.ttf", 20)
                                    except Exception:
                                        font = ImageFont.load_default()

                                    lines = [f"{name.title()}: {round(percent,1)}%" for name, percent in nectarPercentages]
                                    padding = 8
                                    line_h = font.getsize("Tg")[1] + 4
                                    box_w = max(font.getsize(line)[0] for line in lines) + padding * 2
                                    box_h = line_h * len(lines) + padding * 2
                                    draw.rectangle([(10, 10), (10 + box_w, 10 + box_h)], fill=(0, 0, 0, 180))
                                    for idx, line in enumerate(lines):
                                        draw.text((10 + padding, 10 + padding + idx * line_h), line, font=font, fill=(255, 255, 255))

                                    img.save(img_path)
                                    macro.logger.webhook("Nectar Percentages", menuText, "white", imagePath=img_path)
                                except Exception:
                                    macro.logger.webhook("Nectar Percentages", menuText, "white")
                            except Exception:
                                macro.logger.webhook("Nectar Percentages", menuText, "white")
                        except Exception:
                            pass

                    def savePlacedPlanter(slot, field, planterObj, nectar, placementPlan):
                        nonlocal planterData, nectarLastFields
                        planterData[slot] = {
                            "planter": planterObj["name"],
                            "nectar": nectar,
                            "field": field,
                            "harvest_time": placementPlan["harvest_time"],
                            "nectar_est_percent": placementPlan["nectar_est_percent"],
                            "placed_time": placementPlan["placed_time"],
                            "grow_duration": placementPlan["grow_duration"],
                            "natural_grow_duration": placementPlan["natural_grow_duration"]
                        }
                        planterReady = time.strftime("%H:%M:%S", time.gmtime(placementPlan["grow_duration"]))
                        macro.logger.webhook("", f"Planter will be ready in: {planterReady}", "light blue")
                        nectarLastFields[nectar] = field
                        saveAutoPlanterData()
                        sendNectarPercentageWebhook()

                    def getFieldDegradationHours(fieldName):
                        entry = getDecayedDegradationEntry(fieldName)
                        fieldDegradation[fieldName] = entry
                        return entry["hours"]

                    def getNaturalPlanterProgress(planter):
                        if not planter["planter"]:
                            return 0.0
                        naturalGrowDuration = planter.get("natural_grow_duration", 0)
                        placedTime = planter.get("placed_time", 0)
                        if naturalGrowDuration > 0 and placedTime > 0:
                            return max(0.0, min(1.0, (time.time() - placedTime) / naturalGrowDuration))
                        if planter["harvest_time"] <= time.time():
                            return 1.0
                        return 0.0

                    def recordFieldDegradation(planter):
                        fieldName = planter.get("field")
                        planterName = planter.get("planter")
                        if not fieldName or not planterName:
                            return

                        ranking = getPlanterRanking(fieldName, planterName)
                        if not ranking:
                            return

                        naturalGrowHours = max(
                            ranking["grow_time"],
                            (planter.get("natural_grow_duration", 0) or 0) / 3600.0
                        )
                        progress = getNaturalPlanterProgress(planter)
                        degradationToAdd = 1.0 + (naturalGrowHours * max(0.0, progress))
                        currentHours = getFieldDegradationHours(fieldName)
                        fieldDegradation[fieldName] = {
                            "hours": min(48.0, currentHours + degradationToAdd),
                            "updated_at": time.time()
                        }

                    planterSlotsToHarvest = []
                    if macro.setdat["auto_planters_collect_auto"]:
                        for nectarName in macroModule.nectarNames:
                            matchingPlanters = []
                            currentNectarPercent = getCurrentNectarPercent(nectarName)
                            projectedNectarPercent = getTotalNectarPercent(nectarName)

                            if currentNectarPercent >= 99:
                                requiredProgress = 0.0
                            elif projectedNectarPercent >= 120:
                                requiredProgress = 0.55
                            elif currentNectarPercent >= 90 and projectedNectarPercent >= 110:
                                requiredProgress = 0.75
                            else:
                                continue

                            for slot, planter in enumerate(planterData):
                                if planter["planter"] and planter.get("nectar") == nectarName:
                                    matchingPlanters.append((slot, planter, getNaturalPlanterProgress(planter)))

                            matchingPlanters.sort(key=lambda item: (-item[2], item[1]["harvest_time"]))
                            remainingProjected = projectedNectarPercent
                            targetProjected = max(getPriorityInfo(nectarName)["min"] + 5, 100)

                            for slot, planter, progress in matchingPlanters:
                                timeRemaining = max(0, planter["harvest_time"] - time.time())
                                if currentNectarPercent < 99 and progress < requiredProgress and timeRemaining > 45 * 60:
                                    continue
                                planterSlotsToHarvest.append(slot)
                                remainingProjected -= max(0, planter.get("nectar_est_percent", 0))
                                if remainingProjected <= targetProjected:
                                    break

                    for slot, planter in enumerate(planterData):
                        if planter["planter"] and time.time() > planter["harvest_time"]:
                            planterSlotsToHarvest.append(slot)

                    planterSlotsToHarvest = sorted(set(planterSlotsToHarvest))
                    for slot in planterSlotsToHarvest:
                        planter = planterData[slot]
                        if not planter["planter"]:
                            continue
                        if runTask(macro.collectPlanter, args=(planter["planter"], planter["field"])):
                            recordFieldDegradation(planter)
                            planterData[slot] = emptyAutoPlanterSlot()
                            currentNectarCache.clear()
                            saveAutoPlanterData()

                    maxAllowedPlanters = 0
                    for planterName in macroModule.allPlanters:
                        settingName = planterName.replace(" ", "_")
                        if macro.setdat.get(f"auto_planter_{settingName}", False):
                            maxAllowedPlanters += 1
                    maxAllowedPlanters = min(maxAllowedPlanters, macro.setdat["auto_max_planters"])

                    blockedPlacements = set()
                    blockedPlanters = set()

                    def getAvailableFields(occupiedFields):
                        return [
                            field for field in fieldToNectar
                            if macro.setdat.get(f"auto_field_{field.replace(' ', '_')}", False) and field not in occupiedFields
                        ]

                    def buildPlacementCandidates(occupiedFields, occupiedPlanters):
                        candidates = []
                        for field in getAvailableFields(occupiedFields):
                            addedForField = 0
                            for planterObj in macroModule.autoPlanterRankings.get(field, []):
                                planterName = planterObj["name"]
                                if planterName in occupiedPlanters or planterName in blockedPlanters or (planterName, field) in blockedPlacements:
                                    continue

                                settingPlanter = planterName.replace(" ", "_")
                                if not macro.setdat.get(f"auto_planter_{settingPlanter}", False):
                                    continue
                                if not macro.setdat.get(f"auto_planter_{settingPlanter}_field_{field.replace(' ', '_')}", True):
                                    continue

                                candidates.append({
                                    "field": field,
                                    "nectar": fieldToNectar[field],
                                    "planter": planterName,
                                    "planter_obj": planterObj
                                })
                                addedForField += 1
                                if addedForField >= 4:
                                    break
                        return candidates

                    def evaluateCandidate(candidate, projectedNectarPercentages, availableFieldCounts):
                        nectar = candidate["nectar"]
                        priorityInfo = getPriorityInfo(nectar)
                        projectedPercent = projectedNectarPercentages[nectar]
                        if projectedPercent >= max(priorityInfo["min"] + 20, 110):
                            return None

                        placementPlan = calculatePlacementPlan(candidate["field"], candidate["planter_obj"], nectar, projectedPercent)
                        if placementPlan["nectar_est_percent"] <= 0:
                            return None

                        deficitToMin = max(0.0, priorityInfo["min"] - projectedPercent)
                        if deficitToMin > 0:
                            needWeight = 1.0 + (deficitToMin / 18.0)
                        elif projectedPercent < 100:
                            needWeight = 0.45 + ((100 - projectedPercent) / 160.0)
                        else:
                            needWeight = max(0.05, 0.18 - ((projectedPercent - 100) / 120.0))

                        score = candidate["planter_obj"]["nectar_bonus"] * candidate["planter_obj"]["grow_bonus"]
                        score *= priorityInfo["weight"] * needWeight

                        if availableFieldCounts.get(nectar, 0) > 1 and nectarLastFields.get(nectar) == candidate["field"]:
                            score *= 0.97

                        degradationHours = getFieldDegradationHours(candidate["field"])
                        degradationPenalty = 1 / (1 + (degradationHours / 12.0))
                        score *= degradationPenalty
                        score *= max(0.1, candidate["planter_obj"]["grow_time"] / max(0.1, placementPlan["natural_grow_duration"] / 3600.0))

                        return {
                            "score": score,
                            "plan": placementPlan
                        }

                    def findBestPlacements(slotsRemaining, occupiedFields, occupiedPlanters, projectedNectarPercentages):
                        if slotsRemaining <= 0:
                            return 0.0, []

                        candidates = buildPlacementCandidates(occupiedFields, occupiedPlanters)
                        if not candidates:
                            return 0.0, []

                        availableFieldCounts = {}
                        for candidate in candidates:
                            nectar = candidate["nectar"]
                            availableFieldCounts[nectar] = availableFieldCounts.get(nectar, 0) + 1

                        scoredCandidates = []
                        for candidate in candidates:
                            evaluation = evaluateCandidate(candidate, projectedNectarPercentages, availableFieldCounts)
                            if evaluation and evaluation["score"] > 0:
                                scoredCandidates.append((evaluation["score"], candidate, evaluation["plan"]))

                        if not scoredCandidates:
                            return 0.0, []

                        scoredCandidates.sort(key=lambda item: item[0], reverse=True)
                        scoredCandidates = scoredCandidates[:36]

                        bestScore = 0.0
                        bestPlacements = []

                        for score, candidate, placementPlan in scoredCandidates:
                            updatedProjected = projectedNectarPercentages.copy()
                            updatedProjected[candidate["nectar"]] += placementPlan["nectar_est_percent"]

                            futureScore, futurePlacements = findBestPlacements(
                                slotsRemaining - 1,
                                occupiedFields | {candidate["field"]},
                                occupiedPlanters | {candidate["planter"]},
                                updatedProjected
                            )

                            totalScore = score + futureScore
                            if totalScore > bestScore:
                                bestScore = totalScore
                                bestPlacements = [(candidate, placementPlan)] + futurePlacements

                        return bestScore, bestPlacements

                    while True:
                        plantersPlaced = sum(bool(planter["planter"]) for planter in planterData)
                        if plantersPlaced >= maxAllowedPlanters:
                            break

                        openSlots = [idx for idx, planter in enumerate(planterData) if not planter["planter"]]
                        if not openSlots:
                            break

                        projectedNectarPercentages = {
                            nectarName: getTotalNectarPercent(nectarName)
                            for nectarName in macroModule.nectarNames
                        }
                        occupiedFields = {planter["field"] for planter in planterData if planter["field"]}
                        occupiedPlanters = {planter["planter"] for planter in planterData if planter["planter"]}
                        _, plannedPlacements = findBestPlacements(
                            min(len(openSlots), maxAllowedPlanters - plantersPlaced),
                            occupiedFields,
                            occupiedPlanters,
                            projectedNectarPercentages
                        )

                        if not plannedPlacements:
                            break

                        slot = openSlots[0]
                        candidate, placementPlan = plannedPlacements[0]
                        macro.logger.webhook(
                            "",
                            f"Auto-planter chose {candidate['planter'].title()} in {candidate['field'].title()} for {candidate['nectar'].title()}",
                            "dark brown"
                        )

                        if runTask(
                            macro.placePlanter,
                            args=(candidate["planter"], candidate["field"], False),
                            convertAfter=False,
                            allowAFB=False
                        ):
                            savePlacedPlanter(slot, candidate["field"], candidate["planter_obj"], candidate["nectar"], placementPlan)
                            if gatherFlag:
                                runTask(macro.gather, args=(candidate["field"],), resetAfter=False)
                        else:
                            if getattr(macro, "lastPlanterPlacementFailure", None) == "missing_inventory":
                                blockedPlanters.add(candidate["planter"])
                            else:
                                blockedPlacements.add((candidate["planter"], candidate["field"]))
                    
                    executedTasks.add(taskId)
                    return True
                
            if taskId == "ant_challenge":
                if macro.setdat["ant_challenge"]:
                    runTask(macro.antChallenge, resetAfter=False)
                    executedTasks.add(taskId)
                    return True
                return False
            
            # Handle feed bee actions (from quest completer)
            if taskId.startswith("feed_bee_"):
                parts = taskId.split("_")
                if len(parts) >= 3:
                    if parts[2].isdigit():
                        # feed_bee_quantity_item format
                        quantity = int(parts[2])
                        item = "_".join(parts[3:])
                    else:
                        # feed_bee_item format (quantity defaults to 1)
                        quantity = 1
                        item = "_".join(parts[2:])

                    # Convert item names
                    item_mapping = {
                        "treat": "treat",
                        "blueberry": "blueberry",
                        "strawberry": "strawberry",
                        "sunflower_seed": "sunflower seed",
                        "pineapple": "pineapple"
                    }
                    mapped_item = item_mapping.get(item, item.replace("_", " "))

                    runTask(macro.feedBee, args=(mapped_item, quantity), resetAfter=False)
                    executedTasks.add(taskId)
                    return True

            # Special priority tasks (stinger_hunt, mondo_buff, auto_field_boost) are handled after each task
            if taskId in ["stinger_hunt", "mondo_buff", "auto_field_boost"]:
                # These are handled in runTask's priority tasks section
                executedTasks.add(taskId)
                return False

            return False
        
        # Track quest task execution times to prevent spam
        questTaskCooldowns = {}

        # Execute tasks in priority order
        if priorityOrder and len(priorityOrder) > 0:
            # Keep executing tasks until no more tasks can be executed
            # This ensures mobs check all fields before moving to next task
            maxIterations = len(priorityOrder) * 10  # Safety limit to prevent infinite loops
            iteration = 0
            while iteration < maxIterations:
                iteration += 1
                anyTaskExecuted = False
                # Track which regular mob tasks we've checked in this iteration to prevent infinite loops
                regularMobTasksChecked = set()
                for taskId in priorityOrder:
                    # Skip if already executed (for non-mob tasks)
                    if taskId in executedTasks:
                        continue
                    # For regular mob kill tasks, track if we've checked them this iteration
                    # This prevents checking the same mob multiple times in one iteration
                    isRegularMobTask = taskId.startswith("kill_") and taskId.replace("kill_", "") not in ["coconut_crab", "stump_snail"]
                    if isRegularMobTask:
                        if taskId in regularMobTasksChecked:
                            continue  # Already checked this mob in this iteration
                        regularMobTasksChecked.add(taskId)
                    # Execute the task
                    taskExecuted = executeTask(taskId)
                    if taskExecuted:
                        anyTaskExecuted = True
                        # For regular mob kill tasks, don't mark as executed so they can be checked again in next iteration
                        # This allows checking all fields for the mob before moving on
                        if not isRegularMobTask:
                            executedTasks.add(taskId)
                    elif isRegularMobTask:
                        # Task couldn't be executed - mark as executed to avoid repeated attempts
                        executedTasks.add(taskId)
                    # For regular mob tasks, if we killed in any field, break to start next iteration
                    # This ensures we check all fields for the mob before moving to the next task
                    # The break causes the while loop to continue, which will re-check this mob
                    if isRegularMobTask and anyTaskExecuted:
                        break  # Break inner loop to start next iteration and re-check this mob
                # If no tasks were executed, break the loop
                if not anyTaskExecuted:
                    break
        else:
            # Fallback to old order if no priority order is set
            #collect
            for k, _ in macroModule.collectData.items():
                if macro.setdat[k] and macro.hasRespawned(k, macro.collectCooldowns[k]):
                    if k == "wreath" and not isBackpackReadyForWreath():
                        macro.logger.webhook("", "Honey Wreath ready, but backpack is not full yet. Deferring claim", "dark brown", "screen")
                        continue
                    runTask(macro.collect, args=(k,))
            
            #blender
            if macro.setdat["blender_enable"]:
                with open(settingsManager.ensureUserFile("blender.txt"), "r") as f:
                    blenderData = ast.literal_eval(f.read())
                f.close()
                if blenderData["collectTime"] > -1 and time.time() > blenderData["collectTime"]:
                    runTask(macro.blender, args=(blenderData,))

        allGatheredFields = runQuestGathers()

        # Handle planter gather fields (if not already gathered)
        if planterDataRaw:
            try:
                planterGatherFields = [x for x in normalizeManualPlanterData(ast.literal_eval(planterDataRaw))["gatherFields"] if x]
                for field in planterGatherFields:
                    if field not in allGatheredFields:
                        runTask(macro.gather, args=(field,), resetAfter=False)
                        allGatheredFields.append(field)
            except:
                pass
        # Auto-planters: if global gather flag enabled, gather each cycle for any planted fields
        try:
            # Only auto-gather when planters mode is auto and auto-harvest is enabled
            if macro.setdat.get("planters_mode") == 2:
                with open(settingsManager.ensureUserFile("auto_planters.json"), "r") as f:
                    auto_data = json.load(f)
                auto_planters = auto_data.get("planters", [])
                auto_gather = auto_data.get("gather", False)
                if auto_gather:
                    for p in auto_planters:
                        field = p.get("field", "")
                        if field and field not in allGatheredFields:
                            runTask(macro.gather, args=(field,), resetAfter=False)
                            allGatheredFields.append(field)
        except Exception:
            pass
        
        # Old code removed - all tasks now execute via priority order
        
        if taskCompleted:
            mouse.click()
        waitForReadyTask()
