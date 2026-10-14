"""Home source parity and refresh contracts, without Tk or user settings I/O."""

import ast
import copy
import json
from pathlib import Path
import random
import runpy
import shutil
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from modules.gui import app as native
from modules.gui import configuration, editors, widgets
from test_gui_app import Checkbox, Choice, FAKE_TK
from test_gui_configuration import FAKE_TK as CONFIG_TK, Widget as ConfigWidget


DEFAULTS = runpy.run_path(str(ROOT / "src/modules/misc/settings_defaults.py"))
NODE = shutil.which("node")


def settings():
    result = copy.deepcopy(DEFAULTS["DEFAULT_PROFILE_SETTINGS"])
    result.update(copy.deepcopy(DEFAULTS["DEFAULT_GENERAL_SETTINGS"]))
    return result


class MemoryWidget(object):
    """Track widget lifetime and actual pack order rather than mock call order."""

    def __init__(self, master=None, **options):
        self.master = master
        self.options = options
        self.children = []
        self.packed = []
        self.manager = ""
        self.exists = True
        self.bindings = {}
        if isinstance(master, MemoryWidget):
            master.children.append(self)

    def winfo_children(self):
        return list(self.children)

    def winfo_exists(self):
        return self.exists

    def winfo_manager(self):
        return self.manager

    def pack(self, **options):
        self.pack_forget()
        self.manager = "pack"
        if isinstance(self.master, MemoryWidget):
            before = options.get("before")
            index = self.master.packed.index(before) if before else len(self.master.packed)
            self.master.packed.insert(index, self)

    def pack_forget(self):
        self.manager = ""
        if isinstance(self.master, MemoryWidget) and self in self.master.packed:
            self.master.packed.remove(self)

    def destroy(self):
        for child in list(self.children):
            child.destroy()
        self.pack_forget()
        self.exists = False
        if isinstance(self.master, MemoryWidget):
            self.master.children.remove(self)

    def configure(self, **options):
        self.options.update(options)

    def bind(self, event, callback, **options):
        self.bindings[event] = callback

    def grid(self, **options):
        self.manager = "grid"

    def columnconfigure(self, *args, **options):
        pass


def control(parent, value):
    current = [value]
    variable = SimpleNamespace(get=lambda: current[0], set=lambda value: current.__setitem__(0, value))
    return widgets.Control(MemoryWidget(parent), variable)


def make_app():
    app = native.NativeApp.__new__(native.NativeApp)
    app.settings = settings()
    stored = copy.deepcopy(app.settings)
    app.fields = copy.deepcopy(DEFAULTS["DEFAULT_FIELDS"])
    app.profile = "default"
    app.palette = widgets.palette(app.settings.get("gui_theme"))
    app.root = Mock()
    app.root.focus_get.return_value = None
    app.manager = Mock()
    app.manager.loadAllSettings.side_effect = lambda: copy.deepcopy(stored)
    app.manager.loadFields.side_effect = lambda: copy.deepcopy(DEFAULTS["DEFAULT_FIELDS"])
    app.manager.getCurrentProfile.return_value = "default"
    app.controls, app.control_groups, app.rows, app.pages = {}, {}, {}, {}
    app.recording = None
    app.build_shell, app.configure_styles, app.stop_recording = Mock(), Mock(), Mock()
    app.refresh_home, app.update_conditions, app.load_gather_field = Mock(), Mock(), Mock()
    app.action, app.status = Mock(), Mock()
    app.card = lambda parent, title, *args: MemoryWidget(parent, text=title)
    app.label = lambda parent, text, **options: MemoryWidget(parent, text=text, **options)
    app.button = lambda parent, text, command: MemoryWidget(parent, text=text, command=command)

    def add_control(parent, spec, value=None, onchange=None):
        item = control(parent, app.settings.get(spec["id"]) if value is None else value)
        item.spec, item.onchange = spec, onchange
        app.controls[spec["id"]] = item
        if spec.get("scope") not in ("local", "field"):
            app.control_groups.setdefault(spec["id"], []).append(item)
        return item

    def save(key, value, scope="profile"):
        app.settings[key] = stored[key] = value

    app.add_control, app.save = add_control, save
    return app, stored


