import re
from datetime import datetime, timezone
import modules.controls.mouse as mouse
import modules.misc.appManager as appManager
import modules.misc.settingsManager as settingsManager
import modules.screen.ocr as ocr
from modules.controls.keyboard import keyboard
from modules.controls.sleep import pause_aware_time as time
from modules.macro.game_data import MAIN_GAME_PLACE_ID, REJOIN_COLOR_PERCENT
from modules.screen.color_check import get_sample_colors, percent_pixels_similar_to_color
from modules.screen.imageSearch import locateImageOnScreen
from modules.screen.screenshot import mssScreenshot


class RejoinMixin:
    def _parseRejoinAtTime(self):
        value = str(self.setdat.get("rejoin_at_time", "00:00")).strip()
        match = re.fullmatch(r"(\d{1,2}):(\d{2})(?::(\d{2}))?", value)
        if not match:
            return None

        hour = int(match.group(1))
        minute = int(match.group(2))
        second = int(match.group(3) or 0)
        if hour > 23 or minute > 59 or second > 59:
            return None

        return hour, minute, second

    def hasScheduledRejoinArrived(self):
        scheduleType = str(self.setdat.get("rejoin_schedule_type", "hours")).strip().lower()
        if scheduleType == "daily":
            rejoinTime = self._parseRejoinAtTime()
            if rejoinTime is None:
                print(f"Invalid rejoin_at_time setting: {self.setdat.get('rejoin_at_time')}")
                return False

            timeZone = str(self.setdat.get("rejoin_timezone", "local")).strip().lower()
            now = datetime.now(timezone.utc) if timeZone == "utc" else datetime.now().astimezone()
            target = now.replace(
                hour=rejoinTime[0],
                minute=rejoinTime[1],
                second=rejoinTime[2],
                microsecond=0,
            )
            return self.getTiming("rejoin_every") < target.timestamp() <= now.timestamp()

        rejoinEvery = self.setdat.get("rejoin_every", 0)
        return bool(rejoinEvery) and self.hasRespawned("rejoin_every", rejoinEvery*60*60)

    def _getRejoinServerLinks(self, usePrivateServer):
        """Return unique private-server links in their configured failover order."""
        if not usePrivateServer:
            return []

        keys = (
            "private_server_link",
            "fallback_private_server_link_1",
            "fallback_private_server_link_2",
            "fallback_private_server_link_3",
        )
        links = []
        seen = set()
        for key in keys:
            link = str(self.setdat.get(key, "") or "").strip()
            normalized = link.casefold()
            if link and normalized not in seen:
                links.append((key, link))
                seen.add(normalized)
        return links

    def _privateServerDeeplink(self, placeId, privateServerLink):
        """Convert Roblox private and share links into a Roblox deeplink."""
        from urllib.parse import parse_qs, urlparse

        parsed = urlparse(privateServerLink)
        query = {key.lower(): values for key, values in parse_qs(parsed.query).items()}
        code = None
        is_share_link = "share" in parsed.path.lower()
        for key in ("code", "privateserverlinkcode", "privateserverlink", "linkcode"):
            if query.get(key):
                code = query[key][0]
                is_share_link = is_share_link or key == "code"
                break
        if not code and "=" in privateServerLink:
            code = privateServerLink.rsplit("=", 1)[-1].split("&", 1)[0]
        if not code:
            return None
        if is_share_link:
            link_type = query.get("type", ["Server"])[0]
            return f"roblox://navigation/share_links?code={code}&type={link_type}"
        return f"roblox://placeID={placeId}&linkCode={code}"

    @staticmethod
    def _joinErrorFromText(rawText):
        """Classify OCR text from a Roblox join-error dialog."""
        text = " ".join(str(rawText or "").lower().split())
        codeMatch = re.search(r"error\s*code\s*[:;]?\s*([0-9s]+)", text)
        code = codeMatch.group(1).replace("s", "5") if codeMatch else ""
        if not code and re.search(r"\bid\s*=\s*17\b", text):
            code = "279"

        errors = {
            "279": ("connection failure", "retry"),
            "524": ("permission denied", "fallback"),
            "267": ("banned from this experience", "abort"),
            "256": ("server data failure or active ban", "retry"),
            "429": ("too many requests", "cooldown"),
        }
        if code in errors:
            reason, action = errors[code]
            return {"code": code, "reason": reason, "action": action}
        if "permission to join" in text or "do not have permission" in text:
            return {"code": "524", "reason": "permission denied", "action": "fallback"}
        if "join error" in text:
            return {"code": code, "reason": "join error", "action": "retry"}
        return None

    def _detectJoinError(self):
        """OCR the central Roblox dialog area for invalid-server errors."""
        width = max(1, int(self.robloxWindow.mw * 0.7))
        height = max(1, int(self.robloxWindow.mh * 0.55))
        x = int(self.robloxWindow.mx + (self.robloxWindow.mw - width) / 2)
        y = int(self.robloxWindow.my + (self.robloxWindow.mh - height) / 2)
        dialog = mssScreenshot(x, y, width, height)
        text = " ".join(result[1][0] for result in ocr.ocrRead(dialog))
        return self._joinErrorFromText(text)

    def rejoin(self, rejoinMsg = "Rejoining", placeId = MAIN_GAME_PLACE_ID, claimHive = True, usePrivateServer = True):
        if self.skipServer is not None:
            self.skipServer.value = 0
        self.canDetectNight = False
        self.location = "spawn"
        self.cannonFromHive = False
        placeId = str(placeId or MAIN_GAME_PLACE_ID)
        privateServerLinks = self._getRejoinServerLinks(usePrivateServer)
        self.logger.webhook("",rejoinMsg, "dark brown")
        self.set_task_status("rejoining", activity="rejoining")
        mouse.mouseUp()
        keyboard.releaseMovement()
        if appManager.isAppOpen("roblox"):
            self.logger.webhook("", "Closing Roblox before rejoining", "dark brown")
            appManager.closeApp("Roblox")
            time.sleep(3)

        # Retry each configured private server in failover order, then use a
        # public server. Skipping one link invalidates only that link, allowing
        # the next configured backup to begin immediately.
        attempts = [server for server in privateServerLinks for _ in range(5)]
        attempts.extend([("public", "")] * (5 if privateServerLinks else 10))
        firstPublicAttempt = len(privateServerLinks) * 5
        invalidServerLinks = set()
        launchedAttempts = 0
        for i, (serverKey, psLink) in enumerate(attempts):
            joinPS = bool(psLink)
            if joinPS and psLink in invalidServerLinks:
                continue
            if self.skipServer is not None:
                # -1 advertises that /skipserver can currently be used; 1 is
                # the one-shot request written by the Discord bot process.
                self.skipServer.value = -1 if joinPS else 0
            launchedAttempts += 1
            if serverKey != "public":
                serverName = "primary private server" if serverKey == "private_server_link" else serverKey.replace("_", " ")
                self.logger.webhook("", f"Rejoin attempt {launchedAttempts}/{len(attempts)}: {serverName}", "dark brown")
            elif privateServerLinks and i == firstPublicAttempt:
                self.logger.webhook("", "Private-server reconnects failed; falling back to a public server", "red", "screen", ping_category="ping_disconnects")
            
            # A Roblox deeplink can teleport an already-running client and
            # launches the client itself when Roblox is not open. Keeping
            # the process alive avoids a full restart on every rejoin.
            deeplink = f"roblox://placeID={placeId}"
            if joinPS:
                deeplink = self._privateServerDeeplink(placeId, psLink)
                if not deeplink:
                    if self.skipServer is not None:
                        self.skipServer.value = 0
                    invalidServerLinks.add(psLink)
                    self.logger.webhook("", f"Invalid {serverKey.replace('_', ' ')}; trying the next server.", "red", "screen", ping_category="ping_critical_errors")
                    continue
            # If the client is already in Bee Swarm, the sprinkler UI can still
            # be visible while the deeplink teleport finishes. Accepting that
            # immediately starts the spawn→hive walk too early (inputs are
            # ignored), so hive claiming falls through to pad alignment as if
            # it were already on slot 1.
            clientAlreadyOpen = appManager.isAppOpen("roblox")
            appManager.openDeeplink(deeplink)
            # The sprinkler prompt is Fuzzy's established indicator that the
            # joined Bee Swarm session is ready for macro inputs.
            sprinklerImg = self.adjustImage("./images/menu", "sprinkler")
            loadStartTime = time.time()
            # A deeplink is asynchronous, so ignore the old join-error dialog
            # briefly while Roblox starts processing this new request.
            joinErrorScanAfter = loadStartTime + 5
            signUpImage = self.adjustImage("./images/menu", "signup")
            disconnectImage = self.adjustImage("./images/menu", "disconnect")
            # prepare rejoin color-based detection
            try:
                sample_colors = get_sample_colors()
            except Exception:
                sample_colors = [(250, 250, 250), (20, 20, 20)]
            percent_threshold = REJOIN_COLOR_PERCENT
            sustain_seconds = int(self.setdat.get("rejoin_color_duration", 60))
            color_tolerance = int(self.setdat.get("rejoin_color_tolerance", 40))
            sustained_start = 0
            rejoinSuccess = True
            robloxOpenTime = 0
            gameLoaded = False
            lastJoinErrorScan = 0
            # Cold starts have no prior sprinkler. In-game deeplink retries must
            # see it disappear (loading) before the post-rejoin appearance counts.
            sawSprinklerGap = not clientAlreadyOpen
            softRejoinReadyAt = loadStartTime + (2 if clientAlreadyOpen else 0)
            while time.time() - loadStartTime < 36:
                if joinPS and self.skipServer is not None and self.skipServer.value == 1:
                    self.skipServer.value = 0
                    invalidServerLinks.add(psLink)
                    self.logger.webhook("", "Private-server join skipped by Discord command; trying the next configured server", "orange")
                    rejoinSuccess = False
                    break
                # Roblox can recreate its window during launch, so refresh bounds
                # before every round of visual checks.
                if appManager.isAppOpen("roblox"):
                    if not robloxOpenTime:
                        robloxOpenTime = time.time()
                    try:
                        self.setRobloxWindowInfo(setYOffset=False)
                    except Exception:
                        pass
                else:
                    robloxOpenTime = 0
                if (
                    robloxOpenTime
                    and time.time() >= joinErrorScanAfter
                    and time.time() - lastJoinErrorScan >= 2
                ):
                    lastJoinErrorScan = time.time()
                    try:
                        joinError = self._detectJoinError()
                    except Exception:
                        joinError = None
                    if joinError:
                        code = joinError["code"] or "unknown"
                        action = joinError["action"]
                        if action == "fallback" and joinPS:
                            invalidServerLinks.add(psLink)
                            nextStep = "trying the next configured server"
                        elif action == "cooldown":
                            nextStep = "waiting 30 seconds before retrying"
                        elif action == "abort":
                            nextStep = "stopping rejoin attempts"
                        else:
                            nextStep = "retrying the connection"
                        self.logger.webhook(
                            f"Join error {code}",
                            f"Detected {joinError['reason']}; {nextStep}.",
                            "red",
                            "screen",
                            ping_category="ping_disconnects",
                        )
                        mouse.mouseUp()
                        keyboard.releaseMovement()
                        if action == "abort":
                            if self.skipServer is not None:
                                self.skipServer.value = 0
                            self.clear_task_status()
                            return False
                        if action == "cooldown":
                            time.sleep(30)
                        rejoinSuccess = False
                        break
                sprinklerVisible = bool(locateImageOnScreen(
                    sprinklerImg,
                    self.robloxWindow.mx,
                    self.robloxWindow.my + (self.robloxWindow.mh * 3 / 4),
                    self.robloxWindow.mw,
                    self.robloxWindow.mh / 4,
                    0.75,
                ))
                if clientAlreadyOpen and not sprinklerVisible:
                    sawSprinklerGap = True
                if sprinklerVisible and (
                    sawSprinklerGap
                    # Soft rejoins sometimes keep the hotbar visible; once the
                    # teleport has had time to finish, walk from spawn again.
                    or time.time() >= softRejoinReadyAt
                ):
                    gameLoaded = True
                    break
                # Check if the user is stuck on the sign-up screen. Rejoining
                # always uses the Roblox app deeplink, so prompt them to sign in.
                if robloxOpenTime and locateImageOnScreen(signUpImage, self.robloxWindow.mx+(self.robloxWindow.mw/4), self.robloxWindow.my+(self.robloxWindow.mh/3), self.robloxWindow.mw/2, self.robloxWindow.mh*2/3, 0.7):
                    self.logger.webhook("", "Not logged into the Roblox app. Please sign in to continue rejoining via deeplink.", "red", "screen", ping_category="ping_disconnects")
                    rejoinSuccess = False
                    break
                if robloxOpenTime and time.time() - robloxOpenTime > 5:
                    robloxScreen = mssScreenshot(self.robloxWindow.mx, self.robloxWindow.my, self.robloxWindow.mw/2, self.robloxWindow.mh/2.5)
                    robloxScreenText = '\n'.join([x[1][0].lower() for x in ocr.ocrRead(robloxScreen)])
                    if "connect" in robloxScreenText:
                        print(robloxScreenText)
                        self.logger.webhook("","Roblox Home Page is open","brown","screen")
                        rejoinSuccess = False
                        break

                if locateImageOnScreen(disconnectImage, self.robloxWindow.mx, self.robloxWindow.my, self.robloxWindow.mw, self.robloxWindow.mh, 0.75):
                    self.logger.webhook("", "Roblox disconnected while loading; retrying rejoin", "dark brown", "screen")
                    rejoinSuccess = False
                    break

                # Check for sustained dominant color (light/dark) that indicates a stuck screen.
                try:
                    if appManager.isAppFocused("Roblox"):
                        matched = False
                        for col in sample_colors:
                            pct = percent_pixels_similar_to_color(self.robloxWindow.mx, self.robloxWindow.my, self.robloxWindow.mw, self.robloxWindow.mh, col, tolerance=color_tolerance)
                            if pct >= percent_threshold:
                                matched = True
                                break
                        if matched:
                            if sustained_start == 0:
                                sustained_start = time.time()
                            elif time.time() - sustained_start >= sustain_seconds:
                                self.logger.webhook("","Detected sustained screen color — retrying rejoin","dark brown","screen")
                                rejoinSuccess = False
                                break
                        else:
                            sustained_start = 0
                    else:
                        sustained_start = 0
                except Exception:
                    sustained_start = 0
                time.sleep(1)

            if self.skipServer is not None:
                self.skipServer.value = 0

            if not gameLoaded and rejoinSuccess:
                self.logger.webhook(
                    "",
                    f"Game load was not confirmed within 36 seconds; trying the next rejoin target ({launchedAttempts}/{len(attempts)}).",
                    "red",
                    "screen",
                    ping_category="ping_disconnects",
                )
                rejoinSuccess = False
            if not rejoinSuccess:
                continue
            appManager.openApp("Roblox")
            # Match the normal-join path: detect the content offset after the
            # client has loaded, then only toggle fullscreen when that offset
            # shows Roblox is not already fullscreen.
            self.setRobloxWindowInfo(setYOffset=True)

            self.startDetect()
            if not claimHive:
                mouse.click()
                self.canDetectNight = True
                self.clear_task_status()
                return True
            # Every successful join lands at spawn. Always walk the hive route
            # from there — do not treat the player as already on a hive pad.
            self.location = "spawn"
            mouse.click()
            time.sleep(0.35)
            self.setRobloxWindowInfo()
            preferredHiveSlot = self.setdat.get("preferred_hive_slot", 1)
            try:
                preferredHiveSlot = max(1, min(6, int(preferredHiveSlot)))
            except (TypeError, ValueError):
                preferredHiveSlot = 1

            excludedHiveSlots = set()
            if joinPS:
                excludedHiveSlotsRaw = self.setdat.get("hive_exclude_slot", [])
                if not isinstance(excludedHiveSlotsRaw, (list, tuple, set)):
                    excludedHiveSlotsRaw = [] if excludedHiveSlotsRaw in (None, "", 0, "0") else [excludedHiveSlotsRaw]
                for slot in excludedHiveSlotsRaw:
                    try:
                        slot = int(slot)
                    except (TypeError, ValueError):
                        continue
                    if 1 <= slot <= 6:
                        excludedHiveSlots.add(slot)

                # The preferred slot always takes priority over private-server
                # exclusions.
                excludedHiveSlots.discard(preferredHiveSlot)

            acquisition = self.hiveAcquisition.acquire(preferredHiveSlot, excludedHiveSlots)
            newHiveNumber = acquisition.slot

            if not acquisition.claimed:
                if acquisition.reason == "stopped":
                    self.clear_task_status()
                    return False
                details = acquisition.reason
                if acquisition.detection_error:
                    details += f"; detection: {acquisition.detection_error}"
                self.logger.webhook("", f"Failed to claim hive ({details}); retrying rejoin", "dark brown", "screen")
                continue

            self.logger.webhook("", f"Claimed hive {newHiveNumber}", "bright green", "screen", ping_category="ping_critical_errors")
            self.setdat["hive_number"] = newHiveNumber
            settingsManager.saveGeneralSetting("hive_number", newHiveNumber)
            for _ in range(8):
                self.keyboard.press("o")
            self.moveMouseToDefault()
            time.sleep(1)
            self.convert(bypass=True)
            self.cannonFromHive = True
            self.canDetectNight = True
            self.clear_task_status()
            return True
        self.clear_task_status()
        return False
