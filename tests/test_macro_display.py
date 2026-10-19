"""Test macro display coordinate translation without creating a real display."""

import importlib.util
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


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


if __name__ == "__main__":
    unittest.main()
