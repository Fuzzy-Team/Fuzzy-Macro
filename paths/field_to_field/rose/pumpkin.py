# rose to pumpkin. Starts at the center of rose facing north (the gather facing).
# Ends where cannon_to_field/pumpkin.py ends, so goToField can finish with faceDirection.
# run into the top left corner from anywhere in the field
self.keyboard.walk("w", 5)
self.keyboard.walk("a", 8)
# corner to corner
self.keyboard.walk("d", 65/28)
self.keyboard.walk("w", 175/28)
self.keyboard.multiWalk(["w", "d"], (210 + 10)/28)
self.keyboard.walk("d", (80 + 10)/28)
# to center
self.keyboard.press(".")
self.keyboard.press(".")
self.keyboard.press(".")
self.keyboard.press(".")
self.keyboard.multiWalk(["w", "d"], 44/28)
self.keyboard.walk("d", 38/28)
self.keyboard.press(".")
self.keyboard.press(".")
self.keyboard.press(".")
self.keyboard.press(".")
