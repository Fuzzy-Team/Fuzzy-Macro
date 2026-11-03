def run(self):
    for _ in range(4):
        self.keyboard.press('o')
        sleep((10 + self.setdat["vicious_key_delay_ms"]) / 1000)
    self.viciousWalk('w', 9)
    return True


result = run(self)
