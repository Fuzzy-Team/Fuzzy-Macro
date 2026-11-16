# strawberry to spider. Starts at the center of strawberry facing north (the gather facing).
# Ends where cannon_to_field/spider.py ends, so goToField can finish with faceDirection.
# run into the top right corner from anywhere in the field
self.keyboard.walk("w", 5)
self.keyboard.walk("d", 5)
# corner to corner
self.keyboard.press("space", 0.1)
sleep(0.2)
self.keyboard.walk("d", 70/28)
self.keyboard.walk("a", (40 + 16)/28)
# to center
self.keyboard.multiWalk(["s", "d"], 70/28)
