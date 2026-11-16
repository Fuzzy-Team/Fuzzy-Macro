# Starts at the foot of the hive ramp. Walk diagonally back and left, turn around, then forward and left to the center.
self.keyboard.multiTileWalk(["s", "a"], 67.5)
for _ in range(4):
    self.keyboard.press(".")
self.keyboard.tileWalk("w", 31.5)
self.keyboard.multiTileWalk(["a", "w"], 13)
