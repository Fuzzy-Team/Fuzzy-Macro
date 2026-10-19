import re
from datetime import datetime
import modules.misc.settingsManager as settingsManager
from modules.controls.sleep import INTERRUPT_STICKER_SPROUT, pause_aware_time as time
from modules.macro.game_data import (
    SPROUT_BASE_TOKEN_PRIORITY,
    SPROUT_FIELD_TOKEN_PRIORITY,
    SPROUT_RARITIES,
    SPROUT_REPLANT_FALLBACK_SECONDS,
    startLocationDimensions,
    STICKER_SPROUT_COLLECTION_WINDOW_SECONDS,
    STICKER_SPROUT_INTERVAL_SECONDS,
    STICKER_SPROUT_SPAWN_MINUTE_OF_DAY,
)


class SproutMixin:
    def isStickerSproutSpawnMessage(self, text):
        if "sticker" not in text or "sprout" not in text:
            return False
        if "spawned" not in text:
            return False
        return "hive hub" in text or "hive hubs" in text

    def isStickerSproutSoonMessage(self, text):
        if "sticker" not in text or "sprout" not in text:
            return False
        if "spawn" not in text:
            return False
        return "about" in text and ("hive hub" in text or "hive hubs" in text)

    def secondsSinceScheduledStickerSprout(self):
        now = datetime.now()
        secondsIntoDay = now.hour * 60 * 60 + now.minute * 60 + now.second
        firstSpawnSecond = STICKER_SPROUT_SPAWN_MINUTE_OF_DAY * 60
        return (secondsIntoDay - firstSpawnSecond) % STICKER_SPROUT_INTERVAL_SECONDS

    def isScheduledStickerSproutWindow(self):
        return self.secondsSinceScheduledStickerSprout() < STICKER_SPROUT_COLLECTION_WINDOW_SECONDS

    def stickerSproutTimingAnchor(self):
        if self.isScheduledStickerSproutWindow():
            return time.time() - self.secondsSinceScheduledStickerSprout()
        if self.stickerSproutDetectedAt:
            return self.stickerSproutDetectedAt
        return time.time()

    def detectStickerSproutAnnouncement(self, text, now):
        if "sticker" not in text or "sprout" not in text:
            return

        if self.isStickerSproutSpawnMessage(text):
            self.stickerSproutDetectedAt = now
            if (
                self.skipTask is not None
                and not self.stickerSproutInterruptRequested
                and self.status.value != "collect_sticker_sprout"
                and self.stickerSproutReady()
            ):
                self.stickerSproutInterruptRequested = True
                self.skipTask.value = INTERRUPT_STICKER_SPROUT
            if now - self.stickerSproutLastAnnounced >= 10 * 60:
                self.stickerSproutLastAnnounced = now
                self.logger.webhook(
                    "Sticker Sprout",
                    "Spawn detected in Hive Hub",
                    "light green",
                    "screen",
                    ping_category="ping_sticker_events",
                    route_category="activities",
                )
        elif self.isStickerSproutSoonMessage(text) and now - self.stickerSproutLastAnnounced >= 10 * 60:
            self.stickerSproutLastAnnounced = now
            self.logger.webhook(
                "Sticker Sprout",
                "Hive Hub spawn soon",
                "light blue",
                "screen",
                ping_category="ping_sticker_events",
                route_category="activities",
            )

    def stickerSproutReady(self):
        if not self.setdat.get("sticker_sprout_watch", False):
            return False
        cooldownReady = self.hasRespawned("sticker_sprout", self.collectCooldowns.get("sticker_sprout", 3*60*60))
        if cooldownReady:
            text = self.readBlueText()
            if self.isStickerSproutSpawnMessage(text):
                self.stickerSproutDetectedAt = time.time()
        recentlyDetected = self.stickerSproutDetectedAt and time.time() - self.stickerSproutDetectedAt < 10 * 60
        return cooldownReady and (recentlyDetected or self.isScheduledStickerSproutWindow())

    def extractSproutRarity(self, text):
        if "sprout" not in text:
            return None
        for rarity in SPROUT_RARITIES:
            if re.search(rf"\b{re.escape(rarity)}\b", text):
                return rarity
        return None

    def extractPlantedSproutRarity(self, text):
        if "sprout" not in text or "planted" not in text:
            return None
        rarityPattern = "|".join(re.escape(rarity) for rarity in SPROUT_RARITIES)
        match = re.search(rf"\bplanted\s+a(?:n)?\s+({rarityPattern})\s+sprout\b", text)
        return match.group(1) if match else None

    def blueSproutMessageInfo(self):
        text = self.readBlueText()
        if "sprout" not in text:
            return None
        rarity = self.extractPlantedSproutRarity(text)
        if rarity is None and "appeared" not in text and "planted" not in text:
            rarity = self.extractSproutRarity(text)
        return {
            "text": text,
            "rarity": rarity,
        }

    def isSproutCompletionMessage(self, text):
        if "sprout" not in text:
            return False
        if "already" in text and "field" in text:
            return False
        if "planted" in text or "appeared" in text:
            return False
        return True

    def sproutReplantFallbackSeconds(self, rarity):
        return SPROUT_REPLANT_FALLBACK_SECONDS.get(rarity or "", 120)

    def blueSproutMessageVisible(self):
        text = self.readBlueText()
        return "sprout" in text

    def buildSproutTokenPriority(self, field):
        configuredPriority = str(self.setdat.get("sprouts_preferred_tokens", "") or "").strip()
        if configuredPriority:
            return configuredPriority
        normalizedField = str(field or "").replace("_", " ").strip().lower()
        priority = []
        for token in SPROUT_FIELD_TOKEN_PRIORITY.get(normalizedField, []):
            if token not in priority:
                priority.append(token)
        for token in SPROUT_BASE_TOKEN_PRIORITY:
            if token not in priority:
                priority.append(token)
        return ",".join(priority)

    def _sproutBeanLimit(self):
        try:
            value = int(self.setdat.get("sprouts_max_beans", 500) or 500)
        except Exception:
            value = 500
        return max(1, min(500, value))

    def _sproutGatherBeanLimit(self):
        try:
            value = int(self.setdat.get("sprouts_max_beans_per_gather", 500) or 500)
        except Exception:
            value = 500
        return max(1, min(500, value))

    def _sproutFinalLootSeconds(self):
        try:
            value = int(self.setdat.get("sprouts_final_loot_seconds", 60) or 0)
        except Exception:
            value = 60
        return max(0, min(999, value))

    def logSproutBeanLimitReached(self, message, color="light blue"):
        now = time.time()
        if now - getattr(self, "lastSproutBeanLimitLog", 0) < 60:
            return
        self.lastSproutBeanLimitLog = now
        self.logger.webhook("Sprouts", message, color, "screen", route_category="activities")

    def canUseSproutBeanSlot(self, slot):
        if not self.setdat.get("sprouts_enable", False):
            return True
        try:
            sproutSlot = int(self.setdat.get("sprouts_magic_bean_slot", 1) or 1)
            currentSlot = int(slot)
        except Exception:
            return True
        if currentSlot != sproutSlot:
            return True
        return self.sproutBeansUsed < self._sproutBeanLimit()

    def markSproutBeanUsed(self):
        self.sproutBeansUsed += 1

    def unmarkSproutBeanUsed(self):
        self.sproutBeansUsed = max(0, self.sproutBeansUsed - 1)

    def collectSprouts(self):
        if not self.setdat.get("sprouts_enable", False):
            return False
        if self.sproutBeansUsed >= self._sproutBeanLimit():
            self.logSproutBeanLimitReached("Sprout bean limit reached", "orange")
            return False

        field = str(self.setdat.get("sprouts_field", "sunflower") or "sunflower").replace("_", " ").strip().lower()
        if field not in startLocationDimensions:
            field = "sunflower"
        reuseCurrentPosition = self.location == field
        try:
            slot = max(1, min(7, int(self.setdat.get("sprouts_magic_bean_slot", 1) or 1)))
        except Exception:
            slot = 1
        sproutAIModel = str(self.setdat.get("sprouts_ai_model", "Standard") or "Standard")
        sproutAIModelKey = sproutAIModel.strip().lower().replace(" ", "_").replace("-", "_")
        sproutModelConfig = {
            "standard": ("Standard", ""),
            "loot_light": ("Light", "loot_detection_small.mlmodelc"),
            "light": ("Light", "loot_detection_small.mlmodelc"),
            "token_light": ("Light", ""),
            "loot_mini": ("Mini", "loot_detection_mini.mlmodelc"),
            "mini": ("Mini", "loot_detection_mini.mlmodelc"),
            "token_mini": ("Mini", ""),
        }
        sproutModelName, sproutModelFile = sproutModelConfig.get(
            sproutAIModelKey,
            ("Standard", ""),
        )
        try:
            sproutPatternWidth = max(1, min(10, int(self.setdat.get("sprouts_pattern_width", 5) or 5)))
        except Exception:
            sproutPatternWidth = 5

        sproutOverride = {
            "shape": "fuzzy_ai_gather",
            "shift_lock": False,
            "field_drift_compensation": True,
            "start_location": "center",
            "distance": 1,
            "width": sproutPatternWidth,
            "turn": "none",
            "turn_times": 0,
            "goo": False,
            "skip_travel": reuseCurrentPosition or self.location == field,
            "infinite_gather": True,
            "plant_sprout": True,
            "sprout_magic_bean_slot": slot,
            "sprout_max_beans_per_gather": self._sproutGatherBeanLimit(),
            "ai_gather_model": sproutModelName,
            "ai_gather_model_file": sproutModelFile,
            "fuzzy_ai_preferred_tokens": self.buildSproutTokenPriority(field),
            "fuzzy_ai_ignored_tokens": str(self.setdat.get("sprouts_ignored_tokens", "") or ""),
        }
        nextSessionBean = self.sproutBeansUsed + 1
        gatherLimit = self._sproutGatherBeanLimit()
        sessionLimit = self._sproutBeanLimit()
        self.logger.webhook(
            "Sprouts",
            f"Travelling to {field.title()} to plant sprout (1/{gatherLimit} gather and {nextSessionBean}/{sessionLimit} session)",
            "light blue",
            route_category="activities",
        )
        self.gather(field, sproutOverride)
        return True

    def collectStickerSprout(self):
        if not self.stickerSproutReady():
            return False
        try:
            gatherMinutes = max(1, min(30, int(self.setdat.get("sticker_sprout_gather_minutes", 8) or 8)))
        except Exception:
            gatherMinutes = 8
        timingAnchor = self.stickerSproutTimingAnchor()
        self.stickerSproutDetectedAt = 0
        self.stickerSproutInterruptRequested = False
        settingsManager.saveSettingFile("sticker_sprout", timingAnchor, settingsManager.getUserDataPath("timings.txt"))
        self.collectCooldowns["sticker_sprout"] = 3 * 60 * 60
        self.logger.webhook(
            "Sticker Sprout",
            f"Travelling to Hive Hub to collect for {gatherMinutes} minutes",
            "light green",
            "screen",
            ping_category="ping_sticker_events",
            route_category="activities",
        )
        self.gather("hive hub", {
            "mins": gatherMinutes,
            "infinite_gather": False,
            "backpack": 100,
            "return": "rejoin",
        })
        return True
