# Land in Bamboo the way the field path does, then walk right until the face of Panda Bear's raised yellow platform stops the character.
self.runPath("cannon_to_field/bamboo")
self.keyboard.tileWalk("d", 14)
# Hop up onto the platform.
for _ in range(2):
    self.keyboard.keyDown("d")
    self.keyboard.slowPress("space")
    sleep(0.3)
    self.keyboard.keyUp("d")
# Go south past the leaderboard post, then along the platform to his disk, stepping in until the prompt shows.
self.keyboard.tileWalk("s", 6)
self.keyboard.tileWalk("d", 6)
for _ in range(5):
    sleep(0.3)
    if self.isBesideE(["talk", "panda"]):
        break
    self.keyboard.tileWalk("s", 1)
