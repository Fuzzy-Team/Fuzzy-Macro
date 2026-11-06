import hashlib
import os
import platform
import shutil
import sys
from contextlib import contextmanager
import tempfile
import threading
import zipfile
from io import BytesIO

import requests


MODELS_API_URL = "https://api.github.com/repos/Fuzzy-Team/fuzzymacroaimodels/contents"
MODELS_ZIP_URL = "https://github.com/Fuzzy-Team/fuzzymacroaimodels/archive/refs/heads/main.zip"
MODEL_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "models"))
COREML_MODELS = (
    "token_detection_standard.mlmodelc",
    "bloom_detection_standard.mlmodelc",
    "bloom_detection_light.mlmodelc",
    "bloom_detection_mini.mlmodelc",
    "sprinkler_detection_standard.mlmodelc",
    "token_detection_small.mlmodelc",
    "token_detection_mini.mlmodelc",
    "loot_detection_small.mlmodelc",
    "loot_detection_mini.mlmodelc",
)
ONNX_MODELS = (
    "token_detection_standard.onnx",
    "sprinkler_detection_standard.onnx",
    "bloom_detection_standard.onnx",
    "bloom_detection_light.onnx",
    "bloom_detection_mini.onnx",
)
VICIOUS_MODEL = "vicious_bee.onnx"
# Files macOS adds to folders it has opened; never part of a model.
MACOS_METADATA_FILES = {".DS_Store"}


def _macos_version():
    version = platform.mac_ver()[0]
    parts = []
    for part in version.split("."):
        try:
            parts.append(int(part))
        except ValueError:
            parts.append(0)
    while len(parts) < 2:
        parts.append(0)
    return tuple(parts[:2])


# Reading a Core ML output array needs MLMultiArray.getBytesWithHandler, added in macOS 12.3.
# Older systems use the ONNX models.
COREML_MIN_MACOS = (12, 3)

_coreml = False  # not imported yet
_coreml_lock = threading.Lock()


def import_coreml():
    """Return the PyObjC CoreML module, or None where Core ML isn't used (before macOS 12.3) or it fails to load."""
    global _coreml
    with _coreml_lock:
        if _coreml is not False:
            return _coreml
        _coreml = None
        if _macos_version() < COREML_MIN_MACOS:
            return None
        try:
            import CoreML
            _coreml = CoreML
        except Exception as exc:
            print(f"[models] Could not load Core ML, so Core ML models are unavailable: {exc}")
        return _coreml


class CoreMLModel:
    """Runs a compiled .mlmodelc through the system Core ML framework.

    predict({input_name: PIL image}) returns {output_name: numpy array}, matching what
    coremltools did, so the macro doesn't need coremltools (and its sympy dependency).
    """

    def __init__(self, path):
        import Foundation
        coreml = import_coreml()
        if coreml is None:
            raise RuntimeError("Core ML needs macOS 12.3 or later")
        config = coreml.MLModelConfiguration.alloc().init()
        config.setComputeUnits_(coreml.MLComputeUnitsAll)
        url = Foundation.NSURL.fileURLWithPath_(str(path))
        model, error = coreml.MLModel.modelWithContentsOfURL_configuration_error_(url, config, None)
        if model is None:
            raise RuntimeError(f"Core ML could not load {path}: {error}")
        self._coreml = coreml
        self._model = model

    def _pixelBuffer(self, image):
        import numpy as np
        import Quartz
        bgr = np.asarray(image.convert("RGB"))[..., ::-1]
        height, width = bgr.shape[:2]
        status, buffer = Quartz.CVPixelBufferCreate(None, width, height, Quartz.kCVPixelFormatType_32BGRA, None, None)
        if status != 0:
            raise RuntimeError(f"Could not create a {width}x{height} pixel buffer ({status})")
        Quartz.CVPixelBufferLockBaseAddress(buffer, 0)
        try:
            rowBytes = Quartz.CVPixelBufferGetBytesPerRow(buffer)
            raw = Quartz.CVPixelBufferGetBaseAddress(buffer).as_buffer(rowBytes * height)
            pixels = np.frombuffer(raw, dtype=np.uint8).reshape(height, rowBytes)[:, :width * 4].reshape(height, width, 4)
            pixels[..., :3] = bgr
            pixels[..., 3] = 255
        finally:
            Quartz.CVPixelBufferUnlockBaseAddress(buffer, 0)
        return buffer

    def predict(self, inputs):
        import numpy as np
        dtypes = {
            self._coreml.MLMultiArrayDataTypeFloat32: np.float32,
            self._coreml.MLMultiArrayDataTypeFloat16: np.float16,
            self._coreml.MLMultiArrayDataTypeDouble: np.float64,
            self._coreml.MLMultiArrayDataTypeInt32: np.int32,
        }
        features = {
            name: self._coreml.MLFeatureValue.featureValueWithPixelBuffer_(self._pixelBuffer(image))
            for name, image in inputs.items()
        }
        provider, error = self._coreml.MLDictionaryFeatureProvider.alloc().initWithDictionary_error_(features, None)
        result, error = self._model.predictionFromFeatures_error_(provider, None)
        if result is None:
            raise RuntimeError(f"Core ML prediction failed: {error}")
        outputs = {}
        for name in result.featureNames():
            array = result.featureValueForName_(name).multiArrayValue()
            if array is None:
                continue
            dtype = dtypes[array.dataType()]
            shape = tuple(int(s) for s in array.shape())
            strides = tuple(int(s) * np.dtype(dtype).itemsize for s in array.strides())

            def copyOut(pointer, _strides, name=name, dtype=dtype, shape=shape, strides=strides):
                flat = np.frombuffer(pointer, dtype=dtype)
                outputs[name] = np.lib.stride_tricks.as_strided(flat, shape=shape, strides=strides).copy()

            array.getBytesWithHandler_(copyOut)
        return outputs


