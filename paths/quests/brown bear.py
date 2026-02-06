self.runPath("collect/stockings")
self.keyboard.keydown("a")
self.sleep(1)
self.keyboard.press(" ")
self.sleep(2)
self.keyboard.keyup("a")

# slowly walk back until e is visible again
for _ in range(10):
    if self.checkForImage("collect/e_icon.png", confidence=0.8):
        self.keyboard.press("e")
        break
    self.keyboard.keydown("d")
    self.sleep(0.1)
    self.keyboard.keyup("d")