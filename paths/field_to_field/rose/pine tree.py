# rose to pine tree. Starts at the center of rose facing north (the gather facing).
# Ends where cannon_to_field/pine tree.py ends, so goToField can finish with faceDirection.
# center to corner
self.keyboard.walk("a", 20/28)
self.keyboard.multiWalk(["w", "a"], (71 + 10)/28)
self.keyboard.walk("a", (14 + 10)/28)
# to center
self.keyboard.press(",")
self.keyboard.press(",")
self.keyboard.walk("s", 70/28)
self.keyboard.walk("d", 270/28)
self.keyboard.press(".")
self.keyboard.press(".")
