import json
import os
import time
from threading import Thread

try:
    from pypresence import Presence
    PYPRESENCE_AVAILABLE = True
except ImportError:
    PYPRESENCE_AVAILABLE = False
    print("pypresence not installed - Discord Rich Presence will not be available")


def withOverrides(activity, overrides):
    """Apply non-None payload overrides; empty small image/text mean "none"."""
    if not overrides:
        return activity
    merged = {**activity, **{k: v for k, v in overrides.items() if v is not None}}
    for key in ("small_image", "small_text"):
        if merged.get(key) == "":
            merged[key] = None
    return merged


class RichPresenceManager:
    """Manages Discord Rich Presence updates based on macro status"""
    
    # Hardcoded Application ID for Fuzzy Macro
    DISCORD_APP_ID = "1468035015194710068"
    
    def __init__(self, status_value, enabled: bool = False, presence_value=None):
        """
        Initialize Rich Presence Manager
        
        Args:
            status_value: Shared multiprocessing.Value containing current macro status
            enabled: Whether Rich Presence is enabled
            presence_value: Optional shared Value for rich presence overrides
        """
        self.application_id = self.DISCORD_APP_ID
        self.status = status_value
        self.presence = presence_value
        self.enabled = enabled
        self.rpc = None
        self.last_activity = ""
        self.connected = False
        self.running = False
        self.thread = None
        self.start_time = int(time.time())
        
        self.map = {}
        try:
            with open(os.path.join(os.path.dirname(__file__), "rich_presence_map.json"), "r") as f:
                self.map = json.load(f)
        except Exception:
            pass

        # Build asset lookup mapping from provided assets and sensible defaults
        asset_mapping = {}
        # Known quest NPCs
        asset_mapping.update({
            "polar_bear": "polar_bear",
            "polar bear": "polar_bear",
            "brown_bear": "brown_bear",
            "brown bear": "brown_bear",
            "black_bear": "black_bear",
            "black bear": "black_bear",
            "honey_bee": "honey_bee",
            "honey bee": "honey_bee",
            "bucko_bee": "bucko_bee",
            "bucko bee": "bucko_bee",
            "riley_bee": "riley_bee",
            "riley bee": "riley_bee",
        })
        # Add assets lists from the map (if present)
        assets_section = self.map.get("assets", {})
        for group, lst in assets_section.items():
            for name in lst:
                key = name.replace(" ", "_")
                asset_mapping[key] = key
                asset_mapping[name] = key

        # Allow optional explicit lookup section
        explicit = self.map.get("asset_lookup", {}) or {}
        for k, v in explicit.items():
            asset_mapping[k] = v

        self.asset_mapping = asset_mapping
        
    def connect(self) -> bool:
        """Initialize Discord RPC connection"""
        if not PYPRESENCE_AVAILABLE:
            return False
            
        try:
            self.rpc = Presence(self.application_id)
            self.rpc.connect()
            self.connected = True
            print("Discord Rich Presence connected")
            return True
        except Exception:
            # Silently fail if Discord client isn't running
            self.connected = False
            return False
    
    def disconnect(self):
        """Close Discord RPC connection"""
        if not (self.rpc and self.connected):
            return
        # clear first so Discord doesn't show a lingering status
        for close in ("clear", "close"):
            try:
                getattr(self.rpc, close)()
            except Exception:
                pass
        self.connected = False
        self.rpc = None
        print("Discord Rich Presence disconnected")

    def parse_activity(self, status_str: str) -> dict:
        """Parse status string into Rich Presence data"""
        payload_overrides = {}
        if isinstance(status_str, str) and status_str.startswith("rp:"):
            try:
                payload = json.loads(status_str[3:])
            except Exception:
                payload = {}
            for key in ("state", "details", "large_image", "large_text", "small_image", "small_text"):
                if key in payload:
                    payload_overrides[key] = payload[key]
            status_str = payload.get("activity") or payload.get("status") or payload.get("key")
            task = payload.get("task")
            field = payload.get("field")
            if not status_str and task:
                if field:
                    field_key = str(field).replace(" ", "_").lower()
                    status_str = f"{task}_{field_key}"
                else:
                    status_str = str(task)

        # Treat empty, whitespace-only, or explicit 'none' values as idle
        if not status_str or (isinstance(status_str, str) and status_str.strip().lower() in ("", "none")):
            status_str = "idle_main_menu"
        
        status_lower = str(status_str).lower()

        # exact matches from map (use lowercase keys for safety)
        exact = {k.lower(): v for k, v in self.map.get("exact", {}).items()}
        if status_lower in exact:
            return withOverrides(exact[status_lower], payload_overrides)

        # prefix matches
        for pfx, data in self.map.get("prefix", {}).items():
            if status_lower.startswith(pfx.lower()):
                key = status_lower[len(pfx):]
                field = key.replace("_", " ").title()
                payload = dict(data)
                # substitute placeholders
                payload["state"] = payload["state"].replace("{field}", field).replace("{key}", key)
                payload["details"] = payload.get("details", "").replace("{field}", field).replace("{key}", key)
                payload["small_text"] = payload.get("small_text", "").replace("{field}", field).replace("{key}", key)
                small_image = payload.get("small_image") or ""
                small_image = small_image.replace("{asset}", self.asset_mapping.get(key) or key).replace("{key}", key)
                payload["small_image"] = small_image or None
                return withOverrides(payload, payload_overrides)

        # contains rules - checked in map order
        for substring, data in self.map.get("contains", {}).items():
            if substring in status_lower:
                return withOverrides(data, payload_overrides)

        if self.map.get("default"):
            return withOverrides(self.map["default"], payload_overrides)

        # final fallback if no map is loaded
        return withOverrides({
            "state": str(status_str).replace("_", " ").title(),
            "details": "Macro active",
            "large_image": "fuzzy_macro",
            "large_text": "Fuzzy Macro",
            "small_image": None,
            "small_text": None,
        }, payload_overrides)

    def update_presence(self, activity_data: dict):
        """Update Discord Rich Presence with new activity data"""
        if not self.connected or not self.rpc:
            return
        
        try:
            # Build presence payload
            payload = {
                "state": activity_data["state"],
                "details": activity_data["details"],
                "large_image": activity_data["large_image"],
                "large_text": activity_data["large_text"],
                "start": self.start_time,
            }
            
            # Add small image if available
            if activity_data["small_image"]:
                payload["small_image"] = activity_data["small_image"]
                payload["small_text"] = activity_data["small_text"]
            
            self.rpc.update(**payload)
        except Exception:
            # Silently handle errors (e.g., Discord closed)
            self.connected = False
    
    def update_loop(self):
        """Background thread to monitor status and update RPC"""
        while self.running:
            try:
                # Check if enabled
                if not self.enabled:
                    if self.connected:
                        self.disconnect()
                    time.sleep(2)
                    continue
                
                # Try to connect if not connected
                if not self.connected:
                    self.connect()
                    time.sleep(2)
                    continue
                
                # Get current status (presence overrides status when available)
                presence_status = ""
                if self.presence is not None:
                    try:
                        presence_status = self.presence.value
                    except Exception:
                        presence_status = ""

                if presence_status and str(presence_status).strip().lower() not in ("", "none"):
                    current_status = presence_status
                else:
                    current_status = self.status.value
                
                # Update if status changed
                if current_status != self.last_activity:
                    activity_data = self.parse_activity(current_status)
                    self.update_presence(activity_data)
                    self.last_activity = current_status
                
                time.sleep(1)  # Check every second
            except Exception:
                # Silently handle any errors
                time.sleep(2)
    
    def start(self):
        """Start the Rich Presence update thread"""
        if self.running:
            return
        
        if not PYPRESENCE_AVAILABLE:
            return
        
        self.running = True
        self.thread = Thread(target=self.update_loop, daemon=True)
        self.thread.start()
    
    def stop(self):
        """Stop the Rich Presence update thread"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        # Disconnect and give Discord a moment to clear presence
        self.disconnect()
        time.sleep(0.2)

    def set_enabled(self, enabled: bool):
        """Enable or disable Rich Presence"""
        self.enabled = enabled
        if not enabled and self.connected:
            self.disconnect()
