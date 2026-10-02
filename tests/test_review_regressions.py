"""Regression coverage for findings from the Windows branch merge review."""
import ast
import hashlib
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock
import zipfile

from test_windows_compatibility import ROOT, load_module


def load_function(path, name, namespace):
    """Execute a real function in isolation from display and game dependencies."""
    tree = ast.parse((ROOT / path).read_text(encoding='utf-8'))
    function = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == name)
    code = ast.Module(body=[function], type_ignores=[])
    exec(compile(code, str(ROOT / path), 'exec'), namespace)
    return namespace[name]


class UpdateOwnershipTests(unittest.TestCase):
    def setUp(self):
        box = types.ModuleType('modules.misc.messageBox')
        box.msgBox = mock.Mock()
        with mock.patch.dict(sys.modules, {'modules.misc.messageBox': box}):
            self.module = load_module('review_updater', 'src/modules/misc/update.py')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.installed, self.incoming = (Path(self.temp.name) / name for name in ('installed', 'incoming'))
        for directory in (self.installed, self.incoming):
            (directory / 'src/modules/misc').mkdir(parents=True)
            (directory / 'src/main.py').write_text('# main\n', encoding='utf-8')
            (directory / 'src/modules/misc/update.py').write_text('# updater\n', encoding='utf-8')
        self.stale = self.installed / 'src/old.py'
        self.stale.write_text('# old shipped file\n', encoding='utf-8')
        self.custom = self.installed / 'settings/custom.py'
        self.custom.parent.mkdir()
        self.custom.write_text('# user script\n', encoding='utf-8')

    def apply(self):
        with mock.patch.object(self.module, '_load_ignore_rules', return_value=([], [])), mock.patch('sys.stdout', new=io.StringIO()):
            self.module._apply_update_files(str(self.incoming), str(self.installed), ['src/data/user'], ['.git'])

    def test_first_update_keeps_unrecorded_files_in_every_folder(self):
        self.apply()
        self.assertTrue(self.stale.exists())
        self.assertTrue(self.custom.exists())

    def test_recorded_unchanged_file_is_removed_but_custom_file_survives(self):
        self.module._write_installed_files_manifest(str(self.installed), {
            'src/old.py': self.module._git_blob_sha(str(self.stale)),
        })
        self.apply()
        self.assertFalse(self.stale.exists())
        self.assertTrue(self.custom.exists())

    def test_edited_shipped_file_survives(self):
        self.module._write_installed_files_manifest(str(self.installed), {
            'src/old.py': self.module._git_blob_sha(str(self.stale)),
        })
        self.stale.write_text('# edited by user\n', encoding='utf-8')
        self.apply()
        self.assertEqual(self.stale.read_text(), '# edited by user\n')

    def test_empty_manifest_is_distinct_from_missing_or_invalid_manifest(self):
        self.assertIsNone(self.module._read_installed_files_manifest(str(self.installed)))
        self.module._write_installed_files_manifest(str(self.installed), {})
        self.assertEqual(self.module._read_installed_files_manifest(str(self.installed)), {})
        metadata = self.installed / self.module.INSTALLED_FILES_MANIFEST
        metadata.write_text('not json', encoding='utf-8')
        with mock.patch('sys.stdout', new=io.StringIO()):
            self.assertIsNone(self.module._read_installed_files_manifest(str(self.installed)))
        self.apply()
        self.assertTrue(self.stale.exists())