def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)


def web_tasks(cases):
    """Run shipped loadTasks up to its independent timer section.

    taskHTML captures rows instead of creating DOM markup. Description casing
    and image-to-text conversion use the shipped helpers for both data sets,
    so the comparison covers text/order while native icon rendering is tested
    separately. No settings manager, browser hooks, or timers run.
    """
    home = (ROOT / "src/webapp/scripts/tabs/home.js").read_text(encoding="utf-8")
    load = home[home.index("async function loadTasks() {"):home.index("  //planter timers")]
    utilities = (ROOT / "src/webapp/scripts/utilities.js").read_text(encoding="utf-8")
    title_case = utilities[utilities.index("function toTitleCase("):utilities.index("//javascript function to remove html tags")]
    emojis = (ROOT / "src/webapp/scripts/emojis.js").read_text(encoding="utf-8")
    script = title_case + emojis + "\n" + load + "\n}\n" + r"""
let currentSettings, rows;
const isUserChangingMode = false;
const document = {getElementById: id => id === "task-list" ? {} : null};
async function loadAllSettings() { return currentSettings; }
function displayText(desc) {
  return (desc.includes("<img") ? desc : toTitleCase(desc))
    .replace(/<br\s*\/?>/gi, "\n").replace(/<[^>]*>/g, "").trim();
}
function taskHTML(title, desc = "") {
  rows.push([title, displayText(desc)]);
  return "";
}
async function run(cases) {
  const result = [];
  for (const [data, nativeRows] of cases) {
    currentSettings = data;
    rows = [];
    await loadTasks();
    result.push({web: rows, native: nativeRows.map(([title, desc]) => [title, displayText(desc)])});
  }
  process.stdout.write(JSON.stringify(result));
}
"""
    script += "\nrun(" + json.dumps(cases) + ").catch(error => {console.error(error); process.exit(1);});"
    result = subprocess.run([NODE, "-"], input=script, check=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, universal_newlines=True, cwd=str(ROOT), timeout=15)
    return json.loads(result.stdout)


