def run(self):
    self.viciousActivateGlider()
    sleep(2.8)
    for _ in range(1):
        self.keyboard.press('.')
        sleep((10 + self.setdat["vicious_key_delay_ms"]) / 1000)
    sleep(1.0)
    for _ in range(1):
        self.keyboard.press('.')
        sleep((10 + self.setdat["vicious_key_delay_ms"]) / 1000)
    sleep(0.3)
    self.viciousJump()
    sleep(1.5)
    self.viciousWalk('w', 7)
    self.viciousWalk('d', 16)
    return True


result = run(self)
