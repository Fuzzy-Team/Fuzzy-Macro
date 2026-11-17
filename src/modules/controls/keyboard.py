from __future__ import annotations

import pyautogui as pag
from modules.screen import virtual_display
import threading
import time
from typing import TYPE_CHECKING
from modules.controls.sleep import is_paused, is_stopped, wait_while_paused

if TYPE_CHECKING:
    from modules.submacros.hasteCompensation import HasteCompensationRevamped

#keys currently held down through keyboard.keyDown, so a pause can let go of them and press them again
_held = []

#walks re-plan the distance left this often, from the latest movespeed
WALK_TICK = 0.01
#the movespeed thread stops once no walk has asked for the speed for this long
SPEED_IDLE_SECONDS = 1


def _pausePoint():
    """If paused, release the held keys, wait for resume, then press them again.
    Returns the seconds spent paused so the caller can push its deadline back by that much."""
    if not is_paused():
        return 0
    start = time.perf_counter()
    held = list(_held)
    for k in held:
        pag.keyUp(k, _pause=False)
    wait_while_paused()
    if not is_stopped():
        if virtual_display.active(): virtual_display.state(require_window=True)
        for k in held:
            pag.keyDown(k, _pause=False)
    return time.perf_counter() - start


def _holdFor(duration, until=None):
    """Sleep while the keys stay held, pausing and stopping promptly. Time spent paused doesn't count.
    until() is checked every 10 ms and ends the wait early when it returns True."""
    end = time.perf_counter() + duration
    while not is_stopped():
        end += _pausePoint()
        if until and until():
            return
        remaining = end - time.perf_counter()
        if remaining <= 0:
            return
        time.sleep(min(WALK_TICK, remaining))


