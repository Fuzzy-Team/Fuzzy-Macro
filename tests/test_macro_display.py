"""Test macro display coordinate translation without creating a real display."""

import ast
import importlib.util
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
MAIN_DISPLAY = 1
VIRTUAL_DISPLAY = 7
DISPLAY_RECTS = {
    MAIN_DISPLAY: (0, 0, 1440, 900),
    VIRTUAL_DISPLAY: (1440, -90, 1920, 1080),
}


def rect(x, y, w, h):
    return SimpleNamespace(origin=SimpleNamespace(x=x, y=y), size=SimpleNamespace(width=w, height=h))


class FakeQuartz:
    def __init__(self):
        self.active = [MAIN_DISPLAY, VIRTUAL_DISPLAY]

    def CGGetActiveDisplayList(self, maxDisplays, displays, count):
        return 0, tuple(self.active), len(self.active)

    def CGMainDisplayID(self):
        return MAIN_DISPLAY

    def CGDisplayBounds(self, displayID):
        return rect(*DISPLAY_RECTS[displayID])


def load_macro_display(quartz):
    spec = importlib.util.spec_from_file_location("macroDisplay", ROOT / "src/modules/screen/macroDisplay.py")
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"Quartz": quartz}):
        spec.loader.exec_module(module)
    return module


class MacroDisplayTests(unittest.TestCase):
    def setUp(self):
        self.quartz = FakeQuartz()
        self.macroDisplay = load_macro_display(self.quartz)
        self.tmp = tempfile.TemporaryDirectory()
        self.macroDisplay._screenPath = str(Path(self.tmp.name) / "screen.txt")

    def tearDown(self):
        self.tmp.cleanup()

    def write_display_id(self, displayID):
        Path(self.macroDisplay._screenPath).write_text(f"display_type=built-in\ndisplay_id={displayID}\n")
        self.macroDisplay.refresh()

    def test_main_display_coordinates_are_global(self):
        self.write_display_id(0)
        self.assertEqual(self.macroDisplay.bounds(), (0, 0, 1440, 900))
        self.assertEqual(self.macroDisplay.toGlobal(10, 20), (10, 20))

    def test_virtual_display_coordinates_are_offset(self):
        self.write_display_id(VIRTUAL_DISPLAY)
        self.assertEqual(self.macroDisplay.size(), (1920, 1080))
        self.assertEqual(self.macroDisplay.toGlobal(10, 20), (1450, -70))
        self.assertEqual(self.macroDisplay.toLocal(1450, -70), (10, 20))

    def test_missing_virtual_display_falls_back_to_main(self):
        self.write_display_id(VIRTUAL_DISPLAY)
        self.quartz.active = [MAIN_DISPLAY]
        self.assertEqual(self.macroDisplay.origin(), (0, 0))
        self.assertEqual(self.macroDisplay.displayID(), MAIN_DISPLAY)

    def test_missing_screen_file_uses_main_display(self):
        self.macroDisplay.refresh()
        self.assertEqual(self.macroDisplay.bounds(), (0, 0, 1440, 900))



class DisplayLifecycleTests(unittest.TestCase):
    def setUp(self):
        source = ast.parse((ROOT / "src/main.py").read_text())
        main = next(n for n in source.body if isinstance(n, ast.If) and
                    ast.unparse(n.test) == "__name__ == '__main__'")
        functions = [n for n in main.body if isinstance(n, ast.FunctionDef) and
                     n.name in {"syncVirtualDisplay", "startVirtualDisplayWatcher", "checkMainDisplayColorProfile"}]
        self.ns = dict(virtualDisplay=Mock(), screenInfo={"display_id": 7},
                       screenData=Mock(), macroDisplay=Mock(), logger=Mock(),
                       run=SimpleNamespace(value=2), Thread=Mock(),
                       virtualDisplayWatcher=None, time=Mock())
        exec(compile(ast.Module(body=functions, type_ignores=[]), "src/main.py", "exec"), self.ns)

    def test_display_loss_stops_running_and_paused_macro(self):
        for state in (2, 6):
            with self.subTest(state=state):
                self.ns["virtualDisplayWatcher"] = None
                self.ns["run"].value = state
                self.ns["virtualDisplay"].isRunning.return_value = False
                self.ns["startVirtualDisplayWatcher"]()
                self.ns["Thread"].call_args.kwargs["target"]()
                self.assertEqual(self.ns["run"].value, 0)
        self.ns["logger"].webhook.assert_called()

    def test_intentional_disable_does_not_stop_macro(self):
        self.ns["screenInfo"] = {"display_id": 0}
        self.ns["virtualDisplay"].isRunning.return_value = False
        self.ns["startVirtualDisplayWatcher"]()
        self.ns["Thread"].call_args.kwargs["target"]()
        self.assertEqual(self.ns["run"].value, 2)
        self.ns["logger"].webhook.assert_not_called()

    def test_failed_creation_checks_main_display_color(self):
        check = self.ns["checkMainDisplayColorProfile"] = Mock()
        self.ns["virtualDisplay"].sync.return_value = 0
        self.ns["syncVirtualDisplay"]({"use_virtual_display": True})
        check.assert_called_once_with()

    def test_successful_creation_skips_main_display_color(self):
        check = self.ns["checkMainDisplayColorProfile"] = Mock()
        self.ns["virtualDisplay"].sync.return_value = 7
        self.ns["syncVirtualDisplay"]({"use_virtual_display": True})
        check.assert_not_called()


if __name__ == "__main__":
    unittest.main()
