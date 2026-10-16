"""Headless parity checks for the native custom configuration workflows.

No Tk window is created: widgets are replaced by a recording fake, source
behavior is checked by running the shipped JavaScript with Node, and profile
files are exercised against a copy of settingsManager in a temp directory.
"""

import ast
import base64
import importlib.util
import json
from pathlib import Path
import random
import re
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from modules.gui import configuration as cfg
from modules.gui.widgets import Scroll as NativeScroll
from modules.gui.definitions import CUSTOM_DEFINITIONS, TAB_DEFINITIONS


NODE = shutil.which("node")
SCRIPT = (ROOT / "src/webapp/scripts/script.js").read_text()
BOOST = (ROOT / "src/webapp/scripts/tabs/boost.js").read_text()


def between(source, start, end):
    first = source.index(start)
    return source[first:source.index(end, first)]


def run_node(source, expression):
    script = source + "\n;(async () => process.stdout.write(JSON.stringify(await (" + expression + "))))();"
    result = subprocess.run([NODE, "-e", script], check=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, universal_newlines=True, cwd=str(ROOT))
    return json.loads(result.stdout)


# ---------------------------------------------------------------------------
# A recording stand-in for the Tk widgets the module touches
# ---------------------------------------------------------------------------

class Var(object):
    def __init__(self, master=None, value=""):
        self.value = value
        self.callbacks = []

    def get(self):
        return self.value

    def set(self, value):
        self.value = value
        for callback in self.callbacks:
            callback()

    def trace_add(self, mode, callback):
        self.callbacks.append(lambda: callback("var", "", mode))


TK_NOOPS = {"grid", "grid_configure", "grid_forget", "grid_remove", "unbind", "columnconfigure", "rowconfigure", "place", "lift",
            "lower", "focus_set", "update_idletasks", "title", "geometry", "wait_visibility", "grab_set",
            "grab_release", "transient", "resizable", "protocol", "focus_force", "select_range", "icursor",
            "yview_scroll", "yview", "create_text", "create_line", "create_polygon", "create_rectangle", "create_image", "create_oval", "delete",
            "tag_bind", "itemconfigure", "bind_all", "unbind_all", "wait_window", "grid_columnconfigure",
            "grid_rowconfigure", "attributes", "withdraw", "deiconify", "mainloop", "update", "pack_propagate",
            "grid_propagate", "winfo_toplevel", "winfo_screenwidth", "winfo_screenheight", "winfo_reqwidth",
            "winfo_reqheight", "winfo_x", "winfo_y", "winfo_ismapped"}


class Widget(object):
    def __init__(self, master=None, *args, **options):
        self.master = master
        self.options = dict(options)
        self.children = []
        self.slaves = []
        self.bindings = {}
        self.destroyed = False
        self.pack_options = {}
        if master is not None:
            master.children.append(self)

    def cget(self, key):
        return self.options.get(key, "")

    def configure(self, **options):
        if self.destroyed:
            raise RuntimeError("widget was destroyed")
        self.options.update(options)

    config = configure

    def bind(self, sequence, callback, add=None):
        self.bindings[sequence] = callback

    def pack(self, **options):
        self.pack_configure(**options)

    def pack_configure(self, **options):
        siblings = self.master.slaves
        before, after = options.pop("before", None), options.pop("after", None)
        self.pack_options = dict(options)
        if self in siblings:
            siblings.remove(self)
        if before is not None:
            siblings.insert(siblings.index(before), self)
        elif after is not None:
            siblings.insert(siblings.index(after) + 1, self)
        else:
            siblings.append(self)

    def pack_forget(self):
        if self.master is not None and self in self.master.slaves:
            self.master.slaves.remove(self)

    def place(self, **options):
        self.pack_configure(**options)

    def place_forget(self):
        self.pack_forget()

    def pack_slaves(self):
        return list(self.slaves)

    def winfo_manager(self):
        return "pack" if self.master is not None and self in self.master.slaves else ""

    def winfo_exists(self):
        return not self.destroyed

    def winfo_children(self):
        return list(self.children)

    def destroy(self):
        for child in list(self.children):
            child.destroy()
        self.pack_forget()
        if self.master is not None and self in self.master.children:
            self.master.children.remove(self)
        self.destroyed = True

    def winfo_rooty(self):
        return 40 * self.master.slaves.index(self) if self.winfo_manager() else 0

    def winfo_height(self):
        return 40

    def winfo_rootx(self):
        return 0

    def winfo_width(self):
        return 400

    def winfo_pointerxy(self):
        return (-1, -1)

    def after(self, milliseconds, callback=None):
        return "job"

    def after_cancel(self, job):
        return None

    def pack_info(self):
        return dict(self.pack_options)

    def __getattr__(self, name):
        if name in TK_NOOPS:
            return lambda *args, **kwargs: None
        raise AttributeError(name)


class Entry(Widget):
    def __init__(self, master=None, *args, **options):
        Widget.__init__(self, master, *args, **options)
        self.variable = options.get("textvariable") or Var()

    def get(self):
        return self.variable.get()

    def insert(self, index, text):
        self.variable.set(self.variable.get() + text)

    def delete(self, first, last=None):
        self.variable.set("")


class Button(Widget):
    def __init__(self, master, text, command, *args, **options):
        Widget.__init__(self, master)
        self.text = text
        self.command = command
        self.enabled = True

    def set_enabled(self, enabled):
        self.enabled = enabled

    def set_text(self, text):
        self.text = text


class Choice(Widget):
    def __init__(self, master, choices, value, command, colors, multiple=False, width=160):
        Widget.__init__(self, master)
        self.choices, self.value = choices, value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value

    def set_choices(self, choices):
        self.choices = choices


class Card(Widget):
    def __init__(self, master, colors, *args, **kwargs):
        Widget.__init__(self, master)
        self.body = Widget(self, bg=colors["surface"])


