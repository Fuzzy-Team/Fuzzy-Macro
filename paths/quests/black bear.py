self.runPath("collect/wreath")
self.keyboard.keyDown("s")
sleep(1.5)
self.keyboard.keyUp("s")
self.keyboard.multiWalk("sa", 1.5)
sleep(0.2)
self.keyboard.press("d", 3)
self.keyboard.press("w", 1)
for _ in range(10):
    self.keyboard.press("a", 0.1)
    if self.isBesideE(["talk", "black"]):
        break