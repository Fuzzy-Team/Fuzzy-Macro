import ast
import os
import shutil
import json
import tempfile
from datetime import datetime
import re

try:
    from .macro_profile import MacroProfileError, MacroProfileStore, MacroProfileValidationError
except ImportError:
    from macro_profile import MacroProfileError, MacroProfileStore, MacroProfileValidationError

try:
    from .settings_defaults import (
        DEFAULT_AFB,
        DEFAULT_AI_PATTERN_PRESETS,
        DEFAULT_AUTO_PLANTERS,
        DEFAULT_BLENDER,
        DEFAULT_CURRENT_PROFILE,
        DEFAULT_FIELDS,
        DEFAULT_FUZZY_AI_GATHER_PATTERN_PRESET,
        DEFAULT_BLOOMS_AI_PATTERN_PRESET,
        DEFAULT_FUZZY_AI_TOKEN_RANKING,
        DEFAULT_FUZZY_AI_TOKEN_RANKINGS,
        DEFAULT_GENERAL_SETTINGS,
        DEFAULT_HOTBAR_TIMINGS,
        DEFAULT_HOURLY_REPORT_BG,
        DEFAULT_HOURLY_REPORT_HISTORY,
        DEFAULT_HOURLY_REPORT_MAIN,
        DEFAULT_MANUAL_PLANTERS,
        DEFAULT_PROFILE_SETTINGS,
        DEFAULT_STICKER_STACK,
        DEFAULT_TIMINGS,
        FIELD_PATTERN_PRESETS_KEY,
        FUZZY_AI_RUNTIME_DEFAULTS,
        deepcopy_default,
    )
except ImportError:
    # discordBot (and similar) historically import this module as a top-level
    # `settingsManager` via sys.path, so relative imports have no parent package.
    from settings_defaults import (
        DEFAULT_AFB,
        DEFAULT_AI_PATTERN_PRESETS,
        DEFAULT_AUTO_PLANTERS,
        DEFAULT_BLENDER,
        DEFAULT_CURRENT_PROFILE,
        DEFAULT_FIELDS,
        DEFAULT_FUZZY_AI_GATHER_PATTERN_PRESET,
        DEFAULT_BLOOMS_AI_PATTERN_PRESET,
        DEFAULT_FUZZY_AI_TOKEN_RANKING,
        DEFAULT_FUZZY_AI_TOKEN_RANKINGS,
        DEFAULT_GENERAL_SETTINGS,
        DEFAULT_HOTBAR_TIMINGS,
        DEFAULT_HOURLY_REPORT_BG,
        DEFAULT_HOURLY_REPORT_HISTORY,
        DEFAULT_HOURLY_REPORT_MAIN,
        DEFAULT_MANUAL_PLANTERS,
        DEFAULT_PROFILE_SETTINGS,
        DEFAULT_STICKER_STACK,
        DEFAULT_TIMINGS,
        FIELD_PATTERN_PRESETS_KEY,
        FUZZY_AI_RUNTIME_DEFAULTS,
        deepcopy_default,
    )

#returns a dictionary containing the settings
profileName = DEFAULT_CURRENT_PROFILE
_macro_profile_store = None

# File to store current profile persistence (defined after getProjectRoot)
CURRENT_PROFILE_FILE = None

def loadCurrentProfile():
    """Load the current profile from persistent storage"""
    global profileName
    try:
        if os.path.exists(CURRENT_PROFILE_FILE):
            with open(CURRENT_PROFILE_FILE, "r") as f:
                saved_profile = f.read().strip()
                if saved_profile and os.path.exists(getProfilePath(saved_profile)):
                    profileName = saved_profile
    except Exception as e:
        print(f"Warning: Could not load current profile: {e}")

def saveCurrentProfile():
    """Save the current profile to persistent storage"""
    try:
        with open(CURRENT_PROFILE_FILE, "w") as f:
            f.write(profileName)
    except Exception as e:
        print(f"Warning: Could not save current profile: {e}")

# Load the current profile when the module is imported (called at the end of the file)

# Get the project root directory (4 levels up from this file: src/modules/misc/settingsManager.py)
def getProjectRoot():
    """Get the project root directory path"""
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# File to store current profile persistence
CURRENT_PROFILE_FILE = os.path.join(getProjectRoot(), "src", "data", "user", "current_profile.txt")
FUZZY_AI_TOKEN_RANKINGS_FILE = os.path.join(getProjectRoot(), "src", "data", "user", "fuzzy_ai_token_rankings.json")

# Helper functions for common paths
def getProfilesDir():
    """Get the profiles directory path"""
    return os.path.join(getProjectRoot(), "settings", "profiles")

def _getMacroProfileStore():
    global _macro_profile_store
    if _macro_profile_store is None:
        _macro_profile_store = MacroProfileStore(
            getProfilesDir(),
            getDefaultProfileSettings(),
            getDefaultGeneralSettings(),
            loadDefaultFields(),
            field_normalizer=normalizeFieldSettings,
        )
    return _macro_profile_store

