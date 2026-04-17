import ast
import os
import shutil
import json
import zipfile
import tempfile
from datetime import datetime
import re

FUZZY_AI_RUNTIME_DEFAULTS = {
    "fuzzy_ai_confidence_threshold": 0.4,
    "fuzzy_ai_sprinkler_confidence_threshold": 0.6,
    "fuzzy_ai_min_token_distance": 0.3,
    "fuzzy_ai_idle_return_interval": 1.5,
    "fuzzy_ai_no_token_recalibration_timeout": 12.0,
    "fuzzy_ai_movements_before_recalibration": 10,
    "fuzzy_ai_sprinkler_arrival_threshold": 0.8,
    "fuzzy_ai_max_sprinkler_distance": 10.0,
    "fuzzy_ai_sprinkler_rescan_attempts": 3,
    "fuzzy_ai_sprinkler_rescan_delay": 0.3,
    "fuzzy_ai_target_sprinkler_label": "",
    "fuzzy_ai_capture_backend": "auto",
}

DEFAULT_FUZZY_AI_TOKEN_RANKING = {
    "preferred_tokens": "Token Link,Focus,Melody,Blue Boost,Honey Mark,Honey Mark Token,Pollen Mark,Pollen Mark Token,Haste",
    "ignored_tokens": "Honey,Blueberry",
}

#returns a dictionary containing the settings
profileName = "a"
# Track profile changes for running macro processes
_profile_change_counter = 0
_settings_key_file_cache = None

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
DEFAULT_FUZZY_AI_TOKEN_RANKINGS_FILE = os.path.join(getProjectRoot(), "src", "data", "default_settings", "fuzzy_ai_token_rankings.json")

# Helper functions for common paths
def getProfilesDir():
    """Get the profiles directory path"""
    return os.path.join(getProjectRoot(), "settings", "profiles")

def getProfilePath(profile_name=None):
    """Get the path to a specific profile directory"""
    if profile_name is None:
        profile_name = profileName
    return os.path.join(getProfilesDir(), profile_name)

def getDefaultSettingsPath():
    """Get the path to default settings directory"""
    return os.path.join(getProjectRoot(), "src", "data", "default_settings")

def getSettingsDir():
    """Get the settings directory path"""
    return os.path.join(getProjectRoot(), "settings")

def getPatternsDir():
    """Get the patterns directory path"""
    return os.path.join(getProjectRoot(), "settings", "patterns")

def getFuzzyAIModelPath(model_filename):
    """Get the fixed fuzzy AI model path under src/data/models."""
    return os.path.join(getProjectRoot(), "src", "data", "models", model_filename)

def resolveProjectPath(path_value):
    """Resolve a path relative to the project root."""
    if path_value is None:
        return None

    path_text = str(path_value).strip()
    if not path_text:
        return None

    if os.path.isabs(path_text):
        return os.path.normpath(path_text)

    return os.path.normpath(os.path.join(getProjectRoot(), path_text))

def loadDefaultFields():
    """Load default field settings from the bundled defaults."""
    defaults_path = os.path.join(getDefaultSettingsPath(), "fields.txt")
    with open(defaults_path) as f:
        out = ast.literal_eval(f.read())
    return out

def _stripAIGatherFieldKeys(settings):
    if not isinstance(settings, dict):
        return {}
    return {key: value for key, value in settings.items() if not str(key).startswith("fuzzy_ai_")}

def normalizeFieldSettings(field_name, settings, default_fields=None):
    """Merge bundled defaults into a field settings object."""
    if default_fields is None:
        default_fields = loadDefaultFields()

    normalized = {}

    default_field_settings = default_fields.get(field_name)
    if isinstance(default_field_settings, dict):
        normalized.update(_stripAIGatherFieldKeys(default_field_settings))

    if isinstance(settings, dict):
        normalized.update(_stripAIGatherFieldKeys(settings))

    return normalized

def _tokenRankingDefaults():
    return {
        "preferred_tokens": DEFAULT_FUZZY_AI_TOKEN_RANKING["preferred_tokens"],
        "ignored_tokens": DEFAULT_FUZZY_AI_TOKEN_RANKING["ignored_tokens"],
    }

