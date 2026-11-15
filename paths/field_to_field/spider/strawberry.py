# spider to strawberry. Starts at the center of spider facing north (the gather facing).
# Ends where cannon_to_field/strawberry.py ends, so goToField can finish with faceDirection.
# center to corner
self.keyboard.multiWalk(["w", "a"], 80/28)
self.keyboard.walk("a", 6/28)
# to center
self.keyboard.walk("s", 60/28)
self.keyboard.walk("a", 71/28)
self.keyboard.walk("w", 9/28)
self.keyboard.press(",")
self.keyboard.press(",")
