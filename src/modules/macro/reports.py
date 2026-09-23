import cv2
import traceback
from datetime import datetime
import modules.logging.log as logModule
import modules.misc.settingsManager as settingsManager
import modules.screen.ocr as ocr
from modules.controls.sleep import pause_aware_time as time
from modules.screen.screenshot import mssScreenshot
from modules.submacros.hourlyReport import BUFF_RENDER_CONFIG
from modules.submacros.liveGatherReport import LiveGatherReport, LiveQuestProgressReport


class ReportMixin:
    def liveGatherReportEnabled(self):
        return (
            (logModule.delivery_uses_webhook(self.setdat) or logModule.delivery_uses_bot_messages(self.setdat))
            and self.setdat.get("live_gather_report", self.setdat.get("live_honey_report", False))
            and not self.setdat.get("only_send_hourly_report", False)
        )

    def createLiveGatherReport(self, route_category="gathering"):
        return LiveGatherReport(
            logModule.get_default_delivery_route(self.setdat),
            self.robloxWindow,
            self.setdat.get("live_gather_report_interval", 10),
            self.setdat.get("webhook_time_format", 24),
            logModule.build_route_settings(self.setdat),
            self.setdat.get("discord_bot_token", ""),
            None,
            logModule.get_delivery_mode(self.setdat),
            route_category,
        )

    def createLiveQuestProgressReport(self):
        return LiveQuestProgressReport(
            logModule.get_default_delivery_route(self.setdat),
            self.robloxWindow,
            self.setdat.get("live_gather_report_interval", 10),
            self.setdat.get("webhook_time_format", 24),
            logModule.build_route_settings(self.setdat),
            self.setdat.get("discord_bot_token", ""),
            None,
            logModule.get_delivery_mode(self.setdat),
            "quests",
            capture_quest_screen=self.captureQuestWatchScreen,
        )

    def getHoney(self):
        cap = mssScreenshot(self.robloxWindow.mx+(self.robloxWindow.mw//2-241), self.robloxWindow.my+self.robloxWindow.yOffset+5, 140, 36)
        ocrres = ocr.ocrFunc(cap)
        honeyText = ""
        try:
            result = ''.join([x[1][0] for x in ocrres])
            for i in result:
                if i == "(" or i == "+":
                    break
                elif i.isdigit():
                    honeyText += i
            if honeyText:
                return int(honeyText)
        except Exception:
            pass
        return 0

    def hourlyReportBackgroundOnce(self):
        try:
            currMin = datetime.now().minute
            currSec = datetime.now().second

            #check if its time to send hourly report
            if currMin == 0 and time.time() - self.lastHourlyReport > 120:
                itemSnapshot = self.itemMonitor.get_snapshot() if self.setdat.get("item_monitor", True) else None
                hourlyReportData = self.hourlyReport.generateHourlyReport(self.setdat)
                self.logger.hourlyReport("Hourly Report", "", "purple", fields=getattr(self.hourlyReport, "lastEmbedFields", None))

                if itemSnapshot and itemSnapshot.get("collected_items"):
                    try:
                        from modules.submacros.itemMonitor import generate_item_report
                        path, fields = generate_item_report(itemSnapshot, self.setdat, report_type="hourly")
                        if path:
                            self.logger.itemReport("Item Monitor", "", "purple", fields=fields, imagePath=path)
                    except Exception:
                        self.logger.webhook("Item Monitor Error", traceback.format_exc(), "red", ping_category="ping_critical_errors")

                #add to history
                history = settingsManager.loadUserLiteral("hourly_report_history.txt")
                if not isinstance(history, list):
                    history = []

                historyObj = {
                    "endHour": datetime.now().hour,
                    "date": str(datetime.today().date()),
                    "honey": hourlyReportData["honey_per_min"][-1] - hourlyReportData["honey_per_min"][0]
                }
                #max 5 objs
                if len(history) > 4:
                    history.pop(-1)
                history.insert(0,historyObj)

                settingsManager.saveUserLiteral("hourly_report_history.txt", history)

                self.lastHourlyReport = time.time()
                #reset stats
                self.hourlyReport.resetHourlyStats()
                self.itemMonitor.reset_hourly()

            #Hourly report
            if self.status.value != "rejoining":
                #instead of using time.sleep, we want to run the code at the start of the min
                if currMin != self.prevMin:
                    self.prevMin = currMin
                    honey = self.getHoney()
                    print(honey)
                    backpack = self.getBackpack()

                    self.hourlyReport.addHourlyStat("honey_per_min", honey)
                    self.hourlyReport.addHourlyStat("backpack_per_min", backpack)

            # Item monitor: loot toast detection
            if (
                self.setdat.get("item_monitor", True)
                and self.status.value != "rejoining"
                and currSec != getattr(self, "prevItemMonitorSec", -1)
            ):
                self.prevItemMonitorSec = currSec
                try:
                    self.itemMonitor.detect_once()
                    self.hourlyReport.itemMonitorSnapshot = self.itemMonitor.get_snapshot()
                except Exception:
                    pass

            if self.status.value != "rejoining" and not currSec%6 and currSec != self.prevSec:
                i = (60*currMin + currSec)//6
                screen = cv2.cvtColor(self.buffDetector.screenshotBuffArea(), cv2.COLOR_BGRA2BGR)
                height, width = screen.shape[:2]
                uptimeBuffsColors = self.hourlyReport.uptimeBuffsColors
                uptimeBuffsColorVariations = getattr(self.hourlyReport, "uptimeBuffsColorVariations", {})
                uptimeBearBuffs = self.hourlyReport.uptimeBearBuffs
                monitoredBuffs = set(self.hourlyReport.configuredUptimeBuffDataKeys(self.setdat))
                selectedUptimeRows = set(self.hourlyReport.configuredUptimeBuffs)

                sampleValues = {}
                def parseOcrBuffValue(value, default=1):
                    try:
                        parsed = float(value)
                        return parsed if parsed > 0 else default
                    except (TypeError, ValueError):
                        return default

                if "baby_love" in monitoredBuffs:
                    j = "baby_love"
                    if self.buffDetector.detectBuffColorInImage(screen, uptimeBuffsColors[j][0], uptimeBuffsColors[j][1], y1=30*self.multi, variation=uptimeBuffsColorVariations.get(j, 0), searchDirection=7):
                        sampleValues[j] = 1

                if "bear" in monitoredBuffs:
                    bearBuffRes = [int(x) for x in self.buffDetector.getBuffsWithImage(uptimeBearBuffs, screen=screen, threshold=0.78)]
                    if any(bearBuffRes):
                        sampleValues["bear"] = 1

                for j in [key for key in selectedUptimeRows if key in uptimeBuffsColors and key not in {"baby_love", "haste", "melody", "boost", "bear"}]:
                    res = self.buffDetector.detectBuffColorInImage(screen, uptimeBuffsColors[j][0], uptimeBuffsColors[j][1], y1=30*self.multi, y2=50*self.multi, variation=uptimeBuffsColorVariations.get(j, 0), searchDirection=7)
                    if res:
                        chartType = BUFF_RENDER_CONFIG.get(j, ("binary",))[0]
                        if chartType == "binary":
                            sampleValues[j] = 1
                        elif j == "blessing":
                            sampleValues[j] = min(100, parseOcrBuffValue(
                                self.buffDetector.getBuffQuantityFromDetectedRect(screen, res, buff=j)
                            ))
                        else:
                            sampleValues[j] = parseOcrBuffValue(
                                self.buffDetector.getBuffQuantityFromDetectedRect(screen, res, buff=j)
                            )

                if "haste" in monitoredBuffs or "melody" in monitoredBuffs:
                    x = 0
                    for _ in range(3):
                        res = self.buffDetector.detectBuffColorInImage(screen, uptimeBuffsColors["haste"][0], uptimeBuffsColors["haste"][1],x, 30*self.multi, variation=uptimeBuffsColorVariations.get("haste", 0), searchDirection=6)
                        if not res:
                            break
                        x = res[0]
                        if "melody" in monitoredBuffs and self.buffDetector.detectBuffColorInImage(screen, uptimeBuffsColors["melody"][0], uptimeBuffsColors["melody"][1], x+2*self.multi, 30, x+34*self.multi, 40*self.multi, max(12, uptimeBuffsColorVariations.get("melody", 0))):
                            sampleValues["melody"] = 1
                        elif "haste" in monitoredBuffs and not sampleValues.get("haste", 0):
                            x1 = max(0, int(x+6*self.multi))
                            x2 = min(width, int(x+44*self.multi))
                            buffImg = screen[15*self.multi:50*self.multi , x1:x2]
                            sampleValues["haste"] = parseOcrBuffValue(
                                self.buffDetector.getBuffQuantityFromImgTight(buffImg)
                            )
                        x += 44*self.multi
                #print(bd.detectBuffColorInImage(screen, 0xff242424, variation=12, minSize=(3*2,2*2), show=True))

                if any(buff in monitoredBuffs for buff in ("blue_boost", "red_boost", "white_boost")):
                    x = screen.shape[1]
                    for _ in range(3):
                        res = self.buffDetector.detectBuffColorInImage(screen, uptimeBuffsColors["boost"][0], uptimeBuffsColors["boost"][1], y1=30*self.multi, x2=x, variation=uptimeBuffsColorVariations.get("boost", 0), searchDirection=7)
                        if not res:
                            break
                        x = res[0]+res[2]

                        if len(self.buffDetector.detectBuffColorInImage(screen, uptimeBuffsColors["red_boost"][0], uptimeBuffsColors["red_boost"][1], x-30*self.multi, 15*self.multi, x-4*self.multi, 34*self.multi, max(20, uptimeBuffsColorVariations.get("red_boost", 0)))):
                            buffType = "red_boost"
                        elif len(self.buffDetector.detectBuffColorInImage(screen, uptimeBuffsColors["blue_boost"][0], uptimeBuffsColors["blue_boost"][1], x-30*self.multi, 15*self.multi, x-4*self.multi, 34*self.multi, max(20, uptimeBuffsColorVariations.get("blue_boost", 0)))):
                            buffType = "blue_boost"
                        else:
                            buffType = "white_boost"

                        if buffType in monitoredBuffs:
                            x1 = max(0, int(x-25*self.multi))
                            y1 = int(15*self.multi)
                            y2 = int(50*self.multi)
                            buffImg = screen[y1:y2, x1: int(x)]
                            sampleValues[buffType] = parseOcrBuffValue(
                                self.buffDetector.getBuffQuantityFromImgTight(buffImg)
                            )

                        x -= 40*self.multi
                
                self.prevSec = currSec

                isGathering = "gather_" in self.status.value
                self.hourlyReport.recordUptimeSample(i, sampleValues, isGathering=isGathering, monitoredBuffs=monitoredBuffs)
                self.hourlyReport.saveHourlyReportData()
        except Exception:
            self.logger.webhook("Hourly Report Error", traceback.format_exc(), "red", ping_category="ping_critical_errors")

    def hourlyReportBackground(self):
        while True:
            self.hourlyReportBackgroundOnce()
            time.sleep(1)
