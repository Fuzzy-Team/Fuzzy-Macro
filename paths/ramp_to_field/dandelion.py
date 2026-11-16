# Starts at the foot of the hive ramp. Walk diagonally back and left, then left to the center.
self.keyboard.multiTileWalk(["s", "a"], 39)
self.keyboard.tileWalk("a", 14)
for _ in range(2):
    self.keyboard.press(",")
