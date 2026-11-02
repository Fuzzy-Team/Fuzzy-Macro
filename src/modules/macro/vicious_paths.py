from modules.controls.sleep import sleep


class ViciousPathsMixin:
    def Vichop_Hive_to_Pepper(self):
        self.viciousHiveToRamp()
        self.viciousJump()
        self.viciousWalk('d', 3)
        self.viciousWalk('wd', 1.5)
        self.viciousWalk('d', 25.29)
        self.viciousJump()
        sleep(0.303)
        self.viciousWalk('d', 0.91)
        self.viciousWalk('wd', 9.83)
        self.viciousJump()
        sleep(0.27)
        self.viciousWalk('w', 16)
        self.viciousJump()
        sleep(0.219)
        self.viciousWalk('w', 4.18)
        sleep(0.1)
        self.viciousJump()
        sleep(0.235)
        self.viciousWalk('w', 2.95)
        sleep(0.1)
        self.viciousJump()
        sleep(0.237)
        self.viciousWalk('w', 3)
        self.viciousWalk('wd', 11)
        self.viciousWalk('w', 3)
        self.viciousJump()
        sleep(0.267)
        self.viciousWalk('w', 2.66)
        self.viciousWalk('wd', 13)
        self.viciousJump()
        sleep(0.23)
        self.viciousWalk('d', 10)
        self.viciousWalk('sd', 5)
        self.enableShiftLock()
        for _ in range(13):
            self.keyboard.press('pagedown')
            sleep((10 + self.setdat["vicious_key_delay_ms"]) / 1000)
        for _ in range(5):
            self.keyboard.press('pageup')
            sleep((10 + self.setdat["vicious_key_delay_ms"]) / 1000)
        for _ in range(5):
            self.keyboard.press('o')
            sleep((10 + self.setdat["vicious_key_delay_ms"]) / 1000)
        return True


    def Vichop_Pepper_to_Mountaintop(self):
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


    def Vichop_Mountaintop_to_edge(self):
        for _ in range(4):
            self.keyboard.press('o')
            sleep((10 + self.setdat["vicious_key_delay_ms"]) / 1000)
        self.viciousWalk('w', 9)
        return True


    def Vichop_edge_to_Spider(self):
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


    def Vichopspider_to_cactus(self):
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


    def Vichop_Cactus_To_rose(self):
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


    def PepperMainKillVic(self):
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


    def MountainTopKillVic(self):
        self.viciousJump()
        sleep(0.25)
        self.viciousWalk('sd', 8)
        self.viciousActivateGlider()
        sleep(1.0)
        self.viciousWalk('w', 7)
        self.viciousWalk('d', 5.5)
        for _ in range(4):
            self.keyboard.press('.')
            sleep((10 + self.setdat["vicious_key_delay_ms"]) / 1000)
        self.viciousActivateGlider()
        sleep(1.0)
        self.viciousWalk('w', 9)
        self.viciousWalk('a', 5.5)
        for _ in range(4):
            self.keyboard.press('.')
            sleep((10 + self.setdat["vicious_key_delay_ms"]) / 1000)
        self.viciousActivateGlider()
        sleep(1.0)
        self.viciousWalk('w', 9)
        self.viciousWalk('d', 5.5)
        for _ in range(4):
            self.keyboard.press('.')
            sleep((10 + self.setdat["vicious_key_delay_ms"]) / 1000)
        self.viciousActivateGlider()
        sleep(1.0)
        self.viciousWalk('w', 5)
        self.disableShiftLock()
        if not self.checkIfVicSummoned():
            return False
        self.viciousWalk('sd', 8)
        self.viciousWalk('d', 2)
        return self.viciousKillPattern()


    def SpiderKillVic(self):
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


    def CactusKillVic(self):
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


    def RoseKillVic(self):
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
