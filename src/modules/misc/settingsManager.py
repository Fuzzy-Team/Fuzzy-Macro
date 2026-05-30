import ast
import os
import shutil
import json
import zipfile
import tempfile
from datetime import datetime
import re

FUZZY_AI_RUNTIME_DEFAULTS = {
    "fuzzy_ai_confidence_threshold": 0.3,
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
    "fuzzy_ai_debug_mode": None,
    "fuzzy_ai_record_video": None,
    "fuzzy_ai_record_video_fps": None,
}

DEFAULT_FUZZY_AI_TOKEN_RANKING = {
    "preferred_tokens": "Token Link,Focus,Melody,Blue Boost,Honey Mark Station,Honey Mark Token,Pollen Mark Station,Pollen Mark Token,Haste",
    "ignored_tokens": "Honey Token,Blueberry,Bloom,Duped Baby Love,Duped Beamstorm,Duped Beesmas Cheer Token,Duped Black Bear Morph,Duped Blue Bomb Sync,Duped Blue Boost,Duped Blueberry,Duped Bomb,Duped Brown Bear Morph,Duped Festive Blessing Token,Duped Festive Gift Token,Duped Festive Mark Token,Duped Fetch,Duped Flame Fuel,Duped Focus,Duped Fuzz Bombs Token,Duped Glitch Token,Duped Glob,Duped Gumdrop Barrage,Duped Haste,Duped Honey Mark Token,Duped Honey Token,Duped Impale,Duped Inferno Token,Duped Inflate Balloons,Duped Inspire Token,Duped Jelly Bean,Duped Map Corruption,Duped Mark Surge Token,Duped Melody,Duped Mind Hack,Duped Mother Bear Morph,Duped Panda Bear Morph,Duped Pineapple,Duped Polar Bear Morph,Duped Pollen Haze,Duped Pollen Mark Token,Duped Pulse,Duped Puppy Love,Duped Rage Token,Duped Rain Cloud,Duped Red Bomb Sync,Duped Red Boost,Duped Science Bear Morph,Duped Scratch,Duped Snowflake,Duped Snowglobe Shake,Duped Strawberry,Duped Summon Frog Token,Duped Sunflower Seed,Duped Surprise Party,Duped Tabby Love,Duped Target Practice Token,Duped Token Link,Duped Tornado,Duped Treat,Duped Triangulate Token,Duped White Boost",
}
FIELD_PATTERN_PRESETS_KEY = "pattern_presets"

#returns a dictionary containing the settings
profileName = "a"
# Track profile changes for running macro processes
_profile_change_counter = 0
_settings_key_file_cache = None

# File to store current profile persistence (defined after getProjectRoot)
CURRENT_PROFILE_FILE = None

def _readLegacyCurrentProfile():
    for path in (CURRENT_PROFILE_FILE, f"{CURRENT_PROFILE_FILE}.bak"):
        try:
            if path and os.path.exists(path):
                with open(path, "r") as f:
                    saved_profile = f.read().strip()
                if saved_profile and os.path.exists(getProfilePath(saved_profile)):
                    return saved_profile, path
        except Exception:
            pass
    return None, None

def loadCurrentProfile():
    """Load the current profile from persistent storage"""
    global profileName
    try:
        saved_profile, legacy_path = _readLegacyCurrentProfile()
        if saved_profile:
            profileName = saved_profile
            saveCurrentProfile()
            if legacy_path == CURRENT_PROFILE_FILE:
                backup_legacy_file(CURRENT_PROFILE_FILE)
            return

        app_state = read_json_file(APP_STATE_FILE, {}) if APP_STATE_FILE else {}
        saved_profile = app_state.get("current_profile") if isinstance(app_state, dict) else None
        if saved_profile and os.path.exists(getProfilePath(saved_profile)):
            profileName = saved_profile
            return
    except Exception as e:
        print(f"Warning: Could not load current profile: {e}")

def saveCurrentProfile():
    """Save the current profile to persistent storage"""
    try:
        write_json_atomic(APP_STATE_FILE, {
            "schema_version": 1,
            "current_profile": profileName,
        })
    except Exception as e:
        print(f"Warning: Could not save current profile: {e}")

# Load the current profile when the module is imported (called at the end of the file)

# Get the project root directory (4 levels up from this file: src/modules/misc/settingsManager.py)
def getProjectRoot():
    """Get the project root directory path"""
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# File to store current profile persistence
CURRENT_PROFILE_FILE = os.path.join(getProjectRoot(), "src", "data", "user", "current_profile.txt")
APP_STATE_FILE = os.path.join(getProjectRoot(), "src", "data", "user", "app_state.json")
RUNTIME_STATE_FILE = os.path.join(getProjectRoot(), "src", "data", "user", "runtime_state.json")
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

