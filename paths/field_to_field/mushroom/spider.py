# mushroom to spider. Starts at the center of mushroom facing north (the gather facing).
# Ends where cannon_to_field/spider.py ends, so goToField can finish with faceDirection.
# run into the top left corner from anywhere in the field
self.keyboard.walk("w", 5)
self.keyboard.walk("a", 8)
# to center
self.keyboard.walk("d", 65/28)
self.keyboard.press("space", 0.1)
sleep(0.1)
self.keyboard.walk("w", 12/28)
self.keyboard.walk("w", 30/28)
self.keyboard.multiWalk(["w", "d"], 50/28)
