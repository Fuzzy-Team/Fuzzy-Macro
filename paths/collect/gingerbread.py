hiveSlot = int(self.setdat.get("hive_number", 3) or 3)

self.keyboard.tileWalk("w", 5)
self.keyboard.tileWalk("d", 9.2 * hiveSlot - 4)

for _ in range(2):
    self.keyboard.press(".")
self.keyboard.tileWalk("d", 4.7)
self.keyboard.keyDown("space")
self.keyboard.tileWalk("w", 1.5)
self.keyboard.keyUp("space")
sleep(0.6)
self.keyboard.tileWalk("w", 6)
for _ in range(2):
    self.keyboard.press(".")
self.keyboard.tileWalk("w", 25)
self.keyboard.multiTileWalk(["w", "d"], 3)
self.keyboard.tileWalk("w", 15)
self.keyboard.multiTileWalk(["w", "d"], 2)
self.keyboard.tileWalk("w", 13)
sleep(0.6)