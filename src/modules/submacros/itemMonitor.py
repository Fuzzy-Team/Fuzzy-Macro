"""
BSS loot-toast item monitor.

Watches the bottom-right "+N Item" popup, template-matches item labels + digits,
accumulates hourly totals, and feeds Fuzzy's hourly/session reports.
"""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from modules import bitmap_matcher
from modules.screen.screenshot import mssScreenshotPillowRGBA

# Capture size (client pixels at 1x). Retina uses * multi.
HAYSTACK_W = 349
HAYSTACK_H = 49
QUICK_DETECTION_WINDOW_MS = 6000
BANNER_RGB = (34, 87, 168)  # 0xFF2257A8

# Detection key → display name / category / report icon slug
ITEM_META = {
    "Blueberry": {"display": "Blueberry", "category": "Material", "icon": "blueberry"},
    "SunflowerSeed": {"display": "Sunflower Seed", "category": "Material", "icon": "sunflowerseed"},
    "Strawberry": {"display": "Strawberry", "category": "Material", "icon": "strawberry"},
    "Pineapple": {"display": "Pineapple", "category": "Material", "icon": "pineapple"},
    "Treat": {"display": "Treat", "category": "Material", "icon": "treat"},
    "Ticket": {"display": "Ticket", "category": "Currency", "icon": "ticket"},
    "Moon Charm": {"display": "Moon Charm", "category": "Material", "icon": "moon_charm"},
    "Royal Jelly": {"display": "Royal Jelly", "category": "Consumable", "icon": "royal_jelly"},
    "Magic Bean": {"display": "Magic Bean", "category": "Consumable", "icon": "magic_bean"},
    "Soft Wax": {"display": "Soft Wax", "category": "Consumable", "icon": "soft_wax"},
    "Blue Extract": {"display": "Blue Extract", "category": "Consumable", "icon": "blue_extract"},
    "Red Extract": {"display": "Red Extract", "category": "Consumable", "icon": "red_extract"},
    "Enzyme": {"display": "Enzyme", "category": "Consumable", "icon": "enzyme"},
    "Oil": {"display": "Oil", "category": "Consumable", "icon": "oil"},
    "Gumdrops": {"display": "Gumdrops", "category": "Consumable", "icon": "gumdrop"},
    "Star Jelly": {"display": "Star Jelly", "category": "Consumable", "icon": "star_jelly"},
    "Loaded Dice": {"display": "Loaded Dice", "category": "Consumable", "icon": "loaded_dice"},
    "Micro-Converter": {"display": "Micro-Converter", "category": "Consumable", "icon": "micro_converter"},
    "Honeysuckle": {"display": "Honeysuckle", "category": "Material", "icon": "honeysuckle"},
    "Field Dice": {"display": "Field Dice", "category": "Consumable", "icon": "field_dice"},
    "Tropical Drink": {"display": "Tropical Drink", "category": "Consumable", "icon": "tropical_drink"},
    "Bitterberry": {"display": "Bitterberry", "category": "Material", "icon": "bitterberry"},
    "Super Smoothie": {"display": "Super Smoothie", "category": "Consumable", "icon": "super_smoothie"},
}

CATEGORY_ORDER = ("Currency", "Material", "Consumable")
ASSET_DIR = Path("images/itemmonitor")


def _slug(name: str) -> str:
    return name.replace(" ", "_").replace("-", "_").lower()


def _scale_image(img: Image.Image, scale: int) -> Image.Image:
    if scale <= 1:
        return img.convert("RGBA")
    return img.convert("RGBA").resize((img.width * scale, img.height * scale), Image.Resampling.NEAREST)


