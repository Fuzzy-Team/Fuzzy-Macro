"""Vicious Bee fight with target sense: the camera is set to pitch 1, a sprinkler goes down, and the
character walks to violet, green and purple targets while steering around the bee's attacks and
orange targets. When no target is in sight it follows the bee's health bar and the sprinkler.

Distances are in flowers (3.908 studs). Screen positions become flowers with the camera's pitch 1
projection, and every walk is a short diagonal-and-straight move on the movement keys.
"""
import math
import threading
import time

import cv2
import numpy as np

from modules.controls.sleep import is_paused, is_stopped, sleep
from modules.misc.sense_patterns import (
    colour_bounds, detour, find_targets, pixel_search, run_of,
)

FIGHT_SECONDS = 300
FLOWER_TILES = 3.908 / 4
GREEN_SECONDS = 10          # the health bar search also looks for green at the start
TARGET_GRACE = 0.25         # seconds without a target before the route runs
RECOLLECT_SECONDS = 3.0
SEARCH_TICK = 0.01
NO_HITS_SECONDS, HITS_SECONDS = 6, 4

# Camera yaw (in 45 degree steps) each field is fought at
FIELD_YAW = {"pepper": 2, "mountain top": 2, "spider": 4, "cactus": 0, "rose": 0, "clover": 6}
NO_JUMP = ("cactus", "mountain top")

COMBO_COCONUT = 0x8B5E3C
MOB_ATTACK = (0xFF0000, 0xEC1008)
TOP_WEIGHT = 100
WEIGHTS = {"green": 100, "purple": 100, "violet": 50}
# Walking to a target this close (in flowers, per kind) only goes a quarter of the way
STAY_DIAMETER = {"hit": 2.3, "combo": 6.1}
COMBO_MOD = (0.6, 0.5)

DIAMETERS = [5.92, 2.96, 8.87, 11.83, 6.28, 3.33, 9.24, 12.2]
CORNERS = [(0, -.5), (.354, -.354), (.5, 0), (.354, .354), (0, .5), (-.354, .354), (-.5, 0), (-.354, -.354)]
LEGS = [([["d"], ["s", "d"]]), ([["s", "d"], ["s"]]), ([["s"], ["a", "s"]]), ([["a", "s"], ["a"]]),
        ([["a"], ["w", "a"]]), ([["w", "a"], ["w"]]), ([["w"], ["w", "d"]]), ([["w", "d"], ["d"]])]

# Sprinkler colours as 0xRRGGBB (or a pair), with the search rectangle each uses (fractions of the
# window height; the sides swap at yaw 2 and 6)
SPRINKLER_COLOURS = [(55295, 186879), (513791, 3659775), (1497086, 4840703), (7461630, 10216959),
                     7200767, (3122431, 5161215), (551678, 2993407), (3252991, 5949951)]
SIDES_A = [0, .003, .005, .016, .006, .008, .012, .012]
SIDES_B = [0, .002, .003, .014, .006, .008, .010, .010]


# --- screen and world geometry ---

def screen_flowers(x, y, w, h):
    k = 17.6 / (y / h or 0.001)
    return (x - w / 2) / h * k, (y - h / 2) / h * k


def char_px(w, h, kind="ground"):
    """Where the character is on screen: the middle for the camera, a bit lower for the ground."""
    return (w / 2, h / 2) if kind in ("center", "combo") else (w / 2, h * (0.5 + 0.063 * 0.573))


def px_to_flowers(x, y, w, h, kind="ground"):
    fx, fy = screen_flowers(x, y, w, h)
    cx, cy = screen_flowers(*char_px(w, h, kind), w, h)
    return fx - cx, fy - cy


def rotate(x, y, steps):
    angle = steps * math.pi / 4
    return x * math.cos(angle) + y * math.sin(angle), -x * math.sin(angle) + y * math.cos(angle)


