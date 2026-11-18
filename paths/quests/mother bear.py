# Starts at the hive: walk to the bottom of the ramp, then out past Sunflower.
self.walkToRamp()
self.keyboard.tileWalk("s", 9)
self.keyboard.multiTileWalk(["s", "d"], 7)
for _ in range(4):
    self.keyboard.slowPress(".")
self.keyboard.tileWalk("w", 49)
self.keyboard.tileWalk("d", 10)
