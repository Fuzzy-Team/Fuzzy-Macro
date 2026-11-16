# Starts at the foot of the hive ramp. Walk back, then diagonally back and right to the center.
self.keyboard.tileWalk("s", 9)
self.keyboard.multiTileWalk(["s", "d"], 6.75)
for _ in range(2):
    self.keyboard.press(".")
self.keyboard.tileWalk("d", 29)
