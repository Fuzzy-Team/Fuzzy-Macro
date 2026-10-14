"""Headless parity checks against shipped JS. Never import gui.py or start Tk."""

import ast
import json
from pathlib import Path
import random
import re
import shutil
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from modules.gui import calculators as calc
from modules.gui import editors
from modules.gui import token_data
from modules.misc.settings_defaults import DEFAULT_PROFILE_SETTINGS


NODE = shutil.which("node")


def javascript(source, expression):
    """Execute actual source with only the browser-loading hook disabled."""
    script = ('const $ = () => ({load() {return this;}, on() {return this;}});\n'
              + source + '\nprocess.stdout.write(JSON.stringify(' + expression + '));')
    result = subprocess.run([NODE, "-e", script], check=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, universal_newlines=True, cwd=str(ROOT))
    # JS JSON integers are still IEEE doubles. Keep their Number semantics
    # instead of interpreting the printed decimal as an exact Python integer.
    return json.loads(result.stdout, parse_int=float)


TOOLS = (ROOT / "src/webapp/scripts/tabs/tools.js").read_text()
GATHER = (ROOT / "src/webapp/scripts/tabs/gather.js").read_text()
COLLECT = (ROOT / "src/webapp/scripts/tabs/collect.js").read_text()
TOKENS = GATHER[GATHER.index("const fuzzyAITokenNames ="):GATHER.index("function renderFuzzyAITokenList()")]


