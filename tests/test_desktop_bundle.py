"""Writable bundle data and source-update boundaries, without GUI or automation."""

import ast
import os
from pathlib import Path
import runpy
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
desktop = runpy.run_path(str(ROOT / 'src/desktop.py'))
prepare_data = desktop['prepare_data']


class BundleTests(unittest.TestCase):
    def test_trusted_accessibility_does_not_prompt_or_create_window(self):
        api = SimpleNamespace(AXIsProcessTrusted=Mock(return_value=True),
                              AXIsProcessTrustedWithOptions=Mock(), kAXTrustedCheckOptionPrompt='prompt')
        with patch.dict(sys.modules, ApplicationServices=api), patch('tkinter.Tk') as window:
            self.assertTrue(desktop['request_accessibility']())
        api.AXIsProcessTrustedWithOptions.assert_not_called()
        window.assert_not_called()

    def test_permission_window_waits_for_grant_and_quit_cancels_startup(self):
        import tkinter as tk
        from modules.gui import widgets
        for grant in (True, False):
            with self.subTest(grant=grant):
                api = SimpleNamespace(AXIsProcessTrusted=Mock(side_effect=[False, False, True]),
                                      AXIsProcessTrustedWithOptions=Mock(return_value=False),
                                      kAXTrustedCheckOptionPrompt='prompt')
                window, tasks, buttons = Mock(), [], {}
                window.after.side_effect = lambda delay, callback: tasks.append(callback)
                def button(parent, title, command, colors):
                    buttons[title] = command
                    return Mock()
                def run_loop():
                    if not grant:
                        buttons['Quit']()
                        return
                    for _ in range(2):
                        tasks.pop(0)()
                window.mainloop.side_effect = run_loop
                with patch.dict(sys.modules, ApplicationServices=api), \
                        patch.object(tk, 'Tk', return_value=window), \
                        patch.object(tk, 'Frame'), patch.object(tk, 'Label'), \
                        patch.object(widgets, 'Button', side_effect=button), \
                        patch.object(widgets, 'register_fonts'), patch('subprocess.run') as open_settings:
                    self.assertIs(desktop['request_accessibility'](), grant)
                    open_settings.assert_not_called()
                    buttons['Open Accessibility Settings']()
                    open_settings.assert_called_once_with(
                        ['open', 'x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility'], check=True)
                api.AXIsProcessTrustedWithOptions.assert_called_once_with({'prompt': True})
                window.destroy.assert_called_once_with()

    def test_denied_accessibility_stops_before_engine_import_and_data_setup(self):
        gate, prepare, engine = Mock(return_value=False), Mock(), Mock()
        with tempfile.TemporaryDirectory() as temporary, \
                patch.dict(desktop['main'].__globals__, request_accessibility=gate, prepare_data=prepare), \
                patch.object(sys, '_MEIPASS', temporary, create=True), \
                patch.object(sys, 'argv', ['Fuzzy Macro']), \
                patch.object(Path, 'home', return_value=Path(temporary)), \
                patch.object(runpy, 'run_module', engine), \
                patch.object(sys, 'stdout'), patch.object(sys, 'stderr'), patch.dict(os.environ):
            desktop['main']()
            engine.assert_not_called()
            prepare.assert_not_called()
            gate.assert_called_once_with()

    def test_install_refreshes_assets_and_preserves_profiles_and_patterns(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            resources, root = directory / 'resources', directory / 'runtime'
            for name in ('images', 'webapp', 'hourly_report', 'data/bss'):
                path = resources / name / 'asset.txt'
                path.parent.mkdir(parents=True)
                path.write_text('bundled asset')
            for name in ('paths', 'settings/patterns', 'settings/defaults'):
                path = resources / 'seed' / name / 'sample.py'
                path.parent.mkdir(parents=True)
                path.write_text('bundled pattern')
            profile = root / 'settings/profiles/custom/settings.txt'
            profile.parent.mkdir(parents=True)
            profile.write_text('existing profile')
            custom = root / 'settings/patterns/sample.py'
            custom.parent.mkdir(parents=True)
            custom.write_text('custom pattern')
            model_pattern = resources / 'seed/settings/patterns/fuzzy_ai_gather.py'
            model_pattern.write_text('bundled AI pattern')
            previous = os.getcwd()
            try:
                with patch.dict(os.environ):
                    prepare_data(root, resources)
                    self.assertEqual(Path.cwd().resolve(), (root / 'src').resolve())
                    self.assertEqual(os.environ['FUZZY_APP_DATA_DIR'], str(root))
                    self.assertEqual(custom.read_text(), 'custom pattern')
                    self.assertEqual(profile.read_text(), 'existing profile')
                    self.assertTrue((root / 'src/data/models').is_dir())
                    self.assertTrue((root / 'src/data/user').is_dir())
                    (resources / 'images/asset.txt').write_text('new asset')
                    model_pattern.write_text('new AI pattern')
                    (resources / 'seed/settings/defaults/sample.py').write_text('new default')
                    prepare_data(root, resources)
                    self.assertEqual((root / 'src/images/asset.txt').read_text(), 'new asset')
                    self.assertEqual(custom.read_text(), 'custom pattern')
                    self.assertEqual((root / 'settings/patterns/fuzzy_ai_gather.py').read_text(), 'new AI pattern')
                    self.assertEqual((root / 'settings/defaults/sample.py').read_text(), 'new default')
                    self.assertEqual((root / 'paths/sample.py').read_text(), 'bundled pattern')
            finally:
                os.chdir(previous)

    def test_pattern_import_uses_runtime_directory_instead_of_bundle(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / 'runtime/settings/patterns'
            source = ast.parse((ROOT / 'src/gui.py').read_text())
            function = next(node for node in source.body if isinstance(node, ast.FunctionDef) and node.name == 'importPatterns')
            namespace = dict(os=os, __file__=str(Path(temporary) / 'bundle/gui.py'),
                             settingsManager=SimpleNamespace(getPatternsDir=lambda: str(target)))
            exec(compile(ast.Module(body=[function], type_ignores=[]), '<pattern-import>', 'exec'), namespace)
            result = namespace['importPatterns']([dict(name='../custom.py', content='print("custom")')])
            self.assertEqual(result, dict(saved=['custom.py'], errors=[]))
            self.assertEqual((target / 'custom.py').read_text(), 'print("custom")')
            self.assertFalse((Path(temporary) / 'settings/patterns/custom.py').exists())

    def test_frozen_settings_root_uses_the_launcher_data_directory(self):
        source = ast.parse((ROOT / 'src/modules/misc/settingsManager.py').read_text())
        function = next(node for node in source.body if isinstance(node, ast.FunctionDef) and node.name == 'getProjectRoot')
        namespace = dict(os=os, sys=SimpleNamespace(frozen=True))
        exec(compile(ast.Module(body=[function], type_ignores=[]), '<settings-root>', 'exec'), namespace)
        with patch.dict(os.environ, FUZZY_APP_DATA_DIR='/private/tmp/fuzzy-isolated-app'):
            self.assertEqual(namespace['getProjectRoot'](), '/private/tmp/fuzzy-isolated-app')

    def test_frozen_updates_stop_before_network_or_file_changes(self):
        for filename, names in [('src/gui.py', ('update', 'updateFromHash', 'checkForUpdates')),
                                ('src/modules/misc/update.py', ('_installation_root',))]:
            source = ast.parse((ROOT / filename).read_text())
            functions = [node for node in source.body if isinstance(node, ast.FunctionDef) and node.name in names]
            namespace = dict(sys=SimpleNamespace(frozen=True))
            exec(compile(ast.Module(body=functions, type_ignores=[]), '<frozen-updates>', 'exec'), namespace)
            for name in names:
                with self.subTest(name=name), self.assertRaisesRegex((RuntimeError, OSError), 'Replace Fuzzy Macro.app'):
                    namespace[name](*(['abcdef0'] if name == 'updateFromHash' else []))


if __name__ == '__main__':
    unittest.main()
