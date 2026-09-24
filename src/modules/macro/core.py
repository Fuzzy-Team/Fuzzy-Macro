import ast
import json
import threading
from datetime import datetime
import modules.controls.mouse as mouse
import modules.logging.log as logModule
import modules.misc.appManager as appManager
import modules.misc.settingsManager as settingsManager
from modules.controls.keyboard import keyboard
from modules.controls.sleep import (
    get_interrupt_action,
    INTERRUPT_NONE,
    InterruptRequested,
    pause_aware_time as time,
    set_interrupt_action,
    set_resume_callback,
    set_run_state,
)
from modules.macro.game_data import mergedCollectData, PING_SETTING_KEYS
from modules.misc import messageBox
from modules.screen.robloxWindow import RobloxWindowBounds
from modules.screen.screenshot import benchmarkMSS, mssScreenshot
from modules.submacros.fieldDriftCompensation import (
    fieldDriftCompensation as fieldDriftCompensationClass,
)
from modules.submacros.hasteCompensation import HasteCompensationRevamped
from modules.reports.buffs import BuffDetector
from modules.reports.hourly import HourlyReport
from modules.reports.item_monitor import ItemMonitor
from modules.submacros.memoryMatch import MemoryMatch
from modules.submacros.tadAltSync import TadAltSync
from modules.macro.shift_lock import ShiftLockMixin
from modules.macro.events import EventDetectionMixin
from modules.macro.sprouts import SproutMixin
from modules.macro.screen import ScreenMixin
from modules.macro.navigation import NavigationMixin
from modules.macro.collectibles import CollectiblesMixin
from modules.macro.inventory import InventoryMixin
from modules.macro.hive import HiveMixin
from modules.macro.rejoin import RejoinMixin
from modules.macro.reports import ReportMixin
from modules.macro.gather import GatherMixin
from modules.macro.mobs import MobMixin
from modules.macro.planters import PlanterMixin
from modules.macro.quests import QuestMixin
from modules.macro.quest_objectives import QuestObjectiveMixin
from modules.macro.afb import AFBMixin


