import stat
import os
import re
import hashlib
import json
import importlib
import sys
import requests
import zipfile
import shutil
from io import BytesIO
from modules.misc.messageBox import msgBox


# These are shipped patterns whose implementation must stay in sync with the
# bundled model manager.  They are not user-authored patterns, so always
# replace them during an update instead of preserving an obsolete copy.
PATTERN_OVERWRITE_EXCEPTIONS = {"blooms_ai.py", "fuzzy_ai_gather.py"}
OBSOLETE_FILES_URL = "https://raw.githubusercontent.com/Fuzzy-Team/Fuzzy-Macro/refs/heads/main/obsolete_files.json"
INSTALLED_FILES_MANIFEST = os.path.join("src", "data", "user", "installed_files.json")
PENDING_CLEANUP = os.path.join("src", "data", "user", "pending_cleanup.json")

# Preserve this flag across importlib.reload().  It prevents the freshly
# loaded updater from handing off to itself a second time.
if "_UPDATER_HANDOFF_ACTIVE" not in globals():
    _UPDATER_HANDOFF_ACTIVE = False

# Helper: parse version strings like 1.2.3 or 1.2.3a
def _parse_version(v):
    if not v:
        return (0, 0, 0, "")
    v = v.strip()
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)([A-Za-z]?)$", v)
    if not m:
        return (0, 0, 0, "")
    major, minor, patch, letter = m.groups()
    return (int(major), int(minor), int(patch), letter or "")


# return True if remote > local
def _is_remote_newer(local_v, remote_v):
    lv = _parse_version(local_v)
    rv = _parse_version(remote_v)
    for i in range(3):
        if rv[i] != lv[i]:
            return rv[i] > lv[i]
    # numeric parts equal, compare letter: a suffix (letter) denotes
    # a prerelease and is considered older than the same version
    # without a letter. Examples:
    #   1.1.0  > 1.1.0a
    #   1.1.0b > 1.1.0a
    if lv[3] == rv[3]:
        return False
    # local has a letter and remote does not -> remote is newer
    if lv[3] != "" and rv[3] == "":
        return True
    # local has no letter and remote does -> remote is older
    if lv[3] == "" and rv[3] != "":
        return False
    # both have letters: compare lexicographically
    return rv[3] > lv[3]


def _report_update_progress(progress_callback, percent, message):
    percent = max(0, min(100, int(percent)))
    bar_width = 24
    filled = int(bar_width * percent / 100)
    bar = "#" * filled + "-" * (bar_width - filled)
    print(f"\rUpdate progress [{bar}] {percent:3d}% {message}", end="", flush=True)
    if percent >= 100 or "failed" in message.lower() or "aborted" in message.lower():
        print()
    if progress_callback is not None:
        try:
            progress_callback(percent, message)
        except Exception:
            pass


def _download_update_zip(zip_link, progress_callback, start_percent=35, end_percent=65):
    req = requests.get(zip_link, timeout=60, stream=True)
    try:
        req.raise_for_status()

        total = int(req.headers.get("content-length", 0) or 0)
        downloaded = 0
        last_percent = start_percent - 1
        data = BytesIO()

        for chunk in req.iter_content(chunk_size=1024 * 128):
            if not chunk:
                continue
            data.write(chunk)
            downloaded += len(chunk)
            if total:
                percent = start_percent + int((end_percent - start_percent) * downloaded / total)
                if percent != last_percent:
                    _report_update_progress(progress_callback, percent, "Downloading update")
                    last_percent = percent

        if not total:
            _report_update_progress(progress_callback, end_percent, "Downloaded update")

        data.seek(0)
        return zipfile.ZipFile(data)
    finally:
        req.close()


def _git_blob_sha(path):
    """Return the Git blob SHA-1 for the file at ``path``."""
    digest = hashlib.sha1()
    size = os.path.getsize(path)
    digest.update(f"blob {size}\0".encode("utf-8"))
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_protected_path(relative_path, protected_folders):
    """Return whether a relative path is unsafe or protected from updates."""
    parts = relative_path.split("/")
    if (
        not relative_path
        or os.path.isabs(relative_path)
        or relative_path.startswith("/")
        or "\\" in relative_path
        or any(part in {"", ".", ".."} for part in parts)
    ):
        return True
    if parts[0] == ".git" or relative_path in {"backup_macro.zip", ".backup_pending"}:
        return True
    for protected in protected_folders:
        protected = protected.replace(os.sep, "/").strip("/")
        if relative_path == protected or relative_path.startswith(protected + "/"):
            return True
    return False


def _build_installed_files_manifest(extracted, protected_folders):
    """Map regular files in an extracted release to their Git blob hashes."""
    manifest = {}
    for root, dirs, files in os.walk(extracted, followlinks=False):
        rel_root = os.path.relpath(root, extracted)
        rel_root = "" if rel_root == "." else rel_root.replace(os.sep, "/")
        dirs[:] = [
            directory for directory in dirs
            if not os.path.islink(os.path.join(root, directory))
            and not _is_protected_path(
                "/".join(filter(None, (rel_root, directory))), protected_folders
            )
        ]
        for filename in files:
            relative_path = "/".join(filter(None, (rel_root, filename)))
            source_path = os.path.join(root, filename)
            try:
                mode = os.lstat(source_path).st_mode
                if _is_protected_path(relative_path, protected_folders) or not stat.S_ISREG(mode):
                    continue
                manifest[relative_path] = _git_blob_sha(source_path)
            except OSError as exc:
                raise OSError(f"Could not hash shipped file {relative_path}") from exc
    return manifest


