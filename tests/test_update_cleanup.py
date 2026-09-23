import json
import os
import sys
import tempfile
from pathlib import Path
from unittest import TestCase, main, mock


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from modules.misc import update


PROTECTED = [
    os.path.join("src", "data", "user"),
    os.path.join("src", "data", "models"),
    os.path.join("settings", "profiles"),
    os.path.join("settings", "patterns"),
]


class UpdateCleanupTests(TestCase):
    def setUp(self):
        """Create isolated installation and release trees for each test."""
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.install = self.root / "install"
        self.extracted = self.root / "release"
        self.install.mkdir()
        self._make_complete_release()

    def tearDown(self):
        """Remove the temporary test trees."""
        self.temp.cleanup()

    def _write(self, root, relative_path, content="content"):
        """Write a UTF-8 fixture file below ``root`` and return its path."""
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def _make_complete_release(self):
        """Populate the extracted tree with the minimum valid release files."""
        self._write(self.extracted, "src/main.py", "main")
        self._write(self.extracted, "src/modules/misc/update.py", "update")
        for index in range(8):
            self._write(self.extracted, f"shipped/file_{index}.txt", str(index))

    def _write_manifest(self, values):
        """Write an installed-files manifest for the test installation."""
        path = self.install / update.INSTALLED_FILES_MANIFEST
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(values), encoding="utf-8")

    def _hash(self, path):
        """Return the Git blob hash for a fixture file."""
        return update._git_blob_sha(str(path))

    def test_unchanged_stale_file_is_deleted_and_edited_file_is_kept(self):
        """Delete unchanged stale files while retaining user-edited files."""
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
        """Keep an installed file when the incoming release still ships it."""
        installed = self._write(self.install, "shared.txt", "old shipped version")
        self._write(self.extracted, "shared.txt", "new shipped version")
        self._write_manifest({"shared.txt": self._hash(installed)})

        update._remove_obsolete_files(str(self.extracted), str(self.install), PROTECTED)

        self.assertTrue(installed.exists())

    def test_protected_and_escaping_paths_are_never_touched(self):
        """Ignore protected paths and paths that escape the installation root."""
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
        """Avoid deleting through a symlinked directory."""
        target = self._write(self.install, "real/old.txt", "old")
        try:
            (self.install / "linked").symlink_to(self.install / "real", target_is_directory=True)
        except OSError:
            self.skipTest("directory symlinks are unavailable")
        self._write_manifest({"linked/old.txt": self._hash(target)})

        update._remove_obsolete_files(str(self.extracted), str(self.install), PROTECTED)

        self.assertTrue(target.exists())

    def test_python_cleanup_removes_bytecode_and_empty_directories(self):
        """Remove stale Python bytecode and directories left empty by cleanup."""
        source = self._write(self.install, "old/package/gone.py", "pass")
        pyc = self._write(
            self.install, "old/package/__pycache__/gone.cpython-312.pyc", "bytecode"
        )
        self._write_manifest({"old/package/gone.py": self._hash(source)})

        update._remove_obsolete_files(str(self.extracted), str(self.install), PROTECTED)

        self.assertFalse(source.exists())
        self.assertFalse(pyc.exists())
        self.assertFalse((self.install / "old").exists())

    def test_python_cleanup_keeps_bytecode_shipped_by_release(self):
        """Retain bytecode that is present in the incoming release."""
        source = self._write(self.install, "old/gone.py", "pass")
        pyc = self._write(
            self.install, "old/__pycache__/gone.cpython-312.pyc", "bytecode"
        )
        self._write(
            self.extracted, "old/__pycache__/gone.cpython-312.pyc", "new bytecode"
        )
        self._write_manifest({"old/gone.py": self._hash(source)})

        update._remove_obsolete_files(str(self.extracted), str(self.install), PROTECTED)

        self.assertFalse(source.exists())
        self.assertTrue(pyc.exists())

    def test_bootstrap_is_used_only_without_manifest(self):
        """Fetch the installed release tree only when no manifest exists."""
        stale = self._write(self.install, "old.txt", "old")
        historical = {"old.txt": {self._hash(stale)}}
        with mock.patch.object(update, "_download_historical_hashes", return_value=historical) as download:
            update._remove_obsolete_files(
                str(self.extracted), str(self.install), PROTECTED, previous_ref="1.3.3"
            )
        self.assertFalse(stale.exists())
        download.assert_called_once_with("1.3.3")

        stale = self._write(self.install, "old.txt", "old")
        self._write_manifest({"old.txt": self._hash(stale)})
        with mock.patch.object(update, "_download_historical_hashes") as download:
            update._remove_obsolete_files(str(self.extracted), str(self.install), PROTECTED)
        download.assert_not_called()
        self.assertFalse(stale.exists())

    def test_bootstrap_download_failure_skips_cleanup(self):
        """Defer bootstrap cleanup after a download failure and retry later."""
        stale = self._write(self.install, "old.txt", "old")
        with mock.patch.object(update, "_download_historical_hashes", side_effect=OSError("offline")):
            update._finish_file_update(
                str(self.extracted), str(self.install), PROTECTED, previous_ref="1.3.3"
            )
        self.assertTrue(stale.exists())
        pending_path = self.install / update.PENDING_CLEANUP
        self.assertEqual(json.loads(pending_path.read_text())["bootstrap_ref"], "1.3.3")
        self.assertTrue((self.install / update.INSTALLED_FILES_MANIFEST).exists())

        with mock.patch.object(
            update, "_download_historical_hashes", return_value={"old.txt": {self._hash(stale)}}
        ) as download:
            update._finish_file_update(str(self.extracted), str(self.install), PROTECTED)
        download.assert_called_once_with("1.3.3")
        self.assertFalse(stale.exists())
        self.assertIsNone(json.loads(pending_path.read_text())["bootstrap_ref"])

    def test_repeated_bootstrap_failure_preserves_manifest_stale_files(self):
        shipped = self._write(self.extracted, "old.txt", "old")
        installed = self._write(self.install, "old.txt", "old")
        with mock.patch.object(update, "_download_historical_hashes", side_effect=OSError("offline")):
            update._finish_file_update(
                str(self.extracted), str(self.install), PROTECTED, previous_ref="1.3.3"
            )
        self.assertEqual(self._hash(installed), self._hash(shipped))

        shipped.unlink()
        with mock.patch.object(update, "_download_historical_hashes", side_effect=OSError("offline")):
            update._finish_file_update(str(self.extracted), str(self.install), PROTECTED)
        pending = json.loads((self.install / update.PENDING_CLEANUP).read_text())
        self.assertEqual(pending["files"]["old.txt"], self._hash(installed))

        with mock.patch.object(update, "_download_historical_hashes", return_value={}):
            update._finish_file_update(str(self.extracted), str(self.install), PROTECTED)
        self.assertFalse(installed.exists())

    def test_bootstrap_finds_files_from_older_release_tags(self):
        """Remove a historical leftover absent from the current installed tag."""
        stale = self._write(self.install, "very_old.txt", "old release")
        with mock.patch.object(
            update,
            "_download_historical_hashes",
            return_value={"very_old.txt": {self._hash(stale)}},
        ):
            update._remove_obsolete_files(
                str(self.extracted), str(self.install), PROTECTED, previous_ref="1.3.3"
            )
        self.assertFalse(stale.exists())

    def test_bootstrap_keeps_unrecognized_historical_file(self):
        """Keep a file that differs from every shipped historical hash."""
        stale = self._write(self.install, "very_old.txt", "user edit")
        with mock.patch.object(
            update,
            "_download_historical_hashes",
            return_value={"very_old.txt": {"a" * 40}},
        ):
            update._remove_obsolete_files(
                str(self.extracted), str(self.install), PROTECTED, previous_ref="1.3.3"
            )
        self.assertTrue(stale.exists())

    def test_installed_release_ref_prefers_commit_marker(self):
        """Use the installed commit when a commit update followed a release."""
        self._write(self.install, "src/webapp/version.txt", "1.3.3")
        self._write(self.install, "src/webapp/updated_commit.txt", "7dbde7d")
        self.assertEqual(update._installed_release_ref(str(self.install)), "7dbde7d")

    def test_copy_captures_previous_release_before_replacing_version(self):
        """Bootstrap against the old tag after the incoming files are copied."""
        self._write(self.install, "src/webapp/version.txt", "1.3.2")
        self._write(self.extracted, "src/webapp/version.txt", "1.3.3")
        with mock.patch.object(update, "_finish_file_update") as finish:
            update._apply_update_files(
                str(self.extracted), str(self.install), PROTECTED, [".git"]
            )

        self.assertEqual((self.install / "src/webapp/version.txt").read_text(), "1.3.3")
        self.assertEqual(finish.call_args.args[-1], "1.3.2")

    def test_release_tree_returns_only_blob_hashes(self):
        """Use the tree's file hashes without treating directories as files."""
        response = mock.Mock()
        response.json.return_value = {
            "truncated": False,
            "tree": [
                {"type": "tree", "path": "src", "sha": "directory"},
                {"type": "blob", "path": "src/main.py", "sha": "filehash"},
            ],
        }
        with mock.patch.object(update.requests, "get", return_value=response) as get:
            self.assertEqual(
                update._download_installed_manifest("1.3.3"),
                {"src/main.py": "filehash"},
            )
        self.assertIn("/git/trees/1.3.3?recursive=1", get.call_args.args[0])

    def test_release_tree_response_must_be_complete(self):
        """Reject truncated trees before using their missing paths for cleanup."""
        response = mock.Mock()
        response.json.return_value = {"truncated": True, "tree": []}
        with mock.patch.object(update.requests, "get", return_value=response):
            with self.assertRaises(ValueError):
                update._download_installed_manifest("1.3.3")

    def test_historical_hashes_include_installed_commit_and_release_tags(self):
        """Collect hashes from older tags as well as the installed revision."""
        tags = mock.Mock()
        tags.json.return_value = [
            {"commit": {"sha": "a" * 40}},
            {"commit": {"sha": "b" * 40}},
        ]
        trees = {
            "1.3.3": {"old.txt": "1" * 40},
            "a" * 40: {"old.txt": "2" * 40},
            "b" * 40: {"other.txt": "3" * 40},
        }
        with mock.patch.object(update.requests, "get", return_value=tags), mock.patch.object(
            update, "_download_installed_manifest", side_effect=trees.__getitem__
        ) as download:
            hashes = update._download_historical_hashes("1.3.3")

        self.assertEqual(hashes["old.txt"], {"1" * 40, "2" * 40})
        self.assertEqual(hashes["other.txt"], {"3" * 40})
        self.assertEqual(download.call_count, 3)

    def test_incomplete_release_skips_cleanup(self):
        """Skip stale-file cleanup when required release files are absent."""
        (self.extracted / "src/main.py").unlink()
        stale = self._write(self.install, "old.txt", "old")
        self._write_manifest({"old.txt": self._hash(stale)})

        update._remove_obsolete_files(str(self.extracted), str(self.install), PROTECTED)

        self.assertTrue(stale.exists())

    def test_copy_failure_does_not_run_cleanup_or_write_manifest(self):
        """Leave cleanup metadata untouched when the release copy fails."""
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
        """Refuse a cleanup batch larger than the safety threshold."""
        stale_files = [
            self._write(self.install, f"old_{index}.txt", str(index))
            for index in range(3)
        ]
        self._write_manifest({path.name: self._hash(path) for path in stale_files})

        update._remove_obsolete_files(str(self.extracted), str(self.install), PROTECTED)

        self.assertTrue(all(path.exists() for path in stale_files))

    def test_skipped_cleanup_keeps_records_for_later_updates(self):
        """Persist deferred removals and retry them after a larger release."""
        stale_files = [
            self._write(self.install, f"old_{index}.txt", str(index))
            for index in range(3)
        ]
        self._write_manifest({path.name: self._hash(path) for path in stale_files})
        update._finish_file_update(str(self.extracted), str(self.install), PROTECTED)
        self.assertEqual(
            len(json.loads((self.install / update.PENDING_CLEANUP).read_text())["files"]),
            3,
        )
        self.assertNotIn(
            "old_0.txt",
            json.loads((self.install / update.INSTALLED_FILES_MANIFEST).read_text()),
        )

        for index in range(10):
            self._write(self.extracted, f"more/file_{index}.txt", str(index))
        update._finish_file_update(str(self.extracted), str(self.install), PROTECTED)
        self.assertFalse(any(path.exists() for path in stale_files))
        self.assertEqual(
            json.loads((self.install / update.PENDING_CLEANUP).read_text())["files"],
            {},
        )

    def test_failed_removal_remains_pending(self):
        """Keep a removal record pending when deleting its file fails."""
        stale = self._write(self.install, "old.txt", "old")
        self._write_manifest({"old.txt": self._hash(stale)})
        with mock.patch.object(update.os, "remove", side_effect=OSError("busy")):
            update._finish_file_update(str(self.extracted), str(self.install), PROTECTED)

        self.assertTrue(stale.exists())
        self.assertIn(
            "old.txt",
            json.loads((self.install / update.PENDING_CLEANUP).read_text())["files"],
        )

    def test_git_checkout_skips_cleanup(self):
        """Skip cleanup when the installation contains a Git directory."""
        (self.install / ".git").mkdir()
        stale = self._write(self.install, "old.txt", "old")
        self._write_manifest({"old.txt": self._hash(stale)})

        update._remove_obsolete_files(str(self.extracted), str(self.install), PROTECTED)

        self.assertTrue(stale.exists())

    def test_git_worktree_file_skips_cleanup(self):
        """Skip cleanup when the installation contains a Git worktree file."""
        self._write(self.install, ".git", "gitdir: /some/worktree")
        stale = self._write(self.install, "old.txt", "old")
        self._write_manifest({"old.txt": self._hash(stale)})

        update._remove_obsolete_files(str(self.extracted), str(self.install), PROTECTED)

        self.assertTrue(stale.exists())

    def test_manifest_is_atomic_and_excludes_protected_folders(self):
        """Write manifests atomically without inventorying protected folders."""
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

    def test_manifest_parent_symlink_cannot_write_outside_install(self):
        """Reject a manifest parent symlink that leaves the install root."""
        outside = self.root / "outside"
        outside.mkdir()
        (self.install / "src/data").mkdir(parents=True)
        try:
            (self.install / "src/data/user").symlink_to(outside, target_is_directory=True)
        except OSError:
            self.skipTest("directory symlinks are unavailable")

        update._finish_file_update(str(self.extracted), str(self.install), PROTECTED)

        self.assertEqual(list(outside.iterdir()), [])

    def test_manifest_symlink_cannot_read_outside_install(self):
        """Reject an installed-manifest symlink without reading its target."""
        outside = self._write(self.root, "outside.json", "outside")
        manifest = self.install / update.INSTALLED_FILES_MANIFEST
        manifest.parent.mkdir(parents=True)
        try:
            manifest.symlink_to(outside)
        except OSError:
            self.skipTest("file symlinks are unavailable")

        update._finish_file_update(str(self.extracted), str(self.install), PROTECTED)

        self.assertEqual(outside.read_text(), "outside")
        self.assertTrue(manifest.is_symlink())


if __name__ == "__main__":
    main()
