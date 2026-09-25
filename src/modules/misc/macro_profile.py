"""Reads, migrates, validates, and saves Macro Profiles.

Callers get plain dicts and make validated changes. File names, parsing, repair, migration,
locking, and atomic replacement stay inside this module.
"""

from __future__ import annotations

import ast
import copy
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
    MIGRATIONS = ("_migrate_legacy_settings",)

    def __init__(self, profiles_dir, profile_defaults, general_defaults, field_defaults, field_normalizer=None):
        self._profiles_dir = os.path.abspath(profiles_dir)
        self._profile_defaults = copy.deepcopy(profile_defaults)
        self._general_defaults = copy.deepcopy(general_defaults)
        self._field_defaults = copy.deepcopy(field_defaults)
        self._field_normalizer = field_normalizer
        self._lock = threading.RLock()

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

    def apply_change(self, profile, scope, setting, value):
        """Validate and save one setting. Returns all settings (profile and general) after the change."""
        with self._lock, self._file_lock(profile):
            profile_data, general_data, _, errors, _, _ = self._read_and_normalize(profile)
            owner = self._owner(setting, scope)
            filename = self.PROFILE_FILE if owner == "profile" else self.GENERAL_FILE
            self._refuse_overwrite(errors, filename)

            defaults = self._profile_defaults if owner == "profile" else self._general_defaults
            self._validate(setting, value, defaults, {**profile_data, **general_data})
            target = profile_data if owner == "profile" else general_data
            target[setting] = copy.deepcopy(value)
            self._write_file(os.path.join(self._profile_dir(profile), filename), target)
            return {**profile_data, **general_data}

    def apply_changes(self, profile, scope, changes):
        """Validate every change first, then save them."""
        if not isinstance(changes, dict):
            raise MacroProfileValidationError("changes", "expected an object")
        with self._lock, self._file_lock(profile):
            profile_data, general_data, _, errors, _, _ = self._read_and_normalize(profile)
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
                self._write_file(os.path.join(profile_dir, self.PROFILE_FILE), next_profile)
            if next_general != general_data:
                self._write_file(os.path.join(profile_dir, self.GENERAL_FILE), next_general)

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
        warnings = []
        profile_dir = self._profile_dir(profile)
        errors = {}
        changed = {}
        profile_data = self._safe_read(os.path.join(profile_dir, self.PROFILE_FILE), self._profile_defaults, errors, warnings)
        general_data = self._safe_read(os.path.join(profile_dir, self.GENERAL_FILE), self._general_defaults, errors, warnings)
        fields_data = self._safe_read_fields(os.path.join(profile_dir, self.FIELDS_FILE), errors)

        profile_data, general_data, settings_changed = self._normalize_settings(profile_data, general_data)
        fields_data, fields_changed = self._normalize_fields(fields_data)
        changed[self.PROFILE_FILE] = settings_changed[0]
        changed[self.GENERAL_FILE] = settings_changed[1]
        changed[self.FIELDS_FILE] = fields_changed
        return profile_data, general_data, fields_data, errors, changed, warnings

    def _safe_read(self, path, defaults, errors, warnings):
        if not os.path.exists(path):
            return copy.deepcopy(defaults)
        try:
            return self._read_settings_file(path, defaults, warnings)
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
            try:
                parsed = ast.literal_eval(value)
            except Exception:
                parsed = value
                # Text where a number or true/false belongs would break the macro later, so use
                # the default. Other settings keep text: the GUI saves some as plain text.
                if isinstance(default, bool) and value.lower() in ("true", "false"):
                    parsed = value.lower() == "true"
                elif isinstance(default, (bool, int, float)):
                    warnings.append(f"{os.path.basename(path)}: {key}={value!r} is not a valid value; using the default ({default!r})")
                    parsed = copy.deepcopy(default)
            if isinstance(parsed, dict) and set(parsed) == {"source", "value"}:
                parsed = parsed["value"]  # an old GUI bug saved some dropdowns wrapped like this
            if isinstance(default, str) and not isinstance(parsed, str):
                parsed = "" if parsed is None else str(parsed)
            result[key] = parsed
        return result

    def _normalize_settings(self, profile_data, general_data):
        original_profile = copy.deepcopy(profile_data)
        original_general = copy.deepcopy(general_data)
        for key, value in self._profile_defaults.items():
            profile_data.setdefault(key, copy.deepcopy(value))
        for key, value in self._general_defaults.items():
            general_data.setdefault(key, copy.deepcopy(value))
        return profile_data, general_data, (profile_data != original_profile, general_data != original_general)

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

        self._merge_quest_gumdrop_slot(profile_data, general_data, fields_data)
        return profile_data != original_profile, general_data != original_general

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

    @classmethod
    def _write_file(cls, path, data, fields=False):
        if fields:
            content = str(data)
        else:
            content = "\n".join(f"{key}={value}" for key, value in data.items())
        if content and not content.endswith("\n"):
            content += "\n"
        cls._atomic_write(path, content.encode("utf-8"))

    @staticmethod
    def _atomic_write(path, content):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=".macro_profile_", suffix=".tmp", dir=os.path.dirname(path))
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
