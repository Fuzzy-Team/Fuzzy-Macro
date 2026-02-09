import ast
import os
import shutil
import json
import zipfile
import tempfile
from datetime import datetime
import re
import pickle
from modules.misc import messageBox

#returns a dictionary containing the settings
profileName = "a"
# Track profile changes for running macro processes
_profile_change_counter = 0

# File to store current profile persistence (defined after getProjectRoot)
CURRENT_PROFILE_FILE = None
LEGACY_CURRENT_PROFILE_FILE = None
LEGACY_USER_DATA_DIR = None
LEGACY_USER_DATA_FILES = [
    "hourly_report_stats.pkl",
    "timings.txt",
    "auto_planters.json",
    "hourly_report_history.txt",
    "hourly_report_bg.txt",
    "screen.txt",
    "hourly_report_main.txt",
    "AFB.txt",
    "hotbar_timings.txt",
    "blender.txt",
    "current_profile.txt",
    "sticker_stack.txt",
    "manualplanters.txt",
]

CORE_SETTINGS_FILE = "core.json"
GENERAL_SETTINGS_FILE = "general.json"
FIELDS_SETTINGS_FILE = "fields.json"

USER_STATE_DIR = "state"
USER_STATE_TIMING = "timing.json"
USER_STATE_PLANTERS = "planters.json"
USER_STATE_REPORTS = "reports.json"
USER_STATE_UI = "ui.json"
USER_STATE_MISC = "misc.json"

MIGRATION_NOTICE_FILE = "migration_notice.json"

LEGACY_PROFILE_SETTINGS_FILE = "settings.txt"
LEGACY_GENERAL_SETTINGS_FILE = "generalsettings.txt"
LEGACY_FIELDS_FILE = "fields.txt"

def loadCurrentProfile():
    """Load the current profile from persistent storage"""
    global profileName
    try:
        migrateCurrentProfileSelection()
        misc_state = loadMiscState()
        saved_profile = misc_state.get("current_profile")
        if saved_profile and os.path.exists(getProfilePath(saved_profile)):
            profileName = saved_profile
            return
        if os.path.exists(CURRENT_PROFILE_FILE):
            with open(CURRENT_PROFILE_FILE, "r") as f:
                saved_profile = f.read().strip()
                if saved_profile and os.path.exists(getProfilePath(saved_profile)):
                    profileName = saved_profile
                    misc_state["current_profile"] = saved_profile
                    saveMiscState(misc_state)
    except Exception as e:
        print(f"Warning: Could not load current profile: {e}")

def saveCurrentProfile():
    """Save the current profile to persistent storage"""
    try:
        misc_state = loadMiscState()
        misc_state["current_profile"] = profileName
        saveMiscState(misc_state)
    except Exception as e:
        print(f"Warning: Could not save current profile: {e}")

# Load the current profile when the module is imported (called at the end of the file)

# Get the project root directory (4 levels up from this file: src/modules/misc/settingsManager.py)
def getProjectRoot():
    """Get the project root directory path"""
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# File to store current profile persistence (legacy)
CURRENT_PROFILE_FILE = os.path.join(getProjectRoot(), "usrdata", "current_profile.txt")
LEGACY_CURRENT_PROFILE_FILE = os.path.join(getProjectRoot(), "src", "data", "user", "current_profile.txt")
LEGACY_USER_DATA_DIR = os.path.join(getProjectRoot(), "src", "data", "user")

# Helper functions for common paths
def getProfilesDir():
    """Get the profiles directory path"""
    return os.path.join(getUserDataDir(), "profiles")

def getProfilePath(profile_name=None):
    """Get the path to a specific profile directory"""
    if profile_name is None:
        profile_name = profileName
    return os.path.join(getProfilesDir(), profile_name)

def getDefaultSettingsPath():
    """Get the path to default settings directory"""
    return os.path.join(getProjectRoot(), "src", "defaultconfig")

def getUserDataDir():
    """Get the user data directory path"""
    return os.path.join(getProjectRoot(), "usrdata")

def getUserDataPath(*parts):
    """Get a path under the user data directory"""
    migrateLegacySettingsIfNeeded()
    ensureDir(getUserDataDir())
    return os.path.join(getUserDataDir(), *parts)

def getUserStatePath(filename):
    """Get a path under the user data state directory"""
    state_dir = getUserDataPath(USER_STATE_DIR)
    ensureDir(state_dir)
    return os.path.join(state_dir, filename)

def loadUserState(filename, default=None):
    """Load a unified user state JSON file"""
    path = getUserStatePath(filename)
    data = readJsonFile(path, default=default if default is not None else {})
    if default is not None:
        merged = mergeDefaults(data, default)
        if merged != data:
            writeJsonFile(path, merged)
        return merged
    return data

def saveUserState(filename, data):
    """Save a unified user state JSON file"""
    path = getUserStatePath(filename)
    writeJsonFile(path, data)

def _defaultTimingState():
    return {
        "timings": {},
        "AFB": {},
    }

def _defaultPlantersState():
    return {
        "manual": "",
        "auto": {
            "planters": [
                {"planter": "", "nectar": "", "field": "", "harvest_time": 0, "nectar_est_percent": 0},
                {"planter": "", "nectar": "", "field": "", "harvest_time": 0, "nectar_est_percent": 0},
                {"planter": "", "nectar": "", "field": "", "harvest_time": 0, "nectar_est_percent": 0},
            ],
            "nectar_last_field": {
                "comforting": "",
                "refreshing": "",
                "satisfying": "",
                "motivating": "",
                "invigorating": "",
            },
        },
    }

def _defaultReportsState():
    return {
        "hourly_report_history": [],
        "hourly_report_stats": {},
        "hourly_report_bg": "",
        "hourly_report_main": "",
    }

def _defaultUiState():
    return {
        "screen": {},
        "hotbar_timings": [0] * 8,
    }

def _defaultMiscState():
    return {
        "blender": {"item": 1, "collectTime": 0},
        "sticker_stack": 0,
        "current_profile": "a",
    }