def loadFuzzyAITokenRankings():
    """Load per-field AI Gathering token rankings from src/data/user."""
    for path in (FUZZY_AI_TOKEN_RANKINGS_FILE, DEFAULT_FUZZY_AI_TOKEN_RANKINGS_FILE):
        try:
            if os.path.exists(path):
                with open(path, "r") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception as e:
            print(f"Warning: Could not load AI token rankings from {path}: {e}")
    return {}

def saveFuzzyAITokenRankings(data):
    os.makedirs(os.path.dirname(FUZZY_AI_TOKEN_RANKINGS_FILE), exist_ok=True)
    with open(FUZZY_AI_TOKEN_RANKINGS_FILE, "w") as f:
        json.dump(data, f, indent=2)

def loadFuzzyAITokenRanking(field_name):
    rankings = loadFuzzyAITokenRankings()
    ranking = rankings.get(field_name, {})
    defaults = _tokenRankingDefaults()
    if not isinstance(ranking, dict):
        ranking = {}
    return {
        "preferred_tokens": ranking.get("preferred_tokens") or defaults["preferred_tokens"],
        "ignored_tokens": ranking.get("ignored_tokens") or defaults["ignored_tokens"],
    }

def saveFuzzyAITokenRanking(field_name, ranking):
    rankings = loadFuzzyAITokenRankings()
    current = loadFuzzyAITokenRanking(field_name)
    if isinstance(ranking, dict):
        current["preferred_tokens"] = str(ranking.get("preferred_tokens", current["preferred_tokens"]))
        current["ignored_tokens"] = str(ranking.get("ignored_tokens", current["ignored_tokens"]))
    rankings[field_name] = current
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
    settings_file = os.path.join(profile_path, "settings.txt")
    fields_file = os.path.join(profile_path, "fields.txt")
    generalsettings_file = os.path.join(profile_path, "generalsettings.txt")

    if not os.path.exists(settings_file):
        return False, f"Profile '{name}' is missing settings.txt file"

    if not os.path.exists(fields_file):
        return False, f"Profile '{name}' is missing fields.txt file"

    if not os.path.exists(generalsettings_file):
        return False, f"Profile '{name}' is missing generalsettings.txt file"

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
    """Create a new profile using default settings from settings/defaults/"""
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

        # Copy default profile settings (fields.txt and settings.txt)
        default_profile_path = os.path.join(getProjectRoot(), "settings", "defaults", "profiles", "a")
        if os.path.exists(default_profile_path):
            for file_name in ["fields.txt", "settings.txt"]:
                src_file = os.path.join(default_profile_path, file_name)
                dst_file = os.path.join(new_profile_path, file_name)
                if os.path.exists(src_file):
                    shutil.copy2(src_file, dst_file)

        # Copy default generalsettings.txt
        default_generalsettings = os.path.join(getProjectRoot(), "settings", "defaults", "generalsettings.txt")
        if os.path.exists(default_generalsettings):
            dst_generalsettings = os.path.join(new_profile_path, "generalsettings.txt")
            shutil.copy2(default_generalsettings, dst_generalsettings)

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
        out[k] = _parseSettingValue(v)
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

def _chooseRepairValue(existing_value, incoming_value, default_value):
    """Prefer explicit user values over defaults when repairing misplaced keys."""
    if existing_value is None:
        return incoming_value
    if existing_value == incoming_value:
        return existing_value
    if existing_value == default_value and incoming_value != default_value:
        return incoming_value
    return existing_value

def _getDefaultSettingsKeySets():
    """Return known keys for profile and general settings defaults."""
    global _settings_key_file_cache

    if _settings_key_file_cache is not None:
        return _settings_key_file_cache

    profile_keys = set()
    general_keys = set()

    try:
        profile_keys = set(readSettingsFile(os.path.join(getDefaultSettingsPath(), "settings.txt")).keys())
    except Exception:
        pass

    try:
        general_keys = set(readSettingsFile(os.path.join(getDefaultSettingsPath(), "generalsettings.txt")).keys())
    except Exception:
        pass

    _settings_key_file_cache = {
        "profile": profile_keys,
        "general": general_keys,
    }
    return _settings_key_file_cache

