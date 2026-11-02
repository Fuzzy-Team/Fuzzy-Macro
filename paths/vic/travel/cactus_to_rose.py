def run(self):
    for _ in range(1):
        self.keyboard.press(',')
        sleep((10 + self.setdat["vicious_key_delay_ms"]) / 1000)
    for _ in range(6):
        self.keyboard.press('pageup')
        sleep((10 + self.setdat["vicious_key_delay_ms"]) / 1000)
    self.viciousActivateGlider()
    sleep(1.0)
    for _ in range(1):
        self.keyboard.press(',')
        sleep((10 + self.setdat["vicious_key_delay_ms"]) / 1000)
    self.viciousActivateGlider()
    sleep(1.0)
    self.viciousWalk('wd', 9)
    self.viciousWalk('w', 1.5)
    self.viciousJump()
    sleep(0.3)
    self.keyboard.keyDown('w', False)
    sleep(0.4)
    self.keyboard.keyUp('w', False)
    self.viciousWalk('wd', 17)
    self.viciousWalk('w', 2)
    sleep(0.6)
    self.viciousWalk('s', 10)
    self.viciousWalk('sd', 1.5)
    for _ in range(10):
        self.keyboard.press('pagedown')
        sleep((10 + self.setdat["vicious_key_delay_ms"]) / 1000)
    for _ in range(6):
        self.keyboard.press('pageup')
        sleep((10 + self.setdat["vicious_key_delay_ms"]) / 1000)
    for _ in range(7):
        self.keyboard.press('o')
        sleep((10 + self.setdat["vicious_key_delay_ms"]) / 1000)
    self.viciousWalk('sd', 1.5)
    return True


result = run(self)