def loadTimingState():
    return loadUserState(USER_STATE_TIMING, default=_defaultTimingState())

def saveTimingState(data):
    saveUserState(USER_STATE_TIMING, data)

def loadPlantersState():
    return loadUserState(USER_STATE_PLANTERS, default=_defaultPlantersState())

def savePlantersState(data):
    saveUserState(USER_STATE_PLANTERS, data)

def loadReportsState():
    return loadUserState(USER_STATE_REPORTS, default=_defaultReportsState())

def saveReportsState(data):
    saveUserState(USER_STATE_REPORTS, data)

def loadUiState():
    return loadUserState(USER_STATE_UI, default=_defaultUiState())

def saveUiState(data):
    saveUserState(USER_STATE_UI, data)

def loadMiscState():
    return loadUserState(USER_STATE_MISC, default=_defaultMiscState())

def saveMiscState(data):
    saveUserState(USER_STATE_MISC, data)

def loadTimings():
    state = loadTimingState()
    return state.get("timings", {})

def saveTimings(data):
    state = loadTimingState()
    state["timings"] = data
    saveTimingState(state)

def loadAFBTimings():
    state = loadTimingState()
    return state.get("AFB", {})

def saveAFBTimings(data):
    state = loadTimingState()
    state["AFB"] = data
    saveTimingState(state)

def loadManualPlanters():
    state = loadPlantersState()
    return state.get("manual", "")

def saveManualPlanters(data):
    state = loadPlantersState()
    state["manual"] = data
    savePlantersState(state)

def loadAutoPlanters():
    state = loadPlantersState()
    auto = state.get("auto", _defaultPlantersState()["auto"])
    defaults = _defaultPlantersState()["auto"]
    if "planters" not in auto:
        auto["planters"] = defaults["planters"]
    if "nectar_last_field" not in auto:
        auto["nectar_last_field"] = defaults["nectar_last_field"]
    return auto

def saveAutoPlanters(data):
    state = loadPlantersState()
    state["auto"] = data
    savePlantersState(state)

def loadBlenderData():
    state = loadMiscState()
    blender = state.get("blender", _defaultMiscState()["blender"])
    defaults = _defaultMiscState()["blender"]
    for key, value in defaults.items():
        if key not in blender:
            blender[key] = value
    return blender

def saveBlenderData(data):
    state = loadMiscState()
    state["blender"] = data
    saveMiscState(state)

def loadStickerStackCooldown():
    state = loadMiscState()
    value = state.get("sticker_stack", 0)
    try:
        return int(value)
    except Exception:
        return 0

def saveStickerStackCooldown(value):
    state = loadMiscState()
    state["sticker_stack"] = value
    saveMiscState(state)

def loadHotbarTimings():
    state = loadUiState()
    timings = state.get("hotbar_timings", [0] * 8)
    if isinstance(timings, dict):
        out = [0] * 8
        for k, v in timings.items():
            try:
                idx = int(k)
                if 0 <= idx < len(out):
                    out[idx] = v
            except Exception:
                continue
        timings = out
    if isinstance(timings, list) and len(timings) < 8:
        timings = timings + [0] * (8 - len(timings))
    return timings

def saveHotbarTimings(data):
    state = loadUiState()
    state["hotbar_timings"] = data
    saveUiState(state)

def loadScreenData():
    state = loadUiState()
    return state.get("screen", {})

def saveScreenData(data):
    state = loadUiState()
    state["screen"] = data
    saveUiState(state)

def loadHourlyReportHistory():
    state = loadReportsState()
    return state.get("hourly_report_history", [])

def saveHourlyReportHistory(data):
    state = loadReportsState()
    state["hourly_report_history"] = data
    saveReportsState(state)

def loadHourlyReportStats():
    state = loadReportsState()
    return state.get("hourly_report_stats", {})

def saveHourlyReportStats(data):
    state = loadReportsState()
    state["hourly_report_stats"] = data
    saveReportsState(state)

def loadHourlyReportBackground():
    state = loadReportsState()
    return state.get("hourly_report_bg", "")

def saveHourlyReportBackground(data):
    state = loadReportsState()
    state["hourly_report_bg"] = data
    saveReportsState(state)

def loadHourlyReportMain():
    state = loadReportsState()
    return state.get("hourly_report_main", "")

def saveHourlyReportMain(data):
    state = loadReportsState()
    state["hourly_report_main"] = data
    saveReportsState(state)

def getSettingsDir():
    """Get the settings directory path"""
    return os.path.join(getProjectRoot(), "settings")

def getPatternsDir():
    """Get the patterns directory path"""
    return os.path.join(getProjectRoot(), "settings", "patterns")

def ensureDir(path):
    """Ensure a directory exists"""
    os.makedirs(path, exist_ok=True)

def readJsonFile(path, default=None):
    """Read a JSON file and return data, with optional default on missing/invalid"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        if default is not None:
            return default
        raise
    except json.JSONDecodeError as e:
        print(f"Warning: Invalid JSON in {path}: {e}")
        if default is not None:
            return default
        raise

def mergeDefaults(current, defaults):
    """Merge missing keys from defaults into current recursively"""
    if isinstance(current, dict) and isinstance(defaults, dict):
        merged = dict(current)
        for key, value in defaults.items():
            if key not in merged:
                merged[key] = value
            else:
                merged[key] = mergeDefaults(merged[key], value)
        return merged
    if isinstance(current, list) and isinstance(defaults, list):
        merged = list(current)
        if not merged:
            return list(defaults)
        for idx, default_item in enumerate(defaults):
            if idx >= len(merged):
                merged.append(default_item)
            else:
                merged[idx] = mergeDefaults(merged[idx], default_item)
        return merged
    return current

def writeJsonFile(path, data):
    """Write JSON data to a file with stable formatting"""
    ensureDir(os.path.dirname(path))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.write("\n")

def migrateCurrentProfileSelection():
    """Migrate the current profile selection to usrdata if needed"""
    try:
        misc_state = loadMiscState()
        if misc_state.get("current_profile"):
            return
        if os.path.exists(CURRENT_PROFILE_FILE):
            with open(CURRENT_PROFILE_FILE, "r") as f:
                saved_profile = f.read().strip()
                if saved_profile:
                    misc_state["current_profile"] = saved_profile
                    saveMiscState(misc_state)
                    return
        if os.path.exists(LEGACY_CURRENT_PROFILE_FILE):
            with open(LEGACY_CURRENT_PROFILE_FILE, "r") as f:
                saved_profile = f.read().strip()
                if saved_profile:
                    misc_state["current_profile"] = saved_profile
                    saveMiscState(misc_state)
    except Exception as e:
        print(f"Warning: Could not migrate current profile selection: {e}")

def getProfileFiles(profile_name=None):
    """Get file paths for a profile's unified settings files"""
    profile_path = getProfilePath(profile_name)
    return {
        "core": os.path.join(profile_path, CORE_SETTINGS_FILE),
        "general": os.path.join(profile_path, GENERAL_SETTINGS_FILE),
        "fields": os.path.join(profile_path, FIELDS_SETTINGS_FILE),
    }