def point_along_line(x1, y1, x2, y2, distance, w, h):
    """The pixel `distance` flowers from the first point toward the second."""
    ax, ay = px_to_flowers(x1, y1, w, h, "center")
    bx, by = px_to_flowers(x2, y2, w, h, "center")
    length = math.hypot(bx - ax, by - ay) or 1
    tx, ty = ax + (bx - ax) / length * distance, ay + (by - ay) / length * distance
    k = 17.6 / (y1 / h or 0.001)
    return tx * h / k + w / 2, ty * h / k + h / 2


# --- finding things on a frame ---

def thin_hits(hits, gap, cap):
    """Keep hits in order, dropping any closer than gap to one already kept."""
    gap, kept = max(gap, 1), []
    for x, y in hits:
        if all(math.hypot(x - kx, y - ky) >= gap for kx, ky in kept):
            kept.append((x, y))
            if len(kept) >= cap:
                break
    return kept


def mob_attacks(frame):
    """The red attack pixels, nearest the character first, thinned to a dozen points."""
    h, w = frame.shape[:2]
    safety = int(h * 0.01)
    low, high = colour_bounds(MOB_ATTACK)
    ys, xs = np.nonzero(run_of(cv2.inRange(frame, low, high) > 0, safety))
    if not len(xs):
        return []
    cx, cy = char_px(w, h)
    order = np.lexsort((xs, ys, (xs - cx) ** 2 + (ys - cy) ** 2))[:300]
    shift = math.floor((int(abs(safety) * 0.5) // 2) * 0.5)   # the run is to the right: aim at its middle
    return thin_hits([(int(xs[i]) + shift, int(ys[i])) for i in order], h * 0.02, 12)


def range_variance(colour, edge, middle):
    """The (r, g, b) variance for a colour: edge at the extremes, middle in the middle of each channel."""
    first, second = (colour, colour) if isinstance(colour, int) else colour
    out = []
    for shift in (16, 8, 0):
        c = ((first >> shift & 255) + (second >> shift & 255)) / 2
        out.append(round(edge + (middle - edge) * min(c, 255 - c) / 127.5))
    return tuple(out)


def rect_search(frame, colour, variance, width, height):
    """The matching rectangle (width x height from its top left) nearest the window middle."""
    low, high = colour_bounds(colour, variance)
    mask = cv2.inRange(frame, low, high)
    kernel = np.ones((max(1, int(height)), max(1, int(width))), np.uint8)
    ys, xs = np.nonzero(cv2.erode(mask, kernel, anchor=(0, 0)))
    if not len(xs):
        return None
    h, w = frame.shape[:2]
    best = int(np.argmin((xs - w / 2) ** 2 + (ys - h / 2) ** 2))
    return int(xs[best]), int(ys[best])


# --- choosing and routing ---

def plan_targets(items, avoid, size, yaw, offset):
    """The next target and the one after it, or []. items are (x, y, kind, weight, type, mod)."""
    w, h = size
    circles = [(px_to_flowers(a[0], a[1], w, h), a[2] if len(a) > 2 else 2) for a in avoid]
    cands = []
    for x, y, kind, weight, kind_type, mod in items:
        if not (0 <= x < w and 0 <= y < h) or weight <= 0:
            continue
        fx, fy = px_to_flowers(x, y, w, h, kind)
        if any((fx - cx) ** 2 + (fy - cy) ** 2 < r * r for (cx, cy), r in circles):
            continue
        wx, wy = rotate(fx, fy, -yaw)
        mx, my = rotate(mod[0], mod[1], yaw)
        dist = math.hypot(wx + offset[0] + mx, wy + offset[1] + my)
        weight /= max(0.01, 1 - 0.5 ** (dist / 20) * max(0, TOP_WEIGHT - weight) / TOP_WEIGHT)
        cands.append((fx, fy, weight, kind_type, mod))
    if len(cands) < 2:
        return cands
    score = lambda c: math.hypot(c[0], c[1]) / c[2]
    best, plan = math.inf, []
    if len(cands) <= 60:
        for first in sorted(cands, key=score):
            if best <= score(first):
                break
            second = min((c for c in cands if c is not first),
                         key=lambda c: math.hypot(c[0] - first[0], c[1] - first[1]) / c[2])
            total = score(first) + 0.5 * math.hypot(second[0] - first[0], second[1] - first[1]) / second[2]
            if total < best:
                best, plan = total, [first, second]
        return plan
    first = min(cands, key=score)
    second = min((c for c in cands if c is not first),
                 key=lambda c: math.hypot(c[0] - first[0], c[1] - first[1]) / c[2])
    return [first, second]


def route_leg(start, end, obstacles):
    """Waypoints from start to end that skirt each obstacle (x, y, radius), farthest first."""
    points = [end]
    for ox, oy, radius in sorted(obstacles, key=lambda o: -math.hypot(o[0] - start[0], o[1] - start[1])):
        step = detour((points[0][0] - start[0], points[0][1] - start[1]), (ox - start[0], oy - start[1]), radius)
        if step:
            points.insert(0, (start[0] + step[0], start[1] + step[1]))
    return points


class SenseFight:
    """One fight. run() returns "died", "defeated" or "time" (from check(), which is called every
    loop and returns "died", "defeated" or None), or "stopped"."""

    def __init__(self, macro, field, check):
        self.macro, self.field, self.check = macro, field, check
        self.keyboard = macro.keyboard
        self.yaw = FIELD_YAW[field]
        self.held, self.space = set(), False
        self.offset, self.tick = [0.0, 0.0], time.monotonic()
        self.seen, self.planned, self.walked = (0, None), 0, 0
        self.plan, self.planFrame, self.avoid, self.targetAt = [], 0, [], 0
        self.noHit = self.getHit = 0
        self.fog, self.lastFog, self.fixTime = 0, None, None
        self.getting = self.collecting = False
        self.octos = self.idx = self.tokenSeq = self.collectSeq = self.missed = 0
        self.token = (1, 1)
        self.recollectUntil = 0
        self.error = None
        self.stopping = False

    # --- keys and dead reckoning ---

    def integrate(self):
        """Move the character offset by what the held keys have walked since the last call."""
        now = time.monotonic()
        speed = self.keyboard.currentSpeed() or 28
        flowers = (now - self.tick) * speed / 3.908
        self.tick = now
        dx = ("d" in self.held) - ("a" in self.held)
        dy = ("s" in self.held) - ("w" in self.held)
        if dx or dy:
            rx, ry = rotate(dx * flowers, dy * flowers, -self.yaw)
            self.offset[0] += rx
            self.offset[1] += ry

    def hold(self, *keys):
        self.integrate()
        for key in self.held - set(keys):
            self.keyboard.keyUp(key, False)
        for key in set(keys) - self.held:
            self.keyboard.keyDown(key, False)
        self.held = set(keys)

    def setSpace(self, down):
        if down != self.space:
            (self.keyboard.keyDown if down else self.keyboard.keyUp)("space", False)
            self.space = down

    def send(self, flowers, *keys):
        self.hold(*keys)
        try:
            self.keyboard.tileWait(flowers * FLOWER_TILES)
        finally:
            self.hold()

    def walkDelta(self, dx, dy, until=None):
        """Walk dx right and dy down: the diagonal first when it is the shorter way to finish, else
        the straight part first. Returns False if until() ended it."""
        keyX, keyY = ("d" if dx > 0 else "a"), ("s" if dy > 0 else "w")
        (main, large), (side, small) = (((keyX, abs(dx)), (keyY, abs(dy))) if abs(dx) > abs(dy)
                                         else ((keyY, abs(dy)), (keyX, abs(dx))))
        wait = lambda flowers: self.keyboard.tileWait(flowers * FLOWER_TILES, until=until)
        try:
            if small * 1.414 > large - small:
                self.hold(main, side)
                done = wait(small * 1.414)
                if done:
                    self.hold(main)
                    done = wait(large - small)
            else:
                self.hold(main)
                done = wait(large - small)
                if done:
                    self.hold(main, side)
                    done = wait(small * 1.414)
        finally:
            self.hold()
        return done

    def walkTo(self, targets, obstacles=(), until=None):
        """Walk through targets (flowers from the character), steering around obstacles."""
        points, start = [], (0, 0)
        for end in targets:
            points += route_leg(start, end, obstacles)
            start = end
        previous = (0, 0)
        for point in points:
            dx, dy = point[0] - previous[0], point[1] - previous[1]
            previous = point
            if abs(dx) < 0.1 and abs(dy) < 0.1:
                continue
            if not self.walkDelta(dx, dy, until):
                return False
        return True

    def goTo(self, point, offset=(0, 0)):
        """Walk to a screen point plus an offset in flowers, steering around what the search sees."""
        w, h = self.size
        x, y = px_to_flowers(point[0], point[1], w, h)
        obstacles = [(*px_to_flowers(a[0], a[1], w, h), a[2] if len(a) > 2 else 2.2) for a in self.avoid]
        self.walkTo([(x + offset[0], y + offset[1])], obstacles, self.hasTarget)

    # --- seeing ---

    def priority(self, now):
        """Violet only for 6 seconds, then green, purple and violet for 4."""
        if now < self.noHit:
            return "marks"
        if now >= self.getHit:
            self.noHit = now + NO_HITS_SECONDS
            self.getHit = self.noHit + HITS_SECONDS
        return "hits"

    def look(self, frame):
        """The targets and the points to avoid on one frame."""
        h, w = frame.shape[:2]
        char = char_px(w, h)
        found = find_targets(frame, self.priority(time.monotonic()) != "marks", self.fog, False, char)
        items = []
        for name in ("violet", "green", "purple"):
            if found[name]:
                items.append((*found[name], "ground", WEIGHTS[name], "hit" if name != "violet" else "precision", (0, 0)))
        coconut = pixel_search(frame, COMBO_COCONUT, int(h * 0.01), origin=char_px(w, h, "center"))
        if coconut:
            items.append((*coconut, "combo", TOP_WEIGHT, "combo", COMBO_MOD))
        avoid = [(*p, 2) for p in mob_attacks(frame)]
        if found["orange"]:
            avoid.append((*found["orange"], 2.06))
        return (w, h), items, avoid

    def search(self):
        """The search thread: look at every frame and publish what it sees."""
        try:
            while not self.stopping and not is_stopped():
                if is_paused():
                    time.sleep(0.1)
                    continue
                started = time.monotonic()
                self.seen = (self.seen[0] + 1, self.look(self.macro.mondoFrame()))
                time.sleep(max(0, started + SEARCH_TICK - time.monotonic()))
        except Exception as error:
            self.error = error

    def refresh(self):
        """Plan the newest frame once."""
        number, seen = self.seen
        if number == self.planned or seen is None:
            return
        self.planned = number
        self.size, items, self.avoid = seen
        self.integrate()
        plan = plan_targets(items, self.avoid, self.size, self.yaw, self.offset)
        if plan:
            self.plan, self.planFrame, self.targetAt = plan, number, time.monotonic()

    def newPlan(self):
        """True when a frame newer than the last one walked has a target, or the targets have
        been gone for a moment."""
        self.refresh()
        return self.planFrame > self.walked or time.monotonic() - self.targetAt >= TARGET_GRACE

    def hasTarget(self):
        self.refresh()
        return self.planFrame > self.walked

    # --- the fight ---

    def run(self):
        try:
            self.start()
            self.thread = threading.Thread(target=self.search, daemon=True)
            self.thread.start()
            while self.seen[1] is None and not is_stopped() and not self.error:
                time.sleep(0.01)
            end = time.monotonic() + FIGHT_SECONDS
            while not is_stopped():
                if self.macro.checkPauseAndWait():
                    break
                if self.error:
                    raise self.error
                if time.monotonic() >= end:
                    return "time"
                outcome = self.check()
                if outcome:
                    return outcome
                self.step()
                sleep(1 / 60)
            return "stopped"
        finally:
            self.stopping = True
            thread = getattr(self, "thread", None)
            if thread:
                thread.join(1)
            self.keyboard.releaseMovement()

    def start(self):
        """Zoom, pitch and yaw, then the sprinkler."""
        for _ in range(5):
            self.keyboard.press("o")
        self.macro.configureAIGatherCamera()
        turn = self.yaw if self.yaw <= 4 else self.yaw - 8
        for _ in range(abs(turn)):
            self.keyboard.press("." if turn > 0 else ",")
        if self.field == "mountain top":
            self.send(4.6, "a")
            self.send(0.7, "w", "a")
        sleep(0.9)
        self.greenUntil = time.monotonic() + GREEN_SECONDS
        self.macro.placeSprinkler()
        self.offset, self.fixTime = [0.0, 0.0], time.monotonic()

    def step(self):
        self.refresh()
        if self.planFrame > self.walked:
            self.walked = self.planFrame
            self.getting = True
            self.walkPlan()
        elif time.monotonic() - self.targetAt >= TARGET_GRACE:
            self.route()

    def walkPlan(self):
        first, *rest = self.plan
        x, y, _, kind, mod = first
        x, y = x + mod[0], y + mod[1]
        if kind in STAY_DIAMETER and math.hypot(x, y) <= STAY_DIAMETER[kind] * 0.5:
            x, y = x * 0.25, y * 0.25
        targets = [(x, y)] + [(c[0] + c[4][0], c[1] + c[4][1]) for c in rest]
        if abs(x) < 0.1 and abs(y) < 0.1 and not rest:
            return
        obstacles = [(*px_to_flowers(a[0], a[1], *self.size), a[2] if len(a) > 2 else 2) for a in self.avoid]
        self.walkTo(targets, obstacles, self.newPlan)

    # --- finding the bee and the sprinkler ---

    def align(self):
        """The point to walk to: the health bar, else the sprinkler. After a few misses in a row the
        character walks back to the field's corner."""
        macro = self.macro
        found = None
        for attempt in range(2):
            frame = macro.mondoFrame()
            bar = macro.mondoHealthBar(frame, False)
            if bar:
                self.greenUntil = 0     # red is showing: green is no longer looked for
            elif time.monotonic() < self.greenUntil:
                bar = macro.mondoHealthBar(frame, True)
            if bar:
                h = frame.shape[0]
                found = (bar[0], bar[1] + 0.01 * h)
                break
            sleep(1 / 60)
        if not found:
            found = self.sprinklerSearch()
        if not found:
            self.hold()
            self.missed += 1
            if self.missed > 2:
                if self.field not in NO_JUMP:
                    self.setSpace(True)
                self.fixTime = None
                self.fieldAlign()
        return found

    def fieldAlign(self):
        send, field = self.send, self.field
        if field == "spider":
            send(16.26, "w", "a"), send(4, "a"), send(11, "s", "d")
        elif field in ("clover", "cactus"):
            send(12, "d"), send(3, "a")
        elif field == "rose":
            send(12, "d"), self.setSpace(True), send(12, "d", "s")
        elif field == "mountain top":
            send(20, "d"), send(20, "s", "d"), send(2, "w", "a")
            self.keyboard.press("o")
            send(12, "w", "a")
        elif field == "pepper":
            send(24, "w", "a"), self.setSpace(True), send(12, "w"), send(12, "s", "d")

    def sprinklerSearch(self):
        """The sprinkler's screen point, or None. A sprinkler in its own colours also corrects the
        character offset."""
        macro = self.macro
        frame = macro.mondoFrame()
        h, w = frame.shape[:2]
        sides = [[v * h for v in side] for side in ((SIDES_B, SIDES_A) if self.yaw in (2, 6) else (SIDES_A, SIDES_B))]
        widths, heights = sides
        colours = list(SPRINKLER_COLOURS)
        beesmas = bool(macro.beesmas)
        if not beesmas:
            for lst in (colours, widths, heights):
                del lst[4], lst[2]
        first_extra, cutoff = (5, 4) if beesmas else (3, 2)
        variances, count = [0] * len(colours), len(colours)
        for j, edge, middle in [(j, 10, 30) for j in range(first_extra, count)] + [(1, 5, 20)]:
            wide_w, wide_h = widths[j] * 2, heights[j] * 2
            if wide_w <= wide_h:
                wide_w = min(wide_w, h * 0.032)
            else:
                wide_h = min(wide_h, h * 0.032)
            variances.append(range_variance(colours[j], edge, middle))
            colours.append(colours[j])
            widths.append(wide_w)
            heights.append(wide_h)

        def search(shot):
            for i, colour in enumerate(colours):
                point = rect_search(shot, colour, variances[i], widths[i], heights[i])
                if point:
                    return i, point
            return None, None

        i, point = search(frame)
        if point is None:
            return None
        fog, hit = -1, False
        if i <= cutoff:
            fog, hit = (3 if i == 2 and not beesmas else i), True
        if i >= 5 or (i >= 3 and not beesmas):
            again_i, again = search(macro.mondoFrame())
            if again:
                point = again
        shift = 0.02 * h
        sx, sy = point
        if hit:
            if fog == self.fog:
                fx, fy = px_to_flowers(sx, sy + shift, w, h)
                self.offset = list(rotate(-fx, -fy, -self.yaw))
                self.fixTime = time.monotonic()
            if self.lastFog == fog:
                self.fog = fog
            self.lastFog = fog
        else:
            fx, fy = px_to_flowers(sx, sy, w, h)
            if fx * fx + fy * fy > 25:
                cx, cy = char_px(w, h)
                sx, sy = point_along_line(cx, cy, sx, sy, 5, w, h)
        return sx, sy + shift

    # --- the route when no target is in sight ---

    def route(self):
        now = time.monotonic()
        if self.octos >= 4 and now < self.recollectUntil:
            self.collecting, self.tokenSeq = False, 0
            self.getting = False
            found = self.align()
            if found:
                self.goTo(found)
                self.setSpace(False)
            return
        if not self.collecting:
            self.recollectUntil = now + RECOLLECT_SECONDS
            self.octos = 0
        if self.tokenSeq == 8:
            self.tokenSeq = 0
        lastIdx = self.idx
        if self.tokenSeq == 0:
            self.idx += 1
            self.octos += 1
            if self.idx == 3:
                self.idx = 4
                self.octos += 1
            if self.idx == 7:
                self.idx = 0
                self.octos += 1
            if self.idx == 8:
                self.idx = 0
        found = None
        if self.getting or not self.tokenSeq:
            self.getting = False
            found = self.align()
            if found:
                self.collectSeq = (self.collectSeq + 1) % 8
                corner = CORNERS[self.collectSeq]
                self.token = (corner[0] * DIAMETERS[self.idx], corner[1] * DIAMETERS[self.idx])
                self.goTo(found, self.token)
                self.setSpace(False)
            elif not self.collecting:
                self.walkTo([self.token], until=self.hasTarget)
            else:
                corner = CORNERS[self.collectSeq]
                self.collectSeq = (self.collectSeq + 1) % 8
                last = (corner[0] * DIAMETERS[lastIdx], corner[1] * DIAMETERS[lastIdx])
                self.walkTo([(self.token[0] - last[0], self.token[1] - last[1])], until=self.hasTarget)
        if self.tokenSeq or not found:
            first, second = LEGS[self.collectSeq]
            self.collectSeq = (self.collectSeq + 1) % 8
            span = DIAMETERS[self.idx] * 0.202 * FLOWER_TILES
            self.hold(*first)
            try:
                done = self.keyboard.tileWait(span, until=self.hasTarget)
                if done:
                    self.hold(*second)
                    self.keyboard.tileWait(span, until=self.hasTarget)
            finally:
                self.hold()
        self.collecting = True
        self.tokenSeq += 1
