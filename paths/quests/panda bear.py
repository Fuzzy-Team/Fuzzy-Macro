self.keyboard.press("e", 0.1)
# Fly back off the cannon and glide down beside Bamboo.
self.keyboard.keyDown("s")
sleep(1.05)
self.keyboard.slowPress("space")
self.keyboard.slowPress("space")
sleep(0.3)
self.keyboard.keyUp("s")
self.keyboard.slowPress("space")
sleep(0.1)
self.keyboard.slowPress(",")
self.keyboard.slowPress(",")
self.keyboard.tileWalk("w", 20)
self.keyboard.tileWalk("d", 17.5)
# Walk past the block beside the 25 bee gate and across Bamboo until the back wall stops the character, then step back to the row in front of Panda Bear's white disk.
self.keyboard.tileWalk("w", 32)
self.keyboard.tileWalk("s", 3)
# Walk right until the face of Panda Bear's raised yellow platform stops the character, hop up onto it, then step onto the disk until his prompt shows.
self.keyboard.tileWalk("d", 10)
for _ in range(2):
    self.keyboard.keyDown("d")
    self.keyboard.slowPress("space")
    sleep(0.3)
    self.keyboard.keyUp("d")
for i in range(14):
    sleep(0.3)
    if self.isBesideE(["talk", "panda"]):
        break
    if i == 0:
        # No prompt right after the hops: a hop that missed leaves the character at the platform's face, so hop once more.
        self.keyboard.keyDown("d")
        self.keyboard.slowPress("space")
        sleep(0.3)
        self.keyboard.keyUp("d")
    # Small steps with a prompt check after each, right first, then back left in case the character stepped past the bear.
    self.keyboard.tileWalk("d" if i < 5 else "a", 0.5)
