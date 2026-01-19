"""
PyQt6-based GUI for Fuzzy Macro - Modular Architecture
Compatibility wrapper that imports from the new modular gui_pyqt6 package
"""

import sys
import os
import multiprocessing

# Import the new modular GUI system
from src.gui_pyqt6.unified_gui import (
    launch, FuzzyMacroGUI, setRunState, getRunState, log, toggleStartStop,
    updateGUI, openLink, start, stop, pause, resume, getPatterns,
    clearManualPlanters, getManualPlanterData, getAutoPlanterData, clearAutoPlanters,
    clearBlender, clearAFB, resetFieldToDefault, exportFieldSettings,
    importFieldSettings, getMacroVersion, update,
    loadFields, saveField, loadSettings, loadAllSettings, saveProfileSetting,
    saveGeneralSetting, saveDictProfileSettings, initializeFieldSync,
    listProfiles, getCurrentProfile, switchProfile, createProfile, deleteProfile,
    renameProfile, duplicateProfile, exportProfile, importProfile, importProfileContent
)

__all__ = [
    'launch', 'FuzzyMacroGUI', 'setRunState', 'getRunState', 'log', 'toggleStartStop',
    'updateGUI', 'openLink', 'start', 'stop', 'pause', 'resume', 'getPatterns',
    'clearManualPlanters', 'getManualPlanterData', 'getAutoPlanterData', 'clearAutoPlanters',
    'clearBlender', 'clearAFB', 'resetFieldToDefault', 'exportFieldSettings',
    'importFieldSettings', 'getMacroVersion', 'update',
    'loadFields', 'saveField', 'loadSettings', 'loadAllSettings', 'saveProfileSetting',
    'saveGeneralSetting', 'saveDictProfileSettings', 'initializeFieldSync',
    'listProfiles', 'getCurrentProfile', 'switchProfile', 'createProfile', 'deleteProfile',
    'renameProfile', 'duplicateProfile', 'exportProfile', 'importProfile', 'importProfileContent'
]