def _load_json_hashes(path):
    """Load string path-to-hash entries from a JSON object."""
    with open(path, "r", encoding="utf-8") as fh:
        value = json.load(fh)
    if not isinstance(value, dict):
        raise ValueError("expected a JSON object")
    return {
        key: hash_value for key, hash_value in value.items()
        if isinstance(key, str) and isinstance(hash_value, str)
    }


def _metadata_path(destination, relative_path):
    """Reject metadata paths whose parent directory leaves the install root."""
    current = destination
    for part in relative_path.split(os.sep)[:-1]:
        current = os.path.join(current, part)
        if os.path.islink(current):
            raise ValueError(f"Metadata parent is a symlink: {current}")
    root = os.path.realpath(destination)
    if os.path.commonpath((root, os.path.realpath(current))) != root:
        raise ValueError(f"Metadata parent is outside the install root: {current}")
    path = os.path.join(destination, relative_path)
    if os.path.islink(path):
        raise ValueError(f"Metadata file is a symlink: {path}")
    return path


def _download_obsolete_files():
    """Download and validate the bootstrap inventory of obsolete files."""
    response = requests.get(OBSOLETE_FILES_URL, timeout=20, headers={
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
    })
    response.raise_for_status()
    value = response.json()
    if not isinstance(value, dict):
        raise ValueError("expected a JSON object")
    return {
        key: hash_value for key, hash_value in value.items()
        if isinstance(key, str) and isinstance(hash_value, str)
    }


def _safe_regular_file(destination, relative_path, protected_folders):
    """Return an in-root regular file path when it is safe to remove."""
    if _is_protected_path(relative_path, protected_folders):
        return None
    root = os.path.realpath(destination)
    candidate = os.path.join(destination, *relative_path.split("/"))
    try:
        current = destination
        for part in relative_path.split("/")[:-1]:
            current = os.path.join(current, part)
            if os.path.islink(current):
                return None
        mode = os.lstat(candidate).st_mode
    except OSError:
        return None
    resolved = os.path.realpath(candidate)
    try:
        inside_root = os.path.commonpath((root, resolved)) == root
    except ValueError:
        inside_root = False
    if not inside_root or not stat.S_ISREG(mode):
        return None
    return candidate


def _remove_empty_directories(start, destination, protected_folders):
    """Remove empty parent directories up to the installation root."""
    root = os.path.realpath(destination)
    current = os.path.dirname(start)
    while os.path.realpath(current) != root:
        relative_path = os.path.relpath(current, destination).replace(os.sep, "/")
        if _is_protected_path(relative_path, protected_folders) or os.path.islink(current):
            break
        try:
            os.rmdir(current)
        except OSError:
            break
        current = os.path.dirname(current)


def _remove_compiled_files(source_path, destination, protected_folders, new_manifest):
    """Remove unshipped bytecode associated with a deleted Python source file."""
    if not source_path.endswith(".py"):
        return
    cache_dir = os.path.join(os.path.dirname(source_path), "__pycache__")
    source_name = os.path.splitext(os.path.basename(source_path))[0]
    try:
        cache_entries = os.listdir(cache_dir)
    except OSError:
        return
    for filename in cache_entries:
        if not (filename.startswith(source_name + ".cpython-") and filename.endswith(".pyc")):
            continue
        relative_path = os.path.relpath(
            os.path.join(cache_dir, filename), destination
        ).replace(os.sep, "/")
        if relative_path in new_manifest:
            continue
        compiled_path = _safe_regular_file(destination, relative_path, protected_folders)
        if compiled_path is None:
            continue
        try:
            os.remove(compiled_path)
            print(f"[updater] Removed compiled file {relative_path}")
        except OSError as exc:
            print(f"[updater] Could not remove compiled file {relative_path}: {exc}")
    _remove_empty_directories(os.path.join(cache_dir, "placeholder"), destination, protected_folders)


