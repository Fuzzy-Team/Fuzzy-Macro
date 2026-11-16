# spider to the ramp side of the hive row. Starts at the center of the field facing the hive (after faceDirection south), ends facing the same way.
self.keyboard.tileWalk("s", 22.5)
self.keyboard.tileWalk("d", 27)
self.keyboard.tileWalk("w", 64)
self.keyboard.multiTileWalk(["w", "d"], 5.5)
self.keyboard.tileWalk("w", 36)
self.keyboard.tileWalk("s", 1.5)
self.keyboard.tileWalk("d", 35)
self.keyboard.tileWalk("s", 2.7)
