"""Opt-in native rendering check, using a temporary profile and no automation.

Run on macOS with FUZZY_NATIVE_GUI_TEST=1. This opens one normal window and
captures only that process's window. The usual headless suite skips it.
"""

import ast
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from modules.gui.app import NativeApp
from modules.gui.widgets import register_fonts
from test_gui_configuration import load_manager


@unittest.skipUnless(os.environ.get('FUZZY_NATIVE_GUI_TEST') == '1' and sys.platform == 'darwin',
                     'Requires an explicitly enabled macOS native window test')
class NativeRenderingTests(unittest.TestCase):
    def test_home_remains_drawn_after_switching_tabs(self):
        import Quartz
        import tkinter as tk

        with tempfile.TemporaryDirectory(prefix='fuzzy-native-gui-test-') as directory:
            manager = load_manager(directory)
            shutil.copytree(str(ROOT / 'settings/patterns'), str(Path(directory) / 'settings/patterns'))
            version = Path(directory) / 'src/webapp'
            version.mkdir(parents=True)
            shutil.copy2(str(ROOT / 'src/webapp/version.txt'), str(version / 'version.txt'))
            source = ast.parse((ROOT / 'src/gui.py').read_text())
            functions = {'getPatterns', 'getMacroVersion', 'getRunState', 'getRecentLogs', 'usesLegacyDiscordBot'}
            nodes = [node for node in source.body if isinstance(node, ast.FunctionDef) and node.name in functions]
            nodes += [node for node in source.body if isinstance(node, ast.Assign) and
                      any(isinstance(target, ast.Name) and target.id in ('_run_state', '_recent_logs') for target in node.targets)]
            namespace = dict(ast=ast, os=os, sys=sys, settingsManager=manager)
            exec(compile(ast.Module(body=nodes, type_ignores=[]), '<isolated-gui-actions>', 'exec'), namespace)
            register_fonts()
            window = tk.Tk()
            app = NativeApp(window, SimpleNamespace(**namespace), manager)
            window.title('Fuzzy Native GUI test')
            window.geometry('1280x800+50+80')
            errors = []
            window.report_callback_exception = lambda kind, error, traceback: errors.append(error)

            def settle():
                deadline = time.monotonic() + .35
                while time.monotonic() < deadline:
                    window.update()
                    time.sleep(.01)

            def card_pixel(name, x=280, y=75):
                windows = Quartz.CGWindowListCopyWindowInfo(Quartz.kCGWindowListOptionOnScreenOnly, Quartz.kCGNullWindowID)
                owned = next(info for info in windows if info.get(Quartz.kCGWindowOwnerPID) == os.getpid()
                             and info.get(Quartz.kCGWindowName) == 'Fuzzy Native GUI test')
                path = Path(directory) / (name + '.png')
                subprocess.run(['screencapture', '-x', '-o', '-l' + str(owned[Quartz.kCGWindowNumber]), str(path)], check=True, timeout=10)
                with Image.open(str(path)) as image:
                    # Interior of the first Home card, away from text and borders.
                    return image.getpixel((x * image.width // 1280, y * image.width // 1280))[:3]

            def heading_is_drawn():
                windows = Quartz.CGWindowListCopyWindowInfo(Quartz.kCGWindowListOptionOnScreenOnly, Quartz.kCGNullWindowID)
                owned = next(info for info in windows if info.get(Quartz.kCGWindowOwnerPID) == os.getpid()
                             and info.get(Quartz.kCGWindowName) == 'Fuzzy Native GUI test')
                path = Path(directory) / 'heading.png'
                subprocess.run(['screencapture', '-x', '-o', '-l' + str(owned[Quartz.kCGWindowNumber]), str(path)], check=True, timeout=10)
                heading = app.tasks_body.master.heading
                bounds = owned[Quartz.kCGWindowBounds]
                with Image.open(str(path)) as image:
                    scale = image.width / bounds['Width']
                    left = round((heading.winfo_rootx() - bounds['X']) * scale)
                    top = round((heading.winfo_rooty() - bounds['Y']) * scale)
                    return sum(all(channel >= 150 for channel in image.getpixel((x, y))[:3])
                               for x in range(left, left + round(heading.winfo_width() * scale))
                               for y in range(top, top + round(heading.winfo_height() * scale))) > 10

            try:
                settle()
                self.assertEqual(card_pixel('initial'), (30, 30, 30))
                self.assertTrue(heading_is_drawn())
                app.show_tab('collect')

                def descendants(widget):
                    for child in widget.winfo_children():
                        yield child
                        yield from descendants(child)

                sprouts = next(widget for widget in descendants(app.pages['collect'])
                               if getattr(widget, 'text', None) == 'Sprouts')
                sprouts.command()
                app.refresh()
                self.assertIn('configure-sprout-ai-tokens-button', app.controls)
                app.show_tab('config')
                discord = next(widget for widget in descendants(app.pages['config'])
                               if getattr(widget, 'text', None) == 'Discord Config')
                discord.command()
                app.refresh()
                self.assertIs(app.controls['discord_rich_presence'].get(), False)
                app.show_tab('home')
                for _ in range(2):
                    app.show_tab('gather')
                    settle()
                    app.show_tab('home')
                    settle()
                    self.assertEqual(card_pixel('returned'), (30, 30, 30))
                    self.assertTrue(heading_is_drawn())
                window.geometry('800x640')
                settle()
                window.geometry('1280x800')
                settle()
                self.assertEqual(card_pixel('resized'), (30, 30, 30))
                self.assertTrue(heading_is_drawn())
                self.assertEqual(card_pixel('sidebar', 40, 640), (30, 30, 30))
                self.assertEqual(errors, [])
            finally:
                app.close()


if __name__ == '__main__':
    unittest.main()
