# strawberry to mushroom. Starts at the center of strawberry facing north (the gather facing).
# Ends where cannon_to_field/mushroom.py ends, so goToField can finish with faceDirection.
# center to corner
self.keyboard.multiWalk(["w", "d"], (70 + 10)/28)
self.keyboard.walk("w", (20 + 10)/28)
# to center
self.keyboard.walk("s", (71 + 69)/28)
self.keyboard.multiWalk(["s", "d"], 65/28)
self.keyboard.walk("w", 5/28)