def getProfileJsonPath(profile_name=None):
    return os.path.join(getProfilePath(profile_name), "profile.json")

def getFieldsJsonPath(profile_name=None):
    return os.path.join(getProfilePath(profile_name), "fields.json")

def getMigrationLogPath(profile_name=None):
    return os.path.join(getProfilePath(profile_name), "migration_log.json")

def getRuntimeStateJsonPath(profile_name=None):
    return os.path.join(getProfilePath(profile_name), "runtime_state.json")

def getProfileUserDataDir(profile_name=None):
    return os.path.join(getProfilePath(profile_name), "user_data")

def getProfileUserDataPath(filename, profile_name=None):
    return os.path.join(getProfileUserDataDir(profile_name), filename)

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

def _runtimeStateDefault():
    return {
        "schema_version": 1,
        "timings": {},
        "auto_gifted_basic_bee": {},
        "hotbar": {},
        "hotbar_buff_tool": {},
        "sticker_stack": {},
        "blender": {},
        "hourly_report": {},
    }

def _defaultAutoPlanterUserData():
    fields = [
        "dandelion", "bamboo", "pine tree", "mushroom", "spider", "stump",
        "rose", "sunflower", "pineapple", "pumpkin", "blue flower",
        "strawberry", "coconut", "clover", "cactus", "mountain top", "pepper"
    ]
    return {
        "planters": [
            {
                "planter": "",
                "nectar": "",
                "field": "",
                "harvest_time": 0,
                "nectar_est_percent": 0,
                "placed_time": 0,
                "grow_duration": 0,
                "natural_grow_duration": 0,
            }
            for _ in range(3)
        ],
        "nectar_last_field": {
            "comforting": "",
            "refreshing": "",
            "satisfying": "",
            "motivating": "",
            "invigorating": "",
        },
        "gather": False,
        "field_degradation": {
            field: {"hours": 0.0, "updated_at": 0.0}
            for field in fields
        },
    }

def _defaultProfileDocument():
    return {
        "schema_version": 1,
        "profile_settings": _readLegacySettingsFile(os.path.join(getDefaultSettingsPath(), "settings.txt")),
        "general_settings": _readLegacySettingsFile(os.path.join(getDefaultSettingsPath(), "generalsettings.txt")),
    }

def _defaultFieldsDocument():
    return {
        "schema_version": 1,
        "fields": loadDefaultFields(),
    }

