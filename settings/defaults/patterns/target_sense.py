# target_sense: Precision, Scorching Star and X-Flame boosting, ported from the original's
# "target sense" gather pattern (decision table, timers, colours and the X-Flame spin follow
# its source). The pattern runs once per gather cycle with its state in globals; where the original
# runs a buff-watcher loop and a target-finder loop, each cycle does both checks instead.
# Timer lengths come from Windows timing and are unverified on macOS.
import math
import time

import cv2
import numpy as np

from modules.misc.sense_patterns import (
    SCORCHING_ACTIVE, SCORCHING_THRESHOLD, SensePattern, SenseStopped,
)
from modules.screen.imageSearch import captureRegionBGR, locateImageOnScreen

# the original matches these icons exactly; Fuzzy matches by similarity, which approximates that.
# They are 3 px and 6 px crops captured on Windows, so a match on macOS is not guaranteed.
ICON_THRESHOLD = 0.8
PRECISION_ICONS = ("./images/buffs/precision_8x", "./images/buffs/precision_9x",
                   "./images/buffs/precision_10x")
X_FLAME_ICON = "./images/buffs/x_flame"

# Timer names are the original's. A timer exists while now < its end time.
PRECISION_SECONDS = {"rose": 54.842, "strawberry": 52.842, "mushroom": 46.842}
PRECISION_DEFAULT_SECONDS = 56.842
SCORCHING_STAR_SECONDS = 45
SCORCHING_STAR_COOLDOWN = 60
X_FLAME_COOLDOWN = 20
NEW_X_FLAME_SECONDS = 3     # the original: 5.2 with Flame Fuel; that icon is not in the reference, so never
BAG_FULL_SECONDS = 10
TARGETS_GRACE_SECONDS = 8 / 60   # the original: 8 frames, and a timer of 8 / max framerate (default 60)

# Fuzzy walks this far (in tiles) per cycle, then looks again. the original walks the whole way
# on a second thread and is told to stop when a new target appears.
STEP_TILES = 2
AVOID_RADIUS = 2.2

# Colours are 0xRRGGBB. A pair bounds each channel between its two colours.
# fog: orange, violet, green, green while Scorching Star runs, purple
TARGET_COLOURS = {
    0: (0xFFCD6B, 0xCD66FF, 0x01FF01, 0x01FF01, 0x7237FF),
    1: ((0xFFCB66, 0xFFCF6A), (0xCE6BFF, 0xCF6BFF), 0x08FF01, 0x08FF01, (0x773EFF, 0x7843FF)),
    2: ((0xFFCC6C, 0xFFD17F), (0xCD67FF, 0xCD84FF), (0x02FF02, 0x20FF2F), (0x02FF02, 0x08FF2F),
        (0x7542FF, 0x7644FF)),
    3: (0xFFD371, 0xDB9FFF, (0x01FF01, 0x20FF2F), (0x01FF01, 0x08FF2F), 0x7237FF),
}
SPRINKLER_COLOURS = ((0x00D7FF, 0x02D9FF), (0x07D6FF, 0x37DAFF), (0x71DAFE, 0x9BE5FF))

field_yaws = {
    "pepper": 2,
    "rose": 0,
    "strawberry": 2,
}


def timer_running(name):
    return boost["timers"].get(name, 0) > time.monotonic()


def start_timer(name, seconds):
    boost["timers"][name] = time.monotonic() + seconds


def stop_timer(name):
    boost["timers"].pop(name, None)


def target_priority():
    """Which targets to chase, from which timers are running (the original's decision table, in
    order). Falling through to the last rule starts the no-hits and hits timers.
    Returns 'hit', 'prec', 'x_flame', 'marks', 'only_prec' or 'hits!o'."""
    if timer_running("full_bag"):
        return "hit"
    if not timer_running("precision"):
        return "prec"
    if (timer_running("scorching_star_cd") and timer_running("build_flames")
            and timer_running("new_x_flame")):
        return "x_flame"
    if timer_running("get_targets"):
        return "marks"
    if timer_running("scorching_star") or not timer_running("x_flame_cd"):
        return "only_prec"
    if timer_running("no_hit"):
        return "hits!o"
    if timer_running("get_hit"):
        return "marks"
    no_hits = self.setdat["target_sense_no_hits_until"]
    start_timer("no_hit", no_hits)
    start_timer("get_hit", no_hits + self.setdat["target_sense_hits_until"])
    return "marks"


def nearest(points, centre):
    return min(points, key=lambda p: (p[0] - centre[0]) ** 2 + (p[1] - centre[1]) ** 2)


