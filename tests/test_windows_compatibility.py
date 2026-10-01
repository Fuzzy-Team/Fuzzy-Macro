"""Windows regressions runnable without a game, display, or Windows DLLs.

Run with python -m unittest discover -s tests -v.
"""
import builtins
import ctypes
from ctypes import wintypes
import importlib.util
import io
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def load_module(name, relative_path):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class NativeMatcherTests(unittest.TestCase):
    def setUp(self):
        # Exercise selection without trying to load Windows code on this host.
        with mock.patch('platform.system', return_value='Windows'), mock.patch(
            'platform.machine', return_value='AMD64'
        ), mock.patch('sys.stdout', new=io.StringIO()):
            self.module = load_module('windows_matcher', 'src/modules/bitmap_matcher/__init__.py')
        self.addCleanup(self.module._cleanup_extracted_dirs)

    def make_wheel(self, directory, python_tag, arch):
        path = directory / f'bitmap_matcher-0.0.0-{python_tag}-{python_tag}-{arch}.whl'
        with zipfile.ZipFile(path, 'w') as wheel:
            wheel.writestr(f'bitmap_matcher.{python_tag}-{arch}.pyd', b'native-test')
        return path

    def test_standalone_loader_skips_other_python_and_architectures(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch('platform.system', return_value='Windows'), mock.patch(
            'platform.machine', return_value='AMD64'
        ):
            directory = Path(tmp)
            self.make_wheel(directory, 'cp37', 'win_amd64')
            self.make_wheel(directory, self.module._get_cp_tag(), 'win32')
            self.make_wheel(directory, self.module._get_cp_tag(), 'win_amd64')
            selected = self.module.BitmapMatcherLoader([directory]).find_extension()
            self.assertEqual(selected.name, f'bitmap_matcher.{self.module._get_cp_tag()}-win_amd64.pyd')

    def test_standalone_loader_rejects_only_incompatible_wheels(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch('platform.system', return_value='Windows'), mock.patch(
            'platform.machine', return_value='AMD64'
        ):
            self.make_wheel(Path(tmp), 'cp37', 'win32')
            self.assertIsNone(self.module.BitmapMatcherLoader([Path(tmp)]).find_extension())

    def test_unpacked_selector_does_not_pick_a_win32_binary_for_x64(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch('platform.system', return_value='Windows'), mock.patch(
            'platform.machine', return_value='AMD64'
        ), mock.patch.object(self.module, '__file__', str(Path(tmp) / '__init__.py')):
            (Path(tmp) / f'bitmap_matcher.{self.module._get_cp_tag()}-win32.pyd').touch()
            self.assertIsNone(self.module.find_compatible_so())


class WindowsOCRTests(unittest.TestCase):
    def test_windows_ocr_avoids_apple_imports_and_falls_back_from_cuda(self):
        screenshot = types.ModuleType('modules.screen.screenshot')
        screenshot.mssScreenshot = mock.Mock()
        screen = types.ModuleType('modules.screen.screenData')
        screen.getScreenData = lambda: {'screen_width': 1920, 'screen_height': 1080}
        screen.scaleRegion = screen.scaleX = screen.scaleY = mock.Mock()
        pag = types.ModuleType('pyautogui')
        pag.size = lambda: (1920, 1080)
        easy = types.ModuleType('easyocr')
        easy.Reader = mock.Mock(side_effect=[RuntimeError('CUDA unavailable'), mock.Mock()])
        torch = types.ModuleType('torch')
        torch.cuda = types.SimpleNamespace(is_available=lambda: True)
        torch.backends = types.SimpleNamespace()
        modules = {'modules.screen.screenshot': screenshot, 'modules.screen.screenData': screen,
                   'pyautogui': pag, 'easyocr': easy, 'torch': torch, 'paddleocr': None}
        original_import = builtins.__import__

        def import_without_apple(name, *args, **kwargs):
            if name in ('mss.darwin', 'ocrmac'):
                self.fail('Windows tried to import ' + name)
            return original_import(name, *args, **kwargs)

        with mock.patch.dict(sys.modules, modules), mock.patch('platform.system', return_value='Windows'), mock.patch(
            'platform.mac_ver', return_value=('', ('', '', ''), '')
        ), mock.patch('builtins.__import__', side_effect=import_without_apple), mock.patch('sys.stdout', new=io.StringIO()):
            module = load_module('windows_ocr', 'src/modules/screen/ocr.py')
        self.assertEqual(module.ocrLib, 'easyocr')
        self.assertEqual(easy.Reader.call_args_list, [mock.call(['en'], gpu=True), mock.call(['en'], gpu=False)])


class UpdaterTests(unittest.TestCase):
    def setUp(self):
        box = types.ModuleType('modules.misc.messageBox')
        box.msgBox = mock.Mock()
        with mock.patch.dict(sys.modules, {'modules.misc.messageBox': box}):
            self.module = load_module('windows_updater', 'src/modules/misc/update.py')
        self.module._IS_WINDOWS = True

    def test_windows_update_check_uses_branch_and_module_root(self):
        with mock.patch.object(self.module, '_installation_root', return_value=str(ROOT)) as root, mock.patch.object(
            self.module, '_read_local_version', return_value='1.3.3'
        ), mock.patch.object(self.module.requests, 'get') as get:
            get.return_value.text = '1.3.4\n'
            result = self.module.check_for_updates_silent()
            self.assertTrue(result['available'])
            root.assert_called_once_with()
            self.assertIn('/refs/heads/windows/', get.call_args.args[0])

    def test_gitignore_rules_come_from_windows_branch(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(self.module.requests, 'get') as get:
            (Path(tmp) / '.gitignore').write_text('fuzzy-macro-env/\n', encoding='utf-8')
            get.return_value.text = 'fuzzy-macro-env/\n'
            rules = self.module._read_ignore_rules(tmp)
            self.assertIn('/refs/heads/windows/.gitignore', get.call_args.args[0])
            self.assertTrue(self.module._is_gitignored('fuzzy-macro-env/Scripts/python.exe', rules[0]))

    def test_updating_files_preserves_venv_and_user_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            installed, incoming = Path(tmp) / 'installed', Path(tmp) / 'incoming'
            for directory in (installed, incoming):
                (directory / 'src/modules/misc').mkdir(parents=True)
                (directory / 'src/main.py').write_text('# main\n', encoding='utf-8')
                (directory / 'src/modules/misc/update.py').write_text('# updater\n', encoding='utf-8')
            (installed / 'fuzzy-macro-env/Scripts').mkdir(parents=True)
            python = installed / 'fuzzy-macro-env/Scripts/python.exe'
            python.write_bytes(b'keep interpreter')
            (installed / 'paths').mkdir()
            custom = installed / 'paths/custom.py'
            custom.write_text('# user path\n', encoding='utf-8')
            obsolete = installed / 'src/obsolete.py'
            obsolete.write_text('# obsolete\n', encoding='utf-8')
            (incoming / 'src/main.py').write_text('# updated main\n', encoding='utf-8')
            rules = (['fuzzy-macro-env/'], ['fuzzy-macro-env/'])
            with mock.patch.object(self.module, '_load_ignore_rules', return_value=rules), mock.patch('sys.stdout', new=io.StringIO()):
                self.module._apply_update_files(str(incoming), str(installed), [], ['.git'])
            self.assertEqual(python.read_bytes(), b'keep interpreter')
            self.assertTrue(custom.exists())
            self.assertFalse(obsolete.exists())
            self.assertEqual((installed / 'src/main.py').read_text(), '# updated main\n')

    def test_backup_excludes_project_venv(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'fuzzy-macro-env/Scripts').mkdir(parents=True)
            (root / 'fuzzy-macro-env/Scripts/python.exe').write_bytes(b'large runtime')
            (root / 'main.py').write_text('# backed up\n', encoding='utf-8')
            archive = root / 'backup_macro.zip'
            self.module._create_backup(tmp, str(archive), [], ['.git'])
            with zipfile.ZipFile(archive) as backup:
                self.assertEqual(backup.namelist(), ['main.py'])


class WindowsAppTests(unittest.TestCase):
    def setUp(self):
        self.api = types.SimpleNamespace(**{name: mock.Mock() for name in (
            'EnumWindows', 'IsWindowVisible', 'GetWindowTextLengthW', 'GetWindowTextW',
            'GetForegroundWindow', 'ShowWindow', 'SetForegroundWindow', 'GetWindowRect',
        )})
        pag = types.ModuleType('pyautogui')
        pag.size = lambda: (1920, 1080)
        with mock.patch.dict(sys.modules, {'pyautogui': pag}), mock.patch('platform.system', return_value='Windows'), mock.patch.object(
            ctypes, 'windll', types.SimpleNamespace(user32=self.api), create=True
        ), mock.patch.object(ctypes, 'WINFUNCTYPE', ctypes.CFUNCTYPE, create=True):
            self.module = load_module('windows_apps', 'src/modules/misc/appManager.py')

    def test_handles_have_pointer_sized_signatures(self):
        self.assertIs(self.api.GetForegroundWindow.restype, wintypes.HWND)
        self.assertEqual(self.api.GetWindowRect.argtypes[0], wintypes.HWND)
        self.assertEqual(self.api.SetForegroundWindow.argtypes, [wintypes.HWND])

    def test_deeplink_preserves_query_characters(self):
        link = 'roblox://placeId=1537690962&linkCode=private&launchData=a%20b'
        with mock.patch.object(os, 'startfile', create=True) as start, mock.patch.object(subprocess, 'Popen') as popen:
            self.module.openDeeplink(link)
            start.assert_called_once_with(link)
            popen.assert_not_called()

    def test_window_bounds_survive_a_64_bit_handle(self):
        handle = 0x100000123
        self.api.IsWindowVisible.return_value = True
        self.api.GetWindowTextLengthW.return_value = 6
        self.api.GetWindowTextW.side_effect = lambda hwnd, buf, length: setattr(buf, 'value', 'Roblox')

        def window_rect(hwnd, pointer):
            self.assertEqual(hwnd, handle)
            rect = ctypes.cast(pointer, ctypes.POINTER(wintypes.RECT)).contents
            rect.left, rect.top, rect.right, rect.bottom = 0, 0, 1920, 1080
            return True

        self.api.GetWindowRect.side_effect = window_rect
        self.api.EnumWindows.side_effect = lambda callback, param: callback(handle, param)
        with mock.patch.object(ctypes, 'windll', types.SimpleNamespace(user32=self.api), create=True):
            self.assertEqual(self.module.getWindowSize('Roblox'), (0, 0, 1920, 1080))


@unittest.skipUnless(platform.system() == 'Windows', 'requires Windows cmd.exe')
class WindowsInstallerTests(unittest.TestCase):
    def test_installer_handles_special_path_and_stops_on_pip_failure(self):
        # A real venv runs the batch file; sitecustomize intercepts pip before
        # any network access or package mutation. No macro/server is launched.
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "Fuzzy's Macro ! (test)"
            project.mkdir()
            for name in ('install_dependencies.bat', 'requirements-windows.txt'):
                shutil.copy2(ROOT / name, project / name)
            subprocess.run([sys.executable, '-m', 'venv', '--without-pip', str(project / 'fuzzy-macro-env')], check=True)
            hook = Path(tmp) / 'hook'
            hook.mkdir()
            (hook / 'sitecustomize.py').write_text(
                'import os, sys\n'
                'if sys.argv[0] == "-m":\n'
                '    os._exit(int(os.environ["FUZZY_TEST_PIP_EXIT"]))\n'
                'if sys.argv[0] == "-c":\n'
                '    os._exit(0)\n', encoding='utf-8'
            )
            env = dict(os.environ, PYTHONPATH=str(hook), FUZZY_TEST_PIP_EXIT='1')
            result = subprocess.run(['cmd', '/d', '/c', str(project / 'install_dependencies.bat'), '--no-launch'],
                                    input='\n', text=True, capture_output=True, env=env, timeout=60)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Dependency installation failed', result.stdout)
            self.assertNotIn('Installation complete', result.stdout)
            env['FUZZY_TEST_PIP_EXIT'] = '0'
            result = subprocess.run(['cmd', '/d', '/c', str(project / 'install_dependencies.bat'), '--no-launch'],
                                    input='\n', text=True, capture_output=True, env=env, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('Installation complete', result.stdout)


if __name__ == '__main__':
    unittest.main()