class keyboard:
    def __init__(self, walkspeed, enableHasteCompensation, hasteCompensation: HasteCompensationRevamped):
        self.ws = walkspeed
        self.enableHasteCompensation = enableHasteCompensation
        self.hasteCompensation = hasteCompensation

        #latest movespeed, kept current by a background thread while walks are running
        self._speed = 0
        self._speedWanted = 0
        self._speedThread = None

    def currentSpeed(self):
        """The movespeed from the buff bar. A background thread reads it while walks keep asking,
        so a walk never waits on a screen capture. The first call after a quiet spell reads it here."""
        self._speedWanted = time.monotonic() + SPEED_IDLE_SECONDS
        if self._speedThread is None or not self._speedThread.is_alive():
            self._speed = self.hasteCompensation.getHaste()
            self._speedThread = threading.Thread(target=self._readSpeed, daemon=True)
            self._speedThread.start()
        return self._speed

    def _readSpeed(self):
        while time.monotonic() < self._speedWanted and not is_stopped():
            if is_paused():
                time.sleep(0.1)
                continue
            self._speed = self.hasteCompensation.getHaste()
            time.sleep(WALK_TICK)

    def _walkDistance(self, distance, until=None):
        """Keep the held keys down until distance (studs) is covered. Every 10 ms it takes the
        latest movespeed and works out what is left, so a speed change mid-walk changes how long
        the rest takes. The walk runs until the distance is covered, however slow.
        until() is checked on every tick and ends the walk early when it returns True.
        Returns False if until() ended it."""
        last = time.perf_counter()
        speed = self.currentSpeed()
        while distance > 0 and not is_stopped():
            last += _pausePoint()
            if until and until():
                return False
            #a speed of zero would never get there
            if speed <= 0:
                break
            time.sleep(min(WALK_TICK, distance / speed))
            now = time.perf_counter()
            distance -= speed * (now - last)
            last = now
            speed = self.currentSpeed()
        return True

    #duration is seconds at the base speed of 28
    def predictiveTimeWait(self, duration, until=None):
        return self._walkDistance(28 * duration, until)

    def walk(self, k, t, applyHaste=True, method='predictive', until=None):
        keyboard.keyDown(k, False)
        try:
            if applyHaste and self.enableHasteCompensation:
                if method == 'predictive':
                    self.predictiveTimeWait(t, until)
                else:
                    self.timeWait(t)  # Original method
            else:
                _holdFor(t * 28 / self.ws, until)
        finally:
            keyboard.keyUp(k, False)

    def multiWalk(self, keys, t, applyHaste=True, method='predictive'):
        try:
            for k in keys:
                keyboard.keyDown(k, False)

            if applyHaste and self.enableHasteCompensation:
                if method == 'predictive':
                    self.predictiveTimeWait(t)
                else:
                    self.timeWait(t)
            else:
                _holdFor(t * 28 / self.ws)
        finally:
            for k in keys:
                keyboard.keyUp(k, False)

    @staticmethod
    #call the press function of the pag library
    def pagPress(k):
        if virtual_display.active(): virtual_display.state(require_window=True)
        pag.press(k)
    @staticmethod
    def keyDown(k, pause = True):
        if virtual_display.active(): virtual_display.state(require_window=True)
        #for some reason, the function key is sometimes held down, causing it to open the dock or enable dictation
        keyboard.keyUp('fn', False)
        if k not in _held:
            _held.append(k)
        pag.keyDown(k, _pause = pause)

    @staticmethod
    def keyUp(k, pause = True):
        if k in _held:
            _held.remove(k)
        pag.keyUp(k, _pause = pause)

    #pyautogui without the pause
    def press(self,key, delay = 0.02):
        keyboard.keyDown(key, False)
        try:
            _holdFor(delay)
        finally:
            keyboard.keyUp(key, False)

    def write(self, text, interval = 0.1):
        if virtual_display.active(): virtual_display.state(require_window=True)
        pag.typewrite(text, interval)
    #pyautogui with the pause
    def slowPress(self,k):
        if virtual_display.active(): virtual_display.state(require_window=True)
        pag.keyDown(k)
        time.sleep(0.08)
        pag.keyUp(k)

    def getMoveSpeed(self):
        movespeed = self.hasteCompensation.getHaste()
        return movespeed
    
    def timeWait(self, duration):

        baseSpeed = 28
        target_distance = baseSpeed * duration  # Total distance the player should travel
        traveledDistance = 0
        maxTime = baseSpeed/24*duration

        st = time.perf_counter()
        prevTime = st
        prevSpeed = self.getMoveSpeed()

        while traveledDistance < target_distance and prevTime-st < maxTime and not is_stopped():
            paused = _pausePoint()
            st += paused
            prevTime += paused
            currentTime = time.perf_counter()
            speed = self.getMoveSpeed()

            delta_t = currentTime - prevTime

            # Apply trapezoidal integration to calculate traveled distance
            traveledDistance += ((prevSpeed + speed) / 2) * delta_t

            # Update previous values
            prevTime = currentTime
            prevSpeed = speed


    #walk n tiles (4 studs each) with the keys already held, less a 1/8 stud head start
    def tileWait(self, n, hasteCap=0, until=None):
        return self._walkDistance(n * 4 - 1 / 8, until)

    def tileWalk(self, key, tiles, applyHaste = True):
        if applyHaste:
            self.keyDown(key, False)
            try:
                self.tileWait(tiles)
            finally:
                self.keyUp(key, False)
        else:
            self.press(key,(tiles/8.3)*28/self.ws)

    def multiTileWalk(self, keys, tiles, applyHaste = True):
        key_list = list(keys)
        if tiles <= 0 or not key_list:
            return False

        try:
            for key in key_list:
                keyboard.keyDown(key, False)
            if applyHaste:
                self.tileWait(tiles)
            else:
                _holdFor((tiles / 8.3) * 28 / self.ws)
        finally:
            for key in reversed(key_list):
                keyboard.keyUp(key, False)
        return True

    #release all movement keys (wasd, space)
    @staticmethod
    def releaseMovement():
        keys = ["w","a","s","d","space"]
        for k in keys:
            keyboard.keyUp(k, False)
