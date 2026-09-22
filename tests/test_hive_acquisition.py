import unittest

from src.modules.hive_acquisition import HiveAcquisition, confirm_claim


class HiveAcquisitionTests(unittest.TestCase):
    def test_detection_success_does_not_run_fallback(self):
        calls = []
        acquisition = HiveAcquisition(
            detect=lambda preferred, excluded: calls.append(("detect", preferred, excluded)) or 2,
            check=lambda preferred, excluded: calls.append(("check", preferred, excluded)) or 3,
        )
        result = acquisition.acquire(2, {5})
        self.assertTrue(result.claimed)
        self.assertEqual(result.slot, 2)
        self.assertEqual(calls, [("detect", 2, {5})])

    def test_check_runs_when_detection_fails(self):
        calls = []
        acquisition = HiveAcquisition(
            detect=lambda preferred, excluded: calls.append("detect") or 0,
            check=lambda preferred, excluded: calls.append("check") or 4,
        )
        result = acquisition.acquire(1)
        self.assertTrue(result.claimed)
        self.assertEqual(result.slot, 4)
        self.assertEqual(result.reason, "claimed_by_fallback")
        self.assertEqual(calls, ["detect", "check"])

    def test_detection_error_is_reported_after_successful_fallback(self):
        def broken_detection(preferred, excluded):
            raise RuntimeError("camera unavailable")

        acquisition = HiveAcquisition(broken_detection, lambda preferred, excluded: 3)
        result = acquisition.acquire(1)
        self.assertTrue(result.claimed)
        self.assertEqual(result.slot, 3)
        self.assertEqual(result.detection_error, "camera unavailable")

    def test_stop_exits_before_detection(self):
        calls = []
        acquisition = HiveAcquisition(
            detect=lambda preferred, excluded: calls.append("detect"),
            check=lambda preferred, excluded: calls.append("check"),
            control_status=lambda: "stopped",
        )
        result = acquisition.acquire(1)
        self.assertFalse(result.claimed)
        self.assertEqual(result.reason, "stopped")
        self.assertEqual(calls, [])

    def test_stop_after_detection_skips_fallback(self):
        states = iter(("running", "stopped"))
        calls = []
        acquisition = HiveAcquisition(
            detect=lambda preferred, excluded: calls.append("detect") or 0,
            check=lambda preferred, excluded: calls.append("check") or 0,
            control_status=lambda: next(states),
        )
        result = acquisition.acquire(1)
        self.assertEqual(result.reason, "stopped")
        self.assertEqual(calls, ["detect"])

    def test_exclusions_reach_both_strategies(self):
        seen = []
        acquisition = HiveAcquisition(
            detect=lambda preferred, excluded: seen.append(set(excluded)) or 0,
            check=lambda preferred, excluded: seen.append(set(excluded)) or 0,
        )
        result = acquisition.acquire(3, {1, 6})
        self.assertFalse(result.claimed)
        self.assertEqual(seen, [{1, 6}, {1, 6}])

    def test_fatal_interruption_is_not_treated_as_detection_failure(self):
        class StopNow(Exception):
            pass

        def interrupted(preferred, excluded):
            raise StopNow()

        acquisition = HiveAcquisition(
            interrupted,
            lambda preferred, excluded: 2,
            fatal_exceptions=(StopNow,),
        )
        with self.assertRaises(StopNow):
            acquisition.acquire(1)

    def test_prompt_disappearing_confirms_claim(self):
        prompts = iter((True, False))
        presses = []
        accepted = confirm_claim(
            press_claim=lambda: presses.append("e"),
            claim_prompt_visible=lambda: next(prompts),
            control_status=lambda: "running",
            wait=lambda _seconds: None,
        )
        self.assertTrue(accepted)
        self.assertEqual(presses, ["e"])

    def test_claim_retries_once_when_prompt_stays_visible(self):
        presses = []
        accepted = confirm_claim(
            press_claim=lambda: presses.append("e"),
            claim_prompt_visible=lambda: True,
            control_status=lambda: "running",
            wait=lambda _seconds: None,
            checks_per_attempt=2,
        )
        self.assertFalse(accepted)
        self.assertEqual(presses, ["e", "e"])

    def test_stop_during_confirmation_exits(self):
        states = iter(("running", "stopped"))
        presses = []
        accepted = confirm_claim(
            press_claim=lambda: presses.append("e"),
            claim_prompt_visible=lambda: True,
            control_status=lambda: next(states),
            wait=lambda _seconds: None,
        )
        self.assertFalse(accepted)
        self.assertEqual(presses, ["e"])


if __name__ == "__main__":
    unittest.main()
