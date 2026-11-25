self.keyboard.press("e", 0.1)
sleep(0.5)
for _ in range(4):
    self.keyboard.slowPress(".")
# Glide right off the cannon toward the yellow cannon.
self.keyboard.keyDown("d")
sleep(1)
self.keyboard.slowPress("space")
sleep(0.5)
self.keyboard.slowPress("space")
sleep(2.9)
self.keyboard.keyUp("d")
self.keyboard.tileWalk("s", 10)
self.keyboard.tileWalk("d", 22.5)
for _ in range(4):
    self.keyboard.slowPress(",")
# Line up with the ramp beside the 10 bee gate and climb it to the back wall, then slide right along it to Science Bear.
self.keyboard.tileWalk("a", 5.5)
self.keyboard.tileWalk("w", 32)
self.keyboard.multiTileWalk(["w", "d"], 20)
# The slide stops against the step at the back right of the white disk in front of Science Bear: step back and left onto the disk until his prompt shows.
for _ in range(8):
    sleep(0.4)
    if self.isBesideE(["talk", "science"]):
        break
    self.keyboard.multiTileWalk(["s", "a"], 0.5)