@unittest.skipUnless(NODE, "Node is required for the shipped Home source differential")
class HomeSourceTests(unittest.TestCase):
    def assert_source_rows(self, cases):
        app, _ = make_app()
        inputs = []
        for data in cases:
            app.settings = data
            inputs.append([data, app.home_tasks()])
        for index, (data, result) in enumerate(zip(cases, web_tasks(inputs))):
            with self.subTest(case=index, mode=data["macro_mode"], has_priorities=bool(data.get("task_priority_order"))):
                self.assertEqual(result["native"], result["web"])

    def test_real_defaults_in_all_five_modes(self):
        cases = []
        for mode in ("normal", "alt", "field", "quest", "bug"):
            data = settings()
            data["macro_mode"] = mode
            cases.append(data)
        self.assert_source_rows(cases)

    def test_random_enabled_tasks_priorities_and_duplicate_fields(self):
        rng = random.Random(118)
        cases = []
        for mode in ("normal", "alt", "field", "quest", "bug"):
            for _ in range(10):
                data = settings()
                for key, value in list(data.items()):
                    if isinstance(value, bool):
                        data[key] = bool(rng.getrandbits(1))
                data.update(macro_mode=mode, planters_mode=rng.randrange(3), blender_enable=True,
                            fields=["pine tree", "sunflower", "pine tree", "blue flower", "sunflower"],
                            fields_enabled=[bool(rng.getrandbits(1)) for _ in range(5)],
                            blender_item_1="red extract", blender_item_2="oil", blender_item_3="red extract")
                rng.shuffle(data["task_priority_order"])
                # Duplicated priority IDs retain the reference's repeated rows.
                data["task_priority_order"].insert(0, "gather_pine_tree")
                cases.append(data)
        self.assert_source_rows(cases)

    def test_empty_and_missing_priorities_use_each_modes_source_fallback(self):
        cases = []
        for mode in ("normal", "alt", "field", "quest", "bug"):
            for missing in (False, True):
                data = settings()
                data.update(macro_mode=mode, fields=["pine tree", "sunflower", "pine tree", "rose", "rose"],
                            fields_enabled=[True, True, True, False, True], task_priority_order=[])
                if missing:
                    del data["task_priority_order"]
                cases.append(data)
        self.assert_source_rows(cases)

    def test_prioritized_boosters_keep_generic_collect_branch(self):
        data = settings()
        data.update(macro_mode="normal", blue_booster=True, red_booster=True, mountain_booster=True,
                    task_priority_order=["collect_mountain_booster", "collect_blue_booster", "collect_red_booster"])
        self.assert_source_rows([data])
        app, _ = make_app()
        app.settings = data
        self.assertEqual(app.home_tasks(), [("Collect", "Mountain Booster"),
                                          ("Collect", "Blue Booster"), ("Collect", "Red Booster")])

    def test_special_collect_names_emojis_and_rhino_spelling(self):
        data = settings()
        data.update(macro_mode="normal", mondo_buff=True, sprouts_enable=True, sticker_sprout_watch=True,
                    gingerbread=True, rhinobeetle=True,
                    task_priority_order=["mondo_buff", "collect_sprouts", "collect_sticker_sprout",
                                         "collect_gingerbread", "kill_rhinobeetle"])
        self.assert_source_rows([data])

    def test_legacy_fallback_order_icons_and_booster_titles(self):
        data = settings()
        for key, value in list(data.items()):
            if isinstance(value, bool):
                data[key] = True
        data.update(macro_mode="normal", task_priority_order=[], planters_mode=2,
                    blender_item_1="red extract", blender_item_2="oil", blender_item_3="red extract",
                    fields=["sunflower"] * 5, fields_enabled=[True] * 5)
        self.assert_source_rows([data])


