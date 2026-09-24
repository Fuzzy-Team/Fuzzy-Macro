import os
import tempfile
import threading
import unittest
from unittest import mock

from src.modules.misc.macro_profile import (
    MacroProfileError,
    MacroProfileStore,
    MacroProfileValidationError,
)


PROFILE_DEFAULTS = {
    "enabled": True,
    "count": 1,
    "fields": ["pine tree"] * 5,
    "fields_enabled": [True, False, False, False, False],
    "task_priority_order": ["collect_sticker_printer"],
}
GENERAL_DEFAULTS = {
    "macro_mode": "normal",
    "max_cannon_attempts": 5,
    "cannon_hive_resync_attempts": 2,
}
FIELD_DEFAULTS = {"pine tree": {"shape": "lines", "mins": 10}}


class MacroProfileStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.profiles_dir = os.path.join(self.temp_dir.name, "profiles")
        self.store = MacroProfileStore(
            self.profiles_dir,
            PROFILE_DEFAULTS,
            GENERAL_DEFAULTS,
            FIELD_DEFAULTS,
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def path(self, profile, filename):
        return os.path.join(self.profiles_dir, profile, filename)

    def write(self, profile, filename, content):
        path = self.path(profile, filename)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as handle:
            handle.write(content)
        return path

    @staticmethod
    def read(path):
        with open(path) as handle:
            return handle.read()

    def test_initialize_migrates_legacy_modes_and_missing_defaults(self):
        self.write("main", "settings.txt", "enabled=False\n")
        self.write("main", "generalsettings.txt", "field_only_mode=True\n")
        snapshot = self.store.initialize("main").as_dict()
        self.assertEqual(snapshot["settings"]["macro_mode"], "field")
        self.assertEqual(snapshot["settings"]["count"], 1)
        with open(self.path("main", "generalsettings.txt")) as handle:
            persisted = handle.read()
        self.assertIn("macro_mode=field", persisted)
        self.assertNotIn("field_only_mode", persisted)

    def test_initialize_removes_obsolete_hive_claim_choice(self):
        self.write("main", "generalsettings.txt", "hive_claim_method=check\n")
        snapshot = self.store.initialize("main").as_dict()
        self.assertNotIn("hive_claim_method", snapshot["settings"])
        self.assertNotIn("hive_claim_method", self.read(self.path("main", "generalsettings.txt")))

    def test_malformed_source_is_preserved_and_reported(self):
        source = self.write("main", "settings.txt", "this is not a setting\n")
        before = self.read(source)
        snapshot = self.store.initialize("main").as_dict()
        self.assertEqual(self.read(source), before)
        self.assertEqual(snapshot["settings"]["enabled"], True)
        self.assertTrue(any("settings.txt" in error for error in snapshot["migration_errors"]))

    def test_unknown_keys_survive_initialization_and_changes(self):
        self.write("main", "settings.txt", "enabled=True\nfuture_key={'x': 1}\n")
        self.store.initialize("main")
        self.store.apply_change("main", "profile", "count", 3)
        snapshot = self.store.snapshot("main").as_dict()
        self.assertEqual(snapshot["settings"]["future_key"], {"x": 1})

    def test_invalid_change_does_not_advance_snapshot_or_file(self):
        first = self.store.initialize("main")
        path = self.path("main", "generalsettings.txt")
        before = self.read(path)
        with self.assertRaises(MacroProfileValidationError):
            self.store.apply_change("main", "general", "max_cannon_attempts", 30)
        self.assertEqual(self.read(path), before)
        self.assertEqual(self.store.snapshot("main").version, first.version)

    def test_values_are_saved_in_the_format_the_gui_sends(self):
        self.store.initialize("main")
        self.store.apply_change("main", "profile", "count", "12")
        self.store.apply_change("main", "profile", "fields", "pine tree,sunflower")
        settings = self.store.snapshot("main").as_dict()["settings"]
        self.assertEqual(settings["count"], 12)
        self.assertEqual(settings["fields"], "pine tree,sunflower")

    def test_settings_without_defaults_save_to_the_requested_file(self):
        # GUI-only settings such as gui_theme have no default entry
        self.store.initialize("main")
        self.store.apply_change("main", "general", "gui_theme", "Midnight")
        self.assertIn("gui_theme=Midnight", self.read(self.path("main", "generalsettings.txt")))
        self.assertEqual(self.store.snapshot("main").as_dict()["settings"]["gui_theme"], "Midnight")

    def test_values_saved_wrapped_by_an_old_gui_bug_are_unwrapped(self):
        self.write("main", "generalsettings.txt", "macro_mode={'source': 'generalsettings.txt', 'value': 'quest'}\n")
        self.assertEqual(self.store.initialize("main").as_dict()["settings"]["macro_mode"], "quest")

    def gumdrop_store(self, profile_settings, fields):
        self.write("main", "settings.txt", profile_settings)
        self.write("main", "generalsettings.txt", "goo_slot=3\n")
        self.write("main", "fields.txt", repr(fields))
        return MacroProfileStore(self.profiles_dir, {**PROFILE_DEFAULTS, "quest_use_gumdrops": False}, {**GENERAL_DEFAULTS, "goo_slot": 3}, FIELD_DEFAULTS)

    def test_quest_gumdrop_slot_is_used_when_only_goo_quests_use_gumdrops(self):
        store = self.gumdrop_store("quest_use_gumdrops=True\nquest_gumdrop_slot=6\n", {"pine tree": {"shape": "lines", "mins": 10, "goo": False}})
        settings = store.initialize("main").as_dict()["settings"]
        self.assertEqual(settings["goo_slot"], 6)
        self.assertNotIn("quest_gumdrop_slot", settings)
        self.assertNotIn("quest_gumdrop_slot", self.read(self.path("main", "settings.txt")))

    def test_quest_gumdrop_slot_is_retained_when_general_settings_are_malformed(self):
        self.write("main", "settings.txt", "quest_use_gumdrops=True\nquest_gumdrop_slot=6\n")
        self.write("main", "generalsettings.txt", "this is not a setting\n")
        store = MacroProfileStore(
            self.profiles_dir,
            {**PROFILE_DEFAULTS, "quest_use_gumdrops": False},
            {**GENERAL_DEFAULTS, "goo_slot": 3},
            FIELD_DEFAULTS,
        )
        snapshot = store.initialize("main").as_dict()
        self.assertIn("generalsettings.txt", " ".join(snapshot["migration_errors"]))
        self.assertIn("quest_gumdrop_slot=6", self.read(self.path("main", "settings.txt")))

    def test_goo_slot_is_kept_when_fields_use_goo(self):
        store = self.gumdrop_store("quest_use_gumdrops=True\nquest_gumdrop_slot=6\n", {"pine tree": {"shape": "lines", "mins": 10, "goo": True}})
        self.assertEqual(store.initialize("main").as_dict()["settings"]["goo_slot"], 3)

    def test_goo_slot_is_kept_when_goo_quests_are_off(self):
        store = self.gumdrop_store("quest_use_gumdrops=False\nquest_gumdrop_slot=6\n", {"pine tree": {"shape": "lines", "mins": 10}})
        settings = store.initialize("main").as_dict()["settings"]
        self.assertEqual(settings["goo_slot"], 3)
        self.assertNotIn("quest_gumdrop_slot", settings)

    def test_default_legacy_quest_gather_keeps_per_quest_settings(self):
        self.write("main", "settings.txt", "quest_gather_mins=0\npolar_bear_quest_gather_mins=5\n")
        store = MacroProfileStore(self.profiles_dir, {**PROFILE_DEFAULTS, "quest_gather_mins": 0, "polar_bear_quest_gather_mins": 2}, GENERAL_DEFAULTS, FIELD_DEFAULTS)
        settings = store.initialize("main").as_dict()["settings"]
        self.assertEqual(settings["polar_bear_quest_gather_mins"], 5)
        self.assertEqual(store.snapshot("main").as_dict()["settings"]["polar_bear_quest_gather_mins"], 5)

    def test_configured_legacy_quest_gather_migrates_once(self):
        self.write("main", "settings.txt", "quest_gather_mins=7\npolar_bear_quest_gather_mins=5\n")
        store = MacroProfileStore(self.profiles_dir, {**PROFILE_DEFAULTS, "quest_gather_mins": 0, "polar_bear_quest_gather_mins": 2}, GENERAL_DEFAULTS, FIELD_DEFAULTS)
        self.assertEqual(store.initialize("main").as_dict()["settings"]["polar_bear_quest_gather_mins"], 7)
        store.apply_change("main", "profile", "polar_bear_quest_gather_mins", 3)
        self.assertEqual(store.snapshot("main").as_dict()["settings"]["polar_bear_quest_gather_mins"], 3)

    def test_failed_atomic_replace_keeps_file_and_snapshot(self):
        first = self.store.initialize("main")
        path = self.path("main", "settings.txt")
        before = self.read(path)
        with mock.patch("src.modules.misc.macro_profile.os.replace", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.store.apply_change("main", "profile", "count", 2)
        self.assertEqual(self.read(path), before)
        self.assertEqual(self.store.snapshot("main").version, first.version)

    def test_concurrent_unrelated_changes_both_survive(self):
        self.store.initialize("main")
        errors = []

        def change(scope, setting, value):
            try:
                self.store.apply_change("main", scope, setting, value)
            except Exception as exc:  # pragma: no cover - asserted below
                errors.append(exc)

        threads = [
            threading.Thread(target=change, args=("profile", "count", 7)),
            threading.Thread(target=change, args=("general", "macro_mode", "quest")),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(errors, [])
        snapshot = self.store.snapshot("main").as_dict()
        self.assertEqual(snapshot["settings"]["count"], 7)
        self.assertEqual(snapshot["settings"]["macro_mode"], "quest")

    def test_switching_profiles_publishes_distinct_versioned_snapshot(self):
        main = self.store.initialize("main")
        self.store.apply_change("main", "profile", "count", 4)
        alt = self.store.initialize("alt")
        self.assertEqual(alt.profile, "alt")
        self.assertGreater(alt.version, main.version)
        self.assertEqual(alt.as_dict()["settings"]["count"], 1)

    def test_snapshot_is_immutable(self):
        snapshot = self.store.initialize("main")
        with self.assertRaises(TypeError):
            snapshot.settings["count"] = 9

    def test_read_falls_back_to_defaults_unless_strict(self):
        self.write("main", "settings.txt", "this is not a setting\n")
        profile_data, general_data, fields = self.store.read("main")
        self.assertEqual(profile_data["enabled"], True)
        self.assertEqual(general_data["macro_mode"], "normal")
        self.assertIn("pine tree", fields)
        with self.assertRaises(MacroProfileError):
            self.store.read("main", strict=True)

    def test_snapshot_read_has_no_file_side_effects(self):
        self.store.initialize("main")
        paths = [
            self.path("main", "settings.txt"),
            self.path("main", "generalsettings.txt"),
            self.path("main", "fields.txt"),
        ]
        before = {path: (os.stat(path).st_mtime_ns, self.read(path)) for path in paths}
        self.store.snapshot("main")
        after = {path: (os.stat(path).st_mtime_ns, self.read(path)) for path in paths}
        self.assertEqual(after, before)

    def test_transactional_import_validates_before_writing(self):
        self.store.initialize("main")
        path = self.path("main", "generalsettings.txt")
        before = self.read(path)
        with self.assertRaises(MacroProfileValidationError):
            self.store.apply_changes("main", "general", {"macro_mode": "quest", "max_cannon_attempts": 0})
        self.assertEqual(self.read(path), before)

    def test_transactional_import_validates_cross_fields_against_final_state(self):
        self.store.initialize("main")
        self.store.apply_changes(
            "main",
            "general",
            {"max_cannon_attempts": 3, "cannon_hive_resync_attempts": 1},
        )
        settings = self.store.snapshot("main").as_dict()["settings"]
        self.assertEqual(settings["max_cannon_attempts"], 3)
        self.assertEqual(settings["cannon_hive_resync_attempts"], 1)

    def test_prefixed_max_convert_time_key_is_not_split(self):
        defaults = {**PROFILE_DEFAULTS, "max_convert_time": 10}
        store = MacroProfileStore(self.profiles_dir, defaults, GENERAL_DEFAULTS, FIELD_DEFAULTS)
        self.write("main", "settings.txt", "x_max_convert_time=5\nmax_convert_time=7\n")
        settings = store.initialize("main").as_dict()["settings"]
        self.assertEqual(settings["x_max_convert_time"], 5)
        self.assertEqual(settings["max_convert_time"], 7)

    def test_compatibility_save_adapter_delegates_to_deep_module(self):
        from src.modules.misc import settingsManager

        self.store.initialize("main")
        with mock.patch.object(settingsManager, "_macro_profile_store", self.store), mock.patch.object(settingsManager, "profileName", "main"):
            settingsManager.saveProfileSetting("count", 12)
            self.assertEqual(settingsManager.loadSettings()["count"], 12)

    def test_cannon_constraints_are_authoritative(self):
        self.store.initialize("main")
        with self.assertRaises(MacroProfileValidationError):
            self.store.apply_change("main", "general", "cannon_hive_resync_attempts", 5)

    def test_field_normalization_converts_numeric_strings(self):
        from src.modules.misc import settingsManager

        normalized = settingsManager.normalizeFieldSettings(
            "pine tree",
            {"shape": "lines", "distance": "7", "width": "4"},
            {"pine tree": {"shape": "lines", "distance": 1, "width": 4}},
        )

        self.assertEqual(normalized["distance"], 7)
        self.assertEqual(normalized["width"], 4)


if __name__ == "__main__":
    unittest.main()