def _remove_obsolete_files(extracted, destination, protected_folders, progress_callback=None):
    """Remove unchanged stale files and return records to retry on the next update."""
    required = (
        os.path.join(extracted, "src", "main.py"),
        os.path.join(extracted, "src", "modules", "misc", "update.py"),
    )
    if not all(os.path.isfile(path) and not os.path.islink(path) for path in required):
        print("[updater] Skipping obsolete-file cleanup: extracted release is incomplete")
        return None
    if os.path.lexists(os.path.join(destination, ".git")):
        print("[updater] Skipping obsolete-file cleanup in a git checkout")
        return None

    new_manifest = _build_installed_files_manifest(extracted, protected_folders)
    manifest_path = _metadata_path(destination, INSTALLED_FILES_MANIFEST)
    pending_path = _metadata_path(destination, PENDING_CLEANUP)
    pending = {"bootstrap_pending": False, "files": {}}
    if os.path.lexists(pending_path):
        with open(pending_path, "r", encoding="utf-8") as fh:
            pending = json.load(fh)
        if (
            not isinstance(pending, dict)
            or not isinstance(pending.get("bootstrap_pending"), bool)
            or not isinstance(pending.get("files"), dict)
        ):
            raise ValueError("Invalid pending-cleanup record")
        pending["files"] = {
            path: sha for path, sha in pending["files"].items()
            if isinstance(path, str) and isinstance(sha, str)
        }

    if os.path.isfile(manifest_path) and not os.path.islink(manifest_path):
        try:
            previous_manifest = _load_json_hashes(manifest_path)
        except Exception as exc:
            print(f"[updater] Could not read installed-files manifest; skipping cleanup: {exc}")
            return None
    else:
        previous_manifest = {}
        pending["bootstrap_pending"] = True

    if pending["bootstrap_pending"]:
        try:
            previous_manifest.update(_download_obsolete_files())
            pending["bootstrap_pending"] = False
        except Exception as exc:
            print(f"[updater] Could not download obsolete-files list; skipping bootstrap cleanup: {exc}")
            return pending

    stale = {
        path: hash_value for path, hash_value in {
            **previous_manifest, **pending["files"]
        }.items()
        if path not in new_manifest
    }
    pending["files"] = {}
    removals = []
    for relative_path, expected_hash in sorted(stale.items()):
        current_path = _safe_regular_file(destination, relative_path, protected_folders)
        if current_path is None:
            continue
        pending["files"][relative_path] = expected_hash
        try:
            current_hash = _git_blob_sha(current_path)
        except OSError as exc:
            print(f"[updater] Could not check obsolete file {relative_path}: {exc}")
            continue
        if current_hash == expected_hash:
            removals.append((relative_path, current_path))
        else:
            print(f"[updater] Kept edited obsolete file {relative_path}")

    if len(removals) * 5 > len(new_manifest):
        print(
            f"[updater] Skipping obsolete-file cleanup: {len(removals)} files "
            f"exceed 20% of the {len(new_manifest)} shipped files"
        )
        return pending

    _report_update_progress(progress_callback, 81, "Removing obsolete files")
    for index, (relative_path, current_path) in enumerate(removals, start=1):
        try:
            os.remove(current_path)
            pending["files"].pop(relative_path, None)
            print(f"[updater] Removed obsolete file {relative_path}")
            _remove_compiled_files(
                current_path, destination, protected_folders, new_manifest
            )
            _remove_empty_directories(current_path, destination, protected_folders)
            _report_update_progress(
                progress_callback,
                81 + int(2 * index / len(removals)),
                f"Removed obsolete file {index} of {len(removals)}",
            )
        except OSError as exc:
            print(f"[updater] Could not remove obsolete file {relative_path}: {exc}")
    return pending


