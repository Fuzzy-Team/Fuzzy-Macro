import sys
import tempfile
from pathlib import Path
from unittest import TestCase, main, mock


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
from modules.misc import modelManager, update


class ModelCleanupTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.model_dir = Path(self.temp.name) / "models"
        self.model_dir.mkdir()
        patcher = mock.patch.object(modelManager, "MODEL_DIR", str(self.model_dir))
        patcher.start()
        self.addCleanup(patcher.stop)

    def _write(self, name, content="model"):
        path = self.model_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def test_cleanup_removes_every_entry_not_used_on_this_platform(self):
        used = self.model_dir / "token_detection_standard.mlmodelc"
        self._write("token_detection_standard.mlmodelc/weights.bin")
        old = self.model_dir / "old_model.mlmodelc"
        self._write("old_model.mlmodelc/weights.bin")
        alternate_format = self._write("token_detection_standard.onnx")
        custom = self._write("custom_model.onnx")

        with mock.patch.object(modelManager, "_macos_version", return_value=(13, 0)):
            deleted = modelManager.cleanup_unused_models()

        self.assertTrue(used.exists())
        self.assertFalse(old.exists())
        self.assertFalse(alternate_format.exists())
        self.assertFalse(custom.exists())
        self.assertEqual(set(deleted), {
            "old_model.mlmodelc", "token_detection_standard.onnx", "custom_model.onnx",
        })

    def test_onnx_platform_keeps_onnx_and_removes_coreml(self):
        used = self._write("token_detection_standard.onnx")
        unused = self.model_dir / "token_detection_standard.mlmodelc"
        self._write("token_detection_standard.mlmodelc/weights.bin")

        with mock.patch.object(modelManager, "_macos_version", return_value=(0, 0)):
            modelManager.cleanup_unused_models()

        self.assertTrue(used.exists())
        self.assertFalse(unused.exists())

    def test_pt_files_survive_cleanup_at_any_depth(self):
        top_level = self._write("custom.pt")
        upper_case = self._write("CUSTOM.PT")
        nested = self._write("old_bundle/weights.pt")
        unused = self._write("old_bundle/old.bin")

        with mock.patch.object(modelManager, "_macos_version", return_value=(13, 0)):
            deleted = modelManager.cleanup_unused_models()

        self.assertTrue(top_level.exists())
        self.assertTrue(upper_case.exists())
        self.assertTrue(nested.exists())
        self.assertFalse(unused.exists())
        self.assertNotIn("old_bundle", deleted)

    def test_empty_model_list_does_not_delete_everything(self):
        installed = self._write("model.onnx")
        with mock.patch.object(modelManager, "_supported_model_names", return_value=()):
            self.assertEqual(modelManager.cleanup_unused_models(), [])
        self.assertTrue(installed.exists())

    def test_cleanup_does_not_follow_symlinks(self):
        outside = Path(self.temp.name) / "outside"
        outside.mkdir()
        target = outside / "weights.bin"
        target.write_text("keep", encoding="utf-8")
        try:
            (self.model_dir / "linked_model.mlmodelc").symlink_to(outside, target_is_directory=True)
        except OSError:
            self.skipTest("symlinks are unavailable")

        with mock.patch.object(modelManager, "_macos_version", return_value=(13, 0)):
            modelManager.cleanup_unused_models()

        self.assertEqual(target.read_text(), "keep")
        self.assertTrue((self.model_dir / "linked_model.mlmodelc").is_symlink())

    def test_same_name_new_hash_downloads_updated_model(self):
        current = self._write("token_detection_standard.onnx", "old")
        incoming = self._write("remote.txt", "new")
        remote_hash = modelManager._git_blob_sha(incoming)
        incoming.unlink()
        remote_files = [{"path": "token_detection_standard.onnx", "sha": remote_hash}]

        def download(files, name, destination):
            Path(destination).write_text("new", encoding="utf-8")

        with mock.patch.object(modelManager, "_supported_model_names", return_value=("token_detection_standard.onnx",)), \
             mock.patch.object(modelManager, "_remote_tree", return_value=remote_files), \
             mock.patch.object(modelManager, "_download_remote_tree", side_effect=download) as downloader:
            result = modelManager.ensure_supported_models()

        self.assertEqual(current.read_text(), "new")
        self.assertEqual(result["downloaded"], ["token_detection_standard.onnx"])
        downloader.assert_called_once()

    def test_extra_file_inside_model_bundle_forces_replacement(self):
        bundle = self.model_dir / "token_detection_standard.mlmodelc"
        self._write("token_detection_standard.mlmodelc/weights.bin", "current")
        self._write("token_detection_standard.mlmodelc/old.bin", "obsolete")
        known = self._write("known.txt", "current")
        expected_hash = modelManager._git_blob_sha(known)
        known.unlink()
        remote_files = [{"path": "token_detection_standard.mlmodelc/weights.bin", "sha": expected_hash}]

        def download(files, name, destination):
            (bundle / "old.bin").unlink()

        with mock.patch.object(modelManager, "_supported_model_names", return_value=(bundle.name,)), \
             mock.patch.object(modelManager, "_remote_tree", return_value=remote_files), \
             mock.patch.object(modelManager, "_download_remote_tree", side_effect=download) as downloader:
            modelManager.ensure_supported_models()

        downloader.assert_called_once()
        self.assertFalse((bundle / "old.bin").exists())

    def test_macos_metadata_inside_model_bundle_does_not_force_download(self):
        bundle = self.model_dir / "token_detection_standard.mlmodelc"
        weights = self._write("token_detection_standard.mlmodelc/weights.bin", "current")
        self._write("token_detection_standard.mlmodelc/.DS_Store", "finder")
        self._write("token_detection_standard.mlmodelc/._weights.bin", "appledouble")
        remote_files = [{
            "path": "token_detection_standard.mlmodelc/weights.bin",
            "sha": modelManager._git_blob_sha(weights),
        }]

        self.assertTrue(modelManager._local_matches_remote(str(bundle), remote_files, bundle.name))

    def test_bad_download_hash_keeps_installed_model(self):
        existing = self._write("token_detection_standard.onnx", "original")
        expected = self._write("expected.txt", "new")
        expected_hash = modelManager._git_blob_sha(expected)
        expected.unlink()
        remote_files = [{"path": existing.name, "sha": expected_hash, "download_url": "unused"}]

        def corrupt_download(url, destination):
            Path(destination).parent.mkdir(parents=True, exist_ok=True)
            Path(destination).write_text("corrupt", encoding="utf-8")

        with mock.patch.object(modelManager, "_download_file", side_effect=corrupt_download):
            with self.assertRaises(ValueError):
                modelManager._download_remote_tree(remote_files, existing.name, str(existing))
        self.assertEqual(existing.read_text(), "original")

    def test_updater_uses_newly_installed_model_manager(self):
        refreshed = mock.Mock()
        with mock.patch.object(modelManager, "__cached__", None), \
             mock.patch.object(update.importlib, "reload", return_value=refreshed) as reload:
            update._check_ai_models()
        reload.assert_called_once_with(modelManager)
        refreshed.ensure_supported_models.assert_called_once_with()


if __name__ == "__main__":
    main()
