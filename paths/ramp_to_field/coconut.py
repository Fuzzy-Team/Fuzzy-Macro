# Starts at the foot of the hive ramp. Jump onto the ramp, run right along the top, hop the ledges, then left to the center.
#paths run with self only in the local namespace, so bind it for the helper
def jump(seconds, self=self):
    self.keyboard.press("space", seconds)

try:
    self.keyboard.keyDown("d", False)
    jump(0.1)
    self.keyboard.tileWait(2)
    self.keyboard.keyDown("w", False)
    self.keyboard.tileWait(1.8)
    self.keyboard.keyUp("w", False)
    self.keyboard.tileWait(30)
    self.keyboard.keyUp("d", False)
    jump(0.3)
    self.keyboard.tileWalk("d", 4)
    self.keyboard.tileWalk("w", 5)
    self.keyboard.tileWalk("d", 3)
    jump(0.3)
    self.keyboard.tileWalk("w", 6)
    self.keyboard.multiTileWalk(["a", "w"], 2)
    self.keyboard.tileWalk("w", 8)
    self.keyboard.keyDown("w", False)
    self.keyboard.keyDown("d", False)
    self.keyboard.tileWait(11)
    self.keyboard.keyDown("space", False)
    self.keyboard.keyUp("d", False)
    sleep(0.2)
    self.keyboard.keyUp("space", False)
    sleep(1.1)
    jump(0.2)
    self.keyboard.tileWait(18)
    self.keyboard.keyUp("w", False)
finally:
    for key in ("space", "w", "d"):
        self.keyboard.keyUp(key, False)
self.keyboard.tileWalk("a", 13.5)
