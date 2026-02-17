self.runPath("collect/wreath")
self.keyboard.keyDown("s")
sleep(1.5)
self.keyboard.keyUp("s")
self.keyboard.press("a", 0.5)
self.keyboard.keyDown("s")
sleep(2)
self.keyboard.keyUp("s")
self.keyboard.press("w", 1)
for _ in range(10):
    self.keyboard.press("a", 0.1)
    if self.isBesideE(["talk", "black"]):
        for _ in range(2):
            self.keyboard.press("e")
            sleep(0.2)
            self.keyboard.press("e")
            sleep(0.5)
            self.clickdialog(self, mustFindDialog=False)
        break