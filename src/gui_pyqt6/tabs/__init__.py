"""
Tabs package for Fuzzy Macro PyQt6 GUI
Contains all tab modules
"""

from .home_tab import HomeTab
from .gather_tab import GatherTab
from .collect_tab import CollectTab
from .config_tab import ConfigTab
from .kill_tab import KillTab
from .planters_tab import PlantersTab
from .boost_tab import BoostTab
from .quests_tab import QuestsTab
from .profiles_tab import ProfilesTab

__all__ = [
    'HomeTab',
    'GatherTab',
    'CollectTab',
    'ConfigTab',
    'KillTab',
    'PlantersTab',
    'BoostTab',
    'QuestsTab',
    'ProfilesTab'
]