@unittest.skipUnless(NODE, "Node is required only for source differential tests")
class CalculatorParityTests(unittest.TestCase):
    def test_treat_rounding_and_breakdown(self):
        cases = [(1, 25, bonus, bees) for bonus in (0, 20, 100, 100.1, 120, 250.5, 300) for bees in (1, 50)]
        cases += [(12, 18, 133.3, 37), (24, 25, 120, 50)]
        expected = javascript(TOOLS, "{}.map(args => buildBondBreakdownRows(...args))".format(json.dumps(cases)))
        for args, rows in zip(cases, expected):
            with self.subTest(args=args):
                self.assertEqual(calc.build_bond_breakdown_rows(*args), rows)

    def test_bond_display_and_input_normalization(self):
        cases = [[1, 25, 20, 50], [1, 20, 120, 50], [24, 25, 133.3, 49],
                 [5, 5, -2, 0], [7, 2, "bad", "bad"], [2, 4, 999, 90],
                 [1, 10, "120.5bonus", "3.5"]]
        # Let updateBondTreatCalculator normalize the actual source DOM inputs.
        script = TOOLS + """
const ids = ["start-level", "end-level", "bonus", "bee-count"];
function runBond(args) {
  const elements = {};
  for (const id of ["start-level", "end-level", "bonus", "bee-count", "warning", "total-bond", "total-treats-label", "total-treats", "total-cost-one", "total-cost-bees-label", "total-cost-bees", "breakdown-cost-bees-label", "breakdown"]) {
    elements["bond-calc-" + id] = {value: "", style: {}, textContent: "", innerHTML: ""};
  }
  ids.forEach((id, i) => {elements["bond-calc-" + id].value = String(args[i]);});
  global.document = {getElementById: id => elements[id]};
  updateBondTreatCalculator();
  return {bonus: elements["bond-calc-bonus"].value, bees: elements["bond-calc-bee-count"].value,
    totals: ["total-bond", "total-treats", "total-cost-one", "total-cost-bees"].map(id => elements["bond-calc-" + id].textContent),
    warning: elements["bond-calc-warning"].style.display === "block" ? elements["bond-calc-warning"].textContent : ""};
}
"""
        expected = javascript(script, "{}.map(runBond)".format(json.dumps(cases)))
        for args, result in zip(cases, expected):
            actual = calc.calculate_bond(*args)
            self.assertEqual(actual["bonus_percent"], result["bonus"])
            self.assertEqual(actual["bee_count"], result["bees"])
            self.assertEqual(actual["warning"], result["warning"])
            self.assertEqual([calc.format_compact_honey(actual[key]) for key in
                              ("total_bond", "total_treats", "cost_one", "cost_bees")], result["totals"])

    def test_ticket_price_boundaries_and_inverse(self):
        prices = [100000, 101000, 101999, 102000, 1823000, 1824000, 1825000,
                  100000000, 999999999000, 1e18]
        bought = list(range(0, 1000)) + [10000, 100000]
        expected = javascript(TOOLS, "({inverse: %s.map(getTicketsBoughtFromNextPrice), forward: %s.map(getTicketPriceAfterBought)})" %
                              (json.dumps(prices), json.dumps(bought)))
        self.assertEqual([calc.get_tickets_bought_from_next_price(price) for price in prices], expected["inverse"])
        self.assertEqual([calc.get_ticket_price_after_bought(count) for count in bought], expected["forward"])

    def test_ticket_normalization(self):
        cases = [[value, unit] for value in ("", "bad", -10, 0, 0.1, 100, 100.499, 100.5, 100.501, "0x10")
                 for unit in (1, 1000, "1000000", "", "bad")]
        expected = javascript(TOOLS, "{}.map(args => normalizeTicketPrice(...args))".format(json.dumps(cases)))
        self.assertEqual([calc.normalize_ticket_price(*args) for args in cases], expected)

    def test_ticket_purchases_and_budget(self):
        rng = random.Random(41)
        cases = [[price, amount] for price in (100000, 101000, 102000, 1824000, 1825000, 100000000)
                 for amount in (-1, 0, 1, 10.9, 100, 500, "bad")]
        cases += [[calc.normalize_ticket_price(rng.uniform(0, 1000), 1000000), rng.randint(1, 2500)] for _ in range(15)]
        cases += [[100000, 100001]]
        expected = javascript(TOOLS, "{}.map(args => calculateTicketPurchase(...args))".format(json.dumps(cases)))
        for args, result in zip(cases, expected):
            with self.subTest(args=args):
                self.assertEqual(calc.calculate_ticket_purchase(*args), result)
        budgets = [[price, budget] for price in (100000, 1824000, 100000000)
                   for budget in (-1, 0, price - 1, price, price + 1, 1e9, 1e12, 1e18)]
        expected = javascript(TOOLS, "{}.map(args => calculateTicketsForBudget(...args))".format(json.dumps(budgets)))
        for args, result in zip(budgets, expected):
            self.assertEqual(calc.calculate_tickets_for_budget(*args), result)

    def test_compact_and_whole_formatting(self):
        values = [0, 1, -1, 0.125, 1.005, 1.125, 999.999, 1000, -1250, 1e6, 1e9, 1e12, 1e15, 1e18, 1.234567e20,
                  899100899100900000, 4745254745255000000, 3958333333333500000]
        expected = javascript(TOOLS, "{}.map(value => [formatCompactHoney(value), formatWholeNumber(value)])".format(json.dumps(values)))
        self.assertEqual([[calc.format_compact_honey(value), calc.format_whole_number(value)] for value in values], expected)