class Scroll(Widget):
    set_scroll = NativeScroll.set_scroll
    wheel = NativeScroll.wheel

    def __init__(self, master, colors):
        Widget.__init__(self, master)
        self.canvas = Widget(self, bg=colors["bg"])
        self.canvas.pack(side="left", fill="both", expand=True)
        self.bar = Widget(self)
        self.bar.set = lambda first, last: None
        self.bar.pack(side="right", fill="y")
        self.body = Widget(self.canvas)


FAKE_TK = SimpleNamespace(Frame=Widget, Label=Widget, Canvas=Widget, Toplevel=Widget, Entry=Entry,
                          StringVar=Var, TclError=RuntimeError)


class Control(object):
    def __init__(self, value="", master=None, numeric=None):
        self.value, self.numeric = value, numeric
        self.widget = Widget(master)
        self.variable = None

    def get(self):
        return 0 if self.value == "" and self.numeric else self.value

    def set(self, value):
        self.value = value


class TypedControl(Control):
    """A numeric text field whose variable still holds the empty string."""

    def __init__(self, value):
        Control.__init__(self, value, numeric="int")
        self.variable = SimpleNamespace(get=lambda: self.value)


class Manager(object):
    def __init__(self):
        self.saved = []
        self.settings = {}
        self.fields = {}

    def saveDictProfileSettings(self, values):
        self.saved.append(dict(values))

    def loadAllSettings(self):
        return dict(self.settings)

    def loadFields(self):
        return self.fields

    def getCurrentProfile(self):
        return "default"


class App(object):
    def __init__(self, settings=None):
        self.root = Widget()
        self.palette = dict(bg="#121212", surface="#1e1e1e", text="#e0e0e0", dim="#a0a0a0",
                            border="#333333", accent="#ab8062", input="#2b2b2b", hover="#2c2c2c",
                            dim_surface="#141414", accent_hover="#cd9975", selected="#332d28")
        self.settings = dict(settings or {})
        self.manager = Manager()
        self.controls = {}
        self.saves = []
        self.statuses = []
        self.actions = SimpleNamespace()
        self.added = []
        self.refreshes = 0
        self.action_results = {}
        self.update_running = False

    def save(self, key, value, scope="profile"):
        self.saves.append((key, value, scope))
        self.settings[key] = value

    def status(self, text):
        self.statuses.append(text)

    def refresh(self):
        self.refreshes += 1

    def button(self, parent, text, command):
        return Button(parent, text, command)

    def label(self, parent, text, dim=False):
        return Widget(parent, text=text)

    def add_control(self, parent, spec, value=None, onchange=None):
        self.added.append((parent, spec))
        # The NativeApp row layout: row > (heading, right > widget).
        row = Widget(parent)
        Widget(row)
        control = Control(value, Widget(row))
        self.controls[spec["id"]] = control
        return control

    def action(self, name, *args):
        return self.action_results[name](*args) if name in self.action_results else None

    def run_async(self, function, done):
        done(function())

    def open_image(self, path):
        self.statuses.append("image " + path)


def widgets():
    return patch.multiple(cfg, tk=FAKE_TK, Button=Button, Choice=Choice, Scroll=Scroll, Card=Card,
                          rounded_image=lambda *args, **kwargs: object(),
                          draw_hotbar_slot=lambda *args: None, draw_hotbar_icon=lambda *args: None)


def descendants(widget):
    return [child for direct in widget.children for child in [direct] + descendants(direct)]


def model_widgets(control):
    children = descendants(control.widget)
    status = next(w for w in children if w.cget("text") in
                  ("Checking installed models…", "1 model missing.", "Could not check installed models."))
    download_all = next(w for w in children if isinstance(w, Button) and w.text == "Download Missing Models")
    return status, download_all


# ---------------------------------------------------------------------------
# Source-level parity: priority locking, enabled states, copy, cannon clamps
# ---------------------------------------------------------------------------

PRIORITY_JS = (between(SCRIPT, "function isPriorityLockedTask", "function createPriorityLockHeader")
               + between(SCRIPT, "function mergePriorityOrderWithLocks", "function reapplyPriorityLockedPositions")
               + """
function lockState(order) {
  const a = getPriorityLockAnchors(order);
  return {questAnchor: a.questAnchor, planterAnchor: a.planterAnchor, questBeforePlanter: a.questBeforePlanter,
    questIds: a.order.filter((id) => String(id).startsWith("quest_")), hasPlanters: a.order.includes("planters")};
}
""")


def random_orders(count):
    rng = random.Random(7)
    names = ["gather_pine_tree", "gather_clover", "collect_wealth_clock", "kill_ladybug", "mondo_buff",
             "blender", "ant_challenge", "stinger_hunt", "collect_sprouts", "gather_stump"]
    quests = ["quest_polar_bear", "quest_brown_bear", "quest_black_bear", "quest_honey_bee"]
    orders = [[], ["planters"], ["quest_polar_bear"], ["planters", "quest_riley_bee"]]
    for _ in range(count):
        items = rng.sample(names, rng.randint(0, len(names)))
        items += rng.sample(quests, rng.randint(0, len(quests)))
        if rng.random() < .7:
            items.append("planters")
        rng.shuffle(items)
        orders.append(items)
    return orders


