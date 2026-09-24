"""Hive Acquisition policy with detection first and slot checking as fallback."""

from dataclasses import dataclass


def confirm_claim(press_claim, claim_prompt_visible, control_status, wait, attempts=2, checks_per_attempt=20, required_misses=3):
    """Press claim and confirm acceptance by observing the prompt disappear."""
    for _ in range(attempts):
        if control_status() == "stopped":
            return False
        press_claim()
        misses = 0
        for _ in range(checks_per_attempt):
            if control_status() == "stopped":
                return False
            if claim_prompt_visible():
                misses = 0
            else:
                misses += 1
                if misses >= required_misses:
                    return True
            wait(0.05)
    return False


@dataclass(frozen=True)
class HiveAcquisitionResult:
    claimed: bool
    slot: int = 0
    reason: str = ""
    detection_error: str = ""


class HiveAcquisition:
    """Owns strategy order and the observable result of Hive Acquisition."""

    def __init__(self, detect, check, control_status=lambda: "running", fatal_exceptions=()):
        """`detect` returns the claimed slot, 0 if it walked the hive row without a claim,
        or None if it found nothing from spawn. `check` walks from spawn, so it only runs
        while the player is still there (None) or detection raised."""
        self._detect = detect
        self._check = check
        self._control_status = control_status
        self._fatal_exceptions = fatal_exceptions

    def acquire(self, preferred_slot, excluded_slots=None):
        preferred_slot = max(1, min(6, int(preferred_slot)))
        excluded_slots = set(excluded_slots or set())

        if self._control_status() == "stopped":
            return HiveAcquisitionResult(False, reason="stopped")

        detection_error = ""
        detected = None
        try:
            detected = self._detect(preferred_slot, excluded_slots)
            if detected:
                return HiveAcquisitionResult(True, int(detected), "claimed")
        except self._fatal_exceptions:
            raise
        except Exception as exc:
            detection_error = str(exc)

        if self._control_status() == "stopped":
            return HiveAcquisitionResult(False, reason="stopped", detection_error=detection_error)

        if detected is not None:
            # Detection already walked to its pads and checked the rest of the row.
            return HiveAcquisitionResult(False, reason="no_claimable_hive")

        try:
            slot = int(self._check(preferred_slot, excluded_slots) or 0)
        except self._fatal_exceptions:
            raise
        except Exception as exc:
            reason = "detection_and_check_error" if detection_error else "check_error"
            return HiveAcquisitionResult(False, reason=reason, detection_error=detection_error or str(exc))

        if slot:
            return HiveAcquisitionResult(True, slot, "claimed_by_fallback", detection_error)
        return HiveAcquisitionResult(False, reason="no_claimable_hive", detection_error=detection_error)
