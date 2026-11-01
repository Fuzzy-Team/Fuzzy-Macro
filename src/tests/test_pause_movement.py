"""Pausing or stopping mid-walk must release the keys now and keep the walk's remaining time for resume.

Run from src/: python3 -m unittest discover -s tests
"""
import threading
import time
import unittest
from types import SimpleNamespace

import modules.controls.keyboard as keyboardModule
import modules.controls.sleep as sleepModule

RUNNING, STOPPED, PAUSED = 2, 0, 6
# how late a pause or stop may be noticed
REACTION = 0.15


class FakePag:
    """Records key events instead of sending them."""

    def __init__(self):
        self.events = []

    def keyDown(self, key, _pause=True):
        self.events.append((time.perf_counter(), "down", key))

    def keyUp(self, key, _pause=True):
        self.events.append((time.perf_counter(), "up", key))

    def heldIntervals(self, key, endedAt):
        intervals, downAt = [], None
        for at, kind, k in self.events:
            if k != key:
                continue
            if kind == "down" and downAt is None:
                downAt = at
            elif kind == "up" and downAt is not None:
                intervals.append((downAt, at))
                downAt = None
        if downAt is not None:
            intervals.append((downAt, endedAt))
        return intervals


class PauseMovementTest(unittest.TestCase):
    def setUp(self):
        self.pag = FakePag()
        self.run = SimpleNamespace(value=RUNNING)
        self._pag, keyboardModule.pag = keyboardModule.pag, self.pag
        sleepModule.set_run_state(self.run)
        sleepModule.set_resume_callback(None)
        haste = SimpleNamespace(getHaste=lambda: (time.sleep(0.01), 28)[1])
        self.keyboard = keyboardModule.keyboard(28, True, haste)

    def tearDown(self):
        keyboardModule.pag = self._pag
        sleepModule.set_run_state(None)

    def setStateAfter(self, delay, value):
        t = threading.Timer(delay, lambda: setattr(self.run, "value", value))
        t.start()
        self.addCleanup(t.cancel)

    def assertPausedAndResumed(self, walk, duration):
        """Pause at 0.3s for 0.5s: key up promptly, back down on resume, ~duration held in total."""
        pausedAt = time.perf_counter() + 0.3
        self.setStateAfter(0.3, PAUSED)
        self.setStateAfter(0.8, RUNNING)
        walk()
        end = time.perf_counter()
        intervals = self.pag.heldIntervals("w", end)
        self.assertEqual(len(intervals), 2, self.pag.events)
        self.assertLess(intervals[0][1] - pausedAt, REACTION, "key stayed down after pause")
        self.assertGreater(intervals[1][0] - pausedAt, 0.4, "key came back before resume")
        held = sum(b - a for a, b in intervals)
        self.assertAlmostEqual(held, duration, delta=REACTION)

    def assertStopReleases(self, walk):
        stoppedAt = time.perf_counter() + 0.3
        self.setStateAfter(0.3, STOPPED)
        walk()
        end = time.perf_counter()
        self.assertLess(end - stoppedAt, REACTION, "walk kept going after stop")
        self.assertEqual(self.pag.events[-1][1:], ("up", "w"))

    def test_plain_hold_pauses_and_resumes_with_remaining_time(self):
        self.assertPausedAndResumed(lambda: self.keyboard.press("w", 1.0), 1.0)

    def test_hasteless_walk_pauses_and_resumes_with_remaining_time(self):
        self.assertPausedAndResumed(lambda: self.keyboard.walk("w", 1.0, applyHaste=False), 1.0)

    def test_haste_walk_pauses_and_resumes_with_remaining_time(self):
        self.assertPausedAndResumed(lambda: self.keyboard.walk("w", 1.0), 1.0)

    def test_haste_walk_original_method_pauses_and_resumes(self):
        self.assertPausedAndResumed(lambda: self.keyboard.walk("w", 1.0, method="timeWait"), 1.0)

    def test_multi_walk_pauses_and_resumes_with_remaining_time(self):
        self.assertPausedAndResumed(lambda: self.keyboard.multiWalk(["w"], 1.0, applyHaste=False), 1.0)

    def test_tile_walk_pauses_and_resumes(self):
        # 1 tile at speed 28 takes 1/8 + 1/4 of a second per tile in tileWait's units; 3 tiles is ~1s
        start = time.perf_counter()
        self.keyboard.tileWalk("w", 3)
        duration = time.perf_counter() - start
        self.pag.events.clear()
        self.assertPausedAndResumed(lambda: self.keyboard.tileWalk("w", 3), duration)

    def test_hasteless_tile_walk_holds_for_the_tiles_at_walkspeed(self):
        self.keyboard.tileWalk("w", 1, applyHaste=False)
        end = time.perf_counter()
        (down, up), = self.pag.heldIntervals("w", end)
        self.assertAlmostEqual(up - down, (1 / 8.3) * 28 / 28, delta=0.05)

    def test_stop_releases_plain_hold(self):
        self.assertStopReleases(lambda: self.keyboard.press("w", 1.0))

    def test_stop_releases_haste_walk(self):
        self.assertStopReleases(lambda: self.keyboard.walk("w", 1.0))

    def test_stop_releases_tile_walk(self):
        self.assertStopReleases(lambda: self.keyboard.tileWalk("w", 5))


if __name__ == "__main__":
    unittest.main()