class ItemMonitor:
    def __init__(self, robloxWindow):
        self.robloxWindow = robloxWindow
        self.collected_items = {}
        self.session_collected_items = {}
        self.item_timeline = {}  # clock minute -> total amount this hour
        self.last_detection_time = {}
        self.last_detected_value = {}
        self.start_time = time.time()
        self.query_total = 0
        self.total_items_detected = 0
        self._templates_loaded_for = None
        self.item_templates = {}
        self.digit_templates = {}
        self.plus_template = None
        self._load_templates()

    def _scale(self) -> int:
        return 2 if getattr(self.robloxWindow, "isRetina", False) else max(
            1, int(round(getattr(self.robloxWindow, "multi", 1) or 1))
        )

    def _load_templates(self):
        scale = self._scale()
        if self._templates_loaded_for == scale and self.item_templates:
            return

        self.item_templates = {}
        for key in ITEM_META:
            path = ASSET_DIR / f"item_{_slug(key)}.png"
            if path.exists():
                self.item_templates[key] = _scale_image(Image.open(path), scale)

        self.digit_templates = {}
        for n in range(10):
            path = ASSET_DIR / f"digit_{n}.png"
            if path.exists():
                self.digit_templates[n] = _scale_image(Image.open(path), scale)

        plus_path = ASSET_DIR / "plus.png"
        self.plus_template = _scale_image(Image.open(plus_path), scale) if plus_path.exists() else None
        self._templates_loaded_for = scale

    def reset_hourly(self):
        self.collected_items = {}
        self.item_timeline = {}
        self.last_detection_time = {}
        self.last_detected_value = {}

    def reset_all(self):
        self.reset_hourly()
        self.session_collected_items = {}
        self.start_time = time.time()
        self.query_total = 0
        self.total_items_detected = 0

    def get_snapshot(self, session=False):
        collected = self.session_collected_items if session else self.collected_items
        return {
            "collected_items": dict(collected),
            "session_collected_items": dict(self.session_collected_items),
            "item_timeline": dict(self.item_timeline),
            "total_items_detected": self.total_items_detected,
            "query_total": self.query_total,
            "start_time": self.start_time,
        }

    def load_snapshot(self, data):
        if not data:
            return
        self.collected_items = dict(data.get("collected_items") or {})
        self.session_collected_items = dict(
            data.get("session_collected_items")
            or data.get("collected_items")
            or {}
        )
        self.item_timeline = {int(k): int(v) for k, v in (data.get("item_timeline") or {}).items()}
        self.total_items_detected = int(data.get("total_items_detected") or 0)
        self.query_total = int(data.get("query_total") or 0)
        if data.get("start_time"):
            self.start_time = float(data["start_time"])

    def _create_haystack(self):
        scale = self._scale()
        w = HAYSTACK_W * scale
        h = HAYSTACK_H * scale
        rw = getattr(self.robloxWindow, "mw", 0) or 0
        rh = getattr(self.robloxWindow, "mh", 0) or 0
        if rw < w or rh < h:
            return None
        left = int(self.robloxWindow.mx + rw - w)
        top = int(self.robloxWindow.my + rh - h)
        try:
            return mssScreenshotPillowRGBA(left, top, w, h).convert("RGBA")
        except Exception:
            return None

    def _isolate_haystack(self, haystack: Image.Image) -> Image.Image:
        """Crop to blue toast banner region when present."""
        arr = np.asarray(haystack, dtype=np.uint8)
        r, g, b = BANNER_RGB
        rgb = arr[..., :3].astype(np.int16)
        mask = (
            (np.abs(rgb[..., 0] - r) <= 2)
            & (np.abs(rgb[..., 1] - g) <= 2)
            & (np.abs(rgb[..., 2] - b) <= 2)
        )
        ys, xs = np.where(mask)
        if len(xs) < 2 or len(ys) < 2:
            return haystack
        x1, x2 = int(xs.min()), int(xs.max())
        y1, y2 = int(ys.min()), int(ys.max())
        if x2 - x1 < 8 or y2 - y1 < 4:
            return haystack
        return haystack.crop((x1, y1, x2 + 1, y2 + 1))

    def _isolate_digits(self, haystack: Image.Image, item_needle: Image.Image):
        if self.plus_template is None:
            return None
        plus_hit = bitmap_matcher.find_bitmap_cython(haystack, self.plus_template, variance=6)
        item_hit = bitmap_matcher.find_bitmap_cython(haystack, item_needle, variance=0)
        if not plus_hit or not item_hit:
            return None
        plus_w = self.plus_template.size[0]
        digit_x = plus_hit[0] + plus_w
        digit_w = item_hit[0] - digit_x
        if digit_w <= 0 or digit_x < 0 or digit_x >= haystack.size[0]:
            return None
        return haystack.crop((digit_x, 0, digit_x + digit_w, haystack.size[1]))

    def _detect_digits(self, digits_img: Image.Image) -> int:
        """Read toast quantity via digit templates; special-case 1 vs 4 and 3 vs 8."""
        found = {}

        def search_digit(n: int):
            needle = self.digit_templates.get(n)
            if needle is None:
                return
            hits = bitmap_matcher.find_all_bitmap_cython(digits_img, needle, variance=1, max_matches=8) or []
            for x, _y in hits:
                if n == 1 and found.get(x - 5) == 4:
                    continue
                if n == 3 and found.get(x - 1) == 8:
                    continue
                found[x] = n

        for n in (0, 2, 4, 5, 6, 7, 8, 9):
            search_digit(n)
        for n in (1, 3):
            search_digit(n)

        if not found:
            return 0
        return int("".join(str(found[x]) for x in sorted(found)))

    def detect_once(self):
        """One detection pass. Safe to call ~every second from the hourly background loop."""
        self._load_templates()
        haystack = self._create_haystack()
        self.query_total += 1
        if haystack is None or not self.item_templates:
            return None

        isolated = self._isolate_haystack(haystack)

        matched_key = None
        matched_needle = None
        for key, needle in self.item_templates.items():
            if bitmap_matcher.find_bitmap_cython(isolated, needle, variance=0):
                matched_key = key
                matched_needle = needle
                break

        if not matched_key:
            return None

        digits_img = self._isolate_digits(isolated, matched_needle)
        if digits_img is None:
            return None

        n = self._detect_digits(digits_img)
        if n <= 0:
            return None

        now = time.time() * 1000
        last_t = self.last_detection_time.get(matched_key)
        if last_t is not None and (now - last_t) < QUICK_DETECTION_WINDOW_MS:
            amount = max(0, n - self.last_detected_value.get(matched_key, 0))
        else:
            amount = n

        self.last_detection_time[matched_key] = now
        self.last_detected_value[matched_key] = n

        if amount <= 0:
            return None

        self.collected_items[matched_key] = self.collected_items.get(matched_key, 0) + amount
        self.session_collected_items[matched_key] = self.session_collected_items.get(matched_key, 0) + amount
        minute_slot = datetime.now().minute
        self.item_timeline[minute_slot] = self.item_timeline.get(minute_slot, 0) + amount
        self.total_items_detected += 1
        return matched_key, amount

    @staticmethod
    def sorted_items(collected_items, exclude=("Honey",)):
        grouped = {cat: [] for cat in CATEGORY_ORDER}
        for key, qty in (collected_items or {}).items():
            if key in exclude:
                continue
            meta = ITEM_META.get(key, {"display": key, "category": "Material", "icon": _slug(key)})
            cat = meta.get("category", "Material")
            if cat not in grouped:
                cat = "Material"
            grouped[cat].append({
                "key": key,
                "name": meta.get("display", key),
                "qty": int(qty),
                "icon": meta.get("icon", _slug(key)),
                "category": cat,
            })
        result = []
        for cat in CATEGORY_ORDER:
            items = sorted(grouped[cat], key=lambda x: x["qty"], reverse=True)
            result.extend(items)
        return result

    @staticmethod
    def top_items(collected_items, limit=3, exclude=("Honey", "Treat")):
        items = [
            {
                "key": k,
                "name": ITEM_META.get(k, {}).get("display", k),
                "qty": int(v),
                "icon": ITEM_META.get(k, {}).get("icon", _slug(k)),
            }
            for k, v in (collected_items or {}).items()
            if k not in exclude
        ]
        items.sort(key=lambda x: x["qty"], reverse=True)
        return items[:limit]