def initializeMacroProfile(profile_name=None):
    """Run explicit repair and migration for a Macro Profile."""
    return _getMacroProfileStore().initialize(profile_name or profileName).as_dict()

def getMacroProfileSnapshot(profile_name=None):
    """Return a versioned, side-effect-free Macro Profile snapshot."""
    if profile_name is None:
        loadCurrentProfile()
    return _getMacroProfileStore().snapshot(profile_name or profileName).as_dict()

def applyMacroProfileChange(scope, setting, value):
    """Apply one validated change and return a structured result for the GUI."""
    try:
        snapshot = _getMacroProfileStore().apply_change(profileName, scope, setting, value)
        return {"ok": True, "snapshot": snapshot.as_dict()}
    except MacroProfileValidationError as exc:
        return {"ok": False, "error": exc.as_dict()}
    except MacroProfileError as exc:
        return {"ok": False, "error": {"setting": setting, "reason": str(exc)}}

def getProfilePath(profile_name=None):
    """Get the path to a specific profile directory"""
    if profile_name is None:
        profile_name = profileName
    return os.path.join(getProfilesDir(), profile_name)

def getUserDataDir():
    """Get the runtime user data directory path."""
    return os.path.join(getProjectRoot(), "src", "data", "user")

def getUserDataPath(filename):
    """Get an absolute path under the runtime user data directory."""
    return os.path.join(getUserDataDir(), filename)

def getDefaultProfileSettings():
    """Return a deep copy of hardcoded profile settings defaults."""
    return deepcopy_default(DEFAULT_PROFILE_SETTINGS)

def getDefaultGeneralSettings():
    """Return a deep copy of hardcoded general settings defaults."""
    return deepcopy_default(DEFAULT_GENERAL_SETTINGS)

def getSettingsDir():
    """Get the settings directory path"""
    return os.path.join(getProjectRoot(), "settings")

def getPatternsDir():
    """Get the patterns directory path"""
    return os.path.join(getProjectRoot(), "settings", "patterns")

def getFuzzyAIModelPath(model_filename):
    """Get the fixed fuzzy AI model path under src/data/models."""
    return os.path.join(getProjectRoot(), "src", "data", "models", model_filename)

def loadDefaultFields():
    """Load default field settings from hardcoded defaults."""
    return deepcopy_default(DEFAULT_FIELDS)

def _writeTextFile(path, content):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w") as f:
        f.write(content if content.endswith("\n") or content == "" else content + "\n")

def _writeLiteralFile(path, value):
    _writeTextFile(path, str(value))

def _writeJsonFile(path, value):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w") as f:
        json.dump(value, f, indent=3)
        f.write("\n")

def _writeFieldsFile(path, fields_data):
    _writeTextFile(path, str(fields_data))

def ensureProfileFiles(profile_name=None):
    """Create missing profile settings/general/fields files from hardcoded defaults."""
    if profile_name is None:
        profile_name = profileName or DEFAULT_CURRENT_PROFILE
    profile_path = getProfilePath(profile_name)
    os.makedirs(profile_path, exist_ok=True)

    settings_path = os.path.join(profile_path, "settings.txt")
    general_path = os.path.join(profile_path, "generalsettings.txt")
    fields_path = os.path.join(profile_path, "fields.txt")

    if not os.path.exists(settings_path):
        saveDict(settings_path, getDefaultProfileSettings())
    if not os.path.exists(general_path):
        saveDict(general_path, getDefaultGeneralSettings())
    if not os.path.exists(fields_path):
        _writeFieldsFile(fields_path, loadDefaultFields())

def ensureUserFile(filename):
    """Create a single runtime user file from hardcoded defaults if missing."""
    path = getUserDataPath(filename)
    if os.path.exists(path):
        return path

    os.makedirs(getUserDataDir(), exist_ok=True)
    writers = {
        "timings.txt": lambda: saveDict(path, deepcopy_default(DEFAULT_TIMINGS)),
        "AFB.txt": lambda: saveDict(path, deepcopy_default(DEFAULT_AFB)),
        "blender.txt": lambda: _writeLiteralFile(path, deepcopy_default(DEFAULT_BLENDER)),
        "sticker_stack.txt": lambda: _writeTextFile(path, str(DEFAULT_STICKER_STACK)),
        "hotbar_timings.txt": lambda: _writeLiteralFile(path, deepcopy_default(DEFAULT_HOTBAR_TIMINGS)),
        "manualplanters.txt": lambda: _writeTextFile(path, DEFAULT_MANUAL_PLANTERS),
        "auto_planters.json": lambda: _writeJsonFile(path, deepcopy_default(DEFAULT_AUTO_PLANTERS)),
        "current_profile.txt": lambda: _writeTextFile(path, DEFAULT_CURRENT_PROFILE),
        "hourly_report_history.txt": lambda: _writeLiteralFile(path, deepcopy_default(DEFAULT_HOURLY_REPORT_HISTORY)),
        "hourly_report_main.txt": lambda: saveDict(path, deepcopy_default(DEFAULT_HOURLY_REPORT_MAIN)),
        "hourly_report_bg.txt": lambda: saveDict(path, deepcopy_default(DEFAULT_HOURLY_REPORT_BG)),
        "fuzzy_ai_token_rankings.json": lambda: _writeJsonFile(path, deepcopy_default(DEFAULT_FUZZY_AI_TOKEN_RANKINGS)),
    }
    writer = writers.get(filename)
    if writer is None:
        raise ValueError(f"No hardcoded default registered for user file: {filename}")
    writer()
    return path

