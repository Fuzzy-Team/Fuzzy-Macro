def run(self):
    self.viciousWalk('w', 24)
    for _ in range(2):
        self.keyboard.press('.')
        sleep((10 + self.setdat["vicious_key_delay_ms"]) / 1000)
    self.viciousJump()
    sleep(0.34)
    self.viciousWalk('w', 4)
    self.viciousWalk('wd', 6.5)
    self.viciousActivateGlider()
    sleep(1.0)
    self.viciousWalk('w', 7)
    self.viciousWalk('d', 6)
    for _ in range(4):
        self.keyboard.press('.')
        sleep((10 + self.setdat["vicious_key_delay_ms"]) / 1000)
    self.viciousActivateGlider()
    sleep(1.0)
    self.viciousWalk('w', 10)
    self.viciousWalk('a', 6)
    for _ in range(4):
        self.keyboard.press('.')
        sleep((10 + self.setdat["vicious_key_delay_ms"]) / 1000)
    self.viciousActivateGlider()
    sleep(1.0)
    self.viciousWalk('w', 10)
    self.disableShiftLock()
    if not self.checkIfVicSummoned():
        return False
    self.viciousWalk('s', 8)
    self.viciousWalk('sa', 8)
    return self.viciousKillPattern()


result = run(self)
