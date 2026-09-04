# Port of Revolution routes 113 (cannon.20gate) + 018 High (20gate.ant-challenge)
# Ant field / ant challenge pad. Walk studs → Fuzzy walk(studs / 28).

# --- cannon.20gate ---
time.sleep(0.3)
self.keyboard.press("e", 0.05)
time.sleep(0.25)

# Parachute({ [0]=Forward+Left, [2500]=Forward, [4650]=End })
self.keyboard.keyDown("w")
self.keyboard.keyDown("a")
self.keyboard.press("space", 0.05)
self.keyboard.press("space", 0.05)
time.sleep(2.5)
self.keyboard.keyUp("a")
time.sleep(2.15)
self.keyboard.keyUp("w")
time.sleep(1.2)  # SleepAlign — land without closing chute

self.keyboard.walk("d", 50 / 28)  # WalkAlign(Right, 50)
self.keyboard.walk("w", 35 / 28)  # WalkAlign(Forward, 35)

# --- 20gate.ant-challenge (High) ---
# Walk({ [0]=Backward+Left, [20]=Forward, [100]=Left, [155]=Forward,
#        [245]=Right, [285]=Forward, [320]=Left, [385]=End })
self.keyboard.multiWalk(["s", "a"], 20 / 28)
self.keyboard.walk("w", 80 / 28)
self.keyboard.walk("a", 55 / 28)
self.keyboard.walk("w", 90 / 28)
self.keyboard.walk("d", 40 / 28)
self.keyboard.walk("w", 35 / 28)
self.keyboard.walk("a", 65 / 28)

# Checkpoint Walk(Backward, 5)
self.keyboard.walk("s", 5 / 28)
