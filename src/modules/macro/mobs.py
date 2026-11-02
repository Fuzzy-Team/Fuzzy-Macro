import threading
import traceback
import modules.controls.mouse as mouse
import modules.misc.settingsManager as settingsManager
from modules.controls.sleep import InterruptRequested, pause_aware_time as time, sleep
from modules.gather_session import field_pattern_variables, GatherPatternRunner
import modules.macro.pattern_environment as patternEnvironment
from modules.macro.game_data import (
    mobRespawnTimes,
    regularMobQuantitiesInFields,
    regularMobTypesInFields,
)
from modules.screen.imageSearch import locateImageOnScreen


class MobMixin:
    def viciousWalk(self, keys, tiles):
        try:
            for key in keys:
                self.keyboard.keyDown(key, False)
            self.keyboard.tileWait(tiles)
        finally:
            for key in keys:
                self.keyboard.keyUp(key, False)

    def viciousKillPattern(self):
        """Fight for 12 cycles (~40s) in self.viciousField.

        Dying means the bee is still alive, so after returning to the same
        field a fresh 12 cycles start. A full window without a death or a
        defeat means the bee is gone, as before.
        """
        while True:
            died = False
            for _ in range(12):
                for key in "wasd":
                    if self.checkPauseAndWait():
                        return False
                    self.viciousWalk(key, 4)
                    sleep(0.8)
                    # Same blue-text "died" check as the other fights; chat is
                    # never read for deaths, so old "You died" lines can't retrigger.
                    if self.blueTextImageSearch("died", screen=self.blueTextScreen()):
                        died = True
                        break
                if died:
                    break
                if self.checkIfViciousDied():
                    self.hourlyReport.addHourlyStat("vicious_bees", 1)
                    return True
            if not died:
                return False
            # A kill announced right before the death still counts.
            if self.checkIfViciousDied():
                self.hourlyReport.addHourlyStat("vicious_bees", 1)
                return True
            if not self.viciousReturnToField():
                return False

    def viciousReturnToField(self):
        """After dying mid fight, walk back to the same field on this server."""
        field = self.viciousField
        self.keyboard.releaseMovement()
        self.logger.webhook("Vic Hop", f"Died fighting the Vicious Bee in {field.title()}, returning to the same field", "red", "screen", ping_category="ping_character_deaths")
        if self.checkPauseAndWait():
            return False
        self.set_task_status("stinger_hunt", activity=field.title())
        # cannon(allowRejoin=False): a failed cannon must not hop to another server.
        if not (self.reset(convert=False) and self.cannon(allowHiveResync=False, allowRejoin=False)):
            self.logger.webhook("Vic Hop", f"Could not return to {field.title()} after dying, ending the hunt", "orange", "screen", ping_category="ping_vicious_bee")
            return False
        self.goToField(field, "north")
        self.location = field
        self.logger.webhook("Vic Hop", f"Back in {field.title()}, fighting the Vicious Bee again", "yellow", "screen", ping_category="ping_vicious_bee")
        return True

    def viciousSearchRoute(self):
        # Camera sensitivity and key-delay defaults for the Vicious route.
        self.setdat.setdefault("vicious_camera_sensitivity", 1)
        self.setdat.setdefault("vicious_key_delay_ms", 20)
        def search(field, approach):
            self.set_task_status("stinger_hunt", activity=field)
            self.viciousField = field.replace(" back", "").lower()
            if self.setdat.get("macro_mode", "normal") != "vic" and self.viciousField not in self.vicFields:
                return None
            if not self.detectViciousBee():
                self.logger.webhook("Vic Hop", f"{field}: no Vicious Bee detected", "dark brown", "screen")
                return None
            self.logger.webhook("Vic Hop", f"Vicious Bee detected in {field}, approaching", "yellow", "screen", ping_category="ping_vicious_bee")
            result = approach()
            self.logger.webhook("Vic Hop", "Vicious Bee defeated" if result else "Vicious Bee hunt ended without a confirmed defeat", "light green" if result else "orange", "screen", ping_category="ping_vicious_bee")
            return result
        self.logger.webhook("Vic Hop", "Hive ready, checking fields starting with Pepper", "dark brown", "screen")
        self.Vichop_Hive_to_Pepper()
        result = search("Pepper", self.PepperMainKillVic)
        if result is not None:
            return result
        if not self.Vichop_Pepper_to_Mountaintop():
            return False
        # Detect before rotating toward the next field.
        enabled = self.setdat.get("macro_mode", "normal") == "vic" or "mountain top" in self.vicFields
        found = enabled and self.detectViciousBee()
        self.viciousRotate("right", 1)
        if found:
            self.viciousField = "mountain top"
            self.logger.webhook("Vic Hop", "Vicious Bee detected in Mountain Top, approaching", "yellow", "screen", ping_category="ping_vicious_bee")
            result = self.MountainTopKillVic()
            self.logger.webhook("Vic Hop", "Vicious Bee defeated" if result else "Vicious Bee hunt ended without a confirmed defeat", "light green" if result else "orange", "screen", ping_category="ping_vicious_bee")
            return result
        self.logger.webhook("Vic Hop", "Mountain Top: no Vicious Bee detected", "dark brown", "screen")
        self.Vichop_Mountaintop_to_edge()
        self.Vichop_edge_to_Spider()
        result = search("Spider", self.SpiderKillVic)
        if result is not None:
            return result
        self.Vichopspider_to_cactus()
        for key, count in (("pagedown", 10), ("pageup", 2)):
            for _ in range(count):
                self.keyboard.press(key)
                sleep((10 + self.setdat["vicious_key_delay_ms"]) / 1000)
        result = search("Cactus", self.CactusKillVic)
        if result is not None:
            return result
        for _ in range(5):
            self.keyboard.keyDown("pagedown", False)
            sleep((10 + self.setdat["vicious_key_delay_ms"]) / 1000)
            self.keyboard.keyUp("pagedown", False)
            sleep((10 + self.setdat["vicious_key_delay_ms"]) / 1000)
        result = search("Cactus back", self.CactusKillVic)
        if result is not None:
            return result
        self.Vichop_Cactus_To_rose()
        result = search("Rose", self.RoseKillVic)
        if result is None:
            self.disableShiftLock()
            self.logger.webhook("Vic Hop", "Finished checking fields, no Vicious Bee found", "dark brown", "screen")
        return result or False

    def viciousRotate(self, direction, amount):
        """Rotate the camera in discrete steps separated by 50 ms."""
        key = {"left": ",", "right": ".", "up": "pageup", "down": "pagedown"}[direction]
        for _ in range(amount):
            self.keyboard.press(key)
            sleep(0.05)

    def viciousJump(self):
        self.keyboard.keyDown("space", False)
        try:
            sleep(0.05)
        finally:
            self.keyboard.keyUp("space", False)

    def viciousActivateGlider(self):
        self.viciousJump()
        sleep(0.3)
        self.viciousJump()

    def viciousRotateCamera(self, direction, amount, sensitivity):
        """Rotate the mouse camera using the actual in-game sensitivity."""
        import math
        if sensitivity <= 0:
            raise ValueError("Camera sensitivity must be positive")
        delta = math.floor(amount / sensitivity + 0.5)
        dx, dy = {"down": (0, -delta), "left": (-delta, 0)}[direction]
        win = self.robloxWindow
        mouse.moveTo(win.mx + win.mw / 2, win.my + win.mh / 2)
        mouse.pynputMouse.press(mouse.Button.right)
        try:
            sleep(0.1)
            mouse.rightDragBy(dx, dy)
            sleep(0.1)
        finally:
            mouse.pynputMouse.release(mouse.Button.right)

    def viciousRecoverCannon(self, frame=None):
        """Check the reference Fire prompt before recovering through the hive."""
        from modules.screen.ocr import ocrRead
        from modules.screen.screenshot import mssScreenshot
        if frame is None:
            win = self.robloxWindow
            frame = mssScreenshot(win.mx, win.my, win.mw, win.mh)
        if any("Fire" in item[1][0] for item in ocrRead(frame)):
            return True
        self.disableShiftLock()
        if not self.reset(convert=False):
            return False
        for _ in range(6):
            self.keyboard.press("o")
            sleep((10 + self.setdat.get("vicious_key_delay_ms", 20)) / 1000)
        if not self.viciousHiveToCannon():
            return False
        self.enableShiftLock()
        for _ in range(2):
            self.keyboard.press(",")
            sleep((10 + self.setdat.get("vicious_key_delay_ms", 20)) / 1000)
        return True

    def viciousBitmapPosition(self, name, region, tolerance):
        import cv2
        from modules.macro.events import vicious_bitmap_position
        from modules.screen.screenshot import mssScreenshotNP
        frame = mssScreenshotNP(*region)[:, :, :3]
        frame = cv2.resize(frame, (region[2], region[3]), interpolation=cv2.INTER_AREA)
        return vicious_bitmap_position(frame, name, tolerance)

    def viciousActivateChat(self):
        win = self.robloxWindow
        point = self.viciousBitmapPosition("chatclosed", (win.mx, win.my, 200, 100), 25)
        if point is not None:
            mouse.moveTo(win.mx + point[0], win.my + point[1])
            sleep(0.05)
            mouse.mouseDown()
            sleep(0.06)
            mouse.mouseUp()
            sleep(0.2)
        mouse.moveTo(win.mx + 350, win.my + 100)
        if point is not None:
            sleep(0.1)
            mouse.click()
        width, height = mouse.pag.size()
        for x, y in ((1465, 162), (1467, 165)):
            mouse.moveTo(int(x * width / 1920 + 0.5), int(y * height / 1080 + 0.5))
            sleep(0.05)

    def viciousHiveToRamp(self):
        self.viciousWalk("w", 5)
        self.viciousWalk("d", 9.2 * self.setdat["hive_number"] - 4)

    def viciousHiveToCannon(self):
        try:
            attempts = max(1, int(self.setdat.get("max_cannon_attempts", 3)))
        except (TypeError, ValueError):
            attempts = 3
        for attempt in range(attempts):
            if self.checkPauseAndWait():
                return False
            self.viciousHiveToRamp()
            self.viciousJump()
            self.viciousWalk("d", 3)
            self.viciousWalk("wd", 1.7)
            win = self.robloxWindow
            region = (win.mx + win.mw // 2 - 200, win.my, 400, 125)
            for _ in range(10):
                self.viciousWalk("d", 1.5)
                if self.viciousBitmapPosition("redcannon", region, 2) is None:
                    continue
                for correction in range(1, 11):
                    if correction == 10:
                        break
                    sleep(0.5)
                    if self.viciousBitmapPosition("redcannon", region, 2) is not None:
                        sleep(1)
                        return True
                    self.viciousWalk("a", 1.5)
            if attempt + 1 < attempts and not self.reset(convert=False):
                return False
        return False

    def viciousNotification(self, name, frame=None):
        """Reference top-right bitmap search with per-channel tolerance 25.

        The caller must expose the chat before these checks.
        Frames are BGR or BGRA client captures at native resolution.
        """
        import cv2
        from modules.macro.events import vicious_bitmap_matches
        from modules.screen.screenshot import mssScreenshotNP
        if name not in ("vicsummon", "vicdead"):
            raise ValueError("Unknown Vicious notification")
        if frame is None:
            win = self.robloxWindow
            frame = mssScreenshotNP(win.mx, win.my, win.mw, win.mh)
            frame = cv2.resize(frame, (win.mw, win.mh), interpolation=cv2.INTER_AREA)
        height, width = frame.shape[:2]
        region = frame[:height // 2, width // 2:, :3]
        if vicious_bitmap_matches(region, name, 25):
            return True
        # Roblox's current chat font can differ from the bitmap glyphs.
        # Read the same announcement region when the source bitmap misses.
        from PIL import Image
        from modules.screen.ocr import ocrRead
        readable = cv2.resize(region, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        image = Image.fromarray(cv2.cvtColor(readable, cv2.COLOR_BGR2RGB))
        for item in ocrRead(image):
            text = " ".join(item[1][0].lower().split())
            if name == "vicsummon" and "vicious bee is attacking" in text:
                return True
            if name == "vicdead":
                if "vicious bee" in text and "defeated" in text:
                    return True
                # The highlighted defeat line can be unreadable to OCR, but
                # its adjacent stinger reward explicitly identifies the kill.
                import re
                if re.search(r"\+\s*\d+\s+stingers?\s*\(from vicious bee\b", text):
                    return True
        return False

    def checkIfVicSummoned(self, frame=None):
        if frame is None:
            self.viciousActivateChat()
        return self.viciousNotification("vicsummon", frame)

    def checkIfViciousDied(self, frame=None):
        if frame is None:
            self.viciousActivateChat()
        return self.viciousNotification("vicdead", frame)

    def detectViciousBee(self, frame=None):
        """Detect Vicious Bee in a BGRA frame, or capture the Roblox client."""
        import cv2
        import numpy as np
        from modules.misc.modelManager import MODEL_DIR, VICIOUS_MODEL, ensure_missing_models
        from modules.screen.screenshot import mssScreenshotNP
        import os

        if not hasattr(self, "_viciousModel"):
            result = ensure_missing_models((VICIOUS_MODEL,))
            if result["failures"]:
                raise RuntimeError(f"Could not download Vicious Bee model: {result['failures']}")
            self._viciousModel = cv2.dnn.readNetFromONNX(os.path.join(MODEL_DIR, VICIOUS_MODEL))
        if frame is None:
            win = self.robloxWindow
            frame = mssScreenshotNP(win.mx, win.my, win.mw, win.mh)
        resized = cv2.resize(frame, (736, 736), interpolation=cv2.INTER_LINEAR)
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGRA2RGB)
        tensor = np.expand_dims(np.transpose(rgb.astype(np.float16) / 255.0, (2, 0, 1)), 0)
        model = self._viciousModel
        model.setInput(tensor.astype(np.float32))
        output = np.squeeze(model.forward())
        scores = np.max(output[4:, :], axis=0)
        mask = scores > 0.4
        if not np.any(mask):
            return False
        cx, cy, width, height = output[:4, mask]
        boxes = np.stack((cx - width / 2, cy - height / 2, width, height), axis=1)
        return len(cv2.dnn.NMSBoxes(boxes.tolist(), scores[mask].tolist(), 0.4, 0.5)) > 0

    def viciousHop(self, searchAndKill=None):
        """Hop public servers until stopped; searchAndKill handles the night route.

        The callback takes no arguments and runs synchronously on this macro.
        Exceptions propagate so inference or navigation failures stop the run.
        """
        if searchAndKill is None:
            searchAndKill = self.viciousSearchRoute
        while not self.checkPauseAndWait():
            if not self.rejoin(rejoinMsg="Vic Hop", usePrivateServer=False, nightOnly=True):
                continue
            if self.checkPauseAndWait():
                return
            stats = self.hourlyReport.hourlyReportStats
            if not stats["start_time"] or not stats["start_honey"]:
                honey = self.getHoney()
                if honey > 0:
                    self.hourlyReport.setSessionStats(honey, time.time())
            searchAndKill()

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

    def Vichop_Edge_to_Cactus(self):
        self.viciousActivateGlider()
        sleep(1.8)
        for _ in range(2):
            self.keyboard.press('.')
            sleep((10 + self.setdat["vicious_key_delay_ms"]) / 1000)
        sleep(4.0)
        self.viciousJump()
        sleep(0.75)
        self.viciousWalk('sd', 1)
        self.viciousWalk('d', 13)
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

    def hasMondoRespawned(self):
        #check if mondo can be collected (first 10mins)
        minute = self.getCurrentMinute()
        #set respawn time to 20mins
        #mostly just to prevent the macro from going to mondo over and over again for the 10mins
        return minute <= 10 and self.hasRespawned("mondo", 20*60)

    def collectMondoBuff(self, gatherInterrupt = False):
        self.set_task_status("mondo_buff", activity="mondo")
        self.logger.webhook("","Travelling: Mondo Buff","dark brown")
        #go to mondo buff
        if not self.travelViaCannon("Mondo Buff"):
            return False
        self.keyboard.press("e")
        sleep(2.5)
        self.logger.webhook("","Collecting: Mondo Buff","yellow", "screen")
        self.keyboard.walk("w",1)
        self.keyboard.walk("d",3) 
        if self.setdat["mondo_buff_damage"]:
            mondo_buff_wait = self.setdat["mondo_buff_wait"]
            end_time = time.perf_counter() + mondo_buff_wait * 60
            self.logger.webhook("", f"Damaging Mondo for {mondo_buff_wait:g} minutes", "yellow")
            self.enableShiftLock()
            while time.perf_counter() < end_time and self.getCurrentMinute() < 15:
                screen = self.blueTextScreen()
                if self.blueTextImageSearch("defeated", screen=screen) and self.blueTextImageSearch("mondo", screen=screen):
                    break
                if self.setdat["mondo_collect_token"]:
                    self.keyboard.walk("a", 0.45)
                    for slowmove in range(9):
                        self.keyboard.walk("d", 0.048, False)
                        time.sleep(0.035)
                mouse.click()
                time.sleep(1.5)
            self.saveTiming("mondo")
            self.logger.webhook("","Collected: Mondo Buff","light green", ping_category="ping_mondo_buff")
        elif self.setdat["mondo_buff_loot"]: # If looting is enabled, wait until mondo is defeated
            self.logger.webhook("", "Waiting for Mondo to be defeated", "light green")
            self.enableShiftLock() #moves slightly up (or down) when hitting wall, so this reduces that
            while True:
                screen = self.blueTextScreen()
                #defeat
                if self.blueTextImageSearch("defeated", screen=screen) and self.blueTextImageSearch("mondo", screen=screen):
                    self.saveTiming("mondo") 
                    break
                #died
                if self.blueTextImageSearch("died", screen=screen):
                    self.died = True
                    self.keyboard.press("shift")
                    self.logger.webhook("", "Player Died", "red", "screen", ping_category="ping_character_deaths")
                    self.reset(convert=False)
                    #sev recursion here is pretty weird
                    #TODO: not make it recursive
                    self.collectMondoBuff()
                    return
                #time limit
                if self.getCurrentMinute() >= 15: #mondo despawns after 15 minutes if not defeated in time
                    self.keyboard.walk("s",1, False)
                    self.keyboard.press(",")
                    time.sleep(0.5)
                    self.logger.webhook("", "Time Limit (15 minutes)\n Mondo may have despawned. Resetting", "light green", "screen")
                    self.keyboard.press("shift")
                    self.saveTiming("mondo") 
                    self.reset(convert=True)
                    return False
                #collect tokens by bees
                if self.setdat["mondo_collect_token"]: 
                    self.keyboard.walk("a", 0.45)
                    for slowmove in range(9):
                        self.keyboard.walk("d", 0.048, False) #move JUST EVER SO SLIGHTLY, maybe bumps in to wall less
                        time.sleep(0.035)
                mouse.click()
                time.sleep(1.5)

            #loot
            mondo_loot_times = self.setdat["mondo_loot_times"] #how many loops based on what the user inputted
            time.sleep(0.1)
            self.keyboard.walk("d",1,False)
            time.sleep(0.1)
            self.keyboard.press("shift")
            self.keyboard.walk("s",3.15,False)
            self.logger.webhook("", "Looting: Mondo Chick", "yellow", "screen")
            if mondo_loot_times == 1:
                self.logger.webhook("", "Looping 1 time", "light green")
            else:
                self.logger.webhook("", f"Looping {mondo_loot_times} times", "light green")
            self.keyboard.walk("a",3.55)
            for loops in range(mondo_loot_times): 
                for looting in range(6):
                    self.keyboard.walk("w",0.20)
                    self.keyboard.walk("d",2.65)
                    self.keyboard.walk("w",0.20)
                    self.keyboard.walk("a",2.65)
                for looting in range(6):
                    self.keyboard.walk("s",0.20)
                    self.keyboard.walk("d",2.65)
                    self.keyboard.walk("s",0.20)
                    self.keyboard.walk("a",2.65)
        else: #if loot off, just idle
            mondo_buff_wait = self.setdat["mondo_buff_wait"]
            mondo_buff_wait_label = f"{mondo_buff_wait:g}" if isinstance(mondo_buff_wait, float) else str(mondo_buff_wait)
            end_time = time.perf_counter() + mondo_buff_wait * 60  
            self.logger.webhook("", f"Collecting for: {mondo_buff_wait_label} minutes", "yellow")
            # if collecting tokens produced by bees
            if self.setdat["mondo_collect_token"]:
                # enable shiftlock
                self.enableShiftLock()
                while time.perf_counter() < end_time: 
                    self.keyboard.walk("a", 0.45)
                    for slowmove in range(9):
                        self.keyboard.walk("d", 0.048, False) #move JUST EVER SO SLIGHTLY, maybe bumps in to wall less
                        time.sleep(0.035) 
                    time.sleep(3) #longer since we are not detecting anything
            else:
                time.sleep(mondo_buff_wait * 60)
            self.saveTiming("mondo") 
            self.logger.webhook("","Collected: Mondo Buff","light green", ping_category="ping_mondo_buff")
        #done
        self.reset(convert=True)
        return True

    #accept mob and field and return them in the format used for timings.txt file
    #mob_field, eg ladybug_strawberry
    #werewolf is an exception, just return "werewolf"
    def formatMobTimingName(self, mob, field):
        if mob == "werewolf": return mob
        return f"{mob}_{field}"

    def hasMobRespawned(self, mob, field, timing = None):
        return self.hasRespawned(self.formatMobTimingName(mob, field), mobRespawnTimes[mob], True, timing)

    #to be used by the mob run walk paths
    #returns true if there are mobs in the field to be killed (enabled + respawned)
    #returns a list of mobs that have respawned
    def getRespawnedMobs(self, field):
        mobs = regularMobTypesInFields[field]
        out = []
        for m in mobs:
            if self.setdat[m] and self.hasMobRespawned(m, field):
                out.append(m)
        return out

    #check which mobs have respawned in the field and reset their timings
    def setMobTimer(self, field):
        if not field in regularMobTypesInFields: return
        timings = self.getTiming()
        mobs = regularMobTypesInFields[field]
        for m in mobs:
            timingName = self.formatMobTimingName(m, field)
            if not timingName in timings:
                continue
            #check respawn
            if self.hasMobRespawned(m, field, timings[timingName]):
                timings[timingName] = time.time()
                self.hourlyReport.addHourlyStat("bugs", regularMobQuantitiesInFields[field][m])
        settingsManager.saveDict(settingsManager.getUserDataPath("timings.txt"), timings)

    #background thread function to determine if player has defeated the mob
    #time limit of 20s
    def mobRunAttackingBackground(self):
        st = time.time()
        if self.setdat["bees"] > 40:
            timeout = 20
        elif self.setdat["bees"] > 30:
            timeout = 30
        else:
            timeout = 40

        while True:
            screen = self.blueTextScreen()
            if self.blueTextImageSearch("died", screen=screen):
                self.mobRunStatus = "dead"
                break
            elif self.blueTextImageSearch("defeated", screen=screen):
                self.mobRunStatus = "looting"
                break
            elif time.time() - st > timeout:
                self.mobRunStatus = "timeout"
                break

    #background thread to check if token link is collected or the macro runs out of time (max 15s)
    def mobRunLootingBackground(self):
        st = time.time()
        while time.time() - st < 20:
           if self.blueTextImageSearch("tokenlink", 0.8):
            time.sleep(0.5) 
            self.logger.webhook("","Collected Token Link", "white", "blue")
            break
        self.mobRunStatus = "done"

    def killMob(self, mob, field, walkPath = None):
        mobName = mob
        if mob == "rhinobeetle": mobName = "rhino beetle"
        self.set_task_status("bugrun", activity=mob, details=f"Attacking in {field.title()}")
        self.logger.webhook("","{}: {} ({})".format("Travelling" if walkPath is None else "Walking", mobName.title(),field.title()),"dark brown")
        self.mobRunStatus = "attacking"
        attackThread = threading.Thread(target=self.mobRunAttackingBackground)
        attackThread.daemon = True
        if walkPath is None:
            self.waitForBees()
            if not self.travelViaCannon(f"{mobName.title()}"):
                return
            self.goToField(field, "north")
            #attack the mob
            attackThread.start()
        else:
            #attack the mob
            #attack thread will start in the path
            self.canDetectNight = False
            exec(walkPath)
            self.canDetectNight = True
        self.location = field
        self.logger.webhook("","Attacking: {} ({})".format(mobName.title(),field.title()),"dark brown")
        
        st = time.time()
        def updateHourlyTime():
            self.hourlyReport.addHourlyStat("bug_run_time", time.time()-st)
        #move in squares to evade attacks
        #save the last entered side and front keys. This will be used for the looting pattern
        distance = 0.7
        lastSideKey = "d"
        lastFrontKey = "s"
        def dodgeWalk(k,t):
            nonlocal lastSideKey, lastFrontKey
            if k in ["w", "s"]: lastFrontKey = k
            elif k in ["a","d"]: lastSideKey = k
            self.keyboard.walk(k, t)
        while True:
            # Check if paused and wait
            if self.checkPauseAndWait():
                # Stop was requested while paused
                self.mobRunStatus = "done"
                break
            dodgeWalk("s", distance*1.2)
            if self.mobRunStatus != "attacking": break
            dodgeWalk("a", distance*1.8)
            if self.mobRunStatus != "attacking": break
            dodgeWalk("w", distance*1.2)
            if self.mobRunStatus != "attacking": break
            dodgeWalk("d", distance*1.8)
            if self.mobRunStatus != "attacking": break

        attackThread.join()
        if self.mobRunStatus == "dead":
            self.logger.webhook("","Player died", "dark brown","screen", ping_category="ping_character_deaths")
            updateHourlyTime()
            return
        elif self.mobRunStatus == "timeout":
            self.setMobTimer(field)
            self.logger.webhook("","Could not kill {} in time. Maybe it hasn't respawned?".format(mobName.title()), "dark brown", "screen")
            updateHourlyTime()
            return
        time.sleep(1.5)
        #loot
        self.logger.webhook("", "Looting: {}".format(mobName.title()), "bright green", "screen")
        #start another background thread to check for token link/time limit
        lootThread = threading.Thread(target=self.mobRunLootingBackground)
        lootThread.daemon = True
        lootThread.start()
        def lootPattern(f, s):
            if lastSideKey == "a":
                startSideKey = "d"
            elif lastSideKey == "d":
                startSideKey = "a"

            if lastFrontKey == "w":
                startFrontKey = "s"
            elif lastFrontKey == "s":
                startFrontKey = "w"

            while True:
                # Check if paused and wait
                if self.checkPauseAndWait():
                    return  # Stop was requested
                for _ in range(2):
                    self.keyboard.walk(startFrontKey, 0.72*f)
                    if self.mobRunStatus == "done": return
                    self.keyboard.walk(startSideKey, 0.1*s)
                    if self.mobRunStatus == "done": return
                    self.keyboard.walk(lastFrontKey, 0.72*f)
                    if self.mobRunStatus == "done": return
                    self.keyboard.walk(startSideKey, 0.1*s)
                    if self.mobRunStatus == "done": return
                for _ in range(2):
                    self.keyboard.walk(startFrontKey, 0.72*f)
                    if self.mobRunStatus == "done": return
                    self.keyboard.walk(lastSideKey, 0.1*s)
                    if self.mobRunStatus == "done": return
                    self.keyboard.walk(lastFrontKey, 0.72*f)
                    if self.mobRunStatus == "done": return
                    self.keyboard.walk(lastSideKey, 0.1*s)
                    if self.mobRunStatus == "done": return
        lootPattern(1.35, 2.5)
        self.setMobTimer(field)
        self.clear_task_status()
        lootThread.join()
        #check if there are paths for the macro to walk to other fields for mob runs
        #run a path in the field format
        updateHourlyTime()
        self.runPath(f"mob_runs/{field}", fileMustExist=False)

    def stingerHuntBackground(self):
        #find vic
        while not self.stopVic:
            screen = self.blueTextScreen()
            #detect which field the vic is in
            if self.vicField is None:
                for field in self.vicFields:
                    if self.blueTextImageSearch(f"vic{field}", 0.75, screen=screen):
                        self.vicField = field
                        break
            else:
                if self.blueTextImageSearch("died", screen=screen): self.died = True
            
            if self.blueTextImageSearch("vicdefeat", screen=screen):
                self.vicStatus = "defeated"

    def stingerHunt(self):
        self.set_task_status("stinger_hunt", activity="stinger_hunt")
        try:
            result = self.viciousSearchRoute()
            if result:
                self.logger.webhook("", "Defeated Vicious Bee", "light green", "screen", ping_category="ping_vicious_bee")
            self.reset()
            return result
        finally:
            self.night = False

    def stumpSnail(self):
        sideTaskIntervalMinutes = self.setdat.get("stump_snail_balloon_interval", 0)
        try:
            sideTaskInterval = max(0, int(sideTaskIntervalMinutes)) * 60
        except (TypeError, ValueError):
            sideTaskInterval = 0
        patternDuration = 120

        def goToStump():
            for _ in range(3):
                self.cannon()
                self.logger.webhook("", "Travelling: Stump Snail", "dark brown")
                self.goToField("stump")
                if self.placeSprinkler():
                    return True
                self.logger.webhook("", "Failed to land in stump field", "red", "screen", ping_category="ping_critical_errors")
                self.reset()
            return False

        def runGatherPattern(patternName, field, duration):
            st = time.time()
            mouse.moveBy(10, 5)
            self.keyboard.releaseMovement()
            # patterns read the field's size, width and movement keys, as in a normal gather
            nameSpace = {
                **locals(),
                **field_pattern_variables(self.fieldSettings.get(field, {})),
                **vars(patternEnvironment),
                "setPatternYaw": lambda targetYaw: None,
            }
            patternRunner = GatherPatternRunner(
                settingsManager.getProjectRoot(),
                patternName,
                alert=lambda failedPattern, error: self.logger.webhook(
                    "Gather Pattern Failed",
                    f"{failedPattern}: {error}. Using e_lol for the rest of this side task.",
                    "red",
                    ping_category="ping_critical_errors",
                ),
                fatal_exceptions=(InterruptRequested,),
            )
            try:
                while time.time() - st < duration:
                    if self.checkPauseAndWait():
                        break
                    mouse.mouseDown()
                    try:
                        patternRunner.run_cycle(nameSpace, owner=self)
                    except InterruptRequested:
                        raise
                    except Exception:
                        print(traceback.format_exc())
                        break
                    mouse.mouseUp()
            finally:
                mouse.mouseUp()
                patternRunner.finish(nameSpace)

        def runSideTask():
            self.logger.webhook("", "Stump Snail: Running periodic side task", "dark brown")
            self.reset(convert=False)
            if self.travelViaCannon("Stump Snail side task", resetIfAway=False):
                self.goToField("pine tree")
                runGatherPattern("skillet", "pine tree", patternDuration)
                self.reset(convert=True)
            return goToStump()

        if not goToStump():
            return

        # Set status to attacking for hotbar logic
        self.set_task_status("attacking", activity="stump_snail")
        try:
            keepOldData = None
            while keepOldData is None:
                cycleStart = time.time()
                if self.checkPauseAndWait():
                    return
                while True:
                    if self.checkPauseAndWait():
                        return
                    mouse.click()
                    keepOldData = self.keepOldCheck()
                    if keepOldData is not None:
                        mouse.mouseUp()
                        break
                    if sideTaskInterval <= 0 or time.time() - cycleStart >= sideTaskInterval:
                        mouse.mouseUp()
                        break

                if keepOldData is None and sideTaskInterval > 0 and not runSideTask():
                    return
        finally:
            self.set_task_status(None, update_presence=False)  # Reset status after attack
        #handle the other stump snail
        self.logger.webhook("","Stump Snail Killed","bright green", "screen", ping_category="ping_mob_events")
        self.saveTiming("stump_snail")
        def keepOld():
            time.sleep(0.5)
            mouse.moveTo(*keepOldData)
            mouse.click()

        def replace():
            replaceImg = self.adjustImage("./images/menu", "replace")
            x = self.robloxWindow.mx + self.robloxWindow.mw/2-300
            y = self.robloxWindow.my
            res = locateImageOnScreen(replaceImg, x, y, 650, self.robloxWindow.mh, 0.8)
            if res is not None:
                ix, iy = [j//self.robloxWindow.multi for j in res[1]]
                mouse.moveTo(x + ix + 5, y + iy + 5)
                mouse.click()
                return
            if keepOldData is not None:
                mouse.moveTo(keepOldData[0] + 170, keepOldData[1])
                mouse.click()
        amulet = self.setdat["stump_snail_amulet"]
        if amulet == "keep":
            keepOld()
        elif amulet == "replace":
            replace()
        elif amulet == "stop":
            while self.keepOldCheck(): mouse.click()
        elif amulet == "wait for command":
            self.set_task_status("amulet_wait", update_presence=False)
            #wait for user to send command to bot
            while self.status.value == "amulet_wait": mouse.click()
            if self.status.value == "amulet_keep":
                keepOld()
            elif self.status.value == "amulet_replace":
                replace()

        self.clear_task_status()

    #implementation of natro's nm_loot function
    def nmLoot(self, length, reps, dirKey):
        for _ in range(reps):
            self.keyboard.tileWalk("w", length)
            self.keyboard.tileWalk(dirKey, 1.5)
            self.keyboard.tileWalk("s", length)
            self.keyboard.tileWalk(dirKey, 1.5)

    def coconutCrabBackground(self):
        while self.bossStatus is None:
            screen = self.blueTextScreen()
            if self.blueTextImageSearch("died", screen=screen):
                self.died = True
            if self.blueTextImageSearch("coconutcrab_defeat", 0.8, screen=screen):
                self.bossStatus = "defeated"

    def coconutCrab(self):
        self.bossStatus = None
        self.set_task_status("coconut_crab", activity="coconut_crab")
        cocoThread = threading.Thread(target=self.coconutCrabBackground)
        cocoThread.daemon = True
        cocoThread.start()
        st = time.time()
        for _ in range(2):
            if not self.travelViaCannon("Coconut Crab"):
                self.bossStatus = "travel_failed"
                cocoThread.join()
                return
            self.logger.webhook("","Travelling: Coconut Crab","dark brown")
            self.goToField("coconut")
            self.keyboard.walk("s", 1)
            self.keyboard.walk("d", 3)
            self.died = False
            self.bossStatus = None
            st = time.time()
            while True:
                mouse.mouseDown()
                #simplified version of natro's coco crab pattern
                for i in range(2):
                    self.keyboard.walk("a",6, False)
                    self.keyboard.walk("d",6-i*1.8, False)
                self.keyboard.walk("s",2)
                time.sleep(4.5)
                self.keyboard.walk("w",1)
                mouse.mouseUp()
                # Respect user-configurable max kill time (minutes)
                max_kill_time = self.setdat.get("coconut_crab_max_kill_time", 15)
                if time.time() - st > max_kill_time * 60:
                    self.bossStatus = "timelimit"
                if self.died or self.bossStatus is not None: break
            
            if self.died:
                self.logger.webhook("", "Died to Coconut Crab", "dark brown", ping_category="ping_character_deaths")
                self.reset(convert=False)
                self.died = False
            elif self.bossStatus is not None:
                break
            
        if self.bossStatus == "timelimit":
            self.logger.webhook("", "Time Limit: Coconut Crab", "dark brown", ping_category="ping_critical_errors")
        elif self.bossStatus == "defeated":
            self.keyboard.walk("a", 2)
            self.logger.webhook("", "Defeated: Coconut Crab", "bright green", "screen", ping_category="ping_mob_events")
            self.nmLoot(9, 4, "d")
            self.nmLoot(9, 4, "a")
            self.nmLoot(9, 4, "d")
            self.nmLoot(9, 4, "a")
            self.nmLoot(9, 4, "d")
            self.nmLoot(9, 4, "a")
        cocoThread.join()
        self.hourlyReport.addHourlyStat("bug_run_time", time.time()-st)
        self.saveTiming("coconut_crab")
        self.clear_task_status()
        self.reset()

    def kingBeetle(self):
        st = time.time()
        for _ in range(2):
            if not self.travelViaCannon("King Beetle"):
                return
            self.logger.webhook("","Travelling: King Beetle","dark brown")
            self.goToField("blue_flower")
            self.died = False
            self.bossStatus = None
            self.runPath("boss/king_beetle")

            # Continue the movement pattern and check for defeat
            while self.bossStatus is None and not self.died:
                screen = self.blueTextScreen()
                # Check if defeated
                if self.blueTextImageSearch("defeated", screen=screen):
                    self.bossStatus = "defeated"
                    break
                # Check if died
                if self.blueTextImageSearch("died", screen=screen):
                    self.died = True
                    break
                # Continue movement
                self.keyboard.walk("d", 0.25)
                sleep(0.75)

            # Collect rewards if defeated
            if self.bossStatus == "defeated":
                self.keyboard.walk("a", 1)
                self.keyboard.walk("w", 3)
                for i in range(3):
                    self.keyboard.walk("a", 0.25)
                    self.keyboard.walk("s", 2)
                    self.keyboard.walk("a", 0.25)
                    self.keyboard.walk("w", 2)
                sleep(1)

            if self.died or self.bossStatus is not None: break

        if self.died:
            self.logger.webhook("", "Died to King Beetle", "dark brown", ping_category="ping_character_deaths")
            self.reset(convert=False)
            self.died = False
        elif self.bossStatus == "defeated":
            self.logger.webhook("", "Defeated: King Beetle", "bright green", "screen", ping_category="ping_mob_events")
        self.hourlyReport.addHourlyStat("bug_run_time", time.time()-st)
        self.saveTiming("king_beetle")
        self.reset()

    def tunnelBear(self):
        st = time.time()
        for _ in range(2):
            if not self.travelViaCannon("Tunnel Bear"):
                return
            self.logger.webhook("","Travelling: Tunnel Bear","dark brown")
            self.goToField("pineapple")
            self.died = False
            self.bossStatus = None
            self.runPath("boss/tunnel_bear")
            
            # Continue the movement pattern and check for defeat
            while self.bossStatus is None and not self.died:
                screen = self.blueTextScreen()
                # Check if defeated
                if self.blueTextImageSearch("defeated", screen=screen):
                    self.bossStatus = "defeated"
                    break
                # Check if died
                if self.blueTextImageSearch("died", screen=screen):
                    self.died = True
                    break
                # Continue movement
                self.keyboard.walk("d", 0.25)
                sleep(0.75)

            # Collect rewards if defeated
            if self.bossStatus == "defeated":
                self.keyboard.walk("d", 2.5)
                self.keyboard.walk("a", 5)
                sleep(1)
            if self.died or self.bossStatus is not None: break

        if self.died:
            self.logger.webhook("", "Died to Tunnel Bear", "dark brown", ping_category="ping_character_deaths")
            self.reset(convert=False)
            self.died = False
        elif self.bossStatus == "defeated":
            self.logger.webhook("", "Defeated: Tunnel Bear", "bright green", "screen", ping_category="ping_mob_events")
        self.hourlyReport.addHourlyStat("bug_run_time", time.time()-st)
        self.saveTiming("tunnel_bear")
        self.reset()
