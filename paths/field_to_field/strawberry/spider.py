# strawberry to spider. Starts at the center of strawberry facing north (the gather facing).
# Ends where cannon_to_field/spider.py ends, so goToField can finish with faceDirection.
# center to corner
self.keyboard.multiWalk(["w", "d"], (70 + 10)/28)
self.keyboard.walk("w", (20 + 10)/28)
# corner to corner
self.keyboard.press("space", 0.1)
sleep(0.2)
self.keyboard.walk("d", 70/28)
self.keyboard.walk("a", (40 + 16)/28)
# to center
self.keyboard.multiWalk(["s", "d"], 70/28)
