"""Deep persistence module for Macro Profiles.

Callers use snapshots and validated changes. File names, parsing, repair, migration,
locking, and atomic replacement remain implementation details of this module.
"""

from __future__ import annotations

import ast
import copy
import os
import re
import tempfile
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from types import MappingProxyType

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


@dataclass(frozen=True)
class MacroProfileSnapshot:
    profile: str
    version: int
    settings: object
    fields: object
    migration_errors: tuple = ()

    def as_dict(self):
        return {
            "profile": self.profile,
            "version": self.version,
            "settings": _thaw(self.settings),
            "fields": _thaw(self.fields),
            "migration_errors": list(self.migration_errors),
        }


def _as_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _freeze(value):
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze(item) for item in value)
    return value


def _thaw(value):
    if isinstance(value, MappingProxyType):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return copy.deepcopy(value)


class MacroProfileStore:
    """Owns Macro Profile normalization, migration, validation, and persistence."""

    PROFILE_FILE = "settings.txt"
    GENERAL_FILE = "generalsettings.txt"
    FIELDS_FILE = "fields.txt"

    def __init__(self, profiles_dir, profile_defaults, general_defaults, field_defaults, field_normalizer=None):
        self._profiles_dir = os.path.abspath(profiles_dir)
        self._profile_defaults = copy.deepcopy(profile_defaults)
        self._general_defaults = copy.deepcopy(general_defaults)
        self._field_defaults = copy.deepcopy(field_defaults)
        self._field_normalizer = field_normalizer
        self._lock = threading.RLock()
        self._version = 0
        self._snapshot = None

    def initialize(self, profile):
        """Repair and migrate one profile, then publish its first snapshot."""
        with self._lock, self._file_lock(profile):
            profile_data, general_data, fields_data, errors, changed = self._read_and_normalize(profile)
            profile_dir = self._profile_dir(profile)
            os.makedirs(profile_dir, exist_ok=True)
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
            return self._publish(profile, profile_data, general_data, fields_data, errors)

    def snapshot(self, profile):
        """Return an immutable snapshot without changing files."""
        with self._lock:
            profile_data, general_data, fields_data, errors, _ = self._read_and_normalize(profile)
            combined = {**profile_data, **general_data}
            if self._snapshot is not None and self._snapshot.profile == profile:
                current = self._snapshot.as_dict()
                if current["settings"] == combined and current["fields"] == fields_data and current["migration_errors"] == list(errors.values()):
                    return self._snapshot
            return self._publish(profile, profile_data, general_data, fields_data, errors)

    def profile_settings(self, profile):
        """Return the settings stored in the profile's own settings file, without changing files."""
        with self._lock:
            profile_data, _, _, _, _ = self._read_and_normalize(profile)
            return copy.deepcopy(profile_data)

    def apply_change(self, profile, scope, setting, value):
        """Validate and atomically persist a setting-level change."""
        with self._lock, self._file_lock(profile):
            profile_data, general_data, fields_data, errors, _ = self._read_and_normalize(profile)
            if errors:
                raise MacroProfileError("Cannot save while Macro Profile files contain migration errors")

            owner = self._owner(setting, scope)
            defaults = self._profile_defaults if owner == "profile" else self._general_defaults
            self._validate(setting, value, defaults, {**profile_data, **general_data})
            target = profile_data if owner == "profile" else general_data
            target[setting] = copy.deepcopy(value)
            filename = self.PROFILE_FILE if owner == "profile" else self.GENERAL_FILE
            self._write_file(os.path.join(self._profile_dir(profile), filename), target)
            return self._publish(profile, profile_data, general_data, fields_data, {})

    def apply_changes(self, profile, scope, changes):
        """Validate and persist a transactional batch for import adapters."""
        if not isinstance(changes, dict):
            raise MacroProfileValidationError("changes", "expected an object")
        with self._lock, self._file_lock(profile):
            profile_data, general_data, fields_data, errors, _ = self._read_and_normalize(profile)
            if errors:
                raise MacroProfileError("Cannot import while Macro Profile files contain migration errors")
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
            # A batch can span two files. Validate everything first and restore the
            # first file if the second replacement fails.
            profile_path = os.path.join(self._profile_dir(profile), self.PROFILE_FILE)
            general_path = os.path.join(self._profile_dir(profile), self.GENERAL_FILE)
            original_profile = self._read_bytes(profile_path)
            original_general = self._read_bytes(general_path)
            try:
                self._write_file(profile_path, next_profile)
                self._write_file(general_path, next_general)
            except Exception:
                self._restore_bytes(profile_path, original_profile)
                self._restore_bytes(general_path, original_general)
                raise
            return self._publish(profile, next_profile, next_general, fields_data, {})

    def save_field(self, profile, field, settings):
        if not isinstance(settings, dict):
            raise MacroProfileValidationError(field, "field settings must be an object")
        with self._lock, self._file_lock(profile):
            profile_data, general_data, fields_data, errors, _ = self._read_and_normalize(profile)
            if errors:
                raise MacroProfileError("Cannot save while Macro Profile files contain migration errors")
            normalized = self._normalize_field(field, settings)
            fields_data[field] = normalized
            self._write_file(os.path.join(self._profile_dir(profile), self.FIELDS_FILE), fields_data, fields=True)
            return self._publish(profile, profile_data, general_data, fields_data, {})

    def _publish(self, profile, profile_data, general_data, fields_data, errors):
        self._version += 1
        self._snapshot = MacroProfileSnapshot(
            profile=profile,
            version=self._version,
            settings=_freeze({**copy.deepcopy(profile_data), **copy.deepcopy(general_data)}),
            fields=_freeze(copy.deepcopy(fields_data)),
            migration_errors=tuple(errors.values()),
        )
        return self._snapshot

    def _read_and_normalize(self, profile):
        profile_dir = self._profile_dir(profile)
        errors = {}
        changed = {}
        profile_data = self._safe_read(os.path.join(profile_dir, self.PROFILE_FILE), self._profile_defaults, errors)
        general_data = self._safe_read(os.path.join(profile_dir, self.GENERAL_FILE), self._general_defaults, errors)
        fields_data = self._safe_read_fields(os.path.join(profile_dir, self.FIELDS_FILE), errors)

        profile_data, general_data, settings_changed = self._normalize_settings(profile_data, general_data)
        fields_data, fields_changed = self._normalize_fields(fields_data)
        gumdrop_slot_merged = self._merge_quest_gumdrop_slot(profile_data, general_data, fields_data, errors)
        changed[self.PROFILE_FILE] = settings_changed[0] or gumdrop_slot_merged
        changed[self.GENERAL_FILE] = settings_changed[1] or gumdrop_slot_merged
        changed[self.FIELDS_FILE] = fields_changed
        return profile_data, general_data, fields_data, errors, changed

    def _safe_read(self, path, defaults, errors):
        if not os.path.exists(path):
            return copy.deepcopy(defaults)
        try:
            return self._read_settings_file(path, defaults)
        except Exception as exc:
            errors[os.path.basename(path)] = f"{os.path.basename(path)}: {exc}"
            return copy.deepcopy(defaults)

    def _safe_read_fields(self, path, errors):
        if not os.path.exists(path):
            return copy.deepcopy(self._field_defaults)
        try:
            with open(path) as handle:
                raw = handle.read().strip()
            value = ast.literal_eval(raw) if raw else {}
            if not isinstance(value, dict):
                raise ValueError("expected an object")
            return value
        except Exception as exc:
            errors[os.path.basename(path)] = f"{os.path.basename(path)}: {exc}"
            return copy.deepcopy(self._field_defaults)

    @staticmethod
    def _read_settings_file(path, defaults):
        with open(path) as handle:
            raw = handle.read()
        raw = re.sub(r"(?<![A-Za-z_])(?<!\n)max_convert_time=", "\nmax_convert_time=", raw)
        result = {}
        for line_number, line in enumerate(raw.splitlines(), 1):
            if not line.strip():
                continue
            if "=" not in line:
                raise ValueError(f"line {line_number} has no '='")
            key, value = (part.strip() for part in line.split("=", 1))
            try:
                parsed = ast.literal_eval(value)
            except Exception:
                parsed = value
            if isinstance(parsed, dict) and set(parsed) == {"source", "value"}:
                parsed = parsed["value"]  # an old GUI bug saved some dropdowns wrapped like this
            default = defaults.get(key)
            if isinstance(default, str) and not isinstance(parsed, str):
                parsed = "" if parsed is None else str(parsed)
            result[key] = parsed
        return result

    def _normalize_settings(self, profile_data, general_data):
        original_profile = copy.deepcopy(profile_data)
        original_general = copy.deepcopy(general_data)
        # Hive Acquisition always detects first now. Removing the obsolete
        # choice migrates both "check" and "detect" profiles to that behavior.
        profile_data.pop("hive_claim_method", None)
        general_data.pop("hive_claim_method", None)
        profile_keys = set(self._profile_defaults)
        general_keys = set(self._general_defaults)

        for key in list(general_data):
            if key in profile_keys and key not in general_keys:
                profile_data.setdefault(key, general_data.pop(key))
        for key in list(profile_data):
            if key in general_keys and key not in profile_keys:
                general_data.setdefault(key, profile_data.pop(key))
        # The three glitter slots were one setting the GUI kept in sync. Keep a slot the
        # user chose (one that differs from its old default); otherwise find Glitter in
        # the inventory (0) rather than pressing a slot that may hold something else.
        old_glitter_defaults = {"field_booster_glitter_slot": 1, "tad_alt_glitter_slot": 1, "AFB_slotG": 0}
        stored = {key: data.pop(key) for data in (profile_data, general_data) for key in list(data) if key in old_glitter_defaults}
        chosen = [stored[key] for key in old_glitter_defaults if key in stored and stored[key] != old_glitter_defaults[key]]
        if chosen:
            general_data["glitter_slot"] = chosen[0]

        # The old global quest gather override becomes per-quest settings, but only
        # when the user changed it; a default value must not overwrite per-quest ones.
        legacy = {key: profile_data[key] for key in ("quest_gather_mins", "quest_gather_return") if key in profile_data}
        if any(value != self._profile_defaults.get(key) for key, value in legacy.items()):
            for quest in ("polar_bear", "brown_bear", "black_bear", "honey_bee", "bucko_bee", "riley_bee"):
                if "quest_gather_mins" in legacy:
                    profile_data[f"{quest}_quest_gather_mins"] = legacy["quest_gather_mins"]
                if "quest_gather_return" in legacy:
                    profile_data[f"{quest}_quest_gather_return"] = legacy["quest_gather_return"]
            for key in legacy:
                profile_data.pop(key)

        for key, value in self._profile_defaults.items():
            profile_data.setdefault(key, copy.deepcopy(value))
        for key, value in self._general_defaults.items():
            general_data.setdefault(key, copy.deepcopy(value))

        order = profile_data.get("task_priority_order")
        if isinstance(order, list):
            for item, after in (("collect_sprouts", "collect_sticker_printer"), ("collect_sticker_sprout", "collect_sprouts")):
                if item not in order:
                    index = order.index(after) + 1 if after in order else len(order)
                    order.insert(index, item)

        if "field_only_mode" in general_data or "quest_only_mode" in general_data:
            field_only = bool(general_data.pop("field_only_mode", False))
            quest_only = bool(general_data.pop("quest_only_mode", False))
            general_data["macro_mode"] = "field" if field_only else "quest" if quest_only else "normal"

        for key in ("fields", "fields_enabled"):
            value = profile_data.get(key)
            default = self._profile_defaults.get(key, [])
            if isinstance(value, list):
                while len(value) < 5:
                    value.append(copy.deepcopy(default[len(value)] if len(value) < len(default) else default[-1]))

        return profile_data, general_data, (profile_data != original_profile, general_data != original_general)

    @staticmethod
    def _merge_quest_gumdrop_slot(profile_data, general_data, fields_data, errors=None):
        """Goo quests now use goo_slot (the gumdrop slot) instead of a separate quest_gumdrop_slot.

        Keep the slot the user actually relies on: the quest slot if only goo quests use
        gumdrops, otherwise the goo slot. Returns True if the old setting was removed.
        """
        source = profile_data if "quest_gumdrop_slot" in profile_data else general_data
        if "quest_gumdrop_slot" not in source:
            return False
        source_file = MacroProfileStore.PROFILE_FILE if source is profile_data else MacroProfileStore.GENERAL_FILE
        if errors and (source_file in errors or MacroProfileStore.GENERAL_FILE in errors):
            return False
        quest_slot = source.pop("quest_gumdrop_slot")
        uses_field_goo = any(isinstance(field, dict) and field.get("goo") for field in fields_data.values())
        if profile_data.get("quest_use_gumdrops") and not uses_field_goo:
            general_data["goo_slot"] = quest_slot
        return True

    def _normalize_fields(self, fields_data):
        original = copy.deepcopy(fields_data)
        if not isinstance(fields_data, dict):
            fields_data = {}
        for field, defaults in self._field_defaults.items():
            current = fields_data.get(field)
            if not isinstance(current, dict):
                fields_data[field] = copy.deepcopy(defaults)
                continue
            for key, value in defaults.items():
                current.setdefault(key, copy.deepcopy(value))
            fields_data[field] = self._normalize_field(field, current)
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

    @staticmethod
    def _write_file(path, data, fields=False):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if fields:
            content = str(data)
        else:
            content = "\n".join(f"{key}={value}" for key, value in data.items())
        if content and not content.endswith("\n"):
            content += "\n"
        descriptor, temporary = tempfile.mkstemp(prefix=".macro_profile_", suffix=".tmp", dir=os.path.dirname(path))
        try:
            with os.fdopen(descriptor, "w") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        except Exception:
            try:
                os.remove(temporary)
            except OSError:
                pass
            raise

    @staticmethod
    def _read_bytes(path):
        if not os.path.exists(path):
            return None
        with open(path, "rb") as handle:
            return handle.read()

    @staticmethod
    def _restore_bytes(path, content):
        if content is None:
            try:
                os.remove(path)
            except FileNotFoundError:
                pass
            return
        descriptor, temporary = tempfile.mkstemp(prefix=".macro_profile_rollback_", suffix=".tmp", dir=os.path.dirname(path))
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        except Exception:
            try:
                os.remove(temporary)
            except OSError:
                pass
            raise