@unittest.skipUnless(NODE, "Node is required only for source differential tests")
class SourceParityTests(unittest.TestCase):
    def test_priority_lock_rules_match_script(self):
        orders = random_orders(250)
        expected = run_node(PRIORITY_JS, "{}.map((order) => ({{grouped: normalizePriorityOrderGrouping(order), "
                                          "anchors: getPriorityLockAnchors(order), state: lockState(order)}}))"
                            .format(json.dumps(orders)))
        for order, js in zip(orders, expected):
            with self.subTest(order=order):
                self.assertEqual(cfg.normalize_priority_grouping(order), js["grouped"])
                state = cfg.priority_lock_state(order)
                self.assertEqual(state["order"], js["anchors"]["order"])
                self.assertEqual(state["quest_anchor"], js["anchors"]["questAnchor"])
                self.assertEqual(state["planter_anchor"], js["anchors"]["planterAnchor"])
                self.assertEqual(state["quest_before_planter"], js["anchors"]["questBeforePlanter"])

    def test_priority_merge_after_reordering_matches_script(self):
        rng = random.Random(11)
        cases = []
        for order in random_orders(250):
            state = cfg.priority_lock_state(order)
            unlocked = [i for i in state["order"] if not cfg.is_priority_locked(i)]
            rng.shuffle(unlocked)
            cases.append({"order": order, "unlocked": unlocked})
        expected = run_node(PRIORITY_JS, "{}.map((c) => mergePriorityOrderWithLocks(c.unlocked, lockState(c.order)))"
                            .format(json.dumps(cases)))
        for case, js in zip(cases, expected):
            with self.subTest(case=case):
                self.assertEqual(cfg.merge_priority_order(case["unlocked"], cfg.priority_lock_state(case["order"])), js)

    def test_task_enabled_matches_script(self):
        source = between(SCRIPT, "window._isTaskEnabledForSettings = function", "\n  };\n") + "\n  };\n"
        rng = random.Random(3)
        tasks = [c["value"] for c in CUSTOM_DEFINITIONS["task_priorities"]["choices"]]
        tasks += ["quest_polar_bear", "quest_riley_bee", "planters", "collect_sticker_sprout", "unknown_task"]
        keys = ["sprouts_enable", "sticker_sprout_watch", "sticker_printer", "sticker_stack", "wealth_clock",
                "ladybug", "stump_snail", "polar_bear_quest", "riley_bee_quest", "mondo_buff", "stinger_hunt",
                "auto_field_boost", "ant_challenge", "blender", "blender_enable", "planters", "wind_shrine"]
        cases = []
        for _ in range(80):
            settings = {key: rng.choice([True, False, 0, 1, "", "yes", None]) for key in keys if rng.random() < .6}
            settings["planters_mode"] = rng.choice([0, 1, 2, "1", "x", None, ""])
            settings["fields"] = rng.sample(["pine tree", "clover", "stump", "blue flower"], 3)
            settings["fields_enabled"] = [rng.random() < .5 for _ in range(3)]
            cases.append(settings)
        expected = run_node("const window = {};\nfunction holder() {\n" + source + "\n}\nholder();",
                            "{}.map((s) => {}.map((t) => !!window._isTaskEnabledForSettings(t, s)))"
                            .format(json.dumps(cases), json.dumps(tasks)))
        for settings, js in zip(cases, expected):
            with self.subTest(settings=settings):
                self.assertEqual([cfg.task_enabled(task, settings) for task in tasks], js)

    def test_web_task_names_are_all_available(self):
        names = dict(re.findall(r"^\s+(\w+): \"([^\"]+)\",$",
                                between(SCRIPT, "const displayNames = {", "if (displayNames[taskId])"), re.M))
        known = {c["value"]: c["label"] for c in CUSTOM_DEFINITIONS["task_priorities"]["choices"]}
        known.update(cfg.EXTRA_TASK_NAMES)
        for task_id, label in names.items():
            if not cfg.is_priority_locked(task_id):
                self.assertEqual(known.get(task_id), label, task_id)

    def test_copy_host_field_settings_matches_boost(self):
        function = between(BOOST, "async function copyHostFieldSettingsToTadAlt", "function clearAFBData")
        field_sets = [
            {"Pine Tree": {"shape": "", "size": "xl", "width": 0, "shift_lock": 1, "turn": "", "distance": None,
                           "goo": "x", "goo_interval": 0, "start_location": "", "turn_times": 0}},
            {"pine_tree": {"shape": "lines", "invert_lr": True, "field_drift_compensation": "yes"}},
            {" PINE   TREE ": {}},
            {"clover": {"shape": "x"}},
        ]
        script = """
let saved = null, text = "";
const button = {classList: {contains: () => false, add() {}, remove() {}}, set textContent(v) { text = v; }};
globalThis.setTimeout = () => 0;
globalThis.loadInputs = () => {};
globalThis.loadAllSettings = async () => ({tad_alt_default_field: " Pine Tree "});
""" + function + """
async function run(fields) {
  saved = null; text = "";
  globalThis.eel = {loadFields: () => async () => fields, saveDictProfileSettings: (v) => async () => { saved = v; }};
  await copyHostFieldSettingsToTadAlt(button);
  return {saved, text};
}
"""
        expected = run_node(script, "(async () => { const out = []; for (const f of %s) out.push(await run(f)); return out; })()"
                            % json.dumps(field_sets))
        for fields, js in zip(field_sets, expected):
            with self.subTest(fields=fields):
                app = App()
                app.manager.settings = {"tad_alt_default_field": " Pine Tree "}
                app.manager.fields = fields
                control = Control(master=None)
                control.widget = Button(None, "Copy Settings", None)
                cfg._copy_host_field_settings(app, {}, control)
                if js["saved"] is None:
                    self.assertEqual(app.manager.saved, [])
                    self.assertEqual(control.widget.text, "Copy Failed")
                else:
                    self.assertEqual(app.manager.saved, [js["saved"]])
                    self.assertEqual(control.widget.text, "Copied")

    def test_cannon_attempt_clamps_match_saveSetting(self):
        function = between(SCRIPT, "async function saveSetting(ele, type)", "function isPriorityLockedTask")
        script = """
const inputs = {};
const calls = [];
globalThis.document = {getElementById: (id) => inputs[id] || null, querySelectorAll: () => []};
globalThis.getInputValue = (id) => inputs[id].value === "" ? 0 : inputs[id].value;
globalThis.eel = {saveGeneralSetting: (k, v) => async () => { calls.push([k, v]); },
                  saveProfileSetting: (k, v) => async () => {}};
""" + function + """
async function run(id, maxValue, hiveValue) {
  inputs.max_cannon_attempts = {value: maxValue, id: "max_cannon_attempts", dataset: {}};
  inputs.cannon_hive_resync_attempts = {value: hiveValue, id: "cannon_hive_resync_attempts", dataset: {}};
  calls.length = 0;
  await saveSetting(inputs[id], "general");
  return {calls: calls.slice(), max: inputs.max_cannon_attempts.value, hive: inputs.cannon_hive_resync_attempts.value};
}
"""
        values = ["", "0", "1", "2", "3", "5", "24", "25", "26", "99", "abc", "2.7", "-4", " 7"]
        cases = [(key, a, b) for key in ("max_cannon_attempts", "cannon_hive_resync_attempts")
                 for a in values for b in values]
        expected = run_node(script, "(async () => { const out = []; for (const c of %s) out.push(await run(...c)); return out; })()"
                            % json.dumps(cases))
        for (key, max_value, hive_value), js in zip(cases, expected):
            with self.subTest(key=key, max=max_value, hive=hive_value):
                app = App()
                app.controls = {"max_cannon_attempts": TypedControl(max_value),
                                "cannon_hive_resync_attempts": TypedControl(hive_value)}
                cfg._save_cannon_attempts(app, {"id": key}, app.controls[key])
                self.assertEqual([[k, v] for k, v, scope in app.saves], js["calls"])
                self.assertEqual({scope for _, _, scope in app.saves} - {"general"}, set())
                self.assertEqual(str(app.controls["max_cannon_attempts"].value), str(js["max"]))
                self.assertEqual(str(app.controls["cannon_hive_resync_attempts"].value), str(js["hive"]))





