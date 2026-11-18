"""Mondo Chick: finding its health bar, walking to it and fighting it until it is defeated."""
import cv2
import numpy as np
import modules.controls.mouse as mouse
from datetime import datetime
from modules.controls.sleep import is_stopped, pause_aware_time as time, paused_seconds
from modules.screen.imageSearch import captureLogicalBGR

HEALTH_RED = 0x6B131A
HEALTH_GREEN = 0x1FE744
SPRINKLER = 0x01D8FF
LOST_AFTER_MISSES = 11      # health bar not seen this many times in a row: give up on this mondo
RED_ONLY_AFTER = 10         # seconds of looking for red and green before only red is looked for
# After the bar is seen, the walk aims this far (right, down) from it. At loop 200-202 it changes,
# and at 202 the counter starts again.
AIM = {200: (7.5, 1.7), 201: (7.5, 0.3), 202: (9.7, 1)}


def _firstPixel(frame, color, variation=0, rightToLeft=False, run=0):
    """First pixel of the colour, scanning rows from the top and each row left to right (or right to
    left). With run > 0 the colour must also continue for that many pixels below it."""
    bgr = np.array([color & 255, color >> 8 & 255, color >> 16 & 255])
    hits = cv2.inRange(frame, np.clip(bgr - variation, 0, 255).astype(np.uint8),
                       np.clip(bgr + variation, 0, 255).astype(np.uint8)) > 0
    colored = hits.copy()
    for step in range(1, run + 1):
        below = np.zeros_like(hits)
        below[:-step] = colored[step:]
        hits &= below
    if rightToLeft:
        hits = hits[:, ::-1]
    first = int(hits.argmax())
    if not hits.flat[first]:
        return None
    row, col = divmod(first, hits.shape[1])
    return (hits.shape[1] - 1 - col if rightToLeft else col), row


def _middle(points):
    points = [point for point in points if point]
    if not points:
        return None
    return sum(x for x, _ in points) / len(points), sum(y for _, y in points) / len(points)


class MondoMixin:
    def mondoFrame(self):
        window = self.robloxWindow
        return captureLogicalBGR(window.mx, window.my, window.mw, window.mh)

    def mondoHealthBar(self, frame, withGreen):
        """The health bar's position as the middle of what is found scanning from the left and from
        the right. Red wins; green is only used when asked and there is no red."""
        run = int(frame.shape[0] * 0.002)
        both = lambda color: _middle([_firstPixel(frame, color, run=run), _firstPixel(frame, color, rightToLeft=True, run=run)])
        return both(HEALTH_RED) or (both(HEALTH_GREEN) if withGreen else None)

    def mondoSprinkler(self):
        return _firstPixel(self.mondoFrame(), SPRINKLER, 8)

    def mondoGoTo(self, x, y, offsetX=0, offsetY=0):
        """Walk to the screen point plus an offset in tiles: the diagonal and the straight part,
        in the order that keeps the path shortest."""
        window = self.robloxWindow
        w, h = window.mw, window.mh
        factor = (24.4 - 5.8 * (y / h or 0.001)) / h    # the camera looks down, so a pixel is longer near the top
        dx = (x - w * 0.5) * factor + offsetX
        dy = (y - h * 0.5) * factor + offsetY
        if abs(dx) < 0.1 and abs(dy) < 0.1:
            return
        keyX, keyY = ("d" if dx > 0 else "a"), ("s" if dy > 0 else "w")
        (major, long), (minor, short) = (((keyX, abs(dx)), (keyY, abs(dy))) if abs(dx) > abs(dy)
                                         else ((keyY, abs(dy)), (keyX, abs(dx))))
        keyboard = self.keyboard
        try:
            if short * 1.414 > long - short:
                keyboard.keyDown(major, False)
                keyboard.keyDown(minor, False)
                keyboard.tileWait(short * 1.414)
                keyboard.keyUp(minor, False)
                keyboard.tileWait(long - short)
            else:
                keyboard.keyDown(major, False)
                keyboard.tileWait(long - short)
                keyboard.keyDown(minor, False)
                keyboard.tileWait(short * 1.414)
        finally:
            keyboard.keyUp(major, False)
            keyboard.keyUp(minor, False)

    def mondoFight(self, endTime=None):
        """Attack mondo until it is defeated. Mondo is found by its health bar and walked up to; when
        the bar is lost a growing search runs around the spot. Returns why it ended: "defeated",
        "time" (minute 15 or endTime), "died", "lost" (the bar was not found for too long) or "stopped".
        self.mondoSeen says whether mondo or its message was seen."""
        window = self.robloxWindow
        self.mondoSeen = False
        mouse.moveTo(window.mx + 350, window.my + 120)
        mouse.mouseDown()
        try:
            anchored = self.placeSprinkler()    # to come back to when the search wanders off
            startedAt = time.monotonic()
            loops = misses = 0
            recentered = False
            offsetX, offsetY = AIM[202]
            while not is_stopped():
                pausedBefore = paused_seconds()
                if self.checkPauseAndWait():
                    break
                if paused_seconds() > pausedBefore:   # pausing releases the mouse
                    mouse.moveTo(window.mx + 350, window.my + 120)
                    mouse.mouseDown()
                loops += 1
                if misses > 7 and not recentered and anchored:
                    sprinkler = self.mondoSprinkler()
                    if sprinkler:
                        recentered = True
                        self.mondoGoTo(*sprinkler)
                screen = self.blueTextScreen()
                if self.blueTextImageSearch("defeated", screen=screen) and self.blueTextImageSearch("mondo", screen=screen):
                    self.mondoSeen = True
                    return "defeated"
                if self.blueTextImageSearch("died", screen=screen):
                    return "died"
                now = datetime.now()
                if misses > LOST_AFTER_MISSES:
                    return "lost"
                if now.minute + now.second / 60 >= 15 or (endTime and now > endTime):
                    return "time"
                lookingForGreen = time.monotonic() - startedAt < RED_ONLY_AFTER
                bar = self.mondoHealthBar(self.mondoFrame(), lookingForGreen)
                if bar:
                    self.mondoSeen = True
                    misses = 0
                    recentered = False
                    if loops < 200:
                        offsetX, offsetY = AIM[202]
                    elif loops in AIM:
                        offsetX, offsetY = AIM[loops]
                        if loops == 202:
                            loops = 0
                    self.mondoGoTo(*bar, offsetX, offsetY)
                else:
                    misses += 1
                    keys = {1: ("a", "s"), 2: ("s", "d"), 3: ("d", "w"), 0: ("w", "a")}[misses % 4]
                    self.keyboard.multiWalk(keys, misses, False)
                if misses % 4 == 0 and now.minute + now.second / 60 < 0.1:
                    misses = 0      # the hour has just started and mondo has not spawned yet
            return "stopped"
        finally:
            mouse.moveTo(window.mx + 350, window.my + 150)
            mouse.mouseUp()
