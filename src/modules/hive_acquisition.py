"""Hive claiming: the claim confirmation and the order of the claim methods."""


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


def acquire_hive(method, preferred_slot, excluded_slots, detect, check, stopped, fatal_exceptions=()):
    """Claim a hive and return (slot, reason); slot is 0 when no hive was claimed.

    "check" walks from spawn to the preferred pad and scans from there. "detect" reads open
    pads from spawn first and falls back to checking when it found nothing from spawn (it
    returns None) or raised; when it returns 0 it already walked the hive row.
    """
    if stopped():
        return 0, "stopped"
    detection_error = ""
    if method != "check":
        try:
            detected = detect(preferred_slot, excluded_slots)
        except fatal_exceptions:
            raise
        except Exception as exc:
            detected, detection_error = None, f"; detection: {exc}"
        if detected:
            return int(detected), "claimed"
        if stopped():
            return 0, "stopped"
        if detected is not None:
            return 0, "no_claimable_hive"
    try:
        slot = int(check(preferred_slot, excluded_slots) or 0)
    except fatal_exceptions:
        raise
    except Exception as exc:
        return 0, f"check_error: {exc}{detection_error}"
    return (slot, "claimed") if slot else (0, "no_claimable_hive" + detection_error)