# ---------------------------------------------------------------------------
# Priority list behavior
# ---------------------------------------------------------------------------

ORDER = ["gather_pine_tree", "collect_wealth_clock", "quest_polar_bear", "kill_ladybug",
         "quest_brown_bear", "planters", "mondo_buff", "blender"]


def priority_view(order=ORDER, settings=None):
    app = App(dict(settings or {}, task_priority_order=list(order)))
    spec = {"id": "task_priority_order"}
    with widgets():
        view = cfg.PriorityList(app, Widget(), spec, CUSTOM_DEFINITIONS["task_priorities"])
    return app, view


def shown(view):
    names = {id(w): i for i, w in view.rows.items()}
    names.update({id(w): "[" + g + "]" for g, w in view.headers.items()})
    return [names[id(w)] for w in view.list.slaves]


class PriorityListTests(unittest.TestCase):
    def test_locked_groups_stay_at_their_positions(self):
        app, view = priority_view()
        self.assertEqual(shown(view), ["gather_pine_tree", "collect_wealth_clock", "[quest]", "kill_ladybug",
                                       "[planter]", "mondo_buff", "blender"])
        self.assertEqual(view.get(), ["gather_pine_tree", "collect_wealth_clock", "quest_polar_bear",
                                      "quest_brown_bear", "kill_ladybug", "planters", "mondo_buff", "blender"])

    def test_drag_reorders_and_saves_merged_order(self):
        app, view = priority_view()
        with widgets():
            view._press("blender")
            view.drag["y"] = 0
            view._motion(SimpleNamespace(y_root=1))
        self.assertEqual(view.unlocked[0], "blender")
        with widgets():
            view._release(None)
        self.assertEqual(app.settings["task_priority_order"], app.manager.saved[-1]["task_priority_order"])
        merged = app.manager.saved[-1]["task_priority_order"]
        self.assertEqual([i for i in merged if not cfg.is_priority_locked(i)][0], "blender")
        self.assertEqual(merged.index("quest_polar_bear"), 2)
        self.assertEqual(merged.index("planters"), 5)

    def test_click_without_motion_does_not_save(self):
        app, view = priority_view()
        view._press("blender")
        view._release(None)
        self.assertEqual(app.manager.saved, [])

    def test_top_and_bottom_buttons_ignore_hidden_rows(self):
        app, view = priority_view()
        view.move("mondo_buff", 0)
        self.assertEqual(view.unlocked[0], "mondo_buff")
        view.move("mondo_buff", None)
        self.assertEqual(view.unlocked[-1], "mondo_buff")
        self.assertEqual(len(app.manager.saved), 2)

    def test_search_filters_rows_and_lock_headers(self):
        app, view = priority_view()
        view.showing_placeholder = False
        view.search.set("clock")
        self.assertEqual(shown(view), ["collect_wealth_clock"])
        view.search.set("locked")
        self.assertEqual(shown(view), ["[quest]", "[planter]"])
        view.search.set("planters")
        self.assertEqual(shown(view), ["[planter]"])
        view.search.set("")
        self.assertEqual(len(shown(view)), 7)

    def test_set_replaces_order_and_ignores_non_lists(self):
        app, view = priority_view()
        with widgets():
            view.set(["planters", "gather_clover"])
            self.assertEqual(shown(view), ["[planter]", "gather_clover"])
            view.set(None)
        self.assertEqual(shown(view), ["[planter]", "gather_clover"])
        self.assertEqual(view.get(), ["planters", "gather_clover"])

    def test_reset_requires_confirmation_and_reloads_backend_order(self):
        app, view = priority_view()
        app.action_results["resetTaskPrioritiesToDefault"] = lambda: True
        app.manager.settings = {"task_priority_order": ["kill_ladybug", "planters"]}
        app.manager.loadAllSettings = lambda: dict(app.manager.settings)
        with widgets(), patch.object(cfg, "messagebox") as box:
            box.askyesno.return_value = False
            view.reset()
            self.assertEqual(len(view.get()), len(ORDER))
            self.assertFalse(box.showinfo.called)
            box.askyesno.return_value = True
            view.reset()
            self.assertTrue(box.showinfo.called)
        self.assertEqual(view.get(), ["kill_ladybug", "planters"])
        self.assertEqual(app.refreshes, 1)

    def test_failed_reset_reports_and_keeps_list(self):
        app, view = priority_view()
        app.action_results["resetTaskPrioritiesToDefault"] = lambda: False
        with patch.object(cfg, "messagebox") as box:
            box.askyesno.return_value = True
            view.reset()
            self.assertEqual(box.showerror.call_args[0][1],
                             "Failed to reset task priorities. Default order may be missing.")
        self.assertEqual(len(view.get()), len(ORDER))

    def test_disabled_tasks_are_dimmed_from_current_settings(self):
        app, view = priority_view(settings={"mondo_buff": True})
        palette = view.palette
        self.assertEqual(view.rows["mondo_buff"].options["highlightbackground"], palette["border"])
        self.assertEqual(view.rows["mondo_buff"].parts[0].options["bg"], "#262626")
        self.assertEqual(view.rows["blender"].parts[0].options["bg"], palette["dim_surface"])
        app.settings["blender"] = True
        view.refresh_highlights()
        self.assertEqual(view.rows["blender"].parts[0].options["bg"], "#262626")


