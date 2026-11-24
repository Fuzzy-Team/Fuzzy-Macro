from modules.macro.game_data import (
    allPlanters,
    autoPlanterRankings,
    collectData,
    fieldBoosterData,
    nectarFields,
    nectarNames,
    regularMobTypesInFields,
)


def __getattr__(name):
    # The macro class loads on first use, so the GUI can import light submodules
    # (game_data, planter_bonus_loot) without loading OCR, Vision and pyautogui.
    if name == "macro":
        from modules.macro.core import macro
        return macro
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
