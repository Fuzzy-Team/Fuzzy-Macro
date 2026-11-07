"""Reads, migrates, validates, and saves Macro Profiles.

Callers get plain dicts and make validated changes. File names, parsing, repair, migration,
locking, and atomic replacement stay inside this module.
"""

from __future__ import annotations

import ast
import copy
import math
import os
import re
import tempfile
import threading
from contextlib import contextmanager

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows fallback
    fcntl = None


class MacroProfileError(Exception):
    """Base error returned by the Macro Profile interface."""


class MacroProfileValidationError(MacroProfileError):
    def __init__(self, setting, reason):
        self.setting = setting
        self.reason = reason
        super().__init__(f"{setting}: {reason}")

    def as_dict(self):
        return {"setting": self.setting, "reason": self.reason}


_INT_LITERAL = re.compile(r"-?(?:0|[1-9][0-9]*)")
_FLOAT_LITERAL = re.compile(r"-?[0-9]+\.[0-9]+")
_CONSTANTS = {"True": True, "False": False, "None": None}
# Bare words ("auto", "no override") are saved unquoted; literal_eval can only reject them.
_BARE_WORDS = re.compile(r"[A-Za-z_ ]+")


def _literal(value):
    """ast.literal_eval, with the common setting shapes (numbers, True/False/None) parsed directly.
    A profile has ~1600 lines, and literal_eval on each made every load and save take milliseconds."""
    if value in _CONSTANTS:
        return _CONSTANTS[value]
    if _INT_LITERAL.fullmatch(value):
        return int(value)
    if _FLOAT_LITERAL.fullmatch(value):
        return float(value)
    if _BARE_WORDS.fullmatch(value):
        raise ValueError(f"not a literal: {value!r}")
    return ast.literal_eval(value)


def _parse_setting(value, default):
    """Parse one saved value like _read_settings_file; also reports an unusable typed value."""
    invalid = False
    try:
        parsed = _literal(value)
    except Exception:
        parsed = value
        # Text where a number or true/false belongs would break the macro later, so use
        # the default. Other settings keep text: the GUI saves some as plain text.
        if value.isdecimal():
            parsed = int(value)
        elif value.replace(".", "", 1).isdecimal():
            parsed = float(value)
        elif isinstance(default, bool) and value.lower() in ("true", "false"):
            parsed = value.lower() == "true"
        elif isinstance(default, (bool, int, float)):
            parsed = copy.deepcopy(default)
            invalid = True
    if isinstance(parsed, dict) and set(parsed) == {"source", "value"}:
        parsed = parsed["value"]  # an old GUI bug saved some dropdowns wrapped like this
    if isinstance(default, str) and not isinstance(parsed, str):
        parsed = "" if parsed is None else str(parsed)
    return parsed, invalid


def _as_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