def generate_item_report(snapshot, setdat=None, report_type="hourly", output_path="itemReport.png"):
    """
    Draw a standalone Item Monitor report and save to disk.
    Returns (output_path, embed_fields) or (None, None) if there is nothing to show.
    """
    setdat = setdat or {}
    collected = (snapshot or {}).get("collected_items") or {}
    if not collected:
        return None, None

    from modules.submacros.hourlyReport import HourlyReportDrawer, resolveReportTheme

    gui_theme = setdat.get("gui_theme", "Brown")
    theme = resolveReportTheme(gui_theme)
    accent = setdat.get("hourly_report_accent", "green")
    time_format = setdat.get("hourly_report_time_format", 24)

    drawer = ItemReportDrawer(time_format=time_format, theme=theme, accent=accent)
    canvas = drawer.draw(snapshot, report_type=report_type)
    w, h = canvas.size
    canvas = canvas.resize((int(w * 1.2), int(h * 1.2)))
    canvas.save(output_path)

    fields = []
    for item in ItemMonitor.sorted_items(collected)[:15]:
        qty = drawer.millify(item["qty"]).replace(" ", "")
        fields.append(f"+{qty} {item['name']}")
    embed_fields = [{"name": "Items Gained", "value": "\n".join(fields), "inline": False}] if fields else None
    return output_path, embed_fields