@unittest.skipUnless(NODE, "Node is required only for source differential tests")
class EditorSourceParityTests(unittest.TestCase):
    def test_token_models_and_rankings(self):
        models = javascript(TOKENS, "fuzzyAITokenNamesByModel")
        self.assertEqual({name.title(): list(tokens) for name, tokens in token_data.TOKEN_NAMES_BY_MODEL.items()}, models)
        ranking = dict(preferred_tokens=" Token Link,Unknown,Focus,Token Link,Bloom ", ignored_tokens="Focus,Unknown")
        for model in ("standard", "light", "mini"):
            setup = TOKENS + '\nfuzzyAISelectedModel = %s;\n' % json.dumps(model.title())
            setup += 'const document = {getElementById: id => ({value: id.includes("preferred") ? %s : %s})};' % (
                json.dumps(ranking["preferred_tokens"]), json.dumps(ranking["ignored_tokens"]))
            expected = javascript(setup, "getFuzzyAITokenState()")
            self.assertEqual(token_data.token_state(ranking, model), [(row["name"], row["enabled"]) for row in expected])

    def test_sprout_presets_and_hidden_tokens(self):
        sprout_source = COLLECT[COLLECT.index("const sproutAITokenPriority ="):COLLECT.index("async function saveSproutAITokenPopup()")]
        for model in ("standard", "token_light", "loot_mini"):
            for field in ("sunflower", "pine tree", "rose", "unknown"):
                for preset in ("field", "all", "clear"):
                    setup = TOKENS + '\n' + sprout_source + '\n'
                    setup += 'const inputs = {sprouts_preferred_tokens: {value: ""}, sprouts_ignored_tokens: {value: ""}};\n'
                    setup += 'const document = {getElementById: id => inputs[id]};\n'
                    setup += 'getSelectedSproutAIModel = () => %s; getSelectedSproutField = () => %s; renderSproutAITokenList = () => {};\n' % (json.dumps(model), json.dumps(field))
                    setup += 'applySproutAITokenPreset(%s);' % json.dumps(preset)
                    expected = javascript(setup, '({preferred_tokens: inputs.sprouts_preferred_tokens.value, ignored_tokens: inputs.sprouts_ignored_tokens.value})')
                    self.assertEqual(token_data.sprout_preset(preset, field, model), expected)
                    state = token_data.token_state(expected, model, True)
                    self.assertTrue(all(not token_data.hidden_sprout_token(token) for token, _ in state))
                    saved = token_data.token_ranking(state, model, True)
                    self.assertEqual(set(saved["ignored_tokens"].split(",")), set(expected["ignored_tokens"].split(",")))

    def test_planter_presets(self):
        source = (ROOT / "src/webapp/scripts/tabs/planters.js").read_text()
        function = re.search(r"function changePreset\(ele\)\{.*?\n\}", source, re.S).group(0)
        for preset in ("blue", "red", "white", "custom"):
            setup = 'let result = {}; const saveSetting = () => {}; const getInputValue = () => %s; const loadInputs = data => {result = data;};\n' % json.dumps(preset)
            expected = javascript(setup + function + '\nchangePreset({id:"auto_preset"});', "result")
            self.assertEqual(editors.planter_preset(preset), expected)

    def test_planter_icons_and_dropdown_storage(self):
        source = (ROOT / "src/webapp/scripts/emojis.js").read_text()
        expected = javascript(source, "({planters: planterIcons, fields: fieldNectarIcons, nectars: Object.keys(nectarIcons)})")
        self.assertEqual(editors.PLANTER_ICONS, expected["planters"])
        self.assertEqual(editors.FIELD_NECTAR_ICONS, expected["fields"])
        self.assertEqual(list(editors.NECTARS), expected["nectars"])
        self.assertEqual(next(choice["value"] for choice in editors._choices(editors.PLANTER_ICONS)
                              if choice["label"] == "Planter Of Plenty"), "planter of plenty")


