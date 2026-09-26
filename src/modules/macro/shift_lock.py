from modules.controls.sleep import pause_aware_time as time
from modules.screen.shiftLock import detect_shift_lock, detect_shift_lock_with_retries


class ShiftLockMixin:
    def _detect_shift_lock_state_with_retries(self):
        def detect():
            self.robloxWindow.setRobloxWindowBounds(setYOffset=False)
            return detect_shift_lock(self.robloxWindow)

        return detect_shift_lock_with_retries(detect, sleep=time.sleep)

    def ensure_shift_lock_off(self, reason=""):
        try:
            detection = self._detect_shift_lock_state_with_retries()
        except Exception:
            detection = None

        if not detection or detection.get("state") is None:
            return

        if detection["state"]:
            message = "Shift Lock detected, turning it off"
            if reason:
                message = f"Shift Lock detected during {reason}, turning it off"
            self.logger.webhook("", message, "dark brown")
            self.keyboard.press("shift")
            time.sleep(0.35)
            return True
