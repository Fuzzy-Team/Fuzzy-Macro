def run(self):
    for _ in range(4):
        self.keyboard.press('.')
        sleep((10 + self.setdat["vicious_key_delay_ms"]) / 1000)
    for _ in range(2):
        self.keyboard.press('pageup')
        sleep((10 + self.setdat["vicious_key_delay_ms"]) / 1000)
    self.viciousJump()
    sleep(0.3)
    self.keyboard.keyDown('a', False)
    sleep(0.3)
    self.keyboard.keyUp('a', False)
    sleep(0.3)
    for _ in range(1):
        self.keyboard.press('.')
        sleep((10 + self.setdat["vicious_key_delay_ms"]) / 1000)
    self.viciousActivateGlider()
    sleep(3.01)
    for _ in range(1):
        self.keyboard.press('.')
        sleep((10 + self.setdat["vicious_key_delay_ms"]) / 1000)
    sleep(0.6)
    self.viciousJump()
    sleep(1.2)
    if not self.viciousRecoverCannon():
        return False
    self.keyboard.keyDown('e', False)
    sleep((50 + self.setdat['vicious_key_delay_ms']) / 1000)
    self.keyboard.keyUp('e', False)
    sleep(1.8)
    self.viciousJump()
    sleep(0.05)
    self.viciousJump()
    sleep(1.3)
    for _ in range(2):
        self.keyboard.press(',')
        sleep((10 + self.setdat["vicious_key_delay_ms"]) / 1000)
    sleep(0.44)
    self.viciousJump()
    sleep(0.7)
    self.viciousWalk('a', 5.5)
    self.viciousWalk('w', 9)
    for _ in range(4):
        self.keyboard.press('.')
        sleep((10 + self.setdat["vicious_key_delay_ms"]) / 1000)
    self.viciousWalk('w', 6)
    for _ in range(13):
        self.keyboard.press('pageup')
        sleep((10 + self.setdat["vicious_key_delay_ms"]) / 1000)
    for _ in range(5):
        self.keyboard.press('pagedown')
        sleep((10 + self.setdat["vicious_key_delay_ms"]) / 1000)
    self.viciousWalk('d', 1.2)
    for _ in range(7):
        self.keyboard.press('o')
        sleep((10 + self.setdat["vicious_key_delay_ms"]) / 1000)
    self.disableShiftLock()
    sleep(0.05)
    self.viciousRotateCamera("down", 25, self.setdat["vicious_camera_sensitivity"])
    sleep(0.05)
    self.viciousRotateCamera("left", 40, self.setdat["vicious_camera_sensitivity"])
    sleep(0.05)
    self.enableShiftLock()
    for _ in range(7):
        self.keyboard.press("o")
        sleep((10 + self.setdat["vicious_key_delay_ms"]) / 1000)
    return True


result = run(self)
