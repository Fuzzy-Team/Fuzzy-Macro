self.keyboard.walk("s", 7)
self.keyboard.walk("d", 2)
self.keyboard.walk("s", 2)
self.keyboard.walk("a", 0.25)
self.keyboard.press(" ")
self.keyboard.walk("w", 0.5)
sleep(0.5)
self.keyboard.press(" ")
self.keyboard.walk("a", 0.5)
sleep(1)

self.keyboard.walk("d", 3.5)
self.keyboard.walk("s", 0.5)

# Continue the movement pattern and check for defeat
while self.bossStatus is None and not self.died:
    # Check if defeated
    if self.blueTextImageSearch("tunnelbear", 0.8):
        self.bossStatus = "defeated"
        break
    # Check if died
    if self.blueTextImageSearch("died"):
        self.died = True
        break
    # Continue movement
    self.keyboard.walk("d", 0.25)
    sleep(0.75)

# Collect rewards if defeated
if self.bossStatus == "defeated":
    self.keyboard.walk("d", 1.5)
    self.keyboard.walk("a", 3)
    sleep(1)