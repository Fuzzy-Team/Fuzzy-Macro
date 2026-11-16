# mountain top to the ramp side of the hive row. Starts at the center of the field facing the hive (after faceDirection south), ends facing the same way.
for _ in range(15):
    self.keyboard.tileWalk("s", 3)
    self.keyboard.tileWalk("a", 1)
self.keyboard.multiTileWalk(["w", "d"], 36)
self.keyboard.tileWalk("w", 100)
self.keyboard.tileWalk("d", 32)
self.keyboard.tileWalk("w", 37)
self.keyboard.tileWalk("s", 1.5)
self.keyboard.tileWalk("d", 35)
self.keyboard.tileWalk("s", 2.7)
