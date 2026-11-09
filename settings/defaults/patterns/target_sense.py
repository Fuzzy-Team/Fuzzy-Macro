# target_sense: Precision, Scorching Star and X-Flame boosting, ported from Zenith Macro's
# "target sense" gather pattern (decision table, timers, colours and the X-Flame spin follow
# its source). The pattern runs once per gather cycle with its state in globals; where Zenith
# runs a buff-watcher loop and a target-finder loop, each cycle does both checks instead.
# Timer lengths come from Windows timing and are unverified on macOS.
import math
import time

# Timer names are Zenith's. A timer exists while now < its end time.
PRECISION_SECONDS = {"rose": 54.842, "strawberry": 52.842, "mushroom": 46.842}
PRECISION_DEFAULT_SECONDS = 56.842
SCORCHING_STAR_SECONDS = 45
SCORCHING_STAR_COOLDOWN = 60
X_FLAME_COOLDOWN = 20
NEW_X_FLAME_SECONDS = 3     # Zenith: 5.2 with Flame Fuel; that icon is not in the reference, so never
BAG_FULL_SECONDS = 10
TARGETS_GRACE_SECONDS = 8 / 60   # Zenith: 8 frames, and a timer of 8 / max framerate (default 60)


def timer_running(name):
    return boost["timers"].get(name, 0) > time.monotonic()


def start_timer(name, seconds):
    boost["timers"][name] = time.monotonic() + seconds


def stop_timer(name):
    boost["timers"].pop(name, None)


def target_priority():
    """Which targets to chase, from which timers are running (Zenith's decision table, in
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


if "boost" not in globals():
    boost = {"timers": {}}

field_yaws = {
    "pepper": 2,
    "rose": 0,
    "strawberry": 2,
}
setPatternYaw(field_yaws.get(str(field).replace("_", " ").lower(), 0))

window = getattr(self, "robloxWindow", None)
if window is None:
    self.keyboard.walk(tcfbkey, 0.5)
else:
    screen = mssScreenshotNP(window.mx, window.my, window.mw, window.mh)
    bgr = screen[:, :, :3]
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)

    # O/V/G/P target order
    color_ranges = (
        ((5, 80, 100), (28, 255, 255)),
        ((130, 55, 90), (170, 255, 255)),
        ((40, 70, 80), (90, 255, 255)),
        ((100, 70, 80), (135, 255, 255)),
    )
    center_x, center_y = window.mw / 2, window.mh / 2
    target = None
    target_score = -1
    for priority, (lower, upper) in enumerate(color_ranges):
        mask = cv2.inRange(hsv, lower, upper)
        mask[: int(window.mh * 0.10)] = 0
        mask[int(window.mh * 0.95):] = 0
        count, labels, stats, centroids = cv2.connectedComponentsWithStats(mask)
        for component in range(1, count):
            area = int(stats[component, cv2.CC_STAT_AREA])
            if area < max(8, int(window.multi * 8)):
                continue
            x, y = centroids[component]
            distance = math.hypot(x - center_x, y - center_y)
            score = (4 - priority) * 1000 - distance + min(area, 500) * 0.05
            if score > target_score:
                target_score = score
                target = (x, y)

    if target is not None:
        dx = target[0] - center_x
        dy = target[1] - center_y
        dead_zone = max(20, window.mw * 0.035)
        keys = []
        if abs(dx) > dead_zone:
            keys.append(afclrkey if dx < 0 else tclrkey)
        if abs(dy) > dead_zone:
            keys.append(tcfbkey if dy < 0 else afcfbkey)
        if keys:
            duration = min(0.65, max(0.08, math.hypot(dx, dy) / max(window.mw, window.mh) * 1.8))
            self.keyboard.multiWalk(keys, duration)
        else:
            self.keyboard.walk(tcfbkey, 0.08)
    else:
        self.keyboard.walk(tcfbkey, 0.45)
        self.keyboard.walk(tclrkey, 0.12)
        self.keyboard.walk(afcfbkey, 0.45)
        self.keyboard.walk(tclrkey, 0.12)
        self.keyboard.walk(afcfbkey, 0.45)
        self.keyboard.walk(afclrkey, 0.12)
        self.keyboard.walk(tcfbkey, 0.45)
        self.keyboard.walk(afclrkey, 0.12)
