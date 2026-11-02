def run(self):
    for _ in range(9):
        self.keyboard.press('pageup')
        sleep((10 + self.setdat["vicious_key_delay_ms"]) / 1000)
    for _ in range(1):
        self.keyboard.press(',')
        sleep((10 + self.setdat["vicious_key_delay_ms"]) / 1000)
    self.viciousActivateGlider()
    sleep(1.0)
    for _ in range(1):
        self.keyboard.press(',')
        sleep((10 + self.setdat["vicious_key_delay_ms"]) / 1000)
    self.viciousActivateGlider()
    sleep(1.0)
    for _ in range(1):
        self.keyboard.press('.')
        sleep((10 + self.setdat["vicious_key_delay_ms"]) / 1000)
    self.viciousWalk('w', 10)
    self.viciousJump()
    sleep(0.3)
    self.viciousWalk('w', 3.5)
    for _ in range(3):
        self.keyboard.press('.')
        sleep((10 + self.setdat["vicious_key_delay_ms"]) / 1000)
    self.viciousWalk('w', 41.5)
    for _ in range(2):
        self.keyboard.press('.')
        sleep((10 + self.setdat["vicious_key_delay_ms"]) / 1000)
    self.viciousActivateGlider()
    sleep(1.0)
    self.viciousActivateGlider()
    sleep(1.0)
    self.viciousWalk('a', 6.5)
    for _ in range(4):
        self.keyboard.press('.')
        sleep((10 + self.setdat["vicious_key_delay_ms"]) / 1000)
    self.viciousActivateGlider()
    sleep(1.0)
    self.viciousActivateGlider()
    sleep(1.0)
    self.disableShiftLock()
    if not self.checkIfVicSummoned():
        return False
    self.viciousWalk('s', 10)
    return self.viciousKillPattern()


result = run(self)