def choose_targets(priority, orange, violet, green, purple, hit_waiting, size):
    """the original's target table. Each target is an (x, y) or None. Returns the targets to chase
    and the ones to steer around. Orange and violet are the Precision and mark tokens;
    green and purple are the hit tokens."""
    width, height = size
    hits = [p for p in (green, purple) if p]
    precise = [p for p in (orange, violet) if p]
    if priority == "hit":
        if hit_waiting and hits and precise:
            # source: both distances are measured from the window's top-left corner
            centre = (width * 0.5, height * 0.5)
            far = (height * 0.3) ** 2
            hit_x, hit_y = nearest(hits, centre)
            precise_x, precise_y = nearest(precise, centre)
            if hit_x ** 2 + hit_y ** 2 > far or precise_x ** 2 + precise_y ** 2 > far:
                return hits, []
            return precise, []
        return hits or precise, []
    if priority == "prec":
        return precise or hits, []
    if priority == "only_prec":
        return precise, []
    if priority == "marks":
        return [p for p in (violet,) if p], [p for p in (orange,) if p]
    if priority == "hits!o":
        return hits or [p for p in (violet,) if p], [p for p in (orange,) if p]
    return [], []   # x_flame: the move below is the whole behaviour


def colour_bounds(colour):
    """The (low, high) BGR bounds of a colour or colour pair."""
    first, second = (colour, colour) if isinstance(colour, int) else colour
    channels = [(first >> shift & 255, second >> shift & 255) for shift in (0, 8, 16)]
    return tuple(min(c) for c in channels), tuple(max(c) for c in channels)


def run_of(mask, length):
    """Pixels that match and whose next |length| pixels also match: to the right when length
    is positive, below when negative."""
    out = mask.copy()
    for k in range(1, abs(length) + 1):
        if length > 0:
            out[:, :-k] &= mask[:, k:]
            out[:, -k:] = False
        else:
            out[:-k] &= mask[k:]
            out[-k:] = False
    return out