class ContractTests(unittest.TestCase):
    def test_defaults_and_bounds(self):
        self.assertEqual(calc.calculate_bond()["end_level"], 25)
        self.assertEqual(calc.calculate_bond()["bonus_percent"], 20)
        self.assertEqual(calc.calculate_tickets()["next_price"], 100000000)
        self.assertEqual(calc.calculate_tickets(custom_amount=100)["rows"][-1][0], 500)
        self.assertEqual(calc.calculate_tickets(custom_amount=0)["custom_amount"], 1)

    def test_selected_planters_keep_first_occurrence(self):
        settings = dict(cycle1_1_planter="red clay", cycle2_1_planter="red clay",
                        cycle3_2_planter="petal", cycle5_3_planter="heat-treated", auto_planter_petal=True)
        self.assertEqual(editors.selected_planters(settings), ["red_clay", "petal", "heat-treated"])
        self.assertEqual(editors.selected_planters(settings, True), ["petal"])

    def test_export_uses_actual_manager_payload(self):
        app = Mock()
        app.manager.exportPlanterSettings.return_value = '{"metadata":{"macro_version":"1.2"},"settings":{"planters_mode":2}}'
        editors._export_planters(app)
        app.root.clipboard_append.assert_called_once_with(app.manager.exportPlanterSettings.return_value)
        app.manager.exportPlanterSettings.assert_called_once_with()
        app.save.assert_not_called()

    def test_failed_export_does_not_replace_clipboard(self):
        app = Mock()
        app.manager.exportPlanterSettings.return_value = None
        editors._export_planters(app)
        app.root.clipboard_clear.assert_not_called()
        self.assertIn("Could not export", app.status.call_args[0][0])

    def test_auto_reset_retains_source_api_and_reports_failure(self):
        app = Mock()
        app.action.return_value = False
        editors._timer_reset(app, True)
        app.action.assert_called_once_with("resetAutoPlanterTimer", "all")
        app.status.assert_called_once_with("Planter timers could not be reset.")

    def test_python_37_syntax(self):
        for filename in ("editors.py", "calculators.py", "token_data.py"):
            source = (ROOT / "src/modules/gui" / filename).read_text()
            if sys.version_info >= (3, 8):
                ast.parse(source, feature_version=(3, 7))
            else:
                ast.parse(source)


def fake_widget(*args, **kwargs):
    widget = Mock()
    widget.winfo_children.return_value = []
    widget.get_children.return_value = ()
    widget.winfo_manager.return_value = ""
    return widget


