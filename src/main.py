from modules.misc import messageBox
#check if installing dependencies was ran
try:
    import requests
except ModuleNotFoundError:
    try:
        script = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "install_dependencies.command"))
        if os.path.exists(script):
            subprocess.Popen(["/bin/bash", script])
        else:
            messageBox.msgBox(title="Dependencies not installed", text="Dependencies are not installed. Refer to Discord for help.")
    except Exception:
        pass
    sys.exit(0)
from pynput import keyboard
import multiprocessing
import ctypes
from threading import Thread
import eel
import time
import sys
import os
import ast
import subprocess
import atexit
from modules.misc.imageManipulation import adjustImage
from modules.screen.imageSearch import locateImageOnScreen
import pyautogui as pag
from modules.misc.appManager import getWindowSize
import traceback
import modules.misc.settingsManager as settingsManager
import modules.macro as macroModule
import modules.controls.mouse as mouse
import json
from modules.controls.sleep import (
    InterruptRequested,
    INTERRUPT_NONE,
    INTERRUPT_SKIP,
    INTERRUPT_RESET,
)
# delete backup from previous update if pending
try:
    from modules.misc.update import delete_backup_if_pending
    delete_backup_if_pending()
except Exception:
    pass

try:
	from modules.misc.ColorProfile import DisplayColorProfile
except ModuleNotFoundError:
    try:
        script = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "install_dependencies.command"))
        if os.path.exists(script):
            subprocess.Popen(["/bin/bash", script])
        else:
            messageBox.msgBox(title="Dependencies not installed", text="The new update requires new dependencies. Refer to Discord for help.")
    except Exception:
        pass
    quit()
from modules.submacros.hourlyReport import HourlyReport
mw, mh = pag.size()

# Hardcoded petal quest titles to ignore (lowercase)
HARDCODED_PETAL_IGNORE_TITLES = {"petal tabbouleh", "petals", "mashed blooms"}

# Discord Rich Presence Manager
try:
    from pypresence import Presence, exceptions as pypresence_exceptions
    PYPRESENCE_AVAILABLE = True
except ImportError:
    PYPRESENCE_AVAILABLE = False
    print("pypresence not installed - Discord Rich Presence will not be available")

