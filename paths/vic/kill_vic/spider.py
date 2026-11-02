def run(self):
    self.viciousJump()
    sleep(0.2)
    self.keyboard.keyDown('w', False)
    sleep(0.5)
    self.keyboard.keyUp('w', False)
    for _ in range(1):
        self.keyboard.press('.')
        sleep((10 + self.setdat["vicious_key_delay_ms"]) / 1000)
    self.viciousWalk('w', 6)
    for _ in range(1):
        self.keyboard.press('.')
        sleep((10 + self.setdat["vicious_key_delay_ms"]) / 1000)
    self.viciousWalk('w', 8)
    self.viciousActivateGlider()
    sleep(1.0)
    self.viciousWalk('w', 6)
    self.viciousWalk('a', 5)
    for _ in range(4):
        self.keyboard.press('.')
        sleep((10 + self.setdat["vicious_key_delay_ms"]) / 1000)
    self.viciousActivateGlider()
    sleep(1.0)
    self.viciousWalk('w', 8)
    self.viciousWalk('d', 5)
    for _ in range(4):
        self.keyboard.press('.')
        sleep((10 + self.setdat["vicious_key_delay_ms"]) / 1000)
    self.viciousActivateGlider()
    sleep(1.0)
    self.viciousWalk('w', 8)
    self.viciousWalk('a', 5)
    for _ in range(4):
        self.keyboard.press('.')
        sleep((10 + self.setdat["vicious_key_delay_ms"]) / 1000)
    self.viciousActivateGlider()
    sleep(1.0)
    self.viciousWalk('w', 8)
    self.disableShiftLock()
    if not self.checkIfVicSummoned():
        return False
    self.viciousWalk('sa', 15)
    return self.viciousKillPattern()


result = run(self)
