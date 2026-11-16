# Starts at the foot of the hive ramp. Walk back and left, turn around, weave past the fence, climb the mountain, then forward to the center.
self.keyboard.multiTileWalk(["s", "a"], 67.5)
for _ in range(4):
    self.keyboard.press(".")
self.keyboard.tileWalk("w", 31)
self.keyboard.tileWalk("a", 7.8)
self.keyboard.tileWalk("s", 10)
self.keyboard.tileWalk("d", 5)
self.keyboard.tileWalk("w", 1.5)
self.keyboard.tileWalk("a", 60)
self.keyboard.tileWalk("d", 3.75)
self.keyboard.tileWalk("w", 85)
self.keyboard.tileWalk("d", 45)
self.keyboard.tileWalk("s", 50)
self.keyboard.tileWalk("d", 60)
self.keyboard.multiTileWalk(["w", "a"], 15.75)
self.keyboard.tileWalk("w", 13.5)
for _ in range(4):
    self.keyboard.press(".")
