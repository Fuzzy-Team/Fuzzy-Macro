self.runPath("collect/wreath")
self.keyboard.keyDown("s")
sleep(1.5)
self.keyboard.keyUp("s")
self.keyboard.press("a", 0.5)
self.keyboard.keyDown("s")
sleep(2)
self.keyboard.keyUp("s")
self.keyboard.press("w", 1)
for _ in range(5):
    self.keyboard.keyPress("a", 0.1)
    if self.isBesideE(["talk", "black"]):
        break