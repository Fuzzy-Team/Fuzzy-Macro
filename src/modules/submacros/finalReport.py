import time
import copy
import json
import ast
import statistics
from modules.submacros.hourlyReport import HourlyReport, HourlyReportDrawer
from modules.misc.settingsManager import loadFields


class FinalReportDrawer(HourlyReportDrawer):
    """Compatibility wrapper around the shared report drawer template."""

    pass


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

        def hasTimelineData(buffMap):
            if not isinstance(buffMap, dict):
                return False
            return any(len(values) > 0 for values in buffMap.values())

        # Prefer full-session buff history when available.
        if not hasattr(self.hourlyReport, 'sessionUptimeBuffsValues') or not hasTimelineData(self.hourlyReport.sessionUptimeBuffsValues):
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
                getattr(self.hourlyReport, "sessionQuestCompletions", []),
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