class RichPresenceManager:
    """Manages Discord Rich Presence updates based on macro status"""
    
    # Hardcoded Application ID for Fuzzy Macro
    DISCORD_APP_ID = "1468035015194710068"
    
    def __init__(self, status_value, enabled: bool = False, presence_value=None):
        """
        Initialize Rich Presence Manager
        
        Args:
            status_value: Shared multiprocessing.Value containing current macro status
            enabled: Whether Rich Presence is enabled
            presence_value: Optional shared Value for rich presence overrides
        """
        self.application_id = self.DISCORD_APP_ID
        self.status = status_value
        self.presence = presence_value
        self.enabled = enabled
        self.rpc = None
        self.last_activity = ""
        self.connected = False
        self.running = False
        self.thread = None
        self.start_time = int(time.time())
        
        # Load external mapping file for presence (if present)
        self.map = {}
        map_candidates = [
            os.path.join(os.path.dirname(__file__), "modules", "discord_bot", "rich_presence_map.json")
        ]
        for mp in map_candidates:
            try:
                if os.path.exists(mp):
                    with open(mp, "r") as f:
                        self.map = json.load(f)
                    break
            except Exception:
                continue

        # Build asset lookup mapping from provided assets and sensible defaults
        asset_mapping = {}
        # Known quest NPCs
        asset_mapping.update({
            "polar_bear": "polar_bear",
            "polar bear": "polar_bear",
            "brown_bear": "brown_bear",
            "brown bear": "brown_bear",
            "black_bear": "black_bear",
            "black bear": "black_bear",
            "honey_bee": "honey_bee",
            "honey bee": "honey_bee",
            "bucko_bee": "bucko_bee",
            "bucko bee": "bucko_bee",
            "riley_bee": "riley_bee",
            "riley bee": "riley_bee",
        })
        # Add assets lists from the map (if present)
        assets_section = self.map.get("assets", {})
        for group, lst in assets_section.items():
            for name in lst:
                key = name.replace(" ", "_")
                asset_mapping[key] = key
                asset_mapping[name] = key

        # Allow optional explicit lookup section
        explicit = self.map.get("asset_lookup", {}) or {}
        for k, v in explicit.items():
            asset_mapping[k] = v

        self.asset_mapping = asset_mapping
        
    def connect(self) -> bool:
        """Initialize Discord RPC connection"""
        if not PYPRESENCE_AVAILABLE:
            return False
            
        if not self.application_id or self.application_id == "":
            return False
            
        try:
            self.rpc = Presence(self.application_id)
            self.rpc.connect()
            self.connected = True
            print(f"Discord Rich Presence connected")
            return True
        except Exception as e:
            # Silently fail if Discord client isn't running
            self.connected = False
            return False
    
    def disconnect(self):
        """Close Discord RPC connection"""
        if self.rpc and self.connected:
            try:
                # Try to clear presence first (if supported) to remove lingering status
                try:
                    if hasattr(self.rpc, "clear"):
                        self.rpc.clear()
                except Exception:
                    pass
                # Close the RPC connection
                try:
                    self.rpc.close()
                except Exception:
                    pass
            finally:
                self.connected = False
                self.rpc = None
                print("Discord Rich Presence disconnected")
    
    def parse_activity(self, status_str: str) -> dict:
        """Parse status string into Rich Presence data"""
        payload_overrides = {}
        if isinstance(status_str, str) and status_str.startswith("rp:"):
            try:
                payload = json.loads(status_str[3:])
            except Exception:
                payload = {}
            for key in ("state", "details", "large_image", "large_text", "small_image", "small_text"):
                if key in payload:
                    payload_overrides[key] = payload[key]
            status_str = payload.get("activity") or payload.get("status") or payload.get("key")
            task = payload.get("task")
            field = payload.get("field")
            if not status_str and task:
                if field:
                    field_key = str(field).replace(" ", "_").lower()
                    status_str = f"{task}_{field_key}"
                else:
                    status_str = str(task)

        # Treat empty, whitespace-only, or explicit 'none' values as idle
        if not status_str or (isinstance(status_str, str) and status_str.strip().lower() in ("", "none")):
            status_str = "idle_main_menu"
        
        status_lower = str(status_str).lower()

        # exact matches from map (use lowercase keys for safety)
        exact = {k.lower(): v for k, v in self.map.get("exact", {}).items()}
        if status_lower in exact:
            activity = exact[status_lower]
            if payload_overrides:
                merged = dict(activity)
                merged.update({k: v for k, v in payload_overrides.items() if v is not None})
                if merged.get("small_image") == "":
                    merged["small_image"] = None
                if merged.get("small_text") == "":
                    merged["small_text"] = None
                return merged
            return activity

        # prefix matches
        prefix_map = self.map.get("prefix", {})
        for pfx, data in prefix_map.items():
            if status_lower.startswith(pfx.lower()):
                key = status_lower[len(pfx):]
                field = key.replace("_", " ").title()
                payload = dict(data)
                # substitute placeholders
                payload["state"] = payload["state"].replace("{field}", field).replace("{key}", key)
                payload["details"] = payload.get("details", "").replace("{field}", field).replace("{key}", key)
                payload["small_text"] = payload.get("small_text", "").replace("{field}", field).replace("{key}", key)
                # handle small image key patterns
                small_image = payload.get("small_image") or ""
                if "{asset}" in small_image:
                    asset = self.asset_mapping.get(key, None) or key
                    small_image = small_image.replace("{asset}", asset)
                if "{key}" in small_image:
                    small_image = small_image.replace("{key}", key)
                payload["small_image"] = small_image if small_image else None
                if payload_overrides:
                    payload.update({k: v for k, v in payload_overrides.items() if v is not None})
                    if payload.get("small_image") == "":
                        payload["small_image"] = None
                    if payload.get("small_text") == "":
                        payload["small_text"] = None
                return payload

        # contains rules - check in order of specificity
        contains = self.map.get("contains", {})
        for substring, data in contains.items():
            if substring in status_lower:
                activity = data
                if payload_overrides:
                    merged = dict(activity)
                    merged.update({k: v for k, v in payload_overrides.items() if v is not None})
                    if merged.get("small_image") == "":
                        merged["small_image"] = None
                    if merged.get("small_text") == "":
                        merged["small_text"] = None
                    return merged
                return activity

        # fallback to default
        default = self.map.get("default")
        if default:
            activity = default
            if payload_overrides:
                merged = dict(activity)
                merged.update({k: v for k, v in payload_overrides.items() if v is not None})
                if merged.get("small_image") == "":
                    merged["small_image"] = None
                if merged.get("small_text") == "":
                    merged["small_text"] = None
                return merged
            return activity

        # final fallback if no map is loaded
        activity = {
            "state": str(status_str).replace("_", " ").title(),
            "details": "Macro active",
            "large_image": "fuzzy_macro",
            "large_text": "Fuzzy Macro",
            "small_image": None,
            "small_text": None,
        }
        if payload_overrides:
            activity.update({k: v for k, v in payload_overrides.items() if v is not None})
            if activity.get("small_image") == "":
                activity["small_image"] = None
            if activity.get("small_text") == "":
                activity["small_text"] = None
        return activity
    
    def update_presence(self, activity_data: dict):
        """Update Discord Rich Presence with new activity data"""
        if not self.connected or not self.rpc:
            return
        
        try:
            # Build presence payload
            payload = {
                "state": activity_data["state"],
                "details": activity_data["details"],
                "large_image": activity_data["large_image"],
                "large_text": activity_data["large_text"],
                "start": self.start_time,
            }
            
            # Add small image if available
            if activity_data["small_image"]:
                payload["small_image"] = activity_data["small_image"]
                payload["small_text"] = activity_data["small_text"]
            
            self.rpc.update(**payload)
        except Exception as e:
            # Silently handle errors (e.g., Discord closed)
            self.connected = False
    
    def update_loop(self):
        """Background thread to monitor status and update RPC"""
        while self.running:
            try:
                # Check if enabled
                if not self.enabled:
                    if self.connected:
                        self.disconnect()
                    time.sleep(2)
                    continue
                
                # Try to connect if not connected
                if not self.connected:
                    self.connect()
                    time.sleep(2)
                    continue
                
                # Get current status (presence overrides status when available)
                presence_status = ""
                if self.presence is not None:
                    try:
                        presence_status = self.presence.value
                    except Exception:
                        presence_status = ""

                if presence_status and str(presence_status).strip().lower() not in ("", "none"):
                    current_status = presence_status
                else:
                    current_status = self.status.value
                
                # Update if status changed
                if current_status != self.last_activity:
                    activity_data = self.parse_activity(current_status)
                    self.update_presence(activity_data)
                    self.last_activity = current_status
                
                time.sleep(1)  # Check every second
            except Exception as e:
                # Silently handle any errors
                time.sleep(2)
    
    def start(self):
        """Start the Rich Presence update thread"""
        if self.running:
            return
        
        if not PYPRESENCE_AVAILABLE:
            return
        
        self.running = True
        self.thread = Thread(target=self.update_loop, daemon=True)
        self.thread.start()
    
    def stop(self):
        """Stop the Rich Presence update thread"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        # Disconnect and give Discord a moment to clear presence
        self.disconnect()
        try:
            time.sleep(0.2)
        except Exception:
            pass

    def set_enabled(self, enabled: bool):
        """Enable or disable Rich Presence"""
        self.enabled = enabled
        if not enabled and self.connected:
            self.disconnect()

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
        timings = settingsManager.readSettingsFile("./data/user/timings.txt") or {}
    except Exception:
        timings = {}
    # Ensure both bear quest state keys exist in the timings file with a default of 0
    try:
        for required_state in ("brown_bear_quest_state", "black_bear_quest_state"):
            if required_state not in timings:
                try:
                    settingsManager.saveSettingFile(required_state, 0, "./data/user/timings.txt")
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
            settingsManager.saveSettingFile(state_key, 0, "./data/user/timings.txt")
            return True
        # If timer expired, reset state and allow claiming
        if time.time() - timing >= 60 * 60:
            settingsManager.saveSettingFile(state_key, 0, "./data/user/timings.txt")
            return True
        return False
    # state == 0 -> allow claiming
    return True
    
# (set_enabled moved into RichPresenceManager class)
#controller for the macro
def macro(status, logQueue, updateGUI, run, skipTask, presence=None):
    macro = macroModule.macro(status, logQueue, updateGUI, run, skipTask, presence)
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
    
    macro.start()
    #macro.useItemInInventory("blueclayplanter")
    #function to run a task
    #makes it easy to do any checks after a task is complete (like stinger hunt, rejoin every, etc)
    def runTask(func = None, args = (), resetAfter = True, convertAfter = True, allowAFB = True):
        nonlocal taskCompleted

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
            macro.reset(convert=True)
            if action == INTERRUPT_RESET and func:
                return runTask(func, args=args, resetAfter=resetAfter, convertAfter=convertAfter, allowAFB=allowAFB)
            return None

        pending_action = int(skipTask.value)
        if pending_action != INTERRUPT_NONE:
            return handle_interrupt(pending_action)
        
        try:
            #execute the task
            if func:
                returnVal = func(*args) 
                taskCompleted = True
            else:
                returnVal = None
            #task done
            if resetAfter: 
                macro.reset(convert=convertAfter)
            
            #do priority tasks
            if macro.night and macro.setdat["stinger_hunt"]:
                macro.stingerHunt()
            if macro.setdat["mondo_buff"] and macro.hasMondoRespawned():
                macro.collectMondoBuff()
            if macro.hasScheduledRejoinArrived():
                macro.rejoin("Rejoining (Scheduled)")
                macro.saveTiming("rejoin_every")
            
            #auto field boost (can be disabled per-call via allowAFB)
            if allowAFB and macro.setdat["Auto_Field_Boost"] and not macro.AFBLIMIT:
                if macro.hasAFBRespawned("AFB_dice_cd", macro.setdat["AFB_rebuff"]*60) or macro.hasAFBRespawned("AFB_glitter_cd", macro.setdat["AFB_rebuff"]*60-30):
                    macro.AFB(gatherInterrupt=False)
        except InterruptRequested as interrupt:
            return handle_interrupt(interrupt.action)

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
        nonlocal questCache, taskCompleted
        
        
        
        gatherFieldsList = []
        gumdropGatherFieldsList = []
        requireRedField = False
        requireBlueField = False
        requireField = False
        requireBlueGumdropField = False
        requireRedGumdropField = False
        feedBees = []
        setdatEnable = []

        # Refresh quest detection only when cache is stale to avoid duplicate scans in one cycle
        cacheFresh = questGiver in questCache and not taskCompleted
        if cacheFresh and questCache[questGiver] is not None:
            questObjective = questCache[questGiver]
        else:
            questObjective = macro.findQuest(questGiver)
            questCache[questGiver] = questObjective

        # Only submit/get quests if executeQuest is True (when quest appears in priority queue)
        if executeQuest:
            if questObjective is None:  # Quest does not exist -> try to claim a new quest
                if not canClaimTimedBearQuest(questGiver):
                    return setdatEnable, gatherFieldsList, gumdropGatherFieldsList, requireRedField, requireBlueField, feedBees, requireRedGumdropField, requireBlueGumdropField, requireField
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
                return setdatEnable, gatherFieldsList, gumdropGatherFieldsList, requireRedField, requireBlueField, feedBees, requireRedGumdropField, requireBlueGumdropField, requireField

        if questObjective is None: #still not able to find quest
            return setdatEnable, gatherFieldsList, gumdropGatherFieldsList, requireRedField, requireBlueField, feedBees, requireRedGumdropField, requireBlueGumdropField, requireField

        for obj in questObjective:
            objData = obj.split("_")
            if objData[0] == "gather":
                gatherFieldsList.append(objData[1])
            elif objData[0] == "gathergoo":
                if macro.setdat["quest_use_gumdrops"]:
                    gumdropGatherFieldsList.append(objData[1])
                else:
                    gatherFieldsList.append(objData[1])
            elif objData[0] == "kill":
                # kill objectives can be in the form "kill_<num>_<mob>" or "kill_<mob>"
                # determine the mob name robustly
                if len(objData) >= 3:
                    mob_name = objData[2]
                elif len(objData) == 2:
                    mob_name = objData[1]
                else:
                    continue

                # ants are handled via the ant challenge flow
                if "ant" in mob_name and mob_name != "mantis":
                    if "ant_challenge" not in setdatEnable:
                        setdatEnable.append("ant_challenge")
                    if "ant_pass_dispenser" not in setdatEnable:
                        setdatEnable.append("ant_pass_dispenser")
                else:
                    # enable the mob setting (e.g. "rhinobeetle", "werewolf", etc.)
                    if mob_name not in setdatEnable:
                        setdatEnable.append(mob_name)
            elif objData[0] == "token":
                if questGiver == "riley bee":
                    requireRedField = True
                elif questGiver == "bucko bee":
                    requireBlueField = True
                else:
                    requireField = True

            elif objData[0] == "token" and objData[1] == "honeytoken":
                setdatEnable.append("honeytoken")
            elif objData[0] == "fieldtoken" and objData[1] == "blueberry":
                requireBlueField = True
            elif objData[0] == "fieldtoken" and objData[1] == "strawberry":
                requireRedField = True
            elif objData[0] == "feed":
                if objData[1] == "*":
                    amount = 25
                else:
                    amount = int(objData[1])
                feedBees.append((objData[2], amount))
            elif objData[0] == "pollen" and objData[1] == "blue":
                requireBlueField = True
            elif objData[0] == "pollen" and objData[1] == "red":
                requireRedField = True
            elif objData[0] == "pollen" and objData[1] == "white":
                requireField = True
            elif objData[0] == "pollengoo" and objData[1] == "blue":
                if macro.setdat["quest_use_gumdrops"]:
                    requireBlueGumdropField = True
                else:
                    requireBlueField = True
            elif objData[0] == "pollengoo" and objData[1] == "red":
                if macro.setdat["quest_use_gumdrops"]:
                    requireRedGumdropField = True
                else:
                    requireBlueField = True
            elif objData[0] == "pollengoo" and objData[1] == "white":
                if macro.setdat["quest_use_gumdrops"]:
                    requireBlueGumdropField = True
                else:
                    requireField = True
            elif objData[0] == "collect":
                setdatEnable.append(objData[1].replace("-","_"))
        
        return setdatEnable, gatherFieldsList, gumdropGatherFieldsList, requireRedField, requireBlueField, feedBees, requireRedGumdropField, requireBlueGumdropField, requireField

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
        
        macro.setdat = get_cached_settings()
        # Check if profile has changed and reload settings if needed
        macro.checkAndReloadSettings()

        # Migration from old boolean flags to macro_mode is now handled in settings loader

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
            questGatherFieldOverrides = {}
            questGumdropFieldOverrides = {}
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

                        # Detect the current quest title (without executing) so we can honor title-level ignores
                        try:
                            setdatEnable_tmp, gatherFields_tmp, gumdropFields_tmp, needsRed_tmp, needsBlue_tmp, feedBees_tmp, needsRedGumdrop_tmp, needsBlueGumdrop_tmp, needsField_tmp = handleQuest(questName, executeQuest=False)
                            last_titles = getattr(macro, '_last_quest_title', {}) or {}
                            title = last_titles.get(questName, "") or ""
                        except Exception:
                            title = ""

                        # Use hardcoded ignore list and skip if title matches, but only when the
                        # profile setting `skip_petal_quests` is enabled. Default True preserves
                        # previous behavior for users without the setting.
                        if macro.setdat.get("skip_petal_quests", True):
                            ignore_set = HARDCODED_PETAL_IGNORE_TITLES
                            if title.lower() in ignore_set:
                                try:
                                    gui.log(time.strftime("%H:%M:%S"), f"Skipping ignored quest '{title}' for {questName}", "orange")
                                except Exception:
                                    pass
                                macro.logger.webhook("Skipping ignored petal quest", f"Quest: {title}", "orange")
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
                                        setdatEnable, gatherFields, gumdropFields, needsRed, needsBlue, feedBees, needsRedGumdrop, needsBlueGumdrop, needsField = handleQuest(questName)
                                else:
                                    setdatEnable, gatherFields, gumdropFields, needsRed, needsBlue, feedBees, needsRedGumdrop, needsBlueGumdrop, needsField = handleQuest(questName)
                                questGatherOverrides = getQuestGatherOverrides(questName)
                                for k in setdatEnable:
                                    macro.setdat[k] = True
                                for field in gatherFields:
                                    questGatherFields.append(field)
                                    if field not in questGatherFieldOverrides:
                                        questGatherFieldOverrides[field] = dict(questGatherOverrides)
                                for field in gumdropFields:
                                    questGumdropGatherFields.append(field)
                                    if field not in questGumdropFieldOverrides:
                                        questGumdropFieldOverrides[field] = dict(questGatherOverrides)
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
                macro.feedBee(item, quantity)
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
                    runTask(macro.gather, args=(field, questGumdropFieldOverrides.get(field, {}), True), resetAfter=False)
                    allGatheredFields.append(field)

            # Handle regular quest gather fields
            questGatherFields = [x for x in questGatherFields if not (x in allGatheredFields)]
            for field in questGatherFields:
                runTask(macro.gather, args=(field, questGatherFieldOverrides.get(field, {})), resetAfter=False)
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
                    runTask(macro.gather, args=(field, blueFieldOverride), resetAfter=False)

            if redFieldNeeded:
                for f in redFields:
                    if f in allGatheredFields:
                        break
                else:
                    field = "rose"
                    allGatheredFields.append(field)
                    runTask(macro.gather, args=(field, redFieldOverride), resetAfter=False)

            if fieldNeeded and not allGatheredFields:
                if defaultQuestFieldOverride:
                    runTask(macro.gather, args=("pine tree", defaultQuestFieldOverride), resetAfter=False)
                else:
                    runTask(macro.gather, args=("pine tree",), resetAfter=False)

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
                        macro.coconutCrab()
                        executedTasks.add(taskId)
                    continue

                if mob == "king_beetle":
                    if macro.setdat["king_beetle"] and macro.hasRespawned("king_beetle", 24*60*60, applyMobRespawnBonus=True):
                        macro.kingBeetle()
                        executedTasks.add(taskId)
                    continue

                if mob == "tunnel_bear":
                    if macro.setdat["tunnel_bear"] and macro.hasRespawned("tunnel_bear", 48*60*60, applyMobRespawnBonus=True):
                        macro.tunnelBear()
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
        questGatherFieldOverrides = {}
        questGumdropFieldOverrides = {}
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
                setdatEnable, gatherFields, gumdropFields, needsRed, needsBlue, feedBees, needsRedGumdrop, needsBlueGumdrop, needsField = handleQuest(questName, executeQuest=False)
                # Respect title-level ignore list: if the detected quest title is ignored, skip applying requirements
                try:
                    last_titles = getattr(macro, '_last_quest_title', {}) or {}
                    title = last_titles.get(questName, "") or ""
                    # Only apply hardcoded petal-title ignores when the setting is enabled
                    if macro.setdat.get("skip_petal_quests", True):
                        ignore_set = HARDCODED_PETAL_IGNORE_TITLES
                        if title.lower() in ignore_set:
                            try:
                                gui.log(time.strftime("%H:%M:%S"), f"Skipping ignored quest (requirements): '{title}' for {questName}", "orange")
                            except Exception:
                                pass
                            macro.logger.webhook("Skipping ignored petal quest", f"Quest: {title}", "orange")
                            continue
                except Exception:
                    pass
                except Exception:
                    pass
                # Enable any required settings
                for k in setdatEnable:
                    macro.setdat[k] = True
                questGatherOverrides = getQuestGatherOverrides(questName)
                # Store gather fields (will be used after priority queue)
                for field in gatherFields:
                    questGatherFields.append(field)
                    if field not in questGatherFieldOverrides:
                        questGatherFieldOverrides[field] = dict(questGatherOverrides)
                for field in gumdropFields:
                    questGumdropGatherFields.append(field)
                    if field not in questGumdropFieldOverrides:
                        questGumdropFieldOverrides[field] = dict(questGatherOverrides)
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
            with open("./data/user/manualplanters.txt", "w") as f:
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
                # Detect the current quest title (without executing) so we can honor title-level ignores before execution
                try:
                    # populate last_quest_title via requirement-only check
                    _ = handleQuest(questName, executeQuest=False)
                    last_titles = getattr(macro, '_last_quest_title', {}) or {}
                    title = last_titles.get(questName, "") or ""
                    # Only skip based on hardcoded petal titles when the profile setting is enabled
                    if macro.setdat.get("skip_petal_quests", True):
                        ignore_set = HARDCODED_PETAL_IGNORE_TITLES
                        if title.lower() in ignore_set:
                            try:
                                gui.log(time.strftime("%H:%M:%S"), f"Skipping ignored quest (execution): '{title}' for {questName}", "orange")
                            except Exception:
                                pass
                            macro.logger.webhook("Skipping ignored petal quest", f"Quest: {title}", "orange")
                            executedTasks.add(taskId)
                            return False
                except Exception:
                    pass
                
                # Actually execute the quest (submit/get) - this will travel to quest giver if needed
                # For Brown Bear, capture the objectives and gather them immediately
                if questName == "brown bear":
                    setdatEnable, gatherFields, gumdropFields, needsRed, needsBlue, feedBees, needsRedGumdrop, needsBlueGumdrop, needsField = handleQuest(questName, executeQuest=True)
                    
                    # Gather the fields for this quest
                    questGatherOverrides = getQuestGatherOverrides(questName)
                    
                    # Gather regular fields
                    for field in gatherFields:
                        runTask(macro.gather, args=(field, questGatherOverrides), resetAfter=False)
                    
                    # Gather gumdrop fields (if any)
                    for field in gumdropFields:
                        runTask(macro.gather, args=(field, questGatherOverrides, True), resetAfter=False)
                    
                    # Feed bees if needed
                    for item, quantity in feedBees:
                        macro.feedBee(item, quantity)
                        taskCompleted = True
                else:
                    handleQuest(questName, executeQuest=True)
                    
                    # Feed bees for this quest (requirements were already checked above)
                    if questName in questFeedRequirements:
                        feedBees = questFeedRequirements[questName]
                        for item, quantity in feedBees:
                            macro.feedBee(item, quantity)
                            taskCompleted = True
                
                executedTasks.add(taskId)
                executedQuests.add(questName)
                return True
            
            # Handle collect tasks
            if taskId.startswith("collect_"):
                collectName = taskId.replace("collect_", "")
                
                # Special case: sticker_printer
                if collectName == "sticker_printer":
                    if macro.setdat["sticker_printer"] and macro.hasRespawned("sticker_printer", macro.collectCooldowns["sticker_printer"]):
                        runTask(macro.collectStickerPrinter)
                        executedTasks.add(taskId)
                        return True
                    return False
                
                # Special case: sticker_stack
                if collectName == "sticker_stack":
                    if macro.setdat["sticker_stack"]:
                        with open("./data/user/sticker_stack.txt", "r") as f:
                            stickerStackCD = int(f.read())
                        f.close()
                        if macro.hasRespawned("sticker_stack", stickerStackCD):
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
                        macro.coconutCrab()
                        executedTasks.add(taskId)
                        return True
                    return False
                

                # King Beetle respawns every 24 hours (20 hours 24 minutes with Gifted Vicious Bee)
                if mob == "king_beetle":
                    if macro.setdat["king_beetle"] and macro.hasRespawned("king_beetle", 24*60*60, applyMobRespawnBonus=True):
                        macro.kingBeetle()
                        executedTasks.add(taskId)
                        return True
                    return False

                # Tunnel Bear respawns every 48 hours (40 hours 48 minutes with Gifted Vicious Bee)
                if mob == "tunnel_bear":
                    if macro.setdat["tunnel_bear"] and macro.hasRespawned("tunnel_bear", 48*60*60, applyMobRespawnBonus=True):
                        macro.tunnelBear()
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
                if fieldName in questGatherFields or fieldName in questGumdropGatherFields:
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
                    with open("./data/user/blender.txt", "r") as f:
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
                        with open("./data/user/manualplanters.txt", "r") as f:
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
                        with open("./data/user/auto_planters.json", "r") as f:
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

                    def emptyAutoPlanterSlot():
                        return {
                            "planter": "",
                            "nectar": "",
                            "field": "",
                            "harvest_time": 0,
                            "nectar_est_percent": 0,
                            "placed_time": 0,
                            "grow_duration": 0,
                            "natural_grow_duration": 0
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
                        with open("./data/user/auto_planters.json", "w") as f:
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

                    def getPlanterProgress(planter):
                        return getNaturalPlanterProgress(planter)

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
                                if planterName in occupiedPlanters or (planterName, field) in blockedPlacements:
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

        # Execute quest tasks bypassing normal settings restrictions
        def executeQuestTask(taskId):
            """
            Execute quest completer tasks, bypassing normal macro settings restrictions.
            This allows quest tasks to run even when the corresponding features are disabled.
            """
            # Check cooldown to prevent executing the same quest task too frequently
            currentTime = time.time()
            if taskId in questTaskCooldowns:
                lastExecuted = questTaskCooldowns[taskId]
                if currentTime - lastExecuted < 60:  # 60 second cooldown between executions of the same quest task
                    return False
            questTaskCooldowns[taskId] = currentTime
            try:
                # Handle gather tasks (field gathering)
                if taskId.startswith("gather_"):
                    fieldName = taskId.replace("gather_", "").replace("_", " ")
                    # Check if this field exists and execute gather task directly
                    for i in range(len(macro.setdat["fields"])):
                        storedFieldName = macro.setdat["fields"][i]
                        if storedFieldName.lower() == fieldName.lower():
                            # For quest tasks, temporarily enable the field if it's not enabled
                            fieldWasEnabled = macro.setdat["fields_enabled"][i]
                            if not fieldWasEnabled:
                                macro.setdat["fields_enabled"][i] = True
                            try:
                                # Execute gather task
                                macro.logger.webhook("Quest Task", f"Executing gather in field: {storedFieldName}", "light blue")
                                runTask(macro.gather, args=(storedFieldName,), resetAfter=False)
                                macro.logger.webhook("Quest Task", f"Completed gather in field: {storedFieldName}", "bright green")
                                return True
                            finally:
                                # Restore original enabled state
                                macro.setdat["fields_enabled"][i] = fieldWasEnabled
                    return False

                # Handle kill tasks (mob killing)
                elif taskId.startswith("kill_"):
                    mob = taskId.replace("kill_", "")
                    # Handle special cases first
                    if mob == "coconut_crab":
                        if macro.hasRespawned("coconut_crab", 36*60*60, applyMobRespawnBonus=True):
                            runTask(macro.coconutCrab)
                            return True
                    elif mob == "stump_snail":
                        if macro.hasRespawned("stump_snail", 96*60*60, applyMobRespawnBonus=True):
                            runTask(macro.stumpSnail)
                            return True
                    elif mob == "vicious_bee":
                        if macro.hasRespawned("vicious_bee", 36*60*60, applyMobRespawnBonus=True):
                            runTask(macro.viciousBee)
                            return True
                    elif mob == "ant":
                        # Ant killing via Ant Challenge
                        macro.logger.webhook("Quest Task", "Executing ant challenge for quest", "light blue")
                        runTask(macro.antChallenge, resetAfter=False)
                        macro.logger.webhook("Quest Task", "Completed ant challenge", "bright green")
                        return True
                    elif mob == "beetle":
                        # Try to find and kill beetles (not king beetles)
                        # Beetles might spawn in various fields, try common ones
                        commonFields = ["strawberry", "clover", "bamboo", "pineapple"]
                        for field in commonFields:
                            fieldIndex = -1
                            for i in range(len(macro.setdat["fields"])):
                                if macro.setdat["fields"][i] == field:
                                    fieldIndex = i
                                    break

                            if fieldIndex >= 0:
                                fieldWasEnabled = macro.setdat["fields_enabled"][fieldIndex]
                                if not fieldWasEnabled:
                                    macro.setdat["fields_enabled"][fieldIndex] = True

                                try:
                                    macro.logger.webhook("Quest Task", f"Attempting to kill beetle in field: {field}", "light blue")
                                    # Try to kill beetle if available
                                    runTask(macro.killMob, args=(mob, field,), convertAfter=False)
                                    macro.logger.webhook("Quest Task", f"Completed beetle kill attempt in field: {field}", "bright green")
                                    return True
                                except Exception as e:
                                    continue  # Try next field
                                finally:
                                    macro.setdat["fields_enabled"][fieldIndex] = fieldWasEnabled
                        macro.logger.webhook("Quest Task", "No beetles found to kill", "orange")
                        return False
                    else:
                        # For regular mobs, check if mob exists in regularMobData
                        if mob in regularMobData:
                            # For quest tasks, try to kill in the first available field
                            for field in regularMobData[mob]:
                                # Find the field index and temporarily enable it if needed
                                fieldIndex = -1
                                for i in range(len(macro.setdat["fields"])):
                                    if macro.setdat["fields"][i] == field:
                                        fieldIndex = i
                                        break

                                if fieldIndex >= 0:
                                    fieldWasEnabled = macro.setdat["fields_enabled"][fieldIndex]
                                    if not fieldWasEnabled:
                                        macro.setdat["fields_enabled"][fieldIndex] = True

                                    try:
                                        macro.logger.webhook("Quest Task", f"Executing kill {mob} in field: {field}", "light blue")
                                        runTask(macro.killMob, args=(mob, field,), convertAfter=False)
                                        macro.logger.webhook("Quest Task", f"Completed kill {mob} in field: {field}", "bright green")
                                        return True  # Successfully attempted to kill
                                    except Exception as e:
                                        macro.logger.webhook("Quest Task", f"Failed to kill {mob} in {field}: {str(e)}", "orange")
                                        continue  # Try next field
                                    finally:
                                        # Restore original enabled state
                                        macro.setdat["fields_enabled"][fieldIndex] = fieldWasEnabled

                            return True  # Attempted to kill, even if no mobs were found
                    return False

                # Handle collect tasks (dispensers, boosters, etc.)
                elif taskId.startswith("collect_"):
                    collectName = taskId.replace("collect_", "")
                    # Filter out malformed collect tasks (tool-based, completed, token, etc.)
                    if (len(collectName) > 30 or '_with_' in collectName or
                        'complete' in collectName):
                        return False  # Skip malformed collect tasks
                    # Check if this collect item exists in the data
                    if collectName in macroModule.collectData:
                        # Execute collect task directly, ignoring enabled/disabled setting
                        if macro.hasRespawned(collectName, macro.collectCooldowns[collectName]):
                            if collectName == "wreath" and not isBackpackReadyForWreath():
                                macro.logger.webhook("Quest Task", "Honey Wreath ready, but backpack is not full yet. Deferring claim", "orange")
                                return False
                            macro.logger.webhook("Quest Task", f"Executing collect: {collectName}", "light blue")
                            runTask(macro.collect, args=(collectName,))
                            macro.logger.webhook("Quest Task", f"Completed collect: {collectName}", "bright green")
                            return True
                            return True
                        else:
                            # Calculate time remaining
                            timing = macro.getTiming(collectName)
                            cooldown = macro.collectCooldowns[collectName]
                            timeElapsed = time.time() - timing
                            timeRemaining = cooldown - timeElapsed
                            if timeRemaining > 0:
                                hours = int(timeRemaining // 3600)
                                minutes = int((timeRemaining % 3600) // 60)
                                macro.logger.webhook("Quest Task", f"Collect {collectName} not ready, time remaining: {hours}h {minutes}m", "orange")
                            else:
                                macro.logger.webhook("Quest Task", f"Collect {collectName} not ready", "orange")
                    return False

                # Handle craft tasks
                elif taskId == "craft":
                    # Execute blender crafting directly
                    with open("./data/user/blender.txt", "r") as f:
                        blenderData = ast.literal_eval(f.read())
                    if blenderData["collectTime"] > -1 and time.time() > blenderData["collectTime"]:
                        macro.logger.webhook("Quest Task", "Executing craft (blender)", "light blue")
                        runTask(macro.blender, args=(blenderData,))
                        macro.logger.webhook("Quest Task", "Completed craft (blender)", "bright green")
                        return True
                        return True
                    else:
                        if blenderData["collectTime"] > -1:
                            timeRemaining = blenderData["collectTime"] - time.time()
                            if timeRemaining > 0:
                                hours = int(timeRemaining // 3600)
                                minutes = int((timeRemaining % 3600) // 60)
                                macro.logger.webhook("Quest Task", f"Craft (blender) not ready, time remaining: {hours}h {minutes}m", "orange")
                            else:
                                macro.logger.webhook("Quest Task", "Craft (blender) not ready", "orange")
                        else:
                            macro.logger.webhook("Quest Task", "Craft (blender) not ready", "orange")
                    return False

                # Handle feed bee tasks
                elif taskId.startswith("feed_bee_"):
                    # This should already work with the existing logic
                    return False  # Let the main executeTask handle feed_bee tasks

                return False
            except Exception as e:
                macro.logger.webhook("Quest Task Error",
                                   f"Error executing quest task {taskId}: {str(e)}",
                                   "red")
                # Still return False to mark as failed, but log the error
                return False

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
                with open("./data/user/blender.txt", "r") as f:
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
                runTask(macro.gather, args=(field, questGumdropFieldOverrides.get(field, {}), True), resetAfter=False)
                allGatheredFields.append(field)

        # Handle regular quest gather fields
        questGatherFields = [x for x in questGatherFields if not (x in allGatheredFields)]
        for field in questGatherFields:
            runTask(macro.gather, args=(field, questGatherFieldOverrides.get(field, {})), resetAfter=False)
            allGatheredFields.append(field)

        # Handle required blue/red fields for quests
        if blueFieldNeeded:
            for f in blueFields:
                if f in allGatheredFields:
                    break
            else:
                field = "pine tree"
                allGatheredFields.append(field)
                runTask(macro.gather, args=(field, blueFieldOverride), resetAfter=False)
        
        if redFieldNeeded:
            for f in redFields:
                if f in allGatheredFields:
                    break
            else:
                field = "rose"
                allGatheredFields.append(field)
                runTask(macro.gather, args=(field, redFieldOverride), resetAfter=False)
        
        if fieldNeeded and not allGatheredFields:
            if defaultQuestFieldOverride:
                runTask(macro.gather, args=("pine tree", defaultQuestFieldOverride), resetAfter=False)
            else:
                runTask(macro.gather, args=("pine tree",), resetAfter=False)
        
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
                with open("./data/user/auto_planters.json", "r") as f:
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


def watch_for_hotkeys(run):
    # Track currently pressed keys for combination detection
    pressed_keys = set()
    
    # Add debouncing to prevent duplicate triggers
    last_trigger_time = {"start": 0.0, "stop": 0.0, "pause": 0.0}
    debounce_duration = 0.3  # 300ms debounce
    
    # Add threading lock for synchronization
    import threading
    key_lock = threading.Lock()
    
    # Add key state cleanup to handle stuck keys
    last_cleanup_time = 0
    cleanup_interval = 5.0  # Clean up every 5 seconds
    
    # Force stop tracking
    stop_key_held = False
    force_stop_check_interval = 0.1  # Check every 100ms
    last_force_stop_check = 0
    
    # Cache settings to avoid reloading on every keypress
    settings_cache = {}
    last_settings_load = 0
    settings_cache_duration = 1.0  # Reload settings every 1 second max
    
    # Cache Eel recording state to avoid repeated calls
    recording_cache = {"start": False, "pause": False, "stop": False}
    last_recording_check = 0
    recording_cache_duration = 0.5  # Check recording state every 0.5 seconds max

    modifier_keys = ["Ctrl", "Alt", "Shift", "Cmd"]
    ignored_keys = {"Fn"}
    key_aliases = {
        "ctrl_l": "Ctrl", "ctrl_r": "Ctrl", "control": "Ctrl", "ctrl": "Ctrl",
        "alt_l": "Alt", "alt_r": "Alt", "option": "Alt", "alt": "Alt",
        "shift_l": "Shift", "shift_r": "Shift", "shift": "Shift",
        "cmd_l": "Cmd", "cmd_r": "Cmd", "cmd": "Cmd", "meta": "Cmd", "command": "Cmd",
        "space": "Space", "spacebar": "Space",
        "enter": "Enter", "return": "Enter",
        "tab": "Tab",
        "backspace": "Backspace",
        "delete": "Delete", "del": "Delete",
        "esc": "Escape", "escape": "Escape",
        "caps_lock": "CapsLock", "capslock": "CapsLock",
        "left": "ArrowLeft", "arrowleft": "ArrowLeft",
        "right": "ArrowRight", "arrowright": "ArrowRight",
        "up": "ArrowUp", "arrowup": "ArrowUp",
        "down": "ArrowDown", "arrowdown": "ArrowDown",
        "home": "Home",
        "end": "End",
        "page_up": "PageUp", "pageup": "PageUp",
        "page_down": "PageDown", "pagedown": "PageDown",
        "insert": "Insert",
        "fn": "Fn",
        "¡": "1", "™": "2", "£": "3", "¢": "4", "∞": "5",
        "§": "6", "¶": "7", "•": "8", "ª": "9", "º": "0",
        "å": "A", "∫": "B", "ç": "C", "∂": "D", "ƒ": "F",
        "©": "G", "˙": "H", "∆": "J", "˚": "K", "¬": "L",
        "µ": "M", "ø": "O", "π": "P", "œ": "Q", "®": "R",
        "ß": "S", "†": "T", "√": "V", "∑": "W", "≈": "X",
        "¥": "Y", "Ω": "Z", "ω": "Z",
    }
    
    def get_cached_settings():
        nonlocal settings_cache, last_settings_load
        current_time = time.time()
        if current_time - last_settings_load > settings_cache_duration:
            settings_cache = settingsManager.loadAllSettings()
            last_settings_load = current_time
        return settings_cache
    
    def is_recording_keybind():
        nonlocal recording_cache, last_recording_check
        current_time = time.time()
        if current_time - last_recording_check > recording_cache_duration:
            try:
                import eel
                recording_cache["start"] = eel.getElementProperty("start_keybind", "dataset.recording")() == "true"
                recording_cache["pause"] = eel.getElementProperty("pause_keybind", "dataset.recording")() == "true"
                recording_cache["stop"] = eel.getElementProperty("stop_keybind", "dataset.recording")() == "true"
                last_recording_check = current_time
            except:
                recording_cache = {"start": False, "pause": False, "stop": False}
            return recording_cache["start"] or recording_cache["pause"] or recording_cache["stop"]
    
    def normalize_key_name(key_name):
        key_name = str(key_name or "").strip()
        if not key_name:
            return ""
        if key_name.startswith("Key."):
            key_name = key_name[4:]
        if key_name.startswith("'") and key_name.endswith("'") and len(key_name) >= 2:
            key_name = key_name[1:-1]

        alias = key_aliases.get(key_name.lower())
        if alias:
            return alias
        if key_name.lower().startswith("f") and key_name[1:].isdigit():
            return key_name.upper()
        if len(key_name) == 1:
            return key_name.upper()
        return key_name

    def parse_keybind(keybind):
        keys = []
        for raw_key in str(keybind or "").split("+"):
            key_name = normalize_key_name(raw_key)
            if key_name and key_name not in ignored_keys and key_name not in keys:
                keys.append(key_name)
        return tuple(order_keys(keys))

    def order_keys(keys):
        ordered = [key for key in modifier_keys if key in keys]
        ordered.extend(sorted(key for key in keys if key not in modifier_keys))
        return ordered

    def keys_match_keybind(keybind):
        expected_keys = parse_keybind(keybind)
        if not expected_keys:
            return False
        active_keys = {key for key in pressed_keys if key not in ignored_keys}
        return active_keys == set(expected_keys)

    def keybind_is_held(keybind):
        expected_keys = parse_keybind(keybind)
        if not expected_keys:
            return False
        return all(key in pressed_keys for key in expected_keys)

    def convert_key_to_string(key):
        """Convert pynput key objects to the same canonical names saved by the UI."""
        try:
            key_char = getattr(key, "char", None)
            if key_char:
                return normalize_key_name(key_char)
            return normalize_key_name(str(key))
        except Exception as e:
            # Log error but don't crash the listener
            print(f"Error converting key {key}: {e}")
            return normalize_key_name(str(key))
    
    def is_stop_keybind_held():
        """Check if the stop keybind is currently held down"""
        try:
            settings = get_cached_settings()
            if not settings:
                return False
                
            stop_keybind = settings.get("stop_keybind", "F3")
            if not stop_keybind:
                return False
            
            return keybind_is_held(stop_keybind)
        except Exception as e:
            print(f"Error checking stop keybind: {e}")
            return False
    
    def on_press(key):
        nonlocal run, last_cleanup_time, stop_key_held, last_force_stop_check
        
        # Use lock to prevent race conditions
        with key_lock:
            try:
                # Periodic cleanup of stuck keys
                current_time = time.time()
                if current_time - last_cleanup_time > cleanup_interval:
                    # Clear all pressed keys to reset state
                    pressed_keys.clear()
                    last_cleanup_time = current_time
                
                # Get cached settings
                settings = get_cached_settings()
                start_keybind = settings.get("start_keybind", "F1")
                stop_keybind = settings.get("stop_keybind", "F3")
                pause_keybind = settings.get("pause_keybind", "F2")
                
                # Convert key to string for comparison
                key_str = convert_key_to_string(key)
                pressed_keys.add(key_str)
                
                # Don't start/stop macro if we're recording a keybind
                if is_recording_keybind():
                    return  # Ignore keybind during recording

                # Check for force stop (stop keybind held down)
                if is_stop_keybind_held():
                    if not stop_key_held:
                        stop_key_held = True
                    try:
                        import gui
                        gui.stopAllTools()
                    except Exception:
                        pass
                    # Force stop immediately when stop keybind is held
                    if run.value != 0:  # Only if not already stopped
                        run.value = 0
                        # Update GUI immediately so the app shows cleanup in progress.
                        try:
                            import gui
                            gui.setRunState(0)
                            gui.toggleStartStop()
                        except:
                            pass  # If gui is not ready, continue
                else:
                    stop_key_held = False

                # Add debouncing to prevent duplicate triggers
                current_time = time.time()
                
                if keys_match_keybind(start_keybind):
                    if run.value != 3: #only start from fully stopped state
                        return
                    try:
                        import gui
                        if gui.isAnyToolRunning():
                            messageBox.msgBox(title="Tool Running", text="Stop the running tool before starting the macro.")
                            return
                    except Exception:
                        pass
                    # Check debounce with error handling
                    try:
                        if current_time - last_trigger_time["start"] < debounce_duration:
                            return
                    except (TypeError, ValueError):
                        # Reset trigger time if there's a comparison error
                        last_trigger_time["start"] = 0.0
                    last_trigger_time["start"] = current_time
                    run.value = 1
                    # Update GUI immediately (optimistically show running state)
                    try:
                        import gui
                        gui.setRunState(2)  # Update GUI state optimistically to running
                        gui.toggleStartStop()  # Update UI immediately
                    except:
                        pass  # If gui is not ready, continue
                elif keys_match_keybind(stop_keybind) and not stop_key_held:
                    # Check debounce with error handling
                    try:
                        if current_time - last_trigger_time["stop"] < debounce_duration:
                            return
                    except (TypeError, ValueError):
                        # Reset trigger time if there's a comparison error
                        last_trigger_time["stop"] = 0.0
                    last_trigger_time["stop"] = current_time
                    try:
                        import gui
                        gui.stopAllTools()
                    except Exception:
                        pass
                    if run.value == 3: #already stopped
                        return
                    run.value = 0
                    # Update GUI immediately so the app shows cleanup in progress.
                    try:
                        import gui
                        gui.setRunState(0)
                        gui.toggleStartStop()
                    except:
                        pass  # If gui is not ready, continue
                elif keys_match_keybind(pause_keybind):
                    # Check debounce with error handling
                    try:
                        if current_time - last_trigger_time["pause"] < debounce_duration:
                            return
                    except (TypeError, ValueError):
                        # Reset trigger time if there's a comparison error
                        last_trigger_time["pause"] = 0.0
                    last_trigger_time["pause"] = current_time

                    # Toggle between pause and resume
                    if run.value == 2:  # Running -> Pause immediately
                        # Release inputs instantly (like force stop behavior)
                        try:
                            keyboardModule.releaseMovement()
                        except Exception:
                            pass
                        try:
                            mouse.mouseUp()
                        except Exception:
                            pass

                        run.value = 6

                        # Update GUI immediately (optimistically show paused state)
                        try:
                            import gui
                            gui.setRunState(6)
                            gui.toggleStartStop()
                        except:
                            pass
                    elif run.value == 6:  # Paused -> Resume
                        run.value = 2
            except Exception as e:
                # Log error but don't crash the listener
                print(f"Error in on_press: {e}")
                return
    
    def on_release(key):
        # Remove released key from pressed keys using optimized conversion
        with key_lock:
            try:
                key_str = convert_key_to_string(key)
                pressed_keys.discard(key_str)
                
                # Check if stop keybind is no longer held
                if not is_stop_keybind_held():
                    nonlocal stop_key_held
                    stop_key_held = False
            except Exception as e:
                # Log error but don't crash the listener
                print(f"Error in on_release: {e}")
                return

    # Start keyboard listener with error handling and recovery
    # On macOS, this must be called on the main thread
    def start_keyboard_listener():
        try:
            # Ensure we're on the main thread on macOS
            if sys.platform == "darwin":
                import threading
                current_thread = threading.current_thread()
                main_thread = threading.main_thread()
                if current_thread is not main_thread:
                    print("Warning: Keyboard listener should be started on main thread on macOS")
            
            listener = keyboard.Listener(on_press=on_press, on_release=on_release)
            listener.start()
            return listener
        except Exception as e:
            print(f"Failed to start keyboard listener: {e}")
            # Try to restart after a short delay
            import threading
            def restart_listener():
                time.sleep(1)
                try:
                    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
                    listener.start()
                    print("Keyboard listener restarted successfully")
                except Exception as e2:
                    print(f"Failed to restart keyboard listener: {e2}")
            
            restart_thread = threading.Thread(target=restart_listener, daemon=True)
            restart_thread.start()
            return None
    
    # Don't start the listener here - it will be started after GUI launch on main thread
    # start_keyboard_listener()
    
    # Return the function so it can be called later on the main thread
    return start_keyboard_listener

if __name__ == "__main__":
    print("Loading gui...")
    global stopThreads, macroProc
    import gui
    import modules.screen.screenData as screenData
    from modules.controls.keyboard import keyboard as keyboardModule
    import modules.logging.log as logModule
    import modules.misc.appManager as appManager
    import modules.misc.settingsManager as settingsManager
    from modules.discord_bot.discordBot import discordBot
    from modules.submacros.convertAhkPattern import ahkPatternToPython
    from modules.submacros.stream import cloudflaredStream
    import os

    if sys.version_info[1] <= 7:
        print("start method set to spawn")
        multiprocessing.set_start_method("spawn")
    macroProc = None
    #set screen data
    screenData.setScreenData()
    screenInfo = screenData.getScreenData()
    #value to control if macro main loop is running
    #0: stop (terminate process)
    #1: start (start process)
    #2: already running (do nothing)
    #3: already stopped (do nothing)
    #4: disconnected (rejoin)
    manager = multiprocessing.Manager()
    run = manager.Value('i', 3)
    gui.setRunState(3)  # Initialize the global run state
    recentLogs = manager.list()  # Shared list to store recent log entries for discord bot
    gui.setRecentLogs(recentLogs)
    updateGUI = manager.Value('i', 0)
    skipTask = manager.Value('i', INTERRUPT_NONE)  # interrupt action for the running task
    status = manager.Value(ctypes.c_wchar_p, "none")
    presence = manager.Value(ctypes.c_wchar_p, "")
    logQueue = manager.Queue()
    pin_requests = manager.Queue()  # Shared queue for pin requests
    start_keyboard_listener_fn = watch_for_hotkeys(run)
    logger = logModule.log(logQueue, False, None, False, blocking=False)
    gui.configureToolRuntime(logger=logger, status=status, presence=presence)

    disconnectCooldownUntil = 0 #only for running disconnect check on low performance

    #update settings for current profile
    currentProfile = settingsManager.getCurrentProfile()
    profileSettings = settingsManager.loadSettings()
    profileSettingsReference = settingsManager.readSettingsFile(os.path.join(settingsManager.getDefaultSettingsPath(), "settings.txt"))
    settingsManager.saveDict(os.path.join(settingsManager.getProfilePath(currentProfile), "settings.txt"), {**profileSettingsReference, **profileSettings})

    #update general settings for current profile
    generalsettings_path = os.path.join(settingsManager.getProfilePath(currentProfile), "generalsettings.txt")
    generalSettingsReference = settingsManager.readSettingsFile(os.path.join(settingsManager.getDefaultSettingsPath(), "generalsettings.txt"))
    try:
        generalSettings = settingsManager.readSettingsFile(generalsettings_path)
    except FileNotFoundError:
        # If generalsettings.txt doesn't exist, create it from defaults
        generalSettings = {}
        # Ensure the profile directory exists
        profile_dir = settingsManager.getProfilePath(currentProfile)
        os.makedirs(profile_dir, exist_ok=True)
    settingsManager.saveDict(generalsettings_path, {**generalSettingsReference, **generalSettings})

    #convert ahk pattern
    patterns_dir = settingsManager.getPatternsDir()
    if os.path.exists(patterns_dir):
        ahkPatterns = [x for x in os.listdir(patterns_dir) if ".ahk" in x]
        for pattern in ahkPatterns:
            pattern_path = os.path.join(patterns_dir, pattern)
            with open(pattern_path, "r") as f:
                ahk = f.read()
            f.close()
            try:
                python = ahkPatternToPython(ahk)
                print(f"Converted: {pattern}")
                patternName = pattern.rsplit(".", 1)[0].lower()
                output_path = os.path.join(patterns_dir, f"{patternName}.py")
                with open(output_path, "w") as f:
                    f.write(python)
                f.close()
            except:
                messageBox.msgBox(title="Failed to convert pattern", text=f"There was an error converting {pattern}. The pattern will not be used.")
    
    #setup stream class
    stream = cloudflaredStream()

    def onExit():
        stopApp()
        # Reset timed bear quest states on exit so macro resumes checking next run
        try:
            settingsManager.saveSettingFile("brown_bear_quest_state", 0, "./data/user/timings.txt")
        except Exception:
            pass
        try:
            settingsManager.saveSettingFile("black_bear_quest_state", 0, "./data/user/timings.txt")
        except Exception:
            pass
        try:
            if discordBotProc and discordBotProc.is_alive():
                discordBotProc.terminate()
                discordBotProc.join()
        except NameError:
            pass
        try:
            if richPresenceManager:
                richPresenceManager.stop()
        except NameError:
            pass
        
    def stopApp(page= None, sockets = None):
        global stopThreads
        global macroProc
        stopThreads = True
        #print(sockets)
        if macroProc and macroProc.is_alive():
            macroProc.terminate()
            macroProc.join(timeout=2)
            if macroProc.is_alive():
                macroProc.kill()
                macroProc.join(timeout=2)
        macroProc = None
        stream.stop()
        #if discordBotProc.is_alive(): discordBotProc.kill()
        keyboardModule.releaseMovement()
        mouse.mouseUp()
    
    atexit.register(onExit)
        
    #setup and launch gui
    gui.run = run
    gui.launch()
    # Ensure GUI loads current settings immediately on open (adds Brown Bear if missing)
    try:
        gui.updateGUI()
    except Exception:
        pass
    
    # Start keyboard listener after GUI launch to ensure it's on the main thread (required on macOS)
    # This prevents TIS/TSM errors on macOS
    if start_keyboard_listener_fn:
        try:
            start_keyboard_listener_fn()
            print("Keyboard listener started successfully")
        except Exception as e:
            print(f"Failed to start keyboard listener after GUI launch: {e}")
    
    #use run.value to control the macro loop

    #check color profile
    try:
        colorProfileManager = DisplayColorProfile()
        currentProfileColor = colorProfileManager.getCurrentColorProfile()
        if not "sRGB" in currentProfileColor:
            try:
                if messageBox.msgBoxOkCancel(title="Incorrect Color Profile", text=f"You current display's color profile is {currentProfileColor} but sRGB is required for the macro.\nPress 'Ok' to change color profiles"):
                    colorProfileManager.resetDisplayProfile()
                    colorProfileManager.setCustomProfile("/System/Library/ColorSync/Profiles/sRGB Profile.icc")
                    messageBox.msgBox(title="Color Profile Success", text="Successfully changed the current color profile to sRGB")

            except Exception as e:
                messageBox.msgBox(title="Failed to change color profile", text=e)
    except Exception as e:
        pass
    
    #check screen recording permissions
    try:
        cg = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")
        cg.CGRequestScreenCaptureAccess.restype = ctypes.c_bool
        if not cg.CGRequestScreenCaptureAccess():
            messageBox.msgBox(title="Screen Recording Permission", text='Terminal does not have the screen recording permission. The macro will not work properly.\n\nTo fix it, go to System Settings -> Privacy and Security -> Screen Recording -> add and enable Terminal. After that, restart the macro')
    except AttributeError:
        pass
    #check full keyboard access
    try:
        result = subprocess.run(
            ["defaults", "read", "com.apple.universalaccess", "KeyboardAccessEnabled"],
            capture_output=True,
            text=True
        )
        value = result.stdout.strip()
        if value == "1":
            messageBox.msgBox(text = f"Full Keyboard Access is enabled. The macro will not work properly\
                \nTo disable it, go to System Settings -> Accessibility -> Keyboard -> uncheck 'Full Keyboard Access'")
    except Exception as e:
        print("Error reading Full Keyboard Access:", e)

    discordBotProc = None
    prevDiscordBotToken = None
    prevRunState = run.value  # Track previous run state for GUI updates
    autoStopStartTime = None
    autoStopDeadline = None
    autoStopHours = 0.0
    
    # Initialize Rich Presence Manager
    richPresenceManager = None
    
    # Cache settings for main GUI loop to avoid reloading every 0.5 seconds
    gui_settings_cache = {}
    last_gui_settings_load = 0
    gui_settings_cache_duration = 1.0  # Reload settings every 1 second max

    def parseAutoStopHours(settings):
        try:
            hours = float(settings.get("auto_stop_after", 0) or 0)
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, hours)

    while True:
        eel.sleep(0.5)
        
        # Get cached settings
        current_time = time.time()
        if current_time - last_gui_settings_load > gui_settings_cache_duration:
            gui_settings_cache = settingsManager.loadAllSettings()
            last_gui_settings_load = current_time
        setdat = gui_settings_cache

        if autoStopStartTime is not None and run.value in (2, 4, 6):
            latestAutoStopHours = parseAutoStopHours(setdat)
            if latestAutoStopHours != autoStopHours:
                autoStopHours = latestAutoStopHours
                autoStopDeadline = autoStopStartTime + (autoStopHours * 3600) if autoStopHours > 0 else None

        if autoStopDeadline is not None and run.value in (2, 4, 6) and current_time >= autoStopDeadline:
            logger.webhook(
                "Macro Auto Stopped",
                f"Stopped after {autoStopHours:g} hour{'s' if autoStopHours != 1 else ''}.",
                "orange",
            )
            run.value = 0

        #discord bot. Look for changes in the bot token
        currentDiscordBotToken = setdat.get("discord_bot_token", "")
        if setdat.get("discord_bot", False) and currentDiscordBotToken and currentDiscordBotToken.strip() and currentDiscordBotToken != prevDiscordBotToken:
            if discordBotProc is not None and discordBotProc.is_alive():
                print("Detected change in discord bot token, killing previous bot process")
                discordBotProc.terminate()
                discordBotProc.join()
            discordBotProc = multiprocessing.Process(target=discordBot, args=(currentDiscordBotToken, run, status, skipTask, recentLogs, pin_requests, updateGUI), daemon=True)
            prevDiscordBotToken = currentDiscordBotToken
            discordBotProc.start()

        # Discord Rich Presence - Initialize and always show status
        discord_rp_enabled = setdat.get("discord_rich_presence", False)
        
        if richPresenceManager is None and discord_rp_enabled:
            # Initialize Rich Presence Manager
            richPresenceManager = RichPresenceManager(status, enabled=True, presence_value=presence)
            richPresenceManager.start()
            print("Discord Rich Presence started")
        elif richPresenceManager is not None:
            # Update settings if they changed
            richPresenceManager.set_enabled(discord_rp_enabled)
            
            # Update status based on macro run state
            if run.value == 0 or run.value == 3:  # Stopped
                # Clear any presence override and show "On main menu" when not running
                try:
                    if presence is not None:
                        presence.value = ""
                except Exception:
                    pass
                if status.value != "idle_main_menu":
                    status.value = "idle_main_menu"
            elif run.value == 6:  # Paused
                # Show "Paused" status
                if status.value != "paused":
                    status.value = "paused"

        # Check if run state changed
        if run.value != prevRunState:
            # Check for resume (transition from paused to running)
            if prevRunState == 6 and run.value == 2:
                try:
                    appManager.openApp("Roblox")
                except Exception:
                    pass
                logger.webhook("Macro Resumed", "Fuzzy Macro", "bright green")
            # Check for pause (transition from running to paused)
            elif prevRunState == 2 and run.value == 6:
                keyboardModule.releaseMovement()
                mouse.mouseUp()
                logger.webhook("Macro Paused", "Use F2 or /resume to continue", "orange")

            gui.setRunState(run.value)
            try:
                gui.toggleStartStop()  # Update UI
            except:
                pass  # If eel is not ready, continue
            prevRunState = run.value

        if run.value == 1:
            #create and set webhook obj for the logger
            logger.enableWebhook = setdat.get("enable_webhook", False)
            logger.webhookURL = setdat.get("webhook_link", "")
            logger.sendScreenshots = setdat.get("send_screenshot", True)
            stopThreads = False

            #reset hourly report data
            hourlyReport = HourlyReport()
            hourlyReport.resetAllStats()
            #stream
            def waitForStreamURL():
                #wait for up to 15 seconds for the public link
                for _ in range(150):
                    time.sleep(0.1)
                    if stream.publicURL:
                        logger.webhook("Stream Started", f'Stream URL: {stream.publicURL}', "purple")
                        
                        # If bot is enabled, request pinning of the stream message
                        if setdat.get("discord_bot", False) and setdat.get("pin_stream_url", False):
                            import modules.logging.webhook as webhookModule
                            if webhookModule.last_channel_id:
                                try:
                                    pin_requests.put({
                                        'channel_id': webhookModule.last_channel_id,
                                        'search_text': 'Stream URL'
                                    })
                                    print("Pin request queued for stream URL message")
                                except Exception as e:
                                    print(f"Error queueing pin request: {e}")
                        return

                logger.webhook("", f'Stream could not start. Check terminal for more info', "red", ping_category="ping_critical_errors")

            streamLink = None
            if setdat.get("enable_stream", False):
                if stream.isCloudflaredInstalled():
                    logger.webhook("", "Starting Stream...", "light blue")
                    streamLink = stream.start(setdat.get("stream_resolution", 0.75))
                    Thread(target=waitForStreamURL, daemon=True).start()
                else:
                    messageBox.msgBox(text='Cloudflared is required for streaming but is not installed. Visit https://fuzzy-team.gitbook.io/fuzzy-macro/discord-setup/stream-setup for installation instructions', title='Cloudflared not installed')

            print("starting macro proc")
            #check if user enabled field drift compensation but sprinkler is not supreme saturator
            fieldSettings = settingsManager.loadFields()
            sprinkler = setdat["sprinkler_type"]
            for field in setdat.get("fields", []):
                fs = fieldSettings.get(field, {})
                if fs.get("field_drift_compensation", False) and setdat.get("sprinkler_type") != "saturator":
                    messageBox.msgBox(title="Field Drift Compensation", text=f"You have Field Drift Compensation enabled for {field} field, \
                                    but you do not have Supreme Saturator as your sprinkler type in configs.\n\
                                    Field Drift Compensation requires you to own the Supreme Saturator.\n\
                                    Kindly disable field drift compensation if you do not have the Supreme Saturator")
                    break
            #check if blender is enabled but there are no items to craft
            validBlender = not setdat["blender_enable"] #valid blender set to false if blender is enabled, else its true since blender is disabled
            for i in range(1, macroModule.BLENDER_ITEM_SLOTS + 1):
                if setdat[f"blender_item_{i}"] != "none" and (setdat[f"blender_repeat_{i}"] or setdat[f"blender_repeat_inf_{i}"]):
                    validBlender = True
            if not validBlender:
                messageBox.msgBox(title="Blender", text=f"You have blender enabled, \
                                    but there are no more items left to craft.\n\
				                    Check the 'repeat' setting on your blender items and reset blender data.")
            #macro proc
            macroProc = multiprocessing.Process(target=macro, args=(status, logQueue, updateGUI, run, skipTask, presence), daemon=True)
            macroProc.start()

            macro_version = settingsManager.getMacroVersion()
            logger.webhook("Macro Started", f'Fuzzy Macro v{macro_version}\nDisplay: {screenInfo["display_type"]}, {screenInfo["screen_width"]}x{screenInfo["screen_height"]}', "purple")
            run.value = 2
            autoStopStartTime = time.time()
            autoStopHours = parseAutoStopHours(setdat)
            autoStopDeadline = autoStopStartTime + (autoStopHours * 3600) if autoStopHours > 0 else None
            gui.setRunState(2)  # Update the global run state
            try:
                gui.toggleStartStop()  # Update UI
            except:
                pass  # If eel is not ready, continue
            try:
                gui.toggleStartStop()  # Update UI
            except:
                pass  # If eel is not ready, continue
        elif run.value == 0:
            had_macro_proc = bool(macroProc)
            autoStopStartTime = None
            autoStopDeadline = None
            autoStopHours = 0.0

            # Stop macro/tools and release all inputs first.
            gui.setRunState(0)
            try:
                gui.toggleStartStop()
            except:
                pass

            if had_macro_proc:
                logger.webhook("Macro Stopped", "Fuzzy Macro", "red")
            try:
                gui.stopAllTools()
            except Exception:
                pass

            stopApp()

            run.value = 3
            gui.setRunState(3)
            try:
                gui.toggleStartStop()
            except:
                pass

            if not had_macro_proc:
                continue

            # Generate and send final report AFTER stopping inputs
            try:
                print("Generating final report...")
                from modules.submacros.finalReport import FinalReport
                import os
                
                # Create final report object
                finalReportObj = FinalReport()
                sessionStats = finalReportObj.generateFinalReport(setdat)
                
                # Check if report was generated successfully
                if sessionStats and os.path.exists("finalReport.png"):
                    # Format session summary for webhook
                    sessionTime = sessionStats.get("total_session_time", 0)
                    hours = int(sessionTime / 3600)
                    minutes = int((sessionTime % 3600) / 60)
                    timeStr = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
                    
                    totalHoney = sessionStats.get("total_honey", 0)
                    avgHoneyPerHour = sessionStats.get("avg_honey_per_hour", 0)
                    
                    def millify(n):
                        """Format large numbers with suffixes"""
                        if n < 1000:
                            return str(int(n))
                        elif n < 1000000:
                            return f"{n/1000:.1f}K"
                        elif n < 1000000000:
                            return f"{n/1000000:.1f}M"
                        elif n < 1000000000000:
                            return f"{n/1000000000:.1f}B"
                        else:
                            return f"{n/1000000000000:.1f}T"
                    
                    # Add "Estimated" label if session was less than 1 hour
                    avgLabel = "Est. Avg/Hour" if sessionTime < 3600 else "Avg/Hour"
                    description = f"Runtime: {timeStr}\nTotal Honey: {millify(totalHoney)}\n{avgLabel}: {millify(avgHoneyPerHour)}"
                    
                    # Send final report webhook
                    logger.finalReport("Session Complete", description, "purple")
                    print("Final report sent successfully")
                else:
                    print("Failed to generate final report - no data available")
                    
            except Exception as e:
                print(f"Error generating final report: {e}")
                import traceback
                traceback.print_exc()
        elif run.value == 4: #disconnected
            if macroProc and macroProc.is_alive():
                macroProc.kill()
                macroProc.join()
            logger.webhook("","Disconnected", "red", "screen", ping_category="ping_disconnects")
            appManager.closeApp("Roblox")
            keyboardModule.releaseMovement()
            mouse.mouseUp()
            macroProc = multiprocessing.Process(target=macro, args=(status, logQueue, updateGUI, run, skipTask, presence), daemon=True)
            macroProc.start()
            run.value = 2
            gui.setRunState(2)  # Update the global run state
            try:
                gui.toggleStartStop()  # Update UI
            except:
                pass  # If eel is not ready, continue
        # Note: run.value == 6 (paused) is handled in the macro process loop - it waits for resume
        
        # Check for crash (non-zero exitcodes). Log signal name to aid diagnosis.
        if macroProc and not macroProc.is_alive() and hasattr(macroProc, "exitcode") and macroProc.exitcode is not None and macroProc.exitcode != 0:
            exitcode = macroProc.exitcode
            try:
                import signal
                if exitcode < 0:
                    signum = -exitcode
                    try:
                        signame = signal.Signals(signum).name
                    except Exception:
                        signame = str(signum)
                    extra = f" (terminated by signal {signame})"
                else:
                    extra = ""
            except Exception:
                extra = ""
            print(f"Macro process exited{extra}")
            logger.webhook("","Macro Crashed{0}".format(extra), "red", "screen", ping_category="ping_critical_errors")
            macroProc.join()
            appManager.openApp("Roblox")
            keyboardModule.releaseMovement()
            mouse.mouseUp()
            # restart macro process
            macroProc = multiprocessing.Process(target=macro, args=(status, logQueue, updateGUI, run, skipTask, presence), daemon=True)
            macroProc.start()
            run.value = 2
            gui.setRunState(2)  # Update the global run state
            try:
                gui.toggleStartStop()  # Update UI
            except:
                pass  # If eel is not ready, continue

        #detect a new log message
        if not logQueue.empty():
            logData = logQueue.get()
            if logData["type"] == "webhook": #webhook
                msg = f"{logData['title']}<br>{logData['desc']}"

                # Add to recent logs list (keep last 100 entries)
                log_entry = {
                    'time': logData['time'],
                    'title': logData['title'],
                    'desc': logData['desc'],
                    'color': logData['color']
                }
                recentLogs.append(log_entry)
                # Keep only the last 100 entries. Manager proxies can fail
                # if the manager process closes; guard with fallbacks.
                if len(recentLogs) > 100:
                    try:
                        # fast path: use slice operations on proxy
                        recentLogs[:] = recentLogs[-100:]
                    except Exception:
                        # fallback: build a local snapshot and replace contents
                        try:
                            snapshot = list(recentLogs)
                            snapshot = snapshot[-100:]
                            # clear and extend the proxy list in-place
                            try:
                                del recentLogs[:]
                                recentLogs.extend(snapshot)
                            except Exception:
                                # best-effort: if in-place replace fails, attempt to set by index
                                for i, v in enumerate(snapshot):
                                    if i < len(recentLogs):
                                        recentLogs[i] = v
                                    else:
                                        recentLogs.append(v)
                        except Exception:
                            # give up silently to avoid crashing the main loop
                            pass

            #add it to gui
            gui.log(logData["time"], msg, logData["color"])
        
        #detect if the gui needs to be updated
        if updateGUI.value:
            gui.updateGUI()
            updateGUI.value = 0
        
        if run.value == 2 and time.time() > disconnectCooldownUntil:
            img = adjustImage("./images/menu", "disconnect", screenInfo["display_type"])
            wmx, wmy, wmw, wmh = getWindowSize("roblox roblox")
            if locateImageOnScreen(img, wmx+wmw/3, wmy+wmh/2.8, wmw/2.3, wmh/5, 0.7):
                print("disconnected")
                run.value = 4
                disconnectCooldownUntil = time.time() + 300  # 5 min cooldown
