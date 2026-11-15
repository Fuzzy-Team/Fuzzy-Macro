# mushroom to spider. Starts at the center of mushroom facing north (the gather facing).
# Ends where cannon_to_field/spider.py ends, so goToField can finish with faceDirection.
# center to corner
self.keyboard.walk("a", 19/28)
self.keyboard.multiWalk(["w", "a"], (71 + 10)/28)
self.keyboard.walk("w", (10 + 10)/28)
# to center
self.keyboard.walk("d", 65/28)
self.keyboard.press("space", 0.1)
sleep(0.1)
self.keyboard.walk("w", 12/28)
self.keyboard.walk("w", 30/28)
self.keyboard.multiWalk(["w", "d"], 50/28)