class ModelSafetyTests(unittest.TestCase):
    def setUp(self):
        self.module = load_module('review_models', 'src/modules/misc/modelManager.py')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.module.MODEL_DIR = str(self.root)

    def metadata(self, path, data):
        digest = hashlib.sha1(f'blob {len(data)}\0'.encode() + data).hexdigest()
        return [{'path': path, 'sha': digest, 'download_url': 'https://example.invalid/model'}]

    def archive(self, path, data):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as archive:
            archive.writestr('models-main/' + path, data)
        return types.SimpleNamespace(content=buf.getvalue(), raise_for_status=lambda: None)

    def test_pt_file_protects_the_entire_model_package(self):
        package = self.root / 'custom.mlmodelc'
        package.mkdir()
        (package / 'weights.bin').write_bytes(b'needed by custom model')
        (package / 'training.pt').write_bytes(b'protected')
        with mock.patch('sys.stdout', new=io.StringIO()):
            self.assertFalse(self.module._delete_path(str(package)))
        self.assertEqual((package / 'weights.bin').read_bytes(), b'needed by custom model')

    def test_nested_symlink_protects_the_entire_model_package(self):
        package = self.root / 'custom.mlmodelc'
        (package / 'nested').mkdir(parents=True)
        (package / 'weights.bin').write_bytes(b'keep')
        try:
            (package / 'nested/link').symlink_to(self.root / 'target')
        except OSError:
            self.skipTest('symlink creation is unavailable')
        with mock.patch('sys.stdout', new=io.StringIO()):
            self.assertFalse(self.module._delete_path(str(package)))
        self.assertTrue((package / 'weights.bin').exists())
        self.assertTrue((package / 'nested/link').is_symlink())

    def test_unprotected_package_can_still_be_deleted(self):
        package = self.root / 'obsolete.mlmodelc'
        package.mkdir()
        (package / 'weights.bin').write_bytes(b'obsolete')
        self.assertTrue(self.module._delete_path(str(package)))
        self.assertFalse(package.exists())

    def test_cleanup_keeps_custom_models_and_removes_only_unused_managed_models(self):
        custom = self.root / 'custom.mlmodelc'
        custom.mkdir()
        (custom / 'weights.bin').write_bytes(b'user model')
        custom_file = self.root / 'custom.onnx'
        custom_file.write_bytes(b'user model')
        unused = self.root / 'token_detection_standard.mlmodelc'
        unused.mkdir()
        (unused / 'weights.bin').write_bytes(b'managed model')
        active = self.root / 'token_detection_standard.onnx'
        active.write_bytes(b'active model')
        with mock.patch.object(self.module, '_supported_model_names', return_value=(active.name,)), mock.patch('sys.stdout', new=io.StringIO()):
            self.assertEqual(self.module.cleanup_unused_models(), [unused.name])
        self.assertEqual((custom / 'weights.bin').read_bytes(), b'user model')
        self.assertEqual(custom_file.read_bytes(), b'user model')
        self.assertTrue(active.exists())
        self.assertFalse(unused.exists())

    def test_corrupt_zip_never_replaces_existing_single_file_or_package(self):
        for name, relative_path in [('token_detection_standard.onnx', 'token_detection_standard.onnx'),
                                    ('token_detection_standard.mlmodelc', 'token_detection_standard.mlmodelc/weights.bin')]:
            with self.subTest(name=name):
                destination = self.root / name
                existing = self.root / relative_path
                existing.parent.mkdir(parents=True, exist_ok=True)
                existing.write_bytes(b'original')
                response = self.archive(relative_path, b'corrupt')
                with mock.patch.object(self.module.requests, 'get', return_value=response):
                    with self.assertRaises(self.module.ModelIntegrityError):
                        self.module._copy_from_repo_zip(name, str(destination), self.metadata(relative_path, b'expected'))
                self.assertEqual(existing.read_bytes(), b'original')

    def test_valid_zip_is_verified_and_installed(self):
        name = 'token_detection_standard.onnx'
        with mock.patch.object(self.module.requests, 'get', return_value=self.archive(name, b'verified')):
            self.module._copy_from_repo_zip(name, str(self.root / name), self.metadata(name, b'verified'))
        self.assertEqual((self.root / name).read_bytes(), b'verified')

    def test_integrity_failures_never_trigger_zip_fallback(self):
        name = 'token_detection_standard.onnx'
        for entry_point in ('ensure_supported_models', 'ensure_missing_supported_models', 'ensure_missing_models'):
            with self.subTest(entry_point=entry_point), mock.patch.object(
                self.module, '_supported_model_names', return_value=(name,)
            ), mock.patch.object(self.module, '_remote_tree', return_value=self.metadata(name, b'valid')), mock.patch.object(
                self.module, '_download_remote_tree', side_effect=self.module.ModelIntegrityError('bad hash')
            ), mock.patch.object(self.module, '_copy_from_repo_zip') as fallback, mock.patch('sys.stdout', new=io.StringIO()):
                if entry_point == 'ensure_missing_models':
                    self.assertIn(name, self.module.ensure_missing_models([name])['failures'])
                else:
                    with self.assertRaises(self.module.ModelIntegrityError):
                        getattr(self.module, entry_point)()
                fallback.assert_not_called()


class StumpSnailTests(unittest.TestCase):
    def setUp(self):
        self.mouse = mock.Mock()
        self.clock = mock.Mock()
        self.clock.time.side_effect = [0, 60]
        self.stump = load_function('src/modules/macro.py', 'stumpSnail', {'mouse': self.mouse, 'time': self.clock})
        self.macro = mock.Mock()
        self.macro.setdat = {'stump_snail_balloon_interval': 1}
        self.macro.checkPauseAndWait.return_value = False
        self.macro.keepOldCheck.return_value = None

    def test_cannon_failure_stops_before_field_path_and_reward_checks(self):
        self.macro.cannon.return_value = False
        self.stump(self.macro)
        self.macro.goToField.assert_not_called()
        self.macro.placeSprinkler.assert_not_called()
        self.macro.keepOldCheck.assert_not_called()

    def test_failed_landing_stops_after_three_attempts(self):
        self.macro.cannon.return_value = True
        self.macro.placeSprinkler.return_value = False
        self.stump(self.macro)
        self.assertEqual(self.macro.cannon.call_count, 3)
        self.macro.keepOldCheck.assert_not_called()

    def test_side_task_uses_configured_gather_and_stops_when_return_travel_fails(self):
        self.macro.cannon.side_effect = [True, False]
        self.macro.placeSprinkler.return_value = True
        self.stump(self.macro)
        field, override = self.macro.gather.call_args[0]
        self.assertEqual(field, 'pine tree')
        self.assertEqual(override['shape'], 'skillet')
        self.assertEqual(override['mins'], 2)
        self.assertFalse(override['skip_travel'])
        self.assertFalse(override['infinite_gather'])
        self.assertEqual(self.macro.keepOldCheck.call_count, 1)
        self.macro.set_task_status.assert_called_with(None, update_presence=False)


