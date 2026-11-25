# Starts at the hive: walk to the bottom of the ramp, then out past Sunflower.
self.walkToRamp()
self.keyboard.tileWalk("s", 9)
self.keyboard.multiTileWalk(["s", "d"], 7)
for _ in range(4):
    self.keyboard.slowPress(".")
self.keyboard.tileWalk("w", 49)
self.keyboard.tileWalk("d", 10)
# Small steps with a prompt check after each, right first, then back left in case the character stepped past her.
for i in range(20):
    sleep(0.3)
    if self.isBesideE(["talk", "mother"]):
        break
    self.keyboard.tileWalk("d" if i < 12 else "a", 0.5)
