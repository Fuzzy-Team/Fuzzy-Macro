"""Check native form coverage against the web specification without launching a GUI."""

import ast
import base64
import html
import json
from pathlib import Path
import re
import runpy
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
DEFINITIONS_PATH = ROOT / "src/modules/gui/definitions.py"
sys.path.insert(0, str(ROOT / "src"))
from modules.gui import definitions
DATA = vars(definitions)
TABS = DATA["TAB_DEFINITIONS"]
CUSTOM = DATA["CUSTOM_DEFINITIONS"]


def controls_in(value):
    if isinstance(value, dict):
        if "kind" in value:
            yield value
        for child in value.values():
            yield from controls_in(child)
    elif isinstance(value, list):
        for child in value:
            yield from controls_in(child)


CONTROLS = {c["id"]: c for c in controls_in(TABS)}
CONTROLS.update({c["id"]: c for c in controls_in(CUSTOM)})


def text_content(text):
    # HTML drops the spaces around a line break.
    text = re.sub(r"\s*<br\s*/?>\s*", "\n", text, flags=re.I)
    return html.unescape(re.sub(r"<[^>]*>", "", text))


def source_html(tab):
    return (ROOT / "src/webapp/htmlImports/tabs" / (tab + ".html")).read_text(encoding="utf-8")


