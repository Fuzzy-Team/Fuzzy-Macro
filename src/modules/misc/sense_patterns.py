"""Shared engine for the RoseSense, PepperSense and StrabrySense gather patterns.

Movement order, distances, colours, search rectangles and scan order follow the original
Sense patterns (v19). Where the original runs a timer, the pattern checks the clock instead.
Odd behaviour from the original is kept and marked "source:".

A pattern file builds one object per gather and calls run() every cycle:

    sense = RoseSense(self, tcfbkey, tclrkey, afcfbkey, afclrkey, rotup, sc_space)
    sense.run()

Key scripts are space-separated tokens. "a+" / "a-" press / release the pattern's
left key (w, a, s, d = TCFBKey, TCLRKey, AFCFBKey, AFCLRKey, so they respect inverted
movement). Capital letters are the literal keys: "A+" is always the "a" key. "space+" / "space-"
is the jump key.
"""
import math
import time

from modules.controls.sleep import is_paused
from modules.screen.imageSearch import findPixel, locateImageOnScreen

TARGET = 0xFFCD6B         # token target, searched outward from the middle row
PURPLE_TARGET = 0xCD66FF
HIT_TARGET = 0x01FF01     # shown when the backpack is full
FULL_BACKPACK = 0xF70017
SPRINKLER = 0x01D8FF

SCORCHING_ACTIVE = "./images/buffs/scorching_active"
# The original matched this icon exactly (variation 0). Fuzzy matches by similarity, so this is an
# approximation. A quarter of the icon is transparent, so its score depends on the scene behind
# it: on made-up strips it scored 0.57-0.85 with the icon and under 0.25 without it (other
# buff icons included). 0.5 sits in that gap. It has not been checked against a real capture.
SCORCHING_THRESHOLD = 0.5
ICON_BAND_HEIGHT = 100


class SenseStopped(Exception):
    """Ends the current cycle: the macro was stopped, or a lost-sprinkler search gave up.
    run() releases held keys and returns, and the gather loop decides what happens next."""


def round_half_up(value):
    return math.floor(value + 0.5)


