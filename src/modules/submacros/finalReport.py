from PIL import Image, ImageDraw
import time
import copy
import json
import ast
import pickle
import statistics
from modules.submacros.hourlyReport import HourlyReport, HourlyReportDrawer, BuffDetector, resolveReportTheme
from modules.misc.settingsManager import getCurrentProfile, getMacroVersion


class FinalReportDrawer(HourlyReportDrawer):
    """Drawer for final session reports, inherits from HourlyReportDrawer"""

    def __init__(self, time_format=24, theme="dark", accent="green"):
        super().__init__(time_format=time_format, theme=theme, accent=accent)

    def _drawFinalSidebar(self, top, sessionStats, onlyValidHourlyHoney, planterNames, planterTimes,
                          planterFields, buffQuantity, hourlyBuff_list, nectarQuantity,
                          enabled_fields=None, field_patterns=None, draw=True):
        """Draw (or measure, when draw=False) the final-report sidebar. Returns the bottom y."""
        import math as _math
        y2 = top
        totalSessionTime = sessionStats.get("total_session_time", 0)

        # planters (top)
        if planterNames:
            if draw:
                self.draw.text((self.sidebarX, y2), "Planters", font=self.getFont("semibold", 85), fill=self.bodyColor)
            y2 += 250
            if draw:
                self.drawPlanters(y2, planterNames, planterTimes, planterFields)
            y2 += 650

        # fields (beneath planters)
        y2 = self._drawFieldsSection(y2, enabled_fields or [], field_patterns or {}, draw=draw)

        # snapshot buffs
        if draw:
            self.draw.text((self.sidebarX, y2), "Buffs", font=self.getFont("semibold", 85), fill=self.bodyColor)
        y2 += 250
        if draw:
            self.drawBuffs(y2, buffQuantity, hourlyBuff_list)
        buffRows = _math.ceil(len(hourlyBuff_list) / 4) if hourlyBuff_list else 1
        y2 += 300 * max(1, buffRows)

        # nectars
        y2 += 200
        if draw:
            self.draw.text((self.sidebarX, y2), "Nectars", font=self.getFont("semibold", 85), fill=self.bodyColor)
        y2 += 250
        if draw:
            self.drawNectars(y2, nectarQuantity)
        y2 += 500

        # time breakdown
        y2 += 100
        if draw:
            self.draw.text((self.sidebarX, y2), "Time Breakdown", font=self.getFont("semibold", 85), fill=self.bodyColor)
        y2 += 250
        if draw:
            self.drawTaskTimes(y2, [
                {"label": "Gathering",  "data": sessionStats.get("gathering_time", 0),  "color": self.gatherColor},
                {"label": "Converting", "data": sessionStats.get("converting_time", 0), "color": self.convertColor},
                {"label": "Bug Runs",   "data": sessionStats.get("bug_run_time", 0),    "color": self.otherColor},
                {"label": "Other",      "data": sessionStats.get("misc_time", 0),       "color": self.subtleColor},
            ], totalSessionTime)
        y2 += 1500

        # session stats (bottom)
        y2 += 100
        if draw:
            self.draw.text((self.sidebarX, y2), "Session Stats", font=self.getFont("semibold", 85), fill=self.bodyColor)
        y2 += 250
        if draw:
            self.drawSessionStat(y2, "time_icon", "Total Runtime", self.displayTime(totalSessionTime, ['d', 'h', 'm']), self.bodyColor)
        y2 += 300
        if draw:
            finalHoney = onlyValidHourlyHoney[-1] if onlyValidHourlyHoney else 0
            self.drawSessionStat(y2, "honey_icon", "Final Honey", self.millify(finalHoney), self.honeyColor)
        y2 += 300
        if draw:
            self.drawSessionStat(y2, "session_honey_icon", "Total Gained", self.millify(sessionStats.get("total_honey", 0)), (253, 227, 149))
        y2 += 300
        if draw:
            avgSidebarLabel = "Est. Avg/Hour" if totalSessionTime < 3600 else "Avg/Hour"
            self.drawSessionStat(y2, "average_icon", avgSidebarLabel, self.millify(sessionStats.get("avg_honey_per_hour", 0)), self.accentColor)
        y2 += 300

        return y2

    def drawFinalReport(self, hourlyReportStats, sessionStats, honeyPerSec, sessionHoney, onlyValidHourlyHoney, buffQuantity, nectarQuantity, planterData, uptimeBuffsValues, buffGatherIntervals, configuredUptimeBuffs=None, configuredHourlyBuffs=None, enabled_fields=None, field_patterns=None):
        """Draw comprehensive final report with session statistics and trends"""
        import math as _math

        def getAverageBuff(buffValues):
            count = 0
            total = 0
            for gatherFlag, buffValue in zip(buffGatherIntervals, buffValues):
                if gatherFlag:
                    total += buffValue
                    count += 1
            res = total / count if count else 0
            return f"x{res:.2f}"

        from modules.submacros.hourlyReport import DEFAULT_UPTIME_BUFFS, DEFAULT_HOURLY_BUFFS
        uptimeBuff_list = configuredUptimeBuffs if configuredUptimeBuffs is not None else DEFAULT_UPTIME_BUFFS
        hourlyBuff_list = configuredHourlyBuffs if configuredHourlyBuffs is not None else DEFAULT_HOURLY_BUFFS
        if enabled_fields is None:
            enabled_fields = []
        if field_patterns is None:
            field_patterns = {}

        self.sidebarX = self.canvasW - self.sidebarWidth + self.sidebarPadding
        sessionTime = sessionStats.get("total_session_time", 0)

        # x-axis for the honey/backpack charts (minutes across the session)
        dataPoints = len(honeyPerSec) if honeyPerSec else 1
        if sessionTime > 0:
            timeInterval = sessionTime / max(dataPoints - 1, 1) if dataPoints > 1 else 60
            mins = [i * timeInterval / 60 for i in range(dataPoints)]
        else:
            mins = list(range(dataPoints))

        return self._drawStatMonitorReport(
            "Session Report", hourlyReportStats, sessionTime, honeyPerSec, sessionHoney,
            sessionStats.get("total_honey", sessionHoney), onlyValidHourlyHoney,
            buffQuantity, nectarQuantity, planterData, uptimeBuffsValues,
            buffGatherIntervals, configuredUptimeBuffs=uptimeBuff_list,
            configuredHourlyBuffs=hourlyBuff_list, sessionStats=sessionStats,
        )

        buffSampleCount = max(
            max((len(values) for values in uptimeBuffsValues.values()), default=0),
            len(buffGatherIntervals), 1)

        def sessionTimeLabel(i, val):
            if val == 0:
                return "0m"
            if sessionTime < 3600:
                return f"{int(val)}m"
            elif sessionTime < 86400:
                return f"{int(val/60)}h"
            else:
                return f"{int(val/1440)}d"

        def gridBuffLabel(i, val):
            # i is the sample index; derive its time from the session length
            if buffSampleCount <= 1:
                return "0m" if i == 0 else None
            step = max(1, (buffSampleCount - 1) // 5)
            if i not in (0, buffSampleCount - 1) and i % step:
                return None
            minsAt = i * sessionTime / max(buffSampleCount - 1, 1) / 60
            return sessionTimeLabel(i, minsAt)

        self.canvas = Image.new('RGBA', self.canvasSize, (*self.backgroundColor, 255))
        self.draw = ImageDraw.Draw(self.canvas)

        # planter data
        planterNames, planterTimes, planterFields = [], [], []
        if planterData:
            for i in range(len(planterData["planters"])):
                if planterData["planters"][i]:
                    planterNames.append(planterData["planters"][i])
                    planterTimes.append(planterData["harvestTimes"][i] - time.time())
                    planterFields.append(planterData["fields"][i])

        # header banner
        runtimeStr = self.displayTime(sessionTime, ['d', 'h', 'm']) if sessionTime else "0m"
        headerBottom = self._drawHeaderBanner("Session Summary", f"Total Runtime: {runtimeStr}")

        # measure sidebar
        sidebarTop = headerBottom + 80
        sidebarBottom = self._drawFinalSidebar(sidebarTop, sessionStats, onlyValidHourlyHoney,
                                               planterNames, planterTimes, planterFields,
                                               buffQuantity, hourlyBuff_list, nectarQuantity,
                                               enabled_fields, field_patterns, draw=False)

        # left column: stat cards
        y = headerBottom + 80
        cardGap = 60
        cardW = (self.availableSpace - cardGap * 4) // 5
        avgHoneyPerHour = sessionStats.get("avg_honey_per_hour", 0)
        avgLabel = "Estimated Avg\nPer Hour" if sessionTime < 3600 else "Average Honey\nPer Hour"
        cards = [
            ("average_icon",     self.millify(avgHoneyPerHour),                  avgLabel,                        None,            None),
            ("honey_icon",       self.millify(sessionStats.get("total_honey", 0)),"Total Honey\nThis Session",    self.honeyColor, None),
            ("kill_icon",        sessionStats.get("total_bugs", 0),              "Bugs Killed\nThis Session",     (254, 101, 99),  (254, 101, 99)),
            ("quest_icon",       sessionStats.get("total_quests", 0),            "Quests Completed\nThis Session",(103, 253, 153), (103, 253, 153)),
            ("vicious_bee_icon", sessionStats.get("total_vicious_bees", 0),      "Vicious Bees\nThis Session",    (132, 233, 254), (132, 233, 254)),
        ]
        for i, (icon, val, label, fc, ic) in enumerate(cards):
            self.drawStatCard(self.leftPadding + i * (cardW + cardGap), y, icon, val, label, fc, ic, cardWidth=cardW)
        y += 750 + 150

        # buff uptime — two-column grid (moved to the top of the report)
        self.draw.text((self.leftPadding, y), "Average Buff Uptime", fill=self.bodyColor, font=self.getFont("semibold", 85))
        bbox = self.draw.textbbox((0, 0), "(Session Average)", font=self.getFont("medium", 55))
        self.draw.text((self.leftPadding + self.availableSpace - (bbox[2] - bbox[0]), y + 25), "(Session Average)", fill=self.subtleColor, font=self.getFont("medium", 55))
        y += 250
        y = self._drawBuffGrid(self.leftPadding, y, self.availableSpace, uptimeBuff_list,
                               uptimeBuffsValues, getAverageBuff, columns=2, xLabelFunc=gridBuffLabel)

        chartContentWidth = self.canvasW - self.leftPadding * 2
        chartGraphX = self.leftPadding + 450
        chartGraphWidth = chartContentWidth - 570
        y = max(y, sidebarBottom + 180)

        # honey/sec over session
        y += 150
        self.draw.text((self.leftPadding, y), "Honey / Sec Over Time", fill=self.bodyColor, font=self.getFont("semibold", 85))
        peakRate = sessionStats.get("peak_honey_rate", 0)
        ar, ag, ab = self.accentColor
        peakText = f"Peak: {self.millify(peakRate)}/s"
        pbbox = self.draw.textbbox((0, 0), peakText, font=self.getFont("medium", 60))
        self.draw.text((self.leftPadding + chartContentWidth - (pbbox[2] - pbbox[0]), y + 15), peakText, fill=self.accentColor, font=self.getFont("medium", 60))
        y += 950
        self.drawGraph(chartGraphX, y, chartGraphWidth, 700, mins,
                       [{"data": honeyPerSec, "lineColor": self.accentColor,
                         "gradientFill": {0: (ar, ag, ab, 38), 1: (ar, ag, ab, 153)}}],
                       xLabelFunc=sessionTimeLabel, yLabelFunc=lambda i, x: self.millify(x))

        # backpack
        y += 200
        self.draw.text((self.leftPadding, y), "Backpack Utilization", fill=self.bodyColor, font=self.getFont("semibold", 85))
        y += 950
        backpackData = hourlyReportStats.get("backpack_per_min", []) or [0] * len(mins)
        if len(backpackData) < len(mins):
            backpackData = backpackData + [0] * (len(mins) - len(backpackData))
        elif len(backpackData) > len(mins):
            backpackData = backpackData[:len(mins)]
        self.drawGraph(chartGraphX, y, chartGraphWidth, 700, mins,
                       [{"data": backpackData, "lineColor": "gradient",
                         "gradientFill": {0: (65, 255, 128, 90), 0.6: (201, 163, 36, 90), 0.9: (255, 65, 84, 90), 1: (255, 65, 84, 90)}}],
                       maxY=100, xLabelFunc=sessionTimeLabel, yLabelFunc=lambda i, x: f"{int(x)}%")
        leftBottom = y

        # sidebar background (ends at its own content) + content
        finalContentBottom = max(leftBottom, sidebarBottom)
        self.draw.rectangle((self.canvasW - self.sidebarWidth, headerBottom + 40, self.canvasW, sidebarBottom + 60), fill=self.sideBarBackground)
        self._drawFinalSidebar(sidebarTop, sessionStats, onlyValidHourlyHoney,
                               planterNames, planterTimes, planterFields,
                               buffQuantity, hourlyBuff_list, nectarQuantity,
                               enabled_fields, field_patterns, draw=True)

        # crop to content height
        finalH = min(self.canvasMaxH, int(finalContentBottom) + 120)
        self.canvas = self.canvas.crop((0, 0, self.canvasW, finalH))
        self.draw = ImageDraw.Draw(self.canvas)
        return self.canvas


class FinalReport:
    """Handles final session report generation"""
    
    def __init__(self, hourlyReport: HourlyReport = None):
        self.hourlyReport = hourlyReport if hourlyReport else HourlyReport()
        self.drawer = FinalReportDrawer()
        self.lastEmbedFields = None

    def _normalizeCumulativeHoneySeries(self, values, baseline=None):
        """Return a stable cumulative honey series while preserving sample count."""
        if not values:
            return [0]

        numericValues = []
        for value in values:
            try:
                numericValues.append(max(0, float(value)))
            except (TypeError, ValueError):
                numericValues.append(0.0)

        firstNonZero = next((value for value in numericValues if value > 0), 0.0)
        if baseline is None:
            baseline = firstNonZero
        baseline = max(0.0, float(baseline or 0.0))

        # Replace placeholder leading zeroes so the first real reading does not look like session gain.
        if baseline > 0:
            seenPositive = False
            for i, value in enumerate(numericValues):
                if value > 0:
                    seenPositive = True
                    break
                if not seenPositive:
                    numericValues[i] = baseline

        positiveDeltas = []
        prevValue = numericValues[0]
        for value in numericValues[1:]:
            delta = value - prevValue
            if delta > 0:
                positiveDeltas.append(delta)
            if value > 0:
                prevValue = value

        deltaCap = None
        if len(positiveDeltas) >= 5:
            sortedDeltas = sorted(positiveDeltas)
            trimmedCount = max(1, int(len(sortedDeltas) * 0.9))
            trimmedDeltas = sortedDeltas[:trimmedCount]
            medianDelta = statistics.median(trimmedDeltas)
            mad = statistics.median([abs(delta - medianDelta) for delta in trimmedDeltas]) if trimmedDeltas else 0
            p95Trimmed = trimmedDeltas[min(len(trimmedDeltas) - 1, int((len(trimmedDeltas) - 1) * 0.95))]
            deltaCap = max(1.0, medianDelta * 8.0, medianDelta + mad * 10.0, p95Trimmed * 1.5)

        stabilized = [numericValues[0]]
        valueCount = len(numericValues)
        for i, value in enumerate(numericValues[1:], start=1):
            prev = stabilized[-1]

            if value <= 0:
                stabilized.append(prev)
                continue

            if value < prev:
                stabilized.append(prev)
                continue

            delta = value - prev
            if deltaCap is not None and delta > deltaCap:
                nextValue = None
                for lookAhead in range(i + 1, valueCount):
                    candidate = numericValues[lookAhead]
                    if candidate > 0:
                        nextValue = candidate
                        break

                # Ignore obvious OCR spikes that immediately collapse back to the normal range.
                if nextValue is not None and nextValue < value - deltaCap:
                    stabilized.append(prev)
                    continue

                value = prev + deltaCap

            stabilized.append(value)

        return stabilized

    def _buildHoneyPerSec(self, cumulativeHoney):
        if not cumulativeHoney:
            return [0]

        honeyPerSec = [0]
        prevHoney = cumulativeHoney[0]
        for currentHoney in cumulativeHoney[1:]:
            honeyPerSec.append(max(0.0, currentHoney - prevHoney) / 60.0)
            prevHoney = currentHoney
        return honeyPerSec

    def _buildSessionTimeBreakdown(self, sourceStats, sessionTime):
        gatherTime = max(0, float(sourceStats.get("gathering_time", 0) or 0))
        convertTime = max(0, float(sourceStats.get("converting_time", 0) or 0))
        bugRunTime = max(0, float(sourceStats.get("bug_run_time", 0) or 0))
        miscTime = max(0, float(sourceStats.get("misc_time", 0) or 0))

        trackedWithoutOther = gatherTime + convertTime + bugRunTime
        totalCategorized = trackedWithoutOther + miscTime

        if sessionTime > totalCategorized:
            miscTime += sessionTime - totalCategorized
        elif sessionTime > trackedWithoutOther:
            miscTime = min(miscTime, sessionTime - trackedWithoutOther)
        elif sessionTime > 0:
            scale = sessionTime / max(trackedWithoutOther, 1)
            gatherTime *= scale
            convertTime *= scale
            bugRunTime *= scale
            miscTime = 0

        return {
            "gathering_time": gatherTime,
            "converting_time": convertTime,
            "bug_run_time": bugRunTime,
            "misc_time": miscTime,
        }

    def _settingsInt(self, settings, key, default=0):
        try:
            return int(settings.get(key, default)) if isinstance(settings, dict) else default
        except (TypeError, ValueError):
            return default

    def _deriveSessionTime(self, sourceStats, normalizedHoneyPerMin, originalHoneySampleCount=None, stop_time=None):
        """Use stop_time - start_time when available (live stop); fall back to sample count for historical reports."""
        startTime = self.hourlyReport.hourlyReportStats.get("start_time", 0)
        if startTime and stop_time:
            return max(0, stop_time - startTime)

        sampleCount = max(
            originalHoneySampleCount if originalHoneySampleCount is not None else len(normalizedHoneyPerMin or []),
            len(sourceStats.get("backpack_per_min", []) or []),
        )
        if sampleCount > 1:
            return (sampleCount - 1) * 60

        if startTime:
            return max(0, time.time() - startTime)

        return 0

    def generateFinalReport(self, setdat, stop_time=None):
        """Generate a comprehensive final report covering the entire macro session"""
        # Load the saved data
        try:
            self.hourlyReport.loadHourlyReportData()
        except Exception as e:
            print(f"Error loading hourly report data: {e}")
            # Try to create a minimal report if data load fails
            try:
                self.hourlyReport.hourlyReportStats = {
                    "honey_per_min": [0],
                    "backpack_per_min": [0],
                    "bugs": 0,
                    "quests_completed": 0,
                    "vicious_bees": 0,
                    "gathering_time": 0,
                    "converting_time": 0,
                    "bug_run_time": 0,
                    "misc_time": 0,
                    "start_time": 0,
                    "start_honey": 0
                }
                self.hourlyReport.sessionReportStats = {
                    "honey_per_min": [0],
                    "backpack_per_min": [0],
                    "bugs": 0,
                    "quests_completed": 0,
                    "vicious_bees": 0,
                    "gathering_time": 0,
                    "converting_time": 0,
                    "bug_run_time": 0,
                    "misc_time": 0,
                }
                self.hourlyReport.uptimeBuffsValues = {}
                self.hourlyReport.buffGatherIntervals = [0]
            except:
                return None

        sessionReportStats = getattr(self.hourlyReport, "sessionReportStats", {})
        if sessionReportStats.get("honey_per_min"):
            sourceStats = copy.deepcopy(sessionReportStats)
        else:
            # Backward compatibility for old saved data that predates sessionReportStats.
            sourceStats = copy.deepcopy(self.hourlyReport.hourlyReportStats)
        
        raw_uptime = setdat.get("hourly_report_uptime_buffs", "") if isinstance(setdat, dict) else ""
        raw_hourly = setdat.get("hourly_report_hourly_buffs", "") if isinstance(setdat, dict) else ""
        from modules.submacros.hourlyReport import DEFAULT_UPTIME_BUFFS, DEFAULT_HOURLY_BUFFS, normalizeUptimeBuffSelection
        uptime_buffs = normalizeUptimeBuffSelection(raw_uptime, DEFAULT_UPTIME_BUFFS)
        hourly_buffs = [b.strip() for b in raw_hourly.split(",") if b.strip()] if raw_hourly else DEFAULT_HOURLY_BUFFS

        # Always try to capture fresh buff/nectar values from the current screen.
        # The discord /hourlyreport command reads buffs but never saves them to disk,
        # so saved snapshot values may be stale or empty. Fall back to saved values
        # only if the screen read fails (e.g. historical/offline report generation).
        try:
            detector = getattr(self.hourlyReport, "buffDetector", None)
            if not detector:
                try:
                    from modules.screen.robloxWindow import RobloxWindowBounds
                    robloxWindow = RobloxWindowBounds()
                    robloxWindow.setRobloxWindowBounds()
                    detector = BuffDetector(robloxWindow)
                except Exception as de:
                    print(f"Could not create BuffDetector for screen read: {de}")
            if detector:
                try:
                    liveBuffQuantity = detector.getBuffsWithImage(self.hourlyReport.hourBuffs)
                    self.hourlyReport.latestBuffQuantity = list(liveBuffQuantity)
                    self.hourlyReport.latestBuffKeys = list(self.hourlyReport.hourBuffs.keys())
                    self.hourlyReport.latestNectarQuantity = list(detector.getNectars())
                except Exception as se:
                    print(f"Could not read buffs/nectars from screen: {se}")
        except Exception as e:
            print(f"Error refreshing final report buff snapshot: {e}")

        # The saved values are positional, so keep the saved detector keys with them and
        # remap into the current display order before drawing.
        savedBuffQuantity = list(getattr(self.hourlyReport, "latestBuffQuantity", []))
        savedBuffKeys = list(getattr(self.hourlyReport, "latestBuffKeys", []))
        if not savedBuffKeys:
            savedBuffKeys = list(self.hourlyReport.hourBuffs.keys())
        buffByKey = {
            key: savedBuffQuantity[i] if i < len(savedBuffQuantity) else 0
            for i, key in enumerate(savedBuffKeys)
        }
        buffQuantity = [buffByKey.get(key, 0) for key in hourly_buffs]

        nectarQuantity = list(getattr(self.hourlyReport, "latestNectarQuantity", []))
        if len(nectarQuantity) < 5:
            nectarQuantity += [0] * (5 - len(nectarQuantity))
        else:
            nectarQuantity = nectarQuantity[:5]

        # Get planter data
        planterData = ""
        try:
            plantersMode = self._settingsInt(setdat, "planters_mode", 0)
            if plantersMode == 1:
                try:
                    with open("./data/user/manualplanters.txt", "r") as f:
                        planterData = f.read()
                    if planterData:
                        planterData = ast.literal_eval(planterData)
                except (FileNotFoundError, SyntaxError, ValueError):
                    planterData = ""
            elif plantersMode == 2:
                try:
                    with open("./data/user/auto_planters.json", "r") as f:
                        planterData = json.load(f)["planters"]
                    planterData = {
                        "planters": [p["planter"] for p in planterData],
                        "harvestTimes": [p["harvest_time"] for p in planterData],
                        "fields": [p["field"] for p in planterData],
                    }
                    if all(not p for p in planterData["planters"]):
                        planterData = ""
                except (FileNotFoundError, json.JSONDecodeError, KeyError):
                    planterData = ""
        except Exception as e:
            print(f"Error loading planter data: {e}")
            planterData = ""

        # Ensure we have valid honey data and keep one point per minute.
        rawHoneyPerMin = sourceStats.get("honey_per_min", [])
        if not rawHoneyPerMin:
            rawHoneyPerMin = [0]
        originalHoneySampleCount = len(rawHoneyPerMin)
        if originalHoneySampleCount < 3:
            rawHoneyPerMin = [0] * (3 - originalHoneySampleCount) + rawHoneyPerMin

        startHoney = self.hourlyReport.hourlyReportStats.get("start_honey", 0)
        normalizedHoneyPerMin = self._normalizeCumulativeHoneySeries(rawHoneyPerMin, baseline=startHoney)
        sourceStats["honey_per_min"] = normalizedHoneyPerMin

        # Build per-second gain from the normalized cumulative timeline.
        honeyPerSec = self._buildHoneyPerSec(normalizedHoneyPerMin)
        
        # Calculate session statistics
        onlyValidHourlyHoney = [x for x in normalizedHoneyPerMin if x > 0] or normalizedHoneyPerMin.copy()
        
        # Calculate total session honey and time
        sessionHoney = 0
        sessionTime = 0
        if onlyValidHourlyHoney and startHoney:
            sessionHoney = max(0, onlyValidHourlyHoney[-1] - startHoney)
        
        sessionTime = self._deriveSessionTime(sourceStats, normalizedHoneyPerMin, originalHoneySampleCount, stop_time)
        
        # Calculate average honey per hour for the entire session
        avgHoneyPerHour = max(0, (sessionHoney / (sessionTime / 3600)) if sessionTime > 0 else 0)
        
        # Calculate peak honey rate (filter out zeros for more accurate peak)
        validHoneyPerSec = [x for x in honeyPerSec if x > 0]
        peakHoneyRate = max(validHoneyPerSec) if validHoneyPerSec else 0
        
        # Use session-wide stats for final report cards and charts.
        hourlyReportStats = copy.deepcopy(sourceStats)
        timeBreakdown = self._buildSessionTimeBreakdown(sourceStats, sessionTime)
        
        # Add session summary stats
        sessionStats = {
            "total_session_time": sessionTime,
            "total_honey": sessionHoney,
            "avg_honey_per_hour": avgHoneyPerHour,
            "peak_honey_rate": peakHoneyRate,
            "total_bugs": sourceStats.get("bugs", 0),
            "total_quests": sourceStats.get("quests_completed", 0),
            "total_vicious_bees": sourceStats.get("vicious_bees", 0),
            "gathering_time": timeBreakdown["gathering_time"],
            "converting_time": timeBreakdown["converting_time"],
            "bug_run_time": timeBreakdown["bug_run_time"],
            "misc_time": timeBreakdown["misc_time"]
        }

        # Prefer full-session buff history when available.
        if not hasattr(self.hourlyReport, 'sessionUptimeBuffsValues') or not self.hourlyReport.sessionUptimeBuffsValues:
            self.hourlyReport.sessionUptimeBuffsValues = copy.deepcopy(getattr(self.hourlyReport, "uptimeBuffsValues", {}))
        if not hasattr(self.hourlyReport, 'sessionBuffGatherIntervals') or not self.hourlyReport.sessionBuffGatherIntervals:
            self.hourlyReport.sessionBuffGatherIntervals = list(getattr(self.hourlyReport, "buffGatherIntervals", []))

        if not self.hourlyReport.sessionUptimeBuffsValues:
            self.hourlyReport.sessionUptimeBuffsValues = {k:[0]*600 for k in self.hourlyReport.uptimeBuffsColors.keys()}
            self.hourlyReport.sessionUptimeBuffsValues["bear"] = [0]*600
            self.hourlyReport.sessionUptimeBuffsValues["white_boost"] = [0]*600
        
        if not self.hourlyReport.sessionBuffGatherIntervals:
            self.hourlyReport.sessionBuffGatherIntervals = [0] * max(
                max((len(values) for values in self.hourlyReport.sessionUptimeBuffsValues.values()), default=0),
                600
            )

        # apply theme/accent from settings — the report theme follows the macro's GUI theme
        gui_theme = setdat.get("gui_theme", "Brown") if isinstance(setdat, dict) else "Brown"
        theme  = resolveReportTheme(gui_theme)
        accent = setdat.get("hourly_report_accent",  "green") if isinstance(setdat, dict) else "green"
        send_embed_text = setdat.get("hourly_report_embed_text", True) if isinstance(setdat, dict) else True

        # determine enabled gather fields and their patterns (shown beneath planters)
        enabled_fields, field_patterns = [], {}
        try:
            from modules.misc.settingsManager import loadFields
            profile_fields_settings = loadFields()
        except Exception:
            profile_fields_settings = {}
        fields_list = setdat.get("fields", []) if isinstance(setdat, dict) else []
        fields_enabled = setdat.get("fields_enabled", []) if isinstance(setdat, dict) else []
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

        self.drawer = FinalReportDrawer(theme=theme, accent=accent)

        # Draw the comprehensive final report
        try:
            canvas = self.drawer.drawFinalReport(
                hourlyReportStats, sessionStats, honeyPerSec,
                sessionHoney, onlyValidHourlyHoney,
                buffQuantity, nectarQuantity, planterData,
                self.hourlyReport.sessionUptimeBuffsValues, self.hourlyReport.sessionBuffGatherIntervals,
                configuredUptimeBuffs=uptime_buffs,
                configuredHourlyBuffs=hourly_buffs,
                enabled_fields=enabled_fields,
                field_patterns=field_patterns,
            )

            w, h = canvas.size
            canvas = canvas.resize((int(w*1.2), int(h*1.2)))
            canvas.save("finalReport.png")
            print("Final report saved successfully to finalReport.png")

            # generate embed fields for session report
            if send_embed_text:
                self.lastEmbedFields = self.hourlyReport.generateEmbedFields(
                    hourlyReportStats, sessionTime, sessionHoney,
                    sessionHoney,  # honeyThisHour = total for session report
                    onlyValidHourlyHoney, buffQuantity, nectarQuantity, planterData, reportType="session")
            else:
                self.lastEmbedFields = None

            return sessionStats
        except Exception as e:
            print(f"Error drawing final report: {e}")
            import traceback
            traceback.print_exc()
            return None
