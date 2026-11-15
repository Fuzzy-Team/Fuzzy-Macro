# spider to mushroom. Starts at the center of spider facing north (the gather facing).
# Ends where cannon_to_field/mushroom.py ends, so goToField can finish with faceDirection.
# center to corner
self.keyboard.multiWalk(["w", "a"], 80/28)
self.keyboard.walk("a", 6/28)
# to center
self.keyboard.walk("d", 4/28)
self.keyboard.walk("s", 156/28)
