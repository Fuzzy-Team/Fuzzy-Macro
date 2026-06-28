import time as timeModule
import threading
import queue
from modules.screen.screenshot import mssScreenshot
import modules.logging.webhook as logWebhook
import mss
import mss.darwin
mss.darwin.IMAGE_OPTIONS = 0
from modules.screen.robloxWindow import RobloxWindowBounds

colors = {
    "red": "D22B2B",
    "light blue": "89CFF0",
    "blue": "89CFF0",
    "bright green": "7CFC00",
    "light green": "98FB98",
    "dark brown": "5C4033",
    "brown": "D27D2D",
    "purple": "954cf5",
    "orange": "FFA500",
    "white": "FFFFFF",
    "yellow": "FFFF00",
}
newUI = False

PING_CATEGORY_ROUTES = {
    "ping_critical_errors": "critical_errors",
    "ping_disconnects": "disconnects",
    "ping_character_deaths": "character_deaths",
    "ping_vicious_bee": "combat",
    "ping_mondo_buff": "activities",
    "ping_ant_challenge": "activities",
    "ping_sticker_events": "activities",
    "ping_mob_events": "combat",
    "ping_conversion_events": "activities",
    "ping_hourly_reports": "reports",
    "ping_guiding_star": "activities",
    "ping_unusual_sprouts": "activities",
}

ALLOWED_PING_KEYS = {
    "ping_critical_errors",
    "ping_disconnects",
    "ping_character_deaths",
    "ping_hourly_reports",
    "ping_unusual_sprouts",
}

ROUTE_FALLBACKS = {
    "reports": ["hourly_reports", "final_reports", "default"],
    "gathering": ["live_gather_report", "default"],
    "combat": ["mob_events", "vicious_bee", "character_deaths", "default"],
    "activities": ["boosts", "crafting", "sticker_events", "ant_challenge", "mondo_buff", "conversion_events", "planters", "collectibles", "quests", "guiding_star", "default"],
    "system": ["critical_errors", "disconnects", "stream", "default"],
    "live_gather_report": ["gathering", "default"],
    "hourly_reports": ["reports", "default"],
    "final_reports": ["reports", "default"],
    "critical_errors": ["system", "default"],
    "disconnects": ["system", "default"],
    "stream": ["system", "default"],
    "character_deaths": ["combat", "default"],
    "vicious_bee": ["combat", "default"],
    "mob_events": ["combat", "default"],
    "mondo_buff": ["activities", "default"],
    "ant_challenge": ["activities", "default"],
    "sticker_events": ["activities", "default"],
    "conversion_events": ["activities", "default"],
    "planters": ["activities", "default"],
    "collectibles": ["activities", "default"],
    "quests": ["activities", "default"],
    "boosts": ["activities", "default"],
    "crafting": ["activities", "default"],
    "guiding_star": ["activities", "default"],
    "unusual_sprouts": ["activities", "default"],
}

ROUTE_CATEGORIES = [
    "default",
    "macro_status",
    "reports",
    "gathering",
    "combat",
    "activities",
    "system",
    "live_gather_report",
    "hourly_reports",
    "final_reports",
    "critical_errors",
    "disconnects",
    "character_deaths",
    "vicious_bee",
    "mob_events",
    "mondo_buff",
    "ant_challenge",
    "sticker_events",
    "conversion_events",
    "planters",
    "collectibles",
    "quests",
    "boosts",
    "crafting",
    "guiding_star",
    "unusual_sprouts",
    "stream",
]


def normalize_route_category(category):
    if not category:
        return None
    category = str(category).strip()
    if category in PING_CATEGORY_ROUTES:
        return PING_CATEGORY_ROUTES[category]
    if category.startswith("ping_"):
        category = category[5:]
    return category.replace("-", "_").replace(" ", "_")


def route_type(route):
    route = str(route or "").strip()
    if route.startswith("https://"):
        return "webhook"
    if route.isdigit():
        return "bot"
    return None


def infer_route_category(title, desc=""):
    text = f"{title or ''} {desc or ''}".lower()
    if "hourly report" in text:
        return "reports"
    if "session complete" in text or "final report" in text:
        return "reports"
    if "gathering:" in text or "walking back to hive" in text:
        return "gathering"
    if "macro started" in text or "macro stopped" in text or "macro paused" in text or "macro resumed" in text:
        return "macro_status"
    if "stream" in text:
        return "system"
    if "planter" in text:
        return "activities"
    if "quest" in text:
        return "activities"
    if "boost" in text or "afb" in text:
        return "activities"
    if "blender" in text or "crafted:" in text or "craft" in text:
        return "activities"
    if "collecting:" in text or "collected:" in text or "claimed" in text:
        return "activities"
    return "default"


def build_route_settings(settings):
    settings = settings or {}
    return {category: settings.get(f"route_{category}", "") for category in ROUTE_CATEGORIES}