class RefreshTests(unittest.TestCase):
    def test_missing_settings_keep_initial_controls_and_action_buttons_do_not_refresh(self):
        app, stored = make_app()
        app.add_control = native.NativeApp.add_control.__get__(app)
        button_spec = next(spec for sub in native.TAB_DEFINITIONS['collect'] for section in sub['sections']
                           for spec in section['controls'] if spec['id'] == 'configure-sprout-ai-tokens-button')
        with patch.object(native, 'tk', FAKE_TK), patch.object(widgets, 'Choice', Choice):
            app.add_control(ConfigWidget(), button_spec)
            choice = app.add_control(ConfigWidget(), dict(id='webhook_time_format', kind='dropdown',
                                     scope='general', choices=[dict(label='12-hour', value='12h')]))
            checkbox = control(None, False)
            app.controls['discord_rich_presence'] = checkbox
            app.control_groups['discord_rich_presence'] = [checkbox]
            app.refresh()
            self.assertNotIn(button_spec['id'], app.control_groups)
            self.assertEqual(choice.get(), 'none')
            self.assertIs(checkbox.get(), False)
            stored.update(discord_rich_presence=True, webhook_time_format='24h')
            app.refresh()
            self.assertIs(checkbox.get(), True)
            self.assertEqual(choice.get(), '24h')
        app.manager.saveGeneralSetting.assert_not_called()

    def test_ordinary_refresh_preserves_pages_widgets_and_focused_edit(self):
        app, stored = make_app()
        page = MemoryWidget()
        app.pages = {"gather": page, "planters": MemoryWidget()}
        app.refresh_planters = Mock()
        app.field_slot = 0
        app.field_name = stored["fields"][0]
        app.field_data = copy.deepcopy(app.fields[app.field_name])
        app.add_control(page, dict(id="field_enable", scope="local"), value=stored["fields_enabled"][0])
        focused = app.add_control(page, dict(id="move_speed"), value="typing 2.")
        first = app.add_control(page, dict(id="hive_number"), value=1)
        second = app.add_control(page, dict(id="hive_number"), value=1)
        recording = app.add_control(page, dict(id="start_keybind"), value="Listening...")
        app.recording = "start_keybind"
        app.root.focus_get.return_value = focused.widget
        stored.update(move_speed=99, hive_number=4, start_keybind="F8")
        groups, pages = app.control_groups, app.pages
        for _ in range(3):
            app.refresh()
        self.assertIs(app.pages, pages)
        self.assertIs(app.control_groups, groups)
        self.assertEqual(focused.get(), "typing 2.")
        self.assertEqual(recording.get(), "Listening...")
        self.assertEqual([first.get(), second.get()], [4, 4])
        self.assertTrue(all(item.widget.winfo_exists() for item in (focused, first, second, recording)))
        app.load_gather_field.assert_not_called()
        app.build_shell.assert_not_called()
        app.configure_styles.assert_not_called()
        self.assertEqual(app.refresh_planters.call_count, 3)
        self.assertEqual(app.update_conditions.call_count, 3)
        self.assertEqual(app.refresh_home.call_count, 3)

    def test_real_custom_forms_reload_children_and_task_priorities(self):
        app, stored = make_app()
        app.active_tab, app.subtab_selection = "setting", {}
        app.card = lambda parent, title, *args: ConfigWidget(parent, text=title)
        app.add_control = native.NativeApp.add_control.__get__(app)
        specs = [spec for tabs in native.TAB_DEFINITIONS.values() for tab in tabs
                 for section in tab["sections"] for spec in section["controls"]
                 if spec.get("action") in ("quest_overrides", "hotbar", "task_priorities")]
        self.assertEqual({spec["action"] for spec in specs},
                         {"quest_overrides", "hotbar", "task_priorities"})
        with patch.object(native, "tk", FAKE_TK), patch.object(configuration, "tk", CONFIG_TK), \
                patch.object(configuration, "rounded_image", return_value=None), \
                patch.object(widgets, "Choice", Choice):
            app.form(ConfigWidget(), [dict(title=spec["title"], controls=[spec]) for spec in specs])
            self.assertIn("quest_overrides", app.controls)
            self.assertIn("hotbar", app.controls)
            self.assertNotIn("quest_overrides", app.control_groups)
            self.assertNotIn("hotbar", app.control_groups)
            priority = app.controls["task_priority_order"]
            self.assertEqual(app.control_groups["task_priority_order"], [priority])
            children = [spec for row in configuration.CUSTOM_DEFINITIONS["quest_overrides"]["rows"]
                        for spec in row["controls"]]
            children += [spec for section in configuration.CUSTOM_DEFINITIONS["hotbar"]["sections"]
                         for spec in section["controls"]]
            for spec in children:
                self.assertEqual(app.control_groups[spec["id"]], [app.controls[spec["id"]]])
            stored.update(polar_bear_quest_gather_mins="7.5", polar_bear_quest_gather_return="walk",
                          hotbar1_use_every_value="42", hotbar1_use_when="always",
                          task_priority_order=["collect_blue_booster", "gather_pine_tree"])
            app.refresh()
            self.assertEqual(app.controls["polar_bear_quest_gather_mins"].get(), "7.5")
            self.assertEqual(app.controls["polar_bear_quest_gather_return"].get(), "walk")
            self.assertEqual(app.controls["hotbar1_use_every_value"].get(), "42")
            self.assertEqual(app.controls["hotbar1_use_when"].get(), "always")
            self.assertEqual(priority.get(), stored["task_priority_order"])
            self.assertEqual(app.controls["hotbar"].get(), 1)
        app.manager.saveProfileSetting.assert_not_called()
        app.manager.saveDictProfileSettings.assert_not_called()
        app.build_shell.assert_not_called()

    def test_refresh_reloads_real_gather_controls_and_enabled_array_without_saving(self):
        app, stored = make_app()
        app.pages = {"gather": MemoryWidget()}
        app.field_slot = 1
        app.settings["fields_enabled"][1] = stored["fields_enabled"][1] = True
        app.field_name = stored["fields"][1]
        app.field_data = copy.deepcopy(app.fields[app.field_name])
        fields = copy.deepcopy(app.fields)
        app.manager.loadFields.side_effect = lambda: copy.deepcopy(fields)
        app.field_buttons = [Mock() for _ in stored["fields"]]
        app.gather_sections = {"Gather Field": SimpleNamespace(heading=MemoryWidget())}
        app.load_gather_field = native.NativeApp.load_gather_field.__get__(app)
        app.add_control = native.NativeApp.add_control.__get__(app)
        specs = [spec for section in native.TAB_DEFINITIONS["gather"][0]["sections"]
                 for spec in section["controls"] if spec["id"] in ("field", "field_enable", "mins")]
        with patch.object(native, "tk", FAKE_TK), \
                patch.object(widgets, "Checkbox", Checkbox), patch.object(widgets, "Choice", Choice):
            for spec in specs:
                value = (app.field_name if spec["id"] == "field" else
                         stored["fields_enabled"][1] if spec["id"] == "field_enable" else app.field_data["mins"])
                app.add_control(FAKE_TK.Frame(), spec, value=value)
            app.add_control(FAKE_TK.Frame(), dict(id="hive_number", kind="textbox", scope="general"), value="1")
            focused = app.add_control(FAKE_TK.Frame(), dict(id="hive_number", kind="textbox", scope="general"), value="typing")
            app.root.focus_get.return_value = focused.widget
            dead = app.add_control(FAKE_TK.Frame(), dict(id="move_speed", kind="textbox", scope="general"), value="old")
            dead.widget.winfo_exists = Mock(return_value=False)
            stored.update(hive_number="4", move_speed="99")
            stored["fields_enabled"][0] = True
            stored["fields_enabled"][1] = False
            # Alias keys must never overwrite the selected field or its enable flag.
            stored.update(field="rose", field_enable=True)
            app.refresh()
            self.assertIs(app.controls["field_enable"].get(), False)
            self.assertEqual(app.controls["field"].get(), app.field_name)
            self.assertEqual(app.control_groups["hive_number"][0].get(), "4")
            self.assertEqual(focused.get(), "typing")
            self.assertEqual(dead.get(), "old")
            stored["fields_enabled"][1] = True
            app.refresh()
            self.assertIs(app.controls["field_enable"].get(), True)
            stored["fields"][1] = "pine tree"
            fields["pine tree"]["mins"] = "17.5"
            stored["fields_enabled"][1] = True
            app.refresh()
            self.assertIs(app.controls["field_enable"].get(), True)
            self.assertEqual(app.controls["field"].get(), "pine tree")
            self.assertEqual(app.controls["mins"].get(), "17.5")
            app.controls["mins"].widget.bindings["<FocusOut>"]()
        app.manager.saveProfileSetting.assert_not_called()
        app.manager.saveGeneralSetting.assert_not_called()
        app.manager.saveField.assert_not_called()
        app.build_shell.assert_not_called()

    def test_profile_or_theme_change_rebuilds_once_then_refreshes_in_place(self):
        for change in ("profile", "theme"):
            with self.subTest(change=change):
                app, stored = make_app()
                app._tasks, app._log_signature = [("old", "task")], "old logs"
                if change == "profile":
                    app.manager.getCurrentProfile.return_value = "imported"
                else:
                    stored["gui_theme"] = "purple"
                app.refresh()
                app.build_shell.assert_called_once_with()
                app.configure_styles.assert_called_once_with()
                app.stop_recording.assert_called_once_with()
                self.assertIsNone(app._tasks)
                self.assertIsNone(app._log_signature)
                app.refresh()
                app.build_shell.assert_called_once_with()
                app.refresh_home.assert_called_once_with()

    def test_walk_fallback_uses_live_field_return_and_restores_original_row_order(self):
        app, _ = make_app()
        parent = MemoryWidget()
        before, fallback, after = [MemoryWidget(parent) for _ in range(3)]
        for row in parent.children:
            row.pack(fill="x")
        app.rows = {"use_whirlwig_fallback": fallback}
        app.controls["use_whirlwig_fallback"] = control(fallback, False)
        app.controls["return"] = control(None, "walk")
        # Global settings disagree deliberately: return belongs to this field.
        app.settings["return"] = "reset"
        with patch.object(native.tk, "Entry", MemoryWidget):
            for return_mode in ("reset", "rejoin", "whirlwig", "walk", "reset", "walk"):
                app.controls["return"].set(return_mode)
                native.NativeApp.update_conditions(app)
                self.assertEqual(parent.packed, [before, fallback, after] if return_mode == "walk" else [before, after])
                self.assertTrue(fallback.winfo_exists())

    def test_import_off_to_auto_replaces_planter_content_and_keeps_unchanged_controls(self):
        app, stored = make_app()
        app.settings["planters_mode"] = stored["planters_mode"] = 0
        parent = MemoryWidget()
        app.pages = {"planters": parent}
        app.action.return_value = dict(gather=False)
        with patch.object(editors.tk, "Frame", MemoryWidget):
            editors.build_planters(app, parent)
            off = next(item for item in descendants(parent) if item.options.get("text") == "Planters are Off")
            mode = app.controls["planters_mode"]
            imported = dict(planters_mode=2, auto_planter_petal=True, planter_hotbar_petal_slot=4)
            payload = json.dumps(dict(settings=imported))

            def import_settings(text):
                self.assertEqual(text, payload)
                stored.update(json.loads(text)["settings"])
                return dict(success=True, imported_settings_count=len(imported))

            app.manager.importPlanterSettings.side_effect = import_settings
            dialog, text, scrollbar = MemoryWidget(), Mock(), Mock()
            text.get.return_value = payload
            with patch.object(editors, "_dialog", return_value=dialog), \
                    patch.object(editors.tk, "Text", return_value=text), \
                    patch.object(editors.ttk, "Scrollbar", return_value=scrollbar):
                editors._import_planters(app)
                button = next(item for item in descendants(dialog) if item.options.get("text") == "Import")
                button.options["command"]()
            app.manager.importPlanterSettings.assert_called_once_with(payload)
            self.assertFalse(dialog.winfo_exists())
            self.assertFalse(off.winfo_exists())
            self.assertTrue(any(item.options.get("text") == "Auto Planters / Planter+" for item in descendants(parent)))
            self.assertIs(app.controls["planters_mode"], mode)
            self.assertEqual(int(mode.get()), 2)
            maximum = app.controls["auto_max_planters"]
            hotbar = app.controls["planter_hotbar_petal_slot"]
            self.assertEqual(int(hotbar.get()), 4)
            for _ in range(3):
                app.refresh()
            self.assertIs(app.controls["auto_max_planters"], maximum)
            self.assertIs(app.controls["planter_hotbar_petal_slot"], hotbar)
            self.assertTrue(maximum.widget.winfo_exists())
            self.assertTrue(hotbar.widget.winfo_exists())
            stored["auto_planter_paper"] = True
            app.refresh()
            self.assertIn("planter_hotbar_paper_slot", app.controls)
            self.assertTrue(app.controls["planter_hotbar_paper_slot"].widget.winfo_exists())
            self.assertIs(app.controls["auto_max_planters"], maximum)
            app.build_shell.assert_not_called()

    def test_import_auto_to_auto_reloads_gather_from_planter_data_in_place(self):
        app, stored = make_app()
        app.settings["planters_mode"] = stored["planters_mode"] = 2
        data = dict(gather=False)
        app.actions = SimpleNamespace(getAutoPlanterData=Mock(side_effect=lambda: copy.deepcopy(data)))
        app.action = native.NativeApp.action.__get__(app)
        parent = MemoryWidget()
        app.pages = {"planters": parent}
        with patch.object(editors.tk, "Frame", MemoryWidget):
            editors.build_planters(app, parent)
            gather = app.controls["auto_planters_gather"]
            maximum = app.controls["auto_max_planters"]
            self.assertIs(gather.get(), False)
            self.assertNotIn("auto_planters_gather", app.control_groups)
            for enabled in (True, False):
                with self.subTest(gather=enabled):
                    payload = json.dumps(dict(settings=dict(planters_mode=2), auto_planters=dict(gather=enabled)))

                    def import_settings(text):
                        imported = json.loads(text)
                        stored.update(imported["settings"])
                        data.update(imported["auto_planters"])
                        return dict(success=True, imported_settings_count=1)

                    app.manager.importPlanterSettings.side_effect = import_settings
                    dialog, text = MemoryWidget(), Mock()
                    text.get.return_value = payload
                    app.actions.getAutoPlanterData.reset_mock()
                    with patch.object(editors, "_dialog", return_value=dialog), \
                            patch.object(editors.tk, "Text", return_value=text), \
                            patch.object(editors.ttk, "Scrollbar", return_value=Mock()):
                        editors._import_planters(app)
                        button = next(item for item in descendants(dialog) if item.options.get("text") == "Import")
                        button.options["command"]()
                    self.assertFalse(dialog.winfo_exists())
                    app.manager.importPlanterSettings.assert_called_with(payload)
                    app.actions.getAutoPlanterData.assert_called_once_with()
                    self.assertIs(gather.get(), enabled)
                    self.assertIs(app.controls["auto_planters_gather"], gather)
                    self.assertIs(app.controls["auto_max_planters"], maximum)
                    self.assertTrue(gather.widget.winfo_exists())
                    self.assertTrue(maximum.widget.winfo_exists())
                    self.assertNotIn("auto_planters_gather", stored)
            self.assertEqual(app.manager.importPlanterSettings.call_count, 2)
        app.build_shell.assert_not_called()

    def test_home_render_uses_item_icons_and_unchanged_tasks_keep_widgets(self):
        app, _ = make_app()
        app.settings.update(macro_mode="normal", blender_enable=True, sticker_stack=True,
                            task_priority_order=["blender", "collect_sticker_stack"],
                            blender_item_1="red extract", blender_item_2="oil", blender_item_3="red extract",
                            blender_item_4="none", blender_item_5="none")
        app.pages = {"home": MemoryWidget()}
        app.tasks_body = MemoryWidget()
        MemoryWidget(app.tasks_body, text="Tasks")
        MemoryWidget(app.tasks_body, text="description")
        app.start_button, app.mode_choice = Mock(), Mock()
        app.actions = Mock()
        app.actions.getRunState.return_value = 3
        app.render_logs, app.refresh_timers = Mock(), Mock()
        app.image = Mock(side_effect=lambda path, size: (path, size))
        with patch.object(native.tk, "Frame", MemoryWidget):
            native.NativeApp.refresh_home(app)
            icons = [(item.options["text"], item.options["image"]) for item in descendants(app.tasks_body)
                     if "image" in item.options]
            self.assertEqual(icons, [("Red Extract", ("assets/icons/red_extract.png", (20, 20))),
                                     ("Oil", ("assets/icons/oil.png", (20, 20))),
                                     ("Sticker Stack", ("assets/icons/sticker_stack.png", (20, 20)))])
            children = app.tasks_body.winfo_children()
            native.NativeApp.refresh_home(app)
            self.assertEqual(app.tasks_body.winfo_children(), children)
            self.assertTrue(all(item.winfo_exists() for item in children))
            self.assertEqual(app.image.call_count, 3)

    def test_file_uses_python_37_syntax(self):
        source = Path(__file__).read_text(encoding="utf-8")
        if sys.version_info >= (3, 8):
            ast.parse(source, feature_version=(3, 7))
        else:
            ast.parse(source)


if __name__ == "__main__":
    unittest.main()