def ensureDefaultPatterns():
    """Copy shipped patterns missing from settings/patterns. Existing user files are never replaced."""
    defaults_dir = os.path.join(getSettingsDir(), "defaults", "patterns")
    patterns_dir = getPatternsDir()
    if not os.path.isdir(defaults_dir):
        return
    os.makedirs(patterns_dir, exist_ok=True)
    for filename in os.listdir(defaults_dir):
        if os.path.splitext(filename)[1].lower() not in (".py", ".ahk"):
            continue
        target = os.path.join(patterns_dir, filename)
        if not os.path.exists(target):
            shutil.copy2(os.path.join(defaults_dir, filename), target)

def migrateProfilesToGeneralSettings():
    """Give each profile its own generalsettings.txt, copied from the old global one.

    Must run before ensureProfileFiles, which would otherwise create the current
    profile's generalsettings.txt from defaults first and skip that profile.
    """
    global_generalsettings = os.path.join(getSettingsDir(), "generalsettings.txt")
    # Check if global generalsettings exists - if not, migration is already complete
    if not os.path.exists(global_generalsettings) or not os.path.exists(getProfilesDir()):
        return

    migrated = False
    migration_failed = False
    for profile_name in listProfiles():
        generalsettings_file = os.path.join(getProfilesDir(), profile_name, "generalsettings.txt")
        if os.path.exists(generalsettings_file):
            continue
        try:
            shutil.copy2(global_generalsettings, generalsettings_file)
            print(f"Migrated generalsettings.txt for profile: {profile_name}")
            migrated = True
        except Exception as e:
            migration_failed = True
            print(f"Warning: Failed to migrate generalsettings.txt for profile '{profile_name}': {e}")

    # Every profile has its own copy now, so the global file is no longer needed
    if migrated and not migration_failed:
        try:
            os.remove(global_generalsettings)
            print("Removed old global generalsettings.txt file")
        except Exception as e:
            print(f"Warning: Failed to remove old global generalsettings.txt file: {e}")

def ensureRuntimeData():
    """Create user/profile runtime directories and missing seed files."""
    os.makedirs(getUserDataDir(), exist_ok=True)
    os.makedirs(getProfilesDir(), exist_ok=True)
    migrateProfilesToGeneralSettings()
    ensureDefaultPatterns()

    for filename in (
        "timings.txt",
        "AFB.txt",
        "blender.txt",
        "sticker_stack.txt",
        "hotbar_timings.txt",
        "manualplanters.txt",
        "auto_planters.json",
        "hourly_report_history.txt",
        "hourly_report_main.txt",
        "hourly_report_bg.txt",
        "fuzzy_ai_token_rankings.json",
    ):
        ensureUserFile(filename)

    profiles = listProfiles()
    if not profiles:
        # Fresh install: create the default profile only when none exist.
        ensureProfileFiles(DEFAULT_CURRENT_PROFILE)
        if not os.path.exists(CURRENT_PROFILE_FILE):
            _writeTextFile(CURRENT_PROFILE_FILE, DEFAULT_CURRENT_PROFILE)
    else:
        # Repair the active/persisted profile if its trio is incomplete.
        # Never recreate a missing default profile while another profile exists.
        target = profileName if os.path.isdir(getProfilePath(profileName)) else None
        if target is None and os.path.exists(CURRENT_PROFILE_FILE):
            try:
                with open(CURRENT_PROFILE_FILE, "r") as f:
                    saved = f.read().strip()
                if saved and os.path.isdir(getProfilePath(saved)):
                    target = saved
            except Exception:
                target = None
        if target is None:
            # Prefer an existing "default" profile when present, else first profile.
            target = DEFAULT_CURRENT_PROFILE if DEFAULT_CURRENT_PROFILE in profiles else profiles[0]
        ensureProfileFiles(target)
        if not os.path.exists(CURRENT_PROFILE_FILE):
            _writeTextFile(CURRENT_PROFILE_FILE, target)

def saveUserSettingsFile(filename, data):
    saveDict(getUserDataPath(filename), data)

def loadUserJson(filename):
    path = ensureUserFile(filename)
    with open(path, "r") as f:
        return json.load(f)

def saveUserJson(filename, data):
    _writeJsonFile(getUserDataPath(filename), data)

def loadUserText(filename):
    path = ensureUserFile(filename)
    with open(path, "r") as f:
        return f.read()

def saveUserText(filename, text):
    _writeTextFile(getUserDataPath(filename), str(text))

