from PIL import Image, ImageDraw
import time
import copy
import json
import ast
import pickle
import statistics
import math
from modules.submacros.hourlyReport import HourlyReport, HourlyReportDrawer
from modules.misc.settingsManager import loadFields


class FinalReportDrawer(HourlyReportDrawer):
    """Drawer for final session reports, inherits from HourlyReportDrawer"""
    
    def drawFinalReport(self, hourlyReportStats, sessionStats, honeyPerSec, sessionHoney, onlyValidHourlyHoney, buffQuantity, nectarQuantity, planterData, uptimeBuffsValues, buffGatherIntervals, enabled_fields=None, field_patterns=None):
        """Draw comprehensive final report with session statistics and trends"""
        
        def getAverageBuff(buffValues):
            #get the buff average when gathering, rounded to 2p
            count = 0
            total = 0
            for gatherFlag, buffValue in zip(buffGatherIntervals, buffValues):
                if gatherFlag:
                    total += buffValue
                    count += 1

            res = total/count if count else 0
                
            return f"x{res:.2f}"
        
        def formatTime(seconds):
            """Format seconds into readable time string"""
            if seconds < 60:
                return f"{int(seconds)}s"
            elif seconds < 3600:
                return f"{int(seconds/60)}m {int(seconds%60)}s"
            else:
                hours = int(seconds/3600)
                minutes = int((seconds%3600)/60)
                return f"{hours}h {minutes}m"

        self.beginReportCanvas()

        # Calculate time range for x-axis based on actual session length
        sessionTime = sessionStats.get("total_session_time", 0)
        dataPoints = len(honeyPerSec) if honeyPerSec else 1
        
        # Create appropriate time labels based on session duration
        if sessionTime > 0:
            timeInterval = sessionTime / max(dataPoints - 1, 1) if dataPoints > 1 else 60
            mins = [i * timeInterval / 60 for i in range(dataPoints)]  # Convert to minutes for x-axis
        else:
            mins = list(range(dataPoints))

        buffSampleCount = max(
            max((len(values) for values in uptimeBuffsValues.values()), default=0),
            len(buffGatherIntervals),
            1
        )
        if sessionTime > 0:
            buffXAxis = [i * sessionTime / max(buffSampleCount - 1, 1) / 60 for i in range(buffSampleCount)]
        else:
            buffXAxis = list(range(buffSampleCount))
        self.sidebarPadding = 85
        self.sidebarX = self.canvasSize[0] - self.sidebarWidth + self.sidebarPadding
        self.sidebarPanelWidth = self.sidebarWidth - self.sidebarPadding * 2
        self.sidebarInnerInset = 46
        self.sidebarContentWidth = self.sidebarPanelWidth - self.sidebarInnerInset * 2

        sessionTimeStr = formatTime(sessionTime)
        totalHoney = sessionStats.get("total_honey", 0)
        avgHoneyPerHour = sessionStats.get("avg_honey_per_hour", 0)
        peakRate = sessionStats.get("peak_honey_rate", 0)

        self.drawHeroCard(
            self.leftPadding,
            80,
            self.availableSpace,
            350,
            "FINAL REPORT",
            "Session Summary",
            "Full-session performance in the same Fuzzy Macro report language.",
            accent=self.primaryColor
        )
        self.drawBrandCard(self.sidebarX, 80, self.sidebarPanelWidth, 350)

        #section 1: session stats
        y = 470
        cardGap = 28
        cardWidth = int((self.availableSpace - cardGap * 4) / 5)
        avgLabel = "Estimated Avg\nPer Hour" if sessionTime < 3600 else "Average Honey\nPer Hour"
        self.drawStatCard(self.leftPadding, y, "average_icon", self.millify(avgHoneyPerHour), avgLabel, cardWidth=cardWidth)
        self.drawStatCard(self.leftPadding + (cardWidth + cardGap) * 1, y, "honey_icon", self.millify(totalHoney), "Total Honey\nThis Session", self.honeyColor, self.honeyColor, cardWidth=cardWidth)
        self.drawStatCard(self.leftPadding + (cardWidth + cardGap) * 2, y, "kill_icon", sessionStats.get("total_bugs", 0), "Bugs Killed\nThis Session", (254,101,99), (254,101,99), cardWidth=cardWidth)
        self.drawStatCard(self.leftPadding + (cardWidth + cardGap) * 3, y, "quest_icon", sessionStats.get("total_quests", 0), "Quests Completed\nThis Session", (103,253,153), (103,253,153), cardWidth=cardWidth)
        self.drawStatCard(self.leftPadding + (cardWidth + cardGap) * 4, y, "vicious_bee_icon", sessionStats.get("total_vicious_bees", 0), "Vicious Bees\nThis Session", (132,233,254), (132,233,254), cardWidth=cardWidth)

        def sessionTimeLabel(i, val):
            if val == 0:
                return "0m"
            if sessionTime < 3600:
                return f"{int(val)}m"
            if sessionTime < 86400:
                return f"{int(val/60)}h"
            return f"{int(val/1440)}d"

        def buffTimeLabel(i, val):
            if buffSampleCount <= 1:
                return "0m" if i == 0 else None

            labelCount = 6 if sessionTime >= 3600 else 5
            step = max(1, (buffSampleCount - 1) // labelCount)
            if i not in (0, buffSampleCount - 1) and i % step:
                return None
            return sessionTimeLabel(i, val)

        #section 2: honey/sec over session
        y = 980
        panelWidth = self.availableSpace
        self.drawPanel(self.leftPadding, y, panelWidth, 1120, accent=self.honeyColor, fill=self.tintedSurface(self.primaryColor, 0.1))
        headerBottom = self.drawSectionHeader(
            self.leftPadding + 60,
            y + 56,
            panelWidth - 120,
            "Honey / Sec Over Session",
            "Trend line across the full runtime, scaled to the recorded sample cadence.",
            meta=f"Peak {self.millify(peakRate)}/s",
            accent=self.honeyColor
        )
        dataset = [{
            "data": honeyPerSec,
            "lineColor": self.primarySoftColor,
            "gradientFill": {
                0: (*self.primarySoftColor, 18),
                0.6: (*self.primaryColor, 70),
                1: (*self.honeyColor, 140)
            }
        }]
        graphTop = headerBottom + 72
        self.drawGraph(self.leftPadding + 430, graphTop + 700, self.availableSpace - 540, 700, mins, dataset, xLabelFunc=sessionTimeLabel, yLabelFunc=lambda i, x: self.millify(x))

        #section 3: backpack utilization over session
        y = 2160
        self.drawPanel(self.leftPadding, y, panelWidth, 1120, accent=self.primaryColor, fill=self.tintedSurface(self.primaryColor, 0.08))
        headerBottom = self.drawSectionHeader(
            self.leftPadding + 60,
            y + 56,
            panelWidth - 120,
            "Backpack Utilization",
            "Session-wide pressure curve to show where capacity starts clipping the run.",
            meta="0-100%",
            accent=self.primarySoftColor
        )

        backpackData = hourlyReportStats.get("backpack_per_min", [])
        if not backpackData:
            backpackData = [0] * len(mins)
        elif len(backpackData) < len(mins):
            backpackData = backpackData + [0] * (len(mins) - len(backpackData))
        elif len(backpackData) > len(mins):
            backpackData = backpackData[:len(mins)]

        dataset = [{
            "data": backpackData,
            "lineColor": "gradient",
            "gradientFill": {
                0: (65, 255, 128, 90),
                0.6: (201, 163, 36, 90),
                0.9: (255, 65, 84, 90),
                1: (255, 65, 84, 90),
            }
        }]
        graphTop = headerBottom + 72
        self.drawGraph(self.leftPadding + 430, graphTop + 700, self.availableSpace - 540, 700, mins, dataset, maxY=100, xLabelFunc=sessionTimeLabel, yLabelFunc=lambda i, x: f"{int(x)}%")

        #section 4: buff uptime
        y = 3340
        self.drawPanel(self.leftPadding, y, panelWidth, 4300, accent=self.secondaryAccentColor, fill=self.tintedSurface(self.secondaryAccentColor, 0.06))
        headerBottom = self.drawSectionHeader(
            self.leftPadding + 60,
            y + 56,
            panelWidth - 120,
            "Average Buff Uptime",
            "Gathering-window averages across the session, followed by binary coverage charts.",
            meta="Session average",
            accent=self.secondaryAccentColor
        )
        y = headerBottom + 360
        dataset = [
        {
            "data": uptimeBuffsValues.get("blue_boost", [0]*600),
            "lineColor": (77,147,193),
            "average": getAverageBuff(uptimeBuffsValues.get("blue_boost", [0]*600)),
            "gradientFill": {
                0: (77,147,193,10),
                1: (77,147,193,120),
            }
        },
        {
            "data": uptimeBuffsValues.get("red_boost", [0]*600),
            "lineColor": (200,90,80),
            "average": getAverageBuff(uptimeBuffsValues.get("red_boost", [0]*600)),
            "gradientFill": {
                0: (200,90,80,10),
                1: (200,90,80,120),
            }
        },
        {
            "data": uptimeBuffsValues.get("white_boost", [0]*600),
            "lineColor": (220,220,220),
            "average": getAverageBuff(uptimeBuffsValues.get("white_boost", [0]*600)),
            "gradientFill": {
                0: (220,220,220,10),
                1: (220,220,220,120),
            }
        }
        ]
        self.drawBuffUptimeGraphStackableBuff(y, dataset, "boost_buff", xData=buffXAxis)

        y += 460
        dataset = [
        {
            "data": uptimeBuffsValues.get("haste", [0]*600),
            "lineColor": (210,210,210),
            "average": getAverageBuff(uptimeBuffsValues.get("haste", [0]*600)),
            "gradientFill": {
                0: (210,210,210,10),
                1: (210,210,210,120),
            }
        }
        ]
        self.drawBuffUptimeGraphStackableBuff(y, dataset, "haste_buff", xData=buffXAxis)

        y += 460
        dataset = [
        {
            "data": uptimeBuffsValues.get("focus", [0]*600),
            "lineColor": (30,191,5),
            "average": getAverageBuff(uptimeBuffsValues.get("focus", [0]*600)),
            "gradientFill": {
                0: (30,191,5,10),
                1: (30,191,5,120),
            }
        }
        ]
        self.drawBuffUptimeGraphStackableBuff(y, dataset, "focus_buff", xData=buffXAxis)

        y += 460
        dataset = [
        {
            "data": uptimeBuffsValues.get("bomb_combo", [0]*600),
            "lineColor": (160,160,160),
            "average": getAverageBuff(uptimeBuffsValues.get("bomb_combo", [0]*600)),
            "gradientFill": {
                0: (160,160,160,10),
                1: (160,160,160,120),
            }
        }
        ]
        self.drawBuffUptimeGraphStackableBuff(y, dataset, "bomb_combo_buff", xData=buffXAxis)

        y += 460
        dataset = [
        {
            "data": uptimeBuffsValues.get("balloon_aura", [0]*600),
            "lineColor": (50,80,200),
            "average": getAverageBuff(uptimeBuffsValues.get("balloon_aura", [0]*600)),
            "gradientFill": {
                0: (50,80,200,10),
                1: (50,80,200,120),
            }
        }
        ]
        self.drawBuffUptimeGraphStackableBuff(y, dataset, "balloon_aura_buff", xData=buffXAxis)

        y += 460
        dataset = [
        {
            "data": uptimeBuffsValues.get("inspire", [0]*600),
            "lineColor": (195,191,18),
            "average": getAverageBuff(uptimeBuffsValues.get("inspire", [0]*600)),
            "gradientFill": {
                0: (195,191,18,10),
                1: (195,191,18,120),
            }
        }
        ]
        self.drawBuffUptimeGraphStackableBuff(y, dataset, "inspire_buff", xData=buffXAxis)

        y += 260
        dataset = [
        {
            "data": uptimeBuffsValues.get("melody", [0]*600),
            "lineColor": (200,200,200),
            "gradientFill": {
                0: (200,200,200,255),
                1: (200,200,200,255),
            }
        }
        ]
        self.drawBuffUptimeGraphUnstackableBuff(y, dataset, "melody_buff", xData=buffXAxis)

        y += 260
        dataset = [
        {
            "data": uptimeBuffsValues.get("bear", [0]*600),
            "lineColor": (115,71,40),
            "gradientFill": {
                0: (115,71,40,255),
                1: (115,71,40,255),
            }
        }
        ]
        self.drawBuffUptimeGraphUnstackableBuff(y, dataset, "bear_buff", xData=buffXAxis)

        y += 260
        dataset = [
        {
            "data": uptimeBuffsValues.get("baby_love", [0]*600),
            "lineColor": (112,181,195),
            "gradientFill": {
                0: (112,181,195,255),
                1: (112,181,195,255),
            }
        }
        ]
        self.drawBuffUptimeGraphUnstackableBuff(y, dataset, "baby_love_buff", renderTime=True, xData=buffXAxis, xLabelFunc=buffTimeLabel)

        #side bar - Session Summary
        y2 = 470
        self.drawPanel(self.sidebarX, y2, self.sidebarPanelWidth, 1220, accent=self.primaryColor, fill=self.tintedSurface(self.primaryColor, 0.08))
        headerBottom = self.drawSectionHeader(self.sidebarX + 50, y2 + 44, self.sidebarPanelWidth - 100, "Session Snapshot", "High-level totals for the completed run.", accent=self.primarySoftColor)
        y2 = headerBottom + 18

        totalSessionTime = sessionStats.get("total_session_time", 0)
        self.drawSessionStat(y2, "time_icon", "Total Runtime", self.displayTime(totalSessionTime, ['d','h','m']), self.bodyColor)
        y2 += 238

        finalHoney = onlyValidHourlyHoney[-1] if onlyValidHourlyHoney else 0
        self.drawSessionStat(y2, "honey_icon", "Final Honey", self.millify(finalHoney), self.honeyColor)
        y2 += 238

        self.drawSessionStat(y2, "session_honey_icon", "Total Gained", self.millify(totalHoney), "#FDE395")
        y2 += 238

        avgSidebarLabel = "Est. Avg/Hour" if totalSessionTime < 3600 else "Avg/Hour"
        self.drawSessionStat(y2, "average_icon", avgSidebarLabel, self.millify(avgHoneyPerHour), self.secondaryAccentColor)

        y2 += 330
        taskPanelHeight = self.getTaskTimesPanelHeight(4)
        self.drawPanel(self.sidebarX, y2, self.sidebarPanelWidth, taskPanelHeight, accent=self.secondaryAccentColor, fill=self.tintedSurface(self.secondaryAccentColor, 0.06))
        headerBottom = self.drawSectionHeader(self.sidebarX + 50, y2 + 44, self.sidebarPanelWidth - 100, "Time Breakdown", "Where the macro spent the session.", accent=self.secondaryAccentColor)
        y2 = headerBottom + 18

        gatherTime = sessionStats.get("gathering_time", 0)
        convertTime = sessionStats.get("converting_time", 0)
        bugRunTime = sessionStats.get("bug_run_time", 0)
        miscTime = sessionStats.get("misc_time", 0)

        self.drawTaskTimes(y2, [
            {
                "label": "Gathering",
                "data": gatherTime,
                "color": self.primarySoftColor
            },
            {
                "label": "Converting",
                "data": convertTime,
                "color": self.honeyColor
            },
            {
                "label": "Bug Runs",
                "data": bugRunTime,
                "color": self.secondaryAccentColor
            },
            {
                "label": "Other",
                "data": miscTime,
                "color": "#6C5B4E"
            },
        ], totalSessionTime)

        sectionGap = 80
        y2 += taskPanelHeight + sectionGap
        planterNames = []
        planterTimes = []
        planterFields = []
        if planterData:
            for i in range(len(planterData["planters"])):
                if planterData["planters"][i]:
                    planterNames.append(planterData["planters"][i])
                    planterTimes.append(planterData["harvestTimes"][i] - time.time())
                    planterFields.append(planterData["fields"][i])
        if planterNames:
            planterRows = max(1, math.ceil(len(planterNames) / 2))
            planterHeight = planterRows * 600 + max(0, planterRows - 1) * 40
            self.drawPanel(self.sidebarX, y2, self.sidebarPanelWidth, planterHeight + 250, accent=self.primaryColor, fill=self.tintedSurface(self.primaryColor, 0.07))
            headerBottom = self.drawSectionHeader(self.sidebarX + 50, y2 + 44, self.sidebarPanelWidth - 100, "Planters", "Current placements carried into the final snapshot.", accent=self.primaryColor)
            self.drawPlanters(headerBottom + 18, planterNames, planterTimes, planterFields)
            y2 += planterHeight + 290
        
        buffPanelHeight = 820
        self.drawPanel(self.sidebarX, y2, self.sidebarPanelWidth, buffPanelHeight, accent=self.secondaryAccentColor, fill=self.tintedSurface(self.secondaryAccentColor, 0.05))
        headerBottom = self.drawSectionHeader(self.sidebarX + 50, y2 + 44, self.sidebarPanelWidth - 100, "Buffs", "Final captured stack values.", accent=self.secondaryAccentColor)
        self.drawBuffs(headerBottom + 30, buffQuantity)

        y2 += buffPanelHeight + sectionGap
        nectarPanelHeight = 920
        self.drawPanel(self.sidebarX, y2, self.sidebarPanelWidth, nectarPanelHeight, accent=self.honeyColor, fill=self.tintedSurface(self.honeyColor, 0.05))
        headerBottom = self.drawSectionHeader(self.sidebarX + 50, y2 + 44, self.sidebarPanelWidth - 100, "Nectars", "Session-end field nectar percentages.", accent=self.honeyColor)
        self.drawNectars(headerBottom + 38, nectarQuantity)

        return self.canvas


class FinalReport:
    """Handles final session report generation"""
    
    def __init__(self, hourlyReport: HourlyReport = None):
        """
        Initialize FinalReport
        
        Args:
            hourlyReport: Existing HourlyReport instance to get data from
        """
        self.hourlyReport = hourlyReport if hourlyReport else HourlyReport()
        self.drawer = FinalReportDrawer()

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
    
    def generateFinalReport(self, setdat):
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
        
        # Use the most recent values captured by the hourly report instead of live detection.
        buffQuantity = list(getattr(self.hourlyReport, "latestBuffQuantity", []))
        nectarQuantity = list(getattr(self.hourlyReport, "latestNectarQuantity", []))
        if len(buffQuantity) < len(self.hourlyReport.hourBuffs):
            buffQuantity += [0] * (len(self.hourlyReport.hourBuffs) - len(buffQuantity))
        else:
            buffQuantity = buffQuantity[:len(self.hourlyReport.hourBuffs)]
        if len(nectarQuantity) < 5:
            nectarQuantity += [0] * (5 - len(nectarQuantity))
        else:
            nectarQuantity = nectarQuantity[:5]

        # Get planter data
        planterData = ""
        try:
            if setdat.get("planters_mode") == 1:
                try:
                    with open("./data/user/manualplanters.txt", "r") as f:
                        planterData = f.read()
                    if planterData:
                        planterData = ast.literal_eval(planterData)
                except (FileNotFoundError, SyntaxError, ValueError):
                    planterData = ""
            elif setdat.get("planters_mode") == 2:
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
        if len(rawHoneyPerMin) < 3:
            rawHoneyPerMin = [0] * (3 - len(rawHoneyPerMin)) + rawHoneyPerMin

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
        
        if self.hourlyReport.hourlyReportStats.get("start_time"):
            sessionTime = time.time() - self.hourlyReport.hourlyReportStats["start_time"]
        elif len(normalizedHoneyPerMin) > 1:
            # Fallback for legacy/missing start_time data.
            sessionTime = (len(normalizedHoneyPerMin) - 1) * 60
        
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

        # Determine enabled fields and their patterns from profile settings.
        enabled_fields = []
        field_patterns = {}
        try:
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

        # Draw the comprehensive final report
        try:
            canvas = self.drawer.drawFinalReport(
                hourlyReportStats, sessionStats, honeyPerSec, 
                sessionHoney, onlyValidHourlyHoney, 
                buffQuantity, nectarQuantity, planterData, 
                self.hourlyReport.sessionUptimeBuffsValues, self.hourlyReport.sessionBuffGatherIntervals,
                enabled_fields, field_patterns
            )
            
            # Resize for better quality
            w, h = canvas.size
            canvas = canvas.resize((int(w*1.2), int(h*1.2)))
            
            # Save to the correct location
            canvas.save("finalReport.png")
            print("Final report saved successfully to finalReport.png")
            
            return sessionStats
        except Exception as e:
            print(f"Error drawing final report: {e}")
            import traceback
            traceback.print_exc()
            return None
