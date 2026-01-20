import stat
import os
import re
import requests
import zipfile
import shutil
from io import BytesIO
from modules.misc.messageBox import msgBox


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
    # numeric parts equal, compare letter where empty < any letter
    if lv[3] == rv[3]:
        return False
    if lv[3] == "":
        return True
    if rv[3] == "":
        return False
    return rv[3] > lv[3]


# Recursively copy from src to dst, overwriting files. Skip protected names.
def _merge_overwrite(src, dst, protected_folders, protected_files):
    for root, dirs, files in os.walk(src):
        rel_root = os.path.relpath(root, src)
        # compute destination root
        dest_root = os.path.join(dst, rel_root) if rel_root != "." else dst
        if not os.path.exists(dest_root):
            os.makedirs(dest_root, exist_ok=True)
        # filter dirs in-place to avoid descending into protected dirs
        dirs[:] = [d for d in dirs if d not in protected_folders]
        for f in files:
            if f in protected_files:
                continue
            src_file = os.path.join(root, f)
            dest_file = os.path.join(dest_root, f)
            shutil.copy2(src_file, dest_file)


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
    with zipfile.ZipFile(backup_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(destination):
            # skip the backup file itself and src extraction folders
            rel_root = os.path.relpath(root, destination)
            if rel_root == ".":
                rl = ""
            else:
                rl = rel_root
            # skip protected folders
            skip_root = False
            for p in protected_folders:
                if rl == p or rl.startswith(p + os.sep):
                    skip_root = True
                    break
            if skip_root:
                continue
            for f in files:
                if f in protected_files:
                    continue
                absf = os.path.join(root, f)
                arcname = os.path.join(rl, f) if rl else f
                if arcname == os.path.basename(backup_path):
                    continue
                try:
                    zf.write(absf, arcname)
                except Exception:
                    pass


# Mark that a backup exists and should be deleted on next macro run
def _mark_backup_pending(destination):
    try:
        with open(os.path.join(destination, ".backup_pending"), "w") as fh:
            fh.write("1")
    except Exception:
        pass


# Public helper: delete backup if pending (call from macro run)
def delete_backup_if_pending(destination=None):
    if destination is None:
        destination = os.getcwd().replace("/src", "")
    marker = os.path.join(destination, ".backup_pending")
    backup = os.path.join(destination, "backup_macro.zip")
    if os.path.exists(marker):
        try:
            if os.path.exists(backup):
                if os.path.isdir(backup):
                    shutil.rmtree(backup)
                else:
                    os.remove(backup)
        except Exception:
            pass
        try:
            os.remove(marker)
        except Exception:
            pass


def update(t="main"):
    msgBox("Update in progress", "Updating... Do not close terminal")
    # Important: always preserve `settings` and the VCS metadata and user data
    protected_folders = ["settings", os.path.join("data", "user"), "assets"]
    protected_files = [".git"]
    destination = os.getcwd().replace("/src", "")

    # remote version URL and zip link
    remote_version_url = "https://raw.githubusercontent.com/Fuzzy-Team/Fuzzy-Macro/refs/heads/main/src/webapp/version.txt"
    zip_link = "https://github.com/Fuzzy-Team/Fuzzy-Macro/archive/refs/heads/main.zip"
    backup_path = os.path.join(destination, "backup_macro.zip")

    # create a silent backup (overwrite previous backup)
    try:
        _create_backup(destination, backup_path, protected_folders, protected_files)
        _mark_backup_pending(destination)
    except Exception:
        pass

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

    # fetch remote version
    try:
        r = requests.get(remote_version_url, timeout=15)
        r.raise_for_status()
        remote_version = r.text.strip()
    except Exception:
        msgBox("Update failed", "Could not fetch remote version. Update aborted.")
        return False

    if not _is_remote_newer(local_version, remote_version):
        msgBox("Up to date", "No update available. Remote version is not newer.")
        return False

    # download zip
    try:
        req = requests.get(zip_link, timeout=60)
        req.raise_for_status()
        zipf = zipfile.ZipFile(BytesIO(req.content))
        zipf.extractall(destination)
    except Exception:
        msgBox("Update failed", "Could not download or extract update zip.")
        return False

    # find extracted folder (likely starts with 'Fuzzy-Macro')
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
        msgBox("Update failed", "Could not locate extracted update folder.")
        return False

    # merge files, overwriting existing, but skip protected folders
    try:
        _merge_overwrite(extracted, destination, protected_folders, protected_files)
    except Exception:
        msgBox("Update failed", "Error while applying update files.")
        return False

    # cleanup the extracted folder
    try:
        shutil.rmtree(extracted)
    except Exception:
        pass

    # ensure e_macro.command is executable if present
    e_macroPath = os.path.join(destination, "e_macro.command")
    if os.path.exists(e_macroPath):
        try:
            st = os.stat(e_macroPath)
            os.chmod(e_macroPath, st.st_mode | stat.S_IEXEC)
        except Exception:
            pass

    msgBox("Update success", "Update complete. You can now relaunch the macro")
    return True