def loadUserLiteral(filename):
    path = ensureUserFile(filename)
    with open(path, "r") as f:
        raw = f.read().strip()
    if not raw:
        if filename == "manualplanters.txt":
            return []
        if filename == "hourly_report_history.txt":
            return []
        return None
    return ast.literal_eval(raw)

def saveUserLiteral(filename, value):
    _writeLiteralFile(getUserDataPath(filename), value)

def _defaultsForSettingsPath(path):
    """Resolve hardcoded defaults for known settings-style files."""
    name = os.path.basename(path)
    if name == "settings.txt":
        return getDefaultProfileSettings()
    if name == "generalsettings.txt":
        return getDefaultGeneralSettings()
    if name == "timings.txt":
        return deepcopy_default(DEFAULT_TIMINGS)
    if name == "AFB.txt":
        return deepcopy_default(DEFAULT_AFB)
    if name == "hourly_report_main.txt":
        return deepcopy_default(DEFAULT_HOURLY_REPORT_MAIN)
    if name == "hourly_report_bg.txt":
        return deepcopy_default(DEFAULT_HOURLY_REPORT_BG)
    return None

def _stripAIGatherFieldKeys(settings):
    if not isinstance(settings, dict):
        return {}
    return {key: value for key, value in settings.items() if not str(key).startswith("fuzzy_ai_")}

def _buildDefaultAIPatternPreset(pattern, settings=None):
    """Build a starter AI pattern preset, keeping field-specific gather limits."""
    defaults = DEFAULT_AI_PATTERN_PRESETS.get(pattern)
    if not defaults:
        return {}
    base = _fieldSettingsWithoutPatternPresets(settings) if isinstance(settings, dict) else {}
    return {**base, **defaults}

def _ensureDefaultAIPatternPresets(settings):
    """Insert default AI Gathering / BloomsAI pattern presets when a field is missing them."""
    if not isinstance(settings, dict):
        return {}

    presets = _getFieldPatternPresets(settings)
    missing = [pattern for pattern in DEFAULT_AI_PATTERN_PRESETS if pattern not in presets]
    if not missing:
        return settings

    ensured = dict(settings)
    for pattern in missing:
        presets[pattern] = _buildDefaultAIPatternPreset(pattern, ensured)
    ensured[FIELD_PATTERN_PRESETS_KEY] = presets
    return ensured

def normalizeFieldSettings(field_name, settings, default_fields=None):
    """Merge bundled defaults into a field settings object."""
    if default_fields is None:
        default_fields = loadDefaultFields()

    normalized = {}

    default_field_settings = default_fields.get(field_name)
    if isinstance(default_field_settings, dict):
        normalized.update(
            _stripAIGatherFieldKeys(_fieldSettingsWithoutPatternPresets(default_field_settings))
        )

    if isinstance(settings, dict):
        normalized.update(
            _stripAIGatherFieldKeys(_fieldSettingsWithoutPatternPresets(settings))
        )

    # Merge pattern presets. Settings win. Do not inherit bundled AI pattern presets
    # onto existing fields — ensure builds those from the field's current values.
    default_presets = {
        pattern: preset
        for pattern, preset in _getFieldPatternPresets(
            default_field_settings if isinstance(default_field_settings, dict) else {}
        ).items()
        if pattern not in DEFAULT_AI_PATTERN_PRESETS
    }
    settings_presets = _getFieldPatternPresets(settings if isinstance(settings, dict) else {})
    merged_presets = {**default_presets, **settings_presets}
    if merged_presets:
        normalized[FIELD_PATTERN_PRESETS_KEY] = merged_presets

    return _coerceNestedValues(_ensureDefaultAIPatternPresets(normalized))

def _getFieldPatternPresets(settings):
    if not isinstance(settings, dict):
        return {}
    presets = settings.get(FIELD_PATTERN_PRESETS_KEY, {})
    if isinstance(presets, dict):
        return {
            str(pattern): dict(preset)
            for pattern, preset in presets.items()
            if isinstance(preset, dict)
        }
    return {}

def _fieldSettingsWithoutPatternPresets(settings):
    if not isinstance(settings, dict):
        return {}
    return {
        key: value
        for key, value in settings.items()
        if key != FIELD_PATTERN_PRESETS_KEY
    }

def _saveFieldPatternPreset(presets, pattern, settings):
    if not pattern:
        return
    preset = _fieldSettingsWithoutPatternPresets(settings)
    preset["shape"] = pattern
    presets[pattern] = preset

def getDefaultFuzzyAIGatherPatternPreset():
    """Return a copy of the default AI Gathering pattern preset for the UI."""
    return dict(DEFAULT_FUZZY_AI_GATHER_PATTERN_PRESET)

def getDefaultBloomsAIPatternPreset():
    """Return a copy of the default BloomsAI pattern preset for the UI."""
    return dict(DEFAULT_BLOOMS_AI_PATTERN_PRESET)

