"""Exercise the real shell launcher with isolated, fake Python executables."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

LAUNCHER = Path(__file__).resolve().parents[1] / 'run_macro.command'


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='launcher tests ')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.project = self.root / 'project with spaces'
        self.matcher = self.project / 'src/modules/bitmap_matcher'
        self.matcher.mkdir(parents=True)
        shutil.copy2(LAUNCHER, self.project / LAUNCHER.name)
        self.home = self.root / 'user home'
        self.home.mkdir()
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.log = self.root / 'calls'
        self.env = dict(os.environ, HOME=str(self.home), PATH=f'{self.bin}:/usr/bin:/bin', CALL_LOG=str(self.log))
        self.env.pop('SSL_CERT_FILE', None)
        self.write_executable(self.bin / 'pkill', 'echo KILLED >> "$CALL_LOG"\n')
        self.write_executable(self.bin / 'arch', 'echo arm64\n')
        self.write_executable(self.bin / 'sw_vers', 'echo 14.0\n')

    def write_executable(self, path, body):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('#!/bin/sh\n' + body)
        path.chmod(0o755)

    def python(self, version, status=0, path=None, architecture='arm64'):
        path = path or self.bin / f'python{version}'
        self.write_executable(path, f'''if [ "$1" = -c ]; then
    case "$2" in
        *certifi*) echo "${{FAKE_CERT:-}}" ;;
        *) echo '{version} {architecture}' ;;
    esac
    exit 0
fi
if [ "$1" = --version ]; then echo 'Python {version}'; exit 0; fi
printf '%s|%s|%s|%s\\n' '{version}' "$PWD" "$1" "${{SSL_CERT_FILE:-}}" >> "$CALL_LOG"
exit {status}
''')
        return path

    def binary(self, version, architecture='arm64'):
        (self.matcher / f'bitmap_matcher_py{version.replace(".", "")}_{architecture}.so').touch()

    def run_launcher(self):
        return subprocess.run(['/bin/sh', str(self.project / LAUNCHER.name)], env=self.env, text=True, capture_output=True)

    def calls(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def test_launches_only_newest_supported_python(self):
        for version in ('3.12', '3.11'):
            self.python(version)
            self.binary(version)
        result = self.run_launcher()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.calls()), 1, self.calls())
        self.assertTrue(self.calls()[0].startswith('3.12|'))

    def test_preserves_failure_without_retrying_other_python(self):
        self.python('3.12', 23)
        self.python('3.11')
        self.binary('3.12')
        self.binary('3.11')
        self.assertEqual(self.run_launcher().returncode, 23)
        self.assertEqual(len(self.calls()), 1)

    def test_skips_python_without_matching_architecture_binary(self):
        self.python('3.12', architecture='x86_64')
        self.binary('3.12')
        self.python('3.11')
        self.binary('3.11')
        self.assertEqual(self.run_launcher().returncode, 0)
        self.assertTrue(self.calls()[0].startswith('3.11|'))

    def test_prefers_virtual_environment_and_handles_spaces(self):
        self.python('3.11', path=self.home / 'fuzzy-macro-env/bin/python')
        self.binary('3.11')
        self.python('3.12')
        self.binary('3.12')
        self.assertEqual(self.run_launcher().returncode, 0)
        self.assertEqual(self.calls(), [f'3.11|{self.project}/src|main.py|'])

    def test_broken_virtual_environment_stops_with_repair_message(self):
        (self.home / 'fuzzy-macro-env').mkdir()
        self.python('3.12')
        self.binary('3.12')
        result = self.run_launcher()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('install_dependencies.command', result.stderr)
        self.assertEqual(self.calls(), [])

    def test_missing_interpreters_stops_with_install_message(self):
        result = self.run_launcher()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('install_dependencies.command', result.stderr)
        self.assertEqual(self.calls(), [])

    def test_certificate_comes_from_selected_interpreter(self):
        self.python('3.11', path=self.home / 'fuzzy-macro-env/bin/python')
        self.binary('3.11')
        cert = self.root / 'selected cert.pem'
        cert.touch()
        self.env['FAKE_CERT'] = str(cert)
        self.assertEqual(self.run_launcher().returncode, 0)
        self.assertTrue(self.calls()[0].endswith(f'|{cert}'))

    def test_legacy_version_only_matcher_is_supported(self):
        self.python('3.9')
        (self.matcher / 'bitmap_matcher_py39.so').touch()
        self.assertEqual(self.run_launcher().returncode, 0)
        self.assertTrue(self.calls()[0].startswith('3.9|'))

    def test_wrong_version_executable_is_skipped(self):
        self.python('3.13', path=self.bin / 'python3.12')
        self.python('3.11')
        self.binary('3.11')
        self.assertEqual(self.run_launcher().returncode, 0)
        self.assertTrue(self.calls()[0].startswith('3.11|'))

    def test_incompatible_virtual_environment_does_not_fall_back(self):
        self.python('3.13', path=self.home / 'fuzzy-macro-env/bin/python')
        self.python('3.12')
        self.binary('3.12')
        result = self.run_launcher()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('install_dependencies.command', result.stderr)
        self.assertEqual(self.calls(), [])

    def test_broken_virtual_environment_symlink_stops(self):
        (self.home / 'fuzzy-macro-env').symlink_to(self.root / 'missing')
        self.python('3.12')
        self.binary('3.12')
        self.assertNotEqual(self.run_launcher().returncode, 0)
        self.assertEqual(self.calls(), [])

    def test_does_not_kill_other_python_processes(self):
        self.python('3.12')
        self.binary('3.12')
        self.run_launcher()
        self.assertNotIn('KILLED', self.calls())


if __name__ == '__main__':
    unittest.main()
