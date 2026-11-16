# Starts at the foot of the hive ramp. Walk diagonally back and left, turn around, walk forward then right to the center.
self.keyboard.multiTileWalk(["s", "a"], 67.5)
for _ in range(4):
    self.keyboard.press(".")
self.keyboard.tileWalk("w", 23.5)
self.keyboard.multiTileWalk(["w", "d"], 31.5)
self.keyboard.tileWalk("d", 10)
for _ in range(2):
    self.keyboard.press(".")