def _applyFieldPatternPresets(existing_settings, incoming_settings):
    incoming_shape = incoming_settings.get("shape")
    existing_shape = (
        existing_settings.get("shape") if isinstance(existing_settings, dict) else None
    )

    presets = _getFieldPatternPresets(existing_settings)
    presets.update(_getFieldPatternPresets(incoming_settings))
    source_settings = incoming_settings if isinstance(incoming_settings, dict) else existing_settings
    for pattern in DEFAULT_AI_PATTERN_PRESETS:
        if pattern not in presets:
            presets[pattern] = _buildDefaultAIPatternPreset(pattern, source_settings)

    if existing_shape and existing_shape != incoming_shape:
        _saveFieldPatternPreset(presets, existing_shape, existing_settings)

    if existing_shape != incoming_shape and incoming_shape in presets:
        merged_settings = {
            **incoming_settings,
            **presets[incoming_shape],
            "shape": incoming_shape,
        }
    else:
        merged_settings = dict(incoming_settings)

    _saveFieldPatternPreset(presets, incoming_shape, merged_settings)
    merged_settings[FIELD_PATTERN_PRESETS_KEY] = presets
    return merged_settings

def _fieldSettingsWithCurrentPatternPreset(settings):
    if not isinstance(settings, dict):
        return {}

    exported_settings = dict(settings)
    presets = _getFieldPatternPresets(exported_settings)
    current_shape = exported_settings.get("shape")

    if current_shape in presets:
        exported_settings[FIELD_PATTERN_PRESETS_KEY] = {
            current_shape: dict(presets[current_shape])
        }
    else:
        exported_settings.pop(FIELD_PATTERN_PRESETS_KEY, None)

    return exported_settings

def _tokenRankingDefaults():
    return {
        "preferred_tokens": DEFAULT_FUZZY_AI_TOKEN_RANKING["preferred_tokens"],
        "ignored_tokens": DEFAULT_FUZZY_AI_TOKEN_RANKING["ignored_tokens"],
    }

def loadFuzzyAITokenRankings():
    """Load per-field AI Gathering token rankings from src/data/user."""
    try:
        path = ensureUserFile("fuzzy_ai_token_rankings.json")
        with open(path, "r") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except Exception as e:
        print(f"Warning: Could not load AI token rankings: {e}")
    return deepcopy_default(DEFAULT_FUZZY_AI_TOKEN_RANKINGS)

def saveFuzzyAITokenRankings(data):
    os.makedirs(os.path.dirname(FUZZY_AI_TOKEN_RANKINGS_FILE), exist_ok=True)
    with open(FUZZY_AI_TOKEN_RANKINGS_FILE, "w") as f:
        json.dump(data, f, indent=2)

def _normalizeFuzzyAIModel(model):
    value = str(model or "standard").strip().lower()
    return value if value in ("standard", "light", "mini") else "standard"

def loadFuzzyAITokenRanking(field_name, model="standard"):
    rankings = loadFuzzyAITokenRankings()
    field_rankings = rankings.get(field_name, {})
    model = _normalizeFuzzyAIModel(model)
    defaults = _tokenRankingDefaults()
    if not isinstance(field_rankings, dict):
        field_rankings = {}

    # Existing files stored one flat ranking per field. Preserve it as Standard.
    if "preferred_tokens" in field_rankings or "ignored_tokens" in field_rankings:
        ranking = field_rankings if model == "standard" else {}
    else:
        ranking = field_rankings.get(model, {})
    if not isinstance(ranking, dict):
        ranking = {}
    return {
        "preferred_tokens": ranking.get("preferred_tokens") or defaults["preferred_tokens"],
        "ignored_tokens": ranking.get("ignored_tokens") or defaults["ignored_tokens"],
    }

def saveFuzzyAITokenRanking(field_name, ranking, model="standard"):
    rankings = loadFuzzyAITokenRankings()
    model = _normalizeFuzzyAIModel(model)
    field_rankings = rankings.get(field_name, {})
    if not isinstance(field_rankings, dict):
        field_rankings = {}
    if "preferred_tokens" in field_rankings or "ignored_tokens" in field_rankings:
        field_rankings = {"standard": field_rankings}

    current = loadFuzzyAITokenRanking(field_name, model)
    if isinstance(ranking, dict):
        current["preferred_tokens"] = str(ranking.get("preferred_tokens", current["preferred_tokens"]))
        current["ignored_tokens"] = str(ranking.get("ignored_tokens", current["ignored_tokens"]))
    field_rankings[model] = current
    rankings[field_name] = field_rankings
    saveFuzzyAITokenRankings(rankings)
    return current

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

def switchProfile(name):
    """Switch to a different profile"""
    global profileName
    profiles_dir = getProfilesDir()
    profile_path = os.path.join(profiles_dir, name)

    if not os.path.exists(profile_path) or not os.path.isdir(profile_path):
        return False, f"Profile '{name}' not found"

    # Seed any missing required profile files from hardcoded defaults
    ensureProfileFiles(name)

    profileName = name
    # Save the profile selection persistently
    saveCurrentProfile()
    # Switching is the explicit repair/migration point for the selected profile.
    _getMacroProfileStore().initialize(name)

    return True, f"Switched to profile: {name}"