# ---------------------------------------------------------------------------
# Custom builders and actions
# ---------------------------------------------------------------------------

class BuilderTests(unittest.TestCase):
    def test_every_custom_action_in_the_definitions_has_a_builder(self):
        actions = set()

        def walk(value):
            if isinstance(value, dict):
                if value.get("kind") == "custom":
                    actions.add(value["action"])
                for child in value.values():
                    walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)
        walk(TAB_DEFINITIONS)
        self.assertEqual(actions - set(cfg._BUILDERS), set())
        with self.assertRaises(ValueError):
            cfg.build_custom(App(), Widget(), {"action": "not_a_widget"})

    def test_button_and_save_actions_are_owned_exactly_once(self):
        actions = set()

        def walk(value):
            if isinstance(value, dict):
                if value.get("action") and value.get("kind") != "custom":
                    actions.add(value["action"])
                for child in value.values():
                    walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)
        walk(TAB_DEFINITIONS)
        required = {"fallback_private_servers", "export_debug", "update_from_hash",
                    "copy_host_field_settings_to_tad_alt", "select_discord_delivery_mode",
                    "sync_glitter_hotbar_slot", "save_cannon_attempts"}
        self.assertEqual(required - set(cfg._ACTIONS), set())
        self.assertEqual(set(cfg._ACTIONS) - actions, set())
        self.assertFalse(cfg.handle_action(App(), "record_keybind", {}, None))
        self.assertFalse(cfg.handle_action(App(), "apply_theme", {}, None))
        self.assertFalse(cfg.handle_action(App(), "save_gather_field", {}, None))

    def test_hotbar_builds_seven_slots_from_the_definitions(self):
        app = App()
        parent = Widget()
        with widgets():
            control = cfg.build_custom(app, parent, {"action": "hotbar"})
        sections = CUSTOM_DEFINITIONS["hotbar"]["sections"]
        ids = [spec["id"] for _, spec in app.added]
        expected = [c["id"] for section in sections for c in section["controls"]]
        self.assertEqual(ids, expected)
        self.assertEqual(len(ids), 21)
        for _, spec in app.added:
            self.assertEqual(spec["scope"], "profile")
            self.assertNotIn("tool", spec["id"])
        self.assertEqual(control.get(), 1)

    def test_quest_overrides_use_the_six_source_givers(self):
        app = App()
        with widgets():
            cfg.build_custom(app, Widget(), {"action": "quest_overrides"})
        ids = [spec["id"] for _, spec in app.added]
        self.assertEqual(ids, ["{}_quest_gather_{}".format(giver, kind)
                               for giver in ("polar_bear", "brown_bear", "black_bear", "honey_bee",
                                             "bucko_bee", "riley_bee") for kind in ("mins", "return")])
        returns = [spec for _, spec in app.added if spec["id"].endswith("_return")]
        self.assertEqual([c["value"] for c in returns[0]["choices"]],
                         ["no override", "reset", "walk", "rejoin", "whirligig"])
        self.assertTrue(all(spec["limit"] == 4 and spec["numeric"] == "float"
                            for _, spec in app.added if spec["id"].endswith("_mins")))

    def test_glitter_slot_updates_all_three_controls_and_saves_each(self):
        app = App()
        for key in cfg.GLITTER_SLOT_IDS:
            app.controls[key] = Control(1)
        cfg.handle_action(app, "sync_glitter_hotbar_slot", {}, app.controls["AFB_slotG"])
        app.controls["AFB_slotG"].value = "4"
        self.assertTrue(cfg.handle_action(app, "sync_glitter_hotbar_slot", {}, app.controls["AFB_slotG"]))
        self.assertEqual([c.value for c in app.controls.values()], [4, 4, 4])
        self.assertEqual(app.saves[-3:], [(key, 4, "profile") for key in cfg.GLITTER_SLOT_IDS])

    def test_beta_update_validates_confirms_and_reports_backend_result(self):
        app = App()
        app.actions.updateFromHash = lambda commit: commit == "abcdef1"
        control = Control("abc")
        with patch.object(cfg, "messagebox") as box:
            cfg.handle_action(app, "update_from_hash", {}, control)
            self.assertEqual(box.showwarning.call_args[0][1], "Please enter a valid 7-character hex commit hash.")
            control.value = " abcdef1 "
            box.askyesno.return_value = False
            cfg.handle_action(app, "update_from_hash", {}, control)
            self.assertFalse(box.showinfo.called)
            box.askyesno.return_value = True
            cfg.handle_action(app, "update_from_hash", {}, control)
            self.assertEqual(box.showinfo.call_args[0][1], "Update started. The app may close to apply the update.")
            control.value = "1234567"
            cfg.handle_action(app, "update_from_hash", {}, control)
            self.assertEqual(box.showerror.call_args[0][1], "Update failed or was aborted. Check logs for details.")
            app.actions.updateFromHash = lambda commit: 1 / 0
            cfg.handle_action(app, "update_from_hash", {}, control)
            self.assertIn("Error initiating update:", box.showerror.call_args[0][1])
        self.assertFalse(app.update_running)

    def test_debug_export_saves_the_backend_zip_only_on_success(self):
        app = App()
        payload = b"zip bytes"
        folder = Path(tempfile.mkdtemp())
        target = folder / "debug.zip"
        try:
            app.action_results["exportDebugZip"] = lambda profile: (True, base64.b64encode(payload).decode(), "name.zip")
            with patch.object(cfg, "messagebox") as box, patch.object(cfg, "filedialog") as dialog:
                dialog.asksaveasfilename.return_value = str(target)
                cfg.handle_action(app, "export_debug", {"title": "Export"}, None)
                self.assertEqual(target.read_bytes(), payload)
                self.assertEqual(dialog.asksaveasfilename.call_args[1]["initialfile"], "name.zip")
                app.action_results["exportDebugZip"] = lambda profile: (False, "disk full")
                cfg.handle_action(app, "export_debug", {"title": "Export"}, None)
                self.assertEqual(box.showerror.call_args[0][1], "Export failed: disk full")
                app.action_results["exportDebugZip"] = lambda profile: None
                cfg.handle_action(app, "export_debug", {"title": "Export"}, None)
                self.assertEqual(box.showerror.call_args[0][1], "Failed to export debug folder.")
        finally:
            shutil.rmtree(str(folder))

    def test_discord_mode_saves_general_setting_and_toggles_rows(self):
        app = App()
        container = Widget()
        names = ["discord_delivery_mode", "discord_bot_token", "webhook_time_format", "webhook_link",
                 "discord_channel_id"]
        rows = {}
        for name in names:
            row = Widget(container)
            row.pack(fill="x")
            rows[name] = row
            control = Control("", row)
            control.widget = Widget(row)
            app.controls[name] = control
        app.controls["discord_delivery_mode"].value = "webhook"
        with widgets():
            cfg.handle_action(app, "select_discord_delivery_mode", {}, app.controls["discord_delivery_mode"])
        self.assertEqual(app.saves, [("discord_delivery_mode", "webhook", "general")])
        order = lambda: [n for n in names if rows[n].winfo_manager()]
        self.assertEqual(order(), ["discord_delivery_mode", "webhook_time_format", "webhook_link"])
        app.controls["discord_delivery_mode"].value = "discord_bot"
        cfg.handle_action(app, "select_discord_delivery_mode", {}, app.controls["discord_delivery_mode"])
        self.assertEqual(order(), ["discord_delivery_mode", "discord_bot_token", "webhook_time_format",
                                   "discord_channel_id"])
        app.controls["discord_delivery_mode"].value = ""
        cfg.handle_action(app, "select_discord_delivery_mode", {}, app.controls["discord_delivery_mode"])
        self.assertEqual(order(), names[:4])
        self.assertEqual(container.slaves, [rows[n] for n in names[:4]])

    def test_model_groups_follow_the_backend_status(self):
        definition = CUSTOM_DEFINITIONS["model_downloads"]
        models = [{"name": "bloom_detection_mini.onnx", "installed": True, "size_bytes": 3 * 1024 * 1024},
                  {"name": "token_detection_standard.onnx", "installed": False, "size_bytes": 0},
                  {"name": "mystery.bin", "installed": False}]
        groups = cfg.model_groups(models, definition)
        self.assertEqual([(g, [(m["name"], label) for m, label in items]) for g, items in groups],
                         [("Standard", [("token_detection_standard.onnx", "Token Detection")]),
                          ("Mini", [("bloom_detection_mini.onnx", "Bloom Detection")]),
                          ("Other", [("mystery.bin", "AI Model")])])
        self.assertEqual(cfg._format_model_size(3 * 1024 * 1024), "3.0 MB")
        self.assertEqual(cfg._format_model_size(0), "")

    def test_model_download_reports_real_backend_outcomes(self):
        app = App()
        calls = []
        statuses = [{"models": [{"name": "token_detection_standard.onnx", "installed": False, "size_bytes": 0}]},
                    {"models": []}]
        app.actions.getModelStatus = lambda: statuses.pop(0)
        results = [{"ok": False, "message": "busy"},
                   {"ok": False, "failures": {"x": "y"}},
                   {"ok": True, "message": "Downloaded missing models."}]
        app.actions.downloadMissingModels = lambda names: calls.append(names) or results.pop(0)
        with widgets():
            control = cfg.build_custom(app, Widget(), {"action": "model_downloads"})
        body = control.widget
        status, download_all = model_widgets(control)
        self.assertEqual(status.cget("text"), "1 model missing.")
        download_all.command()
        self.assertEqual(status.cget("text"), "busy")
        download_all.command()
        self.assertEqual(status.cget("text"),
                         "Some models could not be downloaded. Check your internet connection and try again.")
        download_all.command()
        self.assertEqual(calls, [None, None, None])
        self.assertEqual(status.cget("text"), "All supported models are installed.")
        self.assertIn("All installed", [w.cget("text") for w in descendants(body)])
        self.assertTrue(download_all.enabled)

    def test_model_status_failure_is_visible(self):
        app = App()
        app.actions.getModelStatus = lambda: 1 / 0
        with widgets():
            control = cfg.build_custom(app, Widget(), {"action": "model_downloads"})
        texts = [w.cget("text") for w in descendants(control.widget)]
        self.assertIn("Could not check installed models.", texts)
        self.assertIn("Unavailable", texts)

    def test_models_start_collapsed_and_toggle_without_reloading(self):
        source = (ROOT / "src/webapp/htmlImports/tabs/config.html").read_text()
        self.assertIn('<details class="model-downloads">', source)
        self.assertNotIn('<details class="model-downloads" open', source)
        app = App()
        calls = []
        app.actions.getModelStatus = lambda: calls.append(True) or {"models": [
            {"name": "token_detection_standard.onnx", "installed": False}]}
        parent = Widget()
        heading = Widget(parent, text="AI Models")
        heading.pack(fill="x")
        description = Widget(parent, text="Download only the AI models that are missing from this Mac.")
        description.pack(fill="x")
        with widgets():
            control = cfg.build_custom(app, parent, {"action": "model_downloads"})
        body = control.widget
        header, content = body.children
        self.assertFalse(heading.winfo_manager())
        self.assertFalse(description.winfo_manager())
        self.assertEqual(body.pack_slaves(), [header])
        self.assertIn("1 missing", [w.cget("text") for w in header.children])
        header.bindings["<ButtonRelease-1>"](None)
        self.assertEqual(body.pack_slaves(), [header, content])
        self.assertIn(description.cget("text"), [w.cget("text") for w in content.children])
        header.bindings["<space>"](None)
        self.assertEqual(body.pack_slaves(), [header])
        header.bindings["<Return>"](None)
        self.assertEqual(body.pack_slaves(), [header, content])
        self.assertEqual(calls, [True])
        for widget in descendants(body):
            font = widget.options.get("font")
            if font:
                self.assertEqual(font[0], "Helvetica")

    def test_download_exception_and_failed_refresh_unlock_buttons(self):
        for refresh_failure in (False, True):
            with self.subTest(refresh_failure=refresh_failure):
                app = App()
                pending = []
                app.run_async = lambda work, done: pending.append((work, done))
                app.actions.getModelStatus = lambda: {"models": [
                    {"name": "token_detection_standard.onnx", "installed": False}]}
                with widgets():
                    control = cfg.build_custom(app, Widget(), {"action": "model_downloads"})
                    work, done = pending.pop(0)
                    done(work())
                    status, download_all = model_widgets(control)
                    buttons = [w for w in descendants(control.widget) if isinstance(w, Button)]
                    self.assertEqual(len(buttons), 2)
                    app.actions.downloadMissingModels = lambda names: {"ok": True}
                    if not refresh_failure:
                        app.actions.downloadMissingModels = lambda names: 1 / 0
                    app.actions.getModelStatus = lambda: 1 / 0
                    download_all.command()
                    self.assertTrue(all(not button.enabled for button in buttons))
                    work, done = pending.pop(0)
                    done(work())
                    if refresh_failure:
                        work, done = pending.pop(0)
                        done(work())
                        self.assertEqual(status.cget("text"), "Could not check installed models.")
                    else:
                        self.assertIn("Could not download models:", status.cget("text"))
                    self.assertTrue(all(button.enabled for button in buttons))

    def test_deferred_model_callbacks_ignore_destroyed_widgets(self):
        for during_download in (False, True):
            with self.subTest(during_download=during_download), widgets():
                app = App()
                pending = []
                app.run_async = lambda work, done: pending.append((work, done))
                app.actions.getModelStatus = lambda: {"models": [
                    {"name": "token_detection_standard.onnx", "installed": False}]}
                app.actions.downloadMissingModels = lambda names: {"ok": True}
                control = cfg.build_custom(app, Widget(), {"action": "model_downloads"})
                if during_download:
                    work, done = pending.pop(0)
                    done(work())
                    model_widgets(control)[1].command()
                control.widget.destroy()
                work, done = pending.pop(0)
                done(work())
                self.assertEqual(pending, [])

    def test_async_wrapper_delivers_actual_results_and_worker_errors(self):
        app = App()
        outcomes = []
        value = {"ok": False, "message": "Already downloading."}
        cfg._run_async(app, lambda: value, lambda ok, result: outcomes.append((ok, result)))
        self.assertEqual(outcomes, [(True, value)])
        self.assertIs(outcomes[0][1], value)
        cfg._run_async(app, lambda: 1 / 0, lambda ok, result: outcomes.append((ok, result)))
        self.assertFalse(outcomes[-1][0])
        self.assertIsInstance(outcomes[-1][1], ZeroDivisionError)
        worker_error = RuntimeError("Worker failed")
        app.run_async = lambda work, done: done(None, worker_error)
        cfg._run_async(app, lambda: value, lambda ok, result: outcomes.append((ok, result)))
        self.assertEqual(outcomes[-1], (False, worker_error))

    def test_hash_update_uses_shared_lock_and_releases_it_after_close(self):
        app = App()
        pending = []
        app.run_async = lambda work, done: pending.append((work, done))
        app.actions.updateFromHash = lambda commit: False
        with patch.object(cfg, "messagebox") as box:
            box.askyesno.return_value = True
            app.update_running = True
            cfg.handle_action(app, "update_from_hash", {}, Control("abcdef1"))
            self.assertEqual(pending, [])
            self.assertFalse(box.askyesno.called)
            app.update_running = False
            def start_other_update(*args, **kwargs):
                app.update_running = True
                return True
            box.askyesno.side_effect = start_other_update
            cfg.handle_action(app, "update_from_hash", {}, Control("abcdef1"))
            self.assertEqual(pending, [])
            box.askyesno.side_effect = None
            app.update_running = False
            cfg.handle_action(app, "update_from_hash", {}, Control("abcdef1"))
            self.assertTrue(app.update_running)
            app.root.destroy()
            work, done = pending.pop(0)
            done(work())
            self.assertFalse(app.update_running)
            self.assertFalse(box.showerror.called)