def loadDefaultCoreSettings():
    return readJsonFile(os.path.join(getDefaultSettingsPath(), CORE_SETTINGS_FILE), default={})

def loadDefaultGeneralSettings():
    return readJsonFile(os.path.join(getDefaultSettingsPath(), GENERAL_SETTINGS_FILE), default={})

def loadDefaultFieldSettings():
    return readJsonFile(os.path.join(getDefaultSettingsPath(), FIELDS_SETTINGS_FILE), default={})

def getMacroVersion():
    """Get the macro version from version.txt file"""
    try:
        destination = os.getcwd().replace("/src", "")
        version_file = os.path.join(destination, "src", "webapp", "version.txt")
        if os.path.exists(version_file):
            with open(version_file, "r") as f:
                version = f.read().strip()
                return version if version else "1.0"
    except Exception as e:
        print(f"Warning: Could not read version.txt: {e}")
    return "1.0"

def listProfiles():
    """List all available profiles"""
    migrateLegacySettingsIfNeeded()
    profiles_dir = getProfilesDir()
    if os.path.exists(profiles_dir):
        profiles = [d for d in os.listdir(profiles_dir) 
                   if os.path.isdir(os.path.join(profiles_dir, d)) and not d.startswith('.')]
        return sorted(profiles)
    return []

def getCurrentProfile():
    """Get the current profile name"""
    global profileName
    return profileName

def getProfileChangeCounter():
    """Get the profile change counter for detecting profile switches"""
    global _profile_change_counter
    return _profile_change_counter

def switchProfile(name):
    """Switch to a different profile"""
    global profileName
    profiles_dir = getProfilesDir()
    profile_path = os.path.join(profiles_dir, name)

    if not os.path.exists(profile_path) or not os.path.isdir(profile_path):
        return False, f"Profile '{name}' not found"

    # Check if required profile files exist
    profile_files = getProfileFiles(name)

    if not os.path.exists(profile_files["core"]):
        return False, f"Profile '{name}' is missing core.json file"

    if not os.path.exists(profile_files["fields"]):
        return False, f"Profile '{name}' is missing fields.json file"

    if not os.path.exists(profile_files["general"]):
        return False, f"Profile '{name}' is missing general.json file"

    profileName = name
    # Save the profile selection persistently
    saveCurrentProfile()
    # Increment the change counter to notify running processes
    global _profile_change_counter
    _profile_change_counter += 1

    # Sync the new profile's field settings to general settings
    initializeFieldSync()

    return True, f"Switched to profile: {name}"

def createProfile(name):
    """Create a new profile using default settings from src/defaultconfig"""
    global profileName
    profiles_dir = getProfilesDir()

    # Sanitize the profile name
    name = name.strip().replace(' ', '_').lower()
    if not name:
        return False, "Profile name cannot be empty"

    # Check if profile already exists
    new_profile_path = os.path.join(profiles_dir, name)
    if os.path.exists(new_profile_path):
        return False, f"Profile '{name}' already exists"

    # Create the new profile directory
    try:
        os.makedirs(new_profile_path)
        profile_files = getProfileFiles(name)

        writeJsonFile(profile_files["core"], loadDefaultCoreSettings())
        writeJsonFile(profile_files["general"], loadDefaultGeneralSettings())
        writeJsonFile(profile_files["fields"], loadDefaultFieldSettings())

        return True, f"Created profile: {name}"
    except Exception as e:
        # Clean up partial profile if creation failed
        if os.path.exists(new_profile_path):
            shutil.rmtree(new_profile_path)
        return False, f"Failed to create profile: {str(e)}"

def deleteProfile(name):
    """Delete a profile (cannot delete current or last profile)"""
    global profileName
    profiles_dir = getProfilesDir()
    
    # Cannot delete current profile
    if name == profileName:
        return False, "Cannot delete the currently active profile"
    
    # Cannot delete if it's the only profile
    profiles = listProfiles()
    if len(profiles) <= 1:
        return False, "Cannot delete the only remaining profile"
    
    profile_path = os.path.join(profiles_dir, name)
    if not os.path.exists(profile_path):
        return False, f"Profile '{name}' not found"
    
    try:
        shutil.rmtree(profile_path)
        return True, f"Deleted profile: {name}"
    except Exception as e:
        return False, f"Failed to delete profile: {str(e)}"

def renameProfile(old_name, new_name):
    """Rename a profile"""
    global profileName
    profiles_dir = getProfilesDir()
    
    # Sanitize the new name
    new_name = new_name.strip().replace(' ', '_').lower()
    if not new_name:
        return False, "New profile name cannot be empty"
    
    old_path = os.path.join(profiles_dir, old_name)
    new_path = os.path.join(profiles_dir, new_name)
    
    if not os.path.exists(old_path):
        return False, f"Profile '{old_name}' not found"
    
    if os.path.exists(new_path):
        return False, f"Profile '{new_name}' already exists"
    
    try:
        os.rename(old_path, new_path)
        # If we renamed the current profile, update the reference
        if old_name == profileName:
            profileName = new_name
        return True, f"Renamed profile from '{old_name}' to '{new_name}'"
    except Exception as e:
        return False, f"Failed to rename profile: {str(e)}"