class DefinitionTests(unittest.TestCase):
    def test_python_37_grammar_and_no_web_source_dependency(self):
        source = DEFINITIONS_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source, feature_version=7) if sys.version_info >= (3, 8) else ast.parse(source)
        self.assertFalse(any(isinstance(node, (ast.FunctionDef, ast.ClassDef)) for node in ast.walk(tree)))
        self.assertEqual([node.module for node in tree.body if isinstance(node, ast.ImportFrom)], ["token_data"])

    def test_schema_and_action_names(self):
        self.assertEqual(set(TABS), {"gather", "collect", "kill", "boost", "quests", "config"})
        allowed = {"id", "title", "desc", "kind", "scope", "choices", "numeric", "limit",
                   "max_selections", "bind", "action", "choices_key"}
        kinds = {"checkbox", "dropdown", "textbox", "multicheck", "keybind", "button",
                 "textbox_with_button", "draglist", "custom"}
        for c in controls_in([TABS, CUSTOM]):
            with self.subTest(control=c["id"]):
                self.assertTrue({"id", "title", "desc", "kind", "scope"}.issubset(c))
                self.assertTrue(set(c).issubset(allowed))
                self.assertIn(c["kind"], kinds)
                self.assertIn(c["scope"], {"general", "profile", "field", "local"})
                if "action" in c:
                    self.assertRegex(c["action"], r"^[a-z][a-z_]*$")
                for choice in c.get("choices", []):
                    self.assertTrue({"label", "value"}.issubset(choice))
                    self.assertTrue(set(choice).issubset({"label", "value", "image"}))
                    self.assertNotRegex(choice["label"], r"<[^>]*>")

    def test_subtab_navigation_matches_source_order_and_labels(self):
        for tab in ("collect", "kill", "boost", "quests", "config"):
            entries = re.findall(r'<div id="([^"]+)" class="' + tab +
                                 r'-tab-item[^\"]*"[^>]*>([^<]*)</div>', source_html(tab))
            expected = [(ident, label.strip()) for ident, label in entries]
            actual = [(sub["id"], sub["title"]) for sub in TABS[tab]]
            self.assertEqual(actual, expected, tab)

    def test_all_literal_standard_controls_retain_source_labels(self):
        string = r'("(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\')'
        object_pattern = (r"\{\s*id:\s*" + string + r",\s*title:\s*" + string +
                          r",\s*desc:\s*" + string)
        for tab in TABS:
            source = re.sub(r"/\*.*?\*/", "", source_html(tab), flags=re.S)
            for raw_id, raw_title, raw_desc in re.findall(object_pattern, source):
                ident, title, desc = map(ast.literal_eval, (raw_id, raw_title, raw_desc))
                if ident == "beta_update_row":
                    ident = "beta_commit_hash"
                with self.subTest(tab=tab, control=ident):
                    self.assertIn(ident, CONTROLS)
                    self.assertEqual(CONTROLS[ident]["title"], text_content(title))
                    self.assertEqual(CONTROLS[ident]["desc"], text_content(desc))
        self.assertNotIn("whirligig_slot", CONTROLS)

    def test_all_memory_rewards_and_exact_asset_bytes(self):
        source = (ROOT / "src/webapp/scripts/memory-match-rewards.js").read_text(encoding="utf-8")
        rewards = json.loads(source.split("=", 1)[1].strip().rstrip(";"))
        native = CONTROLS["memory_match_rewards"]["choices"]
        self.assertEqual([(x["label"], x["value"]) for x in native],
                         [(x["label"], x["value"]) for x in rewards])
        self.assertEqual(len(native), 40)
        for original, choice in zip(rewards, native):
            with self.subTest(reward=choice["value"]):
                expected = base64.b64decode(original["image"].split(",", 1)[1])
                self.assertEqual((DEFINITIONS_PATH.parent / choice["image"]).read_bytes(), expected)
        self.assertEqual(DATA["MEMORY_MATCH_REWARD_TYPES"]["hard wax"], ["winter"])

    def test_all_local_images_exist(self):
        choices = [c for options in DATA["CHOICES"].values() for c in options]
        images = [c["image"] for c in choices if "image" in c]
        images += [v["image"] for v in DATA["SECTION_PRESENTATION"].values() if "image" in v]
        images += [v["image"] for v in CUSTOM.values() if "image" in v]
        for image in images:
            self.assertFalse(image.startswith(("data:", "http:", "https:", "/")))
            self.assertTrue((DEFINITIONS_PATH.parent / image).is_file(), image)

    def test_all_report_buff_choices_match_source(self):
        source = (ROOT / "src/webapp/scripts/report-buffs.js").read_text(encoding="utf-8")
        for setting, array in [("hourly_report_uptime_buffs", "hourlyReportUptimeBuffOptions"),
                               ("hourly_report_hourly_buffs", "hourlyReportSideBuffOptions")]:
            body = re.search(r"window\." + array + r" = \[(.*?)\];", source, re.S).group(1)
            expected = re.findall(r'label: "([^"]+)", value: "([^"]+)", image: `\$\{reportBuffAssetPath\}([^`]+)`', body)
            actual = [(c["label"], c["value"], Path(c["image"]).name)
                      for c in CONTROLS[setting]["choices"]]
            self.assertEqual(actual, expected)
        self.assertEqual(CONTROLS["hourly_report_hourly_buffs"]["max_selections"], 5)
        self.assertNotIn("max_selections", CONTROLS["hourly_report_uptime_buffs"])

    def test_theme_labels_and_stored_names_match_all_eleven_source_options(self):
        source = source_html("config").split('id: "gui_theme"', 1)[1].split('triggerFunction:', 1)[0]
        expected = [(label, value.lower()) for label, value in re.findall(
            r'\{ label: "([^"]+)", value: "([^"]+)" \}', source)]
        actual = [(c["label"], c["value"]) for c in CONTROLS["gui_theme"]["choices"]]
        self.assertEqual(actual, expected)
        self.assertEqual(len(actual), 11)

    def test_dropdown_value_types_and_field_spellings(self):
        self.assertTrue(all(isinstance(c["value"], str) for c in CONTROLS["width"]["choices"]))
        self.assertEqual([c["value"] for c in CONTROLS["hive_exclude_slot"]["choices"]], list(range(1, 7)))
        self.assertEqual(CONTROLS["hive_exclude_slot"]["kind"], "dropdown")
        self.assertEqual(CONTROLS["hive_exclude_slot"]["max_selections"], 0)
        for ident in ("field_booster_glitter_slot", "AFB_slotG", "tad_alt_glitter_slot"):
            self.assertEqual([c["value"] for c in CONTROLS[ident]["choices"]], list(range(8)))
            self.assertEqual(CONTROLS[ident]["action"], "sync_glitter_hotbar_slot")
        self.assertIn("blue flower", [c["value"] for c in CONTROLS["field"]["choices"]])
        self.assertIn("blue_flower", [c["value"] for c in CONTROLS["AFB_field"]["choices"]])
        self.assertEqual(CONTROLS["field_enable"]["scope"], "profile")
        self.assertEqual(CONTROLS["shape"]["scope"], "field")
        self.assertEqual(CONTROLS["shape"]["choices_key"], "patterns")
        self.assertEqual(CONTROLS["tad_alt_gather_shape"]["choices_key"], "default_patterns")
        self.assertEqual(CONTROLS["beta_commit_hash"]["scope"], "local")
        self.assertEqual(CONTROLS["beta_commit_hash"]["limit"], 7)

    def test_model_token_arrays_keep_source_case_and_order(self):
        source = (ROOT / "src/webapp/scripts/tabs/gather.js").read_text(encoding="utf-8")
        standard = ast.literal_eval(re.search(r"const fuzzyAITokenNames = (\[.*?\]);", source, re.S).group(1))
        models = re.search(r"const fuzzyAITokenNamesByModel = (.*?);", source, re.S).group(1)
        expected = {"Standard": standard}
        for model in ("Light", "Mini"):
            expected[model] = ast.literal_eval(re.search(model + r": (\[.*?\])", models, re.S).group(1))
        self.assertEqual({m: [c["value"] for c in cs] for m, cs in DATA["AI_TOKEN_CHOICES_BY_MODEL"].items()}, expected)
        self.assertIs(CUSTOM["fuzzy_ai_tokens"]["models"], DATA["AI_TOKEN_CHOICES_BY_MODEL"])
        self.assertIs(CUSTOM["sprout_ai_tokens"]["models"], DATA["AI_TOKEN_CHOICES_BY_MODEL"])

    def test_bespoke_rows_are_complete(self):
        for slot in range(1, 8):
            for suffix in ("use_when", "use_every_value", "use_every_format"):
                self.assertIn("hotbar{}_{}".format(slot, suffix), CONTROLS)
        for slot in range(1, 6):
            for prefix in ("item", "quantity", "quantity_max", "repeat", "repeat_inf"):
                self.assertIn("blender_{}_{}".format(prefix, slot), CONTROLS)
        self.assertEqual(len(CUSTOM["quest_overrides"]["rows"]), 6)
        for row in CUSTOM["quest_overrides"]["rows"]:
            self.assertEqual([c["id"] for c in row["controls"]],
                             [row["id"] + "_quest_gather_mins", row["id"] + "_quest_gather_return"])
        expected = re.findall(r'data-id="([^"]+)" draggable="true"><span class="drag-handle">[^<]*</span><span class="drag-text">([^<]+)</span>', source_html("config"))
        actual = [(c["value"], c["label"]) for c in CONTROLS["task_priority_order"]["choices"]]
        self.assertEqual(actual, expected)
        self.assertEqual(len(actual), 65)
        for action in ("hotbar", "quest_overrides", "task_priorities", "fallback_private_servers",
                       "model_downloads", "switch_profile", "create_profile", "duplicate_profile",
                       "export_profile", "import_profile", "petals_guide", "sprout_guide"):
            self.assertIn(action, CUSTOM)


if __name__ == "__main__":
    unittest.main()
