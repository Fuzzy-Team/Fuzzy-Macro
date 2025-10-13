from PIL import Image, ImageDraw
import time
import copy
import json
import ast
import pickle
from modules.submacros.hourlyReport import HourlyReport, HourlyReportDrawer


class FinalReportDrawer(HourlyReportDrawer):
    """Drawer for final session reports, inherits from HourlyReportDrawer"""
    
    def drawFinalReport(self, hourlyReportStats, sessionStats, honeyPerSec, sessionHoney, onlyValidHourlyHoney, buffQuantity, nectarQuantity, planterData, uptimeBuffsValues, buffGatherIntervals):
        """Draw comprehensive final report with session statistics and trends"""
        
        def getAverageBuff(buffValues):
            #get the buff average when gathering, rounded to 2p
            count = 0
            total = 0
            for i, e in enumerate(buffGatherIntervals):
                if e:
                    total += buffValues[i]
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
        dataPoints = len(honeyPerSec)
        
        # Create appropriate time labels based on session duration
        if sessionTime > 0:
            timeInterval = sessionTime / max(dataPoints - 1, 1) if dataPoints > 1 else 60
            mins = [i * timeInterval / 60 for i in range(dataPoints)]  # Convert to minutes for x-axis
        else:
            mins = list(range(dataPoints))

        #draw aside bar
        self.draw.rectangle((self.canvasSize[0]-self.sidebarWidth, 0, self.canvasSize[0], self.canvasSize[1]), fill=self.sideBarBackground)

        #draw icon
        macroIcon = Image.open(f"{self.assetPath}/macro_icon.png")
        self.canvas.paste(macroIcon, (5550, 100), macroIcon)
        self.draw.text((5750, 120), "Existance Macro", fill=self.bodyColor, font=self.getFont("semibold", 70))

        #draw title - FINAL REPORT
        self.draw.text((self.leftPadding, 80), "Session Summary", fill=self.bodyColor, font=self.getFont("bold", 120))
        sessionTimeStr = formatTime(sessionTime)
        self.draw.text((self.leftPadding, 260), f"Total Runtime: {sessionTimeStr}", fill=self.bodyColor, font=self.getFont("medium", 60))

        #section 1: session stats - ENHANCED FOR FINAL REPORT
        y = 470
        statSpacing = (self.availableSpace+self.leftPadding)//5
        
        # Show average honey per hour
        avgHoneyPerHour = sessionStats.get("avg_honey_per_hour", 0)
        self.drawStatCard(self.leftPadding, y, "average_icon", self.millify(avgHoneyPerHour), "Average Honey\nPer Hour")
        
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
            if sessionTime < 3600:  # Less than 1 hour
                return f"{int(val)}m"
            elif sessionTime < 86400:  # Less than 24 hours
                return f"{int(val/60)}h"
            else:  # Multiple days
                return f"{int(val/1440)}d"
        
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
        self.drawBuffUptimeGraphStackableBuff(y, dataset, "boost_buff")

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
        self.drawBuffUptimeGraphStackableBuff(y, dataset, "haste_buff")

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
        self.drawBuffUptimeGraphStackableBuff(y, dataset, "focus_buff")

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
        self.drawBuffUptimeGraphStackableBuff(y, dataset, "bomb_combo_buff")

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
        self.drawBuffUptimeGraphStackableBuff(y, dataset, "balloon_aura_buff")

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
        self.drawBuffUptimeGraphStackableBuff(y, dataset, "inspire_buff")

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
        self.drawBuffUptimeGraphUnstackableBuff(y, dataset, "melody_buff")

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
        self.drawBuffUptimeGraphUnstackableBuff(y, dataset, "bear_buff")

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
        self.drawBuffUptimeGraphUnstackableBuff(y, dataset, "baby_love_buff", renderTime=True)

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
        
        # Average honey per hour
        avgHoneyPerHour = sessionStats.get("avg_honey_per_hour", 0)
        self.drawSessionStat(y2, "average_icon", "Avg/Hour", self.millify(avgHoneyPerHour), "#00FF88")

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
        ])

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
                self.hourlyReport.uptimeBuffsValues = {}
                self.hourlyReport.buffGatherIntervals = [0]
            except:
                return None
        
        # Skip buff/nectar detection since we can't access in-game data after macro stops
        # These are set to empty for final report as game is likely stopped
        buffQuantity = [0] * len(self.hourlyReport.hourBuffs)
        nectarQuantity = [0, 0, 0, 0, 0]

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

        # Ensure we have valid data
        if not self.hourlyReport.hourlyReportStats.get("honey_per_min"):
            self.hourlyReport.hourlyReportStats["honey_per_min"] = [0]
        
        if len(self.hourlyReport.hourlyReportStats["honey_per_min"]) < 3:
            self.hourlyReport.hourlyReportStats["honey_per_min"] = [0]*3 + self.hourlyReport.hourlyReportStats["honey_per_min"]
        
        # Filter outliers from honey data
        self.hourlyReport.hourlyReportStats["honey_per_min"] = self.hourlyReport.filterOutliers(self.hourlyReport.hourlyReportStats["honey_per_min"])
        
        # Calculate honey/sec for the entire session
        honeyPerSec = [0]
        prevHoney = self.hourlyReport.hourlyReportStats["honey_per_min"][0]
        for x in self.hourlyReport.hourlyReportStats["honey_per_min"][1:]:
            if x > prevHoney:
                honeyPerSec.append((x-prevHoney)/60)
            else:
                honeyPerSec.append(0)
            prevHoney = x
        
        # Calculate session statistics
        if len(set(self.hourlyReport.hourlyReportStats["honey_per_min"])) <= 1:
            onlyValidHourlyHoney = self.hourlyReport.hourlyReportStats["honey_per_min"].copy()
        else:
            onlyValidHourlyHoney = [x for x in self.hourlyReport.hourlyReportStats["honey_per_min"] if x]
        
        # Calculate total session honey and time
        sessionHoney = 0
        sessionTime = 0
        if onlyValidHourlyHoney and self.hourlyReport.hourlyReportStats.get("start_honey"):
            sessionHoney = onlyValidHourlyHoney[-1] - self.hourlyReport.hourlyReportStats["start_honey"]
        
        if self.hourlyReport.hourlyReportStats.get("start_time"):
            sessionTime = time.time() - self.hourlyReport.hourlyReportStats["start_time"]
        
        # Calculate average honey per hour for the entire session
        avgHoneyPerHour = (sessionHoney / (sessionTime / 3600)) if sessionTime > 0 else 0
        
        # Calculate peak honey rate
        peakHoneyRate = max(honeyPerSec) if honeyPerSec else 0
        
        # Create a deep copy of stats to avoid modification
        hourlyReportStats = copy.deepcopy(self.hourlyReport.hourlyReportStats)
        
        # Add session summary stats
        sessionStats = {
            "total_session_time": sessionTime,
            "total_honey": sessionHoney,
            "avg_honey_per_hour": avgHoneyPerHour,
            "peak_honey_rate": peakHoneyRate,
            "total_bugs": hourlyReportStats.get("bugs", 0),
            "total_quests": hourlyReportStats.get("quests_completed", 0),
            "total_vicious_bees": hourlyReportStats.get("vicious_bees", 0),
            "gathering_time": hourlyReportStats.get("gathering_time", 0),
            "converting_time": hourlyReportStats.get("converting_time", 0),
            "bug_run_time": hourlyReportStats.get("bug_run_time", 0),
            "misc_time": hourlyReportStats.get("misc_time", 0)
        }

        # Ensure uptimeBuffsValues and buffGatherIntervals exist
        if not hasattr(self.hourlyReport, 'uptimeBuffsValues') or not self.hourlyReport.uptimeBuffsValues:
            self.hourlyReport.uptimeBuffsValues = {k:[0]*600 for k in self.hourlyReport.uptimeBuffsColors.keys()}
            self.hourlyReport.uptimeBuffsValues["bear"] = [0]*600
            self.hourlyReport.uptimeBuffsValues["white_boost"] = [0]*600
        
        if not hasattr(self.hourlyReport, 'buffGatherIntervals') or not self.hourlyReport.buffGatherIntervals:
            self.hourlyReport.buffGatherIntervals = [0]*600

        # Draw the comprehensive final report
        try:
            canvas = self.drawer.drawFinalReport(
                hourlyReportStats, sessionStats, honeyPerSec, 
                sessionHoney, onlyValidHourlyHoney, 
                buffQuantity, nectarQuantity, planterData, 
                self.hourlyReport.uptimeBuffsValues, self.hourlyReport.buffGatherIntervals
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