def get_delivery_mode(settings):
    settings = settings or {}
    mode = str(settings.get("discord_delivery_mode", "") or "").strip().lower().replace("-", "_").replace(" ", "_")
    if mode in ("both", "webhook", "discord_bot"):
        return mode
    enable_webhook = settings.get("enable_webhook", False)
    enable_bot = settings.get("discord_bot", False)
    if enable_webhook and enable_bot:
        return "both"
    if enable_bot:
        return "discord_bot"
    if enable_webhook:
        return "webhook"
    return "both"


def delivery_uses_webhook(settings):
    return get_delivery_mode(settings) in ("both", "webhook")


def delivery_uses_bot_commands(settings):
    return get_delivery_mode(settings) in ("both", "discord_bot")


def delivery_uses_bot_messages(settings):
    return get_delivery_mode(settings) == "discord_bot"


def get_default_delivery_route(settings):
    settings = settings or {}
    if delivery_uses_bot_messages(settings):
        return settings.get("discord_channel_id", "")
    return settings.get("webhook_link", "")


def resolve_route(route_settings, category, legacy_webhook_url=""):
    route_settings = route_settings or {}
    category = normalize_route_category(category) or "default"
    candidates = [category] + ROUTE_FALLBACKS.get(category, ["default"])
    for candidate in candidates:
        route = str(route_settings.get(candidate, "") or "").strip()
        if route:
            return route, candidate, route_type(route)
    legacy = str(legacy_webhook_url or "").strip()
    if legacy:
        return legacy, "default", route_type(legacy)
    return "", category, None


def resolve_webhook_route(route_settings, category, legacy_webhook_url=""):
    route_settings = route_settings or {}
    category = normalize_route_category(category) or "default"
    candidates = [category] + ROUTE_FALLBACKS.get(category, ["default"])
    for candidate in candidates:
        route = str(route_settings.get(candidate, "") or "").strip()
        if route_type(route) == "webhook":
            return route, candidate, "webhook"
    legacy = str(legacy_webhook_url or "").strip()
    if route_type(legacy) == "webhook":
        return legacy, "default", "webhook"
    return "", category, None


def resolve_bot_route(route_settings, category, legacy_route=""):
    route_settings = route_settings or {}
    category = normalize_route_category(category) or "default"
    candidates = [category] + ROUTE_FALLBACKS.get(category, ["default"])
    for candidate in candidates:
        route = str(route_settings.get(candidate, "") or "").strip()
        if route_type(route) == "bot":
            return route, candidate, "bot"
    legacy = str(legacy_route or "").strip()
    if route_type(legacy) == "bot":
        return legacy, "default", "bot"
    return "", category, None


class webhookQueue:
    def __init__(self):
        self.queue = queue.Queue()
        self.worker_thread = threading.Thread(target=self._process_queue, daemon=True)
        self.worker_thread.start()

    def _process_queue(self):
        while True:
            # Wait for a message from the queue
            data = self.queue.get()
            if data is None:
                print("Webhook queue stopped.")
                break
            # Send the webhook
            logWebhook.webhook(**data)
            self.queue.task_done()

    def add_to_queue(self, data):
        self.queue.put(data)