class macro(
    ShiftLockMixin,
    EventDetectionMixin,
    SproutMixin,
    ScreenMixin,
    NavigationMixin,
    CollectiblesMixin,
    InventoryMixin,
    HiveMixin,
    RejoinMixin,
    ReportMixin,
    GatherMixin,
    MobMixin,
    PlanterMixin,
    QuestMixin,
    QuestObjectiveMixin,
    AFBMixin,
):
    def __init__(self, status, logQueue, updateGUI, run=None, skipTask=None, presence=None, discordMessageQueue=None, skipServer=None):
        self.status = status
        self.presence = presence
        self.updateGUI = updateGUI
        self.run = run
        self.skipTask = skipTask
        self.skipServer = skipServer
        
        # Set the run state for pause-aware sleep functions
        if run is not None:
            set_run_state(run)
            set_resume_callback(self._redetect_y_offset_after_resume)
        if skipTask is not None:
            set_interrupt_action(skipTask)
        
        profileSnapshot = settingsManager.getMacroProfileSnapshot()
        self.setdat = profileSnapshot["settings"]
        self.fieldSettings = profileSnapshot["fields"]
        # Track the published snapshot, including changes made by other adapters.
        self._last_profile_version = profileSnapshot["version"]
        self._last_profile_name = profileSnapshot["profile"]
        self._reportedProfileProblems = []

        self.robloxWindow = RobloxWindowBounds()
        
        self.hasteCompensation = HasteCompensationRevamped(self.robloxWindow, self.setdat["movespeed"])
        self.fieldDriftCompensation = fieldDriftCompensationClass(self.robloxWindow)
        self.keyboard = keyboard(self.setdat["movespeed"], self.setdat["haste_compensation"], self.hasteCompensation)
        pingSettings = {key: self.setdat.get(key, False) for key in PING_SETTING_KEYS}
        
        self.logger = logModule.log(logQueue, logModule.delivery_uses_webhook(self.setdat), logModule.get_default_delivery_route(self.setdat), self.setdat.get("send_screenshot", True), blocking=self.setdat.get("low_performance", False), hourlyReportOnly=self.setdat.get("only_send_hourly_report", False), robloxWindow=self.robloxWindow, enableDiscordPing=True, discordUserID=self.setdat.get("discord_user_id", ""), pingSettings=pingSettings, webhookTimeFormat=self.setdat.get("webhook_time_format", 24), enableDiscordBot=logModule.delivery_uses_bot_messages(self.setdat), discordMessageQueue=discordMessageQueue, routeSettings=logModule.build_route_settings(self.setdat))
        self.tadAltSync = TadAltSync(
            self.setdat,
            self.logger,
            use_glitter=self.useGlitterFromSlot,
        )
        self._fieldBoosterGlitterGeneration = 0
        self._fieldBoosterGlitterLock = threading.Lock()
        self._fieldBoosterGlitterPending = None
        self.reportProfileProblems(profileSnapshot)
        self.buffDetector = BuffDetector(self.robloxWindow)
        self.hourlyReport = HourlyReport(self.buffDetector, self.setdat.get("hourly_report_time_format", 24))
        self.itemMonitor = ItemMonitor(self.robloxWindow)
        self.memoryMatch = MemoryMatch(self.robloxWindow, debug=True)

        self._applySettingsState()
        self.canDetectNight = True
        self.night = False
        self.location = "spawn"

        self.planterCooldowns = {}

        #memory match
        self.latestMM = "normal"
        self.lastBlueTextScan = 0
        self.guidingStarLastAnnounced = {}
        self.unusualSproutLastAnnounced = {}
        self.windyBeeLastAnnounced = {}
        self.stickerSproutDetectedAt = 0
        self.stickerSproutLastAnnounced = 0
        self.stickerSproutInterruptRequested = False
        self.sproutBeansUsed = 0
        self.lastSproutBeanLimitLog = 0

        self.isGathering = False
        self.converting = False
        self.alreadyConverted = False
        self.cannonFromHive = False
        self._inactiveHoneyResetResumeBlockUntil = 0.0

        #auto field boost
        self.failed = False
        self.AFBLIMIT = False
        self.AFBglitter = False
        self.cAFBglitter = False
        self.cAFBDice = False
        self.afb = False
        self.stop = False

        self.hiveSlotTiles = 9.75 #distance between hive slots (in tiles)


        self.setRobloxWindowInfo(setYOffset=False)

    def reportProfileProblems(self, profileSnapshot):
        """Report settings that couldn't be read (defaults are used for them) once, and again if they change."""
        problems = profileSnapshot.get("migration_errors", []) + profileSnapshot.get("warnings", [])
        if problems == self._reportedProfileProblems:
            return
        self._reportedProfileProblems = problems
        if problems:
            self.logger.webhook(
                "Settings Problem",
                f"Profile '{profileSnapshot['profile']}' has settings that couldn't be read, so defaults are used for them:\n" + "\n".join(f"- {problem}" for problem in problems),
                "red",
                ping_category="ping_critical_errors",
            )

    def checkAndReloadSettings(self):
        """Reload settings for a new loop pass and apply profile changes"""
        profileSnapshot = settingsManager.getMacroProfileSnapshot()
        # Start every pass from the saved settings so quest overrides do not carry over.
        self.setdat = profileSnapshot["settings"]
        self.reportProfileProblems(profileSnapshot)
        profileChanged = profileSnapshot["profile"] != self._last_profile_name
        settingsChanged = (
            profileChanged
            or profileSnapshot["version"] != self._last_profile_version
        )
        if settingsChanged:
            self._last_profile_version = profileSnapshot["version"]
            self._last_profile_name = profileSnapshot["profile"]
            if profileChanged or not self.setdat.get("field_booster_glitter_extend_enabled", False):
                with self._fieldBoosterGlitterLock:
                    self._fieldBoosterGlitterGeneration += 1
                    self._fieldBoosterGlitterPending = None
            self.tadAltSync.update_settings(self.setdat)
            self.fieldSettings = profileSnapshot["fields"]
            # Update logger with new webhook settings
            pingSettings = {key: self.setdat.get(key, False) for key in PING_SETTING_KEYS}
            self.logger.enableWebhook = logModule.delivery_uses_webhook(self.setdat)
            self.logger.enableDiscordBot = logModule.delivery_uses_bot_messages(self.setdat)
            self.logger.webhookURL = logModule.get_default_delivery_route(self.setdat)
            self.logger.routeSettings = logModule.build_route_settings(self.setdat)
            self.logger.sendScreenshots = self.setdat.get("send_screenshot", True)
            self.logger.enableDiscordPing = True
            self.logger.discordUserID = self.setdat.get("discord_user_id", "")
            self.logger.pingSettings = pingSettings
            self.logger.webhookTimeFormat = self.setdat.get("webhook_time_format", 24)
            self.logger.hourlyReportOnly = self.setdat["only_send_hourly_report"]
            # Update movement settings while keeping the boolean enable flag
            # separate from the compensation object used by keyboard.getMoveSpeed().
            self.hasteCompensation = HasteCompensationRevamped(self.robloxWindow, self.setdat["movespeed"])
            self.keyboard.ws = self.setdat["movespeed"]
            self.keyboard.enableHasteCompensation = bool(self.setdat["haste_compensation"])
            self.keyboard.hasteCompensation = self.hasteCompensation
            # Update hourly report time format
            self.hourlyReport.timeFormat = self.setdat.get("hourly_report_time_format", 24)
            self._applySettingsState()
            if profileChanged:
                self.logger.webhook(
                    "Profile Changed",
                    f"Switched to profile: {profileSnapshot['profile']}",
                    "blue",
                )

    def _applySettingsState(self):
        """State derived from settings, rebuilt whenever settings reload."""
        self.collectCooldowns = {k: v[2] for k, v in mergedCollectData.items()}
        self.collectCooldowns["sticker_printer"] = 1*60*60
        self.enableNightDetection = bool(self.setdat["stinger_hunt"])
        #fields vic can appear in, filtered to the ones the player enabled
        vicFields = ["pepper", "mountain top", "rose", "cactus", "spider", "clover"]
        self.vicFields = [x for x in vicFields if self.setdat["stinger_{}".format(x.replace(" ","_"))]]

    #get the size of the roblox window and update the relevant variables
    def setRobloxWindowInfo(self, setYOffset=True):
        self.robloxWindow.setRobloxWindowBounds(setYOffset=setYOffset)
        if setYOffset:
            self.logger.webhook("", f"Detect Y Offset: {self.robloxWindow.contentYOffset}", "dark brown")

    def _redetect_y_offset_after_resume(self):
        self.setRobloxWindowInfo(setYOffset=True)

    def set_task_status(self, status_key=None, *, update_presence=True, **presence):
        """Set the GUI status and, optionally, the Discord presence (activity, task, field, state, details)."""
        self.status.value = status_key or ""
        if not update_presence or self.presence is None:
            return
        payload = {k: v for k, v in presence.items() if v} or {"activity": status_key}
        try:
            self.presence.value = f"rp:{json.dumps(payload)}" if status_key else ""
        except Exception:
            pass

    def clear_task_status(self):
        self.set_task_status(None)

    def raiseIfInterrupted(self):
        action = get_interrupt_action()
        if action != INTERRUPT_NONE:
            raise InterruptRequested(action)

    def checkPauseAndWait(self):
        """Check if macro is paused and wait until resumed. Returns True if stop was requested."""
        if self.run is None:
            return False
        self.raiseIfInterrupted()
        # Wait while paused (state 6)
        wasPaused = False
        while self.run.value == 6:
            wasPaused = True
            self._inactiveHoneyResetResumeBlockUntil = time.monotonic() + 2
            # Keep inputs released while paused
            self.keyboard.releaseMovement()
            mouse.mouseUp()
            time.sleep(0.1)
            self.raiseIfInterrupted()
        if wasPaused:
            self._inactiveHoneyResetResumeBlockUntil = time.monotonic() + 2
            self._redetect_y_offset_after_resume()
        # Check if stop was requested (state 0)
        return self.run.value == 0

    def isInactiveHoneyResetPaused(self):
        if self.run is not None and self.run.value == 6:
            self._inactiveHoneyResetResumeBlockUntil = time.monotonic() + 2
            return True
        return time.monotonic() < self._inactiveHoneyResetResumeBlockUntil

    def getTiming(self,name = None):
        timings_path = settingsManager.getUserDataPath("timings.txt")
        for _ in range(3):
            data = settingsManager.readSettingsFile(timings_path)
            if data: break #most likely another process is writing to the file
            time.sleep(0.1)
        if name is not None:
            if not name in data:
                print(f"could not find timing for {name}, setting a new one")
                settingsManager.saveSettingFile(name, 0, timings_path)
                return 0
            return data[name]
        return data

    def saveTiming(self, name):
        return settingsManager.saveSettingFile(name, time.time(), settingsManager.getUserDataPath("timings.txt"))

    #returns true if the cooldown is up
    #note that cooldown is in seconds
    def hasRespawned(self, name, cooldown, applyMobRespawnBonus = False, timing = None):
        if timing is None: timing = self.getTiming(name)
        if not isinstance(timing, float) and not isinstance(timing, int):
            print(f"Timing is not a valid number? {timing}")
        mobRespawnBonus = 1
        if applyMobRespawnBonus:
            mobRespawnBonus -= 0.15 if self.setdat["gifted_vicious"] else 0
            mobRespawnBonus -= self.setdat["stick_bug_amulet"]/100 
            mobRespawnBonus -= self.setdat["icicles_beequip"]/100 
    
        return time.time() - timing >= cooldown*mobRespawnBonus

    def getCurrentMinute(self):
        return datetime.now().minute

    def backgroundOnce(self):
        with open(settingsManager.ensureUserFile("hotbar_timings.txt"), "r") as f:
            hotbarSlotTimings = ast.literal_eval(f.read())

        #night detection
        if self.enableNightDetection:
            self.detectNight()
        self.scanBlueTextAnnouncements()

        #hotbar
        for i in range(1,8):
            slotUseWhen = self.setdat[f"hotbar{i}_use_when"]
            #check if use when is correct
            if slotUseWhen == "never":
                continue
            elif self.status.value == "rejoining":
                continue
            # Only use hotbar slots configured for 'Gathering' when the macro
            # is actively gathering in-field (self.isGathering True). This
            # prevents hotbar items being used while preparing/traveling to
            # a field before the gather actually begins.
            elif slotUseWhen == "gathering" and not getattr(self, "isGathering", False):
                continue
            elif slotUseWhen == "converting" and not self.status.value == "converting":
                continue
            elif slotUseWhen == "attacking" and not self.status.value == "attacking":
                continue
            # If 'always', or matches any of the above, allow
            #check cd
            cdSecs = self.setdat[f"hotbar{i}_use_every_value"]
            if self.setdat[f"hotbar{i}_use_every_format"] == "mins": 
                cdSecs *= 60
            if time.time() - hotbarSlotTimings[i] < cdSecs: continue
            if not self.canUseSproutBeanSlot(i):
                continue
            sproutHotbarSlot = False
            if self.setdat.get("sprouts_enable", False):
                try:
                    sproutHotbarSlot = int(self.setdat.get("sprouts_magic_bean_slot", 1) or 1) == i
                except Exception:
                    sproutHotbarSlot = False
                if sproutHotbarSlot and self.sproutBeansUsed + 2 > self._sproutBeanLimit():
                    continue
            print(f"pressed hotbar {i}")
            #press the key
            for _ in range(2):
                keyboard.pagPress(str(i))
                time.sleep(0.4)
            if sproutHotbarSlot:
                self.markSproutBeanUsed()
                self.markSproutBeanUsed()
            #update the time pressed
            hotbarSlotTimings[i] = time.time()
            with open(settingsManager.getUserDataPath("hotbar_timings.txt"), "w") as f:
                f.write(str(hotbarSlotTimings))
            f.close()

    def background(self):
        while True:
            self.backgroundOnce()
            time.sleep(1)

    def mergedBackgrounds(self):
        while True:
            self.backgroundOnce()
            self.hourlyReportBackgroundOnce()
            time.sleep(1)

    def startDetect(self):
        #disable game mode
        self.moveMouseToDefault()
        time.sleep(1)
        #check roblox scaling
        #this is done by checking if all pixels at the top of the screen are black
        topScreen = mssScreenshot(0, 0, self.robloxWindow.mw, 2)
        extrema = topScreen.convert("L").getextrema()
        #all are black
        if extrema == (0, 0):
            messageBox.msgBox(text='It seems like you have not enabled roblox scaling. The macro will not work properly.\n1. Close Roblox\n2. Go to finder -> applications -> right click roblox -> get info -> enable "scale to fit below built-in camera"', title='Roblox scaling')
        time.sleep(1)
        self.moveMouseToDefault()

        #check for accessibility
        #this is done by taking 2 different screenshots
        #if they are both the same, we assume that the keypress didnt go through and hence accessibility is not enabled
        originalX = mouse.getPos()[0]
        mouse.moveBy(100, 0)
        time.sleep(0.15)
        newX = mouse.getPos()[0]
        if originalX == newX:
            messageBox.msgBox(text='It seems like terminal does not have the accessibility permission. The macro will not work properly.\n\nTo fix it, go to System Settings -> Privacy and Security -> Accessibility -> add and enable Terminal.\n\nVisit https://fuzzy-team.gitbook.io/fuzzy-macro/common-fixes/terminal-permissions for detailed instructions\n\n NOTE: This popup might be incorrect. If the macro is able to input keypresses and interact with the game, you can dismiss this popup', title='Accessibility Permission')
        time.sleep(1)

    def start(self):
        print("macro object started")
        self.resetAFBSessionTimings()

        if self.setdat.get("macro_mode", "normal") != "alt":
            self.tadAltSync.initialize_alts()

        #enable background threads
        self.nightDetectStreaks = 0
        self.hourlyReport.loadHourlyReportData()
        if getattr(self.hourlyReport, "itemMonitorSnapshot", None):
            self.itemMonitor.load_snapshot(self.hourlyReport.itemMonitorSnapshot)
        self.prevMin = -1  
        self.prevSec = -1
        self.prevItemMonitorSec = -1
        self.multi = self.robloxWindow.multi
        self.lastHourlyReport = 0

        if self.setdat["low_performance"]:
            mergedBackgroundThread = threading.Thread(target=self.mergedBackgrounds, daemon=True)
            mergedBackgroundThread.start()
        else:
            backgroundThread = threading.Thread(target=self.background, daemon=True)
            backgroundThread.start()

            hourlyReportBackgroundThread = threading.Thread(target=self.hourlyReportBackground, daemon=True)
            hourlyReportBackgroundThread.start()
        
        # Rejoin at startup unless Roblox is already open and the user has
        # explicitly disabled Always Rejoin.
        if self.setdat.get("always_rejoin", True) or not appManager.openApp("Roblox"):
            self.rejoin()
        else:
            self.startDetect()
            self.setRobloxWindowInfo()
    
        if not benchmarkMSS():
            self.logger.webhook("", "MSS is too slow, switching to pillow", "dark brown")
        
        if not self.hourlyReport.hourlyReportStats["start_time"] or not self.hourlyReport.hourlyReportStats["start_honey"]:
            self.hourlyReport.setSessionStats(self.getHoney(), time.time())

        self.reset(convert=True)
        self.saveTiming("rejoin_every")