def _supported_model_names():
    # Core ML is the native model format on supported macOS versions. Download
    # ONNX only as the cross-platform fallback; fetching both makes startup
    # repeatedly restore ONNX models that the Core ML runtime later removes.
    if _macos_version() >= COREML_MIN_MACOS:
        return COREML_MODELS + (VICIOUS_MODEL,)
    return ONNX_MODELS + (VICIOUS_MODEL,)


def _delete_path(path):
    try:
        if os.path.islink(path):
            print(f"[models] Kept symlink {path}")
            return False
        if os.path.isdir(path):
            for name in os.listdir(path):
                _delete_path(os.path.join(path, name))
            if os.listdir(path):
                return False
            os.rmdir(path)
        elif os.path.isfile(path):
            if path.lower().endswith(".pt"):
                print(f"[models] Kept .pt file {path}")
                return False
            os.remove(path)
        else:
            return False
        return True
    except Exception as exc:
        print(f"[models] Could not delete obsolete model {path}: {exc}")
        return False


def cleanup_unused_models():
    """Remove every local model not used by this release on this platform."""
    if os.path.islink(MODEL_DIR):
        print(f"[models] Skipping cleanup through symlinked model folder {MODEL_DIR}")
        return []
    try:
        entries = list(os.scandir(MODEL_DIR))
    except OSError as exc:
        print(f"[models] Could not list model folder: {exc}")
        return []
    supported = set(_supported_model_names())
    if not supported:
        print("[models] Skipping cleanup: release has no supported model list")
        return []
    deleted = []
    for entry in entries:
        if entry.name not in supported and _delete_path(entry.path):
            deleted.append(entry.name)
    deleted_models = [name for name in deleted if not _is_macos_metadata(name)]
    if deleted_models:
        print(f"[models] Deleted unused models: {', '.join(deleted_models)}")
    return deleted


def _git_blob_sha(path):
    """Return the Git blob SHA-1 that GitHub reports for the file at ``path``."""
    # Kept separate from update.py, which is replaced from main mid-update.
    digest = hashlib.sha1()
    size = os.path.getsize(path)
    digest.update(f"blob {size}\0".encode("utf-8"))
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_macos_metadata(filename):
    return filename in MACOS_METADATA_FILES or filename.startswith("._")