class HeadlessEditorTests(unittest.TestCase):
    """Exercise builder callbacks without a display, input, or real user files."""

    def setUp(self):
        self.app = Mock()
        self.app.palette = {key: "#111111" for key in ("bg", "surface", "input", "text", "dim", "accent", "border")}
        self.app.settings = dict(DEFAULT_PROFILE_SETTINGS)
        self.app.card.side_effect = fake_widget
        self.controls = {}
        self.buttons = {}

        def add_control(parent, spec, value=None, onchange=None):
            current = [self.app.settings.get(spec["id"]) if value is None else value]
            control = SimpleNamespace(get=lambda: current[0], set=lambda value: current.__setitem__(0, value),
                                      variable=Mock(), widget=Mock(), spec=spec, onchange=onchange)
            self.controls[spec["id"]] = control
            return control

        def button(parent, text, command):
            self.buttons[text] = command
            return fake_widget()

        self.app.add_control.side_effect = add_control
        self.app.button.side_effect = button
        self.app.save.side_effect = lambda key, value, scope="profile": self.app.settings.__setitem__(key, value)
        self.app._tools_session_id = None
        self.app._token_ranking_window = None
        self.frames = patch.object(editors.tk, "Frame", side_effect=fake_widget)
        self.frames.start()
        self.addCleanup(self.frames.stop)

    def test_manual_cycles_and_selected_hotbar_refresh(self):
        self.app.settings["planters_mode"] = 1
        editors.build_planters(self.app, Mock())
        keys = [key for key in self.controls if re.match(r"cycle[1-5]_[1-3]_", key)]
        self.assertEqual(len(keys), 60)
        self.controls["cycle5_3_planter"].onchange("red clay")
        self.assertIn("planter_hotbar_red_clay_slot", self.controls)
        self.assertEqual(self.app.settings["cycle5_3_planter"], "red clay")
        self.app.action.assert_not_called()

    def test_auto_gather_is_separate_and_harvest_flags_exclude_each_other(self):
        self.app.settings["planters_mode"] = 2
        self.app.action.return_value = {"gather": True}
        editors.build_planters(self.app, Mock())
        self.assertEqual(len([key for key in self.controls if re.match(r"auto_planter_.+_field_", key)]), 14 * 17)
        gather = self.controls["auto_planters_gather"]
        self.assertTrue(gather.get())
        self.assertEqual(gather.spec["scope"], "local")
        self.app.action.reset_mock()
        gather.onchange(False)
        self.app.action.assert_called_once_with("setAutoPlanterGather", False)
        self.assertNotIn("auto_planters_gather", self.app.settings)
        self.controls["auto_planters_collect_auto"].onchange(True)
        self.assertFalse(self.app.settings["auto_planters_collect_full"])
        self.assertTrue(self.app.settings["auto_planters_collect_auto"])
        self.controls["auto_planters_collect_full"].onchange(True)
        self.assertFalse(self.controls["auto_planters_collect_auto"].get())
        self.assertFalse(self.app.settings["auto_planters_collect_auto"])

    def test_tools_do_not_start_during_build_and_pass_exact_arguments(self):
        self.app.action.return_value = {"running": False, "state": "idle"}
        editors._build_autoclicker(self.app, Mock())
        self.app.action.assert_called_once_with("getAutoClickerStatus")
        self.controls["autoclicker_interval_ms"].set("1")
        self.controls["autoclicker_start_delay_seconds"].set("99")
        self.buttons["Start"]()
        self.assertIn(unittest.mock.call("startAutoClickerTool", 10, 10), self.app.action.call_args_list)
        self.app.action.reset_mock()
        editors._build_auto_gifted(self.app, Mock())
        self.app.action.assert_called_once_with("getAutoGiftedBasicBeeStatus")
        self.controls["auto-gifted-basic-bee-delay"].set(0)
        self.buttons["Start"]()
        self.assertIn(unittest.mock.call("startAutoGiftedBasicBeeTool", 1, {
            "pause_on_gifted_basic": True, "pause_on_gifted_other": True,
            "pause_on_legendary": False, "pause_on_mythic": True,
            "pause_on_basic": False, "pause_on_other": False}), self.app.action.call_args_list)
        self.app.save.assert_not_called()

    def test_token_cancel_and_save_use_source_manager_api(self):
        self.app.manager.loadFuzzyAITokenRanking.return_value = {
            "preferred_tokens": "Token Link,Focus", "ignored_tokens": "Focus"}
        with patch.object(editors, "_dialog", side_effect=fake_widget), patch.object(editors, "_tree", side_effect=fake_widget):
            window = editors.open_token_ranking(self.app, "pine tree", "Light")
            self.buttons["Cancel"]()
            window.destroy.assert_called_once_with()
            self.app.manager.saveFuzzyAITokenRanking.assert_not_called()
            editors.open_token_ranking(self.app, "pine tree", "Light")
            self.buttons["Save"]()
        self.app.manager.loadFuzzyAITokenRanking.assert_called_with("pine tree", "light")
        args = self.app.manager.saveFuzzyAITokenRanking.call_args[0]
        self.assertEqual((args[0], args[2]), ("pine tree", "light"))
        self.assertTrue(args[1]["preferred_tokens"].startswith("Token Link,"))
        self.assertEqual(args[1]["ignored_tokens"], "Focus")
        self.app.save.assert_not_called()

    def test_editor_dialog_is_modal(self):
        self.app.root.winfo_rootx.return_value = 50
        self.app.root.winfo_rooty.return_value = 80
        self.app.root.winfo_width.return_value = 1280
        self.app.root.winfo_height.return_value = 800
        window = fake_widget()
        with patch.object(editors.tk, "Toplevel", return_value=window):
            self.assertIs(editors._dialog(self.app, "Ranking"), window)
        window.transient.assert_called_once_with(self.app.root)
        window.wait_visibility.assert_called_once_with()
        window.grab_set.assert_called_once_with()
        window.focus_set.assert_called_once_with()

    def test_one_token_editor_per_app_keeps_opening_field_and_model(self):
        self.app.manager.loadFuzzyAITokenRanking.return_value = {
            "preferred_tokens": "Token Link,Focus", "ignored_tokens": "Focus"}
        with patch.object(editors, "_dialog", side_effect=fake_widget) as dialog, patch.object(editors, "_tree", side_effect=fake_widget):
            window = editors.open_token_ranking(self.app, "pine tree", "Light")
            self.app.field_name = "rose"
            self.app.settings["ai_gather_model"] = "Mini"
            second = editors.open_token_ranking(self.app, "rose", "Mini")
            sprout = editors.open_token_ranking(self.app, "rose", "token_mini", sprouts=True)
            self.assertIs(second, window)
            self.assertIs(sprout, window)
            dialog.assert_called_once()
            self.app.manager.loadFuzzyAITokenRanking.assert_called_once_with("pine tree", "light")
            window.lift.assert_called()
            window.focus_set.assert_called()
            self.buttons["Save"]()
            args = self.app.manager.saveFuzzyAITokenRanking.call_args[0]
            self.assertEqual((args[0], args[2]), ("pine tree", "light"))
            self.assertIsNone(self.app._token_ranking_window)
            editors.open_token_ranking(self.app, "rose", "Mini")
            self.assertEqual(dialog.call_count, 2)

    def test_destroyed_token_editor_can_be_reopened(self):
        self.app.manager.loadFuzzyAITokenRanking.return_value = {}
        with patch.object(editors, "_dialog", side_effect=fake_widget), patch.object(editors, "_tree", side_effect=fake_widget):
            window = editors.open_token_ranking(self.app, "pine tree")
            destroyed = next(call[0][1] for call in window.bind.call_args_list if call[0][0] == "<Destroy>")
            destroyed(SimpleNamespace(widget=Mock()))
            self.assertIs(self.app._token_ranking_window, window)
            destroyed(SimpleNamespace(widget=window))
            self.assertIsNone(self.app._token_ranking_window)
            second = editors.open_token_ranking(self.app, "rose")
            self.assertIsNot(second, window)

    def test_sprout_preset_keeps_opening_field_and_model(self):
        with patch.object(editors, "_dialog", side_effect=fake_widget), patch.object(editors, "_tree", side_effect=fake_widget):
            editors.open_token_ranking(self.app, "pine tree", "token_light", sprouts=True)
            self.app.settings["sprouts_field"] = "rose"
            self.app.settings["sprouts_ai_model"] = "token_mini"
            self.buttons["Field Drops"]()
            self.buttons["Save"]()
        expected = token_data.sprout_preset("field", "pine tree", "light")
        state = token_data.token_state(expected, "light", True)
        expected = token_data.token_ranking(state, "light", True)
        self.assertEqual(self.app.settings["sprouts_preferred_tokens"], expected["preferred_tokens"])
        self.assertEqual(self.app.settings["sprouts_ignored_tokens"], expected["ignored_tokens"])

    def test_failed_token_save_keeps_working_copy_and_dialog_open(self):
        self.app.manager.loadFuzzyAITokenRanking.return_value = {}
        self.app.manager.saveFuzzyAITokenRanking.side_effect = ValueError("Invalid ranking")
        with patch.object(editors, "_dialog", side_effect=fake_widget) as dialog, patch.object(editors, "_tree", side_effect=fake_widget):
            window = editors.open_token_ranking(self.app, "pine tree")
            self.buttons["Save"]()
            window.destroy.assert_not_called()
            self.assertIs(self.app._token_ranking_window, window)
            self.assertIn("Could not save", self.app.status.call_args[0][0])
            self.assertIs(editors.open_token_ranking(self.app, "rose"), window)
            dialog.assert_called_once()
            close = next(call[0][1] for call in window.protocol.call_args_list
                         if call[0][0] == "WM_DELETE_WINDOW")
            close()
            self.assertIsNone(self.app._token_ranking_window)

    def test_hotbar_slots_match_source_controls_without_character_limit(self):
        self.app.action.return_value = {"running": False, "state": "idle"}
        self.app.subtabs.side_effect = lambda parent, tabs, key: [builder(parent) for _, _, builder in tabs]
        editors._build_hotbar_buff(self.app, Mock())
        self.assertEqual(len([key for key in self.controls if key.startswith("hotbar_buff_tool_slot")]), 21)
        for slot in range(1, 8):
            control = self.controls["hotbar_buff_tool_slot{}_use_every_value".format(slot)]
            self.assertEqual(control.spec["numeric"], "float")
            self.assertNotIn("limit", control.spec)
            units = self.controls["hotbar_buff_tool_slot{}_use_every_format".format(slot)]
            self.assertEqual([choice["value"] for choice in units.spec["choices"]], ["secs", "mins"])
        self.app.action.assert_called_once_with("getHotbarBuffStatus")

    def test_tools_session_syncs_once_per_app(self):
        editors.build_tools(self.app, Mock())
        session = self.app._tools_session_id
        editors.build_tools(self.app, Mock())
        self.app.action.assert_called_once_with("syncToolSession", session)
        self.assertEqual(len(self.app.subtabs.call_args[0][1]), 5)

    def test_unchanged_hotbar_selection_preserves_controls(self):
        self.app.settings.update(planters_mode=1, cycle1_1_planter="red clay", cycle2_1_planter="red clay")
        editors.build_planters(self.app, Mock())
        control = self.controls["planter_hotbar_red_clay_slot"]
        self.controls["cycle2_1_planter"].onchange("none")
        self.assertIs(self.controls["planter_hotbar_red_clay_slot"], control)
        self.controls["cycle2_1_planter"].onchange("petal")
        self.assertIn("planter_hotbar_petal_slot", self.controls)

    def test_tool_poll_preserves_buttons_and_cancels_on_destroy(self):
        body = fake_widget()
        start_button, stop_button = fake_widget(), fake_widget()
        self.app.button.side_effect = [start_button, stop_button]
        status = dict(running=False, message="Ready")
        self.app.action.side_effect = lambda name: dict(status)
        label = self.app.label.return_value
        editors._tool_status(self.app, body, "getAutoClickerStatus", Mock(), Mock(),
                             [lambda data: data["message"]])
        poll = body.after.call_args[0][1]
        for widget in (start_button, stop_button, label):
            widget.reset_mock()
        poll()
        start_button.pack.assert_not_called()
        stop_button.pack_forget.assert_not_called()
        label.configure.assert_not_called()
        status.update(running=True, message="Running")
        poll()
        start_button.pack_forget.assert_called_once_with()
        stop_button.pack.assert_called_once()
        label.configure.assert_called_once_with(text="Running")
        destroyed = body.bind.call_args[0][1]
        destroyed(SimpleNamespace(widget=Mock()))
        body.after_cancel.assert_not_called()
        destroyed(SimpleNamespace(widget=body))
        body.after_cancel.assert_called_once()

    def test_sprout_save_uses_profile_settings_and_keeps_hidden_tokens_ignored(self):
        with patch.object(editors, "_dialog", side_effect=fake_widget), patch.object(editors, "_tree", side_effect=fake_widget):
            editors.open_token_ranking(self.app, "pine tree", sprouts=True)
            self.buttons["Clear"]()
            self.app.save.assert_not_called()
            self.buttons["Save"]()
        self.assertEqual(self.app.settings["sprouts_preferred_tokens"], "")
        self.assertIn("Bloom", self.app.settings["sprouts_ignored_tokens"].split(","))
        self.app.manager.loadFuzzyAITokenRanking.assert_not_called()
        self.app.manager.saveFuzzyAITokenRanking.assert_not_called()


if __name__ == "__main__":
    unittest.main()
