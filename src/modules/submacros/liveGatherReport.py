import io
import json
import re
import threading
import time

import requests

from modules.screen.screenshot import mssScreenshot


class LiveGatherReport:
    def __init__(self, webhook_url, roblox_window, interval=15, time_format=24):
        self.webhook_url = webhook_url
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

    def start(self, field, gather_time_limit, get_elapsed_seconds, is_paused=None):
        if not self.webhook_id or not self.webhook_token:
            return
        if self.thread and self.thread.is_alive():
            return
        self.stop_event.clear()
        self.thread = threading.Thread(
            target=self._run,
            args=(field, gather_time_limit, get_elapsed_seconds, is_paused),
            daemon=True,
        )
        self.thread.start()

    def stop(self):
        self.stop_event.set()

    def _run(self, field, gather_time_limit, get_elapsed_seconds, is_paused=None):
        while not self.stop_event.is_set():
            while is_paused and is_paused():
                if self.stop_event.wait(0.1):
                    return

            try:
                self._send_or_edit(field, gather_time_limit, get_elapsed_seconds())
            except Exception as e:
                print(f"Live Gather Report Error: {e}")

            if self.stop_event.wait(self.interval):
                break

    def _send_or_edit(self, field, gather_time_limit, elapsed_seconds):
        embed = self._build_embed(field, gather_time_limit, elapsed_seconds)
        image_bytes = self._capture_honey_pollen()
        files = {
            "files[0]": ("live_gather_report.png", image_bytes, "image/png"),
        }
        payload = {
            "embeds": [embed],
            "attachments": [{"id": 0, "filename": "live_gather_report.png"}],
        }

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

    def _capture_honey_pollen(self):
        rw = self.roblox_window
        x = rw.mx + rw.mw // 2 - 320
        y = rw.my + rw.yOffset
        img = mssScreenshot(x, y, 650, 100)
        out = io.BytesIO()
        img.save(out, format="PNG")
        out.seek(0)
        return out.getvalue()

    def _build_embed(self, field, gather_time_limit, elapsed_seconds):
        now = time.strftime("%H:%M:%S", time.localtime())
        if self.time_format == 12:
            now = time.strftime("%I:%M:%S %p", time.localtime()).lstrip("0")
        elapsed = self._format_duration(elapsed_seconds)
        field_name = str(field).replace("_", " ").title()
        return {
            "title": f"[{now}] Gathering {field_name}: {elapsed}/{gather_time_limit}",
            "color": 0x98FB98,
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
