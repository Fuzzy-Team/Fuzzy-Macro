# pine tree to rose. Starts at the center of pine tree facing north (the gather facing).
# Ends where cannon_to_field/rose.py ends, so goToField can finish with faceDirection.
# center to corner
self.keyboard.press(",")
self.keyboard.press(",")
self.keyboard.multiWalk(["w", "d"], (70 + 10)/28)
self.keyboard.walk("d", (30 + 10)/28)
# to center
self.keyboard.press(",")
self.keyboard.press(",")
self.keyboard.walk("a", 40/28)
self.keyboard.walk("w", 390/28)
self.keyboard.press(".")
self.keyboard.press(".")
