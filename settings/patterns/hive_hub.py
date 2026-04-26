self.keyboard.walk("s", 0.5)
for _ in range(6):
    self.keyboard.walk("w", 2.5)
    self.keyboard.walk("d", 0.1)
    self.keyboard.walk("s", 2.5)
    self.keyboard.walk("d", 0.1)

self.keyboard.walk("s", 4)
self.keyboard.walk("d", 4)
self.keyboard.multiWalk(["w", "d"], 5)
self.keyboard.walk("a", 4)