def _github_get(url, timeout=20):
    response = requests.get(
        url,
        timeout=timeout,
        headers={
            "Accept": "application/vnd.github.v3+json",
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )
    response.raise_for_status()
    return response.json()


def _remote_tree(api_url):
    entries = _github_get(api_url)
    if isinstance(entries, dict):
        entries = [entries]
    files = []
    for entry in entries:
        entry_type = entry.get("type")
        if entry_type == "file":
            files.append(entry)
        elif entry_type == "dir":
            files.extend(_remote_tree(entry["url"]))
    return files


def _local_matches_remote(local_root, remote_files, remote_root_path):
    if not remote_files or not os.path.exists(local_root):
        return False
    if len(remote_files) == 1 and remote_files[0].get("path") == remote_root_path:
        return (os.path.isfile(local_root) and not os.path.islink(local_root)
                and _git_blob_sha(local_root) == remote_files[0].get("sha"))
    if not os.path.isdir(local_root) or os.path.islink(local_root):
        return False
    expected_paths = set()
    for remote_file in remote_files:
        rel_path = os.path.relpath(remote_file["path"], remote_root_path)
        expected_paths.add(rel_path)
        local_path = os.path.join(local_root, rel_path)
        if not os.path.isfile(local_path) or os.path.islink(local_path):
            return False
        if _git_blob_sha(local_path) != remote_file.get("sha"):
            return False
    for root, dirs, files in os.walk(local_root):
        if any(os.path.islink(os.path.join(root, name)) for name in dirs):
            return False
        for filename in files:
            path = os.path.relpath(os.path.join(root, filename), local_root)
            if path not in expected_paths and not _is_macos_metadata(filename):
                return False
    return True


def _download_file(url, destination):
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    with requests.get(url, timeout=60, stream=True) as response:
        response.raise_for_status()
        with open(destination, "wb") as fh:
            for chunk in response.iter_content(chunk_size=1024 * 256):
                if chunk:
                    fh.write(chunk)


def _download_remote_tree(remote_files, remote_root_path, destination_root):
    tmp_root = tempfile.mkdtemp(prefix="fuzzy-model-", dir=os.path.dirname(destination_root))
    try:
        if len(remote_files) == 1 and remote_files[0].get("path") == remote_root_path:
            tmp_file = os.path.join(tmp_root, remote_root_path)
            _download_file(remote_files[0]["download_url"], tmp_file)
            if not _local_matches_remote(tmp_file, remote_files, remote_root_path):
                raise ValueError(f"Downloaded model failed hash check: {remote_root_path}")
            if os.path.exists(destination_root):
                if os.path.isdir(destination_root):
                    shutil.rmtree(destination_root)
                else:
                    os.remove(destination_root)
            os.replace(tmp_file, destination_root)
            shutil.rmtree(tmp_root, ignore_errors=True)
            return
        for remote_file in remote_files:
            rel_path = os.path.relpath(remote_file["path"], remote_root_path)
            _download_file(remote_file["download_url"], os.path.join(tmp_root, rel_path))
        if not _local_matches_remote(tmp_root, remote_files, remote_root_path):
            raise ValueError(f"Downloaded model failed hash check: {remote_root_path}")
        if os.path.exists(destination_root):
            if os.path.isdir(destination_root):
                shutil.rmtree(destination_root)
            else:
                os.remove(destination_root)
        os.replace(tmp_root, destination_root)
    except Exception:
        shutil.rmtree(tmp_root, ignore_errors=True)
        raise


def _copy_from_repo_zip(model_name, destination_root):
    response = requests.get(MODELS_ZIP_URL, timeout=90)
    response.raise_for_status()
    archive = zipfile.ZipFile(BytesIO(response.content))
    prefix = None
    for name in archive.namelist():
        parts = name.split("/", 1)
        if len(parts) == 2 and parts[1].startswith(model_name):
            prefix = parts[0] + "/"
            break
    if prefix is None:
        raise FileNotFoundError(f"{model_name} was not found in the model repository zip.")

    model_prefix = prefix + model_name
    tmp_root = tempfile.mkdtemp(prefix="fuzzy-model-", dir=os.path.dirname(destination_root))
    try:
        if model_name.endswith(".onnx"):
            archive.extract(model_prefix, tmp_root)
            extracted_path = os.path.join(tmp_root, model_prefix)
            if os.path.exists(destination_root):
                if os.path.isdir(destination_root):
                    shutil.rmtree(destination_root)
                else:
                    os.remove(destination_root)
            os.replace(extracted_path, destination_root)
            return

        package_tmp = os.path.join(tmp_root, model_name)
        for name in archive.namelist():
            if name == model_prefix or not name.startswith(model_prefix + "/") or name.endswith("/"):
                continue
            rel_path = os.path.relpath(name, model_prefix)
            target = os.path.join(package_tmp, rel_path)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with archive.open(name) as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst)
        if os.path.exists(destination_root):
            if os.path.isdir(destination_root):
                shutil.rmtree(destination_root)
            else:
                os.remove(destination_root)
        os.replace(package_tmp, destination_root)
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)