def duplicateProfile(source_name, new_name):
    """Duplicate an existing profile with a new name"""
    profiles_dir = getProfilesDir()
    
    # Sanitize the new name
    new_name = new_name.strip().replace(' ', '_').lower()
    if not new_name:
        return False, "New profile name cannot be empty"
    
    source_path = os.path.join(profiles_dir, source_name)
    new_path = os.path.join(profiles_dir, new_name)
    
    if not os.path.exists(source_path):
        return False, f"Source profile '{source_name}' not found"
    
    if os.path.exists(new_path):
        return False, f"Profile '{new_name}' already exists"
    
    try:
        shutil.copytree(source_path, new_path)
        return True, f"Duplicated profile '{source_name}' as '{new_name}'"
    except Exception as e:
        return False, f"Failed to duplicate profile: {str(e)}"

def readSettingsFile(path):
    #get each line
    #read the file, format it to:
    #[[key, value], [key, value]]
    with open(path) as f:
        raw = f.read()

    # If `max_convert_time=` was accidentally concatenated onto the previous line,
    # insert a newline before it so it becomes its own setting line.
    raw = re.sub(r'(?<!\n)max_convert_time=', r'\nmax_convert_time=', raw)

    data = [[x.strip() for x in y.split("=", 1)] for y in raw.split("\n") if y]
    #convert to a dict
    out = {}
    for k,v in data:
        try:
            out[k] = ast.literal_eval(v)
        except:
            #check if integer
            if v.isdigit():
                out[k] = int(v)
            elif v.replace(".","",1).isdigit():
                out[k] = float(v)
            out[k] = v
    return out

def saveDict(path, data):
    out = "\n".join([f"{k}={v}" for k, v in sorted(data.items(), key=lambda item: item[0])])
    # Ensure file ends with a newline to avoid accidental concatenation
    if not out.endswith("\n"):
        out = out + "\n"
    with open(path, "w") as f:
        f.write(out)

#update one property of a setting
def saveSettingFile(setting,value, path):
    #get the dictionary
    data = readSettingsFile(path)
    #update the dictionary
    data[setting] = value
    #write it
    saveDict(path, data)

def removeSettingFile(setting, path):
    #get the dictionary
    data = readSettingsFile(path)
    #remove the setting if it exists
    if setting in data:
        del data[setting]
        #write it back
        saveDict(path, data)

_legacy_migration_done = False

def _getMigrationNoticePath():
    return os.path.join(getUserDataDir(), MIGRATION_NOTICE_FILE)

def _loadMigrationNotice():
    return readJsonFile(_getMigrationNoticePath(), default={"shown": False, "pending_paths": [], "backup_path": ""})

def _saveMigrationNotice(data):
    writeJsonFile(_getMigrationNoticePath(), data)

def _collectLegacyUserDataPaths(root):
    paths = []
    for name in LEGACY_USER_DATA_FILES:
        path = os.path.join(root, name)
        if os.path.exists(path):
            paths.append(path)
    return paths

def _ensureBackupDir():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_root = os.path.join(getUserDataDir(), "legacy_backups", timestamp)
    ensureDir(backup_root)
    return backup_root

