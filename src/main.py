import ast
import json
import os
import subprocess
import sys
import time
from modules.misc import messageBox


def exitForMissingDependencies(message):
    script = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "install_dependencies.command"))
    try:
        if os.path.exists(script):
            subprocess.Popen(["/bin/bash", script])
        else:
            messageBox.msgBox(title="Dependencies not installed", text=message)
    except Exception:
        pass
    sys.exit(0)


try:
    # only checks that dependencies are installed
    import requests
    from modules.misc.ColorProfile import DisplayColorProfile
except ModuleNotFoundError:
    exitForMissingDependencies("Dependencies are not installed. Refer to Discord for help.")

import modules.controls.mouse as mouse
import modules.macro as macroModule
import modules.misc.settingsManager as settingsManager
from modules.controls.sleep import (
    InterruptRequested,
    INTERRUPT_NONE,
    INTERRUPT_SKIP,
    INTERRUPT_RESET,
    INTERRUPT_AFB_REROLL,
    INTERRUPT_COLLECT_PLANTER,
    INTERRUPT_STICKER_SPROUT,
)
from modules.misc.modelManager import ensure_missing_supported_models

# delete backup from previous update if pending
try:
    from modules.misc.update import delete_backup_if_pending
    delete_backup_if_pending()
except Exception:
    pass

try:
    ensure_missing_supported_models()