def createProfile(name):
    """Create a new profile using hardcoded default settings."""
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
        os.makedirs(new_profile_path, exist_ok=True)
        ensureProfileFiles(name)
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
            saveCurrentProfile()
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

def readSettingsFile(path, defaults=None):
    #get each line
    #read the file, format it to:
    #[[key, value], [key, value]]
    if not os.path.exists(path):
        resolved = defaults if defaults is not None else _defaultsForSettingsPath(path)
        if resolved is not None:
            data = deepcopy_default(resolved)
            saveDict(path, data)
            return data
        raise FileNotFoundError(f"[Errno 2] No such file or directory: {path!r}")

    with open(path) as f:
        raw = f.read()

    # If `max_convert_time=` was accidentally concatenated onto the previous line,
    # insert a newline before it so it becomes its own setting line.
    raw = re.sub(r'(?<!\n)max_convert_time=', r'\nmax_convert_time=', raw)

    data = [[x.strip() for x in y.split("=", 1)] for y in raw.split("\n") if y]
    #convert to a dict
    resolved_defaults = defaults if defaults is not None else _defaultsForSettingsPath(path)
    out = {}
    for k, v in data:
        parsed = _parseSettingValue(v)
        # Keep string-typed settings as strings (tokens, snowflake IDs, URLs, etc.)
        # even when the raw value looks numeric.
        if resolved_defaults is not None:
            default_val = resolved_defaults.get(k)
            if isinstance(default_val, str) and not isinstance(parsed, str):
                parsed = "" if parsed is None else str(parsed)
        out[k] = parsed
    return out

def _parseSettingValue(value):
    """Parse a settings-file value while preserving unquoted strings."""
    try:
        return ast.literal_eval(value)
    except Exception:
        if value.isdigit():
            return int(value)
        if value.replace(".", "", 1).isdigit():
            return float(value)
        return value

def _coerceScalarValue(value):
    """Normalize numeric strings loaded from legacy profile files."""
    if isinstance(value, str):
        return _parseSettingValue(value)
    return value

