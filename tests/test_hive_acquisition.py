import unittest

from src.modules.hive_acquisition import acquire_hive, confirm_claim


class AcquireHiveTests(unittest.TestCase):
    def acquire(self, method="detect", detect=None, check=None, stopped=lambda: False, excluded=None, **kwargs):
        self.calls = []

        def run(name, strategy):
            def call(preferred, excluded_slots):
                self.calls.append((name, preferred, set(excluded_slots)))
                return strategy(preferred, excluded_slots) if strategy else None
            return call

        return acquire_hive(method, 2, excluded or set(), run("detect", detect), run("check", check), stopped, **kwargs)

    def test_detection_success_does_not_run_check(self):
        self.assertEqual(self.acquire(detect=lambda *_: 3, check=lambda *_: 4), (3, "claimed"))
        self.assertEqual(self.calls, [("detect", 2, set())])

    def test_check_runs_when_nothing_is_detected_from_spawn(self):
        self.assertEqual(self.acquire(check=lambda *_: 4), (4, "claimed"))
        self.assertEqual([call[0] for call in self.calls], ["detect", "check"])

    def test_check_does_not_run_after_detection_walked_the_hive_row(self):
        self.assertEqual(self.acquire(detect=lambda *_: 0, check=lambda *_: 4), (0, "no_claimable_hive"))
        self.assertEqual([call[0] for call in self.calls], ["detect"])

    def test_check_method_skips_detection(self):
        self.assertEqual(self.acquire("check", detect=lambda *_: 3, check=lambda *_: 5), (5, "claimed"))
        self.assertEqual([call[0] for call in self.calls], ["check"])

    def test_detection_error_falls_back_and_is_reported(self):
        def broken(*_):
            raise RuntimeError("camera unavailable")

        self.assertEqual(self.acquire(detect=broken, check=lambda *_: 3), (3, "claimed"))
        self.assertEqual(self.acquire(detect=broken), (0, "no_claimable_hive; detection: camera unavailable"))

    def test_stop_exits_before_detection(self):
        self.assertEqual(self.acquire(stopped=lambda: True), (0, "stopped"))
        self.assertEqual(self.calls, [])

    def test_stop_after_detection_skips_check(self):
        states = iter((False, True))
        self.assertEqual(self.acquire(stopped=lambda: next(states)), (0, "stopped"))
        self.assertEqual([call[0] for call in self.calls], ["detect"])

    def test_exclusions_reach_both_methods(self):
        self.acquire(excluded={1, 6})
        self.assertEqual([call[2] for call in self.calls], [{1, 6}, {1, 6}])

    def test_fatal_interruption_is_not_treated_as_detection_failure(self):
        class StopNow(Exception):
            pass

        def interrupted(*_):
            raise StopNow()

        with self.assertRaises(StopNow):
            self.acquire(detect=interrupted, check=lambda *_: 2, fatal_exceptions=(StopNow,))


class ConfirmClaimTests(unittest.TestCase):
    def test_prompt_disappearing_confirms_claim(self):
        prompts = iter((True, False, False, False))
        presses = []
        accepted = confirm_claim(
            press_claim=lambda: presses.append("e"),
            claim_prompt_visible=lambda: next(prompts),
            control_status=lambda: "running",
            wait=lambda _seconds: None,
        )
        self.assertTrue(accepted)
        self.assertEqual(presses, ["e"])

    def test_prompt_flicker_does_not_confirm_claim(self):
        prompts = iter((True, False, True, False, True, True))
        accepted = confirm_claim(
            press_claim=lambda: None,
            claim_prompt_visible=lambda: next(prompts),
            control_status=lambda: "running",
            wait=lambda _seconds: None,
            attempts=1,
            checks_per_attempt=6,
        )
        self.assertFalse(accepted)

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
