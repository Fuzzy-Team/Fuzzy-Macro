sideTime = 0.11
frontTime = 0.54
time.sleep(2.5)
#self.keyboard.press(",") #feast messes up the camera angle
self.keyboard.walk('d',0.26)
self.keyboard.walk('w',0.22)
for i in range(3):
    self.keyboard.walk("s", frontTime)
    self.keyboard.walk("a", sideTime)
    self.keyboard.walk("w", frontTime)
    self.keyboard.walk("a", sideTime)
self.keyboard.walk("s", frontTime)
self.keyboard.walk("a", sideTime)
self.keyboard.walk("w", frontTime)

   

    
