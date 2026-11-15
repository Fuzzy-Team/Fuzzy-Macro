# pine tree to pumpkin. Starts at the center of pine tree facing north (the gather facing).
# Ends where cannon_to_field/pumpkin.py ends, so goToField can finish with faceDirection.
# center to corner
self.keyboard.press(",")
self.keyboard.press(",")
self.keyboard.multiWalk(["w", "d"], (70 + 10)/28)
self.keyboard.walk("d", (30 + 10)/28)
# corner to corner
self.keyboard.press(".")
self.keyboard.press(".")
self.keyboard.multiWalk(["s", "d"], 80/28)
self.keyboard.walk("d", 190/28)
self.keyboard.multiWalk(["w", "d"], (30 + 10)/28)
self.keyboard.walk("w", (10 + 10)/28)
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
