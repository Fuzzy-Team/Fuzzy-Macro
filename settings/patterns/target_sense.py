import math

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
