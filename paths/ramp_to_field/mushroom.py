
# Starts at the foot of the hive ramp. Walk diagonally back and left, turn around, walk to the center.
self.keyboard.multiTileWalk(["s", "a"], 36)
for _ in range(4):
    self.keyboard.press(".")
self.keyboard.tileWalk("w", 31.5)