def _resolveSettingsFileType(setting, requested_type):
    """Prefer the file that owns this setting in defaults, falling back to the requested type."""
    key_sets = _getDefaultSettingsKeySets()

    if setting in key_sets["profile"] and setting not in key_sets["general"]:
        return "profile"
    if setting in key_sets["general"] and setting not in key_sets["profile"]:
        return "general"
    return requested_type

def saveDict(path, data):
    out = "\n".join([f"{k}={v}" for k,v in data.items()])
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

def _getDefaultProfileFieldsPath():
    return os.path.join(getProjectRoot(), "settings", "defaults", "profiles", "a", "fields.txt")

def _readFieldsFile(fields_path):
    with open(fields_path) as f:
        return ast.literal_eval(f.read())

def _repairFieldsData(fields_data, default_fields):
    repaired = _coerceNestedValues(fields_data)
    updated = False

    for field_name, default_field_settings in default_fields.items():
        if field_name not in repaired or not isinstance(repaired[field_name], dict):
            repaired[field_name] = dict(default_field_settings)
            updated = True
            continue

        field_settings = repaired[field_name]
        for key, default_value in default_field_settings.items():
            if key not in field_settings:
                field_settings[key] = default_value
                updated = True

    return repaired, updated

def _loadFieldsFile(fields_path, repair=True):
    fields_data = _readFieldsFile(fields_path)
    if not repair:
        return _coerceNestedValues(fields_data)

    try:
        default_fields = _readFieldsFile(_getDefaultProfileFieldsPath())
    except Exception:
        default_fields = {}

    fields_data, updated = _repairFieldsData(fields_data, default_fields)
    if updated:
        with open(fields_path, "w") as f:
            f.write(str(fields_data))
    return fields_data

def loadFields():
    fields_path = os.path.join(getProfilePath(), "fields.txt")
    out = _loadFieldsFile(fields_path)

    default_fields = loadDefaultFields()
    fieldsUpdated = False
    for field, settings in out.items():
        normalized = normalizeFieldSettings(field, settings, default_fields)
        if normalized != settings:
            out[field] = normalized
            fieldsUpdated = True

    if fieldsUpdated:
        with open(fields_path, "w") as f:
            f.write(str(out))

    return out

def saveField(field, settings):
    fieldsData = loadFields()
    fieldsData[field] = normalizeFieldSettings(field, settings)
    fields_path = os.path.join(getProfilePath(), "fields.txt")
    with open(fields_path, "w") as f:
        f.write(str(fieldsData))
    f.close()

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

        if settings.get("shape") == "fuzzy_ai_gather":
            blue_model = getFuzzyAIModelPath("blue.onnx")
            sprinkler_model = getFuzzyAIModelPath("sprinkler.onnx")
            if not os.path.exists(blue_model):
                warnings.append("Missing blue model: src/data/models/blue.onnx")
            if not os.path.exists(sprinkler_model):
                warnings.append("Missing sprinkler model: src/data/models/sprinkler.onnx")

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

def syncFieldSettings(setting, value):
    """Synchronize field settings from profile to general settings"""
    try:
        # Update the general settings file
        generalSettingsPath = os.path.join(getProfilePath(), "generalsettings.txt")
        generalData = readSettingsFile(generalSettingsPath)
        generalData[setting] = value
        saveDict(generalSettingsPath, generalData)
    except Exception as e:
        print(f"Warning: Could not sync field settings to general settings: {e}")

def syncFieldSettingsToProfile(setting, value):
    """Synchronize field settings from general to profile settings"""
    try:
        # Update the profile settings file
        profileSettingsPath = os.path.join(getProfilePath(), "settings.txt")
        profileData = readSettingsFile(profileSettingsPath)
        profileData[setting] = value
        saveDict(profileSettingsPath, profileData)
    except Exception as e:
        print(f"Warning: Could not sync field settings to profile settings: {e}")

