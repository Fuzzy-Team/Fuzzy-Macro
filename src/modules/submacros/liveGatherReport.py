import io
import json
import re
import threading
import time

import requests
from PIL import Image, ImageDraw

from modules.screen.screenshot import mssScreenshot
from modules.logging.log import resolve_bot_route, resolve_route, resolve_webhook_route


class LiveGatherReport:
    REFERENCE_WINDOW_WIDTH = 1920
    REFERENCE_WINDOW_HEIGHT = 1080
    REFERENCE_CAPTURE = (650, 100)
    REFERENCE_CAPTURE_LEFT_OFFSET = -320
    REFERENCE_HUD_CARDS = (
        (20, 0, 315, 36),
        (320, 0, 615, 36),
    )
    REFERENCE_CARD_RADIUS = 7

    def __init__(self, webhook_url, roblox_window, interval=15, time_format=24, route_settings=None, bot_token="", ping_user_id=None, delivery_mode="both", route_category="gathering"):
        route_category = route_category or "gathering"
        if delivery_mode == "discord_bot":
            self.route, self.route_category, self.route_kind = resolve_route(route_settings or {}, route_category, "")
            if not self.route:
                self.route, self.route_category, self.route_kind = resolve_bot_route(route_settings or {}, route_category, webhook_url)
        elif delivery_mode == "both":
            self.route, self.route_category, self.route_kind = resolve_route(route_settings or {}, route_category, "")
            if not self.route:
                self.route, self.route_category, self.route_kind = resolve_webhook_route(route_settings or {}, route_category, webhook_url)
        elif delivery_mode == "webhook":
            self.route, self.route_category, self.route_kind = resolve_webhook_route(route_settings or {}, route_category, webhook_url)
        else:
            self.route, self.route_category, self.route_kind = resolve_route(route_settings or {}, route_category, webhook_url)
        self.webhook_url = self.route if self.route_kind == "webhook" else ""
        self.channel_id = self.route if self.route_kind == "bot" else ""
        self.bot_token = bot_token or ""
        self.ping_user_id = ping_user_id
        self.roblox_window = roblox_window
        self.interval = max(10, min(20, int(interval or 15)))
        self.time_format = time_format
        self.stop_event = threading.Event()
        self.thread = None
        self.message_id = None
        self.webhook_id = None
        self.webhook_token = None
        self._parse_webhook_url()

    def _parse_webhook_url(self):
        match = re.search(r"/webhooks/([^/]+)/([^/?]+)", self.webhook_url or "")
        if not match:
            return
        self.webhook_id = match.group(1)
        self.webhook_token = match.group(2)

    def start(self, field, gather_time_limit, get_elapsed_seconds, is_paused=None, activity="Gathering"):
        if self.route_kind == "webhook" and (not self.webhook_id or not self.webhook_token):
            return
        if self.route_kind == "bot" and (not self.channel_id or not self.bot_token):
            return
        if self.route_kind not in ("webhook", "bot"):
            return
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.thread = threading.Thread(
            target=self._run,
            args=(field, gather_time_limit, get_elapsed_seconds, is_paused, activity),
            daemon=True,
        )
        self.thread.start()

    def stop(self):
        self.stop_event.set()

    def _run(self, field, gather_time_limit, get_elapsed_seconds, is_paused=None, activity="Gathering"):
        while not self.stop_event.is_set():
            while is_paused and is_paused():
                if self.stop_event.wait(0.1):
                    return

            try:
                self._send_or_edit(field, gather_time_limit, get_elapsed_seconds(), activity)
            except Exception as e:
                print(f"Live Gather Report Error: {e}")

            if self.stop_event.wait(self.interval):
                break

    def _send_or_edit(self, field, gather_time_limit, elapsed_seconds, activity="Gathering"):
        embed = self._build_embed(field, gather_time_limit, elapsed_seconds, activity)
        image_bytes = self._capture_honey_pollen()
        if self.route_kind == "bot":
            self._send_or_edit_bot(embed, image_bytes)
        else:
            self._send_or_edit_webhook(embed, image_bytes)

    def _send_or_edit_webhook(self, embed, image_bytes):
        files = {
            "files[0]": ("live_gather_report.png", image_bytes, "image/png"),
        }
        payload = {
            "embeds": [embed],
            "attachments": [{"id": 0, "filename": "live_gather_report.png"}],
        }
        if self.ping_user_id:
            payload["content"] = f"<@{self.ping_user_id}>"

        if self.message_id:
            url = f"https://discord.com/api/webhooks/{self.webhook_id}/{self.webhook_token}/messages/{self.message_id}"
            response = requests.patch(
                url,
                data={"payload_json": json.dumps(payload)},
                files=files,
                timeout=15,
            )
        else:
            url = f"https://discord.com/api/webhooks/{self.webhook_id}/{self.webhook_token}?wait=true"
            response = requests.post(
                url,
                data={"payload_json": json.dumps(payload)},
                files=files,
                timeout=15,
            )

        if response.status_code >= 400:
            raise requests.HTTPError(
                f"{response.status_code} Client Error: {response.text}",
                response=response,
            )
        if not self.message_id:
            try:
                self.message_id = response.json().get("id")
            except Exception:
                self.message_id = None

    def _send_or_edit_bot(self, embed, image_bytes):
        headers = {"Authorization": f"Bot {self.bot_token}"}
        files = {
            "files[0]": ("live_gather_report.png", image_bytes, "image/png"),
        }
        payload = {
            "embeds": [embed],
            "attachments": [{"id": 0, "filename": "live_gather_report.png"}],
        }
        if self.ping_user_id:
            payload["content"] = f"<@{self.ping_user_id}>"

        if self.message_id:
            url = f"https://discord.com/api/channels/{self.channel_id}/messages/{self.message_id}"
            response = requests.patch(
                url,
                headers=headers,
                data={"payload_json": json.dumps(payload)},
                files=files,
                timeout=15,
            )
        else:
            url = f"https://discord.com/api/channels/{self.channel_id}/messages"
            response = requests.post(
                url,
                headers=headers,
                data={"payload_json": json.dumps(payload)},
                files=files,
                timeout=15,
            )

        if response.status_code >= 400:
            raise requests.HTTPError(
                f"{response.status_code} Client Error: {response.text}",
                response=response,
            )
        if not self.message_id:
            try:
                self.message_id = response.json().get("id")
            except Exception:
                self.message_id = None

    def _capture_honey_pollen(self):
        rw = self.roblox_window
        scale_x, scale_y = self._hud_scale()
        capture_w = self._scale_x(self.REFERENCE_CAPTURE[0], scale_x)
        capture_h = self._scale_y(self.REFERENCE_CAPTURE[1], scale_y)
        x = rw.mx + rw.mw // 2 + self._scale_x(self.REFERENCE_CAPTURE_LEFT_OFFSET, scale_x)
        y = rw.my + self._scale_y(rw.yOffset, scale_y)
        img = mssScreenshot(x, y, capture_w, capture_h).convert("RGBA")
        honey = self._crop_hud_card(img, self._scale_box(self.REFERENCE_HUD_CARDS[0], scale_x, scale_y), scale_y)
        pollen = self._crop_hud_card(img, self._scale_box(self.REFERENCE_HUD_CARDS[1], scale_x, scale_y), scale_y)
        stacked = Image.new("RGBA", (max(honey.width, pollen.width), honey.height + pollen.height), (0, 0, 0, 0))
        stacked.paste(honey, (0, 0), honey)
        stacked.paste(pollen, (0, honey.height), pollen)
        out = io.BytesIO()
        stacked.save(out, format="PNG")
        out.seek(0)
        return out.getvalue()

    def _hud_scale(self):
        rw = self.roblox_window
        scale_x = max(0.1, rw.mw / float(self.REFERENCE_WINDOW_WIDTH))
        scale_y = max(0.1, rw.mh / float(self.REFERENCE_WINDOW_HEIGHT))
        return scale_x, scale_y

    @staticmethod
    def _scale_x(value, scale_x):
        return int(round(value * scale_x))

    @staticmethod
    def _scale_y(value, scale_y):
        return int(round(value * scale_y))

    @classmethod
    def _scale_box(cls, box, scale_x, scale_y):
        left, top, right, bottom = box
        scaled = (
            cls._scale_x(left, scale_x),
            cls._scale_y(top, scale_y),
            cls._scale_x(right, scale_x),
            cls._scale_y(bottom, scale_y),
        )
        if scaled[2] <= scaled[0]:
            scaled = (scaled[0], scaled[1], scaled[0] + 1, scaled[3])
        if scaled[3] <= scaled[1]:
            scaled = (scaled[0], scaled[1], scaled[2], scaled[1] + 1)
        return scaled

    def _crop_hud_card(self, img, box, scale_y):
        card = img.crop(box)
        mask = Image.new("L", card.size, 0)
        draw = ImageDraw.Draw(mask)
        radius = max(1, self._scale_y(self.REFERENCE_CARD_RADIUS, scale_y))
        draw.rounded_rectangle((0, 0, card.width - 1, card.height - 1), radius=radius, fill=255)
        card.putalpha(mask)
        return card

    def _build_embed(self, field, gather_time_limit, elapsed_seconds, activity="Gathering"):
        now = time.strftime("%H:%M:%S", time.localtime())
        if self.time_format == 12:
            now = time.strftime("%I:%M:%S %p", time.localtime()).lstrip("0")
        elapsed = self._format_duration(elapsed_seconds)
        field_name = str(field).replace("_", " ").title()
        if activity == "Converting":
            title = f"[{now}] Converting: {elapsed}"
            color = 0xA52A2A
        else:
            title = f"[{now}] Gathering {field_name}: {elapsed}/{gather_time_limit}"
            color = 0x98FB98
        return {
            "title": title,
            "color": color,
            "image": {"url": "attachment://live_gather_report.png"},
        }

    @staticmethod
    def _format_duration(seconds):
        seconds = max(0, int(seconds))
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"
