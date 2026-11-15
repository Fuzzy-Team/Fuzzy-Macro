# pine tree to strawberry. Starts at the center of pine tree facing north (the gather facing).
# Ends where cannon_to_field/strawberry.py ends, so goToField can finish with faceDirection.
# center to corner
self.keyboard.press(",")
self.keyboard.press(",")
self.keyboard.multiWalk(["w", "d"], (70 + 10)/28)
self.keyboard.walk("d", (30 + 10)/28)
# corner to corner
self.keyboard.press(".")
self.keyboard.press(".")
self.keyboard.multiWalk(["s", "d"], 160/28)
self.keyboard.walk("d", 40/28)
self.keyboard.multiWalk(["s", "d"], 90/28)
self.keyboard.walk("s", 20/28)
sleep(0.4)
self.keyboard.multiWalk(["w", "a"], 40/28)
self.keyboard.walk("a", 76/28)
# to center
self.keyboard.multiWalk(["s", "a"], 65/28)
self.keyboard.press(",")
self.keyboard.press(",")
