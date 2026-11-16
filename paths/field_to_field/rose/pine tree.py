# rose to pine tree. Starts at the center of rose facing north (the gather facing).
# Ends where cannon_to_field/pine tree.py ends, so goToField can finish with faceDirection.
# run into the top left corner from anywhere in the field
self.keyboard.walk("w", 5)
self.keyboard.walk("a", 8)
# to center
self.keyboard.press(",")
self.keyboard.press(",")
self.keyboard.walk("s", 70/28)
self.keyboard.walk("d", 270/28)
self.keyboard.press(".")
self.keyboard.press(".")
