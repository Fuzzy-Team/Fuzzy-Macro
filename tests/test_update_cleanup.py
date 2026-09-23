import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from modules.misc import update


PROTECTED = [
    os.path.join("src", "data", "user"),
    os.path.join("src", "data", "models"),
    os.path.join("settings", "profiles"),
    os.path.join("settings", "patterns"),
]


class UpdateCleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.install = self.root / "install"
        self.extracted = self.root / "release"
        self.install.mkdir()
        self._make_complete_release()

    def tearDown(self):
        self.temp.cleanup()

    def _write(self, root, relative_path, content="content"):
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def _make_complete_release(self):
        self._write(self.extracted, "src/main.py", "main")
        self._write(self.extracted, "src/modules/misc/update.py", "update")
        for index in range(8):
            self._write(self.extracted, f"shipped/file_{index}.txt", str(index))

    def _write_manifest(self, values):
        path = self.install / update.INSTALLED_FILES_MANIFEST
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(values), encoding="utf-8")

    def _hash(self, path):
        return update._git_blob_sha(str(path))

    def test_unchanged_stale_file_is_deleted_and_edited_file_is_kept(self):
        unchanged = self._write(self.install, "old/unchanged.txt", "old")
        edited = self._write(self.install, "old/edited.txt", "user edit")
        self._write_manifest({
            "old/unchanged.txt": self._hash(unchanged),
            "old/edited.txt": update._git_blob_sha(
                str(self._write(self.root, "original.txt", "original"))
            ),
        })

        update._remove_obsolete_files(str(self.extracted), str(self.install), PROTECTED)

        self.assertFalse(unchanged.exists())
        self.assertTrue(edited.exists())

    def test_file_in_release_is_never_deleted(self):
        installed = self._write(self.install, "shared.txt", "old shipped version")
        self._write(self.extracted, "shared.txt", "new shipped version")
        self._write_manifest({"shared.txt": self._hash(installed)})

        update._remove_obsolete_files(str(self.extracted), str(self.install), PROTECTED)

        self.assertTrue(installed.exists())

    def test_protected_and_escaping_paths_are_never_touched(self):
        protected = self._write(self.install, "src/data/user/notes.txt", "notes")
        outside = self._write(self.root, "outside.txt", "outside")
        self._write_manifest({
            "src/data/user/notes.txt": self._hash(protected),
            "../outside.txt": self._hash(outside),
        })

        update._remove_obsolete_files(str(self.extracted), str(self.install), PROTECTED)

        self.assertTrue(protected.exists())
        self.assertTrue(outside.exists())

    def test_cleanup_does_not_follow_symlinked_directories(self):
        target = self._write(self.install, "real/old.txt", "old")
        try:
            (self.install / "linked").symlink_to(self.install / "real", target_is_directory=True)
        except OSError:
            self.skipTest("directory symlinks are unavailable")
        self._write_manifest({"linked/old.txt": self._hash(target)})

        update._remove_obsolete_files(str(self.extracted), str(self.install), PROTECTED)

        self.assertTrue(target.exists())

    def test_python_cleanup_removes_bytecode_and_empty_directories(self):
        source = self._write(self.install, "old/package/gone.py", "pass")
        pyc = self._write(
            self.install, "old/package/__pycache__/gone.cpython-312.pyc", "bytecode"
        )
        self._write_manifest({"old/package/gone.py": self._hash(source)})

        update._remove_obsolete_files(str(self.extracted), str(self.install), PROTECTED)

        self.assertFalse(source.exists())
        self.assertFalse(pyc.exists())
        self.assertFalse((self.install / "old").exists())

    def test_bootstrap_is_used_only_without_manifest(self):
        stale = self._write(self.install, "old.txt", "old")
        obsolete = {"old.txt": self._hash(stale)}
        with mock.patch.object(update, "_download_obsolete_files", return_value=obsolete) as download:
            update._remove_obsolete_files(str(self.extracted), str(self.install), PROTECTED)
        self.assertFalse(stale.exists())
        download.assert_called_once_with()

        stale = self._write(self.install, "old.txt", "old")
        self._write_manifest({"old.txt": self._hash(stale)})
        with mock.patch.object(update, "_download_obsolete_files") as download:
            update._remove_obsolete_files(str(self.extracted), str(self.install), PROTECTED)
        download.assert_not_called()
        self.assertFalse(stale.exists())

    def test_bootstrap_download_failure_skips_cleanup(self):
        stale = self._write(self.install, "old.txt", "old")
        with mock.patch.object(update, "_download_obsolete_files", side_effect=OSError("offline")):
            update._remove_obsolete_files(str(self.extracted), str(self.install), PROTECTED)
        self.assertTrue(stale.exists())

    def test_incomplete_release_skips_cleanup(self):
        (self.extracted / "src/main.py").unlink()
        stale = self._write(self.install, "old.txt", "old")
        self._write_manifest({"old.txt": self._hash(stale)})

        update._remove_obsolete_files(str(self.extracted), str(self.install), PROTECTED)

        self.assertTrue(stale.exists())

    def test_copy_failure_does_not_run_cleanup_or_write_manifest(self):
        with mock.patch.object(
            update, "_merge_overwrite", side_effect=OSError("copy failed")
        ), mock.patch.object(update, "_finish_file_update") as finish:
            with self.assertRaises(OSError):
                update._apply_update_files(
                    str(self.extracted), str(self.install), PROTECTED, [".git"]
                )

        finish.assert_not_called()
        self.assertFalse((self.install / update.INSTALLED_FILES_MANIFEST).exists())

    def test_cleanup_over_twenty_percent_is_refused(self):
        stale_files = [
            self._write(self.install, f"old_{index}.txt", str(index))
            for index in range(3)
        ]
        self._write_manifest({path.name: self._hash(path) for path in stale_files})

        update._remove_obsolete_files(str(self.extracted), str(self.install), PROTECTED)

        self.assertTrue(all(path.exists() for path in stale_files))

    def test_git_checkout_skips_cleanup(self):
        (self.install / ".git").mkdir()
        stale = self._write(self.install, "old.txt", "old")
        self._write_manifest({"old.txt": self._hash(stale)})

        update._remove_obsolete_files(str(self.extracted), str(self.install), PROTECTED)

        self.assertTrue(stale.exists())

    def test_manifest_is_atomic_and_excludes_protected_folders(self):
        shipped = self._write(self.extracted, "package/module.py", "pass")
        self._write(self.extracted, "src/data/user/default.txt", "protected")
        real_replace = os.replace
        with mock.patch.object(update.os, "replace", wraps=real_replace) as replace:
            update._write_installed_files_manifest(
                str(self.extracted), str(self.install), PROTECTED
            )

        manifest_path = self.install / update.INSTALLED_FILES_MANIFEST
        values = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(values["package/module.py"], self._hash(shipped))
        self.assertNotIn("src/data/user/default.txt", values)
        replace.assert_called_once_with(str(manifest_path) + ".tmp", str(manifest_path))
        self.assertFalse(Path(str(manifest_path) + ".tmp").exists())


if __name__ == "__main__":
    unittest.main()