def _coerceNestedValues(value):
    if isinstance(value, dict):
        return {k: _coerceNestedValues(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_coerceNestedValues(v) for v in value]
    return _coerceScalarValue(value)

def saveDict(path, data):
    out = "\n".join([f"{k}={v}" for k,v in data.items()])
    # Ensure file ends with a newline to avoid accidental concatenation
    if not out.endswith("\n"):
        out = out + "\n"
    abs_path = os.path.abspath(path)
    directory = os.path.dirname(abs_path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    # Write to a temp file then replace, so a concurrent reader never sees a
    # truncated/empty settings file mid-save.
    fd, tmp_path = tempfile.mkstemp(prefix=".settings_", suffix=".tmp", dir=directory or None)
    try:
        with os.fdopen(fd, "w") as f:
            f.write(out)
        os.replace(tmp_path, abs_path)
    except Exception:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass
        raise

#update one property of a setting
def saveSettingFile(setting,value, path):
    #get the dictionary, creating from defaults when possible
    if os.path.exists(path):
        data = readSettingsFile(path)
    else:
        defaults = _defaultsForSettingsPath(path)
        data = deepcopy_default(defaults) if defaults is not None else {}
    #update the dictionary
    data[setting] = value
    #write it
    saveDict(path, data)

def loadFields():
    return getMacroProfileSnapshot(profileName)["fields"]

def saveField(field, settings):
    snapshot = getMacroProfileSnapshot(profileName)
    existingSettings = snapshot["fields"].get(field, {})
    normalizedSettings = normalizeFieldSettings(field, settings)
    mergedSettings = _applyFieldPatternPresets(existingSettings, normalizedSettings)
    _getMacroProfileStore().save_field(profileName, field, mergedSettings)

def exportFieldSettings(field_name):
    """Export field settings as JSON string with metadata"""
    fields_data = loadFields()
    if field_name in fields_data:
        field_settings = _fieldSettingsWithCurrentPatternPreset(fields_data[field_name])
        # Create export data with metadata
        export_data = {
            "metadata": {
                "field_name": field_name,
                "macro_version": getMacroVersion(),
                "export_date": datetime.now().isoformat()
            },
            "settings": field_settings
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

        imported_token_ranking = None
        if "fuzzy_ai_preferred_tokens" in settings or "fuzzy_ai_ignored_tokens" in settings:
            imported_token_ranking = {
                "preferred_tokens": settings.get("fuzzy_ai_preferred_tokens"),
                "ignored_tokens": settings.get("fuzzy_ai_ignored_tokens"),
            }

        settings = normalizeFieldSettings(field_name, settings)

        # Check for missing patterns and replace with defaults
        missing_patterns = []
        warnings = []
        available_patterns = getAvailablePatterns()

        if "shape" in settings:
            requested_pattern = settings["shape"]
            if requested_pattern not in available_patterns:
                # Replace with first available pattern (default)
                default_pattern = available_patterns[0] if available_patterns else "cornerxe_lol"
                settings["shape"] = default_pattern
                missing_patterns.append(f"'{requested_pattern}' → '{default_pattern}'")

        if settings.get("shape") in ("fuzzy_ai_gather", "blooms_ai"):
            token_model = getFuzzyAIModelPath("token_detection_standard.mlmodelc")
            token_model_onnx = getFuzzyAIModelPath("token_detection_standard.onnx")
            sprinkler_model = getFuzzyAIModelPath("sprinkler_detection_standard.mlmodelc")
            sprinkler_model_onnx = getFuzzyAIModelPath("sprinkler_detection_standard.onnx")
            if settings.get("shape") == "fuzzy_ai_gather" and not os.path.exists(token_model) and not os.path.exists(token_model_onnx):
                warnings.append("Missing token model: src/data/models/token_detection_standard.mlmodelc or src/data/models/token_detection_standard.onnx")
            if settings.get("shape") == "blooms_ai":
                blooms_model_names = {
                    "standard": (
                        "bloom_detection_standard.mlmodelc",
                        "bloom_detection_standard.onnx",
                    ),
                    "light": (
                        "bloom_detection_light.mlmodelc",
                        "bloom_detection_light.onnx",
                    ),
                    "mini": (
                        "bloom_detection_mini.mlmodelc",
                        "bloom_detection_mini.onnx",
                    ),
                }
                selected_blooms_model = str(settings.get("blooms_ai_model", "Standard")).strip().lower()
                blooms_coreml, blooms_onnx = blooms_model_names.get(
                    selected_blooms_model, blooms_model_names["standard"]
                )
                if not os.path.exists(getFuzzyAIModelPath(blooms_coreml)) and not os.path.exists(
                    getFuzzyAIModelPath(blooms_onnx)
                ):
                    warnings.append(
                        f"Missing BloomsAI model: src/data/models/{blooms_coreml} or src/data/models/{blooms_onnx}"
                    )
            if not os.path.exists(sprinkler_model) and not os.path.exists(sprinkler_model_onnx):
                warnings.append("Missing sprinkler model: src/data/models/sprinkler_detection_standard.mlmodelc or src/data/models/sprinkler_detection_standard.onnx")

        # Save the imported settings
        saveField(field_name, settings)
        if imported_token_ranking is not None:
            saveFuzzyAITokenRanking(field_name, imported_token_ranking)

        # Return success with information about any pattern replacements and metadata
        result = {
            "success": True,
            "missing_patterns": missing_patterns,
            "warnings": warnings,
            "imported_from_field": exported_field,
            "macro_version": macro_version
        }
        return result

    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON format: {str(e)}")

def _isPlanterSettingKey(key):
    """Return True when a profile setting belongs to the planters tab."""
    if key in {
        "planters_mode",
        "manual_planters_collect_every",
        "manual_planters_collect_full",
        "manual_planters_check",
        "planters_collect_loot",
        "auto_planters_collect_every",
        "auto_planters_collect_full",
        "auto_planters_collect_auto",
        "auto_planters_check",
        "auto_max_planters",
        "auto_preset",
    }:
        return True

    if re.match(r"^cycle\d+_\d+_(planter|field|gather|glitter)$", key):
        return True

    if re.match(r"^auto_priority_\d+_(nectar|min)$", key):
        return True

    return (
        key.startswith("auto_field_")
        or key.startswith("auto_planter_")
        or key.startswith("planter_hotbar_")
    )

def _getAutoPlanterUserPath():
    return os.path.join(getProjectRoot(), "src", "data", "user", "auto_planters.json")

def _readAutoPlanterGatherFlag():
    try:
        with open(_getAutoPlanterUserPath(), "r") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return bool(data.get("gather", False))
    except Exception:
        pass
    return False

def _writeAutoPlanterGatherFlag(value):
    path = _getAutoPlanterUserPath()
    try:
        with open(path, "r") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            data = {}
    except Exception:
        data = {}

    data["gather"] = bool(value)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=3)

def exportPlanterSettings():
    """Export planter profile settings as JSON string with metadata."""
    settings = loadSettings()
    planter_settings = {
        key: value
        for key, value in settings.items()
        if _isPlanterSettingKey(key)
    }

    export_data = {
        "metadata": {
            "settings_type": "planters",
            "macro_version": getMacroVersion(),
            "export_date": datetime.now().isoformat()
        },
        "settings": planter_settings,
        "user_settings": {
            "auto_planters_gather": _readAutoPlanterGatherFlag()
        }
    }
    return json.dumps(export_data, indent=2)

def importPlanterSettings(json_settings):
    """Import planter settings from JSON string with backward compatibility."""
    try:
        data = json.loads(json_settings)

        if isinstance(data, dict) and "metadata" in data and "settings" in data:
            settings = data["settings"]
            user_settings = data.get("user_settings", {})
            metadata = data.get("metadata", {})
            macro_version = metadata.get("macro_version", "unknown")
        else:
            settings = data
            user_settings = data if isinstance(data, dict) else {}
            macro_version = "unknown"

        if not isinstance(settings, dict):
            raise ValueError("Invalid JSON format: expected object")

        planter_settings = {
            key: _coerceNestedValues(value)
            for key, value in settings.items()
            if _isPlanterSettingKey(key)
        }

        if not planter_settings and "auto_planters_gather" not in user_settings:
            raise ValueError("No planter settings found in JSON")

        if planter_settings:
            saveDictProfileSettings(planter_settings)

        if isinstance(user_settings, dict) and "auto_planters_gather" in user_settings:
            _writeAutoPlanterGatherFlag(user_settings["auto_planters_gather"])

        return {
            "success": True,
            "imported_settings_count": len(planter_settings),
            "macro_version": macro_version
        }

    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON format: {str(e)}")

def getAvailablePatterns():
    """Get list of available pattern names"""
    patterns_dir = getPatternsDir()
    if os.path.exists(patterns_dir):
        out = []
        for filename in os.listdir(patterns_dir):
            root, ext = os.path.splitext(filename)
            if ext.lower() in (".py", ".ahk"):
                out.append(root)
        return sorted(out)
    return []

def saveProfileSetting(setting, value):
    return _getMacroProfileStore().apply_change(profileName, "profile", setting, value).as_dict()

def saveDictProfileSettings(dict):
    return _getMacroProfileStore().apply_changes(profileName, "profile", dict).as_dict()

#increment a setting, and return all settings after the change
def incrementProfileSetting(setting, incrValue):
    current = loadSettings()
    if setting not in current:
        raise MacroProfileValidationError(setting, "unknown setting")
    return saveProfileSetting(setting, current[setting] + incrValue)["settings"]

def saveGeneralSetting(setting, value):
    return _getMacroProfileStore().apply_change(profileName, "general", setting, value).as_dict()

def loadSettings():
    return _getMacroProfileStore().read(profileName)[0]

#return a dict containing all settings except field (general, profile, planters)
def loadAllSettings():
    # Reload the selected profile name so a switch made by another process is seen.
    loadCurrentProfile()
    return getMacroProfileSnapshot()["settings"]

def exportProfile(profile_name):
    """Export a profile to JSON content for browser download"""
    profiles_dir = getProfilesDir()
    profile_path = os.path.join(profiles_dir, profile_name)

    if not os.path.exists(profile_path):
        return False, f"Profile '{profile_name}' not found"

    # Read profile data
    try:
        settings_file = os.path.join(profile_path, "settings.txt")
        fields_file = os.path.join(profile_path, "fields.txt")
        generalsettings_file = os.path.join(profile_path, "generalsettings.txt")

        if not os.path.exists(settings_file) or not os.path.exists(fields_file) or not os.path.exists(generalsettings_file):
            return False, f"Profile '{profile_name}' is missing required files"

        settings_data, generalsettings_data, fields_data = _getMacroProfileStore().read(profile_name, strict=True)

        # Ensure sensitive fields are removed from export
        sensitive_keys = ("discord_bot_token", "webhook_link", "private_server_link")
        route_sensitive_keys = [
            key for key in generalsettings_data.keys()
            if str(key).startswith("route_") and str(generalsettings_data.get(key, "")).startswith("https://")
        ]
        for k in list(sensitive_keys) + route_sensitive_keys:
            if k in settings_data:
                settings_data[k] = ""
            if k in generalsettings_data:
                generalsettings_data[k] = ""

        # Create export data structure
        export_data = {
            "profile_name": profile_name,
            "export_date": datetime.now().isoformat(),
            "version": getMacroVersion(),
            "settings": settings_data,
            "fields": fields_data,
            "generalsettings": generalsettings_data
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
        required_keys = ["profile_name", "settings", "fields", "generalsettings"]
        for key in required_keys:
            if key not in import_data:
                return False, f"Invalid import file: missing '{key}' key"

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

        # Write settings file
        settings_file = os.path.join(new_profile_path, "settings.txt")
        saveDict(settings_file, import_data["settings"])

        # Write fields file
        fields_file = os.path.join(new_profile_path, "fields.txt")
        with open(fields_file, 'w') as f:
            f.write(str(import_data["fields"]))

        # Write generalsettings file
        generalsettings_file = os.path.join(new_profile_path, "generalsettings.txt")
        saveDict(generalsettings_file, import_data["generalsettings"])

        # the export may come from an older version, so migrate it now like an installed profile
        _getMacroProfileStore().prepare(new_profile_name)

        return True, f"Profile imported successfully as '{new_profile_name}'"

    except Exception as e:
        return False, f"Failed to import profile: {str(e)}"

# Seed runtime/profile files, then load the current profile when the module is imported
ensureRuntimeData()
loadCurrentProfile()
# Create missing files and run pending migrations (once per profile after an update).
try:
    initializeMacroProfile()
except Exception as exc:
    print(f"Warning: Could not initialize Macro Profile '{profileName}': {exc}")

#clear a file
def clearFile(filePath):
    directory = os.path.dirname(os.path.abspath(filePath))
    if directory:
        os.makedirs(directory, exist_ok=True)
    open(filePath, 'w').close()
