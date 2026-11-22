import cv2
import numpy as np
import modules.controls.mouse as mouse
import modules.screen.ocr as ocr
from modules.controls.sleep import is_stopped, pause_aware_time as time, sleep
from modules.misc.badgeData import get_badge
from modules.misc.imageManipulation import average_hash
from PIL import Image
from modules.screen.screenshot import mssScreenshotNP, mssScreenshotPillowRGBA

BADGE_TIERS = ("grandmaster", "hotshot", "master", "cadet", "ace")


class BadgeMixin:
    """The badge menu is the 4th top icon (inventory, quests, stickers, badges)."""

    def toggleBadge(self):
        mouse.moveTo(self.robloxWindow.mx+180, self.robloxWindow.my+113)
        time.sleep(0.1)
        mouse.moveBy(0, 3)
        time.sleep(0.1)
        mouse.click()
        # Shares the quest menu's open flag: closeQuestMenu closes whichever panel is up.
        self.questMenuOpen = not self.questMenuOpen
        self.questMenuStep = None
        self.questGiverSteps = {}
        time.sleep(0.3)
        mouse.moveTo(self.robloxWindow.mx+312, self.robloxWindow.my+200)
        mouse.click()

    def captureBadgeWatchScreen(self):
        """Capture the visible badge list without scrolling or toggling its UI."""
        return mssScreenshotPillowRGBA(
            self.robloxWindow.mx,
            self.robloxWindow.my + 150,
            300,
            max(1, self.robloxWindow.mh - 150),
        )

    def _badgeStripHash(self):
        strip = mssScreenshotNP(self.robloxWindow.mx, self.robloxWindow.my + 150, 300, min(100, self.robloxWindow.mh - 150))
        return average_hash(Image.fromarray(cv2.cvtColor(strip, cv2.COLOR_BGRA2GRAY)))

    def _scrollBadgeMenu(self, direction, maxSteps=200, delay=0.06):
        """Scroll until the list stops moving. Yields after every notch."""
        prevHash = None
        for _ in range(maxSteps):
            if is_stopped():
                return
            if direction == "top":
                mouse.scroll(100)
            else:
                mouse.scroll(-1, True)
            time.sleep(delay)
            currentHash = self._badgeStripHash()
            if prevHash is not None and prevHash == currentHash:
                return
            prevHash = currentHash
            yield True

    def _parseBadgeStatus(self, text):
        """Return (status, tier) from the OCR text under a badge title."""
        lowered = self.convertCyrillic((text or "").lower())
        tier = next((name for name in BADGE_TIERS if name in lowered), None)
        # A Complete! bar is claimable until clicked. Grandmaster stays Complete! after the claim.
        if "complete" in lowered:
            return "claimable", tier
        return "incomplete", tier

    def findBadge(self, badgeName, badgeScreens=None, keepBadgeMenuOpen=False, logDetection=True):
        """
        Find a badge in the badge menu.
        Returns {status: incomplete|claimable|not_found, tier, click_x, click_y, display_name}.
        badgeScreens reuses captured screens instead of opening and scrolling the menu.
        """
        entry = get_badge(badgeName)
        displayName = entry["display_name"] if entry else str(badgeName).replace("_", " ").title()
        searchName = displayName.lower()
        multi = self.robloxWindow.multi

        def matchTitle(screen):
            best = None
            for bbox, (text, _conf) in ocr.ocrRead(screen):
                line = self.convertCyrillic(text.lower().strip())
                if searchName in line and "badge" in line:
                    yPos = int(min(point[1] for point in bbox))
                    if best is None or yPos < best[1]:
                        best = (line, yPos)
            return best

        def readSection(screen, titleY):
            section = screen.crop((0, titleY, screen.width, min(screen.height, titleY + int(160 * multi))))
            text = " ".join(self.convertCyrillic(t.lower().strip()) for _, (t, _c) in ocr.ocrRead(section))
            status, tier = self._parseBadgeStatus(text)
            # The complete bar is green; click its centre to claim.
            clickX, clickY = 150, titleY + int(90 * multi)
            rgb = np.array(section.convert("RGB")).astype(int)
            green = (rgb[:, :, 1] > 140) & (rgb[:, :, 1] > rgb[:, :, 0] + 30) & (rgb[:, :, 1] > rgb[:, :, 2] + 30)
            if green.sum() > 80:
                rows, cols = np.where(green)
                clickX, clickY = int(cols.mean()), titleY + int(rows.mean())
            return status, tier, clickX, clickY

        def readResult(screen, match):
            status, tier, clickX, clickY = readSection(screen, match[1])
            if logDetection:
                imgPath = "latest-badge.png"
                screen.crop((0, max(0, match[1] - 10), screen.width, min(screen.height, match[1] + int(180 * multi)))).convert("RGB").save(imgPath)
                self.logger.webhook("Badge", f"{displayName}: {status}" + (f" ({tier})" if tier else ""),
                                    "dark brown", imagePath=imgPath, route_category="badges")
            return {"status": status, "tier": tier, "click_x": clickX, "click_y": clickY, "display_name": displayName}

        manageUi = badgeScreens is None
        if manageUi:
            self.toggleInventory("close")
            if is_stopped():
                return None
            self.toggleBadge()
            for _ in self._scrollBadgeMenu("top", delay=0.08):
                pass
            sleep(0.4)

        result = None
        screens = iter(badgeScreens) if badgeScreens is not None else None
        scroller = None
        while result is None and not is_stopped():
            if screens is not None:
                screen = next(screens, None)
            else:
                screen = mssScreenshotPillowRGBA(self.robloxWindow.mx, self.robloxWindow.my + 150, 300,
                                                 max(1, self.robloxWindow.mh - 150))
            if screen is None:
                break
            match = matchTitle(screen)
            # A title at the bottom edge hides its tier and progress bar, so keep scrolling until the whole badge shows.
            cutOff = bool(match) and screens is None and match[1] + int(150 * multi) > screen.height
            if match and not cutOff:
                result = readResult(screen, match)
                break
            if screens is None:
                scroller = scroller or self._scrollBadgeMenu("bottom")
                if next(scroller, None) is None:
                    # End of the list: this is as much of the badge as can be shown.
                    if match:
                        result = readResult(screen, match)
                    break

        if result is None:
            result = {"status": "not_found", "tier": None, "click_x": 150, "click_y": 200, "display_name": displayName}
            if logDetection:
                self.logger.webhook("Badge", f"{displayName}: not found", "orange", "screen", route_category="badges")

        if manageUi and not keepBadgeMenuOpen and not is_stopped():
            self.toggleBadge()
            self.moveMouseToDefault()
        return result

    def claimBadgeReward(self, badgeName, badgeInfo):
        """Click a claimable badge's green bar in the open menu, then return its refreshed state."""
        if badgeInfo.get("status") != "claimable":
            return badgeInfo
        # click_x/click_y are screenshot pixels, which are multi times larger than screen points on Retina.
        multi = self.robloxWindow.multi
        mouse.moveTo(self.robloxWindow.mx + int(badgeInfo["click_x"] / multi), self.robloxWindow.my + 150 + int(badgeInfo["click_y"] / multi))
        time.sleep(0.1)
        mouse.click()
        time.sleep(0.6)
        self.logger.webhook("Badge Claim", f"Claimed {badgeInfo['display_name']} reward", "light green", "screen", route_category="badges")
        return self.findBadge(badgeName, badgeScreens=[self.captureBadgeWatchScreen()], logDetection=False)