except Exception:
    pass

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
    
    private_server_link = macro.setdat.get("private_server_link", "")
    # Accept share links — the rejoin deeplink handler now supports the newer share link format.

    taskCompleted = True
    questCache = {}
    questScanScreens = None
    macro.questGatherInterruptMobs = {}
    macro.questGatherWatchers = {}
    macro.questTaskWatchers = {}
    macro.completedQuestWatchTasks = set()
    macro.completedQuestWatchObjectives = set()
    
    macro.start()
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
        index = int(command.get("index", -1) or -1)
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
            skipTask.value = INTERRUPT_NONE
            macro.keyboard.releaseMovement()
            mouse.mouseUp()
            interrupted_status = status.value.replace('_', ' ').title() if status.value else "Current Task"
            macro.clear_task_status()
            taskCompleted = True
            if action == INTERRUPT_SKIP:
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
                macro.setdat.get("macro_mode", "normal") not in ("quest", "alt")
                and macro.night
                and macro.setdat["stinger_hunt"]
            ):
                macro.stingerHunt()
            if (
                macro.setdat.get("macro_mode", "normal") not in ("quest", "alt")
                and macro.setdat["mondo_buff"]
                and macro.hasMondoRespawned()
            ):
                macro.collectMondoBuff()
            if macro.setdat.get("macro_mode", "normal") != "alt" and macro.hasScheduledRejoinArrived():
                macro.rejoin("Rejoining (Scheduled)")
                macro.saveTiming("rejoin_every")
            
            #auto field boost (can be disabled per-call via allowAFB)
            if allowAFB and macro.setdat["Auto_Field_Boost"] and not macro.AFBLIMIT:
                if macro.hasAFBRespawned("AFB_dice_cd", macro.setdat["AFB_rebuff"]*60) or macro.hasAFBRespawned("AFB_glitter_cd", macro.setdat["AFB_rebuff"]*60-30):
                    macro.AFB(gatherInterrupt=False)
        except InterruptRequested as interrupt:
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

    def handleQuest(questGiver, executeQuest=True):
        nonlocal questCache, questScanScreens, taskCompleted
        
        
        
        gatherFieldsList = []
        gumdropGatherFieldsList = []
        petalGatherFieldsList = []
        requireRedField = False
        requireBlueField = False
        requireField = False
        requireBlueGumdropField = False
        requireRedGumdropField = False
        feedBees = []
        setdatEnable = []

        def registerGatherWatcher(field, objective):
            """Remember which quest objective a field gather is intended to advance."""
            normalizedField = str(field).replace("_", " ").strip().lower()
            watcher = (questGiver, objective)
            watchers = macro.questGatherWatchers.setdefault(normalizedField, [])
            if watcher not in watchers:
                watchers.append(watcher)

        def registerTaskWatcher(task, objective):
            normalizedTask = str(task).replace("-", "_").replace(" ", "_").strip().lower()
            watcher = (questGiver, objective)
            watchers = macro.questTaskWatchers.setdefault(normalizedTask, [])
            if watcher not in watchers:
                watchers.append(watcher)

        def emptyQuestResult():
            return setdatEnable, gatherFieldsList, gumdropGatherFieldsList, petalGatherFieldsList, requireRedField, requireBlueField, feedBees, requireRedGumdropField, requireBlueGumdropField, requireField

        def shouldIgnoreDetectedPetalQuest():
            if not macro.setdat.get("ignore_petal_quests", False):
                return False
            title = ((getattr(macro, "_last_quest_title", {}) or {}).get(questGiver, "") or "").strip()
            if title.lower() not in HARDCODED_PETAL_IGNORE_TITLES:
                return False
            try:
                macro.logger.webhook("Skipping ignored petal quest", f"Quest: {title}", "orange")
            except Exception:
                pass
            return True

        # Refresh quest detection only when cache is stale to avoid duplicate scans in one cycle
        cacheFresh = questGiver in questCache and not taskCompleted
        if cacheFresh and questCache[questGiver] is not None:
            questObjective = questCache[questGiver]
        else:
            if not executeQuest:
                if questScanScreens is None:
                    questScanScreens = macro.captureQuestScreenshots()
                questObjective = macro.findQuest(questGiver, questScreens=questScanScreens)
            else:
                questObjective = macro.findQuest(questGiver)
            questCache[questGiver] = questObjective
            if not executeQuest:
                taskCompleted = False

        if shouldIgnoreDetectedPetalQuest():
            return emptyQuestResult()

        # Only submit/get quests if executeQuest is True (when quest appears in priority queue)
        if executeQuest:
            if questObjective is None:  # Quest does not exist -> try to claim a new quest
                if not canClaimTimedBearQuest(questGiver):
                    return emptyQuestResult()
                questObjective = macro.getNewQuest(questGiver, False)
                # Clear cached entry for this quest giver so subsequent checks re-read the UI
                if questGiver in questCache:
                    del questCache[questGiver]
            elif not len(questObjective):  # No incomplete objectives reported -> submit and get a new quest
                questObjective = macro.getNewQuest(questGiver, True)
                macro.hourlyReport.addHourlyStat("quests_completed", 1)
                # Clear cached entry for this quest giver so we don't reuse stale data
                if questGiver in questCache:
                    del questCache[questGiver]
        else:
            # If not executing, use cached quest or return empty if no quest exists or is completed
            if questObjective is None or not len(questObjective):
                # No quest found or quest completed - we're not executing, so we can't determine requirements
                # Return empty requirements (will be determined when quest executes in priority order)
                return emptyQuestResult()

        if questObjective is None: #still not able to find quest
            return emptyQuestResult()

        for obj in questObjective:
            objData = obj.split("_")
            if objData[0] == "gather":
                field_name = "_".join(objData[1:]).replace("_", " ").strip()
                if field_name:
                    gatherFieldsList.append(field_name)
                    registerGatherWatcher(field_name, obj)
            elif objData[0] == "gathergoo":
                field_name = "_".join(objData[1:]).replace("_", " ").strip()
                if macro.setdat["quest_use_gumdrops"]:
                    if field_name:
                        gumdropGatherFieldsList.append(field_name)
                        registerGatherWatcher(field_name, obj)
                else:
                    if field_name:
                        gatherFieldsList.append(field_name)
                        registerGatherWatcher(field_name, obj)
            elif objData[0] == "gatherpetal":
                field_name = "_".join(objData[1:]).replace("_", " ").strip()
                if field_name:
                    petalGatherFieldsList.append(field_name)
                    registerGatherWatcher(field_name, obj)
            elif objData[0] == "kill":
                # kill objectives can be in the form "kill_<num>_<mob>" or "kill_<mob>"
                # determine the mob name robustly
                if len(objData) >= 3 and objData[1].isdigit():
                    mob_name = "_".join(objData[2:])
                elif len(objData) >= 2:
                    mob_name = "_".join(objData[1:])
                else:
                    continue

                registerTaskWatcher(f"kill_{mob_name}", obj)

                # ants are handled via the ant challenge flow
                if "ant" in mob_name and mob_name != "mantis":
                    registerTaskWatcher("ant_challenge", obj)
                    registerTaskWatcher("collect_ant_pass_dispenser", obj)
                    if "ant_challenge" not in setdatEnable:
                        setdatEnable.append("ant_challenge")
                    if "ant_pass_dispenser" not in setdatEnable:
                        setdatEnable.append("ant_pass_dispenser")
                else:
                    # enable the mob setting (e.g. "rhinobeetle", "werewolf", etc.)
                    if mob_name not in setdatEnable:
                        setdatEnable.append(mob_name)
                    if mob_name in regularMobData:
                        macro.questGatherInterruptMobs.setdefault(questGiver, set()).add(mob_name)
            elif objData[0] == "token" and len(objData) > 1 and objData[1] == "honey":
                if "honeytoken" not in setdatEnable:
                    setdatEnable.append("honeytoken")
                registerGatherWatcher("__any__", obj)
            elif objData[0] == "token":
                if questGiver == "riley bee":
                    requireRedField = True
                    registerGatherWatcher("__red__", obj)
                elif questGiver == "bucko bee":
                    requireBlueField = True
                    registerGatherWatcher("__blue__", obj)
                else:
                    requireField = True
                    registerGatherWatcher("__any__", obj)

            elif objData[0] == "fieldtoken" and objData[1] == "blueberry":
                requireBlueField = True
                registerGatherWatcher("__blue__", obj)
            elif objData[0] == "fieldtoken" and objData[1] == "strawberry":
                requireRedField = True
                registerGatherWatcher("__red__", obj)
            elif objData[0] == "feed":
                if objData[1] == "*":
                    amount = 25
                else:
                    amount = int(objData[1])
                feedBees.append((objData[2], amount))
                registerTaskWatcher(f"feed_{objData[2]}", obj)
            elif objData[0] == "pollen" and objData[1] == "blue":
                requireBlueField = True
                registerGatherWatcher("__blue__", obj)
            elif objData[0] == "pollen" and objData[1] == "red":
                requireRedField = True
                registerGatherWatcher("__red__", obj)
            elif objData[0] == "pollen" and objData[1] == "white":
                requireField = True
                registerGatherWatcher("__any__", obj)
            elif objData[0] == "pollengoo" and objData[1] == "blue":
                if macro.setdat["quest_use_gumdrops"]:
                    requireBlueGumdropField = True
                else:
                    requireBlueField = True
                registerGatherWatcher("__blue__", obj)
            elif objData[0] == "pollengoo" and objData[1] == "red":
                if macro.setdat["quest_use_gumdrops"]:
                    requireRedGumdropField = True
                else:
                    requireRedField = True
                registerGatherWatcher("__red__", obj)
            elif objData[0] == "pollengoo" and objData[1] == "white":
                if macro.setdat["quest_use_gumdrops"]:
                    requireBlueGumdropField = True
                else:
                    requireField = True
                registerGatherWatcher("__any__", obj)
            elif objData[0] == "collect":
                collectTask = objData[1].replace("-", "_")
                setdatEnable.append(collectTask)
                registerTaskWatcher(f"collect_{collectTask}", obj)

        return setdatEnable, gatherFieldsList, gumdropGatherFieldsList, petalGatherFieldsList, requireRedField, requireBlueField, feedBees, requireRedGumdropField, requireBlueGumdropField, requireField

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

    def bloomsAIQuestOverride(baseOverride=None):
        override = dict(baseOverride or {})
        override["shape"] = "blooms_ai"
        override["start_location"] = "center"
        override["shift_lock"] = False
        return override

    def questAIFieldCenterOverride(field, baseOverride=None):
        override = dict(baseOverride or {})
        normalized_field = field.replace("_", " ")
        fieldSetting = {**macro.fieldSettings.get(normalized_field, {}), **override}
        if fieldSetting.get("shape") in ("blooms_ai", "fuzzy_ai_gather"):
            override["start_location"] = "center"
            override["shift_lock"] = False
        return override

    #macro.rejoin()
    # Cache settings to avoid reloading on every iteration
    settings_cache = {}
    last_settings_load = 0
    settings_cache_duration = 0.5  # Reload settings every 0.5 seconds max
    
    def get_cached_settings():
        nonlocal settings_cache, last_settings_load
        current_time = time.time()
        if current_time - last_settings_load > settings_cache_duration:
            settings_cache = settingsManager.loadAllSettings()
            last_settings_load = current_time
        return settings_cache

    def get_task_list_order(settings):
        task_list = settings.get("task_list", None)
        if isinstance(task_list, list):
            return task_list
        task_queue = settings.get("task_queue", None)
        if isinstance(task_queue, list):
            return task_queue
        return settings.get("task_priority_order", [])

    def getQuestGatherOverrides(questName):
        questKeyPrefix = questName.replace(" ", "_")
        questMinsKey = f"{questKeyPrefix}_quest_gather_mins"
        questReturnKey = f"{questKeyPrefix}_quest_gather_return"

        overrides = {}
        mins = macro.setdat.get(questMinsKey, macro.setdat.get("quest_gather_mins", 0))
        returnToHive = macro.setdat.get(questReturnKey, macro.setdat.get("quest_gather_return", "no override"))

        if mins:
            overrides["mins"] = mins
        if returnToHive != "no override":
            overrides["return"] = returnToHive
        return overrides

    def getPetalQuestGatherOverrides(questName):
        overrides = getQuestGatherOverrides(questName)
        mins = macro.setdat.get("petal_quest_gather_mins", 0)
        returnToHive = macro.setdat.get("petal_quest_gather_return", "no override")

        if mins:
            overrides["mins"] = mins
        if returnToHive != "no override":
            overrides["return"] = returnToHive
        return overrides
    
    while True:
        # Check for pause - wait while paused
        while run.value == 6:  # 6 = paused
            time.sleep(0.1)  # Wait while paused
        # Check if stop was requested while paused
        if run.value == 0:
            break  # Exit macro loop if stop requested

        # Quest scans should be cached only within a single outer loop pass.
        # Clearing here guarantees the board is re-read after the task list recycles.
        questCache.clear()
        questScanScreens = None
        macro.questGatherInterruptMobs.clear()
        macro.questGatherWatchers.clear()
        macro.questTaskWatchers.clear()
        macro.completedQuestWatchTasks.clear()
        macro.completedQuestWatchObjectives.clear()
        
        macro.setdat = get_cached_settings()
        # Check if profile has changed and reload settings if needed
        macro.checkAndReloadSettings()

        # Migration from old boolean flags to macro_mode is now handled in settings loader

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

        # Check if quest-only mode is enabled
        if macro.setdat.get("macro_mode", "normal") == "quest":
            # Quest-only mode: skip all tasks except quest-related tasks
            # Initialize quest-related variables
            questGatherFields = []
            questGumdropGatherFields = []
            questPetalGatherFields = []
            questGatherFieldOverrides = {}
            questGumdropFieldOverrides = {}
            questPetalGatherFieldOverrides = {}
            redFieldNeeded = False
            blueFieldNeeded = False
            fieldNeeded = False
            itemsToFeedBees = []
            redGumdropFieldNeeded = False
            blueGumdropFieldNeeded = False
            redFieldOverride = {}
            blueFieldOverride = {}
            redGumdropFieldOverride = {}
            blueGumdropFieldOverride = {}
            defaultQuestFieldOverride = {}

            # Get priority order and filter to only include quest tasks
            priorityOrder = get_task_list_order(macro.setdat)
            executedTasks = set()

            # Filter priority order to only include quest tasks
            questOnlyTasks = []
            for taskId in priorityOrder:
                if taskId.startswith("quest_"):
                    questOnlyTasks.append(taskId)

            # If no quest tasks are in priority order, add all enabled quests
            if not questOnlyTasks:
                questMappings = [
                    ("polar bear", "polar_bear_quest"),
                    ("brown bear", "brown_bear_quest"),
                    ("black bear", "black_bear_quest"),
                    ("honey bee", "honey_bee_quest"),
                    ("bucko bee", "bucko_bee_quest"),
                    ("riley bee", "riley_bee_quest")
                ]
                for questName, questKey in questMappings:
                    if macro.setdat.get(questKey):
                        questOnlyTasks.append(f"quest_{questName.replace(' ', '_')}")

            # Execute quest tasks in priority order
            for taskId in questOnlyTasks:
                if taskId.startswith("quest_"):
                    questName = taskId.replace("quest_", "").replace("_", " ")
                    questKey = f"{questName.replace(' ', '_')}_quest"
                    if macro.setdat.get(questKey):
                        # If this is a timed bear quest, skip checking while on cooldown
                        if questName in ["brown bear", "black bear"]:
                            if not canClaimTimedBearQuest(questName):
                                executedTasks.add(taskId)
                                continue

                        # Handle quest feeding and gathering requirements
                        questMappings = {
                            "polar bear": "polar_bear_quest",
                            "brown bear": "brown_bear_quest",
                            "black bear": "black_bear_quest",
                            "honey bee": "honey_bee_quest",
                            "bucko bee": "bucko_bee_quest",
                            "riley bee": "riley_bee_quest"
                        }

                        if questName in questMappings:
                            enabledKey = questMappings[questName]
                            if macro.setdat.get(enabledKey):
                                # For timed bears, ensure we don't attempt to claim/check while on cooldown
                                if questName in ["brown bear", "black bear"]:
                                    if not canClaimTimedBearQuest(questName):
                                        # still on cooldown; skip applying requirements this cycle
                                        pass
                                    else:
                                        setdatEnable, gatherFields, gumdropFields, petalGatherFields, needsRed, needsBlue, feedBees, needsRedGumdrop, needsBlueGumdrop, needsField = handleQuest(questName)
                                else:
                                    setdatEnable, gatherFields, gumdropFields, petalGatherFields, needsRed, needsBlue, feedBees, needsRedGumdrop, needsBlueGumdrop, needsField = handleQuest(questName)
                                questGatherOverrides = getQuestGatherOverrides(questName)
                                petalQuestGatherOverrides = getPetalQuestGatherOverrides(questName)
                                for k in setdatEnable:
                                    macro.setdat[k] = True
                                runQuestSupportTasks(setdatEnable)
                                for field in gatherFields:
                                    questGatherFields.append(field)
                                    if field not in questGatherFieldOverrides:
                                        questGatherFieldOverrides[field] = dict(questGatherOverrides)
                                for field in gumdropFields:
                                    questGumdropGatherFields.append(field)
                                    if field not in questGumdropFieldOverrides:
                                        questGumdropFieldOverrides[field] = dict(questGatherOverrides)
                                for field in petalGatherFields:
                                    questPetalGatherFields.append(field)
                                    if field not in questPetalGatherFieldOverrides:
                                        questPetalGatherFieldOverrides[field] = dict(petalQuestGatherOverrides)
                                redFieldNeeded = redFieldNeeded or needsRed
                                blueFieldNeeded = blueFieldNeeded or needsBlue
                                itemsToFeedBees.extend(feedBees)
                                redGumdropFieldNeeded = redGumdropFieldNeeded or needsRedGumdrop
                                blueGumdropFieldNeeded = blueGumdropFieldNeeded or needsBlueGumdrop
                                fieldNeeded = fieldNeeded or needsField
                                if needsRed and not redFieldOverride:
                                    redFieldOverride = dict(questGatherOverrides)
                                if needsBlue and not blueFieldOverride:
                                    blueFieldOverride = dict(questGatherOverrides)
                                if needsRedGumdrop and not redGumdropFieldOverride:
                                    redGumdropFieldOverride = dict(questGatherOverrides)
                                if needsBlueGumdrop and not blueGumdropFieldOverride:
                                    blueGumdropFieldOverride = dict(questGatherOverrides)
                                if needsField and not defaultQuestFieldOverride:
                                    defaultQuestFieldOverride = dict(questGatherOverrides)

                        if taskId not in executedTasks:
                            executedTasks.add(taskId)

            # Feed bees for quests (done once per cycle)
            for item, quantity in itemsToFeedBees:
                runTask(macro.feedBee, args=(item, quantity), resetAfter=False)
                taskCompleted = True

            allGatheredFields = []

            # Handle gumdrop gather fields first
            if blueGumdropFieldNeeded:
                blueFields = ["blue flower", "bamboo", "pine tree", "stump"]
                for f in blueFields:
                    if f in questGumdropGatherFields:
                        break
                else:
                    questGumdropGatherFields.append("pine tree")
                    questGumdropFieldOverrides["pine tree"] = dict(blueGumdropFieldOverride)

            if redGumdropFieldNeeded:
                redFields = ["mushroom", "strawberry", "rose", "pepper"]
                for f in redFields:
                    if f in questGumdropGatherFields:
                        break
                else:
                    questGumdropGatherFields.append("rose")
                    questGumdropFieldOverrides["rose"] = dict(redGumdropFieldOverride)

            for field in questGumdropGatherFields:
                if field not in allGatheredFields:
                    runTask(macro.gather, args=(field, questAIFieldCenterOverride(field, questGumdropFieldOverrides.get(field, {})), True), resetAfter=False)
                    allGatheredFields.append(field)

            # Handle regular quest gather fields
            questGatherFields = [x for x in questGatherFields if not (x in allGatheredFields)]
            for field in questGatherFields:
                runTask(macro.gather, args=(field, questAIFieldCenterOverride(field, questGatherFieldOverrides.get(field, {}))), resetAfter=False)
                allGatheredFields.append(field)

            questPetalGatherFields = [x for x in questPetalGatherFields if not (x in allGatheredFields)]
            for field in questPetalGatherFields:
                runTask(macro.gather, args=(field, bloomsAIQuestOverride(questPetalGatherFieldOverrides.get(field, {}))), resetAfter=False)
                allGatheredFields.append(field)

            # Handle required blue/red fields for quests
            blueFields = ["blue flower", "bamboo", "pine tree", "stump"]
            redFields = ["mushroom", "strawberry", "rose", "pepper"]

            if blueFieldNeeded:
                for f in blueFields:
                    if f in allGatheredFields:
                        break
                else:
                    field = "pine tree"
                    allGatheredFields.append(field)
                    runTask(macro.gather, args=(field, questAIFieldCenterOverride(field, blueFieldOverride)), resetAfter=False)

            if redFieldNeeded:
                for f in redFields:
                    if f in allGatheredFields:
                        break
                else:
                    field = "rose"
                    allGatheredFields.append(field)
                    runTask(macro.gather, args=(field, questAIFieldCenterOverride(field, redFieldOverride)), resetAfter=False)

            if fieldNeeded and not allGatheredFields:
                if defaultQuestFieldOverride:
                    runTask(macro.gather, args=("pine tree", questAIFieldCenterOverride("pine tree", defaultQuestFieldOverride)), resetAfter=False)
                else:
                    runTask(macro.gather, args=("pine tree", questAIFieldCenterOverride("pine tree")), resetAfter=False)

            # Skip to next iteration
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
                    if macro.setdat["coconut_crab"] and macro.hasRespawned("coconut_crab", 36*60*60, applyMobRespawnBonus=True):
                        runTask(macro.coconutCrab)
                        executedTasks.add(taskId)
                    continue

                if mob == "king_beetle":
                    if macro.setdat["king_beetle"] and macro.hasRespawned("king_beetle", 24*60*60, applyMobRespawnBonus=True):
                        runTask(macro.kingBeetle)
                        executedTasks.add(taskId)
                    continue

                if mob == "tunnel_bear":
                    if macro.setdat["tunnel_bear"] and macro.hasRespawned("tunnel_bear", 48*60*60, applyMobRespawnBonus=True):
                        runTask(macro.tunnelBear)
                        executedTasks.add(taskId)
                    continue

                if mob == "stump_snail":
                    if macro.setdat["stump_snail"] and macro.hasRespawned("stump_snail", 96*60*60, applyMobRespawnBonus=True):
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

            # Skip to next iteration
            continue

        # Check quest requirements for ALL enabled quests (needed for quest-related gathering fields)
        # But only feed bees for quests that appear in priority queue order
        questGatherFields = []
        questGumdropGatherFields = []
        questPetalGatherFields = []
        questGatherFieldOverrides = {}
        questGumdropFieldOverrides = {}
        questPetalGatherFieldOverrides = {}
        redFieldNeeded = False
        blueFieldNeeded = False
        fieldNeeded = False
        itemsToFeedBees = []
        redGumdropFieldNeeded = False
        blueGumdropFieldNeeded = False
        redFieldOverride = {}
        blueFieldOverride = {}
        redGumdropFieldOverride = {}
        blueGumdropFieldOverride = {}
        defaultQuestFieldOverride = {}
        
        # Track which quests have been executed in priority order (for feeding bees)
        executedQuests = set()
        
        # Store quest feed requirements per quest (to feed only when quest appears in priority)
        questFeedRequirements = {}

        # Check ALL enabled quests for requirements (to know what fields might be needed)
        # But don't execute quests (submit/get) - that will happen when quest appears in priority queue
        for questName, enabledKey in [
            ("polar bear", "polar_bear_quest"),
            ("brown bear", "brown_bear_quest"),
            ("black bear", "black_bear_quest"),
            ("honey bee", "honey_bee_quest"),
            ("bucko bee", "bucko_bee_quest"),
            ("riley bee", "riley_bee_quest")
        ]:
            if macro.setdat.get(enabledKey):
                # If this is a timed bear quest, skip requirement check while on cooldown
                if questName in ["brown bear", "black bear"]:
                    if not canClaimTimedBearQuest(questName):
                        continue

                # Check requirements without executing (submit/get) the quest
                setdatEnable, gatherFields, gumdropFields, petalGatherFields, needsRed, needsBlue, feedBees, needsRedGumdrop, needsBlueGumdrop, needsField = handleQuest(questName, executeQuest=False)
                # Enable any required settings
                for k in setdatEnable:
                    macro.setdat[k] = True
                questGatherOverrides = getQuestGatherOverrides(questName)
                petalQuestGatherOverrides = getPetalQuestGatherOverrides(questName)
                # Store gather fields (will be used after priority queue)
                for field in gatherFields:
                    questGatherFields.append(field)
                    if field not in questGatherFieldOverrides:
                        questGatherFieldOverrides[field] = dict(questGatherOverrides)
                for field in gumdropFields:
                    questGumdropGatherFields.append(field)
                    if field not in questGumdropFieldOverrides:
                        questGumdropFieldOverrides[field] = dict(questGatherOverrides)
                for field in petalGatherFields:
                    questPetalGatherFields.append(field)
                    if field not in questPetalGatherFieldOverrides:
                        questPetalGatherFieldOverrides[field] = dict(petalQuestGatherOverrides)
                redFieldNeeded = redFieldNeeded or needsRed
                blueFieldNeeded = blueFieldNeeded or needsBlue
                redGumdropFieldNeeded = redGumdropFieldNeeded or needsRedGumdrop
                blueGumdropFieldNeeded = blueGumdropFieldNeeded or needsBlueGumdrop
                fieldNeeded = fieldNeeded or needsField
                if needsRed and not redFieldOverride:
                    redFieldOverride = dict(questGatherOverrides)
                if needsBlue and not blueFieldOverride:
                    blueFieldOverride = dict(questGatherOverrides)
                if needsRedGumdrop and not redGumdropFieldOverride:
                    redGumdropFieldOverride = dict(questGatherOverrides)
                if needsBlueGumdrop and not blueGumdropFieldOverride:
                    blueGumdropFieldOverride = dict(questGatherOverrides)
                if needsField and not defaultQuestFieldOverride:
                    defaultQuestFieldOverride = dict(questGatherOverrides)
                # Store feed requirements (will be used when quest appears in priority queue)
                questFeedRequirements[questName] = feedBees
        
                    
        taskCompleted = False

        # A quest-mob gather interrupt discovered above must run before any quest
        # or gather task begins. Otherwise gathering starts only to be interrupted
        # on its first cycle by a mob that was already known to be ready.
        runReadyQuestInterruptMobs()

        # Quest completer feature removed. Quest-giver handling and brown bear logic remain.

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
            
            # Handle quest tasks - execute quest (submit/get) and feed bees when quest appears in priority order
            if taskId.startswith("quest_"):
                questName = taskId.replace("quest_", "").replace("_", " ")
                questKey = f"{questName.replace(' ', '_')}_quest"
                # If the quest setting is disabled, skip any UI scanning for this quest
                if not macro.setdat.get(questKey):
                    return False
                # If this is a timed bear quest, skip while on cooldown
                if questName in ["brown bear", "black bear"]:
                    if not canClaimTimedBearQuest(questName):
                        executedTasks.add(taskId)
                        return False
                # Actually execute the quest (submit/get) - this will travel to quest giver if needed
                # For Brown Bear, capture the objectives and gather them immediately
                if questName == "brown bear":
                    setdatEnable, gatherFields, gumdropFields, petalGatherFields, needsRed, needsBlue, feedBees, needsRedGumdrop, needsBlueGumdrop, needsField = handleQuest(questName, executeQuest=True)
                    
                    # Gather the fields for this quest
                    questGatherOverrides = getQuestGatherOverrides(questName)
                    petalQuestGatherOverrides = getPetalQuestGatherOverrides(questName)
                    
                    # Gather regular fields
                    for field in gatherFields:
                        runTask(macro.gather, args=(field, questAIFieldCenterOverride(field, questGatherOverrides)), resetAfter=False)
                    
                    # Gather gumdrop fields (if any)
                    for field in gumdropFields:
                        runTask(macro.gather, args=(field, questAIFieldCenterOverride(field, questGatherOverrides), True), resetAfter=False)

                    # Gather bloom-petal fields using BloomsAI
                    for field in petalGatherFields:
                        runTask(macro.gather, args=(field, bloomsAIQuestOverride(petalQuestGatherOverrides)), resetAfter=False)
                    
                    # Feed bees if needed
                    for item, quantity in feedBees:
                        runTask(macro.feedBee, args=(item, quantity), resetAfter=False)
                        taskCompleted = True
                else:
                    handleQuest(questName, executeQuest=True)
                    
                    # Feed bees for this quest (requirements were already checked above)
                    if questName in questFeedRequirements:
                        feedBees = questFeedRequirements[questName]
                        for item, quantity in feedBees:
                            runTask(macro.feedBee, args=(item, quantity), resetAfter=False)
                            taskCompleted = True
                
                executedTasks.add(taskId)
                executedQuests.add(questName)
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
                    if macro.setdat["coconut_crab"] and macro.hasRespawned("coconut_crab", 36*60*60, applyMobRespawnBonus=True):
                        runTask(macro.coconutCrab)
                        executedTasks.add(taskId)
                        return True
                    return False
                

                # King Beetle respawns every 24 hours (20 hours 24 minutes with Gifted Vicious Bee)
                if mob == "king_beetle":
                    if macro.setdat["king_beetle"] and macro.hasRespawned("king_beetle", 24*60*60, applyMobRespawnBonus=True):
                        runTask(macro.kingBeetle)
                        executedTasks.add(taskId)
                        return True
                    return False

                # Tunnel Bear respawns every 48 hours (40 hours 48 minutes with Gifted Vicious Bee)
                if mob == "tunnel_bear":
                    if macro.setdat["tunnel_bear"] and macro.hasRespawned("tunnel_bear", 48*60*60, applyMobRespawnBonus=True):
                        runTask(macro.tunnelBear)
                        executedTasks.add(taskId)
                        return True
                    return False
                
                if mob == "stump_snail":
                    if macro.setdat["stump_snail"] and macro.hasRespawned("stump_snail", 96*60*60, applyMobRespawnBonus=True):
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
                if fieldName in questGatherFields or fieldName in questGumdropGatherFields or fieldName in questPetalGatherFields:
                    return False
                
                # Check if this field is enabled in gather tab
                for i in range(len(macro.setdat["fields_enabled"])):
                    if macro.setdat["fields_enabled"][i] and macro.setdat["fields"][i] == fieldName:
                        runTask(macro.gather, args=(fieldName,), resetAfter=False)
                        executedTasks.add(taskId)
                        return True
                
                return False

            if taskId.startswith("gatherpetal_"):
                fieldName = taskId.replace("gatherpetal_", "").replace("_", " ")
                if fieldName in questPetalGatherFields:
                    runTask(macro.gather, args=(fieldName, bloomsAIQuestOverride(questPetalGatherFieldOverrides.get(fieldName, {}))), resetAfter=False)
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
                        else:
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
            
            #blender
            if macro.setdat["blender_enable"]:
                with open(settingsManager.ensureUserFile("blender.txt"), "r") as f:
                    blenderData = ast.literal_eval(f.read())
                f.close()
                if blenderData["collectTime"] > -1 and time.time() > blenderData["collectTime"]:
                    runTask(macro.blender, args=(blenderData,))

        # Handle quest gather fields and required fields that weren't executed in priority order
        # These need to be handled separately as they depend on quest requirements
        blueFields = ["blue flower", "bamboo", "pine tree", "stump"]
        redFields = ["mushroom", "strawberry", "rose", "pepper"]
        
        # Track all gathered fields to avoid duplicates
        allGatheredFields = []
        
        # Handle gumdrop gather fields first
        if blueGumdropFieldNeeded:
            for f in blueFields:
                if f in questGumdropGatherFields:
                    break
            else:
                questGumdropGatherFields.append("pine tree")
                questGumdropFieldOverrides["pine tree"] = dict(blueGumdropFieldOverride)
        
        if redGumdropFieldNeeded:
            for f in redFields:
                if f in questGumdropGatherFields:
                    break
            else:
                questGumdropGatherFields.append("rose")
                questGumdropFieldOverrides["rose"] = dict(redGumdropFieldOverride)

        for field in questGumdropGatherFields:
            if field not in allGatheredFields:
                runTask(macro.gather, args=(field, questAIFieldCenterOverride(field, questGumdropFieldOverrides.get(field, {})), True), resetAfter=False)
                allGatheredFields.append(field)

        # Handle regular quest gather fields
        questGatherFields = [x for x in questGatherFields if not (x in allGatheredFields)]
        for field in questGatherFields:
            runTask(macro.gather, args=(field, questAIFieldCenterOverride(field, questGatherFieldOverrides.get(field, {}))), resetAfter=False)
            allGatheredFields.append(field)

        questPetalGatherFields = [x for x in questPetalGatherFields if not (x in allGatheredFields)]
        for field in questPetalGatherFields:
            runTask(macro.gather, args=(field, bloomsAIQuestOverride(questPetalGatherFieldOverrides.get(field, {}))), resetAfter=False)
            allGatheredFields.append(field)

        # Handle required blue/red fields for quests
        if blueFieldNeeded:
            for f in blueFields:
                if f in allGatheredFields:
                    break
            else:
                field = "pine tree"
                allGatheredFields.append(field)
                runTask(macro.gather, args=(field, questAIFieldCenterOverride(field, blueFieldOverride)), resetAfter=False)
        
        if redFieldNeeded:
            for f in redFields:
                if f in allGatheredFields:
                    break
            else:
                field = "rose"
                allGatheredFields.append(field)
                runTask(macro.gather, args=(field, questAIFieldCenterOverride(field, redFieldOverride)), resetAfter=False)
        
        if fieldNeeded and not allGatheredFields:
            if defaultQuestFieldOverride:
                runTask(macro.gather, args=("pine tree", questAIFieldCenterOverride("pine tree", defaultQuestFieldOverride)), resetAfter=False)
            else:
                runTask(macro.gather, args=("pine tree", questAIFieldCenterOverride("pine tree")), resetAfter=False)
        
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
        
        mouse.click()


if __name__ == "__main__":
    from modules.app import runApp

    runApp(macro)