def migrateLegacyUserDataToState():
    """Unify legacy per-file usrdata into state JSON files"""
    legacy_root = getUserDataDir()
    legacy_src_root = LEGACY_USER_DATA_DIR

    legacy_paths = _collectLegacyUserDataPaths(legacy_root)
    legacy_src_paths = _collectLegacyUserDataPaths(legacy_src_root) if os.path.exists(legacy_src_root) else []

    if not legacy_paths and not legacy_src_paths:
        return False, []

    timing_state = loadTimingState()
    planters_state = loadPlantersState()
    reports_state = loadReportsState()
    ui_state = loadUiState()
    misc_state = loadMiscState()

    def read_legacy_file(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    # Prefer usrdata root, fallback to legacy src/data/user
    def pick_path(name):
        primary = os.path.join(legacy_root, name)
        fallback = os.path.join(legacy_src_root, name)
        return primary if os.path.exists(primary) else (fallback if os.path.exists(fallback) else None)

    # Timings
    timings_path = pick_path("timings.txt")
    if timings_path:
        timing_state["timings"] = readSettingsFile(timings_path) or {}

    afb_path = pick_path("AFB.txt")
    if afb_path:
        timing_state["AFB"] = readSettingsFile(afb_path) or {}

    # Planters
    manual_path = pick_path("manualplanters.txt")
    if manual_path:
        raw = read_legacy_file(manual_path).strip()
        planters_state["manual"] = ast.literal_eval(raw) if raw else ""

    auto_path = pick_path("auto_planters.json")
    if auto_path:
        try:
            with open(auto_path, "r", encoding="utf-8") as f:
                planters_state["auto"] = json.load(f)
        except Exception:
            pass

    # Reports
    history_path = pick_path("hourly_report_history.txt")
    if history_path:
        raw = read_legacy_file(history_path).strip()
        reports_state["hourly_report_history"] = ast.literal_eval(raw) if raw else []

    stats_path = pick_path("hourly_report_stats.pkl")
    if stats_path:
        try:
            with open(stats_path, "rb") as f:
                reports_state["hourly_report_stats"] = pickle.load(f)
        except Exception:
            reports_state["hourly_report_stats"] = {}

    bg_path = pick_path("hourly_report_bg.txt")
    if bg_path:
        reports_state["hourly_report_bg"] = read_legacy_file(bg_path)

    main_path = pick_path("hourly_report_main.txt")
    if main_path:
        reports_state["hourly_report_main"] = read_legacy_file(main_path)

    # UI
    screen_path = pick_path("screen.txt")
    if screen_path:
        ui_state["screen"] = readSettingsFile(screen_path) or {}

    hotbar_path = pick_path("hotbar_timings.txt")
    if hotbar_path:
        raw = read_legacy_file(hotbar_path).strip()
        ui_state["hotbar_timings"] = ast.literal_eval(raw) if raw else [0] * 8

    # Misc
    blender_path = pick_path("blender.txt")
    if blender_path:
        raw = read_legacy_file(blender_path).strip()
        misc_state["blender"] = ast.literal_eval(raw) if raw else _defaultMiscState()["blender"]

    sticker_path = pick_path("sticker_stack.txt")
    if sticker_path:
        raw = read_legacy_file(sticker_path).strip()
        misc_state["sticker_stack"] = int(raw) if raw.isdigit() else 0

    current_profile_path = pick_path("current_profile.txt")
    if current_profile_path:
        raw = read_legacy_file(current_profile_path).strip()
        if raw:
            misc_state["current_profile"] = raw

    saveTimingState(timing_state)
    savePlantersState(planters_state)
    saveReportsState(reports_state)
    saveUiState(ui_state)
    saveMiscState(misc_state)

    return True, list(set(legacy_paths + legacy_src_paths))

def _move_to_trash(paths):
    trash_dir = os.path.expanduser("~/.Trash")
    ensureDir(trash_dir)
    abs_paths = [os.path.abspath(p) for p in paths if os.path.exists(p)]
    filtered = []
    for p in abs_paths:
        if any(p != other and p.startswith(other + os.sep) for other in abs_paths):
            continue
        filtered.append(p)

    for path in filtered:
        if not os.path.exists(path):
            continue
        base = os.path.basename(path.rstrip(os.sep))
        target = os.path.join(trash_dir, base)
        if os.path.exists(target):
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            target = os.path.join(trash_dir, f"{base}_{stamp}")
        try:
            shutil.move(path, target)
        except Exception as e:
            print(f"Warning: Could not move {path} to Trash: {e}")

def promptLegacyCleanupIfNeeded():
    notice = _loadMigrationNotice()
    if notice.get("shown"):
        return
    pending = notice.get("pending_paths", [])
    if not pending:
        notice["shown"] = True
        _saveMigrationNotice(notice)
        return

    backup_path = notice.get("backup_path", "")
    prompt = (
        "Settings and other content were migrated to a new data system. "
        "A backup was created" + (f" at {backup_path}." if backup_path else ".") +
        "\n\nPlease test and confirm the migration was successful before deleting old files. "
        "Do you want to move the old settings files to Trash now?"
    )

    if messageBox.msgBoxOkCancel(title="Migration Complete", text=prompt):
        _move_to_trash(pending)

    notice["shown"] = True
    _saveMigrationNotice(notice)

def _normalize_core_fields(core_settings, default_core):
    """Ensure fields/fields_enabled arrays are sized consistently"""
    defaultFields = default_core.get("fields", ['pine tree', 'sunflower', 'dandelion', 'pine tree', 'sunflower'])
    defaultFieldsEnabled = default_core.get("fields_enabled", [True, False, False, False, False])
    fields = core_settings.get("fields", [])
    fieldsEnabled = core_settings.get("fields_enabled", [])
    updated = False

    while len(fields) < 5:
        fields.append(defaultFields[len(fields)] if len(fields) < len(defaultFields) else defaultFields[-1])
        updated = True
    while len(fieldsEnabled) < 5:
        fieldsEnabled.append(defaultFieldsEnabled[len(fieldsEnabled)] if len(fieldsEnabled) < len(defaultFieldsEnabled) else False)
        updated = True

    if updated:
        core_settings["fields"] = fields
        core_settings["fields_enabled"] = fieldsEnabled

    return core_settings, updated

def _merge_field_settings(default_fields, legacy_fields):
    merged = {}
    for field, defaults in default_fields.items():
        profile_settings = legacy_fields.get(field, {}) if isinstance(legacy_fields, dict) else {}
        merged[field] = {**defaults, **profile_settings}
    if isinstance(legacy_fields, dict):
        for field, settings in legacy_fields.items():
            if field not in merged:
                merged[field] = settings
    return merged

def _should_keep_legacy_backup(legacy_general_data):
    env = os.getenv("FUZZY_KEEP_LEGACY_SETTINGS_BACKUP", "").strip().lower()
    if env in ("1", "true", "yes"):
        return True
    if isinstance(legacy_general_data, dict):
        return bool(legacy_general_data.get("keep_legacy_settings_backup", False))
    return False

def ensureDefaultProfileExists():
    ensureDir(getProfilesDir())
    if not listProfiles():
        createProfile("a")

def migrateLegacySettingsIfNeeded():
    """Migrate legacy settings files to unified JSON layout"""
    global _legacy_migration_done
    if _legacy_migration_done:
        return
    _legacy_migration_done = True

    legacy_profiles_dir = os.path.join(getProjectRoot(), "settings", "profiles")
    legacy_global_general = os.path.join(getProjectRoot(), "settings", LEGACY_GENERAL_SETTINGS_FILE)
    legacy_profiles = []

    if os.path.exists(legacy_profiles_dir):
        legacy_profiles = [d for d in os.listdir(legacy_profiles_dir)
                           if os.path.isdir(os.path.join(legacy_profiles_dir, d)) and not d.startswith(".")]

    legacy_user_files = _collectLegacyUserDataPaths(getUserDataDir())
    if not legacy_profiles and not os.path.exists(legacy_global_general) and not os.path.exists(LEGACY_USER_DATA_DIR) and not legacy_user_files:
        ensureDefaultProfileExists()
        return

    default_core = loadDefaultCoreSettings()
    default_general = loadDefaultGeneralSettings()
    default_fields = loadDefaultFieldSettings()

    legacy_global_general_data = {}
    if os.path.exists(legacy_global_general):
        try:
            legacy_global_general_data = readSettingsFile(legacy_global_general)
        except Exception:
            legacy_global_general_data = {}

    backup_root = None
    try:
        backup_root = _ensureBackupDir()
    except Exception as e:
        print(f"Warning: Could not create legacy backup directory: {e}")

    for profile_name in legacy_profiles:
        legacy_profile_path = os.path.join(legacy_profiles_dir, profile_name)
        legacy_settings_path = os.path.join(legacy_profile_path, LEGACY_PROFILE_SETTINGS_FILE)
        legacy_general_path = os.path.join(legacy_profile_path, LEGACY_GENERAL_SETTINGS_FILE)
        legacy_fields_path = os.path.join(legacy_profile_path, LEGACY_FIELDS_FILE)

        profile_files = getProfileFiles(profile_name)
        if os.path.exists(profile_files["core"]) and os.path.exists(profile_files["general"]) and os.path.exists(profile_files["fields"]):
            continue

        core_data = {}
        general_data = {}
        fields_data = {}

        if os.path.exists(legacy_settings_path):
            try:
                core_data = readSettingsFile(legacy_settings_path)
            except Exception:
                core_data = {}

        if os.path.exists(legacy_general_path):
            try:
                general_data = readSettingsFile(legacy_general_path)
            except Exception:
                general_data = {}
        elif legacy_global_general_data:
            general_data = dict(legacy_global_general_data)

        if os.path.exists(legacy_fields_path):
            try:
                with open(legacy_fields_path, "r") as f:
                    fields_data = ast.literal_eval(f.read())
            except Exception:
                fields_data = {}

        # Migrate old macro mode flags in general settings
        if "field_only_mode" in general_data or "quest_only_mode" in general_data:
            field_only = general_data.get("field_only_mode", False)
            quest_only = general_data.get("quest_only_mode", False)
            if field_only and quest_only:
                general_data["macro_mode"] = "field"
            elif field_only:
                general_data["macro_mode"] = "field"
            elif quest_only:
                general_data["macro_mode"] = "quest"
            else:
                general_data["macro_mode"] = "normal"
            general_data.pop("field_only_mode", None)
            general_data.pop("quest_only_mode", None)

        merged_core = {**default_core, **core_data}
        merged_core, _ = _normalize_core_fields(merged_core, default_core)
        merged_general = {**default_general, **general_data}
        merged_fields = _merge_field_settings(default_fields, fields_data)

        writeJsonFile(profile_files["core"], merged_core)
        writeJsonFile(profile_files["general"], merged_general)
        writeJsonFile(profile_files["fields"], merged_fields)

    ensureDefaultProfileExists()

    # Backup legacy data
    if backup_root:
        try:
            if legacy_profiles:
                shutil.copytree(legacy_profiles_dir, os.path.join(backup_root, "profiles"), dirs_exist_ok=True)
            if os.path.exists(legacy_global_general):
                shutil.copy2(legacy_global_general, os.path.join(backup_root, LEGACY_GENERAL_SETTINGS_FILE))
            if os.path.exists(LEGACY_USER_DATA_DIR):
                shutil.copytree(LEGACY_USER_DATA_DIR, os.path.join(backup_root, "user"), dirs_exist_ok=True)
            legacy_usrdata_files = _collectLegacyUserDataPaths(getUserDataDir())
            if legacy_usrdata_files:
                usrdata_backup = os.path.join(backup_root, "usrdata")
                ensureDir(usrdata_backup)
                for path in legacy_usrdata_files:
                    shutil.copy2(path, os.path.join(usrdata_backup, os.path.basename(path)))
        except Exception as e:
            print(f"Warning: Could not create legacy backup: {e}")

    # Migrate legacy user data into unified state files
    user_data_migrated, user_data_paths = migrateLegacyUserDataToState()

    # Prepare a cleanup prompt for legacy sources
    pending_paths = []
    if legacy_profiles and os.path.exists(legacy_profiles_dir):
        pending_paths.append(legacy_profiles_dir)
    if os.path.exists(legacy_global_general):
        pending_paths.append(legacy_global_general)
    if os.path.exists(LEGACY_USER_DATA_DIR):
        pending_paths.append(LEGACY_USER_DATA_DIR)
    pending_paths.extend(user_data_paths)

    if pending_paths:
        notice = _loadMigrationNotice()
        if not notice.get("shown", False):
            notice["shown"] = False
            notice["pending_paths"] = sorted(list(set(pending_paths)))
            notice["backup_path"] = backup_root or ""
            _saveMigrationNotice(notice)

def loadFields():
    profile_files = getProfileFiles()
    fields_path = profile_files["fields"]
    default_fields = loadDefaultFieldSettings()

    fields_data = readJsonFile(fields_path, default={})

    updated = False
    merged = {}

    for field, defaults in default_fields.items():
        profile_settings = fields_data.get(field, {})
        merged[field] = {**defaults, **profile_settings}
        if merged[field] != profile_settings:
            updated = True

    # Preserve any custom fields not in defaults
    for field, settings in fields_data.items():
        if field not in merged:
            merged[field] = settings

    if updated or fields_data != merged:
        writeJsonFile(fields_path, merged)

    return merged

def saveField(field, settings):
    fieldsData = loadFields()
    fieldsData[field] = settings
    fields_path = getProfileFiles()["fields"]
    writeJsonFile(fields_path, fieldsData)

def exportFieldSettings(field_name):
    """Export field settings as JSON string with metadata"""
    fields_data = loadFields()
    if field_name in fields_data:
        # Create export data with metadata
        export_data = {
            "metadata": {
                "field_name": field_name,
                "macro_version": getMacroVersion(),
                "export_date": datetime.now().isoformat()
            },
            "settings": fields_data[field_name]
        }
        return json.dumps(export_data, indent=2)
    else:
        raise ValueError(f"Field '{field_name}' not found in current profile")

def importFieldSettings(field_name, json_settings):
    """Import field settings from JSON string with backward compatibility"""
    try:
        data = json.loads(json_settings)
        
        # Handle new format with metadata
        if isinstance(data, dict) and "metadata" in data and "settings" in data:
            settings = data["settings"]
            metadata = data.get("metadata", {})
            exported_field = metadata.get("field_name", "unknown")
            macro_version = metadata.get("macro_version", "unknown")
        # Handle old format (direct settings object)
        else:
            settings = data
            exported_field = "unknown"
            macro_version = "unknown"
        
        # Validate that settings is a dictionary
        if not isinstance(settings, dict):
            raise ValueError("Invalid JSON format: expected object")

        # Check for missing patterns and replace with defaults
        missing_patterns = []
        available_patterns = getAvailablePatterns()

        if "shape" in settings:
            requested_pattern = settings["shape"]
            if requested_pattern not in available_patterns:
                # Replace with first available pattern (default)
                default_pattern = available_patterns[0] if available_patterns else "cornerxe_lol"
                settings["shape"] = default_pattern
                missing_patterns.append(f"'{requested_pattern}' → '{default_pattern}'")

        # Save the imported settings
        saveField(field_name, settings)

        # Return success with information about any pattern replacements and metadata
        result = {
            "success": True,
            "missing_patterns": missing_patterns,
            "imported_from_field": exported_field,
            "macro_version": macro_version
        }
        return result

    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON format: {str(e)}")

def getAvailablePatterns():
    """Get list of available pattern names"""
    patterns_dir = getPatternsDir()
    if os.path.exists(patterns_dir):
        return [f.replace(".py", "") for f in os.listdir(patterns_dir) if f.endswith(".py")]
    return []

def syncFieldSettings(setting, value):
    """Synchronize field settings from profile to general settings"""
    try:
        # Update the general settings file
        generalSettingsPath = getProfileFiles()["general"]
        generalData = readJsonFile(generalSettingsPath, default={})
        generalData[setting] = value
        writeJsonFile(generalSettingsPath, generalData)
    except Exception as e:
        print(f"Warning: Could not sync field settings to general settings: {e}")

def syncFieldSettingsToProfile(setting, value):
    """Synchronize field settings from general to profile settings"""
    try:
        # Update the profile settings file
        profileSettingsPath = getProfileFiles()["core"]
        profileData = readJsonFile(profileSettingsPath, default={})
        profileData[setting] = value
        writeJsonFile(profileSettingsPath, profileData)
    except Exception as e:
        print(f"Warning: Could not sync field settings to profile settings: {e}")

def saveProfileSetting(setting, value):
    settings_path = getProfileFiles()["core"]
    data = readJsonFile(settings_path, default={})
    data[setting] = value
    writeJsonFile(settings_path, data)
    # Synchronize field settings with general settings
    if setting in ["fields", "fields_enabled"]:
        syncFieldSettings(setting, value)

def saveDictProfileSettings(dict):
    settings_path = getProfileFiles()["core"]
    data = readJsonFile(settings_path, default={})
    data.update(dict)
    writeJsonFile(settings_path, data)

#increment a setting, and return the dictionary for the setting
def incrementProfileSetting(setting, incrValue):
    #get the dictionary
    settings_path = getProfileFiles()["core"]
    data = readJsonFile(settings_path, default={})
    #update the dictionary
    data[setting] += incrValue
    #write it
    writeJsonFile(settings_path, data)
    return data

def saveGeneralSetting(setting, value):
    generalsettings_path = getProfileFiles()["general"]
    data = readJsonFile(generalsettings_path, default={})
    data[setting] = value
    writeJsonFile(generalsettings_path, data)
    # Synchronize field settings with profile settings
    if setting in ["fields", "fields_enabled"]:
        syncFieldSettingsToProfile(setting, value)

def removeGeneralSetting(setting):
    generalsettings_path = getProfileFiles()["general"]
    data = readJsonFile(generalsettings_path, default={})
    if setting in data:
        del data[setting]
        writeJsonFile(generalsettings_path, data)

def loadSettings():
    migrateLegacySettingsIfNeeded()
    settings_path = getProfileFiles()["core"]
    default_settings = loadDefaultCoreSettings()
    try:
        settings = readJsonFile(settings_path, default={})
    except FileNotFoundError:
        print(f"Warning: Profile '{profileName}' core settings file not found, using defaults")
        settings = {}

    merged = {**default_settings, **settings}

    # Ensure fields and fields_enabled arrays have 5 elements
    defaultFields = default_settings.get("fields", ['pine tree', 'sunflower', 'dandelion', 'pine tree', 'sunflower'])
    defaultFieldsEnabled = default_settings.get("fields_enabled", [True, False, False, False, False])

    fields = merged.get("fields", [])
    fieldsEnabled = merged.get("fields_enabled", [])

    updated = False
    while len(fields) < 5:
        fields.append(defaultFields[len(fields)] if len(fields) < len(defaultFields) else defaultFields[-1])
        updated = True
    while len(fieldsEnabled) < 5:
        fieldsEnabled.append(defaultFieldsEnabled[len(fieldsEnabled)] if len(fieldsEnabled) < len(defaultFieldsEnabled) else False)
        updated = True

    if updated:
        merged["fields"] = fields
        merged["fields_enabled"] = fieldsEnabled

    if merged != settings or updated:
        writeJsonFile(settings_path, merged)

    return merged

#return a dict containing all settings except field (general, profile, planters)
def loadAllSettings():
    migrateLegacySettingsIfNeeded()

    generalsettings_path = getProfileFiles()["general"]
    try:
        generalSettings = readJsonFile(generalsettings_path, default={})
    except FileNotFoundError:
        print(f"Warning: Profile '{profileName}' general settings file not found, using defaults")
        generalSettings = {}

    default_general = loadDefaultGeneralSettings()
    generalSettings = {**default_general, **generalSettings}

    # Migrate old boolean flags to new macro_mode setting
    migrated = False
    field_only = generalSettings.get("field_only_mode", False)
    quest_only = generalSettings.get("quest_only_mode", False)

    # Check if old settings exist (regardless of their value)
    if "field_only_mode" in generalSettings or "quest_only_mode" in generalSettings:
        if field_only and quest_only:
            # If both are somehow true, prioritize field mode
            generalSettings["macro_mode"] = "field"
        elif field_only:
            generalSettings["macro_mode"] = "field"
        elif quest_only:
            generalSettings["macro_mode"] = "quest"
        else:
            generalSettings["macro_mode"] = "normal"

        # Remove old settings
        if "field_only_mode" in generalSettings:
            del generalSettings["field_only_mode"]
            migrated = True
        if "quest_only_mode" in generalSettings:
            del generalSettings["quest_only_mode"]
            migrated = True

        # Save the migrated settings back to file
        if migrated:
            writeJsonFile(generalsettings_path, generalSettings)
            print("Migrated old field_only_mode/quest_only_mode settings to new macro_mode setting")

    if generalSettings != readJsonFile(generalsettings_path, default=generalSettings):
        writeJsonFile(generalsettings_path, generalSettings)

    return {**loadSettings(), **generalSettings}

def ensureCurrentProfileDefaults():
    """Ensure current profile files exist and include defaults"""
    loadAllSettings()
    loadFields()

def initializeFieldSync():
    """Initialize field synchronization between profile and general settings"""
    try:
        settings_path = getProfileFiles()["core"]
        generalsettings_path = getProfileFiles()["general"]
        try:
            profileData = readJsonFile(settings_path, default={})
        except FileNotFoundError:
            print(f"Warning: Profile '{profileName}' settings file not found during sync, skipping")
            return

        generalData = readJsonFile(generalsettings_path, default={})

        # Check if field settings exist in both files
        profileFields = profileData.get("fields", [])
        generalFields = generalData.get("fields", [])

        # If general settings has different fields, sync from profile to general
        if profileFields != generalFields and profileFields:
            generalData["fields"] = profileFields
            writeJsonFile(generalsettings_path, generalData)

        # Sync fields_enabled as well
        profileFieldsEnabled = profileData.get("fields_enabled", [])
        generalFieldsEnabled = generalData.get("fields_enabled", [])

        if profileFieldsEnabled != generalFieldsEnabled and profileFieldsEnabled:
            generalData["fields_enabled"] = profileFieldsEnabled
            writeJsonFile(generalsettings_path, generalData)
            
    except Exception as e:
        print(f"Warning: Could not initialize field synchronization: {e}")

def exportProfile(profile_name):
    """Export a profile to JSON content for browser download"""
    profiles_dir = getProfilesDir()
    profile_path = os.path.join(profiles_dir, profile_name)

    if not os.path.exists(profile_path):
        return False, f"Profile '{profile_name}' not found"

    # Read profile data
    try:
        profile_files = getProfileFiles(profile_name)

        if not os.path.exists(profile_files["core"]) or not os.path.exists(profile_files["fields"]) or not os.path.exists(profile_files["general"]):
            return False, f"Profile '{profile_name}' is missing required files"

        settings_data = readJsonFile(profile_files["core"], default={})
        fields_data = loadFields() if profile_name == getCurrentProfile() else readJsonFile(profile_files["fields"], default={})
        generalsettings_data = readJsonFile(profile_files["general"], default={})

        # Create export data structure
        export_data = {
            "profile_name": profile_name,
            "export_date": datetime.now().isoformat(),
            "version": "2.0",
            "core": settings_data,
            "fields": fields_data,
            "general": generalsettings_data
        }

        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"profile_{profile_name}_{timestamp}.json"

        # Return JSON content and filename
        json_content = json.dumps(export_data, indent=2, ensure_ascii=False)
        return True, json_content, filename

    except Exception as e:
        return False, f"Failed to export profile: {str(e)}"

def importProfile(import_path, new_profile_name=None):
    """Import a profile from a JSON file"""
    if not os.path.exists(import_path):
        return False, f"Import file '{import_path}' not found"

    try:
        # Read and validate import data
        with open(import_path, 'r', encoding='utf-8') as f:
            import_data = json.load(f)

        return _importProfileData(import_data, new_profile_name)
    except Exception as e:
        return False, f"Failed to import profile: {str(e)}"

def importProfileContent(json_content, new_profile_name=None):
    """Import a profile from JSON content string"""
    try:
        import_data = json.loads(json_content)
        return _importProfileData(import_data, new_profile_name)
    except json.JSONDecodeError:
        return False, "Invalid JSON content"
    except Exception as e:
        return False, f"Failed to import profile: {str(e)}"

def _importProfileData(import_data, new_profile_name=None):
    """Internal function to import profile data"""
    try:
        # Validate structure
        if all(k in import_data for k in ["profile_name", "core", "fields", "general"]):
            core_data = import_data["core"]
            fields_data = import_data["fields"]
            general_data = import_data["general"]
        elif all(k in import_data for k in ["profile_name", "settings", "fields", "generalsettings"]):
            core_data = import_data["settings"]
            fields_data = import_data["fields"]
            general_data = import_data["generalsettings"]
        else:
            return False, "Invalid import file: missing required keys"

        # Determine new profile name
        if new_profile_name is None:
            original_name = import_data["profile_name"]
            new_profile_name = original_name
            counter = 1
            while os.path.exists(os.path.join(getProfilesDir(), new_profile_name)):
                new_profile_name = f"{original_name}_imported_{counter}"
                counter += 1

        # Sanitize profile name
        new_profile_name = new_profile_name.strip().replace(' ', '_').lower()
        if not new_profile_name:
            return False, "Profile name cannot be empty"

        # Check if profile already exists
        new_profile_path = os.path.join(getProfilesDir(), new_profile_name)
        if os.path.exists(new_profile_path):
            return False, f"Profile '{new_profile_name}' already exists"

        # Create profile directory
        os.makedirs(new_profile_path)

        profile_files = getProfileFiles(new_profile_name)

        # Write settings file
        writeJsonFile(profile_files["core"], core_data)

        # Write fields file
        writeJsonFile(profile_files["fields"], fields_data)

        # Write general settings file
        writeJsonFile(profile_files["general"], general_data)

        return True, f"Profile imported successfully as '{new_profile_name}'"

    except Exception as e:
        return False, f"Failed to import profile: {str(e)}"

# Load the current profile when the module is imported
loadCurrentProfile()

#clear a file
def clearFile(filePath):
    open(filePath, 'w').close()