def saveProfileSetting(setting, value):
    if _resolveSettingsFileType(setting, "profile") == "general":
        saveGeneralSetting(setting, value)
        return

    settings_path = os.path.join(getProfilePath(), "settings.txt")
    saveSettingFile(setting, value, settings_path)
    # Synchronize field settings with general settings
    if setting in ["fields", "fields_enabled"]:
        syncFieldSettings(setting, value)

def saveDictProfileSettings(dict):
    settings_path = os.path.join(getProfilePath(), "settings.txt")
    saveDict(settings_path, {**readSettingsFile(settings_path), **dict})

#increment a setting, and return the dictionary for the setting
def incrementProfileSetting(setting, incrValue):
    #get the dictionary
    settings_path = os.path.join(getProfilePath(), "settings.txt")
    data = readSettingsFile(settings_path)
    #update the dictionary
    data[setting] += incrValue
    #write it
    saveDict(settings_path, data)
    return data

def saveGeneralSetting(setting, value):
    if _resolveSettingsFileType(setting, "general") == "profile":
        saveProfileSetting(setting, value)
        return

    generalsettings_path = os.path.join(getProfilePath(), "generalsettings.txt")
    saveSettingFile(setting, value, generalsettings_path)
    # Synchronize field settings with profile settings
    if setting in ["fields", "fields_enabled"]:
        syncFieldSettingsToProfile(setting, value)

def removeGeneralSetting(setting):
    generalsettings_path = os.path.join(getProfilePath(), "generalsettings.txt")
    removeSettingFile(setting, generalsettings_path)

def _moveMisplacedSettings(settings_path, generalsettings_path):
    """Move settings written to the wrong file back to their expected owner."""
    key_sets = _getDefaultSettingsKeySets()
    default_profile_settings = {}
    default_general_settings = {}

    try:
        default_profile_settings = readSettingsFile(os.path.join(getDefaultSettingsPath(), "settings.txt"))
    except Exception:
        pass

    try:
        default_general_settings = readSettingsFile(os.path.join(getDefaultSettingsPath(), "generalsettings.txt"))
    except Exception:
        pass

    changed = False

    try:
        settings_data = readSettingsFile(settings_path)
    except FileNotFoundError:
        settings_data = dict(default_profile_settings)
        changed = True

    try:
        general_data = readSettingsFile(generalsettings_path)
    except FileNotFoundError:
        general_data = dict(default_general_settings)
        changed = True

    for key in list(general_data.keys()):
        if key not in key_sets["profile"] or key in key_sets["general"]:
            continue
        moved_value = general_data.pop(key)
        settings_data[key] = _chooseRepairValue(
            settings_data.get(key),
            moved_value,
            default_profile_settings.get(key),
        )
        changed = True

    for key in list(settings_data.keys()):
        if key not in key_sets["general"] or key in key_sets["profile"]:
            continue
        moved_value = settings_data.pop(key)
        general_data[key] = _chooseRepairValue(
            general_data.get(key),
            moved_value,
            default_general_settings.get(key),
        )
        changed = True

    for key, value in default_profile_settings.items():
        if key not in settings_data:
            settings_data[key] = value
            changed = True

    for key, value in default_general_settings.items():
        if key not in general_data:
            general_data[key] = value
            changed = True

    if changed:
        saveDict(settings_path, settings_data)
        saveDict(generalsettings_path, general_data)

