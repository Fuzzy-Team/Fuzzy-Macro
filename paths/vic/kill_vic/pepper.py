def run(self):
    self.viciousJump()
    sleep(0.3)
    self.viciousWalk('d', 7)
    self.viciousActivateGlider()
    sleep(1.0)
    self.viciousWalk('w', 7)
    self.viciousWalk('d', 6)
    for _ in range(4):
        self.keyboard.press('.')
        sleep((10 + self.setdat["vicious_key_delay_ms"]) / 1000)
    self.viciousActivateGlider()
    sleep(1.0)
    self.viciousWalk('w', 8)
    self.viciousWalk('a', 6)
    for _ in range(4):
        self.keyboard.press('.')
        sleep((10 + self.setdat["vicious_key_delay_ms"]) / 1000)
    self.viciousActivateGlider()
    sleep(1.0)
    self.viciousWalk('w', 9)
    self.disableShiftLock()
    if not self.checkIfVicSummoned():
        return False
    self.viciousWalk('as', 7)
    self.viciousWalk('s', 6)
    return self.viciousKillPattern()


result = run(self)