def pixel_search(shot, colour, safety=0, blob_length=0, blob_size=0, blob_safety=0):
    """the original's pixel search over a whole window capture, in its "center" mode: the (x, y) of
    the matching pixel nearest the middle of the window, or None.

    safety: a match needs |safety| more matching pixels after it (right if positive, below if
    negative). With blob_length and blob_size, a match also needs a blob: inside a square of
    blob_size around it, the first and last matching pixels (counted with blob_safety) must be
    blob_length apart, and the result is the middle of the two."""
    safety, blob_length, blob_safety = int(safety), int(blob_length), int(blob_safety)
    height, width = shot.shape[:2]
    low, high = colour_bounds(colour)
    mask = cv2.inRange(shot, low, high) > 0
    ys, xs = np.nonzero(run_of(mask, safety))
    if not len(xs):
        return None
    origin_x, origin_y = round(width * 0.5), round(height * 0.5)
    order = np.argsort((xs - origin_x) ** 2 + (ys - origin_y) ** 2, kind="stable")
    blob_size = round(blob_size)
    if blob_length <= 0 or blob_size <= 0:
        return int(xs[order[0]]), int(ys[order[0]])
    blob_mask = run_of(mask, blob_safety)
    half = blob_size // 2
    # A blob's middle is within half a square (corner to corner) of the pixel that found it,
    # so nothing farther than best + reach can win.
    reach = half * math.sqrt(2)
    best = None
    best_key = None   # (squared distance, scan position): a tie goes to the pixel scanned first
    for index in order:
        x, y = int(xs[index]), int(ys[index])
        if best is not None and math.hypot(x - origin_x, y - origin_y) - reach > math.sqrt(best_key[0]) + 1e-6:
            break
        left, top = max(0, x - half), max(0, y - half)
        window = blob_mask[top:min(height - 1, y + half) + 1, left:min(width - 1, x + half) + 1]
        flat = window.ravel()
        first = int(flat.argmax())
        if not flat[first]:
            continue
        last = flat.size - 1 - int(flat[::-1].argmax())
        first_y, first_x = divmod(first, window.shape[1])
        last_y, last_x = divmod(last, window.shape[1])
        if (last_x - first_x) ** 2 + (last_y - first_y) ** 2 < blob_length ** 2:
            continue
        found = (left + (first_x + last_x) // 2, top + (first_y + last_y) // 2)
        key = ((found[0] - origin_x) ** 2 + (found[1] - origin_y) ** 2, y * width + x)
        if best is None or key < best_key:
            best, best_key = found, key
    return best


def find_targets(shot, search_all, fog, scorching):
    """The orange, violet, green and purple targets on screen, as (x, y) or None. Marks and
    Precision-only gathering skip the green and purple search."""
    height = shot.shape[0]
    blob_length, blob_size = height * 0.021, height * 0.12
    orange, violet, green, green_scorching, purple = TARGET_COLOURS[fog]
    # source: the safety distances (as a fraction of the window height) grow with fog
    if fog == 0:
        orange_s, violet_s, green_s, purple_s, blob_s = 0.005, 0.003, 0.003, 0.005, 0.003
    else:
        orange_s, violet_s, green_s, purple_s, blob_s = 0.007, 0.004, 0.004, 0.007, 0.006
    found = {
        "orange": pixel_search(shot, orange, height * orange_s, blob_length, blob_size, -height * blob_s),
        "violet": pixel_search(shot, violet, height * violet_s),
        "green": None,
        "purple": None,
    }
    if search_all:
        found["green"] = pixel_search(shot, green_scorching if scorching else green,
                                      height * green_s, blob_length, blob_size, 0)
        found["purple"] = pixel_search(shot, purple, height * purple_s, blob_length, blob_size,
                                       -height * blob_s)
    return found


def sprinkler_colour_index(shot, yaw, limit=2):
    """The first sprinkler colour (up to index limit) found on screen, or None."""
    height = shot.shape[0]
    sign = -1 if yaw in (2, 6) else 1   # source: the checks run the other way for yaw 2 and 6
    safeties = (0.003, 0.003, 0.006)
    blob_safeties = (0.001, 0.001, 0.003)
    for index, colour in enumerate(SPRINKLER_COLOURS[:limit + 1]):
        if pixel_search(shot, colour, sign * height * safeties[index], height * 0.02, height * 0.16,
                        -sign * height * blob_safeties[index]):
            return index
    return None


def read_fog(shot, yaw, new_shot):
    """The fog level from the sprinkler's colour, or None if it is not on screen. Like
    the original, the third colour first reads as fog 3, and any fog above 0 is then searched again
    on a fresh capture (new_shot()) for a colour at or below that level. So the third colour
    settles on 2 and fog 3 only stands if that second look finds nothing."""
    index = sprinkler_colour_index(shot, yaw)
    if index is None:
        return None
    fog = 3 if index == 2 else index
    if fog:
        again = sprinkler_colour_index(new_shot(), yaw, fog)
        if again is not None:
            fog = again
    return fog


def detour(target, obstacle, radius):
    """the original's tangent waypoint: where to aim first so the walk to target (tiles from the
    player) skirts a circle of radius around obstacle, or None if the way is clear."""
    tx, ty = target
    cx, cy = obstacle
    distance = math.hypot(cx, cy)
    if tx * tx + ty * ty < distance * distance - radius * radius:
        return None
    if distance <= radius:
        return -cx, -cy
    theta = math.atan2(cy, cx)
    alpha = math.asin(radius / distance)
    aim = math.atan2(ty, tx)

    def wrap(angle):
        return (angle + math.pi) % (2 * math.pi) - math.pi

    low, high = wrap(theta - alpha), wrap(theta + alpha)
    blocked = low <= aim <= high if low <= high else aim >= low or aim <= high
    if not blocked:
        return None
    reach = math.sqrt(distance * distance - radius * radius)
    left = reach * math.cos(theta + alpha), reach * math.sin(theta + alpha)
    right = reach * math.cos(theta - alpha), reach * math.sin(theta - alpha)

    def gap(a, b):
        return abs((a - b + math.pi) % (2 * math.pi) - math.pi)

    return left if gap(aim, theta + alpha) < gap(aim, theta - alpha) else right


class TargetSense(SensePattern):
    """The Sense engine's input and pause helpers, running the original's buff watcher and target
    finder once per cycle."""

    def run(self):
        try:
            window = self.macro.robloxWindow
            self.w, self.h = window.mw, window.mh
            self.scan()
            priority = target_priority()
            if priority == "x_flame" and boost["timers"]["new_x_flame"] != boost["x_flame_window"]:
                boost["x_flame_window"] = boost["timers"]["new_x_flame"]
                self.x_flame()
            shot = self.screenshot()
            seen = read_fog(shot, self.yaw, self.screenshot)
            if seen is not None:
                if boost["last_fog"] == seen:   # a change counts once it is seen twice in a row
                    boost["fog"] = seen
                boost["last_fog"] = seen
            target, avoid = self.pick(priority, shot)
            if target:
                self.go_to(target, avoid)
            else:
                self.search_step()
            self.hold()
        except SenseStopped:
            self.finish()
        except Exception:
            self.finish()   # the gather falls back to another pattern: don't leave keys held
            raise

    # --- the buff watcher ---

    def icon_in(self, path, x, y, width, height):
        """Look for an icon in a window-relative rectangle."""
        self.idle()
        window = self.macro.robloxWindow
        return locateImageOnScreen(path, window.mx + x, window.my + y, width, height,
                                   ICON_THRESHOLD, scales=[1.0]) is not None

    def scan(self):
        """The bag, then the Precision, Scorching Star and X-Flame icons start, restart and
        stop the timers."""
        # full_bag runs for 10 s once the bag is full or nothing is being collected. the original
        # ends the gather when it runs out; Fuzzy's gather ends on its own backpack limit.
        full = self.macro.getBackpack() >= fieldSetting["backpack"]
        collecting = not full and self.pixel(round(self.w * 0.5 + 256), 39,
                                             round(self.w * 0.5 + 276), 44, 0xFFFFFF, 5)
        if full or not collecting:
            if not boost["bag_timer_started"]:
                start_timer("full_bag", BAG_FULL_SECONDS)
                boost["bag_timer_started"] = True
        else:
            stop_timer("full_bag")
            boost["bag_timer_started"] = False

        # the original reads Scorching Star's stack icon in the bar above the hotbar and starts
        # these timers when it disappears. Fuzzy already has the buff icon in the top row
        # (the Sense patterns use it), which appears at that moment, so the timers start
        # when it shows up, and the star is ready again once it and its 45 s timer are gone.
        scorching = self.icon_visible(SCORCHING_ACTIVE, SCORCHING_THRESHOLD)
        if scorching and boost["scorching_ready"]:
            boost["scorching_ready"] = False
            start_timer("scorching_star_cd", SCORCHING_STAR_COOLDOWN)
            start_timer("scorching_star", SCORCHING_STAR_SECONDS)
            start_timer("get_targets", self.macro.setdat["target_sense_scorch_get_marks"])
            start_timer("build_flames", self.macro.setdat["target_sense_build_flames"])
        elif not scorching and not timer_running("scorching_star"):
            boost["scorching_ready"] = True

        # X-Flame's icon (same bar as the original's: 520 x 26 px, 128 px above the bottom) is
        # shown while it is ready; when it goes, X-Flame is on cooldown.
        if self.icon_in(X_FLAME_ICON, round(self.w * 0.5 - 260), self.h - 128, 520, 26):
            stop_timer("x_flame_cd")
            boost["x_flame_ready"] = True
        elif boost["x_flame_ready"]:
            boost["x_flame_ready"] = False
            start_timer("x_flame_cd", X_FLAME_COOLDOWN)
            start_timer("new_x_flame", NEW_X_FLAME_SECONDS)

        # the original restarts the Precision timer on every look that finds the icon.
        if any(self.icon_visible(path, ICON_THRESHOLD) for path in PRECISION_ICONS):
            seconds = PRECISION_SECONDS.get(str(field).replace("_", " ").lower(), PRECISION_DEFAULT_SECONDS)
            start_timer("precision", seconds - self.macro.setdat["target_sense_refresh_precision"])

    # --- the target finder ---

    def screenshot(self):
        """The Roblox window as a BGR array in window pixels."""
        self.idle()
        window = self.macro.robloxWindow
        shot = captureRegionBGR(window.mx, window.my, self.w, self.h)
        if shot.shape[:2] != (self.h, self.w):
            shot = cv2.resize(shot, (self.w, self.h), interpolation=cv2.INTER_NEAREST_EXACT)
        return shot

    def pick(self, priority, shot):
        """The target to walk to, or None, and the points to steer around."""
        now = time.monotonic()
        found = find_targets(shot, priority not in ("marks", "only_prec"), boost["fog"],
                             timer_running("scorching_star"))
        if any(found.values()):
            boost["targets_until"] = now + TARGETS_GRACE_SECONDS
            if not boost["hit_wait_started"]:
                boost["hit_wait_started"] = True
                start_timer("hit_wait", self.macro.setdat["target_sense_hit_wait"])
        elif now >= boost["targets_until"]:
            # nothing in sight for a moment: the no-hits and hits cycle starts over
            boost["hit_wait_started"] = False
            stop_timer("no_hit")
            stop_timer("get_hit")
        points, avoid = choose_targets(priority, found["orange"], found["violet"], found["green"],
                                       found["purple"], timer_running("hit_wait"), (self.w, self.h))
        if not points:
            return None, avoid
        return nearest(points, (self.w * 0.5, self.h * 0.5)), avoid

    # --- moving ---

    def hold(self, *letters):
        """Hold exactly these screen-direction keys (W A S D), releasing the rest."""
        keep = {letter.lower() for letter in letters}
        script = [f"{key.upper()}-" for key in "wasd" if key in self.held and key not in keep]
        script += [f"{letter}+" for letter in letters if letter.lower() not in self.held]
        self.keys(" ".join(script))

    def tiles(self, x, y):
        """the original's screen pixels to tiles from the player, for the camera pitch it gathers
        at: the camera looks down at an angle, so a pixel is longer near the top."""
        scale = y / self.h or 0.001
        factor = (24.4 - 5.8 * scale) / self.h
        return (x - self.w * 0.5) * factor, (y - self.h * 0.5) * factor

    def go_to(self, target, avoid):
        """the original's short walk: the diagonal and the straight part, in the order it picks,
        steering around the points to avoid. Stops after STEP_TILES so the next cycle can
        look again."""
        goal = self.tiles(*target)
        if abs(goal[0]) < 0.1 and abs(goal[1]) < 0.1:
            return
        waypoints = [goal]
        obstacles = sorted((self.tiles(*spot) for spot in avoid),
                           key=lambda o: o[0] ** 2 + o[1] ** 2, reverse=True)
        for obstacle in obstacles:
            waypoint = detour(waypoints[0], obstacle, AVOID_RADIUS)
            if waypoint:
                waypoints.insert(0, waypoint)
        budget = STEP_TILES
        here = (0, 0)
        for waypoint in waypoints:
            dx, dy = waypoint[0] - here[0], waypoint[1] - here[1]
            here = waypoint
            if abs(dx) < 0.1 and abs(dy) < 0.1:
                continue
            key_x, key_y = ("D" if dx > 0 else "A"), ("S" if dy > 0 else "W")
            (major, long), (minor, short) = (((key_x, abs(dx)), (key_y, abs(dy))) if abs(dx) > abs(dy)
                                              else ((key_y, abs(dy)), (key_x, abs(dx))))
            diagonal = ((major, minor), short * 1.414)
            straight = ((major,), long - short)
            for letters, tiles in ((diagonal, straight) if short * 1.414 > long - short else (straight, diagonal)):
                tiles = min(tiles, budget)
                if tiles <= 0:
                    continue
                self.hold(*letters)
                self.walk(tiles)
                budget -= tiles
                if budget <= 0:
                    return

    def search_step(self):
        """No target: one leg of Fuzzy's small search loop per cycle."""
        steps = ((tcfbkey, 0.45), (tclrkey, 0.12), (afcfbkey, 0.45), (tclrkey, 0.12),
                 (afcfbkey, 0.45), (afclrkey, 0.12), (tcfbkey, 0.45), (afclrkey, 0.12))
        key, seconds = steps[boost["search_step"] % len(steps)]
        boost["search_step"] += 1
        self.hold()
        self.idle()
        self.macro.keyboard.walk(key, seconds)

    def x_flame(self):
        """the original's X-Flame move: the camera turns left eight times (one full circle) in
        pairs, with two steps back between them. the original has this move but the source that
        calls it is missing from the reference; it runs once per new X-Flame window."""
        def turns(count):
            for i in range(count):
                if i:
                    self.wait_ms(50)
                self.idle()
                self.macro.keyboard.press(rotleft)

        def step_back():
            self.hold("S")
            self.walk(0.6)
            self.hold()

        self.hold()
        self.wait_ms(500)
        turns(2)
        step_back()
        self.wait_ms(450)
        turns(2)
        self.wait_ms(450)
        turns(2)
        step_back()
        self.wait_ms(450)
        turns(2)


if "boost" not in globals():
    boost = {"timers": {}, "bag_timer_started": False, "scorching_ready": True,
             "x_flame_ready": True, "x_flame_window": None, "fog": 0, "last_fog": 0,
             "targets_until": 0, "hit_wait_started": False, "search_step": 0}

yaw = field_yaws.get(str(field).replace("_", " ").lower(), 0)
setPatternYaw(yaw)
if "sense" not in globals():
    sense = TargetSense(self, tcfbkey, tclrkey, afcfbkey, afclrkey, rotup, sc_space)
    sense.yaw = yaw
sense.run()


def onGatherEnd():
    sense.finish()
