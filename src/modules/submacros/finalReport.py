from PIL import Image, ImageDraw
import time
import copy
import json
import ast
import pickle
import statistics
from modules.submacros.hourlyReport import HourlyReport, HourlyReportDrawer
from modules.misc.settingsManager import getCurrentProfile, getMacroVersion


class FinalReportDrawer(HourlyReportDrawer):
    """Drawer for final session reports, inherits from HourlyReportDrawer"""
    
    def drawFinalReport(self, hourlyReportStats, sessionStats, honeyPerSec, sessionHoney, onlyValidHourlyHoney, buffQuantity, nectarQuantity, planterData, uptimeBuffsValues, buffGatherIntervals):
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

        self.canvas = Image.new('RGBA', self.canvasSize, self.backgroundColor)
        self.draw = ImageDraw.Draw(self.canvas)

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

        #draw aside bar
        self.draw.rectangle((self.canvasSize[0]-self.sidebarWidth, 0, self.canvasSize[0], self.canvasSize[1]), fill=self.sideBarBackground)

        #draw icon and title (matches hourly report styling)
        macroIcon = Image.open(f"{self.assetPath}/macro_icon.png").convert("RGBA")
        # Resize icon to a more appropriate size for the top-right header
        icon_w, icon_h = (200, 200)
        macroIcon = macroIcon.resize((icon_w, icon_h), Image.LANCZOS)
        icon_x = 5550
        icon_y = 100
        self.canvas.paste(macroIcon, (icon_x, icon_y), macroIcon)

        # Position the title text to the right of the icon and vertically center
        title_x = icon_x + icon_w + 30
        title_text = "Fuzzy Macro"
        try:
            profile_name = getCurrentProfile()
        except Exception:
            profile_name = None
        profile_text = f"Profile: {profile_name}" if profile_name else None

        title_font = self.getFont("semibold", 80)
        profile_font = self.getFont("medium", 60)

        title_bbox = self.draw.textbbox((0, 0), title_text, font=title_font)
        title_h = title_bbox[3] - title_bbox[1]
        profile_h = 0
        spacing = 10
        if profile_text:
            profile_bbox = self.draw.textbbox((0, 0), profile_text, font=profile_font)
            profile_h = profile_bbox[3] - profile_bbox[1]

        total_text_h = title_h + (spacing + profile_h if profile_text else 0)
        text_top = icon_y + (icon_h - total_text_h) // 2

        # draw title and optional profile
        self.draw.text((title_x, text_top), title_text, fill=self.bodyColor, font=title_font)
        if profile_text:
            self.draw.text((title_x, text_top + title_h + spacing), profile_text, fill=self.bodyColor, font=profile_font)

        # draw macro version below profile/title if available
        try:
            macro_version = getMacroVersion()
            version_text = f"v{macro_version}"
            version_font = self.getFont("medium", 40)
            version_y = text_top + title_h + spacing + (profile_h + 10 if profile_text else 10)
            self.draw.text((title_x, version_y), version_text, fill=self.bodyColor, font=version_font)
        except Exception:
            pass

        #draw title - FINAL REPORT
        self.draw.text((self.leftPadding, 80), "Session Summary", fill=self.bodyColor, font=self.getFont("bold", 120))
        sessionTimeStr = formatTime(sessionTime)
        self.draw.text((self.leftPadding, 260), f"Total Runtime: {sessionTimeStr}", fill=self.bodyColor, font=self.getFont("medium", 60))

        #section 1: session stats - ENHANCED FOR FINAL REPORT
        y = 470
        statSpacing = (self.availableSpace+self.leftPadding)//5
        
        # Show average honey per hour (with "Estimated" if less than 1 hour)
        avgHoneyPerHour = sessionStats.get("avg_honey_per_hour", 0)
        sessionTime = sessionStats.get("total_session_time", 0)
        avgLabel = "Estimated Avg\nPer Hour" if sessionTime < 3600 else "Average Honey\nPer Hour"
        self.drawStatCard(self.leftPadding, y, "average_icon", self.millify(avgHoneyPerHour), avgLabel)
        
        # Show total honey made
        totalHoney = sessionStats.get("total_honey", 0)
        self.drawStatCard(self.leftPadding+statSpacing*1, y, "honey_icon", self.millify(totalHoney), "Total Honey\nThis Session", (248,191,23))
        
        # Show bugs killed
        totalBugs = sessionStats.get("total_bugs", 0)
        self.drawStatCard(self.leftPadding+statSpacing*2, y, "kill_icon", totalBugs, "Bugs Killed\nThis Session", (254,101,99), (254,101,99))
        
        # Show quests completed
        totalQuests = sessionStats.get("total_quests", 0)
        self.drawStatCard(self.leftPadding+statSpacing*3, y, "quest_icon", totalQuests, "Quests Completed\nThis Session", (103,253,153), (103,253,153))
        
        # Show vicious bees
        totalVicious = sessionStats.get("total_vicious_bees", 0)
        self.drawStatCard(self.leftPadding+statSpacing*4, y, "vicious_bee_icon", totalVicious, "Vicious Bees\nThis Session", (132,233,254), (132,233,254))

        #section 2: honey/sec over session
        y += 900
        self.draw.text((self.leftPadding, y), "Honey/Sec Over Time", fill=self.bodyColor, font=self.getFont("semibold", 85))
        
        # Add peak rate indicator
        peakRate = sessionStats.get("peak_honey_rate", 0)
        self.draw.text((self.leftPadding + 1200, y), f"Peak: {self.millify(peakRate)}/s", fill=(174, 22, 250), font=self.getFont("medium", 65))
        
        y += 950
        dataset = [{
            "data": honeyPerSec,
            "lineColor": (174, 22, 250),
            "gradientFill": {
                0: (174,22,250,38),
                1: (174,22,250,153)
            }
        }]
        
        # Use different x-label function for session view
        def sessionTimeLabel(i, val):
            """Format time labels based on session duration"""
            if val == 0:
                return "0m"
            if sessionTime < 3600:  # Less than 1 hour
                return f"{int(val)}m"
            elif sessionTime < 86400:  # Less than 24 hours
                return f"{int(val/60)}h"
            else:  # Multiple days
                return f"{int(val/1440)}d"

        def buffTimeLabel(i, val):
            if buffSampleCount <= 1:
                return "0m" if i == 0 else None

            labelCount = 6 if sessionTime >= 3600 else 5
            step = max(1, (buffSampleCount - 1) // labelCount)
            if i not in (0, buffSampleCount - 1) and i % step:
                return None
            return sessionTimeLabel(i, val)
        
        self.drawGraph(self.leftPadding+450, y, self.availableSpace-570, 700, mins, dataset, xLabelFunc=sessionTimeLabel, yLabelFunc=lambda i,x : self.millify(x))

        #section 3: backpack utilization over session
        y += 200
        self.draw.text((self.leftPadding, y), "Backpack Utilization", fill=self.bodyColor, font=self.getFont("semibold", 85))
        y += 950
        
        # Ensure backpack data exists and has same length as time data
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
        self.drawGraph(self.leftPadding+450, y, self.availableSpace-570, 700, mins, dataset, maxY=100, xLabelFunc=sessionTimeLabel, yLabelFunc=lambda i,x: f"{int(x)}%")

        #section 4: buff uptime (session average)
        y += 200
        self.draw.text((self.leftPadding, y), "Average Buff Uptime", fill=self.bodyColor, font=self.getFont("semibold", 85))
        
        # Add note about session average
        self.draw.text((self.leftPadding + 1200, y), "(Session Average)", fill=(150, 150, 150), font=self.getFont("medium", 55))
        
        y += 750
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
        self.sidebarPadding = 110
        self.sidebarX = self.canvasSize[0] - self.sidebarWidth + self.sidebarPadding
        self.draw.text((self.sidebarX, y2), "Session Stats", font=self.getFont("semibold", 85), fill=self.bodyColor)
        y2 += 250
        
        # Total session time
        totalSessionTime = sessionStats.get("total_session_time", 0)
        self.drawSessionStat(y2, "time_icon", "Total Runtime", self.displayTime(totalSessionTime, ['d','h','m']), self.bodyColor)
        y2 += 300
        
        # Final honey amount
        finalHoney = onlyValidHourlyHoney[-1] if onlyValidHourlyHoney else 0
        self.drawSessionStat(y2, "honey_icon", "Final Honey", self.millify(finalHoney), "#F8BF17")
        y2 += 300
        
        # Total honey made in session
        totalHoney = sessionStats.get("total_honey", 0)
        self.drawSessionStat(y2, "session_honey_icon", "Total Gained", self.millify(totalHoney), "#FDE395")
        y2 += 300
        
        # Average honey per hour (with "Est." if less than 1 hour)
        avgHoneyPerHour = sessionStats.get("avg_honey_per_hour", 0)
        totalSessionTime = sessionStats.get("total_session_time", 0)
        avgSidebarLabel = "Est. Avg/Hour" if totalSessionTime < 3600 else "Avg/Hour"
        self.drawSessionStat(y2, "average_icon", avgSidebarLabel, self.millify(avgHoneyPerHour), "#00FF88")

        #task time breakdown
        y2 += 500
        self.draw.text((self.sidebarX, y2), "Time Breakdown", font=self.getFont("semibold", 85), fill=self.bodyColor)
        y2 += 250
        
        gatherTime = sessionStats.get("gathering_time", 0)
        convertTime = sessionStats.get("converting_time", 0)
        bugRunTime = sessionStats.get("bug_run_time", 0)
        miscTime = sessionStats.get("misc_time", 0)
        
        self.drawTaskTimes(y2, [
            {
                "label": "Gathering",
                "data": gatherTime,
                "color": "#6A0DAD"
            },
            {
                "label": "Converting",
                "data": convertTime,
                "color": "#9966FF"
            },
            {
                "label": "Bug Runs",
                "data": bugRunTime,
                "color": "#C3A6FF"
            },
            {
                "label": "Other",
                "data": miscTime,
                "color": "#E6D6FF"
            },
        ], totalSessionTime)

        #planters
        y2 += 1500
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
            self.draw.text((self.sidebarX, y2), "Planters", font=self.getFont("semibold", 85), fill=self.bodyColor)
            y2 += 250
            self.drawPlanters(y2, planterNames, planterTimes, planterFields)
            y2 += 650
        
        #buffs
        self.draw.text((self.sidebarX, y2), "Buffs", font=self.getFont("semibold", 85), fill=self.bodyColor)
        y2 += 250
        self.drawBuffs(y2, buffQuantity)

        #nectars
        y2 += 500
        self.draw.text((self.sidebarX, y2), "Nectars", font=self.getFont("semibold", 85), fill=self.bodyColor)
        y2 += 250
        self.drawNectars(y2, nectarQuantity)

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
                    planterData = settingsManager.loadManualPlanters()
                    planterData = settingsManager.loadManualPlanters()
                except (FileNotFoundError, SyntaxError, ValueError):
                    planterData = ""
            elif setdat.get("planters_mode") == 2:
                try:
                    planterData = settingsManager.loadAutoPlanters()["planters"]
                    planterData = settingsManager.loadAutoPlanters()["planters"]
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

        # Draw the comprehensive final report
        try:
            canvas = self.drawer.drawFinalReport(
                hourlyReportStats, sessionStats, honeyPerSec, 
                sessionHoney, onlyValidHourlyHoney, 
                buffQuantity, nectarQuantity, planterData, 
                self.hourlyReport.sessionUptimeBuffsValues, self.hourlyReport.sessionBuffGatherIntervals
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
