import os
import modules.controls.mouse as mouse
import modules.misc.appManager as appManager
from modules.controls.sleep import pause_aware_time as time, sleep
from modules.macro.game_data import (
    fieldFaceNorthKeys,
    HIVE_HUB_PLACE_ID,
    REJOIN_COLOR_PERCENT,
    hiveHubStartLocationOffsets,
)
from modules.screen.color_check import get_sample_colors, percent_pixels_similar_to_color


class NavigationMixin:
    #run a path. Choose automater over python if it exists
    #file must exist: if set to False, will not attempt to run the file if it doesnt exist
    def runPath(self, name, fileMustExist = True):
        ws = self.setdat["movespeed"]  # read by path files
        path = f"../paths/{name}"
        #try running a automator workflow
        #if it doesnt exist, run the .py file instead

        if os.path.exists(path+".workflow"):
            os.system(f"/usr/bin/automator {path}.workflow")
        else:
            pyPath = f"{path}.py"
            #ensure that path exists
            if not fileMustExist and not os.path.isfile(pyPath): return
            exec(open(pyPath).read())

    def faceDirection(self, field, dir):
        keys = fieldFaceNorthKeys[field]
        if dir == "south": #invert the keys
            if keys is None:
                keys = ["."]*4
            elif len(keys) == 4:
                keys = None
            else:
                keys = ["." if x == "," else "," for x in keys]
        
        if keys is not None:
            for k in keys:
                self.keyboard.press(k)

    #run the path to go to a field
    #faceDir what direction to face after landing in a field (default, north, south)
    def goToField(self, field, faceDir = "default", startLocation = "center"):
        # Accept a string or a list/tuple of tokens/words and normalize to a
        # single field name (e.g. ["blue", "flower"] -> "blue flower").
        if isinstance(field, (list, tuple)):
            try:
                field = " ".join([str(f) for f in field])
            except Exception:
                field = str(field)

        # Normalize field name to handle both space and underscore formats
        normalized_field = str(field).replace('_', ' ').strip()
        self.location = normalized_field
        if normalized_field == "hive hub":
            startLocation = str(startLocation or "center").replace("_", " ").strip().lower()
            if startLocation not in hiveHubStartLocationOffsets:
                startLocation = "center"
            self.rejoin(
                rejoinMsg="Travelling: Hive Hub",
                placeId=HIVE_HUB_PLACE_ID,
                claimHive=False,
                usePrivateServer=bool(self.setdat.get("hive_hub_private_server", False)),
            )
            #HIVE HUB PATH
            self.keyboard.press("shift")
            self.keyboard.keyDown("w")
            time.sleep(6)
            self.keyboard.keyUp("w")
            self.keyboard.keyDown("d")
            time.sleep(0.5)
            self.keyboard.keyUp("d")
            self.keyboard.keyDown("w")
            time.sleep(1.25)
            self.keyboard.keyUp("w")
            self.keyboard.keyDown("a")
            time.sleep(0.5)
            self.keyboard.keyUp("a")
            self.keyboard.press(".")
            self.keyboard.press(".")
            self.keyboard.press("O")
            self.keyboard.press("O")
            self.keyboard.press("O")
            self.keyboard.press("O")
            for key, seconds in hiveHubStartLocationOffsets[startLocation]:
                self.keyboard.keyDown(key)
                time.sleep(seconds)
                self.keyboard.keyUp(key)
            self.keyboard.press("shift")
            return
        self.runPath(f"cannon_to_field/{normalized_field}")
        if faceDir == "default": return
        self.faceDirection(normalized_field, faceDir)

    def moveMouseToDefault(self):
        mouse.moveTo(self.robloxWindow.mx+370, self.robloxWindow.my+self.robloxWindow.yOffset+110)

    def setCameraPitch(self, target_pitch, current_pitch=0):
        """
        Adjust camera pitch with PageUp/PageDown.
        Higher pitch = look up. Practical range: about -6..3.
        """
        try:
            target_pitch = int(target_pitch)
        except (TypeError, ValueError):
            target_pitch = 0
        target_pitch = max(-6, min(3, target_pitch))
        try:
            current_pitch = int(current_pitch)
        except (TypeError, ValueError):
            current_pitch = 0

        delta = target_pitch - current_pitch
        if delta == 0:
            return target_pitch
        key = "pageup" if delta > 0 else "pagedown"
        for _ in range(abs(delta)):
            self.keyboard.keyDown(key, False)
            time.sleep(0.01)
            self.keyboard.keyUp(key, False)
            time.sleep(0.01)
        return target_pitch

    def setCameraZoom(self, target_zoom, current_zoom=0):
        """
        Adjust camera zoom with I/O. Higher zoom = more zoomed out (O).
        Range 0..5.
        """
        try:
            target_zoom = int(target_zoom)
        except (TypeError, ValueError):
            target_zoom = 0
        target_zoom = max(0, min(5, target_zoom))
        try:
            current_zoom = int(current_zoom)
        except (TypeError, ValueError):
            current_zoom = 0

        delta = target_zoom - current_zoom
        if delta == 0:
            return target_zoom
        key = "o" if delta > 0 else "i"
        for _ in range(abs(delta)):
            self.keyboard.keyDown(key, False)
            time.sleep(0.01)
            self.keyboard.keyUp(key, False)
            time.sleep(0.01)
        return target_zoom

    def cannon(self, fast = False, allowHiveResync = True, allowRejoin = True):
        def detect_rejoin_mode_color():
            try:
                if not appManager.isAppFocused("Roblox"):
                    return None
                percent_threshold = REJOIN_COLOR_PERCENT
                color_tolerance = int(self.setdat.get("rejoin_color_tolerance", 40))
                sample_colors = get_sample_colors()
                for col in sample_colors:
                    pct = percent_pixels_similar_to_color(
                        self.robloxWindow.mx,
                        self.robloxWindow.my,
                        self.robloxWindow.mw,
                        self.robloxWindow.mh,
                        col,
                        tolerance=color_tolerance,
                    )
                    if pct >= percent_threshold:
                        return col
            except Exception:
                pass
            return None

        try:
            max_attempts = int(self.setdat.get("max_cannon_attempts", 3))
        except (TypeError, ValueError):
            max_attempts = 3
        max_attempts = max(1, max_attempts)
        try:
            hive_resync_attempts = int(self.setdat.get("cannon_hive_resync_attempts", 0))
        except (TypeError, ValueError):
            hive_resync_attempts = 0
        hive_resync_attempts = max(0, hive_resync_attempts)
        if hive_resync_attempts >= max_attempts:
            hive_resync_attempts = max(0, max_attempts - 1)
        first_attempt_color = None
        for i in range(max_attempts):
            if self.cannonFromHive:
                hiveNumber = self.setdat["hive_number"]
            else:
                hiveNumber = 3
            forwardTime = 0.8 if self.cannonFromHive else 0.2
            self.keyboard.walk("w", forwardTime / 2)
            self.keyboard.walk("d", 1.2 * hiveNumber + i + 1)
            self.keyboard.keyDown("d")
            time.sleep(0.5)
            self.keyboard.slowPress("space")
            time.sleep(0.2)
            self.keyboard.keyDown("d")
            self.keyboard.walk("w", 0.2)

            if fast:
                self.keyboard.walk("d", 0.95)
                time.sleep(0.1)
                return True
            self.keyboard.walk("d", 0.2)
            self.keyboard.walk("s", 0.07)
            startTime = time.time()
            self.keyboard.keyDown("d")
            foundCannon = False
            while time.time() - startTime < 0.9:
                if self.isBesideEImage("cannon"):
                    foundCannon = True
                    break
            self.keyboard.keyUp("d")
            if foundCannon:
                for _ in range(3):
                    time.sleep(0.4)
                    if self.isBesideEImage("cannon"):
                        return True
                    self.keyboard.walk("a", 0.2)
            self.logger.webhook("Notice", f"Could not find cannon (attempt {i + 1}/{max_attempts})", "dark brown", "screen")
            detected_color = detect_rejoin_mode_color()
            if allowHiveResync and hive_resync_attempts and i + 1 >= hive_resync_attempts:
                if self.resyncHiveSlotFromHive():
                    return self.cannon(fast=fast, allowHiveResync=False, allowRejoin=allowRejoin)
                self.logger.webhook("", "Hive slot recheck failed; rejoining", "dark brown", "screen")
                if allowRejoin and self.rejoin():
                    return self.cannon(fast=fast, allowHiveResync=False, allowRejoin=False)
                return False

            if i < max_attempts - 1:
                first_attempt_color = detected_color
                if detected_color is not None:
                    retries_left = max_attempts - (i + 1)
                    retry_label = "time" if retries_left == 1 else "times"
                    self.logger.webhook("", f"Detected light/dark-mode screen while searching for cannon. Resetting and retrying cannon search ({retries_left} {retry_label} remaining).", "dark brown", "screen")
                self.reset(convert=False)
                continue

            if detected_color is not None and first_attempt_color is not None and tuple(detected_color) == tuple(first_attempt_color):
                self.logger.webhook("", "Detected the same light/dark-mode color again after reset while searching for cannon. Rejoining.", "dark brown", "screen")
            elif detected_color is not None:
                self.logger.webhook("", "Detected light/dark-mode screen again while searching for cannon. Rejoining.", "dark brown", "screen")
            self.logger.webhook(
                "Notice",
                f"Failed to reach cannon after {max_attempts} attempts" + ("; rejoining" if allowRejoin else "; aborting travel"),
                "red",
                ping_category="ping_critical_errors",
            )
            if allowRejoin and self.rejoin():
                return self.cannon(fast=fast, allowHiveResync=False, allowRejoin=False)
            return False
        return False

    def travelViaCannon(self, context="Travel", resetIfAway=True, convertOnReset=False):
        if resetIfAway and self.location != "spawn":
            self.logger.webhook("", f"Returning to hive before {context.lower()}", "dark brown")
            if not self.reset(convert=convertOnReset):
                return False
        if self.cannon():
            return True
        self.logger.webhook(
            f"{context}: aborted",
            "Could not confirm cannon access before travel",
            "red",
            "screen",
            ping_category="ping_critical_errors",
        )
        return False

    #use the accurate sleep and sleep for ms
    def sleepMSMove(self, key, time):
        self.keyboard.keyDown(key, False)
        sleep(time/1000)
        self.keyboard.keyUp(key, False)
