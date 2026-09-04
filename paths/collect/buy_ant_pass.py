# Port of Revolution routes 113 + 019 + 033
# cannon.20gate → 20gate.ant-pass → ant-pass.ant-shop (buy ant pass)

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

# --- 20gate.ant-pass ---
# Walk({ [0]=Backward+Left, [20]=Forward, [80]=Left, [136]=Forward, [200]=Left, [260]=End })
self.keyboard.multiWalk(["s", "a"], 20 / 28)
self.keyboard.walk("w", 60 / 28)
self.keyboard.walk("a", 56 / 28)
self.keyboard.walk("w", 64 / 28)
self.keyboard.walk("a", 80 / 28)