def loadSettings():
    settings_path = os.path.join(getProfilePath(), "settings.txt")
    generalsettings_path = os.path.join(getProfilePath(), "generalsettings.txt")
    default_settings_path = os.path.join(getDefaultSettingsPath(), "settings.txt")
    _moveMisplacedSettings(settings_path, generalsettings_path)
    # Read the profile settings if present (capture raw profile to detect legacy keys)
    try:
        profile_raw = readSettingsFile(settings_path)
        settings = profile_raw.copy()
    except FileNotFoundError:
        profile_raw = {}
        print(f"Warning: Profile '{profileName}' settings file not found, using defaults")
        # Fall back to default settings if profile file is missing
        settings = readSettingsFile(default_settings_path)

    # Read default settings and ensure profile contains any missing keys
    defaultSettings = readSettingsFile(default_settings_path)
    merged_new_keys = False
    for k, v in defaultSettings.items():
        if k not in settings:
            settings[k] = v
            merged_new_keys = True

    # Migrate legacy global quest gather override to per-quest keys on first load
    try:
        legacy_present = any(k in profile_raw for k in ("quest_gather_mins", "quest_gather_return"))
        if legacy_present:
            legacy_mins = profile_raw.get("quest_gather_mins", None)
            legacy_return = profile_raw.get("quest_gather_return", None)
            # Only migrate if legacy values differ from defaults (i.e., the user had configured them)
            default_mins = defaultSettings.get("quest_gather_mins")
            default_return = defaultSettings.get("quest_gather_return")
            do_migrate = False
            if legacy_mins is not None and legacy_mins != default_mins:
                do_migrate = True
            if legacy_return is not None and legacy_return != default_return:
                do_migrate = True

            if do_migrate:
                per_quests = ["polar_bear", "brown_bear", "black_bear", "honey_bee", "bucko_bee", "riley_bee"]
                for q in per_quests:
                    mins_key = f"{q}_quest_gather_mins"
                    return_key = f"{q}_quest_gather_return"
                    if legacy_mins is not None:
                        settings[mins_key] = legacy_mins
                    if legacy_return is not None:
                        settings[return_key] = legacy_return
                # Remove old global keys so migration happens only once
                if "quest_gather_mins" in settings:
                    del settings["quest_gather_mins"]
                if "quest_gather_return" in settings:
                    del settings["quest_gather_return"]
                merged_new_keys = True
    except Exception:
        # If migration fails for any reason, skip without blocking startup
        pass

    # Ensure fields and fields_enabled arrays have 5 elements
    defaultFields = defaultSettings.get("fields", ['pine tree', 'sunflower', 'dandelion', 'pine tree', 'sunflower'])
    defaultFieldsEnabled = defaultSettings.get("fields_enabled", [True, False, False, False, False])
    
    fields = settings.get("fields", [])
    fieldsEnabled = settings.get("fields_enabled", [])
    
    # Extend arrays to 5 elements if needed
    updated = False
    while len(fields) < 5:
        fields.append(defaultFields[len(fields)] if len(fields) < len(defaultFields) else defaultFields[-1])
        updated = True
    while len(fieldsEnabled) < 5:
        fieldsEnabled.append(defaultFieldsEnabled[len(fieldsEnabled)] if len(fieldsEnabled) < len(defaultFieldsEnabled) else False)
        updated = True

    if updated:
        settings["fields"] = fields
        settings["fields_enabled"] = fieldsEnabled

    # Persist settings if we added default keys or extended arrays
    if merged_new_keys or updated:
        try:
            saveDict(settings_path, settings)
        except Exception:
            pass

    return settings

#return a dict containing all settings except field (general, profile, planters)
def loadAllSettings():
    # Ensure current profile is reloaded from persistent storage so other processes
    # (like the Discord bot) can change the active profile and have the main
    # GUI process pick it up immediately.
    try:
        loadCurrentProfile()
    except Exception:
        pass

    # Auto-migrate profiles to have their own generalsettings.txt files
    migrateProfilesToGeneralSettings()

    generalsettings_path = os.path.join(getProfilePath(), "generalsettings.txt")
    settings_path = os.path.join(getProfilePath(), "settings.txt")
    _moveMisplacedSettings(settings_path, generalsettings_path)
    try:
        generalSettings = readSettingsFile(generalsettings_path)
    except FileNotFoundError:
        print(f"Warning: Profile '{profileName}' generalsettings file not found, using defaults")
        generalSettings = readSettingsFile(os.path.join(getDefaultSettingsPath(), "generalsettings.txt"))

    # Merge any new default general settings keys into the profile.
    general_defaults_path = os.path.join(getDefaultSettingsPath(), "generalsettings.txt")
    merged_general_keys = False
    try:
        defaultGeneralSettings = readSettingsFile(general_defaults_path)
        for k, v in defaultGeneralSettings.items():
            if k not in generalSettings:
                generalSettings[k] = v
                merged_general_keys = True
    except Exception:
        pass

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
            saveDict(generalsettings_path, generalSettings)
            print("Migrated old field_only_mode/quest_only_mode settings to new macro_mode setting")

    if merged_general_keys:
        try:
            saveDict(generalsettings_path, generalSettings)
        except Exception:
            pass

    return {**loadSettings(), **generalSettings}