def read_json_file(path, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except Exception:
        return default

def write_json_atomic(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp_path, path)

def backup_legacy_file(path):
    if not os.path.exists(path):
        return
    backup_dir = os.path.join(getProjectRoot(), "src", "data", "legacy_user_backups")
    os.makedirs(backup_dir, exist_ok=True)

    rel = _project_relative_path(path).replace("\\", "/")
    safe_name = rel.replace("/", "__")
    target = os.path.join(backup_dir, safe_name)
    if os.path.exists(target):
        root, ext = os.path.splitext(safe_name)
        suffix = datetime.now().strftime("%Y%m%d_%H%M%S")
        target = os.path.join(backup_dir, f"{root}.{suffix}{ext}")
    os.replace(path, target)

def _project_relative_path(path):
    abs_path = os.path.abspath(path)
    try:
        return os.path.relpath(abs_path, getProjectRoot())
    except Exception:
        return abs_path

def coerce_setting_value(value):
    if isinstance(value, str):
        stripped = value.strip()
        if stripped in ("True", "False"):
            return stripped == "True"
        return _parseSettingValue(stripped)
    if isinstance(value, dict):
        return {k: coerce_setting_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [coerce_setting_value(v) for v in value]
    return value

def load_legacy_key_value_file(path):
    return _readLegacySettingsFile(path)

def load_legacy_python_literal_file(path):
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read().strip()
    if not raw:
        return {}
    return ast.literal_eval(raw)

def _readLegacySettingsFile(path):
    with open(path) as f:
        raw = f.read()

    raw = re.sub(r'(?<!\n)max_convert_time=', r'\nmax_convert_time=', raw)
    data = [[x.strip() for x in y.split("=", 1)] for y in raw.split("\n") if y and "=" in y]
    out = {}
    for k, v in data:
        out[k] = _parseSettingValue(v)
    return out

def _getProfileDocument(profile_name=None):
    profile_path = getProfileJsonPath(profile_name)
    data = read_json_file(profile_path)
    if not isinstance(data, dict):
        return None
    data.setdefault("schema_version", 1)
    data.setdefault("profile_settings", {})
    data.setdefault("general_settings", {})
    return data

def _loadProfileDocument(profile_name=None):
    data = _getProfileDocument(profile_name)
    if data is not None:
        return data

    name = profile_name if profile_name is not None else profileName
    return _buildProfileDocumentFromLegacy(name)[0]

def _saveProfileDocument(data, profile_name=None):
    data = {
        "schema_version": int(data.get("schema_version", 1) or 1),
        "profile_settings": dict(data.get("profile_settings", {}) or {}),
        "general_settings": dict(data.get("general_settings", {}) or {}),
    }
    write_json_atomic(getProfileJsonPath(profile_name), data)

def _loadFieldsDocument(profile_name=None):
    data = read_json_file(getFieldsJsonPath(profile_name))
    if isinstance(data, dict) and isinstance(data.get("fields"), dict):
        data.setdefault("schema_version", 1)
        return data

    name = profile_name if profile_name is not None else profileName
    default_fields = _readFieldsFile(_getDefaultProfileFieldsPath())
    legacy_path = os.path.join(getProfilePath(name), "fields.txt")
    try:
        fields = load_legacy_python_literal_file(legacy_path)
    except Exception:
        fields = {}
    fields, _ = _repairFieldsData(fields, default_fields)
    return {"schema_version": 1, "fields": fields}

def _saveFieldsDocument(fields, profile_name=None):
    write_json_atomic(getFieldsJsonPath(profile_name), {
        "schema_version": 1,
        "fields": fields,
    })

def _runtimeSectionForPath(path):
    rel = _project_relative_path(path).replace("\\", "/")
    mapping = {
        "src/data/user/timings.txt": "timings",
        "src/data/user/AFB.txt": "auto_gifted_basic_bee",
        "src/data/user/hotbar_timings.txt": "hotbar",
        "src/data/user/hotbar_buff_tool_timings.txt": "hotbar_buff_tool",
        "src/data/user/sticker_stack.txt": "sticker_stack",
        "src/data/user/blender.txt": "blender",
        "src/data/user/hourly_report_main.txt": "hourly_report",
        "src/data/user/hourly_report_bg.txt": "hourly_report",
    }
    if rel.startswith("data/user/"):
        rel = f"src/{rel}"
    return mapping.get(rel)

def _loadRuntimeState():
    state = read_json_file(getRuntimeStateJsonPath())
    if not isinstance(state, dict):
        state = _runtimeStateDefault()
    default_state = _runtimeStateDefault()
    for key, value in default_state.items():
        if key not in state:
            state[key] = value
    for key in default_state:
        if key != "schema_version" and not isinstance(state.get(key), dict):
            state[key] = {}
    state["schema_version"] = 1
    return state

def _saveRuntimeState(state):
    write_json_atomic(getRuntimeStateJsonPath(), state)

def readProfileUserJson(filename, default=None, profile_name=None):
    return read_json_file(getProfileUserDataPath(filename, profile_name), default)

def writeProfileUserJson(filename, data, profile_name=None):
    write_json_atomic(getProfileUserDataPath(filename, profile_name), data)

def _jsonUserDataName(filename):
    mapping = {
        "screen.txt": "screen.json",
        "manualplanters.txt": "manualplanters.json",
        "blender.txt": "blender.json",
        "sticker_stack.txt": "sticker_stack.json",
        "hotbar_timings.txt": "hotbar_timings.json",
        "hotbar_buff_tool_timings.txt": "hotbar_buff_tool_timings.json",
        "hourly_report_history.txt": "hourly_report_history.json",
    }
    return mapping.get(filename, filename)

def readProfileUserData(filename, default=None, profile_name=None):
    return readProfileUserJson(_jsonUserDataName(filename), default, profile_name)

def writeProfileUserData(filename, data, profile_name=None):
    writeProfileUserJson(_jsonUserDataName(filename), data, profile_name)

def readProfileUserLiteral(filename, default=None, profile_name=None):
    path = getProfileUserDataPath(filename, profile_name)
    try:
        return load_legacy_python_literal_file(path)
    except Exception:
        return default

def writeProfileUserLiteral(filename, data, profile_name=None):
    path = getProfileUserDataPath(filename, profile_name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(str(data))

def clearProfileUserFile(filename, profile_name=None):
    path = getProfileUserDataPath(filename, profile_name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w").close()

def _readRuntimeSection(section):
    state = _loadRuntimeState()
    return dict(state.get(section, {}) or {})

def _writeRuntimeSection(section, data):
    state = _loadRuntimeState()
    state[section] = dict(data or {})
    _saveRuntimeState(state)

def _settingOwner(setting, requested_type):
    return _resolveSettingsFileType(setting, requested_type)

def _isApprovedUnknownSetting(key):
    key = str(key)
    return (
        key.startswith("ping_")
        or key.startswith("cycle")
        or key.startswith("auto_planter_")
        or key.startswith("auto_field_")
        or key.startswith("planter_hotbar_")
    )

def _chooseMigrationValue(correct_value, misplaced_value, default_value, log, key):
    if correct_value is None:
        return misplaced_value
    if correct_value == misplaced_value:
        return correct_value
    if correct_value == default_value and misplaced_value != default_value:
        return misplaced_value
    if misplaced_value == default_value:
        return correct_value
    log.setdefault("conflicts", {})[key] = {
        "kept": correct_value,
        "discarded": misplaced_value,
    }
    return correct_value

def _buildProfileDocumentFromLegacy(profile_name):
    settings_path = os.path.join(getProfilePath(profile_name), "settings.txt")
    general_path = os.path.join(getProfilePath(profile_name), "generalsettings.txt")
    default_profile = _readLegacySettingsFile(os.path.join(getDefaultSettingsPath(), "settings.txt"))
    default_general = _readLegacySettingsFile(os.path.join(getDefaultSettingsPath(), "generalsettings.txt"))
    profile_keys = set(default_profile.keys())
    general_keys = set(default_general.keys())
    log = {
        "schema_version": 1,
        "migrated_at": datetime.now().isoformat(),
        "moved_settings": [],
        "missing_defaults": [],
        "unknown_settings": {},
        "conflicts": {},
        "dropped_runtime_keys": {},
        "errors": [],
    }

    try:
        legacy_profile = _readLegacySettingsFile(settings_path)
    except Exception as e:
        legacy_profile = {}
        log["errors"].append(f"Could not read settings.txt: {e}")

    try:
        legacy_general = _readLegacySettingsFile(general_path)
    except Exception as e:
        legacy_general = {}
        log["errors"].append(f"Could not read generalsettings.txt: {e}")

    profile_settings = {}
    general_settings = {}

    for key, value in legacy_profile.items():
        value = coerce_setting_value(value)
        if key in profile_keys or (key not in general_keys and _isApprovedUnknownSetting(key)):
            profile_settings[key] = value
        elif key in general_keys:
            general_settings[key] = _chooseMigrationValue(
                general_settings.get(key), value, default_general.get(key), log, key
            )
            log["moved_settings"].append({"key": key, "from": "settings.txt", "to": "general_settings"})
        else:
            log["unknown_settings"][key] = {"source": "settings.txt", "value": value}

    for key, value in legacy_general.items():
        value = coerce_setting_value(value)
        if key in general_keys or (key not in profile_keys and _isApprovedUnknownSetting(key)):
            general_settings[key] = _chooseMigrationValue(
                general_settings.get(key), value, default_general.get(key), log, key
            )
        elif key in profile_keys:
            profile_settings[key] = _chooseMigrationValue(
                profile_settings.get(key), value, default_profile.get(key), log, key
            )
            log["moved_settings"].append({"key": key, "from": "generalsettings.txt", "to": "profile_settings"})
        else:
            log["unknown_settings"][key] = {"source": "generalsettings.txt", "value": value}

    for key, value in default_profile.items():
        if key not in profile_settings:
            profile_settings[key] = value
            log["missing_defaults"].append({"key": key, "section": "profile_settings"})

    for key, value in default_general.items():
        if key not in general_settings:
            general_settings[key] = value
            log["missing_defaults"].append({"key": key, "section": "general_settings"})

    return {
        "schema_version": 1,
        "profile_settings": profile_settings,
        "general_settings": general_settings,
    }, log

def _normalizeRuntimeTimingKey(section, key, value, log):
    key = str(key)
    known_exact = {
        "rejoin_every", "convert_balloon", "last_booster", "mondo",
        "wealth_clock", "honey_dispenser", "blueberry_dispenser",
        "strawberry_dispenser", "royal_jelly_dispenser", "treat_dispenser",
        "ant_pass_dispenser", "robo_pass_dispenser", "glue_dispenser",
        "stockings", "feast", "gingerbread", "samovar", "snow_machine",
        "lid_art", "candles", "wreath", "gummy_beacon", "sticker_printer",
        "sticker_stack", "stump_snail", "coconut_crab", "king_beetle",
        "tunnel_bear", "memory_match", "mega_memory_match",
        "extreme_memory_match", "winter_memory_match", "night_memory_match",
        "blue_booster", "red_booster", "mountain_booster", "wind_shrine",
        "honeystorm", "AFB_dice_cd", "AFB_glitter_cd", "AFB_limit",
    }
    known_patterns = (
        r"^(ladybug|rhinobeetle|mantis|scorpion|spider|werewolf)_.+",
        r"^(brown_bear|black_bear)_quest_(cd|state)$",
    )
    if section in ("hotbar", "hotbar_buff_tool"):
        return key, _coerceTimingValue(value)
    if key in known_exact or any(re.match(pattern, key) for pattern in known_patterns):
        if key.endswith("_quest_state"):
            return key, 1 if value in (1, True, "1", "True", "true") else 0
        return key, _coerceTimingValue(value)
    log.setdefault("dropped_runtime_keys", {}).setdefault(section, {})[key] = value
    return None, None

def _coerceTimingValue(value):
    try:
        return float(value)
    except Exception:
        return 0

def _normaliseRuntimeSection(section, data, log):
    if not isinstance(data, dict):
        data = {}
    out = {}
    for key, value in data.items():
        normalized_key, normalized_value = _normalizeRuntimeTimingKey(section, key, value, log)
        if normalized_key is not None:
            out[str(normalized_key)] = normalized_value
    if section in ("hotbar", "hotbar_buff_tool"):
        for slot in range(1, 8):
            out.setdefault(str(slot), 0)
    return out

def _loadLegacyRuntimeSection(path, parser):
    if not os.path.exists(path):
        return {}
    try:
        return parser(path)
    except Exception:
        return {}

def _migrateRuntimeState(log, profile_name=None):
    state = _runtimeStateDefault()
    runtime_sources = {
        "timings": (os.path.join(getProjectRoot(), "src", "data", "user", "timings.txt"), _readLegacySettingsFile),
        "auto_gifted_basic_bee": (os.path.join(getProjectRoot(), "src", "data", "user", "AFB.txt"), _readLegacySettingsFile),
        "hotbar": (os.path.join(getProjectRoot(), "src", "data", "user", "hotbar_timings.txt"), load_legacy_python_literal_file),
        "hotbar_buff_tool": (os.path.join(getProjectRoot(), "src", "data", "user", "hotbar_buff_tool_timings.txt"), load_legacy_python_literal_file),
        "sticker_stack": (os.path.join(getProjectRoot(), "src", "data", "user", "sticker_stack.txt"), _readLegacySettingsFile),
        "blender": (os.path.join(getProjectRoot(), "src", "data", "user", "blender.txt"), load_legacy_python_literal_file),
    }
    for section, (path, parser) in runtime_sources.items():
        data = _loadLegacyRuntimeSection(path, parser)
        state[section] = _normaliseRuntimeSection(section, data, log)
    write_json_atomic(getRuntimeStateJsonPath(profile_name), state)
    for path, _parser in runtime_sources.values():
        backup_legacy_file(path)

def _validateAutoPlantersJson(log, profile_name=None):
    path = getProfileUserDataPath("auto_planters.json", profile_name)
    legacy_path = os.path.join(getProjectRoot(), "src", "data", "user", "auto_planters.json")
    if not os.path.exists(path) and os.path.exists(legacy_path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        shutil.copy2(legacy_path, path)
    data = read_json_file(path)
    if not isinstance(data, dict):
        data = {"gather": False, "planters": []}
        log.setdefault("errors", []).append("Recreated invalid auto_planters.json")
    data.setdefault("gather", False)
    if not isinstance(data.get("planters"), list):
        data["planters"] = []
    write_json_atomic(path, data)

def _validateFuzzyAITokenRankingsJson(log, profile_name=None):
    profile_path = getProfileUserDataPath("fuzzy_ai_token_rankings.json", profile_name)
    if not os.path.exists(profile_path) and os.path.exists(FUZZY_AI_TOKEN_RANKINGS_FILE):
        os.makedirs(os.path.dirname(profile_path), exist_ok=True)
        shutil.copy2(FUZZY_AI_TOKEN_RANKINGS_FILE, profile_path)
    data = read_json_file(profile_path, {})
    if not isinstance(data, dict):
        data = {}
        log.setdefault("errors", []).append("Recreated invalid fuzzy_ai_token_rankings.json")
    write_json_atomic(profile_path, data)

def _migrateProfileUserFiles(profile_name, log):
    legacy_dir = os.path.join(getProjectRoot(), "src", "data", "user")
    user_dir = getProfileUserDataDir(profile_name)
    os.makedirs(user_dir, exist_ok=True)
    for filename in (
        "manualplanters.txt",
        "auto_planters.json",
        "blender.txt",
        "sticker_stack.txt",
        "hotbar_timings.txt",
        "hotbar_buff_tool_timings.txt",
        "hourly_report_history.txt",
        "hourly_report_stats.pkl",
        "screen.txt",
        "fuzzy_ai_token_rankings.json",
    ):
        src = os.path.join(legacy_dir, filename)
        dst = os.path.join(user_dir, filename)
        if os.path.exists(src) and not os.path.exists(dst):
            try:
                shutil.copy2(src, dst)
            except Exception as e:
                log.setdefault("errors", []).append(f"Could not migrate {filename}: {e}")

    screenshots_src = os.path.join(legacy_dir, "inventory_screenshots")
    screenshots_dst = os.path.join(user_dir, "inventory_screenshots")
    if os.path.exists(screenshots_src) and not os.path.exists(screenshots_dst):
        try:
            shutil.copytree(screenshots_src, screenshots_dst)
        except Exception as e:
            log.setdefault("errors", []).append(f"Could not migrate inventory_screenshots: {e}")

    _migrateProfileUserTextJson(profile_name, log)

def _migrateProfileUserTextJson(profile_name, log):
    migrations = {
        "screen.txt": ("screen.json", _readLegacySettingsFile, None),
        "manualplanters.txt": ("manualplanters.json", load_legacy_python_literal_file, {}),
        "blender.txt": ("blender.json", load_legacy_python_literal_file, {"item": 1, "collectTime": 0}),
        "sticker_stack.txt": ("sticker_stack.json", _readLegacySettingsFile, {"sticker_stack": 0}),
        "hotbar_timings.txt": ("hotbar_timings.json", load_legacy_python_literal_file, {slot: 0 for slot in range(1, 8)}),
        "hotbar_buff_tool_timings.txt": ("hotbar_buff_tool_timings.json", load_legacy_python_literal_file, {slot: 0 for slot in range(1, 8)}),
        "hourly_report_history.txt": ("hourly_report_history.json", load_legacy_python_literal_file, []),
    }
    for old_name, (new_name, parser, default_value) in migrations.items():
        old_path = getProfileUserDataPath(old_name, profile_name)
        new_path = getProfileUserDataPath(new_name, profile_name)
        if os.path.exists(new_path):
            continue
        data = default_value
        if os.path.exists(old_path):
            try:
                data = parser(old_path)
            except Exception as e:
                log.setdefault("errors", []).append(f"Could not convert {old_name} to JSON: {e}")
        if data is None:
            data = {}
        write_json_atomic(new_path, data)
    for old_name in migrations:
        backup_legacy_file(getProfileUserDataPath(old_name, profile_name))

def _trashLegacyUserDataFiles():
    legacy_dir = os.path.join(getProjectRoot(), "src", "data", "user")
    legacy_basenames = (
        "current_profile.txt",
        "auto_planters.json",
        "blender.txt",
        "fuzzy_ai_token_rankings.json",
        "hotbar_timings.txt",
        "hotbar_buff_tool_timings.txt",
        "sticker_stack.txt",
        "hourly_report_history.txt",
        "hourly_report_stats.pkl",
        "hourly_report_main.txt",
        "hourly_report_bg.txt",
        "screen.txt",
        "timings.txt",
        "AFB.txt",
        "inventory_screenshots",
    )
    for entry in os.listdir(legacy_dir) if os.path.exists(legacy_dir) else []:
        if entry == "app_state.json":
            continue
        should_backup = any(entry == name or entry.startswith(f"{name}.bak") for name in legacy_basenames)
        if should_backup:
            backup_legacy_file(os.path.join(legacy_dir, entry))

def _ensureProfileUserDataFiles(profile_name):
    os.makedirs(getProfileUserDataDir(profile_name), exist_ok=True)
    defaults = {
    }
    for filename, content in defaults.items():
        path = getProfileUserDataPath(filename, profile_name)
        if not os.path.exists(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)

    json_defaults = {
        "blender.json": {"item": 1, "collectTime": 0},
        "manualplanters.json": {},
        "sticker_stack.json": {"sticker_stack": 0},
        "hourly_report_history.json": [],
        "screen.json": {
            "display_type": "built-in",
            "screen_width": 2880,
            "screen_height": 1800,
            "reference_width": 2880,
            "reference_height": 1800,
            "x_scale": 1,
            "y_scale": 1,
            "y_multiplier": 1,
            "x_multiplier": 1,
            "y_length_multiplier": 1,
            "x_length_multiplier": 1,
        },
        "hotbar_timings.json": {str(slot): 0 for slot in range(1, 8)},
        "hotbar_buff_tool_timings.json": {str(slot): 0 for slot in range(1, 8)},
    }
    for filename, data in json_defaults.items():
        if not os.path.exists(getProfileUserDataPath(filename, profile_name)):
            writeProfileUserJson(filename, data, profile_name)

    if not os.path.exists(getProfileUserDataPath("auto_planters.json", profile_name)):
        writeProfileUserJson("auto_planters.json", _defaultAutoPlanterUserData(), profile_name)

    if not os.path.exists(getProfileUserDataPath("fuzzy_ai_token_rankings.json", profile_name)):
        default_rankings = read_json_file(DEFAULT_FUZZY_AI_TOKEN_RANKINGS_FILE, {})
        writeProfileUserJson("fuzzy_ai_token_rankings.json", default_rankings if isinstance(default_rankings, dict) else {}, profile_name)

def _ensureProfileJsonFiles(profile_name):
    os.makedirs(getProfilePath(profile_name), exist_ok=True)
    if not os.path.exists(getProfileJsonPath(profile_name)):
        _saveProfileDocument(_defaultProfileDocument(), profile_name)
    if not os.path.exists(getFieldsJsonPath(profile_name)):
        fields_doc = _defaultFieldsDocument()
        _saveFieldsDocument(fields_doc["fields"], profile_name)
    if not os.path.exists(getRuntimeStateJsonPath(profile_name)):
        write_json_atomic(getRuntimeStateJsonPath(profile_name), _runtimeStateDefault())
    _ensureProfileUserDataFiles(profile_name)

def _listProfilesRaw():
    profiles_dir = getProfilesDir()
    if os.path.exists(profiles_dir):
        profiles = [
            d for d in os.listdir(profiles_dir)
            if os.path.isdir(os.path.join(profiles_dir, d)) and not d.startswith('.')
        ]
        return sorted(profiles)
    return []

def ensureSettingsFilesExist():
    """Create the generated settings/user-data tree when an install has none."""
    os.makedirs(getProfilesDir(), exist_ok=True)
    profiles = _listProfilesRaw()
    if not profiles:
        _ensureProfileJsonFiles("a")
        profiles = ["a"]
    if not os.path.exists(APP_STATE_FILE):
        selected = profileName if profileName in profiles else profiles[0]
        legacy_profile, _legacy_path = _readLegacyCurrentProfile()
        if legacy_profile in profiles:
            selected = legacy_profile
        write_json_atomic(APP_STATE_FILE, {"schema_version": 1, "current_profile": selected})

def migrateUserDataToJson():
    """Migrate legacy profile and runtime user data to JSON. Safe to call repeatedly."""
    try:
        os.makedirs(os.path.join(getProjectRoot(), "src", "data", "user"), exist_ok=True)
        ensureSettingsFilesExist()
        legacy_profile, legacy_path = _readLegacyCurrentProfile()
        if legacy_profile:
            if legacy_profile and os.path.exists(getProfilePath(legacy_profile)):
                write_json_atomic(APP_STATE_FILE, {"schema_version": 1, "current_profile": legacy_profile})
            if legacy_path == CURRENT_PROFILE_FILE:
                backup_legacy_file(CURRENT_PROFILE_FILE)

        for profile in listProfiles():
            profile_log = {}
            if not os.path.exists(getProfileJsonPath(profile)):
                profile_doc, profile_log = _buildProfileDocumentFromLegacy(profile)
                _saveProfileDocument(profile_doc, profile)
                backup_legacy_file(os.path.join(getProfilePath(profile), "settings.txt"))
                backup_legacy_file(os.path.join(getProfilePath(profile), "generalsettings.txt"))

            if not os.path.exists(getFieldsJsonPath(profile)):
                fields_doc = _loadFieldsDocument(profile)
                _saveFieldsDocument(fields_doc["fields"], profile)
                backup_legacy_file(os.path.join(getProfilePath(profile), "fields.txt"))

            if profile_log:
                write_json_atomic(getMigrationLogPath(profile), profile_log)

            _migrateProfileUserTextJson(profile, profile_log)
            _ensureProfileJsonFiles(profile)

        runtime_log = {"schema_version": 1, "migrated_at": datetime.now().isoformat(), "dropped_runtime_keys": {}}
        active_profile = profileName
        app_state = read_json_file(APP_STATE_FILE, {})
        if isinstance(app_state, dict) and app_state.get("current_profile"):
            active_profile = app_state["current_profile"]
        if not os.path.exists(getRuntimeStateJsonPath(active_profile)):
            _migrateRuntimeState(runtime_log, active_profile)

        _migrateProfileUserFiles(active_profile, runtime_log)
        _validateAutoPlantersJson(runtime_log, active_profile)
        _validateFuzzyAITokenRankingsJson(runtime_log, active_profile)
        _trashLegacyUserDataFiles()
    except Exception as e:
        print(f"Warning: JSON settings migration failed: {e}")

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

def _applyFieldPatternPresets(existing_settings, incoming_settings):
    incoming_shape = incoming_settings.get("shape")
    existing_shape = (
        existing_settings.get("shape") if isinstance(existing_settings, dict) else None
    )

    presets = _getFieldPatternPresets(existing_settings)
    presets.update(_getFieldPatternPresets(incoming_settings))

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
    profile_rankings = getProfileUserDataPath("fuzzy_ai_token_rankings.json")
    for path in (profile_rankings, FUZZY_AI_TOKEN_RANKINGS_FILE, DEFAULT_FUZZY_AI_TOKEN_RANKINGS_FILE):
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
    write_json_atomic(getProfileUserDataPath("fuzzy_ai_token_rankings.json"), data)

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
    return _listProfilesRaw()

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

    # Check if required profile files exist. Legacy profiles are migrated on demand.
    if not os.path.exists(getProfileJsonPath(name)) or not os.path.exists(getFieldsJsonPath(name)):
        migrateUserDataToJson()

    if not os.path.exists(getProfileJsonPath(name)):
        return False, f"Profile '{name}' is missing profile.json file"

    if not os.path.exists(getFieldsJsonPath(name)):
        return False, f"Profile '{name}' is missing fields.json file"

    profileName = name
    _ensureProfileJsonFiles(name)
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

        _ensureProfileJsonFiles(name)

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
    section = _runtimeSectionForPath(path)
    if section:
        return _readRuntimeSection(section)

    abs_path = os.path.abspath(path)
    try:
        profile_path = os.path.abspath(os.path.join(getProfilePath(), "settings.txt"))
        general_path = os.path.abspath(os.path.join(getProfilePath(), "generalsettings.txt"))
        if abs_path == profile_path:
            return dict(_loadProfileDocument().get("profile_settings", {}))
        if abs_path == general_path:
            return dict(_loadProfileDocument().get("general_settings", {}))
    except Exception:
        pass

    return _readLegacySettingsFile(path)

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
    section = _runtimeSectionForPath(path)
    if section:
        _writeRuntimeSection(section, data)
        return

    abs_path = os.path.abspath(path)
    try:
        profile_path = os.path.abspath(os.path.join(getProfilePath(), "settings.txt"))
        general_path = os.path.abspath(os.path.join(getProfilePath(), "generalsettings.txt"))
        if abs_path in (profile_path, general_path):
            doc = _loadProfileDocument()
            if abs_path == profile_path:
                doc["profile_settings"] = dict(data)
            else:
                doc["general_settings"] = dict(data)
            _saveProfileDocument(doc)
            return
    except Exception:
        pass

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
    return os.path.join(getDefaultSettingsPath(), "fields.txt")

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
    if os.path.basename(fields_path) == "fields.txt":
        profile_dir = os.path.dirname(os.path.abspath(fields_path))
        json_path = os.path.join(profile_dir, "fields.json")
        data = read_json_file(json_path)
        if isinstance(data, dict) and isinstance(data.get("fields"), dict):
            return _coerceNestedValues(data["fields"])

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
    out = _loadFieldsDocument().get("fields", {})

    default_fields = loadDefaultFields()
    fieldsUpdated = False
    for field, settings in out.items():
        normalized = normalizeFieldSettings(field, settings, default_fields)
        if normalized != settings:
            out[field] = normalized
            fieldsUpdated = True

    if fieldsUpdated:
        _saveFieldsDocument(out)

    return out

def saveField(field, settings):
    fieldsData = loadFields()
    existingSettings = fieldsData.get(field, {})
    normalizedSettings = normalizeFieldSettings(field, settings)
    fieldsData[field] = _applyFieldPatternPresets(existingSettings, normalizedSettings)
    _saveFieldsDocument(fieldsData)

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
            blue_model = getFuzzyAIModelPath("tokens.onnx")
            blue_model_coreml = getFuzzyAIModelPath("best.mlpackage")
            sprinkler_model = getFuzzyAIModelPath("sprinkler.onnx")
            sprinkler_model_coreml = getFuzzyAIModelPath("sprinkler.mlpackage")
            if not os.path.exists(blue_model) and not os.path.exists(blue_model_coreml):
                warnings.append("Missing blue model: src/data/models/tokens.onnx or src/data/models/best.mlpackage")
            if not os.path.exists(sprinkler_model) and not os.path.exists(sprinkler_model_coreml):
                warnings.append("Missing sprinkler model: src/data/models/sprinkler.onnx or src/data/models/sprinkler.mlpackage")

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
    return getProfileUserDataPath("auto_planters.json")

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
        if not os.path.exists(getProfileJsonPath(profile_name)) or not os.path.exists(getFieldsJsonPath(profile_name)):
            migrateUserDataToJson()

        if not os.path.exists(getProfileJsonPath(profile_name)) or not os.path.exists(getFieldsJsonPath(profile_name)):
            return False, f"Profile '{profile_name}' is missing required files"

        profile_doc = _loadProfileDocument(profile_name)
        settings_data = dict(profile_doc.get("profile_settings", {}))
        fields_data = loadFields() if profile_name == getCurrentProfile() else _loadFieldsDocument(profile_name).get("fields", {})
        generalsettings_data = dict(profile_doc.get("general_settings", {}))

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

        _saveProfileDocument({
            "schema_version": 1,
            "profile_settings": import_data["settings"],
            "general_settings": import_data["generalsettings"],
        }, new_profile_name)
        _saveFieldsDocument(import_data["fields"], new_profile_name)
        write_json_atomic(getRuntimeStateJsonPath(new_profile_name), _runtimeStateDefault())

        return True, f"Profile imported successfully as '{new_profile_name}'"

    except Exception as e:
        return False, f"Failed to import profile: {str(e)}"

# Migrate legacy settings before the module is used by the GUI or macro process.
migrateUserDataToJson()
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
