# Starts at the foot of the hive ramp. Walk back and left, turn around, go around the pond, then forward and right to the center.
self.keyboard.multiTileWalk(["s", "a"], 67.5)
for _ in range(4):
    self.keyboard.press(".")
self.keyboard.tileWalk("w", 30)
self.keyboard.multiTileWalk(["w", "d"], 20)
for _ in range(2):
    self.keyboard.press(".")
self.keyboard.tileWalk("w", 43.5)
self.keyboard.tileWalk("d", 18)
self.keyboard.tileWalk("w", 6)
for _ in range(2):
    self.keyboard.press(",")
self.keyboard.tileWalk("w", 43)
self.keyboard.multiTileWalk(["w", "d"], 30)
self.keyboard.tileWalk("d", 24)
self.keyboard.tileWalk("s", 10)
for _ in range(2):
    self.keyboard.press(".")