@unittest.skipIf(sys.platform == 'win32', 'macOS installer tests require POSIX shells')
class MacVersionTests(unittest.TestCase):
    def test_short_versions_and_patch_releases_compare_numerically(self):
        for script in ('install_dependencies.command', 'run_macro.command'):
            source = (ROOT / script).read_text()
            start = source.index('version_at_least() {')
            function = source[start:source.index('\n}', start) + 2]
            for actual, required, expected in [('13.0', '13.0.0', 0), ('10.15', '10.15.0', 0),
                                                ('10.15.7', '10.15.0', 0), ('11.0', '12.0', 1),
                                                ('13.0.1', '13.0.2', 1)]:
                with self.subTest(script=script, actual=actual, required=required):
                    result = subprocess.run(['sh', '-c', function + '\nversion_at_least "$1" "$2"', 'test', actual, required])
                    self.assertEqual(result.returncode, expected)

    def test_install_helper_propagates_pip_failure_even_with_constraint_cleanup(self):
        source = (ROOT / 'install_dependencies.command').read_text()
        start = source.index('install_pip_package() {')
        function = source[start:source.index('\n}', start) + 2]
        code = 'pip() { return 23; }\nchip=i386\nconstraints="numpy<2"\n' + function + '\ninstall_pip_package test'
        result = subprocess.run(['bash', '-c', code])
        self.assertEqual(result.returncode, 23)


class AIFallbackTests(unittest.TestCase):
    def test_each_distributed_pattern_ignores_unusable_coreml_and_requests_onnx(self):
        for pattern, name in [('fuzzy_ai_gather', 'token_detection_standard'), ('blooms_ai', 'bloom_detection_standard')]:
            for directory in ('settings/patterns', 'settings/defaults/patterns'):
                for onnx_exists in (True, False):
                    with self.subTest(pattern=pattern, directory=directory, onnx_exists=onnx_exists), tempfile.TemporaryDirectory() as tmp:
                        model_dir = Path(tmp)
                        (model_dir / (name + '.mlmodelc')).mkdir()
                        if onnx_exists:
                            (model_dir / (name + '.onnx')).touch()
                        agc = mock.Mock()
                        agc.coreml_available.return_value = False
                        agc.coerce_text.side_effect = lambda value, default: default if value is None else str(value)
                        agc.resolve_sprinkler_model.return_value = (None, 'opencv_onnx')

                        class SelectionComplete(Exception):
                            pass

                        agc.build_capture.side_effect = SelectionComplete

                        def download(tag, filenames):
                            self.assertNotIn(name + '.mlmodelc', filenames)
                            (model_dir / (name + '.onnx')).touch()
                            return {}

                        agc.check_missing_models.side_effect = download
                        namespace = {'agc': agc, 'MODEL_DIR': model_dir, 'self': mock.Mock(),
                                     'CAPTURE_BACKEND': 'mss', 'INPUT_WIDTH': 992, 'INPUT_HEIGHT': 480,
                                     'LABELS_TOKENS': {}, 'TOKEN_MODEL_OPTIONS': {'standard': ('Standard', None, {}, 992, 480)},
                                     'BLOOM_MODEL_SELECTION': 'standard',
                                     'BLOOM_MODEL_VARIANTS': {'standard': ('Standard', name + '.mlmodelc', name + '.onnx', 736, 'output')}}
                        initialise = load_function(directory + '/' + pattern + '.py', '_initialise_runtime', namespace)
                        with self.assertRaises(SelectionComplete):
                            initialise()
                        agc.require_coreml_or_raise.assert_not_called()
                        self.assertEqual(agc.check_missing_models.call_count, 0 if onnx_exists else 1)


class LegacyIntentsTests(unittest.TestCase):
    def setUp(self):
        self.discord = mock.Mock()
        self.discord.Intents.default.side_effect = lambda: types.SimpleNamespace(value=0)
        self.requests = mock.Mock()
        self.intents = load_function('src/modules/discord_bot/legacyCommands.py', 'gateway_intents', {
            'discord': self.discord, 'requests': self.requests,
        })

    def test_content_intent_requested_only_with_authorized_application_flag(self):
        for flags in (0, 1 << 18, 1 << 19):
            with self.subTest(flags=flags), mock.patch('sys.stdout', new=io.StringIO()):
                self.requests.get.return_value.json.return_value = {'flags': flags}
                intents = self.intents('test-token')
                self.assertEqual(intents.value, (1 << 15) if flags else 0)
                self.assertFalse(intents.value & ((1 << 1) | (1 << 8)))

    def test_failed_authorization_check_keeps_nonprivileged_mention_commands(self):
        import requests
        self.requests.RequestException = requests.RequestException
        self.requests.get.side_effect = requests.RequestException('unavailable')
        with mock.patch('sys.stdout', new=io.StringIO()):
            self.assertEqual(self.intents('test-token').value, 0)


if __name__ == '__main__':
    unittest.main()