class SensePattern:
    """Everything the three patterns share. Subclasses supply targets_missing()."""

    LOOPED_PARTS = 64   # source: LoopedPart() is called 64 times after its functions
    LOST_SPRINKLER_PASSES = 2   # laps of a lost-sprinkler search route before giving up

    def __init__(self, macro, tc_fb, tc_lr, af_cfb, af_clr, rot_up, space):
        self.macro = macro
        self.rot_up = rot_up
        self.keymap = {"w": tc_fb, "a": tc_lr, "s": af_cfb, "d": af_clr,
                       "W": "w", "A": "a", "S": "s", "D": "d", "space": space}
        self.held = set()
        self.started = False

    # --- running ---

    def run(self):
        """One cycle: the first call also does the setup. The source keeps keys held from one
        repetition to the next. Fuzzy does drift compensation and other work between cycles,
        so held keys are let go at the end of a cycle and pressed again at the start of the
        next one. finish() releases everything when the gather ends or the cycle fails."""
        try:
            if not self.started:
                self.start()
            self.press_held()
            for _ in range(self.LOOPED_PARTS):
                self.looped_part()
            self.release_held()
        except SenseStopped:
            self.finish()
        except BaseException:
            self.finish()
            raise

    def press_held(self):
        for key in self.held:
            self.macro.keyboard.keyDown(key, False)

    def release_held(self):
        for key in self.held:
            self.macro.keyboard.keyUp(key, False)

    def start(self):
        window = self.macro.robloxWindow
        self.w, self.h = window.mw, window.mh
        for _ in range(4):
            self.idle()
            self.macro.keyboard.press(self.rot_up, 0.017)  # Camera tap hold: 17 ms.
        self.circle_line = 1
        self.missed_sprinkler = 0   # source: foundSprinklerLastTime
        self.last_found = (round_half_up(self.w * 0.5), round_half_up(self.h * 0.5))
        self.started = True

    def finish(self):
        self.release_held()
        self.held.clear()

    # --- input and searching; every one stops, pauses and resumes held keys first ---

    def idle(self):
        paused = is_paused()
        if self.macro.checkPauseAndWait():
            raise SenseStopped()
        if paused:
            for key in self.held:
                self.macro.keyboard.keyDown(key, False)

    def keys(self, script):
        for token in script.split():
            key = self.keymap[token[:-1]]
            self.idle()
            if token[-1] == "+":
                self.macro.keyboard.keyDown(key, False)
                self.held.add(key)
            else:
                self.macro.keyboard.keyUp(key, False)
                self.held.discard(key)

    def walk(self, tiles):
        self.idle()
        self.macro.keyboard.tileWait(tiles)

    def wait_ms(self, milliseconds):
        """Sleep in slices, so a pause that lands mid-wait releases and re-presses held keys."""
        end = time.monotonic() + int(milliseconds) / 1000
        while True:
            self.idle()
            remaining = end - time.monotonic()
            if remaining <= 0:
                return
            time.sleep(min(remaining, 0.05))   # not sleep(): it would wait out a pause itself

    def pixel(self, x1, y1, x2, y2, color, variation):
        """PixelSearch. The original searches up to x = w and y = h, one pixel past the client
        area. A rectangle with one end inside the window is cut to it; one wholly outside
        finds nothing (so a token on the last or first row can't vouch for itself)."""
        self.idle()
        right, bottom = self.w - 1, self.h - 1
        if (max(x1, x2) < 0 or min(x1, x2) > right
                or max(y1, y2) < 0 or min(y1, y2) > bottom):
            return None
        clip = lambda value, limit: min(max(value, 0), limit)
        return findPixel(self.macro.robloxWindow, clip(x1, right), clip(y1, bottom),
                         clip(x2, right), clip(y2, bottom), color, variation)

    def icon_visible(self, path, threshold):
        """ImageSearch in the buff row at the top of the window, by similarity."""
        self.idle()
        window = self.macro.robloxWindow
        return locateImageOnScreen(path, window.mx, window.my, self.w, ICON_BAND_HEIGHT,
                                   threshold, scales=[1.0]) is not None

    # --- walking toward a point ---

    def _aim(self, x, y):
        """Release the literal keys, then return the key and length of each screen axis
        (in tiles) as ((x key, x length), (y key, y length))."""
        self.last_found = (x, y)
        mx = (x - self.w * 0.5) / self.h * 17
        my = (y - self.h * 0.5) / self.h * 16
        self.keys("W- A- S- D-")
        return ("D" if mx > 0 else "A", abs(mx)), ("S" if my > 0 else "W", abs(my))

    def go_to(self, x, y):
        """GoToXYPosition: the diagonal first, then the rest of the longer axis."""
        (x_key, x_len), (y_key, y_len) = self._aim(x, y)
        major, minor = ((x_key, x_len), (y_key, y_len)) if x_len > y_len else ((y_key, y_len), (x_key, x_len))
        self.keys(f"{x_key}+ {y_key}+")
        self.walk(minor[1] * 1.414)
        self.keys(minor[0] + "-")
        self.walk(major[1] - minor[1])
        self.keys(major[0] + "-")

    def target_walk(self, x, y):
        """TargetWalk: like go_to, but leaves keys held for the next step. A long thin
        approach drops the minor key after the diagonal; otherwise both end up held."""
        (x_key, x_len), (y_key, y_len) = self._aim(x, y)
        (major_key, major_len), (minor_key, minor_len) = (
            ((x_key, x_len), (y_key, y_len)) if x_len > y_len else ((y_key, y_len), (x_key, x_len)))
        if major_len > minor_len * 2.414:
            self.keys(f"{x_key}+ {y_key}+")
            self.walk(minor_len * 1.414)
            self.keys(minor_key + "-")
        else:
            self.keys(major_key + "+")
            self.walk(major_len - minor_len)
            self.keys(minor_key + "+")

    def go_to_sprinkler_corner(self, x, y, scale):
        self.go_to(x + self.h * scale, y - self.h * scale)

    def go_to_mirror_of_last_found(self):
        """The point opposite the last target through the middle of the screen."""
        x, y = self.last_found
        self.go_to(-1 * (x - self.w / 2) + self.w / 2, -1 * (y - self.h / 2) + self.h / 2)

    # --- finding targets ---

    def find_target(self):
        """The 0xFFCD6B target: search up from the middle row, then down. A hit only counts
        if the pixel above (or below) it, or the one next to that, has the colour too."""
        row = round_half_up(self.h / 2)
        while row >= 0:
            hit = self.pixel(0, row, self.w, 0, TARGET, 0)
            if hit is None:
                break
            if self.pixel(hit[0], hit[1] - 1, hit[0] + 1, hit[1] - 1, TARGET, 0):
                return hit
            row = hit[1] - 1
        row = round_half_up(self.h / 2) + 2
        while True:
            hit = self.pixel(0, row, self.w, self.h, TARGET, 0)
            if hit is None:
                return None
            if self.pixel(hit[0], hit[1] + 1, hit[0] + 1, hit[1] + 1, TARGET, 0):
                return hit
            row = hit[1] + 1

    def find_in_halves(self, color):
        """The upper half bottom-up, then the lower half top-down."""
        middle = round_half_up(self.h / 2)
        return (self.pixel(0, middle, self.w, 0, color, 0)
                or self.pixel(0, middle + 2, self.w, self.h, color, 0))

    def find_sprinkler(self, variation=8):
        return self.pixel(0, 0, self.w, self.h, SPRINKLER, variation)

    def shift_out(self, y):
        """Move y away from the middle band of the screen by half a target."""
        if y > self.h * 0.544:
            return y + self.h * 0.044
        if y < self.h * 0.456:
            return y - self.h * 0.044
        return y

    def shift_in(self, y):
        if y > self.h * 0.544:
            return y - self.h * 0.044
        if y < self.h * 0.456:
            return y + self.h * 0.044
        return y

    # --- one step of the pattern ---

    def looped_part(self):
        if self.circle_line <= 0:
            self.search_and_walk()
        else:
            self.keep_walking()

    def search_and_walk(self):
        """Not mid-circle: go to a full-backpack hit target if there is one, otherwise to
        the nearer of the two token targets."""
        if self.pixel(round_half_up(self.w / 2) + 60, 25, round_half_up(self.w / 2) + 64, 34,
                      FULL_BACKPACK, 40):
            hit = self.find_in_halves(HIT_TARGET)
            if hit:
                self.go_to(hit[0], self.shift_in(hit[1]))
                return
        target = self.find_target()
        purple = self.find_in_halves(PURPLE_TARGET)
        if target and purple:
            tx, ty = target[0], self.shift_out(target[1])
            px, py = purple[0], self.shift_out(purple[1])
            self.circle_line = -3
            if (tx - self.w * 0.5) ** 2 + (ty - self.h * 0.5) ** 2 < (px - self.w * 0.5) ** 2 + (py - self.h * 0.5) ** 2:
                self.target_walk(tx, ty)
            else:
                self.target_walk(px, py)
        elif target:
            self.circle_line = -3
            self.target_walk(target[0], self.shift_in(target[1]))
        elif purple:
            self.circle_line = -3
            self.target_walk(purple[0], self.shift_out(purple[1]))
        else:
            self.targets_missing()

    def keep_walking(self):
        """Mid-circle (circle_line > 0): only the 0xFFCD6B target breaks the circle."""
        target = self.find_target()
        if target:
            self.keys("w- a- s- d-")
            self.circle_line = -3
            self.target_walk(target[0], self.shift_out(target[1]))
        else:
            self.targets_missing()

    # --- walking the circle when no target is on screen ---

    CIRCLE_INNER = {   # circle_line: keys, tiles
        2: ("a- s+ d+", 0.5), 3: ("d-", 0.5), 4: ("a+", 0.5), 5: ("s-", 0.5), 6: ("w+", 0.5),
        7: ("a-", 0.5), 8: ("d+", 0.5), 9: ("w-", 0.5), 10: ("w+", 0.7),
    }
    CIRCLE_OUTER = ("w- s+", "d-", "a+", "s-", "w+", "a-", "d+", "w-")   # 2 lines each, 1 tile

    def circle_step(self):
        """One leg of the small octagon (lines 2-10), then the big one (11-26)."""
        line = self.circle_line
        if line <= 10:
            keys, tiles = self.CIRCLE_INNER[line]
        elif line <= 26:
            keys, tiles = self.CIRCLE_OUTER[(line - 11) // 2], 1
        else:
            self.keys("d- a+ s+")
            self.walk(0.7)
            self.circle_line = 0
            return
        self.keys(keys)
        self.walk(tiles)
        self.circle_line = line + 1

    def shake(self, pause_ms):
        """First step of the circle: wiggle the character, then stand still."""
        self.keys("a- s- w+ d+")
        self.wait_ms(pause_ms)
        self.keys("w- d- a+ s+")
        self.wait_ms(pause_ms)
        self.keys("a- s-")

    def sprinkler_ladder(self, steps, variation=8):
        """Walk each (keys before, tiles, keys after) step, looking for the sprinkler after
        each one. Returns the first hit, or None."""
        for before, tiles, after in steps:
            self.keys(before)
            self.walk(tiles)
            self.keys(after)
            hit = self.find_sprinkler(variation)
            if hit:
                return hit
        return None

    def finish_sprinkler_search(self, hit):
        self.keys("space+")
        self.missed_sprinkler = 0
        self.go_to_sprinkler_corner(hit[0], hit[1], 0.2)
        self.keys("space-")

    def after_circle_search(self):
        """Runs between the first sprinkler search and acting on it (StrabrySense only)."""

    def circle_sprinkler_check(self, corner_scale, search_lost):
        """circle_line == 1: look for the sprinkler and stand on its corner. Two misses in a
        row call search_lost(), which returns where it found the sprinkler, or None once it
        gives up. Giving up ends the cycle, so the gather can check its time limit and
        backpack, and the next cycle starts over from a target search."""
        self.circle_line = 2
        hit = self.find_sprinkler()
        self.after_circle_search()
        if hit:
            self.go_to_sprinkler_corner(hit[0], hit[1], corner_scale)
            self.missed_sprinkler = 0
            return
        self.missed_sprinkler += 1
        if self.missed_sprinkler == 2:
            self.keys("space+")
            self.go_to_mirror_of_last_found()
            hit = self.find_sprinkler() or search_lost()
            if not hit:
                self.missed_sprinkler = 0
                self.circle_line = 0
                raise SenseStopped()
            self.finish_sprinkler_search(hit)


class RoseSense(SensePattern):
    LOOP = (   # one search lap, variation 4: keys before, tiles, keys after
        ("s+", 8, "s-"), ("d+", 8, "d-"), ("w+", 8, "w-"), ("d+", 8, "d-"),
        ("w+", 8, "w-"), ("d+", 8, "d-"), ("w+", 8, "w-"), ("d+", 8, "d-"),
        ("a+ s+ space+", 8, "a- s-"), ("a+ s+", 8, "a- s-"),
        ("a+", 4, "a-"), ("a+", 4, "space- a-"),
    )

    def targets_missing(self):
        if self.circle_line <= 0:
            self.shake(40)
            self.circle_line = 1
        elif self.circle_line == 1:
            self.circle_sprinkler_check(0.1, self.search_lost_sprinkler)
        else:
            self.circle_step()

    def search_lost_sprinkler(self):
        hit = self.sprinkler_ladder((
            ("d+", 10, ""), ("", 10, ""), ("", 8, ""), ("space- d- w+", 6, ""),
            ("", 6, "w-"), ("s+", 8, ""), ("d+", 8, "s- d-"),
        ))
        for _ in range(self.LOST_SPRINKLER_PASSES):
            if hit:
                break
            hit = self.sprinkler_ladder(self.LOOP, 4)
        return hit


class PepperSense(SensePattern):
    def targets_missing(self):
        if self.circle_line <= 0:
            self.shake(40)
            self.circle_line = 1
        elif self.circle_line == 1:
            self.circle_sprinkler_check(0.2, self.search_lost_sprinkler)
        else:
            self.circle_step()

    def sweep(self):
        """Three legs across the field, looking for the sprinkler after each."""
        self.keys("a+")
        self.wait_ms(20)
        self.keys("space+")
        self.walk(10)
        hit = self.find_sprinkler()
        if hit:
            return hit
        self.keys("a- w+")
        self.walk(10)
        hit = self.find_sprinkler()
        if hit:
            return hit
        self.keys("space- w- s+ d+")
        self.walk(10)
        self.keys("s- d-")
        return self.find_sprinkler()

    def search_lost_sprinkler(self):
        hit = self.sprinkler_ladder((("a+", 8, ""), ("a- w+", 8, ""), ("", 8, "")))
        if hit:
            return hit
        self.walk(8)
        self.keys("w-")
        for _ in range(2):
            hit = self.sweep()
            if hit:
                return hit
        self.keys("a+")
        self.walk(10)
        self.keys("a- s+")
        self.walk(32)
        self.keys("space+")
        self.walk(2)
        self.keys("space- s-")
        self.wait_ms(800)
        self.keys("space+ a+")
        self.walk(2)
        self.keys("w+")
        self.walk(32)
        self.keys("space- w- a-")
        for _ in range(self.LOST_SPRINKLER_PASSES):
            hit = self.sweep()
            if hit:
                return hit
        return None


class StrabrySense(SensePattern):
    """Starts in "precise mark" mode for one second, which walks straight to marks instead
    of the diagonal-first approach."""

    PRECISION_SECONDS = 1

    def start(self):
        super().start()
        self.precision_until = time.monotonic() + self.PRECISION_SECONDS

    def looped_part(self):
        precise = time.monotonic() < self.precision_until
        if not precise:
            super().looped_part()
        elif self.circle_line <= 0:
            purple = self.find_in_halves(PURPLE_TARGET)
            if purple:
                self.go_to(purple[0], self.shift_out(purple[1]))
                return
            hit = self.find_in_halves(HIT_TARGET)
            if hit:
                self.circle_line = -3
                self.go_to_precise_mark(hit[0], self.shift_in(hit[1]))
            else:
                self.targets_missing()
        else:
            purple = self.find_in_halves(PURPLE_TARGET)
            if purple:
                self.circle_line = -3
                self.go_to_precise_mark(purple[0], self.shift_out(purple[1]))
            else:
                self.targets_missing()

    def go_to_precise_mark(self, x, y):
        """One axis at a time, x first."""
        for key, tiles in self._aim(x, y):
            self.keys(key + "+")
            self.walk(tiles)
            self.keys(key + "-")

    def after_circle_search(self):
        # source: Precision 10x also sets the timer to 8, but that icon is not shipped, so
        # nothing extends precise mode beyond its first second.
        if self.icon_visible(SCORCHING_ACTIVE, SCORCHING_THRESHOLD):
            self.precision_until = 0

    def targets_missing(self):
        if self.circle_line <= 0:
            self.shake(20)
            self.circle_line += 1
        elif self.circle_line == 1:
            self.circle_sprinkler_check(0.2, self.search_lost_sprinkler)
        else:
            self.circle_step()

    def search_lost_sprinkler(self):
        self.keys("s+")
        self.walk(4)
        self.keys("s- d+")
        self.walk(10)
        hit = self.find_sprinkler() or self.sprinkler_ladder((
            ("", 10, ""), ("", 10, ""), ("d- w+", 11, ""), ("", 11, ""),
        ))
        if hit:
            return hit
        self.keys("w- space-")
        for _ in range(self.LOST_SPRINKLER_PASSES):
            self.keys("w+")
            self.wait_ms(20)
            self.keys("space+")
            self.wait_ms(1000)
            hit = self.find_sprinkler()
            self.keys("w- s+ d+")
            self.wait_ms(200)
            self.keys("space-")
            self.walk(5)
            self.keys("s- d-")
            if hit:
                return hit
            hit = self.find_sprinkler()
            if hit:
                return hit
            self.keys("a+")
            self.walk(4)
            hit = self.find_sprinkler()
            if hit:
                return hit
            self.keys("a-")
            self.wait_ms(500)
            hit = self.find_sprinkler()
            if hit:
                return hit
            self.wait_ms(500)
            hit = self.find_sprinkler()
            if hit:
                return hit
            self.keys("d+")
            self.walk(4)
            hit = self.find_sprinkler()
            if hit:
                return hit
            self.keys("d-")
        return None
