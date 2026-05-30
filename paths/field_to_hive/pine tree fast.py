hiveSlot = int(self.setdat.get("hive_number", 3) or 3)

# Camera angle adjustment (RotUp x11, RotDown x4)
for _ in range(11):
    self.keyboard.press(".")
time.sleep(0.1)
for _ in range(4):
    self.keyboard.press(",")

# Zoom in x5
for _ in range(5):
    self.keyboard.press(".")
    time.sleep(0.05)

# Walking route to glider launch point
self.keyboard.multiTileWalk(["a", "w"], 15)
self.keyboard.tileWalk("w", 6)
self.keyboard.tileWalk("a", 6)
self.keyboard.multiTileWalk(["s", "d"], 23)
self.keyboard.tileWalk("s", 36)
self.keyboard.multiTileWalk(["s", "d"], 7)
self.keyboard.tileWalk("s", 8)

# Brief jump
self.keyboard.press("space", 0.1)

self.keyboard.tileWalk("s", 5)
time.sleep(0.5)
self.keyboard.tileWalk("d", 3)
self.keyboard.tileWalk("w", 7)
self.keyboard.tileWalk("s", 8)
time.sleep(0.3)

# Rotate camera left x3
for _ in range(3):
    self.keyboard.press(",")
time.sleep(0.1)

# Activate glider (E), start moving forward
self.keyboard.press("e", 0.01)
self.keyboard.keyDown("w")
time.sleep(0.01)

# Double jump to enable glider
for _ in range(2):
    self.keyboard.press("space", 0.2)
    time.sleep(0.2)

time.sleep(0.15)
self.keyboard.slowPress(",")  # RotLeft to aim glide trajectory
time.sleep(3.25)              # glide duration
self.keyboard.keyUp("w")
self.keyboard.press("space")
time.sleep(0.5)

# Post-landing adjustment
self.keyboard.tileWalk("s", 3.5)
self.keyboard.tileWalk("d", 25)
self.keyboard.multiTileWalk(["w", "d"], 5)
self.keyboard.tileWalk("s", 4)
self.keyboard.tileWalk("a", 9.2 * hiveSlot - 4)

# Zoom out x4
for _ in range(4):
    self.keyboard.press("o")
    time.sleep(0.05)
time.sleep(0.1)
