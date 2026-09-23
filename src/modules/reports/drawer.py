"""Draw hourly, final, and item monitor report images."""
import math
import time
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
from modules.misc.settingsManager import getCurrentProfile, getMacroVersion
from modules.reports.buffs import (
    BUFF_RENDER_CONFIG,
    DEFAULT_HOURLY_BUFFS,
    DEFAULT_UPTIME_BUFFS,
    HOURLY_BUFF_ASSETS,
    MAX_HOURLY_BUFF_OPTIONS,
    MAX_UPTIME_BUFF_OPTIONS,
    normalizeHourlyBuffSelection,
)
from modules.reports.theme import (
    ACCENT_COLORS,
    MACRO_BASE_BG_MIX,
    MACRO_TINT_SATURATION,
    mixColor,
    saturate,
    THEMES,
)


class HourlyReportDrawer:
    def __init__(self, time_format=24, theme="dark", accent="green"):
        t = THEMES.get(theme, THEMES["dark"])
        self.backgroundColor = t["bg"]
        self.sideBarBackground = t["sidebar_bg"]
        self.cardBackground = t["card_bg"]
        self.bodyColor = t["text_primary"]
        self.subtleColor = t["text_secondary"]
        self.gridColor = t["grid"]
        self.gatherColor = t["gather"]
        self.convertColor = t["convert"]
        self.otherColor = t["other"]
        self.honeyColor = t["honey"]
        # Macro themes bake in their own accent (the webapp --primary); fall back
        # to the configurable accent palette for the legacy dark/midnight/oled themes.
        self.accentColor = t.get("accent", ACCENT_COLORS.get(accent, ACCENT_COLORS["green"]))
        self.accentColorDim = tuple(max(0, int(c * 0.35)) for c in self.accentColor)

        # Panel / graph chrome. For macro themes this is tinted toward the accent
        # so the whole report (panels, graph backgrounds, gridlines) reflects the
        # theme, not just the highlight line. The canvas base (behind/between the
        # panels) gets only a very faint tint so it reads as a dark backdrop.
        # Legacy themes keep the neutral look.
        if "accent" in t:
            tint = saturate(self.accentColor, MACRO_TINT_SATURATION)
            self.baseBackgroundColor = mixColor((18, 18, 18), tint, MACRO_BASE_BG_MIX)
            self.panelColor     = mixColor((32, 30, 32), tint, 0.15)
            self.panelOutline   = mixColor((40, 38, 40), tint, 0.20)
            self.graphBgColor   = mixColor((20, 20, 20), tint, 0.10)
            self.graphGridColor = mixColor((47, 47, 55), tint, 0.22)
            self.graphTickColor = mixColor((64, 60, 78), tint, 0.22)
        else:
            self.baseBackgroundColor = (18, 18, 18)
            self.panelColor     = (32, 30, 32)
            self.panelOutline   = (40, 38, 40)
            self.graphBgColor   = (20, 20, 20)
            self.graphGridColor = (47, 47, 55)
            self.graphTickColor = (64, 60, 78)

        # canvas width is fixed; height is dynamic (cropped to content at the end)
        self.canvasW = 5800
        self.canvasMaxH = 20000  # generous working height, cropped down after drawing
        self.canvasSize = (self.canvasW, self.canvasMaxH)
        self.sidebarWidth = 1650
        self.leftPadding = 150
        self.sidebarPadding = 110
        self.availableSpace = self.canvasW - self.sidebarWidth - self.leftPadding*2
        self.time_format = time_format
        self.hour = datetime.now().hour
        if self.hour == 0:
            self.hour = 23
        else:
            self.hour -= 1
        self.assetPath = "hourly_report/assets"

    def normalizeUptimeBuffList(self, buffList):
        seen = set()
        normalized = []
        for buff in buffList or []:
            key = str(buff).strip().lower().replace(" ", "_")
            if key in BUFF_RENDER_CONFIG and key not in seen:
                normalized.append(key)
                seen.add(key)
            if len(normalized) >= MAX_UPTIME_BUFF_OPTIONS:
                break
        return normalized or DEFAULT_UPTIME_BUFFS[:MAX_UPTIME_BUFF_OPTIONS]

    def _fitText(self, text, maxWidth, weight="semibold", size=60, minSize=28):
        size = int(size)
        while size > minSize:
            font = self.getFont(weight, size)
            bbox = self.draw.textbbox((0, 0), str(text), font=font)
            if bbox[2] - bbox[0] <= maxWidth:
                return font
            size -= 4
        return self.getFont(weight, minSize)

    def _drawPanel(self, box, title=None, titleSize=64):
        x, y, w, h = box
        self.draw.rounded_rectangle((x, y, x + w, y + h), radius=20, fill=self.panelColor, outline=self.panelOutline, width=10)
        if title:
            font = self.getFont("bold", titleSize)
            bbox = self.draw.textbbox((0, 0), title, font=font)
            self.draw.text((x + (w - (bbox[2] - bbox[0])) / 2, y + 16), title, font=font, fill=self.bodyColor)

    def _compositeRGBA(self, overlay, box):
        """Alpha-composite an RGBA overlay onto the canvas at `box` (x0, y0, x1, y1).

        Pillow's ImageDraw writes alpha into destination pixels instead of blending,
        so translucent fills must be drawn on a temp layer and composited here.
        Otherwise the saved PNG keeps partial alpha and Discord (etc.) blends the
        report against its own background — the muddy grey chart look.
        """
        x0, y0, x1, y1 = box
        if x1 <= x0 or y1 <= y0:
            return
        region = self.canvas.crop((x0, y0, x1, y1))
        if region.mode != "RGBA":
            region = region.convert("RGBA")
        if overlay.mode != "RGBA":
            overlay = overlay.convert("RGBA")
        self.canvas.paste(Image.alpha_composite(region, overlay), (x0, y0))

    def _drawGraphGrid(self, graph, xTicks=6, yTicks=4, timelineTicks=True):
        x, y, w, h = graph
        # Opaque fill — ImageDraw alpha would punch holes through the panel.
        self.draw.rectangle((x - 60, y, x + w + 60, y + h), fill=self.graphBgColor)
        for i in range(xTicks + 1):
            gx = x + w * i / xTicks
            self.draw.line((gx, y, gx, y + h), fill=self.graphGridColor, width=3)
        for i in range(1, yTicks):
            gy = y + h * i / yTicks
            self.draw.line((x - 60, gy, x + w + 60, gy), fill=self.graphGridColor, width=3)
        if timelineTicks:
            for i in range(61):
                gx = x + w * i / 60
                tick = 45 if i % 10 == 0 else 25
                self.draw.line((gx, y + h + 20, gx, y + h + 20 + tick), fill=self.graphTickColor, width=3)

    def _timeLabels(self, count=7):
        labels = []
        base = datetime.now().replace(minute=0, second=0, microsecond=0)
        for i in range(count):
            minute = i * 10
            t = base.replace(hour=(base.hour + (minute // 60)) % 24, minute=minute % 60)
            if self.time_format == 12:
                labels.append(t.strftime("%I:%M %p"))
            else:
                labels.append(t.strftime("%H:%M"))
        return labels

    def _elapsedTimeLabels(self, duration, count=7):
        duration = max(0, int(duration or 0))
        labels = []
        for i in range(count):
            seconds = round(duration * i / max(count - 1, 1))
            if duration >= 3600:
                labels.append(self._durationHMS(seconds))
            else:
                labels.append(f"{seconds // 60:02d}:{seconds % 60:02d}")
        return labels

    def _drawTimeLabels(self, graph, y, labels=None):
        x, _, w, _ = graph
        font = self.getFont("bold", 44)
        labels = labels or self._timeLabels()
        for i, label in enumerate(labels):
            bbox = self.draw.textbbox((0, 0), label, font=font)
            self.draw.text((x + w * i / max(len(labels) - 1, 1) - (bbox[2] - bbox[0]) / 2, y), label, font=font, fill=self.bodyColor)

    def _drawAreaSeries(self, graph, data, color, maxY=None, minY=0, width=6, alpha=115, smooth=False):
        x, y, w, h = graph
        values = [float(v or 0) for v in (data or [0])]
        if len(values) == 1:
            values = values * 2
        if maxY is None:
            maxY = max(max(values), minY + 1)
        maxY = max(maxY, minY + 1)
        interval = w / max(len(values) - 1, 1)
        pts = []
        for i, val in enumerate(values):
            val = max(minY, min(maxY, val))
            pts.append((x + i * interval, y + h - ((val - minY) / (maxY - minY)) * h))
        poly = [(x, y + h)] + pts + [(x + w, y + h)]
        fill = (*color[:3], alpha) if len(color) >= 3 else color
        # Composite translucent fill so gridlines show through without leaving
        # partial-alpha holes in the exported PNG.
        pad = max(2, int(width) + 2)
        x0 = max(0, int(min(p[0] for p in poly)) - pad)
        y0 = max(0, int(min(p[1] for p in poly)) - pad)
        x1 = min(self.canvas.size[0], int(max(p[0] for p in poly)) + pad + 1)
        y1 = min(self.canvas.size[1], int(max(p[1] for p in poly)) + pad + 1)
        if x1 > x0 and y1 > y0:
            overlay = Image.new("RGBA", (x1 - x0, y1 - y0), (0, 0, 0, 0))
            ImageDraw.Draw(overlay).polygon(
                [(px - x0, py - y0) for px, py in poly], fill=fill
            )
            self._compositeRGBA(overlay, (x0, y0, x1, y1))
        if len(pts) > 1:
            line_color = color[:3]
            if smooth:
                self.draw.line(pts, fill=line_color, width=width, joint="curve")
            else:
                self.draw.line(pts, fill=line_color, width=width)

    def _drawYAxisLabels(self, graph, values, fontSize=40):
        x, y, _, h = graph
        font = self.getFont("bold", fontSize)
        for i, text in enumerate(values):
            bbox = self.draw.textbbox((0, 0), text, font=font)
            self.draw.text((x - 120 - (bbox[2] - bbox[0]), y + h * i / max(len(values) - 1, 1) - 28), text, font=font, fill=self.bodyColor)

    def _durationHMS(self, seconds):
        seconds = max(0, int(seconds or 0))
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        return f"{h:02d}:{m:02d}:{s:02d}"

    def _drawActivityCard(self, region, title, rows, honeyGraphData=None, honeyGraphLabels=None):
        self._drawPanel(region, title)
        x, y, w, h = region
        total = max(1, sum(max(0, r["seconds"]) for r in rows))
        angle = -90
        legendTop = y + (432 if title == "SESSION" else 348)
        pieSize = 280
        pieCenterY = legendTop + 110
        pieTop = pieCenterY - pieSize / 2
        pieLeft = x + 95
        pie = (pieLeft, pieTop, pieLeft + pieSize, pieTop + pieSize)
        for row in rows:
            extent = row["seconds"] / total * 360
            self.draw.pieslice(pie, angle, angle + extent, fill=row["color"])
            angle += extent
        font = self.getFont("bold", 48)
        for i, row in enumerate(rows):
            ly = legendTop + i * 88
            self.draw.rounded_rectangle((x + 650, ly, x + 694, ly + 44), radius=4, fill=row["color"])
            labelFont = self._fitText(row["label"], 200, "bold", 48, 34)
            bbox = self.draw.textbbox((0, 0), row["label"], font=labelFont)
            self.draw.text((x + 620 - (bbox[2] - bbox[0]), ly - 13), row["label"], font=labelFont, fill=self.bodyColor)
            self.draw.text((x + 735, ly - 13), self._durationHMS(row["seconds"]), font=font, fill=self.bodyColor)
            pct = f"{round(row['seconds'] / total * 100)}%"
            bbox = self.draw.textbbox((0, 0), pct, font=font)
            self.draw.text((x + w - 140 - (bbox[2] - bbox[0]), ly - 13), pct, font=font, fill=self.bodyColor)
        if honeyGraphData:
            graph = (x + 200, y + h - 560, w - 280, 480)
            self._drawGraphGrid(graph, xTicks=6, yTicks=4, timelineTicks=False)
            minY = min(honeyGraphData)
            maxY = max(max(honeyGraphData), minY + 1)
            span = maxY - minY
            labels = [self.millify(maxY - span * i / 4) for i in range(5)]
            self._drawYAxisLabels(graph, labels, 28)
            self._drawAreaSeries(graph, honeyGraphData, self.gatherColor, maxY=maxY, minY=minY, alpha=120)
            if honeyGraphLabels:
                small = self.getFont("bold", 30)
                for i, label in enumerate(honeyGraphLabels):
                    bbox = self.draw.textbbox((0, 0), label, font=small)
                    self.draw.text((graph[0] + graph[2] * i / max(len(honeyGraphLabels) - 1, 1) - (bbox[2] - bbox[0]) / 2, graph[1] + graph[3] + 14), label, font=small, fill=self.bodyColor)

    def _currentBuffValue(self, values, key):
        data = values.get(key, []) if isinstance(values, dict) else []
        for val in reversed(data):
            if val:
                return val
        return 0

    def _drawLegacyBuffsCard(self, region, buffQuantity, hourlyBuffList, nectarQuantity, uptimeBuffsValues):
        self._drawPanel(region, "BUFFS")
        x, y, w, _ = region
        iconKeys = normalizeHourlyBuffSelection(hourlyBuffList)
        iconCount = max(1, min(MAX_HOURLY_BUFF_OPTIONS, len(iconKeys)))
        iconSize = 220
        for i, key in enumerate(iconKeys):
            iconX = x + 48 + i * ((w - 96 - iconSize) / max(iconCount - 1, 1))
            iconY = y + 124
            asset = HOURLY_BUFF_ASSETS.get(key, key + "_buff")
            try:
                img = Image.open(f"{self.assetPath}/{asset}.png").convert("RGBA").resize((iconSize, iconSize))
                self.canvas.paste(img, (int(iconX), iconY), img)
            except FileNotFoundError:
                pass
            value = self._currentBuffValue(uptimeBuffsValues, key)
            if not value and key in hourlyBuffList:
                idx = hourlyBuffList.index(key)
                value = buffQuantity[idx] if idx < len(buffQuantity) else 0
            txt = f"x{value}" if value else "x0"
            font = self.getFont("bold", 72)
            bbox = self.draw.textbbox((0, 0), txt, font=font, stroke_width=5)
            self.draw.text((iconX + iconSize - 10 - (bbox[2] - bbox[0]), iconY + int(iconSize * 0.6)), txt, font=font, fill=self.bodyColor, stroke_width=5, stroke_fill=(0, 0, 0))

        nectarNames = ["comforting", "motivating", "satisfying", "refreshing", "invigorating"]
        nectarOrder = [0, 2, 4, 3, 1]
        nectarColors = [(126, 158, 179), (147, 125, 179), (179, 152, 167), (120, 179, 117), (179, 89, 81)]
        for i, name in enumerate(nectarNames):
            dataIndex = nectarOrder[i]
            value = int(nectarQuantity[dataIndex] if dataIndex < len(nectarQuantity) and nectarQuantity[dataIndex] else 0)
            cx = int(x + 150 + i * ((w - 100 - 200) / 4))
            cy = y + 510
            color = nectarColors[i]
            self.draw.arc((cx - 100, cy - 100, cx + 100, cy + 100), -90, -90 + value / 100 * 360, fill=color, width=32)
            self.draw.arc((cx - 100, cy - 100, cx + 100, cy + 100), -90 + value / 100 * 360, 270, fill=tuple(int(c * .3) for c in color), width=32)
            font = self.getFont("bold", 54)
            pct = f"{value}%"
            bbox = self.draw.textbbox((0, 0), pct, font=font)
            self.draw.text((cx - (bbox[2] - bbox[0]) / 2, cy - 28), pct, font=font, fill=color)
            label = name[:3].upper()
            labelFont = self.getFont("bold", 48)
            bbox = self.draw.textbbox((0, 0), label, font=labelFont)
            self.draw.text((cx - (bbox[2] - bbox[0]) / 2, y + 630), label, font=labelFont, fill=color)

    def _drawLegacyPlantersCard(self, region, planterData):
        self._drawPanel(region, "PLANTERS")
        x, y, w, _ = region
        names = []
        fields = []
        times = []
        if planterData:
            for i, name in enumerate(planterData.get("planters", [])[:3]):
                if name:
                    names.append(name)
                    fields.append(planterData.get("fields", [""] * 3)[i])
                    times.append(planterData.get("harvestTimes", [0] * 3)[i] - time.time())
        if not names:
            names, fields, times = ["unknown", "unknown", "unknown"], ["None", "None", "None"], [0, 0, 0]
        slot = w / 3
        for i, name in enumerate(names[:3]):
            cx = x + slot * i + slot / 2
            asset = name.replace(" ", "_") + "_planter"
            try:
                img = Image.open(f"{self.assetPath}/{asset}.png").convert("RGBA").resize((220, 220))
                self.canvas.paste(img, (int(cx - 110), y + 110), img)
            except FileNotFoundError:
                pass
            field = str(fields[i]).title()
            font = self._fitText(field, slot - 60, "bold", 52, 34)
            bbox = self.draw.textbbox((0, 0), field, font=font)
            self.draw.text((cx - (bbox[2] - bbox[0]) / 2, y + 340), field, font=font, fill=self.bodyColor)
            duration = "Ready" if times[i] <= 0 else self.displayTime(times[i], ["h", "m"])
            font = self._fitText(duration, slot - 60, "bold", 46, 32)
            bbox = self.draw.textbbox((0, 0), duration, font=font)
            self.draw.text((cx - (bbox[2] - bbox[0]) / 2, y + 406), duration, font=font, fill=(230, 230, 230))

    def _drawLegacyStatsCard(self, region, statsRows):
        self._drawPanel(region, "STATS")
        x, y, w, _ = region
        rows = [
            ("Total Boss Kills", statsRows.get("bosses", 0)),
            ("Total Vic Kills", statsRows.get("vicious_bees", 0)),
            ("Total Bug Kills", statsRows.get("bugs", 0)),
            ("Total Planters", statsRows.get("planters", 0)),
            ("Quests Done", statsRows.get("quests_completed", 0)),
            ("Disconnects", statsRows.get("disconnects", 0)),
        ]
        rowFont = self.getFont("bold", 60)
        y2 = y + 122
        for label, value in rows:
            self.draw.text((x + 170, y2), label, font=rowFont, fill=self.bodyColor)
            self.draw.text((x + w // 2 + 130, y2), str(int(value or 0)), font=rowFont, fill=self.bodyColor)
            self.draw.rounded_rectangle((x + w // 2 + 470, y2 + 36, x + w // 2 + 520, y2 + 48), radius=6, fill=(102, 102, 102))
            y2 += 78

    def _drawLegacyInfoCard(self, region, reportTitle, sessionTime):
        self._drawPanel(region)
        x, y, w, _ = region
        cx = x + w / 2
        try:
            versionText = f"v{getMacroVersion()}"
        except Exception:
            versionText = "version"
        try:
            profileText = getCurrentProfile()
        except Exception:
            profileText = "unknown"
        lines = [
            (reportTitle, (255, 218, 61), 56),
            (f"Fuzzy Macro - {versionText}", (255, 255, 255), 56),
            (f"Runtime: {self._durationHMS(sessionTime)}", (79, 223, 38), 56),
            (f"Profile: {profileText}", self.accentColor, 56),
            ("Made by Logan :)", (4, 180, 228), 56),
        ]
        yy = y + 34
        for text, color, size in lines:
            font = self._fitText(text, w - 140, "bold", size, 34)
            bbox = self.draw.textbbox((0, 0), text, font=font)
            self.draw.text((cx - (bbox[2] - bbox[0]) / 2, yy), text, font=font, fill=color)
            yy += 74

    def _drawUptimeRows(self, region, uptimeBuffList, uptimeBuffsValues, buffGatherIntervals, reportKind, timeLabels=None):
        self._drawPanel(region, "BUFF UPTIME")
        x, y, w, h = region
        graphX = x + 320
        graphW = 3600
        top = y + 135
        bottomSpace = 130
        rowH = max(95, (h - 235 - bottomSpace) / max(len(uptimeBuffList), 1))
        for idx, key in enumerate(uptimeBuffList):
            cfg = BUFF_RENDER_CONFIG[key]
            chartType, maxY, colorInfo, asset = cfg
            gy = int(top + idx * rowH)
            gh = int(rowH - 8)
            graph = (graphX, gy, graphW, gh)
            self._drawGraphGrid(graph, xTicks=6, yTicks=2, timelineTicks=False)
            try:
                img = Image.open(f"{self.assetPath}/{asset}.png").convert("RGBA").resize((110, 110))
                self.canvas.paste(img, (x + 75, gy + max(0, (gh - 110) // 2)), img)
            except FileNotFoundError:
                pass
            labelFont = self.getFont("bold", 36 if len(uptimeBuffList) > 12 else 44)
            if chartType == "multi":
                colors = colorInfo
                for dataKey, rgb in colors:
                    data = uptimeBuffsValues.get(dataKey, [0] * 600)
                    self._drawAreaSeries(graph, data, rgb, maxY=maxY, width=4, alpha=80)
            else:
                rgb = colorInfo
                data = uptimeBuffsValues.get(key, [0] * 600)
                self._drawAreaSeries(graph, data, rgb, maxY=maxY, width=4, alpha=115)
            label = f"x0-{maxY}" if chartType != "binary" else "x0-1"
            self.draw.text((x + 74, gy + gh - 38), label, font=labelFont, fill=self.bodyColor)
        self._drawTimeLabels((graphX, top, graphW, h - 260), y + h - 85, timeLabels)

    def _drawStatMonitorReport(self, reportTitle, hourlyReportStats, sessionTime, honeyPerSec, sessionHoney,
                               honeyThisHour, onlyValidHourlyHoney, buffQuantity, nectarQuantity, planterData,
                               uptimeBuffsValues, buffGatherIntervals, configuredUptimeBuffs=None,
                               configuredHourlyBuffs=None, sessionStats=None, itemMonitorData=None):
        self.canvasW = 6000
        self.canvasMaxH = 5800
        self.canvasSize = (6000, 5800)
        self.canvas = Image.new("RGBA", self.canvasSize, (*self.baseBackgroundColor, 255))
        self.draw = ImageDraw.Draw(self.canvas)

        regions = {
            "honey/sec": (120, 120, 4080, 1080),
            "stats": (4320, 120, 1560, 5560),
            "backpack": (120, 1320, 4080, 1140),
            "buffs": (120, 2580, 4080, 3100),
        }
        statRegions = {
            "lasthour": (4420, 220, 1360, 1206),
            "session": (4420, 1626, 1360, 1289),
            "buffs": (4420, 3015, 1360, 720),
            "planters": (4420, 3835, 1360, 495),
            "stats": (4420, 4440, 1360, 620),
            "info": (4420, 5160, 1360, 420),
        }
        for key, region in regions.items():
            self._drawPanel(region, None)
        for key, region in statRegions.items():
            self._drawPanel(region, None)
        timeLabels = self._elapsedTimeLabels(sessionTime) if reportTitle == "Session Report" else self._timeLabels()

        self._drawPanel(regions["honey/sec"], "HONEY/SEC")
        honeyGraph = (440, 250, 3600, 800)
        self._drawGraphGrid(honeyGraph, xTicks=6, yTicks=4)
        honeyData = honeyPerSec or [0]
        maxHoney = max(max(honeyData), 1)
        self._drawYAxisLabels(honeyGraph, [self.millify(maxHoney - maxHoney * i / 4) for i in range(5)], 40)
        self._drawAreaSeries(honeyGraph, honeyData, (254, 202, 64), maxY=maxHoney, alpha=125)
        self._drawTimeLabels(honeyGraph, regions["honey/sec"][1] + regions["honey/sec"][3] - 85, timeLabels)

        self._drawPanel(regions["backpack"], "BACKPACK")
        backpackGraph = (440, 1450, 3600, 860)
        self._drawGraphGrid(backpackGraph, xTicks=6, yTicks=2)
        self._drawYAxisLabels(backpackGraph, ["100%", "50%", "0%"], 40)
        self._drawAreaSeries(backpackGraph, hourlyReportStats.get("backpack_per_min", [0]), (65, 255, 128), maxY=100, alpha=130)
        self._drawTimeLabels(backpackGraph, regions["backpack"][1] + regions["backpack"][3] - 85, timeLabels)

        uptimeList = self.normalizeUptimeBuffList(configuredUptimeBuffs)
        self._drawUptimeRows(regions["buffs"], uptimeList, uptimeBuffsValues, buffGatherIntervals, reportTitle, timeLabels)

        totalBreakdown = max(1, sessionTime)
        hourRows = [
            {"label": "Gather", "seconds": hourlyReportStats.get("gathering_time", 0), "color": self.gatherColor},
            {"label": "Convert", "seconds": hourlyReportStats.get("converting_time", 0), "color": self.convertColor},
            {"label": "Other", "seconds": hourlyReportStats.get("bug_run_time", 0) + hourlyReportStats.get("misc_time", 0), "color": self.otherColor},
        ]
        sessionSource = sessionStats or {}
        sessionRows = [
            {"label": "Gather", "seconds": sessionSource.get("gathering_time", hourlyReportStats.get("gathering_time", 0)), "color": self.gatherColor},
            {"label": "Convert", "seconds": sessionSource.get("converting_time", hourlyReportStats.get("converting_time", 0)), "color": self.convertColor},
            {"label": "Other", "seconds": sessionSource.get("bug_run_time", hourlyReportStats.get("bug_run_time", 0)) + sessionSource.get("misc_time", hourlyReportStats.get("misc_time", 0)), "color": self.otherColor},
        ]

        self._drawActivityCard(statRegions["lasthour"], "LAST HOUR", hourRows, honeyData, timeLabels)
        x, y, w, _ = statRegions["lasthour"]
        topFont = self.getFont("bold", 60)
        self.draw.text((x + 200, y + 96), "Honey Earned", font=topFont, fill=self.bodyColor)
        self.draw.text((x + 720, y + 96), self.millify(honeyThisHour), font=topFont, fill=self.bodyColor)
        self.draw.polygon([(x + 980, y + 119), (x + 955, y + 161), (x + 1005, y + 161)], fill=(0, 255, 0))
        avg = max(0, sessionHoney / (totalBreakdown / 3600)) if totalBreakdown else 0
        self.draw.text((x + 170, y + 180), "Hourly Average", font=topFont, fill=self.bodyColor)
        self.draw.text((x + 720, y + 180), self.millify(avg), font=topFont, fill=self.bodyColor)

        self._drawActivityCard(statRegions["session"], "SESSION", sessionRows, onlyValidHourlyHoney or [0], timeLabels)
        x, y, w, _ = statRegions["session"]
        currentHoney = onlyValidHourlyHoney[-1] if onlyValidHourlyHoney else 0
        sessionLines = [
            ("Starting Honey", self.millify(hourlyReportStats.get("start_honey", 0))),
            ("Current Honey", self.millify(currentHoney)),
            ("Session Honey", self.millify(sessionHoney)),
            ("Session Time", self._durationHMS(sessionTime)),
        ]
        for i, (label, value) in enumerate(sessionLines):
            yy = y + 96 + i * 84
            self.draw.text((x + 210, yy), label, font=topFont, fill=self.bodyColor)
            self.draw.text((x + 720, yy), value, font=topFont, fill=self.bodyColor)

        hourlyBuffList = configuredHourlyBuffs if configuredHourlyBuffs is not None else DEFAULT_HOURLY_BUFFS
        self._drawLegacyBuffsCard(statRegions["buffs"], buffQuantity, hourlyBuffList, nectarQuantity, uptimeBuffsValues)
        self._drawLegacyPlantersCard(statRegions["planters"], planterData)
        statsRows = {
            "bugs": sessionSource.get("total_bugs", sessionSource.get("bugs", hourlyReportStats.get("bugs", 0))),
            "vicious_bees": sessionSource.get("total_vicious_bees", sessionSource.get("vicious_bees", hourlyReportStats.get("vicious_bees", 0))),
            "quests_completed": sessionSource.get("total_quests", sessionSource.get("quests_completed", hourlyReportStats.get("quests_completed", 0))),
            "planters": len([p for p in planterData.get("planters", []) if p]) if planterData else 0,
        }
        self._drawLegacyStatsCard(statRegions["stats"], statsRows)
        self._drawLegacyInfoCard(statRegions["info"], reportTitle, sessionTime)
        return self.canvas


    def millify(self, n):
        if not n: return "0"
        millnames = ['',' K',' M',' B',' T', 'Qd']
        n = float(n)
        millidx = max(0,min(len(millnames)-1,
                            int(math.floor(0 if n == 0 else math.log10(abs(n))/3))))

        return '{:.2f} {}'.format(n / 10**(3 * millidx), millnames[millidx])

    def displayTime(self, seconds, units = ['w','d','h','m','s']):
        intervals = (
            ('w', 604800),  # 60 * 60 * 24 * 7
            ('d', 86400),    # 60 * 60 * 24
            ('h', 3600),    # 60 * 60
            ('m', 60),
            ('s', 1),
        )
        result = []

        for name, count in intervals:
            value = seconds // count
            if value:
                seconds -= value * count
                if value == 1:
                    name = name.rstrip('s')
                if name in units:
                    value = int(value)
                    if value < 10:
                        value = "0"+str(value)
                    result.append("{}{}".format(value, name))
        if not result:
            return "0s"
        return ' '.join(result)
        
    def getFont(self, weight, fontSize):
        return ImageFont.truetype(f"hourly_report/Inter/static/Inter_18pt-{weight.title()}.ttf", fontSize)

    def getGradientColorAtRatio(self, ratio, gradientSpec):
        #calculates the RGBA color from gradientSpec at a given vertical ratio (0=bottom, 1=top)
        if not gradientSpec:
            return (0, 0, 0, 0) # Default transparent black if no spec

        sorted_stops = sorted(gradientSpec.items()) # list of (position_ratio, color_tuple)

        # Clamp ratio
        ratio = max(0.0, min(1.0, ratio))

        # Find which two stops this ratio is between
        for j in range(len(sorted_stops) - 1):
            pos1, col1 = sorted_stops[j]
            pos2, col2 = sorted_stops[j + 1]
            if pos1 <= ratio <= pos2:
                if pos2 - pos1 == 0:
                    local_ratio = 0
                else:
                    local_ratio = (ratio - pos1) / (pos2 - pos1)

                #interpolate RGBA values
                try:
                    r = int(col1[0] + (col2[0] - col1[0]) * local_ratio)
                    g = int(col1[1] + (col2[1] - col1[1]) * local_ratio)
                    b = int(col1[2] + (col2[2] - col1[2]) * local_ratio)
                    #handle alpha
                    a = 255 
                    if len(col1) > 3 and len(col2) > 3:
                            a = int(col1[3] + (col2[3] - col1[3]) * local_ratio)
                    elif len(col1) > 3:
                        a = col1[3]
                    elif len(col2) > 3:
                        a = col2[3]

                    return (r, g, b, a)
                except IndexError:
                    print(f"Warning: Color tuple length mismatch in gradientSpec between {col1} and {col2}")
                    return (0,0,0,255)

        # If ratio is below the first stop or above the last stop (should not happen with clamping)
        if ratio < sorted_stops[0][0]:
            return sorted_stops[0][1] # Return first color
        else:
            return sorted_stops[-1][1] # Return last color


    def drawGraph(self, graphX, graphY, width, height, xData, datasets, maxY = None, showXAxisLabels=True, showYAxisLabels=True, ticks=5, yLabelFunc=None, xLabelFunc=None):
        # Validate data lengths
        for dataset in datasets:
            data = dataset["data"]
            #pad the data
            data = [0]*(len(xData) - len(data)) + data
        
            # Prevent division by zero with minimal data
            xInterval = width / max(len(data) - 1, 1)
            if not maxY:
                maxY = max(data) if data else 1
                if not maxY:
                    maxY = 1
            else:
                data = [maxY if y > maxY else y for y in data]

            font = self.getFont("semibold", 60)
            fontColor = self.subtleColor
            gridColor = self.gridColor
            #draw xaxis
            if showXAxisLabels:
                for i, val in enumerate(xData):
                    val = xLabelFunc(i, val) if xLabelFunc else val
                    if val:
                        val = str(val)
                        #get the text width, so the text can be centered with the x axis point
                        bbox = self.draw.textbbox((0, 0), val, font=font)
                        textWidth = bbox[2] - bbox[0]
                        self.draw.text((graphX+xInterval*i - textWidth/2, graphY+20), val, font=font, fill= fontColor)
            
            #draw y labels and y grid
            #calculating ticks
            yInterval = height/max(ticks-1, 1)
            yValInterval = maxY/max(ticks-1, 1)

            for i in range(ticks):
                y = graphY - yInterval*i
                if showYAxisLabels:
                    text = yValInterval*i
                    text = yLabelFunc(i, text) if yLabelFunc else text
                    if text:
                        text = str(text)
                        bbox = self.draw.textbbox((0, 0), text, font=font)
                        textWidth = bbox[2] - bbox[0]
                        textHeight = bbox[3] - bbox[1]
                        self.draw.text((graphX - textWidth - 100, y - textHeight/2), text, font=font, fill= fontColor)
                self.draw.line((graphX-30, y, graphX+30+width, y), fill=gridColor, width=3)


            # Collect curve points
            points = []
            for i, val in enumerate(data):
                px = graphX + i * xInterval
                py = graphY - (val / maxY * height)
                points.append((px, py))
            # Close polygon at bottom
            points.append((graphX + (len(xData) - 1) * xInterval, graphY))
            points.append((graphX, graphY))

            #make gradient
            gradientSpec = dataset.get("gradientFill", None)
            if gradientSpec:
                gradient = Image.new('RGBA', (int(width), int(height)), (0, 0, 0, 0))
                grad_draw = ImageDraw.Draw(gradient)
                sorted_stops = sorted(gradientSpec.items())  # list of (position, color)
                stop_positions = [int(pos * height) for pos, _ in sorted_stops]

                for i in range(height):
                    # Normalize position (0 to 1)
                    ratio = i / float(max(height - 1, 1))

                    # Find which two stops this ratio is between
                    for j in range(len(sorted_stops) - 1):
                        pos1, col1 = sorted_stops[j]
                        pos2, col2 = sorted_stops[j + 1]
                        if pos1 <= ratio <= pos2:
                            local_ratio = (ratio - pos1) / (pos2 - pos1)
                            r = int(col1[0] + (col2[0] - col1[0]) * local_ratio)
                            g = int(col1[1] + (col2[1] - col1[1]) * local_ratio)
                            b = int(col1[2] + (col2[2] - col1[2]) * local_ratio)
                            a = int(col1[3] + (col2[3] - col1[3]) * local_ratio)
                            grad_draw.line([(0, height - i), (width, height - i)], fill=(r, g, b, a))
                            break
                

            #composite gradient on dark background
            bg = Image.new('RGBA', (int(width), int(height)), (*self.backgroundColor, 255))
            gradient = Image.alpha_composite(bg, gradient)

            #create a mask with polygon in the shape of the graph
            mask = Image.new('L', (int(width), int(height)), 0)
            mask_draw = ImageDraw.Draw(mask)
            rel_pts = [(px - graphX, py - (graphY - height)) for px, py in points]
            mask_draw.polygon(rel_pts, fill=255)

            #paste the gradient and mask onto the canvas
            self.canvas.paste(gradient, (graphX, graphY - height), mask)

            lineColor = dataset["lineColor"]
            #gradient color.
            if gradientSpec and lineColor == "gradient":
                #draw the line
                for i in range(len(points) - 3):
                    #Since line doesnt accept gradients, we will break the line down into segments, 
                    #and assign each segment a color
                    x0, y0 = points[i]
                    x1, y1 = points[i+1]

                    #calculate length of the line
                    dx = x1 - x0
                    dy = y1 - y0
                    length = math.sqrt(dx*dx + dy*dy)

                    if length == 0: continue # Skip zero-length segments

                    #get the number of segments
                    segmentCount = max(1, int(length / 10))

                    for k in range(segmentCount):
                        t0 = k / segmentCount
                        t1 = (k + 1) / segmentCount

                        sub_x0 = x0 + dx * t0
                        sub_y0 = y0 + dy * t0
                        sub_x1 = x0 + dx * t1
                        sub_y1 = y0 + dy * t1
                        mid_y = (sub_y0 + sub_y1) / 2.0
                        # Convert Y coord to ratio (0=bottom, 1=top)
                        mid_yRatio = (graphY - mid_y) / height if height > 0 else 0.0

                        # Get color for this ratio
                        r, g, b, a = self.getGradientColorAtRatio(mid_yRatio, gradientSpec)

                        self.draw.line(
                            (int(sub_x0), int(sub_y0), int(sub_x1), int(sub_y1)),
                            fill=(r, g, b), # Use opaque RGB for line
                            width=7
                        )

            else:
                # Draw the entire line with a solid color
                # Use points[:len(data)] to only draw line over actual data points, not polygon closing points
                self.draw.line(points[:len(data)], fill=lineColor, width=7)

    def drawDoughnutChart(self, x, y, size, datasets, holeRatio = 0.6):

        total = sum([x["data"] for x in datasets])
        if not total:
            total = 1
        angleStart = -90
        chartArea = (x, y, x+size, y+size)

        #draw the section
        for dataset in datasets:
            angleEnd = angleStart + (dataset["data"] / total) * 360
            self.draw.pieslice(chartArea, angleStart, angleEnd, fill=dataset["color"])
            angleStart = angleEnd

        #draw the hole
        if holeRatio > 0:
            hole_size = int(size * holeRatio)
            offset = (size - hole_size) // 2
            hole_bbox = (x+offset, y+offset, x+offset + hole_size, y+offset + hole_size)
            self.draw.ellipse(hole_bbox, fill=self.sideBarBackground)

    def drawProgressChart(self, x, y, size, percentage, color, holeRatio = 0.6,):
        chartArea = (x, y, x+size, y+size)

        # Track background: blend color onto the card so the PNG stays opaque.
        track_alpha = 140 / 255.0
        track = tuple(
            int(round(c * track_alpha + b * (1.0 - track_alpha)))
            for c, b in zip(color[:3], self.sideBarBackground)
        )
        self.draw.pieslice(chartArea, -90, 360, fill=track)
        self.draw.pieslice(chartArea, -90, (int(percentage) / 100) * 360 - 90, fill=color)

        #draw the hole
        if holeRatio > 0:
            hole_size = int(size * holeRatio)
            offset = (size - hole_size) // 2
            hole_bbox = (x+offset, y+offset, x+offset + hole_size, y+offset + hole_size)
            self.draw.ellipse(hole_bbox, fill=self.sideBarBackground)

        font = self.getFont("semibold", 65)
        text = f"{int(percentage)}%"
        text_bbox = self.draw.textbbox((0, 0), text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        self.draw.text((x + (size - text_width) // 2, y + (size - text_height) // 2 - 10), text, fill=self.bodyColor, font=font)

    def drawStatCard(self, x, y, statImage, statValue, statTitle, fontColor = None, imageColor = None, cardWidth = 700, cardHeight = 750):
        leftPadding = x+100
        self.draw.rounded_rectangle((x, y, x+cardWidth, y+cardHeight), fill=self.cardBackground, radius=55)
        #load the image
        img = Image.open(f"{self.assetPath}/{statImage}.png").convert("RGBA")
        width, height = img.size
        imageHeight = 190
        imageWidth = int(width*(imageHeight/height))
        img = img.resize((imageWidth, imageHeight))

        #recolor the image
        if imageColor:
            r,g,b = imageColor
            pixels = img.load()
            for i in range(img.width):
                for j in range(img.height):
                    _, _, _, a = pixels[i, j]
                    if a > 0:  #only recolor non-transparent pixels
                        pixels[i, j] = (r,g,b, a)

        self.canvas.paste(img, (leftPadding, y + 95), img)

        self.draw.text((leftPadding, y+370), str(statValue), font=self.getFont("semibold", 80), fill=fontColor if fontColor else self.bodyColor)
        self.draw.text((leftPadding, y+545), statTitle, font=self.getFont("medium", 52), fill=self.subtleColor)

    def drawSessionStat(self, y, imageName, label, value, valueColor):
        imgContainerDimension = 180
        self.draw.rounded_rectangle((self.sidebarX, y, self.sidebarX+imgContainerDimension, y+imgContainerDimension), radius=50, fill=self.cardBackground)
        img = Image.open(f"{self.assetPath}/{imageName}.png").convert("RGBA")
        width, height = img.size
        imageWidth = 120
        imageHeight = int(height*(imageWidth/width))
        img = img.resize((imageWidth, imageHeight))
        #center the image in the container
        self.canvas.paste(img, (self.sidebarX + (imgContainerDimension-imageWidth)//2 , y + (imgContainerDimension-imageHeight)//2), img)

        #draw label and value
        #make sure they are vertically centered with the image container
        font = self.getFont("semibold", 68)
        ascent, _ = font.getmetrics()
        textY = y + (imgContainerDimension - ascent)//2
        self.draw.text((self.sidebarX+imgContainerDimension+50, textY), label, self.bodyColor, font=font)
        #value is right-aligned
        bbox = self.draw.textbbox((0, 0), value, font=font)
        textWidth = bbox[2] - bbox[0]
        self.draw.text((self.canvasSize[0]-self.sidebarPadding-textWidth, textY), str(value), valueColor, font=font)

    def drawTaskTimes(self, y, datasets, totalTime=None):
        legendIconDimension = 80
        font = self.getFont("medium", 68)
        x = self.sidebarX
        totalData = totalTime if totalTime is not None else sum([x["data"] for x in datasets])
        if not totalData:
            totalData = 1

        for dataset in datasets:
            self.draw.rounded_rectangle((x, y, x+legendIconDimension, y+legendIconDimension), fill=dataset["color"], radius=10)
            bbox = self.draw.textbbox((0, 0), dataset["label"], font=font)
            textHeight = bbox[3] - bbox[1]
            textY = y #+ (legendIconDimension - textHeight) // 2 -25
            self.draw.text((x+legendIconDimension + 50, textY), f"{dataset['label']}:", self.bodyColor, font=font)
            self.draw.text((x+legendIconDimension + 600, textY), self.displayTime(dataset["data"]), self.bodyColor, font=font)
            self.draw.text((x+legendIconDimension + 1000, textY), f"{round(dataset['data']/totalData*100, 1)}%", (220,220,220), font=font)
            y+= 150

        y += 100
        doughnutChartSize = 600
        self.drawDoughnutChart(self.sidebarX + 450, y, doughnutChartSize, datasets, holeRatio=0.4)

    def drawPlanters(self, y, planterNames, planterTimes, planterFields):
        fieldNectarIcons = {
            "sunflower": "satisfying",
            "dandelion": "comforting",
            "mushroom": "motivating",
            "blue flower": "refreshing",
            "clover": "invigorating",
            "strawberry": "refreshing",
            "spider": "motivating",
            "bamboo": "comforting",
            "pineapple": "satisfying",
            "stump": "motivating",
            "cactus": "invigorating",
            "pumpkin": "satisfying",
            "pine tree": "comforting",
            "rose": "motivating",
            "mountain top": "invigorating",
            "pepper": "invigorating",
            "coconut": "refreshing"
        }

        planterX = self.sidebarX
        fieldFont = self.getFont("semibold", 68)
        timeFont = self.getFont("semibold", 55)
        for i in range(len(planterNames)):
            if not planterNames[i]:
                continue
            bbox = self.draw.textbbox((0, 0), planterFields[i].title(), font=fieldFont)
            fieldTextWidth = bbox[2] - bbox[0]

            nectarImg = Image.open(f'{self.assetPath}/{fieldNectarIcons[planterFields[i]]}.png')
            width, height = nectarImg.size
            nectarImageHeight = bbox[3] - bbox[1]
            nectarImageWidth = int(width*(nectarImageHeight/height))
            nectarImg = nectarImg.resize((nectarImageWidth, nectarImageHeight))

            fieldAndNectarWidth = fieldTextWidth + nectarImageWidth + 30

            img = Image.open(f'{self.assetPath}/{planterNames[i].replace(" ","_")}_planter.png')
            width, height = img.size
            imageHeight = 250
            imageWidth = int(width*(imageHeight/height))
            img = img.resize((imageWidth, imageHeight))

            timeText = self.displayTime(planterTimes[i], ["h", "m"]) if planterTimes[i] > 0 else "Ready!"
            bbox = self.draw.textbbox((0, 0), timeText, font=timeFont)
            timeTextWidth = bbox[2] - bbox[0]

            maxWidth = max(fieldAndNectarWidth, imageWidth, timeTextWidth)
            self.canvas.paste(img, (planterX + (maxWidth-imageWidth)//2, y), img)
            self.draw.text((planterX + (maxWidth - fieldAndNectarWidth)//2, y+300), planterFields[i].title(), font=fieldFont, fill= self.bodyColor) 
            self.canvas.paste(nectarImg, (planterX + (maxWidth - fieldAndNectarWidth)//2 + fieldTextWidth + 30, y+315), nectarImg)
            self.draw.text((planterX + (maxWidth - timeTextWidth)//2, y+400), timeText, font=timeFont, fill= tuple([205]*3)) 

            planterX += maxWidth + 200

    def drawBuffs(self, y, buffData, hourlyBuffKeys=None, perRow=4):
        if hourlyBuffKeys is None:
            hourlyBuffKeys = DEFAULT_HOURLY_BUFFS

        font = self.getFont("bold", 60)
        availWidth = self.canvasSize[0] - self.sidebarPadding - self.sidebarX
        colWidth = availWidth // perRow
        imageWidth = min(230, colWidth - 30)
        rowHeight = 300
        for i, buffKey in enumerate(hourlyBuffKeys):
            buff = str(buffData[i]) if i < len(buffData) else "0"
            col = i % perRow
            row = i // perRow
            x = self.sidebarX + colWidth * col
            yy = y + row * rowHeight
            assetName = HOURLY_BUFF_ASSETS.get(buffKey, buffKey + "_buff")
            try:
                img = Image.open(f"{self.assetPath}/{assetName}.png").convert("RGBA")
            except FileNotFoundError:
                continue
            width, height = img.size
            imageHeight = int(height * (imageWidth / width))
            img = img.resize((imageWidth, imageHeight))

            overlay = Image.new("RGBA", img.size, (0, 0, 0, 100 if buff == "0" else 20))
            img = Image.alpha_composite(img, overlay)
            self.canvas.paste(img, (x, yy), img)

            if buff != "0":
                buffText = f"x{buff}"
                bbox = self.draw.textbbox((0, 0), buffText, font=font, stroke_width=4)
                textWidth = bbox[2] - bbox[0]
                self.draw.text((x + imageWidth - textWidth - 5, yy + imageHeight - 60 - 15), buffText, fill=self.bodyColor, font=font, stroke_width=4, stroke_fill=(0, 0, 0))

    def drawNectars(self, y, nectarData):
        nectarColors = [(165, 207, 234), (235, 120, 108), (194, 166, 236), (162, 239, 163), (239, 205, 224)]
        nectarNames = ["comforting", "motivating", "satisfying", "refreshing", "invigorating"]
        nectarOrder = [0, 2, 4, 3, 1]
        visibleNectars = [(i, dataIndex) for i, dataIndex in enumerate(nectarOrder) if dataIndex < len(nectarData)]
        count = max(len(visibleNectars), 1)
        availWidth = self.canvasSize[0] - self.sidebarPadding - self.sidebarX
        slot = availWidth // count
        progressChartSize = min(300, slot - 20)
        imageHeight = int(progressChartSize * 0.4)
        for slotIndex, (i, dataIndex) in enumerate(visibleNectars):
            x = self.sidebarX + slotIndex * slot + (slot - progressChartSize) // 2
            self.drawProgressChart(x, y, progressChartSize, nectarData[dataIndex], nectarColors[i], 0.75)

            img = Image.open(f"{self.assetPath}/{nectarNames[i]}.png").convert("RGBA")
            width, height = img.size
            imageWidth = int(width*(imageHeight/height))
            img = img.resize((imageWidth, imageHeight))
            self.canvas.paste(img, (x + (progressChartSize-imageWidth)//2, y+progressChartSize + 60), img)

    def _drawHeaderBanner(self, title, subtitle):
        """Full-width header banner with accent stripe, title (left) and macro identity (right). Returns bottom y."""
        x0, y0 = self.leftPadding, 80
        x1 = self.canvasW - self.leftPadding
        bannerH = 360
        y1 = y0 + bannerH
        self.draw.rounded_rectangle((x0, y0, x1, y1), radius=55, fill=self.cardBackground)
        # title + subtitle
        self.draw.text((x0+90, y0+75), title, fill=self.bodyColor, font=self.getFont("bold", 120))
        self.draw.text((x0+95, y0+235), subtitle, fill=self.subtleColor, font=self.getFont("medium", 58))

        # macro identity on the right
        try:
            icon = Image.open(f"{self.assetPath}/macro_icon.png").convert("RGBA").resize((190, 190))
            iconX = x1 - 230
            iconY = y0 + (bannerH - 190) // 2
            self.canvas.paste(icon, (iconX, iconY), icon)
            textRight = iconX - 45
        except FileNotFoundError:
            textRight = x1 - 60

        try:
            profile_name = getCurrentProfile()
        except Exception:
            profile_name = None
        try:
            version_text = f"v{getMacroVersion()}"
        except Exception:
            version_text = None

        lines = [("Fuzzy Macro", self.getFont("semibold", 68), self.bodyColor)]
        if profile_name:
            lines.append((f"Profile: {profile_name}", self.getFont("medium", 50), self.subtleColor))
        if version_text:
            lines.append((version_text, self.getFont("medium", 40), self.subtleColor))

        total_h = sum((f.getmetrics()[0] + 14) for _, f, _ in lines) - 14
        ty = y0 + (bannerH - total_h) // 2
        for text, f, col in lines:
            bbox = self.draw.textbbox((0, 0), text, font=f)
            tw = bbox[2] - bbox[0]
            self.draw.text((textRight - tw, ty), text, font=f, fill=col)
            ty += f.getmetrics()[0] + 14

        return y1

    def _drawBuffRow(self, x, y, colW, rowH, buff_key, uptimeBuffsValues, getAverageBuff, xLabelFunc=None):
        """Draw a single buff uptime cell: icon + name on the left, mini graph filling the rest."""
        cfg = BUFF_RENDER_CONFIG.get(buff_key)
        if not cfg:
            return
        chart_type, max_y, color_info, asset = cfg

        iconDim = 150
        iconX = x + 10
        iconY = y + (rowH - iconDim) // 2 - 30
        try:
            img = Image.open(f"{self.assetPath}/{asset}.png").convert("RGBA").resize((iconDim, iconDim))
            self.canvas.paste(img, (iconX, iconY), img)
        except FileNotFoundError:
            pass
        # buff name under the icon
        name = buff_key.replace("_", " ").title()
        self.draw.text((iconX - 10, iconY + iconDim + 8), name, font=self.getFont("medium", 40), fill=self.subtleColor)

        graphX = x + iconDim + 90
        graphW = colW - iconDim - 110
        graphH = rowH - 150
        baseline = y + rowH - 70

        if chart_type == "multi":
            datasets, avgs = [], []
            for dk, rgb in color_info:
                data = uptimeBuffsValues.get(dk, [0] * 600)
                r, g, b = rgb
                datasets.append({"data": data, "lineColor": rgb, "gradientFill": {0: (r, g, b, 10), 1: (r, g, b, 120)}})
                avgs.append((getAverageBuff(data), rgb))
            my = max_y
        elif chart_type == "stackable":
            r, g, b = color_info
            data = uptimeBuffsValues.get(buff_key, [0] * 600)
            datasets = [{"data": data, "lineColor": color_info, "gradientFill": {0: (r, g, b, 10), 1: (r, g, b, 120)}}]
            avgs = [(getAverageBuff(data), color_info)]
            my = max_y
        else:  # binary
            r, g, b = color_info
            data = uptimeBuffsValues.get(buff_key, [0] * 600)
            datasets = [{"data": data, "lineColor": color_info, "gradientFill": {0: (r, g, b, 255), 1: (r, g, b, 255)}}]
            avgs = [(getAverageBuff(data), color_info)]
            my = 1

        xData = list(range(max((len(d["data"]) for d in datasets), default=1)))
        self.drawGraph(graphX, baseline, graphW, graphH, xData, datasets, maxY=my,
                       showXAxisLabels=bool(xLabelFunc), showYAxisLabels=False, ticks=2, xLabelFunc=xLabelFunc)

        # average values (top-right of graph)
        ay = y + 18
        avgFont = self.getFont("semibold", 46)
        for avgText, col in avgs:
            bbox = self.draw.textbbox((0, 0), avgText, font=avgFont)
            tw = bbox[2] - bbox[0]
            self.draw.text((graphX + graphW - tw, ay), avgText, font=avgFont, fill=col)
            ay += 54

    def _drawBuffGrid(self, x, y, totalWidth, buffList, uptimeBuffsValues, getAverageBuff, columns=2, colGap=110, rowH=400, xLabelFunc=None):
        """Lay out buff uptime cells in a row-major grid (main buffs fill the top rows). Returns bottom y."""
        buffList = [b for b in buffList if b in BUFF_RENDER_CONFIG]
        n = len(buffList)
        if not n:
            return y
        colW = (totalWidth - colGap * (columns - 1)) / columns
        # bottom-most cell of each column gets the x-axis time labels
        bottomCells = set()
        for c in range(columns):
            idxs = [i for i in range(n) if i % columns == c]
            if idxs:
                bottomCells.add(idxs[-1])
        bottom = y
        for idx, buff_key in enumerate(buffList):
            row = idx // columns
            col = idx % columns
            cx = int(x + col * (colW + colGap))
            cy = y + row * rowH
            self._drawBuffRow(cx, cy, int(colW), rowH - 20, buff_key, uptimeBuffsValues, getAverageBuff,
                              xLabelFunc if idx in bottomCells else None)
            bottom = max(bottom, cy + rowH)
        return bottom

    def _drawFieldsSection(self, y, enabled_fields, field_patterns, draw=True):
        """Draw a compact Fields card. Returns the new bottom y."""
        if not enabled_fields:
            return y
        padding = 45
        header_height = 105
        column_gap = 35
        row_gap = 30
        columns = 2 if len(enabled_fields) > 1 else 1
        container_x = self.sidebarX - 30
        container_right = self.canvasSize[0] - self.sidebarPadding + 30
        inner_x = container_x + padding
        inner_right = container_right - padding
        tile_width = (inner_right - inner_x - column_gap * (columns - 1)) // columns
        tile_height = 180
        rows = math.ceil(len(enabled_fields) / columns)
        total_height = padding + header_height + rows * tile_height + max(0, rows - 1) * row_gap + padding
        if draw:
            self.draw.rounded_rectangle((container_x, y, container_right, y + total_height), radius=40, fill=self.cardBackground)
            self.draw.rounded_rectangle((container_x, y, container_x + 18, y + total_height), radius=9, fill=self.accentColor)
            header_y = y + padding - 5
            self.draw.text((inner_x, header_y), "Fields", font=self.getFont("semibold", 85), fill=self.bodyColor)
            count_text = f"{len(enabled_fields)} active"
            count_font = self.getFont("medium", 46)
            bbox = self.draw.textbbox((0, 0), count_text, font=count_font)
            self.draw.text((inner_right - (bbox[2] - bbox[0]), header_y + 22), count_text, font=count_font, fill=self.subtleColor)

            field_font = self.getFont("semibold", 54)
            pattern_font = self.getFont("medium", 38)
            for idx, fname in enumerate(enabled_fields):
                pattern = field_patterns.get(fname, "unknown")
                col = idx % columns
                row = idx // columns
                tile_x = int(inner_x + col * (tile_width + column_gap))
                tile_y = int(y + padding + header_height + row * (tile_height + row_gap))
                self.draw.rounded_rectangle((tile_x, tile_y, tile_x + tile_width, tile_y + tile_height), radius=28, fill=self.sideBarBackground)
                self.draw.rounded_rectangle((tile_x + 24, tile_y + 36, tile_x + 44, tile_y + tile_height - 36), radius=10, fill=self.accentColorDim)
                self.draw.text((tile_x + 70, tile_y + 34), fname.title(), font=field_font, fill=self.bodyColor)
                pattern_text = pattern.replace("_", " ").title()
                bbox = self.draw.textbbox((0, 0), pattern_text, font=pattern_font)
                pill_w = min(tile_width - 90, (bbox[2] - bbox[0]) + 48)
                pill_x = tile_x + 70
                pill_y = tile_y + 110
                self.draw.rounded_rectangle((pill_x, pill_y, pill_x + pill_w, pill_y + 48), radius=18, fill=self.backgroundColor)
                self.draw.text((pill_x + 24, pill_y + 5), pattern_text, font=pattern_font, fill=self.subtleColor)
        return y + total_height + 100

    def _drawHourlySidebar(self, top, sessionTime, onlyValidHourlyHoney, sessionHoney, hourlyReportStats,
                           planterNames, planterTimes, planterFields, buffQuantity, hourlyBuff_list,
                           nectarQuantity, enabled_fields, field_patterns, draw=True):
        """Draw (or measure, when draw=False) the right sidebar. Returns the bottom y."""
        y2 = top

        # planters (top)
        if planterNames:
            if draw:
                self.draw.text((self.sidebarX, y2), "Planters", font=self.getFont("semibold", 85), fill=self.bodyColor)
            y2 += 250
            if draw:
                self.drawPlanters(y2, planterNames, planterTimes, planterFields)
            y2 += 650

        # fields (beneath planters)
        y2 = self._drawFieldsSection(y2, enabled_fields, field_patterns, draw=draw)

        # snapshot buffs
        if draw:
            self.draw.text((self.sidebarX, y2), "Buffs", font=self.getFont("semibold", 85), fill=self.bodyColor)
        y2 += 250
        if draw:
            self.drawBuffs(y2, buffQuantity, hourlyBuff_list)
        buffRows = math.ceil(len(hourlyBuff_list) / 4) if hourlyBuff_list else 1
        y2 += 300 * max(1, buffRows)

        # nectars
        y2 += 200
        if draw:
            self.draw.text((self.sidebarX, y2), "Nectars", font=self.getFont("semibold", 85), fill=self.bodyColor)
        y2 += 250
        if draw:
            self.drawNectars(y2, nectarQuantity)
        y2 += 500

        # task times
        y2 += 100
        if draw:
            self.draw.text((self.sidebarX, y2), "Task Times", font=self.getFont("semibold", 85), fill=self.bodyColor)
        y2 += 250
        if draw:
            self.drawTaskTimes(y2, [
                {"label": "Gathering",  "data": hourlyReportStats["gathering_time"],  "color": self.gatherColor},
                {"label": "Converting", "data": hourlyReportStats["converting_time"], "color": self.convertColor},
                {"label": "Bug Run",    "data": hourlyReportStats["bug_run_time"],    "color": self.otherColor},
                {"label": "Other",      "data": hourlyReportStats["misc_time"],       "color": self.subtleColor},
            ])
        y2 += 1500

        # session stats (bottom)
        y2 += 100
        if draw:
            self.draw.text((self.sidebarX, y2), "Session", font=self.getFont("semibold", 85), fill=self.bodyColor)
        y2 += 250
        if draw:
            self.drawSessionStat(y2, "time_icon", "Session Time", self.displayTime(sessionTime, ['d', 'h', 'm']), self.bodyColor)
        y2 += 300
        if draw:
            self.drawSessionStat(y2, "honey_icon", "Current Honey", self.millify(onlyValidHourlyHoney[-1]), self.honeyColor)
        y2 += 300
        if draw:
            self.drawSessionStat(y2, "session_honey_icon", "Session Honey", self.millify(sessionHoney), (253, 227, 149))
        y2 += 300

        return y2

    def drawHourlyReport(self, hourlyReportStats, sessionTime, honeyPerMin, sessionHoney, honeyThisHour, onlyValidHourlyHoney, buffQuantity, nectarQuantity, planterData, uptimeBuffsValues, buffGatherIntervals, enabled_fields=None, field_patterns=None, configuredUptimeBuffs=None, configuredHourlyBuffs=None):

        def getAverageBuff(buffValues):
            count = 0
            total = 0
            for i, e in enumerate(buffGatherIntervals):
                if e and i < len(buffValues):
                    total += buffValues[i]
                    count += 1
            res = total / count if count else 0
            return f"x{res:.2f}"

        uptimeBuff_list = configuredUptimeBuffs if configuredUptimeBuffs is not None else DEFAULT_UPTIME_BUFFS
        hourlyBuff_list = configuredHourlyBuffs if configuredHourlyBuffs is not None else DEFAULT_HOURLY_BUFFS
        if enabled_fields is None:
            enabled_fields = []
        if field_patterns is None:
            field_patterns = {}

        return self._drawStatMonitorReport(
            "Hourly Report", hourlyReportStats, sessionTime, honeyPerMin, sessionHoney,
            honeyThisHour, onlyValidHourlyHoney, buffQuantity, nectarQuantity, planterData,
            uptimeBuffsValues, buffGatherIntervals,
            configuredUptimeBuffs=uptimeBuff_list,
            configuredHourlyBuffs=hourlyBuff_list,
        )

        self.sidebarX = self.canvasW - self.sidebarWidth + self.sidebarPadding
        mins = list(range(61))

        # working canvas (cropped to content height at the end)
        self.canvas = Image.new('RGBA', self.canvasSize, (*self.backgroundColor, 255))
        self.draw = ImageDraw.Draw(self.canvas)

        # gather planter data for the sidebar
        planterNames, planterTimes, planterFields = [], [], []
        if planterData:
            for i in range(len(planterData["planters"])):
                if planterData["planters"][i]:
                    planterNames.append(planterData["planters"][i])
                    planterTimes.append(planterData["harvestTimes"][i] - time.time())
                    planterFields.append(planterData["fields"][i])

        # ---- header banner (full width) ----
        headerBottom = self._drawHeaderBanner("Hourly Report", "Your stats for this hour")

        # ---- measure sidebar height so its background can be sized first ----
        sidebarTop = headerBottom + 80
        sidebarBottom = self._drawHourlySidebar(sidebarTop, sessionTime, onlyValidHourlyHoney, sessionHoney,
                                                hourlyReportStats, planterNames, planterTimes, planterFields,
                                                buffQuantity, hourlyBuff_list, nectarQuantity,
                                                enabled_fields, field_patterns, draw=False)

        # ---- left column: stat cards, charts, buff grid ----
        y = headerBottom + 80
        # stat cards (evenly fill the left region width)
        cardGap = 60
        cardW = (self.availableSpace - cardGap * 4) // 5
        avgHoneyPerHour = max(0, sessionHoney / (sessionTime / 3600)) if sessionTime > 0 else 0
        cards = [
            ("average_icon",     self.millify(avgHoneyPerHour),          "Average Honey\nPer Hour",     None,            None),
            ("honey_icon",       self.millify(honeyThisHour),            "Honey Made\nThis Hour",       self.honeyColor, None),
            ("kill_icon",        hourlyReportStats["bugs"],              "Bugs Killed\nThis Hour",      (254, 101, 99),  (254, 101, 99)),
            ("quest_icon",       hourlyReportStats["quests_completed"],  "Quests Completed\nThis Hour", (103, 253, 153), (103, 253, 153)),
            ("vicious_bee_icon", hourlyReportStats["vicious_bees"],      "Vicious Bees\nThis Hour",     (132, 233, 254), (132, 233, 254)),
        ]
        for i, (icon, val, label, fc, ic) in enumerate(cards):
            self.drawStatCard(self.leftPadding + i * (cardW + cardGap), y, icon, val, label, fc, ic, cardWidth=cardW)
        y += 750 + 150

        # buff uptime — two-column grid (moved to the top of the report)
        self.draw.text((self.leftPadding, y), "Buff Uptime", fill=self.bodyColor, font=self.getFont("semibold", 85))
        y += 250

        def gridTimeLabel(i, val):
            if i % 100:
                return
            m = val // 10
            hour = self.hour
            if m == 60:
                hour = (hour + 1) % 24
                m = 0
            return f"{str(hour).zfill(2)}:{str(int(m)).zfill(2)}"

        y = self._drawBuffGrid(self.leftPadding, y, self.availableSpace, uptimeBuff_list,
                               uptimeBuffsValues, getAverageBuff, columns=2, xLabelFunc=gridTimeLabel)

        chartContentWidth = self.canvasW - self.leftPadding * 2
        chartGraphX = self.leftPadding + 450
        chartGraphWidth = chartContentWidth - 570
        y = max(y, sidebarBottom + 180)

        # honey/sec — accent colored
        y += 150
        self.draw.text((self.leftPadding, y), "Honey / Sec", fill=self.bodyColor, font=self.getFont("semibold", 85))
        y += 950
        ar, ag, ab = self.accentColor
        self.drawGraph(chartGraphX, y, chartGraphWidth, 700, mins,
                       [{"data": honeyPerMin, "lineColor": self.accentColor,
                         "gradientFill": {0: (ar, ag, ab, 38), 1: (ar, ag, ab, 153)}}],
                       xLabelFunc=self.transformXLabelTime, yLabelFunc=lambda i, x: self.millify(x))

        # backpack
        y += 200
        self.draw.text((self.leftPadding, y), "Backpack", fill=self.bodyColor, font=self.getFont("semibold", 85))
        y += 950
        self.drawGraph(chartGraphX, y, chartGraphWidth, 700, mins,
                       [{"data": hourlyReportStats["backpack_per_min"], "lineColor": "gradient",
                         "gradientFill": {0: (65, 255, 128, 90), 0.6: (201, 163, 36, 90), 0.9: (255, 65, 84, 90), 1: (255, 65, 84, 90)}}],
                       maxY=100, xLabelFunc=self.transformXLabelTime, yLabelFunc=lambda i, x: f"{int(x)}%")

        leftBottom = y

        # ---- draw the sidebar (background ends at its own content, then content) ----
        finalContentBottom = max(leftBottom, sidebarBottom)
        self.draw.rectangle((self.canvasW - self.sidebarWidth, headerBottom + 40, self.canvasW, sidebarBottom + 60), fill=self.sideBarBackground)
        self._drawHourlySidebar(sidebarTop, sessionTime, onlyValidHourlyHoney, sessionHoney,
                                hourlyReportStats, planterNames, planterTimes, planterFields,
                                buffQuantity, hourlyBuff_list, nectarQuantity,
                                enabled_fields, field_patterns, draw=True)

        # ---- crop to actual content height ----
        finalH = min(self.canvasMaxH, int(finalContentBottom) + 120)
        self.canvas = self.canvas.crop((0, 0, self.canvasW, finalH))
        self.draw = ImageDraw.Draw(self.canvas)
        return self.canvas