def _write_json_atomically(path, value):
    """Serialize a value to JSON and atomically replace the destination file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = path + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(value, fh, indent=2, sort_keys=True)
            fh.write("\n")
        os.replace(tmp_path, path)
    finally:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError as exc:
            print(f"[updater] Could not remove temporary file {tmp_path}: {exc}")


def _write_installed_files_manifest(extracted, destination, protected_folders):
    """Atomically record the files shipped by the extracted release."""
    manifest = _build_installed_files_manifest(extracted, protected_folders)
    manifest_path = _metadata_path(destination, INSTALLED_FILES_MANIFEST)
    _write_json_atomically(manifest_path, manifest)


def _finish_file_update(extracted, destination, protected_folders, progress_callback=None):
    """Run best-effort stale-file cleanup and persist updater metadata."""
    try:
        pending = _remove_obsolete_files(
            extracted, destination, protected_folders, progress_callback
        )
        if pending is None:
            return
        pending_path = _metadata_path(destination, PENDING_CLEANUP)
        if pending["bootstrap_pending"] or pending["files"] or os.path.lexists(pending_path):
            _write_json_atomically(pending_path, pending)
    except Exception as exc:
        print(f"[updater] Obsolete-file cleanup failed; continuing update: {exc}")
        return
    try:
        _write_installed_files_manifest(extracted, destination, protected_folders)
    except Exception as exc:
        print(f"[updater] Could not write installed-files manifest: {exc}")


def _apply_update_files(
    extracted, destination, protected_folders, protected_files, progress_callback=None
):
    """Merge an extracted release and finish its cleanup bookkeeping."""
    _merge_overwrite(extracted, destination, protected_folders, protected_files)
    _finish_file_update(extracted, destination, protected_folders, progress_callback)


def _refresh_updater(destination, progress_callback=None):
    update_py_url = "https://raw.githubusercontent.com/Fuzzy-Team/Fuzzy-Macro/refs/heads/main/src/modules/misc/update.py"
    headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
    }
    _report_update_progress(progress_callback, 5, "Refreshing updater")
    response = requests.get(update_py_url, timeout=20, headers=headers)
    response.raise_for_status()

    target_update = os.path.join(destination, "src", "modules", "misc", "update.py")
    os.makedirs(os.path.dirname(target_update), exist_ok=True)
    tmp_path = target_update + ".tmp"
    try:
        with open(tmp_path, "w", encoding="utf-8") as fh:
            fh.write(response.text)
        os.replace(tmp_path, target_update)
    finally:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass


def _run_refreshed_updater(destination, entry_point, *args, **kwargs):
    """Refresh update.py and run its latest entry point in this update run.

    Return ``None`` when the current updater should continue as a safe
    fallback; otherwise return ``(True, result)`` from the refreshed updater.
    """
    global _UPDATER_HANDOFF_ACTIVE
    if _UPDATER_HANDOFF_ACTIVE:
        return None

    try:
        _refresh_updater(destination, kwargs.get("progress_callback"))
    except Exception as exc:
        print(f"[updater] Could not refresh updater; continuing with current version: {exc}")
        return None

    current_module = sys.modules.get(__name__)
    if current_module is None:
        return None

    try:
        _UPDATER_HANDOFF_ACTIVE = True
        cached_bytecode = getattr(current_module, "__cached__", None)
        if cached_bytecode and os.path.exists(cached_bytecode):
            try:
                os.remove(cached_bytecode)
            except OSError:
                # Reload can still validate the source itself; a read-only
                # bytecode cache should not prevent a normal update.
                pass
        importlib.invalidate_caches()
        refreshed_module = importlib.reload(current_module)

        # The refreshed entry point begins with the same handoff check.  Make
        # its refresh call a no-op so it proceeds directly with the newly
        # loaded implementation instead of fetching/reloading recursively.
        original_refresh = refreshed_module._refresh_updater
        refreshed_module._refresh_updater = lambda *unused_args, **unused_kwargs: None
        try:
            print("[updater] Running refreshed updater")
            return True, getattr(refreshed_module, entry_point)(*args, **kwargs)
        finally:
            refreshed_module._refresh_updater = original_refresh
    except Exception as exc:
        print(f"[updater] Could not reload refreshed updater; continuing with current version: {exc}")
        return None
    finally:
        _UPDATER_HANDOFF_ACTIVE = False


# Recursively copy from src to dst, overwriting files. Skip protected names.
def _merge_overwrite(src, dst, protected_folders, protected_files):
    for root, dirs, files in os.walk(src):
        rel_root = os.path.relpath(root, src)
        # compute destination root
        dest_root = os.path.join(dst, rel_root) if rel_root != "." else dst
        if not os.path.exists(dest_root):
            os.makedirs(dest_root, exist_ok=True)
        # filter dirs in-place to avoid descending into protected dirs
        # compare using relative paths so nested protected paths like
        # 'src/data' or 'data/user' are honored
        norm_protected = [os.path.normpath(p) for p in protected_folders]
        filtered = []
        for d in dirs:
            candidate = os.path.normpath(os.path.join(rel_root, d)) if rel_root != "." else os.path.normpath(d)
            if candidate not in norm_protected:
                filtered.append(d)
        dirs[:] = filtered
        for f in files:
            if f in protected_files:
                continue
            src_file = os.path.join(root, f)
            dest_file = os.path.join(dest_root, f)
            shutil.copy2(src_file, dest_file)


def _resolve_update_pattern_source(extracted):
    """Prefer shipped defaults/patterns; fall back to settings/patterns for older zips."""
    defaults_patterns = os.path.join(extracted, "settings", "defaults", "patterns")
    active_patterns = os.path.join(extracted, "settings", "patterns")
    if os.path.isdir(defaults_patterns):
        return defaults_patterns
    if os.path.isdir(active_patterns):
        return active_patterns
    return None


def _merge_patterns(src_patterns, dst_patterns, overwrite_exceptions=None):
    """
    Copy shipped patterns into the user's patterns folder.

    - New pattern files are added.
    - Existing user patterns are left alone (manual edits preserved).
    - Files in overwrite_exceptions are always replaced (built-in AI patterns).
    - Conflicting updates are written as name.newN.ext as a non-destructive fallback.
    """
    if not src_patterns or not os.path.isdir(src_patterns):
        return

    if overwrite_exceptions is None:
        overwrite_exceptions = PATTERN_OVERWRITE_EXCEPTIONS

    os.makedirs(dst_patterns, exist_ok=True)
    for root, dirs, files in os.walk(src_patterns):
        rel_root = os.path.relpath(root, src_patterns)
        dest_root = os.path.join(dst_patterns, rel_root) if rel_root != "." else dst_patterns
        os.makedirs(dest_root, exist_ok=True)
        for f in files:
            if f.endswith(".pyc") or f == "__pycache__":
                continue
            src_file = os.path.join(root, f)
            dest_file = os.path.join(dest_root, f)
            if f in overwrite_exceptions:
                try:
                    shutil.copy2(src_file, dest_file)
                except Exception:
                    pass
            elif not os.path.exists(dest_file):
                try:
                    shutil.copy2(src_file, dest_file)
                except Exception:
                    pass
            else:
                # create a non-destructive alternative name
                base, ext = os.path.splitext(f)
                suffix = 1
                while True:
                    new_name = f"{base}.new{suffix}{ext}"
                    new_path = os.path.join(dest_root, new_name)
                    if not os.path.exists(new_path):
                        try:
                            shutil.copy2(src_file, new_path)
                        except Exception:
                            pass
                        break
                    suffix += 1


# Create a zip backup of `destination`, excluding protected folders/files.
def _create_backup(destination, backup_path, protected_folders, protected_files):
    if os.path.exists(backup_path):
        try:
            os.remove(backup_path)
        except Exception:
            try:
                os.unlink(backup_path)
            except Exception:
                pass
    # Recordings are generated artifacts and can be many gigabytes. Including
    # them makes the updater appear stuck at 30% while it compresses videos.
    excluded_folders = set(protected_folders)
    excluded_folders.update({
        ".git",
        os.path.join("src", "data", "user", "fuzzy_ai_recordings"),
    })
    backup_abs = os.path.abspath(backup_path)

    with zipfile.ZipFile(backup_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(destination):
            # skip the backup file itself and src extraction folders
            rel_root = os.path.relpath(root, destination)
            if rel_root == ".":
                rl = ""
            else:
                rl = rel_root
            # Prune excluded trees before os.walk descends into them.
            dirs[:] = [
                d for d in dirs
                if not any(
                    (os.path.join(rl, d) if rl else d) == p
                    or (os.path.join(rl, d) if rl else d).startswith(p + os.sep)
                    for p in excluded_folders
                )
            ]
            for f in files:
                if f in protected_files:
                    continue
                absf = os.path.join(root, f)
                arcname = os.path.join(rl, f) if rl else f
                if os.path.abspath(absf) == backup_abs:
                    continue
                try:
                    zf.write(absf, arcname)
                except Exception:
                    pass


# Mark that a backup exists and should be deleted after one full macro launch.
def _mark_backup_pending(destination):
    try:
        with open(os.path.join(destination, ".backup_pending"), "w") as fh:
            fh.write("defer_once")
    except Exception:
        pass


# Public helper: delete backup if pending (call from macro run)
def delete_backup_if_pending(destination=None):
    import sys
    from modules.misc.messageBox import msgBoxOkCancel
    # Try both root and /src for marker and backup
    paths_to_check = []
    if destination is not None:
        paths_to_check.append(destination)
    cwd = os.getcwd()
    root = cwd.replace("/src", "")
    paths_to_check.extend([cwd, root])
    checked = set()
    for base in paths_to_check:
        if not base or base in checked:
            continue
        checked.add(base)
        marker = os.path.join(base, ".backup_pending")
        backup = os.path.join(base, "backup_macro.zip")
        try:
            if os.path.exists(marker) or os.path.exists(backup):
                if os.path.exists(marker):
                    try:
                        with open(marker, "r") as fh:
                            marker_state = fh.read().strip()
                    except Exception:
                        marker_state = ""

                    if marker_state == "defer_once":
                        with open(marker, "w") as fh:
                            fh.write("ready")
                        break

                prompt = "A backup from a previous update was found.\nDo you want to delete the backup now? (Recommended if the macro is working fine.)"
                response = msgBoxOkCancel("Delete Backup?", prompt)
                if response:
                    if os.path.exists(marker):
                        os.remove(marker)
                    if os.path.exists(backup):
                        if os.path.isdir(backup):
                            shutil.rmtree(backup)
                        else:
                            os.remove(backup)
                break
        except Exception as e:
            print(f"[delete_backup_if_pending] Error: {e}", file=sys.stderr)
            pass


def _discover_remote_version(remote_version_url, timeout=15):
    """Discover the latest non-prerelease tag from GitHub, falling back to
    the tags endpoint and finally to `remote_version_url` if all else fails.
    Returns the version string (without a leading 'v') or None on failure.
    """
    github_releases_api = "https://api.github.com/repos/Fuzzy-Team/Fuzzy-Macro/releases?per_page=100"
    github_tags_api = "https://api.github.com/repos/Fuzzy-Team/Fuzzy-Macro/tags?per_page=100"
    try:
        headers = {
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
            "Accept": "application/vnd.github.v3+json",
        }
        r = requests.get(github_releases_api, timeout=timeout, headers=headers)
        r.raise_for_status()
        releases = r.json()
        for rel in releases:
            if not rel.get("prerelease") and rel.get("tag_name"):
                return rel.get("tag_name").lstrip("v")
        # fallback to tags endpoint
        rt = requests.get(github_tags_api, timeout=timeout, headers=headers)
        rt.raise_for_status()
        tags = rt.json()
        if tags:
            return tags[0].get("name", "").lstrip("v")
    except Exception:
        pass
    # final fallback: read provided remote_version_url
    try:
        r = requests.get(remote_version_url, timeout=timeout, headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        })
        r.raise_for_status()
        rv = r.text.strip()
        return rv
    except Exception:
        return None


def update(t="main", update_channel="stable", progress_callback=None):
    """Install the latest release from the selected update channel."""
    _report_update_progress(progress_callback, 0, "Starting update")
    # Don't show the blocking "Updating..." dialog while merely checking
    # for updates. Show it only after we've determined that a newer
    # remote version exists (see below) so the user only confirms when
    # an actual update will be applied.
    # Important: preserve user data and profiles. Protect the patterns folder
    # during the generic overwrite, then handle pattern files with explicit
    # merge rules below so specific built-in patterns can be updated safely.
    protected_folders = [
        os.path.join("src", "data", "user"),
        os.path.join("src", "data", "models"),
        os.path.join("settings", "profiles"),
        os.path.join("settings", "patterns"),
    ]
    protected_files = [".git"]
    pattern_overwrite_exceptions = PATTERN_OVERWRITE_EXCEPTIONS
    destination = os.getcwd().replace("/src", "")

    refreshed_result = _run_refreshed_updater(
        destination,
        "update",
        t=t,
        update_channel=update_channel,
        progress_callback=progress_callback,
    )
    if refreshed_result is not None:
        return refreshed_result[1]

    # remote version URL and zip link
    import time
    # Use GitHub releases API with channel filtering
    github_releases_api = "https://api.github.com/repos/Fuzzy-Team/Fuzzy-Macro/releases?per_page=100"
    backup_path = os.path.join(destination, "backup_macro.zip")

    # read local version
    local_version = "0.0.0"
    local_version_path = os.path.join(destination, "src", "webapp", "version.txt")
    if not os.path.exists(local_version_path):
        local_version_path = os.path.join(destination, "version.txt")
    try:
        if os.path.exists(local_version_path):
            with open(local_version_path, "r") as fh:
                local_version = fh.read().strip()
    except Exception:
        local_version = "0.0.0"

    # Discover remote version using GitHub releases API with channel filtering
    headers = {
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
        "Accept": "application/vnd.github.v3+json",
    }
    
    remote_version = None
    try:
        _report_update_progress(progress_callback, 25, "Checking latest version")
        r = requests.get(github_releases_api, timeout=10, headers=headers)
        r.raise_for_status()
        releases = r.json()
        
        if releases:
            # Filter releases based on channel preference
            if update_channel == "beta":
                # Beta channel: accept any release (prerelease or stable)
                # Get the first one (most recent)
                if releases[0].get("tag_name"):
                    remote_version = releases[0].get("tag_name").lstrip("v")
            else:
                # Stable channel: only non-prerelease versions
                for rel in releases:
                    if not rel.get("prerelease") and rel.get("tag_name"):
                        remote_version = rel.get("tag_name").lstrip("v")
                        break
    except Exception:
        pass
    
    if not remote_version:
        _report_update_progress(progress_callback, 100, "Update failed: could not fetch remote version")
        msgBox("Update failed", "Could not fetch remote version. Update aborted.")
        return False

    # Construct zip link using the fetched remote_version
    zip_link = f"https://github.com/Fuzzy-Team/Fuzzy-Macro/archive/refs/tags/{remote_version}.zip"

    if not _is_remote_newer(local_version, remote_version):
        _report_update_progress(progress_callback, 100, "No update available")
        msgBox("Up to date", "No update available. Remote version is not newer.")
        return False

    # At this point we know an update is available — prompt the user to
    # start the update. This is intentionally shown after checking so
    # the dialog doesn't appear during the version check.
    msgBox("Update in progress", "Updating... Do not close terminal, press ok to start update.")

    # create a silent backup (overwrite previous backup) only after confirming
    # that an update will be applied.
    try:
        _report_update_progress(progress_callback, 30, "Creating backup")
        _create_backup(destination, backup_path, [], protected_files)
        _mark_backup_pending(destination)
    except Exception:
        pass

    # download zip
    try:
        _report_update_progress(progress_callback, 35, f"Downloading v{remote_version}")
        zipf = _download_update_zip(zip_link, progress_callback, 35, 65)
        _report_update_progress(progress_callback, 68, "Extracting update")
        zipf.extractall(destination)
    except Exception:
        _report_update_progress(progress_callback, 100, "Update failed: could not download or extract")
        msgBox("Update failed", "Could not download or extract update zip.")
        return False

    # find extracted folder (likely starts with 'Fuzzy-Macro')
    _report_update_progress(progress_callback, 72, "Locating extracted files")
    extracted = None
    for f in os.listdir(destination):
        if f.startswith("Fuzzy-Macro") and os.path.isdir(os.path.join(destination, f)):
            extracted = os.path.join(destination, f)
            break
    if not extracted:
        # fallback: try any new directory containing 'src'
        for f in os.listdir(destination):
            p = os.path.join(destination, f)
            if os.path.isdir(p) and os.path.exists(os.path.join(p, "src")):
                extracted = p
                break
    if not extracted:
        _report_update_progress(progress_callback, 100, "Update failed: extracted folder missing")
        msgBox("Update failed", "Could not locate extracted update folder.")
        return False

    # merge files, overwriting existing, but skip protected folders
    try:
        _report_update_progress(progress_callback, 78, "Applying update files")
        _apply_update_files(
            extracted, destination, protected_folders, protected_files, progress_callback
        )
    except Exception:
        _report_update_progress(progress_callback, 100, "Update failed: could not apply files")
        msgBox("Update failed", "Error while applying update files.")
        return False

    try:
        _report_update_progress(progress_callback, 84, "Checking AI models")
        from modules.misc.modelManager import ensure_supported_models
        ensure_supported_models()
    except Exception as e:
        print(f"[models] Could not check/download AI models: {e}")

    # Merge patterns from shipped defaults into the user's patterns folder.
    # settings/patterns is protected above so user edits survive the generic
    # overwrite; defaults/patterns is updated normally and is the catalog of
    # official patterns to add (without replacing existing user copies).
    try:
        _report_update_progress(progress_callback, 86, "Merging patterns")
        src_patterns = _resolve_update_pattern_source(extracted)
        dst_patterns = os.path.join(destination, "settings", "patterns")
        _merge_patterns(src_patterns, dst_patterns, pattern_overwrite_exceptions)
    except Exception:
        # non-fatal: don't interrupt whole update for pattern merge issues
        pass

    # Clean up `.newN` duplicates: if corresponding base file exists, remove
    # the `.newN` file; otherwise rename it to the base name (remove suffix).
    try:
        import re as _re
        if os.path.exists(dst_patterns):
            for root, dirs, files in os.walk(dst_patterns):
                for f in files:
                    m = _re.match(r"^(?P<base>.+?)\.new\d+(?P<ext>\..+)?$", f)
                    if not m:
                        continue
                    base = m.group('base')
                    ext = m.group('ext') or ''
                    candidate = base + ext
                    src_new = os.path.join(root, f)
                    target = os.path.join(root, candidate)
                    try:
                        if os.path.exists(target):
                            # base exists — remove the .new file
                            os.remove(src_new)
                        else:
                            # rename .newN -> base
                            os.replace(src_new, target)
                    except Exception:
                        pass
    except Exception:
        pass

    # cleanup the extracted folder
    try:
        _report_update_progress(progress_callback, 92, "Cleaning up update files")
        shutil.rmtree(extracted)
    except Exception:
        pass

    # ensure run_macro.command is executable if present
    run_macroPath = os.path.join(destination, "run_macro.command")
    if os.path.exists(run_macroPath):
        try:
            st = os.stat(run_macroPath)
            os.chmod(run_macroPath, st.st_mode | stat.S_IEXEC)
        except Exception:
            pass
    # Remove any leftover commit marker since this was a normal update
    try:
        webapp_commit = os.path.join(destination, "src", "webapp", "updated_commit.txt")
        if os.path.exists(webapp_commit):
            os.remove(webapp_commit)
    except Exception:
        pass
    # Attempt to run install dependencies script (non-blocking). Fail silently.
    try:
        _report_update_progress(progress_callback, 96, "Finishing update")
        install_script = os.path.join(destination, "install_dependencies.command")
        if os.path.exists(install_script):
            try:
                st = os.stat(install_script)
                os.chmod(install_script, st.st_mode | stat.S_IEXEC)
            except Exception:
                pass
            try:
                import subprocess
                # Detached, fully silent run: redirect stdin/stdout/stderr and
                # start a new session so the process isn't tied to this updater.
                subprocess.Popen(["sh", install_script],
                                 stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL,
                                 stdin=subprocess.DEVNULL,
                                 start_new_session=True,
                                 close_fds=True)
            except Exception:
                pass
    except Exception:
        pass

    _report_update_progress(progress_callback, 100, "Update complete")
    msgBox("Update success", "Update complete. You can now relaunch the macro")
    return True


def update_from_commit(commit_hash, progress_callback=None):
    """Update the macro from a specific commit hash (zip at /archive/<hash>.zip)."""
    _report_update_progress(progress_callback, 0, f"Starting update to {commit_hash}")
    protected_folders = [
        os.path.join("src", "data", "user"),
        os.path.join("src", "data", "models"),
        os.path.join("settings", "profiles"),
        os.path.join("settings", "patterns"),
    ]
    protected_files = [".git"]
    pattern_overwrite_exceptions = PATTERN_OVERWRITE_EXCEPTIONS
    destination = os.getcwd().replace("/src", "")

    refreshed_result = _run_refreshed_updater(
        destination,
        "update_from_commit",
        commit_hash=commit_hash,
        progress_callback=progress_callback,
    )
    if refreshed_result is not None:
        return refreshed_result[1]

    msgBox("Update in progress", f"Updating to commit {commit_hash}... Do not close terminal")

    remote_zip = f"https://github.com/Fuzzy-Team/Fuzzy-Macro/archive/{commit_hash}.zip"
    backup_path = os.path.join(destination, "backup_macro.zip")

    try:
        _report_update_progress(progress_callback, 15, "Creating backup")
        _create_backup(destination, backup_path, [], protected_files)
        _mark_backup_pending(destination)
    except Exception:
        pass

    # download zip for the commit
    try:
        _report_update_progress(progress_callback, 35, f"Downloading {commit_hash}")
        zipf = _download_update_zip(remote_zip, progress_callback, 35, 65)
        _report_update_progress(progress_callback, 68, "Extracting update")
        zipf.extractall(destination)
    except Exception:
        _report_update_progress(progress_callback, 100, "Update failed: could not download or extract")
        msgBox("Update failed", "Could not download or extract update zip for the specified commit.")
        return False

    # find extracted folder
    _report_update_progress(progress_callback, 72, "Locating extracted files")
    extracted = None
    for f in os.listdir(destination):
        if f.startswith("Fuzzy-Macro") and os.path.isdir(os.path.join(destination, f)):
            extracted = os.path.join(destination, f)
            break
    if not extracted:
        for f in os.listdir(destination):
            p = os.path.join(destination, f)
            if os.path.isdir(p) and os.path.exists(os.path.join(p, "src")):
                extracted = p
                break
    if not extracted:
        _report_update_progress(progress_callback, 100, "Update failed: extracted folder missing")
        msgBox("Update failed", "Could not locate extracted update folder.")
        return False

    try:
        _report_update_progress(progress_callback, 78, "Applying update files")
        _apply_update_files(
            extracted, destination, protected_folders, protected_files, progress_callback
        )
    except Exception:
        _report_update_progress(progress_callback, 100, "Update failed: could not apply files")
        msgBox("Update failed", "Error while applying update files.")
        return False

    try:
        _report_update_progress(progress_callback, 84, "Checking AI models")
        from modules.misc.modelManager import ensure_supported_models
        ensure_supported_models()
    except Exception as e:
        print(f"[models] Could not check/download AI models: {e}")

    # merge patterns similar to update()
    try:
        _report_update_progress(progress_callback, 86, "Merging patterns")
        src_patterns = _resolve_update_pattern_source(extracted)
        dst_patterns = os.path.join(destination, "settings", "patterns")
        _merge_patterns(src_patterns, dst_patterns, pattern_overwrite_exceptions)
    except Exception:
        pass

    # Clean up `.newN` duplicates created during merge: if corresponding
    # base file exists, remove the `.newN` file; otherwise rename it to
    # the base name (remove suffix).
    try:
        import re as _re
        if os.path.exists(dst_patterns):
            for root, dirs, files in os.walk(dst_patterns):
                for f in files:
                    m = _re.match(r"^(?P<base>.+?)\.new\d+(?P<ext>\..+)?$", f)
                    if not m:
                        continue
                    base = m.group('base')
                    ext = m.group('ext') or ''
                    candidate = base + ext
                    src_new = os.path.join(root, f)
                    target = os.path.join(root, candidate)
                    try:
                        if os.path.exists(target):
                            # base exists — remove the .new file
                            os.remove(src_new)
                        else:
                            # rename .newN -> base
                            os.replace(src_new, target)
                    except Exception:
                        pass
    except Exception:
        pass

    # cleanup the extracted folder
    try:
        _report_update_progress(progress_callback, 92, "Cleaning up update files")
        shutil.rmtree(extracted)
    except Exception:
        pass

    # ensure run_macro.command is executable if present
    run_macroPath = os.path.join(destination, "run_macro.command")
    if os.path.exists(run_macroPath):
        try:
            st = os.stat(run_macroPath)
            os.chmod(run_macroPath, st.st_mode | stat.S_IEXEC)
        except Exception:
            pass

    # Write a marker file in webapp so the UI can show the commit hash next to version
    try:
        webapp_commit = os.path.join(destination, "src", "webapp", "updated_commit.txt")
        with open(webapp_commit, "w") as fh:
            fh.write(commit_hash[:7])
    except Exception:
        pass
    # Attempt to run install dependencies script (non-blocking). Fail silently.
    try:
        _report_update_progress(progress_callback, 96, "Finishing update")
        install_script = os.path.join(destination, "install_dependencies.command")
        if os.path.exists(install_script):
            try:
                st = os.stat(install_script)
                os.chmod(install_script, st.st_mode | stat.S_IEXEC)
            except Exception:
                pass
            try:
                import subprocess
                # Detached, fully silent run
                subprocess.Popen(["sh", install_script],
                                 stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL,
                                 stdin=subprocess.DEVNULL,
                                 start_new_session=True,
                                 close_fds=True)
            except Exception:
                pass
    except Exception:
        pass

    _report_update_progress(progress_callback, 100, "Update complete")
    msgBox("Update success", "Update complete. You can now relaunch the macro")
    return True


def check_for_updates_silent(update_channel="stable"):
    """
    Silently check if an update is available without downloading or showing popups.
    Uses GitHub releases API to find the latest version based on the update channel.
    
    Args:
        update_channel: "stable" (non-prerelease) or "beta" (includes prerelease)
    
    Returns a dict with 'available' (bool), 'current_version' (str), and 'latest_version' (str).
    Returns None on error.
    """
    try:
        destination = os.getcwd().replace("/src", "")
        
        # Read local version
        local_version = "0.0.0"
        local_version_path = os.path.join(destination, "src", "webapp", "version.txt")
        if not os.path.exists(local_version_path):
            local_version_path = os.path.join(destination, "version.txt")
        try:
            if os.path.exists(local_version_path):
                with open(local_version_path, "r") as fh:
                    local_version = fh.read().strip()
        except Exception:
            local_version = "0.0.0"
        
        # Query GitHub releases API
        github_releases_api = "https://api.github.com/repos/Fuzzy-Team/Fuzzy-Macro/releases?per_page=100"
        headers = {
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
            "Accept": "application/vnd.github.v3+json",
        }
        
        r = requests.get(github_releases_api, timeout=10, headers=headers)
        r.raise_for_status()
        releases = r.json()
        
        if not releases:
            return None
        
        # Filter releases based on channel preference
        remote_version = None
        if update_channel == "beta":
            # Beta channel: accept any release (prerelease or stable)
            # Just get the first one (most recent)
            if releases[0].get("tag_name"):
                remote_version = releases[0].get("tag_name").lstrip("v")
        else:
            # Stable channel: only non-prerelease versions
            for rel in releases:
                if not rel.get("prerelease") and rel.get("tag_name"):
                    remote_version = rel.get("tag_name").lstrip("v")
                    break
        
        if not remote_version:
            return None
        
        # Check if remote is newer
        is_newer = _is_remote_newer(local_version, remote_version)
        
        return {
            'available': is_newer,
            'current_version': local_version,
            'latest_version': remote_version
        }
    except Exception as e:
        print(f"Error checking for updates: {e}")
        return None