class CompatibilityTests(unittest.TestCase):
    def test_source_parses_as_python_37(self):
        source = (ROOT / "src/modules/gui/configuration.py").read_text()
        ast.parse(source, feature_version=(3, 7))


# ---------------------------------------------------------------------------
# Profile workflows against a temporary copy of settingsManager
# ---------------------------------------------------------------------------

def load_manager(root):
    misc = Path(root) / "src" / "modules" / "misc"
    misc.mkdir(parents=True)
    for name in ("settingsManager.py", "settings_defaults.py"):
        shutil.copy(str(ROOT / "src/modules/misc" / name), str(misc / name))
    sys.path.insert(0, str(misc))
    try:
        spec = importlib.util.spec_from_file_location("isolated_settings_manager", str(misc / "settingsManager.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(misc))
    return module


class ProfileWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.manager = load_manager(self.root)
        self.addCleanup(shutil.rmtree, self.root, True)
        self.assertTrue(self.manager.getProjectRoot().startswith(self.root))
        self.app = App()
        self.app.manager = self.manager

    def test_profile_list_caps_height_and_keeps_switch_actions_in_scroller(self):
        for number in range(12):
            self.assertTrue(self.manager.createProfile("profile{}".format(number))[0])
        with widgets():
            control = cfg.build_custom(self.app, Widget(), {"action": "switch_profile"})
            scroller = next(w for w in control.widget.children if isinstance(w, Scroll))
            listing = scroller.body
            self.assertEqual(len(listing.children), len(self.manager.listProfiles()))
            listing.bindings["<Configure>"](SimpleNamespace(height=800))
            self.assertEqual(scroller.canvas.cget("height"), 400)
            scroller.canvas.options["yscrollcommand"]("0", "0.4")
            self.assertTrue(scroller.bar.winfo_manager())
            listing.bindings["<Configure>"](SimpleNamespace(height=90))
            self.assertEqual(scroller.canvas.cget("height"), 90)
            scroller.canvas.options["yscrollcommand"]("0", "1")
            self.assertFalse(scroller.bar.winfo_manager())
            switch = next(w for w in descendants(listing) if isinstance(w, Button) and w.text == "Switch")
            row = switch.master.master
            profile = row.children[0].children[0].cget("text")
            switch.command()
            self.assertEqual(self.manager.getCurrentProfile(), profile)
            self.assertEqual(len(listing.children), len(self.manager.listProfiles()))

    def test_create_and_duplicate_use_manager_name_rules(self):
        self.assertEqual(cfg.create_profile(self.app, "   "), (False, "Please enter a profile name"))
        ok, message = cfg.create_profile(self.app, "  My New Profile ")
        self.assertTrue(ok, message)
        self.assertIn("my_new_profile", self.manager.listProfiles())
        self.assertEqual(cfg.create_profile(self.app, "My New Profile")[0], False)
        self.assertEqual(cfg.duplicate_profile(self.app, "my_new_profile", " "),
                         (False, "Please enter a new profile name"))
        ok, message = cfg.duplicate_profile(self.app, "my_new_profile", "Copy Of It")
        self.assertTrue(ok, message)
        self.assertIn("copy_of_it", self.manager.listProfiles())
        self.assertFalse(cfg.duplicate_profile(self.app, "missing", "other")[0])

    def test_export_blanks_private_values_and_writes_the_manager_file(self):
        self.manager.saveGeneralSetting("webhook_link", "https://discord.com/api/webhooks/1/secret")
        self.manager.saveGeneralSetting("discord_bot_token", "tokentokentoken")
        self.manager.saveGeneralSetting("private_server_link", "https://www.roblox.com/games/1?privateServerLinkCode=1")
        self.manager.saveGeneralSetting("route_reports", "https://discord.com/api/webhooks/2/secret")
        profile = self.manager.getCurrentProfile()
        target = Path(self.root) / "export.json"
        names = []
        result = cfg.export_profile(self.app, profile, lambda name: names.append(name) or str(target))
        self.assertEqual(result, (True, "Profile exported as export.json"))
        self.assertTrue(names[0].startswith("profile_{}_".format(profile)) and names[0].endswith(".json"))
        data = json.loads(target.read_text(encoding="utf-8"))
        for section in (data["settings"], data["generalsettings"]):
            for key in ("webhook_link", "discord_bot_token", "private_server_link", "route_reports"):
                self.assertEqual(section.get(key, ""), "", key)
        self.assertNotIn("secret", target.read_text(encoding="utf-8"))
        self.assertEqual(data["profile_name"], profile)

    def test_export_cancel_and_errors_write_nothing(self):
        self.assertEqual(cfg.export_profile(self.app, "", lambda name: "x"),
                         (False, "Please select a profile to export"))
        self.assertIsNone(cfg.export_profile(self.app, self.manager.getCurrentProfile(), lambda name: ""))
        self.assertFalse(cfg.export_profile(self.app, "missing", lambda name: "x")[0])

    def test_import_round_trip_requires_a_name_and_keeps_data(self):
        self.manager.saveProfileSetting("task_priority_order", ["blender", "planters"])
        profile = self.manager.getCurrentProfile()
        path = Path(self.root) / "profile.json"
        cfg.export_profile(self.app, profile, lambda name: str(path))
        self.assertEqual(cfg.import_profile(self.app, str(path), " "), (False, "Please enter a profile name"))
        ok, message = cfg.import_profile(self.app, str(path), " Imported One ")
        self.assertTrue(ok, message)
        self.assertEqual(message, "Profile imported successfully as 'imported_one'")
        self.manager.switchProfile("imported_one")
        self.assertEqual(self.manager.loadAllSettings()["task_priority_order"][:2], ["blender", "planters"])
        self.assertFalse(cfg.import_profile(self.app, str(path), "imported_one")[0])
        path.write_text("not json", encoding="utf-8")
        self.assertEqual(cfg.import_profile(self.app, str(path), "other"), (False, "Invalid JSON content"))
        with self.assertRaises(IOError):
            cfg.import_profile(self.app, str(Path(self.root) / "missing.json"), "other")


if __name__ == "__main__":
    unittest.main()
