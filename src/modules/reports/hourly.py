"""Collect hourly and session stats and build the hourly report."""
import ast
import copy
import numpy as np
import os
import pickle
import time
from modules.misc import settingsManager
from modules.misc.settingsManager import loadFields
from modules.reports.buffs import (
    BuffDetector,
    expandUptimeBuffDataKeys,
    normalizeHourlyBuffSelection,
    normalizeUptimeBuffSelection,
)
from modules.reports.drawer import HourlyReportDrawer
from modules.reports.theme import resolveReportTheme


class HourlyReport():
    def __init__(self, buffDetector: BuffDetector = None, time_format=24, theme="dark", accent="green", configuredUptimeBuffs=None, configuredHourlyBuffs=None):
        self.configuredUptimeBuffs = normalizeUptimeBuffSelection(configuredUptimeBuffs)
        self.configuredHourlyBuffs = normalizeHourlyBuffSelection(configuredHourlyBuffs)

        # hourly snapshot buff detection config (template-based)
        # key → [position, transform, stackable]
        self.hourBuffs = {k: ["top", True, True] for k in self.configuredHourlyBuffs if k not in ("tide_blessing", "mondo")}
        self.hourBuffs.update({
            "tabby_love":   ["top",    True, True],
            "polar_power":  ["top",    True, True],
            "wealth_clock": ["top",    True, True],
            "blessing":     ["top",    True, True],
            "bloat":        ["top",    True, True],
            "tide_blessing":["top",    True, True],
            "mondo":        ["top",    True, True],
        })
        # keep only the buffs that are actually configured
        self.hourBuffs = {k: v for k, v in self.hourBuffs.items() if k in self.configuredHourlyBuffs}

        self.uptimeBearBuffs = {
            "bearmorph1": ["top", True, False],
            "bearmorph2": ["top", True, False],
            "bearmorph3": ["top", True, False],
            "bearmorph4": ["top", True, False],
            "bearmorph5": ["top", True, False],
            "bearmorph6": ["top", True, False],
        }

        # pixel-color detection for continuous uptime buffs
        self.uptimeBuffsColors = {
            "baby_love":    [0xff8de4f3, (5, 1)],
            "haste":        [0xfff0f0f0, (5, 1)],
            "melody":       [0xff242424, (3, 2)],
            "focus":        [0xff22ff06, (5, 1)],
            "bomb_combo":   [0xff272727, (5, 1)],
            "balloon_aura": [0xfffafd38, (5, 1)],
            "boost":        [0xff90ff8e, (5, 1)],
            "blue_boost":   [0xff56a4e4, (4, 2)],
            "red_boost":    [0xffe46156, (4, 2)],
            "inspire":      [0xfff4ef14, (5, 1)],
            # new buffs — colors for pixel detection (added to extend detection support)
            "reindeerfetch":[0xffcc2c2c, (5, 1)],
            "wealth_clock": [0xffe2ac35, (5, 1)],
            "tide_blessing":[0xff91c2fd, (5, 1)],
            "mondo":        [0xff80ff00, (5, 1)],
            "blessing":     [0xffc8ca3c, (5, 1)],
            "bloat":        [0xff4880cc, (4, 1)],
            "honey_mark":   [0xffffd119, (5, 1)],
            "pollen_mark":  [0xffffe994, (5, 1)],
            "jb_share":     [0xfff9ccff, (5, 1)],
            "festive_mark": [0xffc84335, (5, 1)],
            "popstar":      [0xff0096ff, (5, 1)],
            "scorching_star": [0xffff3400, (5, 1)],
            "gummy_star":   [0xfff191ff, (5, 1)],
            "guiding":      [0xffffff80, (5, 1)],
        }
        # The in-game buff icons are sampled from a very small strip, and their
        # edge pixels vary with display scale, bloom, and background overlap.
        # These tolerances are tuned from the checked-in samples/ screenshots.
        self.uptimeBuffsColorVariations = {
            "baby_love": 8,
            "haste": 8,
            "melody": 5,
            "focus": 6,
            "bomb_combo": 5,
            "balloon_aura": 8,
            "boost": 8,
            "blue_boost": 8,
            "red_boost": 8,
            "inspire": 8,
            "reindeerfetch": 8,
            "wealth_clock": 10,
            "tide_blessing": 10,
            "mondo": 10,
            "blessing": 10,
            "bloat": 10,
            "honey_mark": 8,
            "pollen_mark": 8,
            "jb_share": 8,
            "festive_mark": 8,
            "popstar": 8,
            "scorching_star": 30,
            "gummy_star": 30,
            "guiding": 8,
        }

        self.buffDetector = buffDetector
        self.hourlyReportDrawer = HourlyReportDrawer(time_format, theme=theme, accent=accent)

        # store theme/accent for re-applying when settings change
        self._theme = theme
        self._accent = accent

        # setup stats
        self.hourlyReportStats = {}
        self.sessionReportStats = {}
        self.sessionUptimeBuffsValues = {}
        self.sessionBuffGatherIntervals = []
        self.latestBuffQuantity = []
        self.latestBuffKeys = []
        self.latestNectarQuantity = []
        self.lastEmbedFields = None
        self.itemMonitorSnapshot = None

    def _defaultSessionReportStats(self):
        return {
            "honey_per_min": [],
            "backpack_per_min": [],
            "bugs": 0,
            "quests_completed": 0,
            "vicious_bees": 0,
            "gathering_time": 0,
            "converting_time": 0,
            "bug_run_time": 0,
            "misc_time": 0,
        }

    def _defaultHourlyUptimeBuffs(self):
        uptimeBuffs = {k:[0]*600 for k in self.uptimeBuffsColors.keys()}
        for k in ["bear", "white_boost"]:
            uptimeBuffs[k] = [0]*600
        return uptimeBuffs

    def _defaultSessionUptimeBuffs(self):
        sessionUptimeBuffs = {k:[] for k in self.uptimeBuffsColors.keys()}
        for k in ["bear", "white_boost"]:
            sessionUptimeBuffs[k] = []
        return sessionUptimeBuffs

    def configuredUptimeBuffDataKeys(self, settings=None):
        rawBuffs = None
        if isinstance(settings, dict):
            rawBuffs = settings.get("hourly_report_uptime_buffs")
        selectedBuffs = normalizeUptimeBuffSelection(rawBuffs, self.configuredUptimeBuffs)
        self.configuredUptimeBuffs = selectedBuffs
        return expandUptimeBuffDataKeys(selectedBuffs)

    def recordUptimeSample(self, index, sampleValues, isGathering=False, monitoredBuffs=None):
        monitored = set(monitoredBuffs or self._defaultSessionUptimeBuffs().keys())
        for buffName in monitored:
            try:
                value = float(sampleValues.get(buffName, 0) or 0)
            except (TypeError, ValueError):
                value = 0
            if value.is_integer():
                value = int(value)
            if buffName not in self.uptimeBuffsValues:
                self.uptimeBuffsValues[buffName] = [0] * 600
            if 0 <= index < len(self.uptimeBuffsValues[buffName]):
                self.uptimeBuffsValues[buffName][index] = value

            if buffName not in self.sessionUptimeBuffsValues:
                self.sessionUptimeBuffsValues[buffName] = []
            self.sessionUptimeBuffsValues[buffName].append(value)

        if not hasattr(self, "buffGatherIntervals") or self.buffGatherIntervals is None:
            self.buffGatherIntervals = [0] * 600
        if 0 <= index < len(self.buffGatherIntervals):
            self.buffGatherIntervals[index] = 1 if isGathering else 0

        if not hasattr(self, "sessionBuffGatherIntervals") or self.sessionBuffGatherIntervals is None:
            self.sessionBuffGatherIntervals = []
        self.sessionBuffGatherIntervals.append(1 if isGathering else 0)

    def filterOutliers(self, values, threshold=3):
        nonZeroValues = [x for x in values if x]
        
        # If no non-zero values or insufficient data, return original values
        if len(nonZeroValues) < 2:
            return values
        
        # Calculate the mean and standard deviation
        mean = np.mean(nonZeroValues)
        std_dev = np.std(nonZeroValues)

        #standard deviation is 0, no outliers, prevent division by zero
        if std_dev == 0:
            return values 
        
        # Calculate Z-scores
        z_scores = [(x - mean) / std_dev for x in values]
        
        # Filter out values with Z-scores greater than the threshold
        filtered_values = [x for x, z in zip(values, z_scores) if abs(z) < threshold or not x]
        
        return filtered_values

    def generateEmbedFields(self, hourlyReportStats, sessionTime, sessionHoney, honeyThisHour, onlyValidHourlyHoney, buffQuantity, nectarQuantity, planterData, reportType="hourly", itemMonitorData=None):
        """Build old-style Discord embed text fields for hybrid embed+image output."""
        def fmt(n):
            return self.hourlyReportDrawer.millify(n).replace(" ", "")
        def fmtTime(s):
            return self.hourlyReportDrawer.displayTime(s, ['h', 'm', 's']).replace(" ", "")
        def pct(part, total):
            return f"{round(part / total * 100, 1)}%" if total else "0%"
        def planterEmoji(planterName):
            return "🪴" if planterName else "🌱"
        def fieldEmoji(fieldName):
            field_emojis = {
                "sunflower": "🌻",
                "dandelion": "🌼",
                "mushroom": "🍄",
                "blue flower": "🔷",
                "clover": "🍀",
                "strawberry": "🍓",
                "spider": "🕷️",
                "bamboo": "🐼",
                "pineapple": "🍍",
                "stump": "🐌",
                "cactus": "🌵",
                "pumpkin": "🎃",
                "pine tree": "🌲",
                "rose": "🌹",
                "mountain top": "⛰️",
                "pepper": "🌶️",
                "coconut": "🥥",
                "hive hub": "🏠",
            }
            normalized_name = fieldName.replace("_", " ").strip().lower()
            return field_emojis.get(normalized_name, "🌼" if normalized_name else "")
        def nectarEmoji(nectarName):
            return {
                "comforting": "🌙",
                "motivating": "🍄",
                "satisfying": "💜",
                "refreshing": "💧",
                "invigorating": "🔥",
            }.get(nectarName, "✨")

        avgHoney = max(0, sessionHoney / (sessionTime / 3600)) if sessionTime > 0 else 0
        currentHoney = onlyValidHourlyHoney[-1] if onlyValidHourlyHoney else 0
        totalTime = max(1, hourlyReportStats.get("gathering_time", 0) + hourlyReportStats.get("converting_time", 0) + hourlyReportStats.get("bug_run_time", 0) + hourlyReportStats.get("misc_time", 0))

        fields = []

        if reportType == "session":
            session_lines = [
                f"🍯 Current: {fmt(currentHoney)}",
                f"🍯 Honey Earned: {fmt(honeyThisHour)}",
                f"🍯 Hourly Average: {fmt(avgHoney)}",
                f"🕓 Duration: {fmtTime(sessionTime)}",
            ]
            fields.append({"name": "Session", "value": "\n".join(session_lines), "inline": False})
        else:
            honeyLines = [
                f"🍯 Honey Earned: {fmt(honeyThisHour)}",
                f"🍯 Hourly Average: {fmt(avgHoney)}",
            ]
            fields.append({"name": "Hourly", "value": "\n".join(honeyLines), "inline": False})

            session_lines = [
                f"🍯 Starting: {fmt(hourlyReportStats.get('start_honey', 0))}",
                f"🍯 Current: {fmt(currentHoney)}",
                f"🍯 Session: {fmt(sessionHoney)}",
                f"🕓 Duration: {fmtTime(sessionTime)}",
            ]
            fields.append({"name": "Session", "value": "\n".join(session_lines), "inline": False})

        # Activity breakdown
        gath = hourlyReportStats.get("gathering_time", 0)
        conv = hourlyReportStats.get("converting_time", 0)
        bug  = hourlyReportStats.get("bug_run_time", 0)
        misc = hourlyReportStats.get("misc_time", 0)
        activity_lines = [
            f"🟢 Gathering: {fmtTime(gath)}",
            f"🟠 Converting: {fmtTime(conv)}",
        ]
        if bug > 0:
            activity_lines.append(f"🔴 Bug Run: {fmtTime(bug)}")
        activity_lines.append(f"🔵 Travelling: {fmtTime(misc)}")
        fields.append({"name": "Activity", "value": "\n".join(activity_lines), "inline": False})

        # Bugs / quests / vicious bees (compact inline)
        stats_parts = []
        if hourlyReportStats.get("bugs", 0):
            stats_parts.append(f"🐛 Bugs: {hourlyReportStats['bugs']}")
        if hourlyReportStats.get("quests_completed", 0):
            stats_parts.append(f"📜 Quests: {hourlyReportStats['quests_completed']}")
        if hourlyReportStats.get("vicious_bees", 0):
            stats_parts.append(f"🐝 Vicious: {hourlyReportStats['vicious_bees']}")
        if stats_parts:
            fields.append({"name": "Stats", "value": "  •  ".join(stats_parts), "inline": False})

        # Nectars (non-zero)
        nectar_names = ["comforting", "motivating", "satisfying", "refreshing", "invigorating"]
        nectar_order = [0, 2, 4, 3, 1]
        nectar_parts = []
        for name, data_index in zip(nectar_names, nectar_order):
            if data_index < len(nectarQuantity) and int(nectarQuantity[data_index] or 0) > 0:
                nectar_parts.append(f"{nectarEmoji(name)} {name.title()}: {int(nectarQuantity[data_index])}%")
        if nectar_parts:
            fields.append({"name": "Nectar", "value": "\n".join(nectar_parts), "inline": False})

        # Planters
        if planterData:
            planter_parts = []
            for i in range(len(planterData.get("planters", []))):
                pname = planterData["planters"][i]
                if not pname:
                    continue
                field = planterData.get("fields", [])[i] if i < len(planterData.get("fields", [])) else ""
                harvest = planterData.get("harvestTimes", [])[i] if i < len(planterData.get("harvestTimes", [])) else 0
                remaining = harvest - time.time()
                timeStr = self.hourlyReportDrawer.displayTime(max(0, remaining), ['h', 'm']) if remaining > 0 else "Ready!"
                planter_parts.append(f"{planterEmoji(pname)} {pname.title()}: {timeStr} {fieldEmoji(field)}")
            if planter_parts:
                fields.append({"name": "Planters", "value": "\n".join(planter_parts), "inline": False})

        return fields

    def generateHourlyReport(self, setdat, itemMonitorData=None):
        raw_hourly = setdat.get("hourly_report_hourly_buffs", "") if isinstance(setdat, dict) else ""
        hourly_buffs = normalizeHourlyBuffSelection(raw_hourly, self.configuredHourlyBuffs)
        self.configuredHourlyBuffs = hourly_buffs
        self.hourBuffs = {
            "tabby_love":   ["top",    True, True],
            "polar_power":  ["top",    True, True],
            "wealth_clock": ["top",    True, True],
            "blessing":     ["top",    True, True],
            "bloat":        ["top",    True, True],
            "tide_blessing":["top",    True, True],
            "mondo":        ["top",    True, True],
        }
        self.hourBuffs = {k: v for k, v in self.hourBuffs.items() if k in hourly_buffs}
        buffQuantity = self.buffDetector.getBuffsWithImage(self.hourBuffs)
        nectarQuantity = self.buffDetector.getNectars()
        self.latestBuffQuantity = list(buffQuantity)
        self.latestBuffKeys = list(self.hourBuffs.keys())
        self.latestNectarQuantity = list(nectarQuantity)
        #mssScreenshot(save=True)

        #get the hourly report data

        planterData = ""
        #get planter data
        if setdat["planters_mode"] == 1:
            planterData = settingsManager.loadUserText("manualplanters.txt")

            if planterData:
                planterData = ast.literal_eval(planterData)
        elif setdat["planters_mode"] == 2:
            planterData = settingsManager.loadUserJson("auto_planters.json")["planters"]
            planterData = {
                "planters": [p["planter"] for p in planterData],
                "harvestTimes": [p["harvest_time"] for p in planterData],
                "fields": [p["field"] for p in planterData],
            }
            if all(not p for p in planterData["planters"]):
                planterData = ""


        #get history
        historyData = settingsManager.loadUserLiteral("hourly_report_history.txt")
        if not isinstance(historyData, list):
            historyData = []

        if len(self.hourlyReportStats["honey_per_min"]) < 3:
            self.hourlyReportStats["honey_per_min"] = [0]*3 + self.hourlyReportStats["honey_per_min"]
        #filter out the honey/min
        print(self.hourlyReportStats["honey_per_min"])
        #self.hourlyReportStats["honey_per_min"] = [x for x in self.hourlyReportStats["honey_per_min"] if x]
        self.hourlyReportStats["honey_per_min"] = self.filterOutliers(self.hourlyReportStats["honey_per_min"])
        #calculate honey/min
        honeyPerMin = [0]
        prevHoney = self.hourlyReportStats["honey_per_min"][0]
        for x in self.hourlyReportStats["honey_per_min"][1:]:
            if x > prevHoney:
                honeyPerMin.append((x-prevHoney)/60)
            prevHoney = x
        
        #calculate some stats
        if len(set(self.hourlyReportStats["honey_per_min"])) <= 1:
            onlyValidHourlyHoney = self.hourlyReportStats["honey_per_min"].copy()
        else:
            onlyValidHourlyHoney = [x for x in self.hourlyReportStats["honey_per_min"] if x] #removes all zeroes
        sessionHoney = max(0, onlyValidHourlyHoney[-1]- self.hourlyReportStats["start_honey"])
        sessionTime = time.time()-self.hourlyReportStats["start_time"]
        honeyThisHour = max(0, onlyValidHourlyHoney[-1] - onlyValidHourlyHoney[0])

        hourlyReportStats = copy.deepcopy(self.hourlyReportStats)

        # determine enabled fields and their patterns from profile settings
        enabled_fields = []
        field_patterns = {}
        try:
            profile_fields_settings = loadFields()
        except Exception:
            profile_fields_settings = {}

        fields_list = setdat.get("fields", []) if isinstance(setdat, dict) else []
        fields_enabled = setdat.get("fields_enabled", []) if isinstance(setdat, dict) else []
        # normalize lengths
        if len(fields_enabled) < len(fields_list):
            fields_enabled += [False] * (len(fields_list) - len(fields_enabled))

        for i, fname in enumerate(fields_list):
            try:
                if fields_enabled[i]:
                    enabled_fields.append(fname)
                    pattern = profile_fields_settings.get(fname, {}).get("shape") if isinstance(profile_fields_settings, dict) else None
                    field_patterns[fname] = pattern or "unknown"
            except Exception:
                continue

        # read customization from settings — the report theme follows the macro's GUI theme
        gui_theme = setdat.get("gui_theme", "Brown") if isinstance(setdat, dict) else "Brown"
        theme  = resolveReportTheme(gui_theme)
        accent = setdat.get("hourly_report_accent", "green") if isinstance(setdat, dict) else "green"
        send_embed_text = setdat.get("hourly_report_embed_text", True) if isinstance(setdat, dict) else True

        # parse configurable buff lists from settings (comma-separated strings)
        raw_uptime = setdat.get("hourly_report_uptime_buffs", "") if isinstance(setdat, dict) else ""
        uptime_buffs = normalizeUptimeBuffSelection(raw_uptime, self.configuredUptimeBuffs)
        detectedBuffByKey = {
            key: buffQuantity[i] if i < len(buffQuantity) else 0
            for i, key in enumerate(self.latestBuffKeys or list(self.hourBuffs.keys()))
        }
        displayBuffQuantity = [detectedBuffByKey.get(key, 0) for key in hourly_buffs]

        # re-apply theme/accent if they changed
        if theme != self._theme or accent != self._accent:
            self.hourlyReportDrawer = HourlyReportDrawer(self.hourlyReportDrawer.time_format, theme=theme, accent=accent)
            self._theme = theme
            self._accent = accent

        canvas = self.hourlyReportDrawer.drawHourlyReport(hourlyReportStats, sessionTime, honeyPerMin,
                                                          sessionHoney, honeyThisHour, onlyValidHourlyHoney,
                                                          displayBuffQuantity, nectarQuantity, planterData,
                                                          self.uptimeBuffsValues, self.buffGatherIntervals,
                                                          enabled_fields, field_patterns,
                                                          configuredUptimeBuffs=uptime_buffs,
                                                          configuredHourlyBuffs=hourly_buffs)
        w, h = canvas.size
        canvas = canvas.resize((int(w*1.2), int(h*1.2)))
        # Flatten to RGB so Discord/webhooks never composite leftover alpha.
        canvas.convert("RGB").save("hourlyReport.png")

        # generate embed text fields (stored as attribute for caller to use)
        if send_embed_text:
            self.lastEmbedFields = self.generateEmbedFields(
                hourlyReportStats, sessionTime, sessionHoney, honeyThisHour,
                    onlyValidHourlyHoney, displayBuffQuantity, nectarQuantity, planterData,
                    reportType="hourly")
        else:
            self.lastEmbedFields = None

        return hourlyReportStats

    def resetHourlyStats(self):
        self.hourlyReportStats["honey_per_min"] = []
        self.hourlyReportStats["backpack_per_min"] = []
        self.hourlyReportStats["bugs"] = 0
        self.hourlyReportStats["quests_completed"] = 0
        self.hourlyReportStats["vicious_bees"] = 0
        self.hourlyReportStats["gathering_time"] = 0
        self.hourlyReportStats["converting_time"] = 0
        self.hourlyReportStats["bug_run_time"] = 0
        self.hourlyReportStats["misc_time"] = 0

        self.uptimeBuffsValues = self._defaultHourlyUptimeBuffs()
        self.buffGatherIntervals = [0]*600
        if self.itemMonitorSnapshot is not None:
            self.itemMonitorSnapshot = {
                **self.itemMonitorSnapshot,
                "collected_items": {},
                "item_timeline": {},
                "session_collected_items": dict(self.itemMonitorSnapshot.get("session_collected_items") or {}),
            }

        self.saveHourlyReportData()
    
    def resetAllStats(self):
        self.hourlyReportStats["start_time"] = 0
        self.hourlyReportStats["start_honey"] = 0
        self.sessionReportStats = self._defaultSessionReportStats()
        self.sessionUptimeBuffsValues = self._defaultSessionUptimeBuffs()
        self.sessionBuffGatherIntervals = []
        self.latestBuffQuantity = []
        self.latestBuffKeys = []
        self.latestNectarQuantity = []
        self.itemMonitorSnapshot = None
        self.resetHourlyStats()
    
    def addHourlyStat(self, stat, value):
        if isinstance(self.hourlyReportStats[stat], list):
            self.hourlyReportStats[stat].append(value)
        else:
            self.hourlyReportStats[stat] += value

        # Keep session totals independent from hourly resets.
        if stat in self.sessionReportStats:
            if isinstance(self.sessionReportStats[stat], list):
                self.sessionReportStats[stat].append(value)
            else:
                self.sessionReportStats[stat] += value
        self.saveHourlyReportData()
    
    def setSessionStats(self, start_honey, start_time):
        self.hourlyReportStats["start_honey"] = start_honey
        self.hourlyReportStats["start_time"] = start_time
        self.saveHourlyReportData()
    
    def saveHourlyReportData(self):
        path = settingsManager.getUserDataPath("hourly_report_stats.pkl")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump({
                "hourlyReportStats": self.hourlyReportStats,
                "sessionReportStats": self.sessionReportStats,
                "uptimeBuffsValues": self.uptimeBuffsValues,
                "buffGatherIntervals": self.buffGatherIntervals,
                "sessionUptimeBuffsValues": self.sessionUptimeBuffsValues,
                "sessionBuffGatherIntervals": self.sessionBuffGatherIntervals,
                "latestBuffQuantity": self.latestBuffQuantity,
                "latestBuffKeys": self.latestBuffKeys,
                "latestNectarQuantity": self.latestNectarQuantity,
                "itemMonitorSnapshot": self.itemMonitorSnapshot,
            }, f)
    
    def loadHourlyReportData(self):
        path = settingsManager.getUserDataPath("hourly_report_stats.pkl")
        if not os.path.exists(path):
            return
        with open(path, "rb") as f:
            data = pickle.load(f)
            self.hourlyReportStats = data["hourlyReportStats"]
            self.sessionReportStats = data.get("sessionReportStats", self._defaultSessionReportStats())
            self.uptimeBuffsValues = data.get("uptimeBuffsValues", self._defaultHourlyUptimeBuffs())
            self.buffGatherIntervals = data.get("buffGatherIntervals", [0]*600)
            self.sessionUptimeBuffsValues = data.get("sessionUptimeBuffsValues", self._defaultSessionUptimeBuffs())
            self.sessionBuffGatherIntervals = data.get("sessionBuffGatherIntervals", [])
            self.latestBuffQuantity = data.get("latestBuffQuantity", [])
            self.latestBuffKeys = data.get("latestBuffKeys", [])
            self.latestNectarQuantity = data.get("latestNectarQuantity", [])
            self.itemMonitorSnapshot = data.get("itemMonitorSnapshot")