def initializeFieldSync():
    """Initialize field synchronization between profile and general settings"""
    try:
        settings_path = os.path.join(getProfilePath(), "settings.txt")
        generalsettings_path = os.path.join(getProfilePath(), "generalsettings.txt")
        try:
            profileData = readSettingsFile(settings_path)
        except FileNotFoundError:
            print(f"Warning: Profile '{profileName}' settings file not found during sync, skipping")
            return

        generalData = readSettingsFile(generalsettings_path)

        # Check if field settings exist in both files
        profileFields = profileData.get("fields", [])
        generalFields = generalData.get("fields", [])

        # If general settings has different fields, sync from profile to general
        if profileFields != generalFields and profileFields:
            generalData["fields"] = profileFields
            saveDict(generalsettings_path, generalData)

        # Sync fields_enabled as well
        profileFieldsEnabled = profileData.get("fields_enabled", [])
        generalFieldsEnabled = generalData.get("fields_enabled", [])

        if profileFieldsEnabled != generalFieldsEnabled and profileFieldsEnabled:
            generalData["fields_enabled"] = profileFieldsEnabled
            saveDict(generalsettings_path, generalData)
            
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
        settings_file = os.path.join(profile_path, "settings.txt")
        fields_file = os.path.join(profile_path, "fields.txt")
        generalsettings_file = os.path.join(profile_path, "generalsettings.txt")

        if not os.path.exists(settings_file) or not os.path.exists(fields_file) or not os.path.exists(generalsettings_file):
            return False, f"Profile '{profile_name}' is missing required files"

        _moveMisplacedSettings(settings_file, generalsettings_file)
        settings_data = readSettingsFile(settings_file)
        fields_data = loadFields() if profile_name == getCurrentProfile() else _loadFieldsFile(fields_file)
        generalsettings_data = readSettingsFile(generalsettings_file)

        # Ensure sensitive fields are removed from export
        sensitive_keys = ("discord_bot_token", "webhook_link", "private_server_link")
        for k in sensitive_keys:
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

        return True, f"Profile imported successfully as '{new_profile_name}'"

    except Exception as e:
        return False, f"Failed to import profile: {str(e)}"

# Load the current profile when the module is imported
loadCurrentProfile()

#clear a file
def clearFile(filePath):
    open(filePath, 'w').close()

def migrateProfilesToGeneralSettings():
    """Migrate existing profiles to have their own generalsettings.txt files"""
    profiles_dir = getProfilesDir()
    global_generalsettings = os.path.join(getSettingsDir(), "generalsettings.txt")

    # Check if global generalsettings exists - if not, migration is already complete
    if not os.path.exists(global_generalsettings):
        return

    if not os.path.exists(profiles_dir):
        return

    # Read global generalsettings
    try:
        global_data = readSettingsFile(global_generalsettings)
    except FileNotFoundError:
        print("Warning: Global generalsettings.txt not found, cannot migrate profiles")
        return

    migration_performed = False

    # Iterate through all profiles
    for profile_name in listProfiles():
        profile_path = os.path.join(profiles_dir, profile_name)
        generalsettings_file = os.path.join(profile_path, "generalsettings.txt")

        # Skip if profile already has generalsettings.txt
        if os.path.exists(generalsettings_file):
            continue

        # Copy global generalsettings to profile
        try:
            shutil.copy2(global_generalsettings, generalsettings_file)
            print(f"Migrated generalsettings.txt for profile: {profile_name}")
            migration_performed = True
        except Exception as e:
            print(f"Warning: Failed to migrate generalsettings.txt for profile '{profile_name}': {e}")

    # Only print completion message and delete old file if migration was actually performed
    if migration_performed:
        print("Profile migration completed")

        # Delete the old global generalsettings file since all profiles now have their own copies
        try:
            os.remove(global_generalsettings)
            print("Removed old global generalsettings.txt file")
        except Exception as e:
            print(f"Warning: Failed to remove old global generalsettings.txt file: {e}")
