time.sleep(0.3)  # Sleep(300)
self.keyboard.press("e", 0.05)  # KeyPress(E), keyDelay=50ms
time.sleep(0.25)  # Sleep(250)

# Parachute({ [0]=Forward+Left, [2500]=Forward, [4650]=End })
self.keyboard.keyDown("w")
self.keyboard.keyDown("a")
self.keyboard.press("space", 0.05)
self.keyboard.press("space", 0.05)
time.sleep(2.5)
self.keyboard.keyUp("a")
time.sleep(2.15)
self.keyboard.keyUp("w")
# SleepAlign(300) — stay on chute until grounded (do not press space)
time.sleep(1.2)

# WalkAlign(Right, 50), WalkAlign(Forward, 35) — Low alignment (no +8)
self.keyboard.walk("d", 50 / 28)
self.keyboard.walk("w", 35 / 28)

# Walk table 1 (stud keyframes)
self.keyboard.multiWalk(["s", "a"], 20 / 28)   # 0-20: Backward+Left
self.keyboard.walk("w", 60 / 28)               # 20-80: Forward
self.keyboard.walk("a", 56 / 28)               # 80-136: Left
self.keyboard.walk("w", 64 / 28)               # 136-200: Forward
self.keyboard.multiWalk(["w", "a"], 90 / 28)   # 200-290: Forward+Left
self.keyboard.walk("a", 47 / 28)               # 290-337: Left
self.keyboard.walk("w", 13 / 28)               # 337-350: Forward

# Walk table 2
self.keyboard.walk("w", 140 / 28)              # 0-140: Forward (NoParachute)
self.keyboard.walk("d", 170 / 28)              # 140-310: Right

# Walk table 3
self.keyboard.walk("s", 20 / 28)               # 0-20: Backward
self.keyboard.multiWalk(["s", "a"], 45 / 28)   # 20-65: Backward+Left
self.keyboard.walk("s", 55 / 28)               # 65-120: Backward
self.keyboard.multiWalk(["s", "d"], 6 / 28)    # 120-126: Backward+Right
self.keyboard.walk("s", 74 / 28)               # 126-200: Backward

# Jump({ Delay=100, Distance=60, Direction={Backward} })
self.keyboard.keyDown("s")
time.sleep(0.1)
self.keyboard.press("space", 0.05)
self.keyboard.keyUp("s")
self.keyboard.walk("s", 60 / 28)
time.sleep(0.15)  # SleepAlign(150)

# Jump({ Delay=100, Distance=10, Direction={Forward}, WalkBefore=4 })
self.keyboard.walk("w", 4 / 28)
self.keyboard.keyDown("w")
time.sleep(0.1)
self.keyboard.press("space", 0.05)
self.keyboard.keyUp("w")
self.keyboard.walk("w", 10 / 28)
time.sleep(0.35)  # SleepAlign(350)
self.keyboard.walk("d", 4 / 28)

# Use gumdrop to enter gummy bear's lair
use_slot = False
try:
    use_slot = bool(self.setdat.get("glue_dispenser_use_gumdrop_slot", False))
except Exception:
    use_slot = False

if use_slot:
    self.keyboard.walk("a", 1.4)
    self.keyboard.walk("w", 0.15)
    self.keyboard.walk("a", 0.3)
    time.sleep(0.3)
    self.keyboard.walk("w", 0.1)
    slot = self.setdat.get("goo_slot", 2)
    self.keyboard.press(str(slot))
    self.canDetectNight = False
    time.sleep(2)
    self.keyboard.walk("w", 2.5)
    time.sleep(0.5)
    self.canDetectNight = True
else:
    itemCoords = self.findItemInInventory("gumdrops")
    if itemCoords is not None:
        self.keyboard.walk("a", 1.4)
        self.keyboard.walk("w", 0.15)
        self.keyboard.walk("a", 0.3)
        time.sleep(0.3)
        self.keyboard.walk("w", 0.1)
        self.useItemInInventory(x=itemCoords[0], y=itemCoords[1])
        self.canDetectNight = False
        time.sleep(2)
        self.keyboard.walk("w", 2.5)
        time.sleep(0.5)
        self.canDetectNight = True
