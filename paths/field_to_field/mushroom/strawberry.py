# mushroom to strawberry. Starts at the center of mushroom facing north (the gather facing).
# Ends where cannon_to_field/strawberry.py ends, so goToField can finish with faceDirection.
# run into the top left corner from anywhere in the field
self.keyboard.walk("w", 5)
self.keyboard.walk("a", 8)
# corner to corner
self.keyboard.walk("d", 65/28)
self.keyboard.press("space", 0.1)
sleep(0.1)
self.keyboard.walk("w", 12/28)
self.keyboard.walk("w", 30/28)
self.keyboard.multiWalk(["w", "d"], 50/28)
# corner to corner
self.keyboard.multiWalk(["w", "a"], 80/28)
self.keyboard.walk("a", 6/28)
# to center
self.keyboard.walk("s", 60/28)
self.keyboard.walk("a", 71/28)
self.keyboard.walk("w", 9/28)
self.keyboard.press(",")
self.keyboard.press(",")