class log:
    def __init__(self, logQueue, enableWebhook, webhookURL, sendScreenshots, hourlyReportOnly=False, blocking=False, robloxWindow: RobloxWindowBounds = None, enableDiscordPing=False, discordUserID=None, pingSettings=None, webhookTimeFormat=24, enableDiscordBot=False, discordMessageQueue=None, routeSettings=None):
        self.logQueue = logQueue
        self.webhookURL = webhookURL
        self.enableWebhook = enableWebhook
        self.enableDiscordBot = enableDiscordBot
        self.discordMessageQueue = discordMessageQueue
        self.routeSettings = routeSettings or {}
        self.blocking = blocking
        self.hourlyReportOnly = hourlyReportOnly
        self.robloxWindow = robloxWindow
        self.sendScreenshots = sendScreenshots
        self.enableDiscordPing = enableDiscordPing
        self.discordUserID = discordUserID
        self.pingSettings = pingSettings or {}
        self.webhookTimeFormat = webhookTimeFormat

        if not self.blocking:
            self.webhookQueue = webhookQueue()

    def log(self, msg):
        # Display in GUI or macro logs (to be implemented)
        pass

    def update_routes_from_settings(self, settings):
        settings = settings or {}
        self.routeSettings = build_route_settings(settings)
        self.webhookURL = get_default_delivery_route(settings)
        self.enableWebhook = delivery_uses_webhook(settings)
        self.enableDiscordBot = delivery_uses_bot_messages(settings)

    def _capture_image(self, ss=None, imagePath=None):
        if not self.sendScreenshots:
            return None
        if imagePath:
            return imagePath
        if not ss:
            return None

        webhookImgPath = "webhookScreenshot.png"
        if self.robloxWindow:
            robloxWindow = self.robloxWindow
        else:
            print("new window bounds")
            robloxWindow = RobloxWindowBounds()
            robloxWindow.setRobloxWindowBounds()

        screenshotRegions = {
            "screen": (robloxWindow.mx, robloxWindow.my, robloxWindow.mw, robloxWindow.mh),
            "honey-pollen": (robloxWindow.mx+robloxWindow.mw//2-320, robloxWindow.my+robloxWindow.yOffset, 650, 40),
            "sticker": (robloxWindow.mx+200, robloxWindow.my+70, 376, 225),
            "blue": (robloxWindow.mx+robloxWindow.mw*3/4, robloxWindow.my+robloxWindow.mh*2/3, robloxWindow.mw//4, robloxWindow.mh//3),
        }
        if ss not in screenshotRegions:
            return None
        print(screenshotRegions["screen"])

        for _ in range(2):
            try:
                mssScreenshot(*screenshotRegions[ss], save=True, filename=webhookImgPath)
                return webhookImgPath
            except mss.exception.ScreenShotError:
                timeModule.sleep(0.5)
        return None

    def _ping_user_id(self, route_category, ping_category=None):
        ping_key = ping_category
        if not ping_key:
            ping_key = f"ping_{normalize_route_category(route_category)}"
        if ping_key not in ALLOWED_PING_KEYS:
            return None
        if self.discordUserID and self.pingSettings.get(ping_key, False):
            return self.discordUserID
        return None

    def _send_discord_bot(self, channel_id, title, desc, time, color, imagePath=None, ping_user_id=None, time_format=None, fields=None):
        if not self.enableDiscordBot or not self.discordMessageQueue:
            return None
        data = {
            "channel_id": str(channel_id),
            "title": title,
            "desc": desc,
            "time": time,
            "color": color,
            "imagePath": imagePath,
            "ping_user_id": ping_user_id,
            "time_format": time_format if time_format is not None else self.webhookTimeFormat,
            "fields": fields,
        }
        try:
            self.discordMessageQueue.put(data)
        except Exception as e:
            print(f"Discord bot queue error: {e}")
        return None

    def _deliver(self, title, desc, color, imagePath=None, ping_category=None, route_category=None, time_format=None, allow_hourly_only_filter=True, fields=None):
        if allow_hourly_only_filter and self.hourlyReportOnly:
            return

        time = timeModule.strftime("%H:%M:%S", timeModule.localtime())
        category = normalize_route_category(route_category) or normalize_route_category(ping_category) or infer_route_category(title, desc)
        if self.enableWebhook and not self.enableDiscordBot:
            route, resolved_category, resolved_type = resolve_webhook_route(self.routeSettings, category, self.webhookURL)
        elif self.enableDiscordBot and not self.enableWebhook:
            route, resolved_category, resolved_type = resolve_route(self.routeSettings, category, "")
            if not route:
                route, resolved_category, resolved_type = resolve_bot_route(self.routeSettings, category, self.webhookURL)
        else:
            route, resolved_category, resolved_type = resolve_route(self.routeSettings, category, "")
            if not route:
                route, resolved_category, resolved_type = resolve_webhook_route(self.routeSettings, category, self.webhookURL)
        ping_user_id = self._ping_user_id(resolved_category, ping_category)
        time_format = time_format if time_format is not None else self.webhookTimeFormat

        if not route:
            print(f"Warning: No Discord route configured. Skipping message: {title} {desc}")
            return
        if resolved_type == "webhook":
            if not self.enableWebhook and not self.enableDiscordBot:
                return
            webhookData = {
                "url": route,
                "title": title,
                "desc": desc,
                "time": time,
                "color": colors[color],
                "imagePath": imagePath,
                "ping_user_id": ping_user_id,
                "time_format": time_format,
                "fields": fields,
            }
            if self.blocking:
                logWebhook.webhook(**webhookData)
            else:
                self.webhookQueue.add_to_queue(webhookData)
            return
        if resolved_type == "bot":
            self._send_discord_bot(route, title, desc, time, colors[color], imagePath, ping_user_id, time_format, fields)
            return
        print(f"Warning: Invalid Discord route '{route}'. Expected https:// webhook or numeric channel ID.")

    def webhook(self, title, desc, color, ss=None, imagePath=None, ping_category=None, route_category=None):
        # Update logs
        time = timeModule.strftime("%H:%M:%S", timeModule.localtime())
        logData = {
            "type": "webhook",
            "time": time,
            "title": title,
            "desc": desc,
            "color": colors[color]
        }
        self.logQueue.put(logData)

        print(f"[{time}] {title} {desc}")

        webhookImgPath = self._capture_image(ss, imagePath)
        self._deliver(title, desc, color, webhookImgPath, ping_category, route_category, self.webhookTimeFormat)

    def hourlyReport(self, title, desc, color, time_format=None, fields=None):
        self._deliver(title, desc, color, "hourlyReport.png", "ping_hourly_reports", "reports", time_format, allow_hourly_only_filter=False, fields=fields)
    
    def finalReport(self, title, desc, color, time_format=None, fields=None):
        self._deliver(title, desc, color, "finalReport.png", "ping_hourly_reports", "reports", time_format, allow_hourly_only_filter=False, fields=fields)
