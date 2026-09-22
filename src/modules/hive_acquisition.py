"""Hive Acquisition policy with detection first and slot checking as fallback."""

from dataclasses import dataclass


def confirm_claim(press_claim, claim_prompt_visible, control_status, wait, attempts=2, checks_per_attempt=20):
    """Press claim and confirm acceptance by observing the prompt disappear."""
    for _ in range(attempts):
        if control_status() == "stopped":
            return False
        press_claim()
        for _ in range(checks_per_attempt):
            if control_status() == "stopped":
                return False
            if not claim_prompt_visible():
                return True
            wait(0.05)
    return False


@dataclass(frozen=True)
class HiveAcquisitionResult:
    claimed: bool
    slot: int = 0
    reason: str = ""
    attempted_slots: tuple = ()
    detection_error: str = ""


class HiveAcquisition:
    """Owns strategy order and the observable result of Hive Acquisition."""

    def __init__(self, detect, check, control_status=lambda: "running", fatal_exceptions=()):
        self._detect = detect
        self._check = check
        self._control_status = control_status
        self._fatal_exceptions = fatal_exceptions

    def acquire(self, preferred_slot, excluded_slots=None):
        preferred_slot = max(1, min(6, int(preferred_slot)))
        excluded_slots = set(excluded_slots or set())
        attempted = []

        if self._control_status() == "stopped":
            return HiveAcquisitionResult(False, reason="stopped")

        detection_error = ""
        try:
            slot = int(self._detect(preferred_slot, excluded_slots) or 0)
            attempted.append(preferred_slot)
            if slot:
                return HiveAcquisitionResult(True, slot, "claimed", tuple(dict.fromkeys(attempted + [slot])))
        except self._fatal_exceptions:
            raise
        except Exception as exc:
            detection_error = str(exc)

        if self._control_status() == "stopped":
            return HiveAcquisitionResult(
                False,
                reason="stopped",
                attempted_slots=tuple(dict.fromkeys(attempted)),
                detection_error=detection_error,
            )

        try:
            slot = int(self._check(preferred_slot, excluded_slots) or 0)
            attempted.append(preferred_slot)
            if slot:
                return HiveAcquisitionResult(
                    True,
                    slot,
                    "claimed_by_fallback",
                    tuple(dict.fromkeys(attempted + [slot])),
                    detection_error,
                )
        except self._fatal_exceptions:
            raise
        except Exception as exc:
            reason = "check_error"
            if detection_error:
                reason = "detection_and_check_error"
            return HiveAcquisitionResult(
                False,
                reason=reason,
                attempted_slots=tuple(dict.fromkeys(attempted)),
                detection_error=detection_error or str(exc),
            )

        return HiveAcquisitionResult(
            False,
            reason="no_claimable_hive",
            attempted_slots=tuple(dict.fromkeys(attempted)),
            detection_error=detection_error,
        )
