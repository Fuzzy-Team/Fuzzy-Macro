"""Collect cooldown ready times, shared by the Discord /cooldowns command and the stream page."""
from typing import Dict, List, Optional, Tuple

from modules.misc import settingsManager


def get_cooldown_rows(settings: Optional[Dict] = None) -> List[Tuple[str, float]]:
    """(name, ready-at unix time) for each enabled item the macro tracks in timings.txt, soonest first."""
    from modules.macro.game_data import collectData, fieldBoosterData

    if settings is None:
        settings = settingsManager.loadAllSettings()
    timings = settingsManager.readSettingsFile(settingsManager.getUserDataPath("timings.txt"))

    cooldowns = {name: data[2] for name, data in {**collectData, **fieldBoosterData}.items() if data[2]}
    cooldowns["sticker_printer"] = 60 * 60  # same value as Macro._applySettingsState
    cooldowns["sticker_stack"] = int(settingsManager.loadUserText("sticker_stack.txt"))
    cooldowns["sticker_sprout"] = 3 * 60 * 60

    rows = []
    for name, cooldown in cooldowns.items():
        setting_name = "sticker_sprout_watch" if name == "sticker_sprout" else name
        if not settings.get(setting_name):
            continue
        ready_at = timings.get(name, 0) + cooldown
        if name in fieldBoosterData:
            ready_at = max(ready_at, timings.get("last_booster", 0) + settings.get("boost_seperate", 0) * 60)
        rows.append((name, ready_at))
    return sorted(rows, key=lambda row: row[1])
