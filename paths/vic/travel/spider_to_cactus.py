def run(self):
    self.viciousJump()
    sleep(0.2)
    self.keyboard.keyDown('w', False)
    sleep(0.5)
    self.keyboard.keyUp('w', False)
    for _ in range(1):
        self.keyboard.press('.')
        sleep((10 + self.setdat["vicious_key_delay_ms"]) / 1000)
    self.viciousWalk('w', 13)
    for _ in range(1):
        self.keyboard.press(',')
        sleep((10 + self.setdat["vicious_key_delay_ms"]) / 1000)
    self.viciousActivateGlider()
    sleep(1.0)
    self.viciousWalk('w', 9)
    for _ in range(1):
        self.keyboard.press('.')
        sleep((10 + self.setdat["vicious_key_delay_ms"]) / 1000)
    self.viciousActivateGlider()
    sleep(1.0)
    self.viciousWalk('w', 2)
    for _ in range(1):
        self.keyboard.press('.')
        sleep((10 + self.setdat["vicious_key_delay_ms"]) / 1000)
    self.viciousActivateGlider()
    sleep(1.0)
    for _ in range(2):
        self.keyboard.press(',')
        sleep((10 + self.setdat["vicious_key_delay_ms"]) / 1000)
    self.viciousWalk('d', 6)
    self.viciousWalk('w', 3)
    return True


result = run(self)
