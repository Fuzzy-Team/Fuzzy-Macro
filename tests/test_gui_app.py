"""Headless regressions for native controls and the Tk/runtime boundary.

The native modules only define widgets on import. Backend functions are compiled
from their AST so neither gui.py nor the settings manager starts or writes data.
"""

import ast
import copy
import json
from pathlib import Path
import queue
import runpy
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from modules.gui import app as native
from modules.gui import widgets


class Variable(object):
    def __init__(self, master=None, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class Widget(object):
    """Only the widget operations used by textbox construction and recording."""

    def __init__(self, master=None, **options):
        self.master = master
        self.options = options
        self.bindings = {}
        self.text = options.get("text", "")
        self.enabled = True
        self.focus_set = Mock()
        self.pack = Mock()
        self.pack_forget = Mock()
        self.grid = Mock()
        self.grid_columnconfigure = Mock()

    def cget(self, key):
        return self.options.get(key, "")

    def configure(self, **options):
        self.options.update(options)

    def __setitem__(self, key, value):
        self.options[key] = value

    def bind(self, sequence, callback, add=None):
        self.bindings[sequence] = callback

    def register(self, callback):
        return callback

    def winfo_exists(self):
        return True

    def set_text(self, text):
        self.text = text

    def set_enabled(self, enabled):
        self.enabled = enabled

    def draw(self):
        pass


class Checkbox(Widget):
    def __init__(self, master, value, command, colors):
        Widget.__init__(self, master)
        self.variable = Variable(value=value)
        self.command = command


class Choice(Widget):
    def __init__(self, master, choices, value, command, colors, **options):
        Widget.__init__(self, master, **options)
        self.variable = Variable(value=value)
        self.command = command

    def get(self):
        return self.variable.get()

    def set(self, value):
        self.variable.set(value)


FAKE_TK = SimpleNamespace(Frame=Widget, Entry=Widget, Label=Widget, StringVar=Variable)


def make_app(settings=None):
    app = native.NativeApp.__new__(native.NativeApp)
    app.root = Mock()
    app.subtab_selection = {}
    app.ui_state_path = str(Path(tempfile.gettempdir()) / "fuzzy-gui-test-state.json")
    app.settings = dict(settings or {})
    app.manager = Mock()
    app.actions = Mock()
    app.palette = widgets.palette("brown")
    app.controls = {}
    app.control_groups = {}
    app.rows = {}
    app.active_tab = "gather"
    app.pending = queue.Queue()
    app.recording = None
    app.recording_lock = threading.Lock()
    app.recorded_keys = set()
    app.stop_supervisor = threading.Event()
    app.supervisor_thread = None
    app.close_callback = None
    app.closing = False
    app.destroyed = False
    app.failure = None
    app.update_running = False
    app.refresh_home = Mock()
    app.update_conditions = Mock()
    app.status = Mock()
    app.update_button = Widget()
    app.update_text = Widget()
    app.progress = Widget()
    return app


def add_keybind(app, identifier, value):
    app.controls[identifier] = widgets.Control(Widget(), Variable(value=value))
    app.control_groups[identifier] = [app.controls[identifier]]
    app.settings[identifier] = value


def drain(app):
    while not app.pending.empty():
        callback, args = app.pending.get_nowait()
        callback(*args)


class TextboxTests(unittest.TestCase):
    def setUp(self):
        self.app = make_app()
        self.parent = Widget(bg=self.app.palette["surface"])
        self.tk_patch = patch.object(native, "tk", FAKE_TK)
        self.tk_patch.start()
        self.addCleanup(self.tk_patch.stop)

    def test_focus_loss_commits_changes_once_and_return_moves_focus(self):
        changed = Mock()
        control = self.app.add_control(self.parent, dict(id="mins", kind="textbox", numeric="float"),
                                       value="8", onchange=changed)
        blur = control.widget.bindings["<FocusOut>"]
        blur()
        changed.assert_not_called()
        control.variable.set("12.5")
        control.widget.bindings["<Return>"](None)
        self.parent.focus_set.assert_called_once()
        blur()
        blur()
        changed.assert_called_once_with("12.5")

    def test_field_switch_then_edit_back_to_previous_value_is_saved(self):
        # Use actual field settings and the real gather save/load callbacks.
        defaults = runpy.run_path(str(ROOT / "src/modules/misc/settings_defaults.py"))["DEFAULT_FIELDS"]
        fields = copy.deepcopy({name: defaults[name] for name in ("sunflower", "pine tree")})
        fields["sunflower"]["mins"] = "8"
        fields["pine tree"]["mins"] = "12"
        original_fields = copy.deepcopy(fields)
        self.app.settings.update(fields=["sunflower", "pine tree"], fields_enabled=[True, True])
        self.app.manager.loadFields.side_effect = lambda: copy.deepcopy(fields)
        self.app.manager.saveField.side_effect = lambda name, data: fields.__setitem__(name, copy.deepcopy(data))
        self.app.field_slot = 0
        self.app.field_name = "sunflower"
        self.app.field_data = copy.deepcopy(fields["sunflower"])
        self.app.field_buttons = [Widget(), Widget()]
        self.app.gather_sections = {"Gather Field": SimpleNamespace(heading=Widget())}
        self.app.pages = {"gather": SimpleNamespace(canvas=Mock())}
        specs = [spec for section in native.TAB_DEFINITIONS["gather"][0]["sections"]
                 for spec in section["controls"] if spec.get("scope") == "field"]
        for spec in specs:
            self.app.controls[spec["id"]] = widgets.Control(Widget(), Variable(
                value=self.app.field_data.get(spec["id"], "")), spec.get("numeric"))
        for identifier in ("field", "field_enable"):
            self.app.controls[identifier] = widgets.Control(Widget(), Variable())
        spec = next(spec for spec in specs if spec["id"] == "mins")
        control = self.app.add_control(self.parent, spec, value="8")
        blur = control.widget.bindings["<FocusOut>"]
        self.app.load_gather_field()
        self.app.select_field_slot(1)
        self.app.manager.saveField.assert_not_called()
        # This must save even though it equals the first field's original value.
        control.variable.set("8")
        blur()
        blur()
        self.app.manager.saveField.assert_called_once()
        name, data = self.app.manager.saveField.call_args[0]
        self.assertEqual(name, "pine tree")
        self.assertEqual(data["mins"], "8")
        self.assertEqual(data["pattern_presets"][data["shape"]]["mins"], "8")
        self.assertEqual(fields["sunflower"], original_fields["sunflower"])
        self.assertEqual(fields["pine tree"]["mins"], "8")

    def test_empty_numeric_commit_is_zero_and_reloads_do_not_save(self):
        for numeric in ("int", "float"):
            with self.subTest(numeric=numeric):
                changed = Mock()
                control = self.app.add_control(self.parent, dict(id=numeric, kind="textbox", numeric=numeric),
                                               value="5", onchange=changed)
                control.set("7")
                blur = control.widget.bindings["<FocusOut>"]
                blur()
                changed.assert_not_called()
                control.variable.set("")
                blur()
                blur()
                changed.assert_called_once_with(0)


class ControlRegistrationTests(unittest.TestCase):
    def test_gather_aliases_stay_out_of_setting_groups_and_dispatch_to_arrays(self):
        app = make_app(dict(fields=["sunflower", "pine tree"], fields_enabled=[True, True]))
        app.field_slot = 1
        app.load_gather_field = Mock()
        stored = copy.deepcopy(app.settings)
        app.manager.loadAllSettings.side_effect = lambda: copy.deepcopy(stored)
        app.manager.saveProfileSetting.side_effect = lambda key, value: stored.__setitem__(key, value)
        specs = [spec for section in native.TAB_DEFINITIONS["gather"][0]["sections"]
                 for spec in section["controls"] if spec["id"] in ("field", "field_enable")]
        with patch.object(native, "tk", FAKE_TK), \
                patch.object(widgets, "Checkbox", Checkbox), patch.object(widgets, "Choice", Choice):
            for spec in specs:
                value = False if spec["id"] == "field_enable" else "rose"
                item = app.add_control(Widget(), spec, value=value)
                self.assertIs(app.controls[spec["id"]], item)
                self.assertNotIn(spec["id"], app.control_groups)
                item.widget.command()
        self.assertEqual(stored["fields"], ["sunflower", "rose"])
        self.assertEqual(stored["fields_enabled"], [True, False])
        self.assertNotIn("field", stored)
        self.assertNotIn("field_enable", stored)
        app.manager.saveProfileSetting.assert_any_call("fields", ["sunflower", "rose"])
        app.manager.saveProfileSetting.assert_any_call("fields_enabled", [True, False])
        app.load_gather_field.assert_called_once_with()


class KeybindTests(unittest.TestCase):
    def setUp(self):
        self.app = make_app()
        add_keybind(self.app, "start_keybind", "F1")
        add_keybind(self.app, "stop_keybind", "F3")
        self.app.manager.loadAllSettings.side_effect = lambda: dict(self.app.settings)

        def save(key, value):
            self.app.settings[key] = value

        self.app.manager.saveGeneralSetting.side_effect = save
        self.dialogs = patch.object(native, "messagebox", Mock())
        self.messagebox = self.dialogs.start()
        self.addCleanup(self.dialogs.stop)

    def press(self, key, state=0):
        return self.app.record_key(SimpleNamespace(keysym=key, state=state))

    def test_rejected_binding_restores_display_and_ignores_later_keys(self):
        for key, state in (("a", 0), ("F5", 0), ("F3", 0), ("l", 4)):
            with self.subTest(key=key, state=state):
                self.app.start_recording("start_keybind")
                self.press(key, state)
                self.assertEqual(self.app.finish_key(None), "break")
                self.assertFalse(self.app.is_recording())
                self.assertEqual(self.app.controls["start_keybind"].widget.text, "F1")
                self.press("F8")
                self.app.finish_key(None)
                self.app.manager.saveGeneralSetting.assert_not_called()
        self.assertEqual(self.messagebox.showerror.call_count, 4)

    def test_outside_click_cancels_but_recording_button_click_keeps_capture(self):
        self.app.start_recording("start_keybind")
        self.press("Control_L")
        self.app.cancel_recording_click(SimpleNamespace(widget=self.app.controls["start_keybind"].widget))
        self.assertTrue(self.app.is_recording())
        self.app.cancel_recording_click(SimpleNamespace(widget=Widget()))
        self.assertFalse(self.app.is_recording())
        self.assertEqual(self.app.controls["start_keybind"].widget.text, "F1")
        self.press("F8")
        self.app.finish_key(None)
        self.app.manager.saveGeneralSetting.assert_not_called()
        self.app.start_recording("start_keybind")
        self.press("F8")
        self.app.finish_key(None)
        self.app.manager.saveGeneralSetting.assert_called_once_with("start_keybind", "F8")

    def test_constructor_registers_outside_click_cancellation(self):
        root = Mock()
        manager, actions = Mock(), Mock()
        manager.loadAllSettings.return_value = {}
        manager.loadFields.return_value = {}
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        manager.getUserDataPath.return_value = str(Path(directory.name) / "gui_state.json")
        actions.getRecentLogs.return_value = []
        with patch.object(native.NativeApp, "configure_styles"), patch.object(native.NativeApp, "build_shell"):
            app = native.NativeApp(root, actions, manager)
        root.bind_all.assert_any_call("<ButtonPress-1>", app.cancel_recording_click, add="+")

    def test_platform_modifier_masks_and_tk_aliases_use_runtime_key_names(self):
        cases = [("darwin", "F8", 4 | 1 | 16 | 8, "Ctrl+Alt+Shift+Cmd+F8"),
                 ("win32", "F8", 4 | 1 | 0x20000, "Ctrl+Alt+Shift+F8"),
                 ("darwin", "Caps_Lock", 2, "CapsLock"),
                 ("win32", "Caps_Lock", 2, "CapsLock"),
                 ("win32", "KP_4", 0, "Numpad4"),
                 ("darwin", "Left", 0, "ArrowLeft")]
        for platform, key, state, expected in cases:
            with self.subTest(platform=platform, key=key), patch.object(sys, "platform", platform):
                self.app.start_recording("start_keybind")
                self.press(key, state)
                self.app.finish_key(None)
                self.app.manager.saveGeneralSetting.assert_called_with("start_keybind", expected)
                self.assertEqual(self.app.controls["start_keybind"].widget.text, expected.replace("+", " + "))
                self.assertFalse(self.app.is_recording())
        self.messagebox.showerror.assert_not_called()

    def test_physical_letters_survive_option_and_numlock_on_supported_tk_formats(self):
        cases = [('darwin', '8.6.10', (5 << 16) | 169, 'copyright', 16, 'Alt+G'),
                 ('darwin', '8.6.11', (5 << 24) | 169, 'copyright', 16, 'Alt+G'),
                 ('win32', '8.6.11', 0x47, 'g', 8, 'G')]
        for platform, version, code, keysym, state, expected in cases:
            with self.subTest(platform=platform, version=version), patch.object(sys, 'platform', platform):
                self.app.root.tk.call.return_value = version
                self.app.start_recording('start_keybind')
                self.app.record_key(SimpleNamespace(keysym=keysym, keycode=code, state=state))
                self.app.finish_key(None)
                self.app.manager.saveGeneralSetting.assert_called_with('start_keybind', expected)
        self.messagebox.showerror.assert_not_called()

    def test_modifier_release_waits_for_main_key_and_clear_cancels(self):
        self.app.start_recording("start_keybind")
        self.press("Shift_L")
        self.app.finish_key(None)
        self.assertTrue(self.app.is_recording())
        self.app.manager.saveGeneralSetting.assert_not_called()
        self.press("F8", 1)
        self.app.finish_key(None)
        self.app.manager.saveGeneralSetting.assert_called_once_with("start_keybind", "Shift+F8")
        for key in ("Delete", "BackSpace"):
            with self.subTest(key=key):
                self.app.start_recording("start_keybind")
                self.assertEqual(self.press(key), "break")
                self.assertFalse(self.app.is_recording())
                self.assertEqual(self.app.controls["start_keybind"].widget.text, "Click to record")
                self.app.manager.saveGeneralSetting.assert_called_with("start_keybind", "")


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.app = make_app()
        self.dialogs = patch.object(native, "messagebox", Mock())
        self.messagebox = self.dialogs.start()
        self.addCleanup(self.dialogs.stop)
        self.threads = []
        real_thread = threading.Thread

        def thread(*args, **kwargs):
            worker = real_thread(*args, **kwargs)
            self.threads.append(worker)
            return worker

        self.thread_patch = patch.object(native.threading, "Thread", side_effect=thread)
        self.thread_patch.start()
        self.addCleanup(self.thread_patch.stop)

    def complete_workers(self):
        # Joining before draining deliberately keeps Tk callbacks on this thread.
        for worker in self.threads:
            worker.join(2)
            self.assertFalse(worker.is_alive(), "update worker failed to finish")
        drain(self.app)

    def assert_retryable(self):
        self.assertFalse(self.app.update_running)
        self.assertTrue(self.app.update_button.enabled)
        self.app.progress.pack_forget.assert_called()

    def test_lock_covers_check_and_install_and_failed_install_allows_retry(self):
        checking, checked = threading.Event(), threading.Event()
        installing, installed = threading.Event(), threading.Event()
        self.addCleanup(checked.set)
        self.addCleanup(installed.set)

        def check():
            checking.set()
            if not checked.wait(2):
                raise RuntimeError("test check timed out")
            return {"available": True}

        def install():
            installing.set()
            if not installed.wait(2):
                raise RuntimeError("test install timed out")
            return False

        self.app.actions.checkForUpdates.side_effect = check
        self.app.actions.update.side_effect = install
        self.messagebox.askyesno.return_value = True
        self.app.check_updates()
        self.assertTrue(checking.wait(2))
        self.assertTrue(self.app.update_running)
        self.assertFalse(self.app.update_button.enabled)
        self.app.check_updates()
        self.app.actions.checkForUpdates.assert_called_once()
        checked.set()
        self.complete_workers()
        self.assertTrue(installing.wait(2))
        self.assertTrue(self.app.update_running)
        self.assertFalse(self.app.update_button.enabled)
        self.app.check_updates()
        self.app.actions.checkForUpdates.assert_called_once()
        self.app.actions.update.assert_called_once()
        installed.set()
        self.complete_workers()
        self.assert_retryable()
        self.app.actions.checkForUpdates.side_effect = None
        self.app.actions.checkForUpdates.return_value = {"available": False}
        self.app.check_updates()
        self.complete_workers()
        self.assertEqual(self.app.actions.checkForUpdates.call_count, 2)
        self.assert_retryable()

    def test_check_failure_no_update_and_declined_install_release_lock(self):
        for info in (None, {"available": False}, {"available": True}):
            with self.subTest(info=info):
                self.app.actions.checkForUpdates.return_value = info
                self.messagebox.askyesno.return_value = False
                self.app.check_updates()
                self.complete_workers()
                self.assert_retryable()
                self.app.actions.update.assert_not_called()

    def test_successful_install_closes_on_tk_thread(self):
        main_thread = threading.get_ident()
        worker_threads = []

        def install():
            worker_threads.append(threading.get_ident())
            return True

        self.app.actions.checkForUpdates.return_value = {"available": True}
        self.app.actions.update.side_effect = install
        self.messagebox.askyesno.return_value = True
        self.app.root.destroy.side_effect = lambda: self.assertEqual(threading.get_ident(), main_thread)
        self.app.check_updates()
        self.complete_workers()
        self.complete_workers()
        self.assertTrue(self.app.destroyed)
        self.app.root.destroy.assert_called_once()
        self.assertEqual(len(worker_threads), 1)
        self.assertNotEqual(worker_threads[0], main_thread)

    def test_raised_check_and_install_errors_release_lock(self):
        for stage in ("check", "install"):
            with self.subTest(stage=stage):
                self.app = make_app()
                self.app.actions.checkForUpdates.side_effect = RuntimeError("offline") if stage == "check" else None
                self.app.actions.checkForUpdates.return_value = {"available": True}
                self.app.actions.update.side_effect = RuntimeError("cannot install")
                self.messagebox.askyesno.return_value = True
                self.app.check_updates()
                self.complete_workers()
                self.complete_workers()
                self.app.actions.checkForUpdates.assert_called_once()
                if stage == "install":
                    self.app.actions.update.assert_called_once()
                self.assert_retryable()
        self.messagebox.showerror.assert_called()


class SupervisorTests(unittest.TestCase):
    def pump_until_destroyed(self, app):
        while not app.destroyed:
            try:
                callback, args = app.pending.get(timeout=2)
            except queue.Empty:
                self.fail("supervisor never scheduled window destruction")
            callback(*args)

    def test_callback_exception_reschedules_poll_and_next_callback_runs(self):
        app = make_app()
        failure = ValueError("queued callback failed")
        failed, following = Mock(side_effect=failure), Mock()
        app.enqueue(failed, "first")
        app.enqueue(following, "second")
        with self.assertRaises(ValueError) as raised:
            app.poll_pending()
        self.assertIs(raised.exception, failure)
        failed.assert_called_once_with("first")
        following.assert_not_called()
        app.root.after.assert_called_once_with(16, app.poll_pending)
        _, scheduled = app.root.after.call_args[0]
        scheduled()
        following.assert_called_once_with("second")
        self.assertTrue(app.pending.empty())
        self.assertEqual(app.root.after.call_count, 2)

    def test_slow_tick_keeps_tk_callbacks_live_and_cleanup_precedes_destroy(self):
        app = make_app()
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        main_thread = threading.get_ident()
        calls = []

        def tick():
            calls.append(("tick", threading.get_ident()))
            entered.set()
            if not release.wait(2):
                raise RuntimeError("test tick timed out")
            return 60

        def cleanup():
            calls.append(("cleanup", threading.get_ident()))

        def mainloop():
            self.assertTrue(entered.wait(2))
            pulse = Mock()
            app.enqueue(pulse)
            app.poll_pending()
            pulse.assert_called_once()
            app.root.after.assert_any_call(16, app.poll_pending)
            app.close()
            app.close()
            self.assertTrue(app.closing)
            app.root.destroy.assert_not_called()
            self.assertNotIn("cleanup", [name for name, _ in calls])
            release.set()
            self.pump_until_destroyed(app)

        app.root.mainloop.side_effect = mainloop
        app.root.destroy.side_effect = lambda: calls.append(("destroy", threading.get_ident()))
        app.refresh_home.side_effect = lambda: self.assertEqual(threading.get_ident(), main_thread)
        app.run_event_loop(tick, cleanup)
        self.assertEqual([name for name, _ in calls], ["tick", "cleanup", "destroy"])
        self.assertNotEqual(calls[0][1], main_thread)
        self.assertEqual(calls[2][1], main_thread)
        self.assertFalse(app.supervisor_thread.is_alive())
        app.close()
        app.finish_close()
        app.root.destroy.assert_called_once()

    def test_tick_and_cleanup_errors_propagate_after_window_destruction(self):
        for tick_error, cleanup_error in ((ValueError("tick failed"), None),
                                          (SystemExit(7), RuntimeError("cleanup failed")),
                                          (None, RuntimeError("cleanup failed"))):
            with self.subTest(tick_error=tick_error, cleanup_error=cleanup_error):
                app = make_app()
                calls = []

                def tick():
                    if tick_error is not None:
                        raise tick_error
                    app.stop_supervisor.set()
                    return 0

                def cleanup():
                    calls.append("cleanup")
                    if cleanup_error is not None:
                        raise cleanup_error

                app.root.mainloop.side_effect = lambda: self.pump_until_destroyed(app)
                app.root.destroy.side_effect = lambda: calls.append("destroy")
                expected = tick_error if tick_error is not None else cleanup_error
                with self.assertRaises(type(expected)) as raised:
                    app.run_event_loop(tick, cleanup)
                self.assertIs(raised.exception, expected)
                self.assertEqual(calls, ["cleanup", "destroy"])
                app.root.destroy.assert_called_once()
                self.assertFalse(app.supervisor_thread.is_alive())

    def test_close_before_runtime_still_cleans_up_before_destroy_once(self):
        app = make_app()
        calls = []
        app.close_callback = lambda: calls.append("cleanup")
        app.root.destroy.side_effect = lambda: calls.append("destroy")
        app.close()
        app.close()
        self.assertEqual(calls, ["cleanup", "destroy"])


def load_backend_functions(names, namespace):
    source = ast.parse((ROOT / "src/gui.py").read_text(encoding="utf-8"))
    module = ast.parse("")
    module.body = [node for node in source.body if isinstance(node, ast.FunctionDef) and node.name in names]
    exec(compile(module, "src/gui.py", "exec"), namespace)
    return namespace


class PlanterResetTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "auto_planters.json"
        manager = SimpleNamespace(loadUserJson=self.load, saveUserJson=self.save)
        self.backend = load_backend_functions({"emptyAutoPlanterSlot", "emptyAutoPlanterFieldDegradation",
                                              "defaultAutoPlanterData", "normalizeAutoPlanterData",
                                              "resetAutoPlanterTimer"}, {"settingsManager": manager})
        self.data = self.backend["defaultAutoPlanterData"]()
        self.data.update(gather=True)
        self.data["nectar_last_field"]["comforting"] = "pine tree"
        self.data["field_degradation"]["pine tree"] = {"hours": 3.25, "updated_at": 1700000000}
        for index, slot in enumerate(self.data["planters"]):
            slot.update(planter=("paper", "plastic", "candy")[index], nectar="comforting", field="pine tree",
                        harvest_time=1700003600 + index, nectar_est_percent=45, placed_time=1700000000,
                        grow_duration=3600, natural_grow_duration=7200)
        self.save("auto_planters.json", self.data)

    def load(self, filename):
        self.assertEqual(filename, "auto_planters.json")
        return json.loads(self.path.read_text(encoding="utf-8"))

    def save(self, filename, data):
        self.assertEqual(filename, "auto_planters.json")
        self.path.write_text(json.dumps(data), encoding="utf-8")

    def assert_empty_slot(self, slot):
        self.assertEqual(slot, {"planter": "", "nectar": "", "field": "", "harvest_time": 0,
                                "nectar_est_percent": 0, "placed_time": 0,
                                "grow_duration": 0, "natural_grow_duration": 0})

    def test_reset_all_clears_slots_and_retains_nectar_gather_and_degradation(self):
        self.assertTrue(self.backend["resetAutoPlanterTimer"]("all"))
        result = self.load("auto_planters.json")
        self.assertEqual(len(result["planters"]), 3)
        for slot in result["planters"]:
            self.assert_empty_slot(slot)
        for key in ("nectar_last_field", "gather", "field_degradation"):
            self.assertEqual(result[key], self.data[key])

    def test_single_reset_preserves_other_slots_and_invalid_indices_do_not_write(self):
        self.assertTrue(self.backend["resetAutoPlanterTimer"](1))
        result = self.load("auto_planters.json")
        self.assert_empty_slot(result["planters"][1])
        self.assertEqual(result["planters"][0], self.data["planters"][0])
        self.assertEqual(result["planters"][2], self.data["planters"][2])
        for key in ("nectar_last_field", "gather", "field_degradation"):
            self.assertEqual(result[key], self.data[key])
        before = self.path.read_bytes()
        for index in (-1, 3):
            with self.subTest(index=index):
                self.assertFalse(self.backend["resetAutoPlanterTimer"](index))
                self.assertEqual(self.path.read_bytes(), before)


class CompatibilityTests(unittest.TestCase):
    def test_python_37_syntax(self):
        for relative in ("tests/test_gui_app.py", "src/modules/gui/app.py", "src/modules/gui/widgets.py",
                         "src/gui.py", "src/main.py"):
            with self.subTest(path=relative):
                source = (ROOT / relative).read_text(encoding="utf-8")
                if sys.version_info >= (3, 8):
                    ast.parse(source, feature_version=7)
                else:
                    ast.parse(source)


if __name__ == "__main__":
    unittest.main()
