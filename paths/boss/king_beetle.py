# get into area
self.keyboard.keyDown("a")
sleep(1)
self.keyboard.keyUp("a")
self.keyboard.keyDown("w")
sleep(4)
self.keyboard.keyUp("w")

sleep(0.5)
self.keyboard.walk("d", 1)
self.keyboard.walk("s", 0.05)
self.keyboard.walk("d", 4)
self.keyboard.walk("w", 0.05)

self.keyboard.walk("a", 0.1)
self.keyboard.walk("s", 0.75)

self.keyboard.press("space")
self.keyboard.walk("s", 0.175)
self.keyboard.walk("d", 0.3)

#back right corner
self.keyboard.walk("s", 5.5)
self.keyboard.walk("d", 6)
self.keyboard.walk("s", 0.7)
#credit to rubicorb.v2 & laganyt for the path