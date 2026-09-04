import json
import threading
import time
import urllib.request


class TadAltSync:
    """Synchronize Discord-remote-controlled TAD alt macros with field boosts."""

    def __init__(self, settings, logger=None, use_glitter=None):
        self.settings = settings
        self.logger = logger
        self.use_glitter = use_glitter
        self._generation = 0
        self._lock = threading.Lock()

    def update_settings(self, settings):
        self.settings = settings

    def _enabled_webhooks(self):
        if not self.settings.get("tad_alt_sync_enabled", False):
            return []
        webhooks = []
        for number in (1, 2):
            if not self.settings.get(f"tad_alt_{number}_enabled", False):
                continue
            url = str(self.settings.get(f"tad_alt_{number}_webhook", "") or "").strip()
            if url:
                webhooks.append((number, url))
        return webhooks

    @staticmethod
    def _post_command(url, command):
        body = json.dumps({"content": command}).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json", "User-Agent": "Fuzzy-Macro-TAD-Alt-Sync"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            response.read()

    def _send_all(self, webhooks, command):
        failures = []
        for number, url in webhooks:
            try:
                self._post_command(url, command)
            except Exception:
                failures.append(number)
        return failures

    def _log(self, title, description, color):
        if self.logger is not None:
            self.logger.webhook(title, description, color, route_category="boosts")

    def _default_gather_settings(self):
        return {
            "shape": str(self.settings.get("tad_alt_gather_shape", "e_lol") or "e_lol"),
            "size": str(self.settings.get("tad_alt_gather_size", "m") or "m").lower(),
            "width": int(self.settings.get("tad_alt_gather_width", 5) or 5),
            "shift_lock": bool(self.settings.get("tad_alt_gather_shift_lock", False)),
            "field_drift_compensation": bool(self.settings.get("tad_alt_gather_drift_compensation", False)),
            "invert_lr": bool(self.settings.get("tad_alt_gather_invert_lr", False)),
            "invert_fb": bool(self.settings.get("tad_alt_gather_invert_fb", False)),
            "turn": str(self.settings.get("tad_alt_gather_turn", "none") or "none").lower(),
            "turn_times": int(self.settings.get("tad_alt_gather_turn_times", 1) or 1),
            "start_location": str(self.settings.get("tad_alt_gather_start_location", "center") or "center").lower(),
            "distance": int(self.settings.get("tad_alt_gather_distance", 1) or 1),
            "goo": bool(self.settings.get("tad_alt_gather_goo", False)),
            "goo_interval": int(self.settings.get("tad_alt_gather_goo_interval", 3) or 3),
        }

    def _change_field(self, webhooks, field, apply_default_settings=False):
        field = " ".join(str(field or "").replace("_", " ").split())
        failures = self._send_all(webhooks, "?stop")
        time.sleep(max(0, float(self.settings.get("tad_alt_restart_delay", 10) or 0)))
        failures.extend(self._send_all(webhooks, f"?set FieldName1 {field.title()}"))
        if apply_default_settings:
            payload = json.dumps(self._default_gather_settings(), separators=(",", ":"))
            failures.extend(self._send_all(webhooks, f"?set AltGatherSettings {payload}"))
        time.sleep(2)
        failures.extend(self._send_all(webhooks, "?start"))
        return sorted(set(failures))

    def initialize_alts(self):
        """Schedule enabled alts to start without blocking host startup."""
        webhooks = self._enabled_webhooks()
        if not webhooks:
            return False
        default_field = str(self.settings.get("tad_alt_default_field", "pine tree") or "pine tree").strip()
        thread = threading.Thread(
            target=self._initialize_alts,
            args=(webhooks, default_field),
            name="tad-alt-sync-initialize",
            daemon=True,
        )
        thread.start()
        return True

    def _initialize_alts(self, webhooks, default_field):
        try:
            failures = self._change_field(webhooks, default_field, apply_default_settings=True)
            if failures:
                self._log("TAD Alt Sync", f"Could not initialize TAD alt(s): {', '.join(map(str, failures))}", "red")
            else:
                self._log("TAD Alt Sync", f"TAD alt(s) started in {default_field.title()}", "bright green")
        except Exception:
            self._log("TAD Alt Sync", "Could not initialize TAD alt(s)", "red")

    def sync_to_boost(self, field, extend_with_glitter=None, extension_duration=0):
        webhooks = self._enabled_webhooks()
        field = str(field or "").strip().lower()
        if not webhooks or not field:
            return False

        with self._lock:
            self._generation += 1
            generation = self._generation

        failures = self._change_field(webhooks, field)
        if failures:
            self._log("TAD Alt Sync", f"Could not update TAD alt(s): {', '.join(map(str, failures))}", "red")
        else:
            self._log("TAD Alt Sync", f"TAD alt(s) moved to {field.title()}", "bright green")

        duration = max(0, float(self.settings.get("tad_alt_boost_duration", 900) or 0))
        if extend_with_glitter is None:
            extend_with_glitter = bool(self.settings.get("tad_alt_glitter_extend_enabled", False))
        glitter_slot = min(7, max(0, int(self.settings.get("tad_alt_glitter_slot", 1) or 0)))
        thread = threading.Thread(
            target=self._restore_after_boost,
            args=(generation, duration, extend_with_glitter, glitter_slot, extension_duration),
            name="tad-alt-sync-restore",
            daemon=True,
        )
        thread.start()
        return True

    def _restore_after_boost(self, generation, duration, extend_with_glitter=False, glitter_slot=1, extension_duration=0):
        glitter_used = False
        if extend_with_glitter and self.use_glitter is not None:
            time.sleep(max(0, duration - 5))
            with self._lock:
                if generation != self._generation:
                    return
            try:
                self.use_glitter(glitter_slot)
                glitter_used = True
                self._log(
                    "TAD Alt Sync",
                    f"Used Glitter from hotbar slot {glitter_slot}; extending the alt boost assignment",
                    "bright green",
                )
            except Exception:
                self._log("TAD Alt Sync", "Could not use Glitter; using the normal boost duration", "red")
            time.sleep(duration + 5 if glitter_used else min(5, duration))
        else:
            time.sleep(duration + max(0, extension_duration))
        with self._lock:
            if generation != self._generation:
                return

        webhooks = self._enabled_webhooks()
        if not webhooks:
            return
        default_field = str(self.settings.get("tad_alt_default_field", "pine tree") or "pine tree").strip()
        failures = self._change_field(webhooks, default_field, apply_default_settings=True)
        if failures:
            self._log("TAD Alt Sync", f"Could not restore TAD alt(s): {', '.join(map(str, failures))}", "red")
        else:
            self._log("TAD Alt Sync", f"TAD alt(s) returned to {default_field.title()}", "bright green")
