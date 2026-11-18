self.keyboard.press("e", 0.1)
# Glide back and left off the cannon toward Mountain Top.
self.keyboard.keyDown("a")
self.keyboard.keyDown("s")
sleep(1.4)
self.keyboard.slowPress("space")
self.keyboard.slowPress("space")
sleep(1.1)
self.keyboard.keyUp("a")
sleep(0.65)
self.keyboard.keyUp("s")
self.keyboard.slowPress("space")
for _ in range(4):
    self.keyboard.slowPress(".")
sleep(1.5)
# Walk along the wall past the Clover dispenser to the 30 bee gate, then through it and up to the summit.
self.keyboard.multiTileWalk(["d", "w"], 4)
self.keyboard.tileWalk("w", 23)
self.keyboard.tileWalk("a", 25)
self.keyboard.tileWalk("w", 50)
self.keyboard.press("space", 0.05)
self.keyboard.tileWalk("w", 40)
self.keyboard.press("space", 0.05)
# Walk left onto the blue ringed pad beside the white Lid Art disk.
self.keyboard.tileWalk("w", 1)
self.keyboard.tileWalk("a", 5)
for _ in range(6):
    if self.isBesideE(["talk", "onett"]):
        break
    self.keyboard.tileWalk("a", 0.7)
# Onett stands just past the far side of the pad: step toward him until his prompt shows.
for key in ["w"] * 6 + ["a"] * 4:
    sleep(0.4)
    if self.isBesideE(["talk", "onett"]):
        break
    self.keyboard.tileWalk(key, 0.5)