class MacroProfileStore:
    """Owns Macro Profile normalization, migration, validation, and persistence."""

    PROFILE_FILE = "settings.txt"
    GENERAL_FILE = "generalsettings.txt"
    FIELDS_FILE = "fields.txt"
    MIGRATION_FILE = ".migration_version"
    # One-time upgrades, in order. Append new ones to the end and never reorder or remove
    # them: each profile stores how many have run, so the version bumps by itself.
    MIGRATIONS = ("_migrate_legacy_settings", "_migrate_priority_tasks")
    # Gather patterns that lost their version suffix. Saved and imported `shape` values are mapped on load.
    PATTERN_RENAMES = {"bamb_dupe_v11": "bamb_dupe", "pine_dupe_v12": "pine_dupe", "octo_v4": "octo"}

    def __init__(self, profiles_dir, profile_defaults, general_defaults, field_defaults, field_normalizer=None):
        self._profiles_dir = os.path.abspath(profiles_dir)
        self._profile_defaults = copy.deepcopy(profile_defaults)
        self._general_defaults = copy.deepcopy(general_defaults)
        self._field_defaults = copy.deepcopy(field_defaults)
        self._field_normalizer = field_normalizer
        self._lock = threading.RLock()
        self._read_cache = {}  # path -> (file stamp, parsed settings, warnings)

    def initialize(self, profile):
        """Create missing files and run pending migrations, then return the profile like load()."""
        with self._lock, self._file_lock(profile):
            profile_data, general_data, fields_data, errors, changed, warnings = self._read_and_normalize(profile)
            profile_dir = self._profile_dir(profile)
            os.makedirs(profile_dir, exist_ok=True)
            for warning in warnings:
                print(f"Warning: Macro Profile '{profile}': {warning}")

            # Migrations wait until every file reads, so a half-read profile is never migrated.
            pending = () if errors else self.MIGRATIONS[self._migrated_version(profile):]
            for migration in pending:
                profile_changed, general_changed = getattr(self, migration)(profile_data, general_data, fields_data)
                changed[self.PROFILE_FILE] = changed[self.PROFILE_FILE] or profile_changed
                changed[self.GENERAL_FILE] = changed[self.GENERAL_FILE] or general_changed

            for filename, data in (
                (self.PROFILE_FILE, profile_data),
                (self.GENERAL_FILE, general_data),
                (self.FIELDS_FILE, fields_data),
            ):
                if filename in errors:
                    continue
                path = os.path.join(profile_dir, filename)
                if changed.get(filename) or not os.path.exists(path):
                    self._write_file(path, data, fields=filename == self.FIELDS_FILE)
            if pending:
                self._atomic_write(os.path.join(profile_dir, self.MIGRATION_FILE), str(len(self.MIGRATIONS)).encode("utf-8"))
            return self._profile_dict(profile, profile_data, general_data, fields_data, errors, warnings)

    def load(self, profile):
        """Return the profile without changing files:
        {profile, settings, profile_settings, general_settings, fields, errors, warnings}.

        settings combines profile_settings and general_settings. errors lists files that
        couldn't be read (their defaults are used); warnings lists lines that were skipped
        or replaced.
        """
        with self._lock:
            profile_data, general_data, fields_data, errors, _, warnings = self._read_and_normalize(profile)
            return self._profile_dict(profile, profile_data, general_data, fields_data, errors, warnings)

    def load_settings(self, profile):
        """Return settings and read diagnostics without reading or normalizing fields."""
        with self._lock:
            profile_data, general_data, errors, _, warnings = self._read_settings(profile)
            return {
                "settings": {**profile_data, **general_data},
                "profile_settings": profile_data,
                "general_settings": general_data,
                "errors": list(errors.values()),
                "warnings": list(warnings),
            }

    def apply_change(self, profile, scope, setting, value):
        """Validate and save one setting. Returns all settings (profile and general) after the change."""
        with self._lock, self._file_lock(profile):
            profile_data, general_data, errors, _, _ = self._read_settings(profile)
            owner = self._owner(setting, scope)
            filename = self.PROFILE_FILE if owner == "profile" else self.GENERAL_FILE
            self._refuse_overwrite(errors, filename)

            defaults = self._profile_defaults if owner == "profile" else self._general_defaults
            self._validate(setting, value, defaults, {**profile_data, **general_data})
            target = profile_data if owner == "profile" else general_data
            target[setting] = copy.deepcopy(value)
            self._write_file(os.path.join(self._profile_dir(profile), filename), target, changed=(setting,))
            return {**profile_data, **general_data}

    def apply_changes(self, profile, scope, changes):
        """Validate every change first, then save them."""
        if not isinstance(changes, dict):
            raise MacroProfileValidationError("changes", "expected an object")
        with self._lock, self._file_lock(profile):
            profile_data, general_data, errors, _, _ = self._read_settings(profile)
            self._refuse_overwrite(errors, self.PROFILE_FILE, self.GENERAL_FILE)
            next_profile = copy.deepcopy(profile_data)
            next_general = copy.deepcopy(general_data)
            combined = {**next_profile, **next_general}
            owners = {}
            for setting, value in changes.items():
                owner = self._owner(setting, scope)
                owners[setting] = owner
                (next_profile if owner == "profile" else next_general)[setting] = copy.deepcopy(value)
                combined[setting] = copy.deepcopy(value)
            for setting, value in changes.items():
                defaults = self._profile_defaults if owners[setting] == "profile" else self._general_defaults
                self._validate(setting, value, defaults, combined)
            profile_dir = self._profile_dir(profile)
            if next_profile != profile_data:
                self._write_file(os.path.join(profile_dir, self.PROFILE_FILE), next_profile,
                                 changed=[key for key in changes if owners[key] == "profile"])
            if next_general != general_data:
                self._write_file(os.path.join(profile_dir, self.GENERAL_FILE), next_general,
                                 changed=[key for key in changes if owners[key] == "general"])

    def save_field(self, profile, field, settings):
        if not isinstance(settings, dict):
            raise MacroProfileValidationError(field, "field settings must be an object")
        with self._lock, self._file_lock(profile):
            _, _, fields_data, errors, _, _ = self._read_and_normalize(profile)
            self._refuse_overwrite(errors, self.FIELDS_FILE)
            normalized = self._normalize_field(field, settings)
            fields_data[field] = normalized
            self._write_file(os.path.join(self._profile_dir(profile), self.FIELDS_FILE), fields_data, fields=True)

    @staticmethod
    def _profile_dict(profile, profile_data, general_data, fields_data, errors, warnings):
        return {
            "profile": profile,
            "settings": {**profile_data, **general_data},
            "profile_settings": profile_data,
            "general_settings": general_data,
            "fields": fields_data,
            "errors": list(errors.values()),
            "warnings": list(warnings),
        }

    @staticmethod
    def _refuse_overwrite(errors, *filenames):
        """An unreadable file is shown as defaults; saving would replace the user's copy with them."""
        for filename in filenames:
            if filename in errors:
                raise MacroProfileError(f"Cannot save: {errors[filename]}. Fix or remove {filename} first.")

    def _read_and_normalize(self, profile):
        """Read the profile and fill in defaults. Migrations run in initialize, not here."""
        profile_data, general_data, errors, changed, warnings = self._read_settings(profile)
        fields_data = self._safe_read_fields(os.path.join(self._profile_dir(profile), self.FIELDS_FILE), errors)
        fields_data, changed[self.FIELDS_FILE] = self._normalize_fields(fields_data)
        return profile_data, general_data, fields_data, errors, changed, warnings

    def _read_settings(self, profile):
        """Read and normalize only the two settings files."""
        warnings = []
        profile_dir = self._profile_dir(profile)
        errors = {}
        profile_data = self._safe_read(os.path.join(profile_dir, self.PROFILE_FILE), self._profile_defaults, errors, warnings)
        general_data = self._safe_read(os.path.join(profile_dir, self.GENERAL_FILE), self._general_defaults, errors, warnings)
        profile_data, general_data, settings_changed = self._normalize_settings(profile_data, general_data)
        changed = {self.PROFILE_FILE: settings_changed[0], self.GENERAL_FILE: settings_changed[1]}
        return profile_data, general_data, errors, changed, warnings

    def _safe_read(self, path, defaults, errors, warnings):
        if not os.path.exists(path):
            return copy.deepcopy(defaults)
        try:
            # Settings are read far more often than they change, so reuse the parse of an unchanged file.
            stat = os.stat(path)
            stamp = (stat.st_mtime_ns, stat.st_size, stat.st_ino)
            cached = self._read_cache.get(path)
            if cached is None or cached[0] != stamp:
                read_warnings = []
                cached = (stamp, self._read_settings_file(path, defaults, read_warnings), read_warnings)
                self._read_cache[path] = cached
            warnings.extend(cached[2])
            return {key: copy.deepcopy(value) if isinstance(value, (list, dict, set)) else value
                    for key, value in cached[1].items()}
        except Exception as exc:
            errors[os.path.basename(path)] = f"{os.path.basename(path)}: {exc}"
            return copy.deepcopy(defaults)

    def _safe_read_fields(self, path, errors):
        if not os.path.exists(path):
            return copy.deepcopy(self._field_defaults)
        try:
            return self._read_fields_file(path)
        except Exception as exc:
            errors[self.FIELDS_FILE] = f"{self.FIELDS_FILE}: {exc}"
            return copy.deepcopy(self._field_defaults)

    @staticmethod
    def _read_fields_file(path):
        with open(path, encoding="utf-8") as handle:
            raw = handle.read().strip()
        value = ast.literal_eval(raw) if raw else {}
        if not isinstance(value, dict):
            raise ValueError("expected an object")
        return value

    def _migrated_version(self, profile):
        try:
            with open(os.path.join(self._profile_dir(profile), self.MIGRATION_FILE), encoding="utf-8") as handle:
                return int(handle.read().strip())
        except (OSError, ValueError):
            return 0

    @staticmethod
    def _read_settings_file(path, defaults, warnings):
        """Parse key=value lines. A line that isn't a setting is skipped (and reported)
        rather than failing the file, so one bad line can't reset every other setting."""
        with open(path, "rb") as handle:
            content = handle.read()
        try:
            raw = content.decode("utf-8")
        except UnicodeDecodeError:
            raw = content.decode("utf-8", errors="replace")
            warnings.append(f"{os.path.basename(path)} is not valid UTF-8; unreadable characters were replaced")
        if "max_convert_time=" in raw:
            raw = re.sub(r"(?<![A-Za-z_])(?<!\n)max_convert_time=", "\nmax_convert_time=", raw)
        result = {}
        for line_number, line in enumerate(raw.splitlines(), 1):
            if not line.strip():
                continue
            key, separator, value = line.partition("=")
            key, value = key.strip(), value.strip()
            if not separator or not key:
                warnings.append(f"{os.path.basename(path)} line {line_number} is not a setting and was skipped: {line.strip()[:60]!r}")
                continue
            default = defaults.get(key)
            parsed, invalid = _parse_setting(value, default)
            if invalid:
                warnings.append(f"{os.path.basename(path)}: {key}={value!r} is not a valid value; using the default ({default!r})")
            result[key] = parsed
        return result

    def _normalize_settings(self, profile_data, general_data):
        """Fill in missing defaults. A file changed only if a key was added."""
        changed = []
        for data, defaults in ((profile_data, self._profile_defaults), (general_data, self._general_defaults)):
            missing = [key for key in defaults if key not in data]
            for key in missing:
                data[key] = copy.deepcopy(defaults[key])
            changed.append(bool(missing))
        return profile_data, general_data, tuple(changed)

    def _migrate_legacy_settings(self, profile_data, general_data, fields_data):
        """One-time upgrades of settings saved by older versions. Returns (profile changed, general changed)."""
        original_profile = copy.deepcopy(profile_data)
        original_general = copy.deepcopy(general_data)
        profile_keys = set(self._profile_defaults)
        general_keys = set(self._general_defaults)

        # Move settings stored in the wrong file to their owner, keeping a value the
        # user changed over a default when both files have the key.
        for source, target, owner_keys, other_keys, defaults in (
            (general_data, profile_data, profile_keys, general_keys, self._profile_defaults),
            (profile_data, general_data, general_keys, profile_keys, self._general_defaults),
        ):
            for key in list(source):
                if key in owner_keys and key not in other_keys:
                    moved = source.pop(key)
                    if key not in target or (target[key] == defaults[key] and moved != defaults[key]):
                        target[key] = moved
        # Field booster extending now uses the general glitter_slot. Keep the slot the user
        # chose (0 finds Glitter in the inventory). TAD alts and AFB keep their own slots.
        for data in (profile_data, general_data):
            if "field_booster_glitter_slot" in data:
                slot = data.pop("field_booster_glitter_slot")
                if slot != 1 and slot in range(0, 8):
                    general_data["glitter_slot"] = slot

        order = profile_data.get("task_priority_order")
        if isinstance(order, list):
            for item, after in (("collect_sprouts", "collect_sticker_printer"), ("collect_sticker_sprout", "collect_sprouts"),
                                ("quest_panda_bear", "quest_riley_bee"), ("quest_science_bear", "quest_panda_bear"),
                                ("quest_mother_bear", "quest_science_bear"), ("quest_onett", "quest_mother_bear"),
                                ("quest_spirit_bear", "quest_onett")):
                if item not in order:
                    index = order.index(after) + 1 if after in order else len(order)
                    order.insert(index, item)

        if "field_only_mode" in general_data or "quest_only_mode" in general_data:
            field_only = bool(general_data.pop("field_only_mode", False))
            quest_only = bool(general_data.pop("quest_only_mode", False))
            general_data["macro_mode"] = "field" if field_only else "quest" if quest_only else "normal"

        lists = [profile_data.get(key) for key in ("fields", "fields_enabled")]
        #both lists stay the same length, so a field's flag is always at its own index
        target = max([3] + [len(value) for value in lists if isinstance(value, list)])
        for key in ("fields", "fields_enabled"):
            value = profile_data.get(key)
            default = self._profile_defaults.get(key, [])
            if isinstance(value, list):
                while len(value) < target:
                    value.append(copy.deepcopy(default[len(value)] if len(value) < len(default) else default[-1]))

        self._merge_quest_gumdrop_slot(profile_data, general_data, fields_data)
        return profile_data != original_profile, general_data != original_general

    def _migrate_priority_tasks(self, profile_data, general_data, fields_data):
        """Add task IDs introduced after a profile was saved to its priority order."""
        original_profile = copy.deepcopy(profile_data)
        order = profile_data.get("task_priority_order")
        default_order = self._profile_defaults.get("task_priority_order", [])
        if isinstance(order, list):
            for index, task in enumerate(default_order):
                if task in order:
                    continue
                # Put a new task next to its nearest default neighbour that is already in
                # the saved order. Existing entries never move, so custom priority survives.
                before = next((item for item in reversed(default_order[:index]) if item in order), None)
                after = next((item for item in default_order[index + 1:] if item in order), None)
                if before is not None:
                    order.insert(order.index(before) + 1, task)
                elif after is not None:
                    order.insert(order.index(after), task)
                else:
                    order.append(task)
        return profile_data != original_profile, False

    @staticmethod
    def _merge_quest_gumdrop_slot(profile_data, general_data, fields_data):
        """Goo quests now use goo_slot (the gumdrop slot) instead of a separate quest_gumdrop_slot.

        Keep the slot the user actually relies on: the quest slot if only goo quests use
        gumdrops, otherwise the goo slot.
        """
        source = profile_data if "quest_gumdrop_slot" in profile_data else general_data
        if "quest_gumdrop_slot" not in source:
            return
        quest_slot = source.pop("quest_gumdrop_slot")
        uses_field_goo = any(isinstance(field, dict) and field.get("goo") for field in fields_data.values())
        if profile_data.get("quest_use_gumdrops") and not uses_field_goo:
            general_data["goo_slot"] = quest_slot

    def _normalize_fields(self, fields_data):
        original = copy.deepcopy(fields_data)
        if not isinstance(fields_data, dict):
            fields_data = {}
        for field, defaults in self._field_defaults.items():
            current = fields_data.get(field)
            if not isinstance(current, dict):
                current = copy.deepcopy(defaults)
            else:
                for key, value in defaults.items():
                    current.setdefault(key, copy.deepcopy(value))
            fields_data[field] = self._normalize_field(field, current)
            shape = fields_data[field].get("shape")
            if isinstance(shape, str):
                fields_data[field]["shape"] = self.PATTERN_RENAMES.get(shape, shape)
        return fields_data, fields_data != original

    def _normalize_field(self, field, settings):
        value = copy.deepcopy(settings)
        if self._field_normalizer is not None:
            value = self._field_normalizer(field, value, self._field_defaults)
        return value

    def _owner(self, setting, requested_scope):
        if setting in self._profile_defaults and setting not in self._general_defaults:
            return "profile"
        if setting in self._general_defaults and setting not in self._profile_defaults:
            return "general"
        if requested_scope not in ("profile", "general"):
            raise MacroProfileValidationError(setting, "scope must be profile or general")
        return requested_scope

    def _validate(self, setting, value, defaults, combined):
        """Reject values that break a constraint. Types are not enforced: readers accept
        the formats the GUI saves (numeric strings, comma-separated lists, ...)."""
        from modules.quest_planning import FIELDS, OBJECTIVE_SETTING_CHOICES, gather_objective_types, load_quest_catalog

        choices = {"quest_scheduling": ("quest giver priority", "optimize quest completion"),
                   "quest_progress_check_mode": ("interval", "every iteration")}
        if setting in choices and value not in choices[setting]:
            raise MacroProfileValidationError(setting, "choose one of the listed options")
        if setting == "cooldown_field" and value not in ("none", *FIELDS):
            raise MacroProfileValidationError(setting, "choose a field or None")
        property_name = None
        if setting.startswith("quest_objective_"):
            name = setting[len("quest_objective_"):]
            objective = next((item for item in gather_objective_types(load_quest_catalog())
                              if name.startswith(item["value"] + "_")), None)
            property_name = name[len(objective["value"]) + 1:] if objective else None
            if objective is None or (property_name not in ("field", "pattern", "mins", "backpack", "return")
                                     and property_name not in OBJECTIVE_SETTING_CHOICES):
                raise MacroProfileValidationError(setting, "choose a gathering objective from the quest catalog")
            if property_name in OBJECTIVE_SETTING_CHOICES and str(value) not in ("auto", *OBJECTIVE_SETTING_CHOICES[property_name]):
                raise MacroProfileValidationError(setting, "choose one of the listed options")
            if property_name == "field" and value != "auto" and value not in objective["fields"]:
                raise MacroProfileValidationError(setting, "choose a field that supports this objective")
            if property_name == "return" and value not in ("no override", "reset", "walk", "rejoin", "whirligig"):
                raise MacroProfileValidationError(setting, "choose one of the listed return methods")
            if property_name == "pattern" and (not isinstance(value, str) or not value or os.path.basename(value) != value):
                raise MacroProfileValidationError(setting, "choose a gather pattern")
        if setting in ("quest_progress_check_seconds", "petal_quest_gather_mins") or property_name in ("mins", "backpack"):
            if property_name == "backpack" and value == "auto":
                return
            try:
                number = float(value)
            except (TypeError, ValueError):
                raise MacroProfileValidationError(setting, "enter a number")
            minimum = 0 if property_name == "mins" or setting == "petal_quest_gather_mins" else 1
            if not math.isfinite(number) or number < minimum:
                raise MacroProfileValidationError(setting, f"must be at least {minimum}")
            if property_name == "backpack" and number > 100:
                raise MacroProfileValidationError(setting, "must be between 1 and 100, or Auto")

        if setting in ("max_cannon_attempts", "cannon_hive_resync_attempts"):
            if not isinstance(value, int) or isinstance(value, bool):
                raise MacroProfileValidationError(setting, "expected int")
            if not 0 <= value <= 25:
                raise MacroProfileValidationError(setting, "must be between 0 and 25")
            max_attempts = value if setting == "max_cannon_attempts" else _as_int(combined.get("max_cannon_attempts"), 1)
            resync_attempts = value if setting == "cannon_hive_resync_attempts" else _as_int(combined.get("cannon_hive_resync_attempts"), 0)
            if max_attempts < 1:
                raise MacroProfileValidationError(setting, "max cannon attempts must be at least 1")
            if resync_attempts >= max_attempts:
                raise MacroProfileValidationError(setting, "hive resync attempts must be less than max cannon attempts")

    def _profile_dir(self, profile):
        safe = str(profile).strip()
        if not safe or safe in (".", "..") or os.path.basename(safe) != safe:
            raise MacroProfileValidationError("profile", "invalid profile name")
        return os.path.join(self._profiles_dir, safe)

    @contextmanager
    def _file_lock(self, profile):
        profile_dir = self._profile_dir(profile)
        os.makedirs(profile_dir, exist_ok=True)
        lock_path = os.path.join(profile_dir, ".macro_profile.lock")
        with open(lock_path, "a+") as lock_file:
            if fcntl is not None:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                if fcntl is not None:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def _write_file(self, path, data, fields=False, changed=None):
        if fields:
            content = str(data)
        else:
            content = "\n".join(f"{key}={value}" for key, value in data.items())
        if content and not content.endswith("\n"):
            content += "\n"
        stamp = self._atomic_write(path, content.encode("utf-8"))
        if changed is not None and not fields:
            self._remember_written(path, data, changed, stamp)

    def _remember_written(self, path, data, changed, stamp):
        """Reuse this write as the next read's parse instead of re-reading the file.

        Only the keys the caller changed are parsed again; every other value came from a
        read or the defaults and is already in the form a re-read would produce. If that
        can't be guaranteed (a value with a line break, an unparsable one), the entry is
        dropped and the next read parses the file as before.
        """
        name = os.path.basename(path)
        if name not in (self.PROFILE_FILE, self.GENERAL_FILE):
            return
        defaults = self._profile_defaults if name == self.PROFILE_FILE else self._general_defaults
        parsing = set(changed)
        snapshot, warnings = {}, []
        try:
            for key, value in data.items():
                if key in parsing:
                    text = str(value)
                    if "\n" in text or "\r" in text:
                        raise ValueError("line break in value")
                    default = defaults.get(key)
                    value, invalid = _parse_setting(text, default)
                    if invalid:
                        warnings.append(f"{name}: {key}={text!r} is not a valid value; using the default ({default!r})")
                snapshot[key] = copy.deepcopy(value) if isinstance(value, (list, dict, set)) else value
        except Exception:
            self._read_cache.pop(path, None)
            return
        self._read_cache[path] = (stamp, snapshot, warnings)

    @staticmethod
    def _atomic_write(path, content):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=".macro_profile_", suffix=".tmp", dir=os.path.dirname(path))
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
                written = os.fstat(handle.fileno())
            os.replace(temporary, path)
            return (written.st_mtime_ns, written.st_size, written.st_ino)
        except Exception:
            try:
                os.remove(temporary)
            except OSError:
                pass
            raise
