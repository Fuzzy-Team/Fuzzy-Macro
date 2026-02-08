self.runPath("collect/stockings")
self.keyboard.keyDown("a")
sleep(1)
self.keyboard.press(" ")
sleep(2)
self.keyboard.keyUp("a")

# slowly walk back until e is visible again
for _ in range(10):
    if self.isBesideE(["talk", "brown"]):
        break
    self.keyboard.keyDown("d")
    sleep(0.1)
    self.keyboard.keyUp("d")