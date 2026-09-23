import json
import os
import sys
import tempfile
from pathlib import Path
from unittest import TestCase, main, mock


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
from modules.misc import update

PROTECTED = ["src/data/user", "src/data/models", "settings/profiles", "settings/patterns"]


class UpdateCleanupTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.install = self.root / "install"
        self.install.mkdir()
        self.extracted = self.install / "Fuzzy-Macro-release"
        self._write(self.extracted, "src/main.py", "main")
        self._write(self.extracted, "src/modules/misc/update.py", "updater")
        self._write(self.extracted, ".gitignore", "__pycache__/\n*.py[cod]\n")
        self.origin_gitignore = ""

    def _write(self, root, relative_path, content="content"):
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def _apply(self):
        response = mock.Mock(text=self.origin_gitignore)
        with mock.patch.object(update.requests, "get", return_value=response):
            update._apply_update_files(str(self.extracted), str(self.install), PROTECTED,
                                       [".git", "backup_macro.zip", ".backup_pending"])

    def test_hash_comparison_skips_same_and_replaces_changed(self):
        same = self._write(self.install, "same.txt", "same")
        changed = self._write(self.install, "changed.txt", "old")
        self._write(self.extracted, "same.txt", "same")
        self._write(self.extracted, "changed.txt", "new")
        original_copy = update.shutil.copy2
        copies = []

        def record_copy(source, destination):
            copies.append(Path(destination).name)
            return original_copy(source, destination)

        with mock.patch.object(update.shutil, "copy2", side_effect=record_copy):
            self._apply()
        self.assertEqual(same.read_text(), "same")
        self.assertEqual(changed.read_text(), "new")
        self.assertNotIn("same.txt", copies)
        self.assertIn("changed.txt", copies)

    def test_missing_files_are_deleted_even_if_edited_or_untracked(self):
        edited = self._write(self.install, "old/edited.py", "my edit")
        untracked = self._write(self.install, "old/extra.txt", "not shipped")
        self._apply()
        self.assertFalse(edited.exists())
        self.assertFalse(untracked.exists())
        self.assertFalse((self.install / "old").exists())

    def test_incoming_file_is_never_deleted(self):
        installed = self._write(self.install, "legacy.py", "old")
        self._write(self.extracted, "legacy.py", "new")
        self._apply()
        self.assertEqual(installed.read_text(), "new")

    def test_gitignored_files_and_directories_are_kept(self):
        self._write(self.extracted, ".gitignore", "*.log\nbuild/\n/anchored.txt\n")
        ignored = [self._write(self.install, "nested/run.log"),
                   self._write(self.install, "build/generated.txt"),
                   self._write(self.install, "anchored.txt")]
        stale = self._write(self.install, "nested/remove.txt")
        self._apply()
        self.assertTrue(all(path.exists() for path in ignored))
        self.assertFalse(stale.exists())

    def test_release_gitignore_controls_cleanup(self):
        self._write(self.install, ".gitignore", "old.txt\n")
        stale = self._write(self.install, "old.txt")
        self._apply()
        self.assertFalse(stale.exists())

    def test_origin_gitignore_keeps_files_missing_from_older_zip(self):
        self.origin_gitignore = "future-output/\n"
        kept = self._write(self.install, "future-output/generated.txt")
        self._apply()
        self.assertTrue(kept.exists())

    def test_origin_gitignore_download_failure_skips_cleanup(self):
        stale = self._write(self.install, "old.txt")
        with mock.patch.object(update, "_read_ignore_rules", side_effect=OSError("offline")):
            self._apply()
        self.assertTrue(stale.exists())

    def test_missing_release_gitignore_skips_cleanup(self):
        (self.extracted / ".gitignore").unlink()
        stale = self._write(self.install, "old.txt")
        self._apply()
        self.assertTrue(stale.exists())

    def test_protected_folders_and_backup_files_are_untouched(self):
        kept = [self._write(self.install, path) for path in (
            "src/data/user/notes.txt", "src/data/models/model.pt",
            "settings/profiles/custom.json", "settings/patterns/custom.py",
            "backup_macro.zip", ".backup_pending")]
        self._apply()
        self.assertTrue(all(path.exists() for path in kept))

    def test_symlinks_are_not_followed(self):
        outside = self._write(self.root, "outside.txt")
        try:
            (self.install / "linked.txt").symlink_to(outside)
            (self.install / "linked_dir").symlink_to(self.root, target_is_directory=True)
        except OSError:
            self.skipTest("symlinks are unavailable")
        self._apply()
        self.assertEqual(outside.read_text(), "content")
        self.assertTrue((self.install / "linked.txt").is_symlink())
        self.assertTrue((self.install / "linked_dir").is_symlink())

    def test_cleanup_rejects_escaping_paths(self):
        outside = self._write(self.root, "outside.txt")
        self.assertIsNone(update._safe_regular_file(str(self.install), "../outside.txt", PROTECTED))
        self.assertIsNone(update._safe_regular_file(str(self.install), str(outside), PROTECTED))
        self.assertEqual(outside.read_text(), "content")

    def test_copy_refuses_symlinked_destination_parent(self):
        outside = self.root / "outside"
        outside.mkdir()
        try:
            (self.install / "linked").symlink_to(outside, target_is_directory=True)
        except OSError:
            self.skipTest("symlinks are unavailable")
        self._write(self.extracted, "linked/file.txt")
        with self.assertRaises(OSError):
            self._apply()
        self.assertFalse((outside / "file.txt").exists())

    def test_compiled_files_follow_release_gitignore(self):
        source = self._write(self.install, "old/gone.py")
        compiled = self._write(self.install, "old/__pycache__/gone.cpython-312.pyc")
        self._apply()
        self.assertFalse(source.exists())
        self.assertTrue(compiled.exists())

    def test_incomplete_release_skips_deletion(self):
        (self.extracted / "src/main.py").unlink()
        stale = self._write(self.install, "old.txt")
        self._apply()
        self.assertTrue(stale.exists())

    def test_copy_failure_skips_deletion_and_manifest(self):
        stale = self._write(self.install, "old.txt")
        with mock.patch.object(update, "_merge_overwrite", side_effect=OSError("copy failed")):
            with self.assertRaises(OSError):
                self._apply()
        self.assertTrue(stale.exists())
        self.assertFalse((self.install / update.INSTALLED_FILES_MANIFEST).exists())

    def test_git_checkout_skips_deletion(self):
        (self.install / ".git").mkdir()
        stale = self._write(self.install, "old.txt")
        self._apply()
        self.assertTrue(stale.exists())

    def test_git_worktree_file_skips_deletion(self):
        self._write(self.install, ".git", "gitdir: /some/worktree")
        stale = self._write(self.install, "old.txt")
        self._apply()
        self.assertTrue(stale.exists())

    def test_many_stale_files_are_deleted(self):
        stale = [self._write(self.install, f"old_{i}.txt") for i in range(20)]
        self._apply()
        self.assertTrue(all(not path.exists() for path in stale))

    def test_manifest_is_atomic_and_excludes_protected_folders(self):
        shipped = self._write(self.extracted, "package/module.py", "pass")
        self._write(self.extracted, "src/data/user/default.txt")
        real_replace = os.replace
        with mock.patch.object(update.os, "replace", wraps=real_replace) as replace:
            self._apply()
        manifest_path = self.install / update.INSTALLED_FILES_MANIFEST
        manifest = json.loads(manifest_path.read_text())
        self.assertEqual(manifest["package/module.py"], update._git_blob_sha(shipped))
        self.assertNotIn("src/data/user/default.txt", manifest)
        replace.assert_called_once_with(str(manifest_path) + ".tmp", str(manifest_path))
        self.assertFalse(Path(str(manifest_path) + ".tmp").exists())

    def test_manifest_parent_symlink_cannot_write_outside_install(self):
        outside = self.root / "outside"
        outside.mkdir()
        (self.install / "src/data").mkdir(parents=True)
        try:
            (self.install / "src/data/user").symlink_to(outside, target_is_directory=True)
        except OSError:
            self.skipTest("symlinks are unavailable")
        self._apply()
        self.assertEqual(list(outside.iterdir()), [])

    def test_cleanup_error_does_not_fail_update(self):
        stale = self._write(self.install, "old.txt")
        with mock.patch.object(update.os, "remove", side_effect=OSError("busy")):
            self._apply()
        self.assertTrue(stale.exists())
        self.assertTrue((self.install / update.INSTALLED_FILES_MANIFEST).exists())


if __name__ == "__main__":
    main()
