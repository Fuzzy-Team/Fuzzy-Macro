
self.keyboard.slowPress(",")
self.keyboard.slowPress(",")
self.keyboard.slowPress(",")
self.keyboard.slowPress("e")
self.keyboard.slowPress("space")
self.keyboard.slowPress("space")
#walk forward only briefly once gliding, longer overshoots onto the mushroom caps at the far edge
self.keyboard.keyDown("w")
sleep(0.3)
self.keyboard.keyUp("w")
self.keyboard.slowPress("space")
self.keyboard.slowPress(",")
#self.keyboard.walk("s",0.4)
sleep(1)