def ensure_supported_models():
    os.makedirs(MODEL_DIR, exist_ok=True)
    downloaded = []
    skipped = []
    for model_name in _supported_model_names():
        api_url = f"{MODELS_API_URL}/{model_name}"
        local_path = os.path.join(MODEL_DIR, model_name)
        try:
            remote_files = _remote_tree(api_url)
            if _local_matches_remote(local_path, remote_files, model_name):
                skipped.append(model_name)
                continue
            print(f"[models] Downloading {model_name}...")
            _download_remote_tree(remote_files, model_name, local_path)
            downloaded.append(model_name)
        except Exception as exc:
            if os.path.exists(local_path):
                print(f"[models] Skipping remote hash check for {model_name}: {exc}")
                skipped.append(model_name)
                continue
            print(f"[models] Downloading {model_name} from repository zip...")
            _copy_from_repo_zip(model_name, local_path)
            downloaded.append(model_name)
    if downloaded:
        print(f"[models] Downloaded/updated: {', '.join(downloaded)}")
    elif skipped:
        print("[models] Models are up to date")
    cleanup_unused_models()
    return {"downloaded": downloaded, "skipped": skipped, "model_dir": MODEL_DIR}


@contextmanager
def _model_download_progress(total):
    width = 0

    def update(completed, message):
        nonlocal width
        filled = 24 * completed // total if total else 24
        line = f"[models] [{'#' * filled}{'-' * (24 - filled)}] {completed}/{total} {message}"
        sys.stdout.write("\r" + line.ljust(width))
        sys.stdout.flush()
        width = len(line)

    try:
        yield update
    finally:
        if width:
            sys.stdout.write("\n")
            sys.stdout.flush()


def ensure_missing_supported_models():
    os.makedirs(MODEL_DIR, exist_ok=True)
    downloaded = []
    skipped = []
    model_names = _supported_model_names()
    skipped = [name for name in model_names if os.path.exists(os.path.join(MODEL_DIR, name))]
    missing = [name for name in model_names if name not in skipped]
    with _model_download_progress(len(missing)) as progress:
        for model_name in missing:
            local_path = os.path.join(MODEL_DIR, model_name)
            progress(len(downloaded), f"Downloading {model_name}...")
            try:
                remote_files = _remote_tree(f"{MODELS_API_URL}/{model_name}")
                _download_remote_tree(remote_files, model_name, local_path)
            except Exception:
                progress(len(downloaded), f"Downloading {model_name} from repository zip...")
                _copy_from_repo_zip(model_name, local_path)
            downloaded.append(model_name)
            progress(len(downloaded), "Models downloaded" if len(downloaded) == len(missing) else f"Downloaded {model_name}")
    cleanup_unused_models()
    return {"downloaded": downloaded, "skipped": skipped, "model_dir": MODEL_DIR}


def ensure_missing_models(model_names):
    os.makedirs(MODEL_DIR, exist_ok=True)
    downloaded = []
    skipped = []
    missing_remote = []
    failures = {}
    for model_name in model_names:
        if model_name not in set(COREML_MODELS).union(ONNX_MODELS, (VICIOUS_MODEL,)):
            failures[model_name] = "unknown model name"
            continue
        local_path = os.path.join(MODEL_DIR, model_name)
        if os.path.exists(local_path):
            skipped.append(model_name)
            continue
        try:
            remote_files = _remote_tree(f"{MODELS_API_URL}/{model_name}")
            print(f"[models] Downloading missing {model_name}...")
            _download_remote_tree(remote_files, model_name, local_path)
            downloaded.append(model_name)
        except Exception as exc:
            print(f"[models] Remote check failed for {model_name}: {exc}")
            try:
                print(f"[models] Checking repository zip for {model_name}...")
                _copy_from_repo_zip(model_name, local_path)
                downloaded.append(model_name)
            except Exception as zip_exc:
                missing_remote.append(model_name)
                failures[model_name] = (
                    f"direct download failed: {exc}; repository zip fallback failed: {zip_exc}"
                )

    # Callers can explicitly request the ONNX fallback on macOS.  Do not run
    # the platform cleanup here, as it would delete that fallback before the
    # caller has a chance to load it.
    return {
        "downloaded": downloaded,
        "skipped": skipped,
        "missing_remote": missing_remote,
        "failures": failures,
        "model_dir": MODEL_DIR,
    }
