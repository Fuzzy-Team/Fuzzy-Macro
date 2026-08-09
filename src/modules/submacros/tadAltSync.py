import json
import threading
import time
import urllib.request


class TadAltSync:
    """Synchronize Discord-remote-controlled TAD alt macros with field boosts."""

    def __init__(self, settings, logger=None):
        self.settings = settings
        self.logger = logger
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

    def _change_field(self, webhooks, field):
        failures = self._send_all(webhooks, "?stop")
        time.sleep(max(0, float(self.settings.get("tad_alt_restart_delay", 10) or 0)))
        failures.extend(self._send_all(webhooks, f"?set FieldName1 {field.title()}"))
        time.sleep(2)
        failures.extend(self._send_all(webhooks, "?start"))
        return sorted(set(failures))

    def initialize_alts(self):
        """Start enabled alts in the configured default field."""
        webhooks = self._enabled_webhooks()
        if not webhooks:
            return False
        default_field = str(self.settings.get("tad_alt_default_field", "pine tree") or "pine tree").strip()
        failures = self._change_field(webhooks, default_field)
        if failures:
            self._log("TAD Alt Sync", f"Could not initialize TAD alt(s): {', '.join(map(str, failures))}", "red")
        else:
            self._log("TAD Alt Sync", f"TAD alt(s) started in {default_field.title()}", "bright green")
        return not failures

    def sync_to_boost(self, field):
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
        thread = threading.Thread(
            target=self._restore_after_boost,
            args=(generation, duration),
            name="tad-alt-sync-restore",
            daemon=True,
        )
        thread.start()
        return True

    def _restore_after_boost(self, generation, duration):
        time.sleep(duration)
        with self._lock:
            if generation != self._generation:
                return

        webhooks = self._enabled_webhooks()
        if not webhooks:
            return
        default_field = str(self.settings.get("tad_alt_default_field", "pine tree") or "pine tree").strip()
        failures = self._change_field(webhooks, default_field)
        if failures:
            self._log("TAD Alt Sync", f"Could not restore TAD alt(s): {', '.join(map(str, failures))}", "red")
        else:
            self._log("TAD Alt Sync", f"TAD alt(s) returned to {default_field.title()}", "bright green")
