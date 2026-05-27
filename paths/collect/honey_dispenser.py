hiveSlot = int(self.setdat.get("hive_number", 3) or 3)

self.keyboard.tileWalk("w", 1)
self.keyboard.tileWalk("a", 9.2 * (7 - hiveSlot) + 10)
self.keyboard.multiTileWalk(["s", "d"], 2)
self.keyboard.tileWalk("s", 2)
