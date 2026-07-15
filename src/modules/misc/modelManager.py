import hashlib
import os
import platform
import shutil
import tempfile
import zipfile
from io import BytesIO

import requests


MODELS_API_URL = "https://api.github.com/repos/Fuzzy-Team/fuzzymacroaimodels/contents"
MODELS_ZIP_URL = "https://github.com/Fuzzy-Team/fuzzymacroaimodels/archive/refs/heads/main.zip"
MODEL_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "models"))
COREML_MODELS = (
    "token_detection_standard.mlmodelc",
    "sprinkler_detection_standard.mlmodelc",
    "token_detection_small.mlmodelc",
    "token_detection_mini.mlmodelc",
    "loot_detection_small.mlmodelc",
    "loot_detection_mini.mlmodelc",
)
ONNX_MODELS = (
    "token_detection_standard.onnx",
    "sprinkler_detection_standard.onnx",
)
OBSOLETE_MODELS = (
    "best.mlpackage",
    "sprinkler.mlpackage",
)


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


def _supported_model_names():
    # Core ML is the native model format on supported macOS versions. Download
    # ONNX only as the cross-platform fallback; fetching both makes startup
    # repeatedly restore ONNX models that the Core ML runtime later removes.
    if _macos_version() >= (12, 0):
        return COREML_MODELS
    return ONNX_MODELS


def _delete_path(path):
    try:
        if os.path.isdir(path):
            shutil.rmtree(path)
        elif os.path.exists(path):
            os.remove(path)
        else:
            return False
        return True
    except Exception as exc:
        print(f"[models] Could not delete obsolete model {path}: {exc}")
        return False


def cleanup_obsolete_models():
    deleted = []
    for model_name in OBSOLETE_MODELS:
        model_path = os.path.join(MODEL_DIR, model_name)
        if _delete_path(model_path):
            deleted.append(model_name)
    if deleted:
        print(f"[models] Deleted obsolete models: {', '.join(deleted)}")
    return deleted


def cleanup_unsupported_model_formats():
    supported = set(_supported_model_names())
    all_known = set(COREML_MODELS).union(ONNX_MODELS)
    deleted = []
    for model_name in sorted(all_known - supported):
        model_path = os.path.join(MODEL_DIR, model_name)
        if _delete_path(model_path):
            deleted.append(model_name)
    if deleted:
        print(f"[models] Deleted unsupported model format: {', '.join(deleted)}")
    return deleted


def cleanup_unused_models():
    deleted = []
    deleted.extend(cleanup_obsolete_models())
    deleted.extend(cleanup_unsupported_model_formats())
    return deleted


def _git_blob_sha(path):
    h = hashlib.sha1()
    size = os.path.getsize(path)
    h.update(f"blob {size}\0".encode("utf-8"))
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


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
    if not os.path.exists(local_root):
        return False
    if len(remote_files) == 1 and remote_files[0].get("path") == remote_root_path:
        return os.path.isfile(local_root) and _git_blob_sha(local_root) == remote_files[0].get("sha")
    for remote_file in remote_files:
        rel_path = os.path.relpath(remote_file["path"], remote_root_path)
        local_path = os.path.join(local_root, rel_path)
        if not os.path.isfile(local_path):
            return False
        if _git_blob_sha(local_path) != remote_file.get("sha"):
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


def ensure_missing_supported_models():
    os.makedirs(MODEL_DIR, exist_ok=True)
    downloaded = []
    skipped = []
    for model_name in _supported_model_names():
        local_path = os.path.join(MODEL_DIR, model_name)
        if os.path.exists(local_path):
            skipped.append(model_name)
            continue
        try:
            remote_files = _remote_tree(f"{MODELS_API_URL}/{model_name}")
            print(f"[models] Downloading missing {model_name}...")
            _download_remote_tree(remote_files, model_name, local_path)
        except Exception as exc:
            print(f"[models] Could not download {model_name} directly: {exc}")
            print(f"[models] Checking repository zip for {model_name}...")
            _copy_from_repo_zip(model_name, local_path)
        downloaded.append(model_name)
    cleanup_unused_models()
    return {"downloaded": downloaded, "skipped": skipped, "model_dir": MODEL_DIR}


def ensure_missing_models(model_names):
    os.makedirs(MODEL_DIR, exist_ok=True)
    downloaded = []
    skipped = []
    missing_remote = []
    for model_name in model_names:
        if model_name not in _supported_model_names():
            raise ValueError(f"{model_name} is not a supported model.")
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
            except Exception:
                missing_remote.append(model_name)
    cleanup_unused_models()
    return {
        "downloaded": downloaded,
        "skipped": skipped,
        "missing_remote": missing_remote,
        "model_dir": MODEL_DIR,
    }