class ItemReportDrawer:
    """Standalone Item Monitor report image."""

    VERSION = "0.1"

    def __init__(self, time_format=24, theme="dark", accent="green"):
        from modules.submacros.hourlyReport import HourlyReportDrawer
        # Reuse theme/palette construction from the hourly drawer
        base = HourlyReportDrawer(time_format=time_format, theme=theme, accent=accent)
        self.backgroundColor = base.baseBackgroundColor
        self.panelColor = base.panelColor
        self.panelOutline = base.panelOutline
        self.bodyColor = base.bodyColor
        self.subtleColor = base.subtleColor
        self.graphBgColor = base.graphBgColor
        self.graphGridColor = base.graphGridColor
        self.graphTickColor = base.graphTickColor
        self.accentColor = base.accentColor
        self.time_format = time_format
        self.assetPath = "hourly_report/assets"
        self._base = base

    def getFont(self, weight, fontSize):
        return self._base.getFont(weight, fontSize)

    def millify(self, n):
        return self._base.millify(n)

    def _fitText(self, text, maxWidth, weight="semibold", size=40, minSize=18):
        size = int(size)
        while size > minSize:
            font = self.getFont(weight, size)
            bbox = self.draw.textbbox((0, 0), str(text), font=font)
            if bbox[2] - bbox[0] <= maxWidth:
                return font
            size -= 2
        return self.getFont(weight, minSize)

    def _drawPanel(self, box, title=None, titleSize=48):
        x, y, w, h = box
        self.draw.rounded_rectangle(
            (x, y, x + w, y + h), radius=20,
            fill=self.panelColor, outline=self.panelOutline, width=5,
        )
        if title:
            font = self.getFont("bold", titleSize)
            bbox = self.draw.textbbox((0, 0), title, font=font)
            self.draw.text(
                (x + (w - (bbox[2] - bbox[0])) / 2, y + 10),
                title, font=font, fill=self.bodyColor,
            )

    def draw(self, snapshot, report_type="hourly"):
        from modules.misc.settingsManager import getMacroVersion
        import platform

        collected = (snapshot or {}).get("collected_items") or {}
        timeline = (snapshot or {}).get("item_timeline") or {}
        sorted_items = ItemMonitor.sorted_items(collected)
        top = ItemMonitor.top_items(collected, limit=3)

        W, H = 4000, 1100
        self.canvas = Image.new("RGBA", (W, H), (*self.backgroundColor, 255))
        self.draw = ImageDraw.Draw(self.canvas)

        items_region = (50, 50, 2900, 1000)
        this_hour_region = (3000, 50, 950, 500)
        info_region = (3000, 600, 950, 450)

        self._drawPanel(items_region, "Items Gained")
        self._drawPanel(this_hour_region, "This Hour" if report_type == "hourly" else "This Session")
        self._drawPanel(info_region, f"ItemMonitor")

        self._drawItemCards(items_region, sorted_items)
        self._drawTimeline(items_region, timeline)
        self._drawTopThree(this_hour_region, top)

        # Info panel
        ix, iy, iw, ih = info_region
        uptime = max(0, time.time() - float((snapshot or {}).get("start_time") or time.time()))
        uptime_str = f"{int(uptime // 3600):02d}:{int((uptime % 3600) // 60):02d}:{int(uptime % 60):02d}"
        qps = 0.0
        if uptime > 0:
            qps = float((snapshot or {}).get("query_total") or 0) / uptime
        total_detected = int((snapshot or {}).get("total_items_detected") or 0)

        lines = [
            f"Total Items Detected: {total_detected}",
            f"Queries Per Sec: {qps:.2f}",
            f"Uptime: {uptime_str}",
        ]
        font = self.getFont("semibold", 36)
        y = iy + 80
        for i, line in enumerate(lines):
            color = (0, 212, 255) if i == 3 else self.subtleColor
            bbox = self.draw.textbbox((0, 0), line, font=font)
            self.draw.text((ix + (iw - (bbox[2] - bbox[0])) / 2, y), line, font=font, fill=color)
            y += 52

        # Footer branding
        footer_font = self.getFont("semibold", 32)
        version_text = f"Fuzzy Macro v{getMacroVersion()}"
        bbox = self.draw.textbbox((0, 0), version_text, font=footer_font)
        self.draw.text(
            (ix + (iw - (bbox[2] - bbox[0])) / 2, iy + ih - 60),
            version_text, font=footer_font, fill=(180, 123, 209),
        )
        return self.canvas

    def _drawItemCards(self, region, sorted_items):
        x, y, w, h = region
        card_w, card_h = 200, 220
        pad = 30
        cols = max(1, (w - pad * 2) // (card_w + pad))
        start_x = x + pad
        start_y = y + 80
        max_rows = 2  # leave room for timeline

        for i, item in enumerate(sorted_items):
            col = i % cols
            row = i // cols
            if row >= max_rows:
                break
            cx = start_x + col * (card_w + pad)
            cy = start_y + row * (card_h + pad)
            self.draw.rounded_rectangle(
                (cx, cy, cx + card_w, cy + card_h),
                radius=15, fill=(50, 50, 50), outline=self.panelOutline, width=3,
            )

            icon_size = 100
            try:
                icon = Image.open(f"{self.assetPath}/items/{item['icon']}.png").convert("RGBA")
                icon = icon.resize((icon_size, icon_size), Image.Resampling.LANCZOS)
                self.canvas.paste(icon, (cx + (card_w - icon_size) // 2, cy + 50), icon)
            except Exception:
                pass

            name_font = self._fitText(item["name"], card_w - 20, weight="semibold", size=28, minSize=14)
            name_bbox = self.draw.textbbox((0, 0), item["name"], font=name_font)
            self.draw.text(
                (cx + (card_w - (name_bbox[2] - name_bbox[0])) / 2, cy + 12),
                item["name"], font=name_font, fill=self.subtleColor,
            )

            qty_text = f"+{self.millify(item['qty']).replace(' ', '')}"
            qty_font = self.getFont("bold", 36)
            qty_bbox = self.draw.textbbox((0, 0), qty_text, font=qty_font)
            self.draw.text(
                (cx + (card_w - (qty_bbox[2] - qty_bbox[0])) / 2, cy + 160),
                qty_text, font=qty_font, fill=(54, 203, 54),
            )

    def _drawTimeline(self, region, timeline):
        x, y, w, h = region
        graph = (x + 100, y + h - 210, w - 200, 120)
        gx, gy, gw, gh = graph

        # Background + grid
        self.draw.rounded_rectangle(
            (gx - 20, gy - 10, gx + gw + 20, gy + gh + 10),
            radius=12, fill=(*self.graphBgColor, 180), outline=self.graphGridColor, width=2,
        )
        for i in range(7):
            px = gx + gw * i / 6
            self.draw.line((px, gy, px, gy + gh), fill=self.graphGridColor, width=2)
        self.draw.line((gx, gy + gh / 2, gx + gw, gy + gh / 2), fill=self.graphGridColor, width=2)

        # Time labels for the current hour
        base = datetime.now().replace(minute=0, second=0, microsecond=0)
        label_font = self.getFont("bold", 24)
        for i in range(7):
            minute = i * 10
            t = base.replace(hour=(base.hour + (minute // 60)) % 24, minute=minute % 60)
            label = t.strftime("%I:%M %p") if self.time_format == 12 else t.strftime("%H:%M")
            bbox = self.draw.textbbox((0, 0), label, font=label_font)
            self.draw.text(
                (gx + gw * i / 6 - (bbox[2] - bbox[0]) / 2, gy + gh + 18),
                label, font=label_font, fill=self.bodyColor,
            )

        values = [int(timeline.get(m, timeline.get(str(m), 0)) or 0) for m in range(60)]
        max_val = max(values) if values else 0
        # Y labels
        y_font = self.getFont("bold", 22)
        for label, ratio in ((str(max_val or 0), 0), (str((max_val or 0) // 2), 0.5), ("0", 1)):
            bbox = self.draw.textbbox((0, 0), label, font=y_font)
            self.draw.text(
                (gx - 20 - (bbox[2] - bbox[0]), gy + gh * ratio - 12),
                label, font=y_font, fill=self.bodyColor,
            )

        if max_val <= 0:
            return

        bar_w = gw / 60
        for minute, count in enumerate(values):
            if count <= 0:
                continue
            bar_h = gh * count / max_val
            bx = gx + bar_w * minute + 2
            by = gy + gh - bar_h
            self.draw.rectangle((bx, by, bx + bar_w - 4, gy + gh), fill=(0, 255, 0))
            self.draw.rectangle((bx, by, bx + bar_w - 4, gy + gh), outline=(0, 170, 0), width=1)

    def _drawTopThree(self, region, top_items):
        x, y, w, h = region
        if not top_items:
            empty_font = self.getFont("semibold", 36)
            text = "No items yet"
            bbox = self.draw.textbbox((0, 0), text, font=empty_font)
            self.draw.text(
                (x + (w - (bbox[2] - bbox[0])) / 2, y + h / 2),
                text, font=empty_font, fill=self.subtleColor,
            )
            return

        colors = [(255, 215, 0), (192, 192, 192), (205, 127, 50)]
        card_w, card_h = 280, 360
        spacing = 20
        total_w = card_w * min(3, len(top_items)) + spacing * (min(3, len(top_items)) - 1)
        start_x = x + (w - total_w) / 2
        start_y = y + 80

        for rank, item in enumerate(top_items[:3]):
            cx = start_x + rank * (card_w + spacing)
            cy = start_y
            self.draw.rounded_rectangle(
                (cx, cy, cx + card_w, cy + card_h),
                radius=15, fill=(42, 42, 42), outline=colors[rank], width=4,
            )

            icon_size = 100
            try:
                icon = Image.open(f"{self.assetPath}/items/{item['icon']}.png").convert("RGBA")
                icon = icon.resize((icon_size, icon_size), Image.Resampling.LANCZOS)
                self.canvas.paste(icon, (int(cx + (card_w - icon_size) / 2), int(cy + 40)), icon)
            except Exception:
                pass

            name_font = self._fitText(item["name"], card_w - 20, weight="bold", size=30, minSize=16)
            name_bbox = self.draw.textbbox((0, 0), item["name"], font=name_font)
            self.draw.text(
                (cx + (card_w - (name_bbox[2] - name_bbox[0])) / 2, cy + 160),
                item["name"], font=name_font, fill=self.bodyColor,
            )

            qty_text = f"+{self.millify(item['qty']).replace(' ', '')}"
            qty_font = self.getFont("bold", 36)
            qty_bbox = self.draw.textbbox((0, 0), qty_text, font=qty_font)
            self.draw.text(
                (cx + (card_w - (qty_bbox[2] - qty_bbox[0])) / 2, cy + 210),
                qty_text, font=qty_font, fill=(0, 255, 0),
            )

            rank_text = f"#{rank + 1}"
            rank_font = self.getFont("bold", 56)
            rank_bbox = self.draw.textbbox((0, 0), rank_text, font=rank_font)
            self.draw.text(
                (cx + (card_w - (rank_bbox[2] - rank_bbox[0])) / 2, cy + 270),
                rank_text, font=rank_font, fill=colors[rank],
            )
