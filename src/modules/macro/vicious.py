import modules.controls.mouse as mouse
from modules.controls.sleep import pause_aware_time as time, sleep


class ViciousMixin:
    def recordVicStat(self, name, amount=1):
        if self.setdat.get("macro_mode") == "vic":
            self.hourlyReport.addHourlyStat("vic_" + name, amount)

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
                        self.recordVicStat("deaths")
                        break
                if died:
                    break
                if self.checkIfViciousDied():
                    self.hourlyReport.addHourlyStat("vicious_bees", 1)
                    self.recordVicStat("defeats")
                    self.recordVicStat("stingers", getattr(self, "_viciousRewardAmount", 0))
                    return True
            if not died:
                return False
            # A kill announced right before the death still counts.
            if self.checkIfViciousDied():
                self.hourlyReport.addHourlyStat("vicious_bees", 1)
                self.recordVicStat("defeats")
                self.recordVicStat("stingers", getattr(self, "_viciousRewardAmount", 0))
                return True
            if not self.viciousReturnToField():
                return False


    def viciousResetCamera(self):
        """Restore the pitch expected by hive reset and normal travel."""
        for _ in range(10):
            self.keyboard.press("pageup")
        for _ in range(4):
            self.keyboard.press("pagedown")


    def viciousReturnToField(self):
        """After dying mid fight, walk back to the same field on this server."""
        field = self.viciousField
        self.keyboard.releaseMovement()
        self.logger.webhook("Vic Hop", f"Died fighting the Vicious Bee in {field.title()}, returning to the same field", "red", "screen", ping_category="ping_character_deaths")
        if self.checkPauseAndWait():
            return False
        self.set_task_status("stinger_hunt", activity=field.title())
        # cannon(allowRejoin=False): a failed cannon must not hop to another server.
        self.viciousResetCamera()
        if not (self.reset(convert=False) and self.cannon(allowHiveResync=False, allowRejoin=False)):
            self.logger.webhook("Vic Hop", f"Could not return to {field.title()} after dying, ending the hunt", "orange", "screen", ping_category="ping_vicious_bee")
            return False
        self.goToField(field, "north")
        self.recordVicStat("returns")
        self.logger.webhook("Vic Hop", f"Back in {field.title()}, fighting the Vicious Bee again", "yellow", "screen", ping_category="ping_vicious_bee")
        return True


    def detectViciousAnnouncement(self, text, now):
        """Remember a live attack notification, never old chat history."""
        import re
        match = re.search(r"\bvicious bee is attacking\s+[^:]+?\s+in the\s+(pepper|mountain top|spider|cactus|rose)\s+(?:field|patch)\b", text.lower())
        announcement = match.group(0) if match else None
        if announcement is not None and announcement != getattr(self, "_viciousLastAttack", None):
            field = match.group(1)
            if self.setdat.get("macro_mode", "normal") == "vic" or field in self.vicFields:
                self._viciousAttackTarget = (field, now)
        self._viciousLastAttack = announcement

    def viciousFightAnnouncedField(self):
        target = getattr(self, "_viciousAttackTarget", None)
        self._viciousAttackTarget = None
        if target is None or time.time() - target[1] > 180:
            return None
        field = target[0]
        if self.setdat.get("macro_mode", "normal") != "vic" and field not in self.vicFields:
            return None
        if self.checkPauseAndWait():
            return False
        if time.time() - target[1] > 180:
            return None
        self.recordVicStat("sightings")
        self.viciousField = field
        self.set_task_status("stinger_hunt", activity=field.title())
        self.logger.webhook("Vicious Bee", f"Attack announced in {field.title()}, travelling to fight", "yellow", "screen", ping_category="ping_vicious_bee")
        self.viciousActivateChat()
        self._viciousAnnouncementBaseline = self._viciousAnnouncementCounts()
        self.ensure_shift_lock_off(reason="Travel to announced Vicious Bee")
        self.viciousResetCamera()
        if not self.reset(convert=False) or not self.cannon(allowHiveResync=False, allowRejoin=False):
            return False
        self.goToField(field, "north")
        result = self.viciousKillPattern()
        self.logger.webhook("Vicious Bee", "Vicious Bee defeated" if result else "Vicious Bee hunt ended without a confirmed defeat", "light green" if result else "orange", "screen", ping_category="ping_vicious_bee")
        return result

    def viciousSearchRoute(self):
        # Camera sensitivity and key-delay defaults for the Vicious route.
        self.setdat.setdefault("vicious_camera_sensitivity", 1)
        self.setdat.setdefault("vicious_key_delay_ms", 20)
        def search(field, approach):
            result = self.viciousFightAnnouncedField()
            if result is not None:
                return result
            self.set_task_status("stinger_hunt", activity=field)
            self.viciousField = field.replace(" back", "").lower()
            if self.setdat.get("macro_mode", "normal") != "vic" and self.viciousField not in self.vicFields:
                return None
            if not self.detectViciousBee():
                self.logger.webhook("Vic Hop", f"{field}: no Vicious Bee detected", "dark brown", "screen")
                return None
            self.recordVicStat("sightings")
            self.logger.webhook("Vic Hop", f"Vicious Bee detected in {field}, approaching", "yellow", "screen", ping_category="ping_vicious_bee")
            self.viciousActivateChat()
            self._viciousAnnouncementBaseline = self._viciousAnnouncementCounts()
            result = self.runPath(approach)
            self.logger.webhook("Vic Hop", "Vicious Bee defeated" if result else "Vicious Bee hunt ended without a confirmed defeat", "light green" if result else "orange", "screen", ping_category="ping_vicious_bee")
            return result
        result = self.viciousFightAnnouncedField()
        if result is not None:
            return result
        self.logger.webhook("Vic Hop", "Hive ready, checking fields starting with Pepper", "dark brown", "screen")
        self.runPath("vic/travel/hive_to_pepper")
        result = search("Pepper", "vic/kill_vic/pepper")
        if result is not None:
            return result
        if not self.runPath("vic/travel/pepper_to_mountain_top"):
            return False
        result = self.viciousFightAnnouncedField()
        if result is not None:
            return result
        # Detect before rotating toward the next field.
        enabled = self.setdat.get("macro_mode", "normal") == "vic" or "mountain top" in self.vicFields
        found = enabled and self.detectViciousBee()
        self.viciousRotate("right", 1)
        if found:
            self.recordVicStat("sightings")
            self.viciousField = "mountain top"
            self.logger.webhook("Vic Hop", "Vicious Bee detected in Mountain Top, approaching", "yellow", "screen", ping_category="ping_vicious_bee")
            self.viciousActivateChat()
            self._viciousAnnouncementBaseline = self._viciousAnnouncementCounts()
            result = self.runPath("vic/kill_vic/mountain top")
            self.logger.webhook("Vic Hop", "Vicious Bee defeated" if result else "Vicious Bee hunt ended without a confirmed defeat", "light green" if result else "orange", "screen", ping_category="ping_vicious_bee")
            return result
        self.logger.webhook("Vic Hop", "Mountain Top: no Vicious Bee detected", "dark brown", "screen")
        self.runPath("vic/travel/mountain_top_to_edge")
        self.runPath("vic/travel/edge_to_spider")
        result = search("Spider", "vic/kill_vic/spider")
        if result is not None:
            return result
        self.runPath("vic/travel/spider_to_cactus")
        for key, count in (("pagedown", 10), ("pageup", 2)):
            for _ in range(count):
                self.keyboard.press(key)
                sleep((10 + self.setdat["vicious_key_delay_ms"]) / 1000)
        result = search("Cactus", "vic/kill_vic/cactus")
        if result is not None:
            return result
        for _ in range(5):
            self.keyboard.keyDown("pagedown", False)
            sleep((10 + self.setdat["vicious_key_delay_ms"]) / 1000)
            self.keyboard.keyUp("pagedown", False)
            sleep((10 + self.setdat["vicious_key_delay_ms"]) / 1000)
        result = search("Cactus back", "vic/kill_vic/cactus")
        if result is not None:
            return result
        self.runPath("vic/travel/cactus_to_rose")
        result = search("Rose", "vic/kill_vic/rose")
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
        self.viciousResetCamera()
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
            self._viciousOpenedChat = (win.mx + point[0], win.my + point[1])
            mouse.moveTo(*self._viciousOpenedChat)
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
            if attempt + 1 < attempts:
                self.viciousResetCamera()
                if not self.reset(convert=False):
                    return False
        return False


    def _viciousAnnouncementCounts(self, frame=None):
        """Count system announcements so old chat cannot confirm a new fight."""
        import cv2
        import re
        from PIL import Image
        from modules.screen.ocr import ocrRead
        from modules.screen.screenshot import mssScreenshotNP
        if frame is None:
            win = self.robloxWindow
            frame = mssScreenshotNP(win.mx, win.my, win.mw, win.mh)
            frame = cv2.resize(frame, (win.mw, win.mh), interpolation=cv2.INTER_AREA)
        height, width = frame.shape[:2]
        region = frame[:height // 2, width // 2:, :3]
        readable = cv2.resize(region, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        image = Image.fromarray(cv2.cvtColor(readable, cv2.COLOR_BGR2RGB))
        counts = {"vicsummon": 0, "vicdead": 0}
        defeat_lines = reward_lines = 0
        reward_amount = 0
        field = getattr(self, "viciousField", None)
        for item in ocrRead(image):
            text = " ".join(item[1][0].lower().split())
            # Warning icons can OCR as L, TA, or other short prefixes.
            # Colons identify player chat rather than a system announcement.
            if re.match(r"^(?!.*:).{0,3}vicious bee is attacking\b", text):
                if field is None or re.search(r"\bin the " + re.escape(field) + r"\b", text):
                    counts["vicsummon"] += 1
            if re.match(r"^(?!.*:).{0,3}vicious bee (?:has been )?defeated\b", text):
                defeat_lines += 1
            if re.match(r"^\W*\+\s*\d+\s+stingers?\s*\(from vicious bee\b", text):
                reward_lines += 1
                reward_amount += int(re.search(r"\+\s*(\d+)", text).group(1))
        counts["vicdead"] = max(defeat_lines, reward_lines)
        counts["stingers"] = reward_amount
        return counts

    def viciousNotification(self, name, frame=None):
        if name not in ("vicsummon", "vicdead"):
            raise ValueError("Unknown Vicious notification")
        counts = self._viciousAnnouncementCounts(frame)
        count = counts[name]
        if name == "vicsummon":
            # The model has already found a bee; accept this field's attack
            # even if it started before the approach snapshot.
            return count > 0
        baseline = getattr(self, "_viciousAnnouncementBaseline", {})
        self._viciousRewardAmount = max(0, counts["stingers"] - baseline.get("stingers", 0))
        return count > baseline.get(name, 0)


    def checkIfVicSummoned(self, frame=None):
        if frame is None:
            self.viciousActivateChat()
        return self.viciousNotification("vicsummon", frame)


    def checkIfViciousDied(self, frame=None):
        if frame is None:
            self.viciousActivateChat()
        return self.viciousNotification("vicdead", frame)


    def _loadViciousModel(self):
        import cv2
        from modules.misc.modelManager import MODEL_DIR, VICIOUS_MODEL, ensure_missing_models
        import os

        if not hasattr(self, "_viciousModel"):
            result = ensure_missing_models((VICIOUS_MODEL,))
            if result["failures"]:
                raise RuntimeError(f"Could not download Vicious Bee model: {result['failures']}")
            self._viciousModel = cv2.dnn.readNetFromONNX(os.path.join(MODEL_DIR, VICIOUS_MODEL))

    def detectViciousBee(self, frame=None):
        """Detect Vicious Bee in a BGRA frame, or capture the Roblox client."""
        import cv2
        import numpy as np
        from modules.screen.screenshot import mssScreenshotNP
        self._loadViciousModel()
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


    def viciousHop(self):
        """Run one server search; the main loop reloads settings between hops."""
        if self.checkPauseAndWait():
            return
        try:
            self._loadViciousModel()
        except Exception as exc:
            from modules.controls.sleep import InterruptRequested
            if isinstance(exc, InterruptRequested):
                raise
            self.logger.webhook("Vic Hop", f"Could not load Vicious Bee detection model: {exc}", "red", "screen")
            if self.run is not None:
                self.run.value = 0
            return
        self._viciousAttackTarget = None
        self._viciousLastAttack = None
        if not self.rejoin(rejoinMsg="Vic Hop", usePrivateServer=False, nightOnly=True):
            return
        if self.checkPauseAndWait():
            return
        stats = self.hourlyReport.hourlyReportStats
        if not stats["start_time"]:
            self.hourlyReport.setSessionStats(stats["start_honey"], time.time())
        if not stats["start_honey"]:
            honey = self.getHoney()
            if honey > 0:
                self.hourlyReport.setSessionStats(honey, stats["start_time"])
        self.viciousSearchRoute()
        self._viciousAttackTarget = None


    def stingerHunt(self):
        if not self.vicFields:
            self.night = False
            return False
        started = time.time()
        self._viciousOpenedChat = None
        self.set_task_status("stinger_hunt", activity="stinger_hunt")
        try:
            try:
                self._loadViciousModel()
            except Exception as exc:
                from modules.controls.sleep import InterruptRequested
                if isinstance(exc, InterruptRequested):
                    raise
                self.logger.webhook("Stinger Hunt", f"Could not load Vicious Bee detection model: {exc}", "orange", "screen")
                return False
            if self.location != "spawn":
                self.viciousResetCamera()
                if not self.reset(convert=False):
                    return False
            result = self.viciousSearchRoute()
        finally:
            self._viciousAttackTarget = None
            self.night = False
            self.viciousResetCamera()
            point = self._viciousOpenedChat
            if point is not None:
                mouse.moveTo(*point)
                mouse.click()
                self._viciousOpenedChat = None
            self.hourlyReport.addHourlyStat("bug_run_time", time.time() - started)
            # This can re-raise a pending interrupt during its pause-aware wait.
            # All other cleanup must already be complete.
            self.ensure_shift_lock_off(reason="Stinger Hunt cleanup")
        self.reset()
        return result
