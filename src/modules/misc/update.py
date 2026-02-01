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


def update(t="main"):
    msgBox("Update in progress", "Updating... Do not close terminal")
    # Important: preserve user data and profiles. Protect pattern folder
    # during the generic overwrite so we can merge new/old patterns safely.
    protected_folders = [
        os.path.join("src", "data", "user"),
        os.path.join("settings", "profiles"),
        os.path.join("settings", "patterns"),
    ]
    protected_files = [".git"]
    destination = os.getcwd().replace("/src", "")

    # remote version URL and zip link
    # Attempt to fetch the latest `update.py` from upstream and replace the
    # local copy before performing the rest of the update. This allows bug
    # fixes in the updater itself to take effect immediately for this run.
    try:
        update_py_url = "https://raw.githubusercontent.com/Fuzzy-Team/Fuzzy-Macro/refs/heads/main/src/modules/misc/update.py"
        h = {
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        }
        r_up = requests.get(update_py_url, timeout=20, headers=h)
        r_up.raise_for_status()
        upd_code = r_up.text
        target_update = os.path.join(destination, "src", "modules", "misc", "update.py")
        target_dir = os.path.dirname(target_update)
        os.makedirs(target_dir, exist_ok=True)
        tmp_path = target_update + ".tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as fh:
                fh.write(upd_code)
            os.replace(tmp_path, target_update)
        except Exception:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
    except Exception:
        # non-fatal: continue with current updater if fetch fails
        pass

    # remote version URL and zip link
    import time
    # Add cache-busting query param to version URL
    remote_version_url = f"https://raw.githubusercontent.com/Fuzzy-Team/Fuzzy-Macro/refs/heads/main/src/webapp/version.txt?cb={int(time.time())}"
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


    # fetch remote version (disable caching)
    try:
        headers = {
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
        r = requests.get(remote_version_url, timeout=15, headers=headers)
        r.raise_for_status()
        remote_version = r.text.strip()
    except Exception:
        msgBox("Update failed", "Could not fetch remote version. Update aborted.")
        return False

    # Construct zip link using the fetched remote_version
    zip_link = f"https://github.com/Fuzzy-Team/Fuzzy-Macro/archive/refs/tags/{remote_version}.zip"

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

    # Merge patterns: combine files from extracted/settings/patterns with
    # existing settings/patterns in destination. We protected patterns above
    # so the generic merge didn't overwrite them. Here we perform a union
    # copy: copy new files, and if a filename collides, keep the existing
    # file and write the incoming file with a suffix to avoid data loss.
    try:
        src_patterns = os.path.join(extracted, "settings", "patterns")
        dst_patterns = os.path.join(destination, "settings", "patterns")
        if os.path.exists(src_patterns):
            for root, dirs, files in os.walk(src_patterns):
                rel_root = os.path.relpath(root, src_patterns)
                dest_root = os.path.join(dst_patterns, rel_root) if rel_root != "." else dst_patterns
                os.makedirs(dest_root, exist_ok=True)
                for f in files:
                    src_file = os.path.join(root, f)
                    dest_file = os.path.join(dest_root, f)
                    if not os.path.exists(dest_file):
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

    msgBox("Update success", "Update complete. You can now relaunch the macro")
    return True


def update_from_commit(commit_hash):
    """Update the macro from a specific commit hash (zip at /archive/<hash>.zip)."""
    msgBox("Update in progress", f"Updating to commit {commit_hash}... Do not close terminal")
    protected_folders = [
        os.path.join("src", "data", "user"),
        os.path.join("settings", "profiles"),
        os.path.join("settings", "patterns"),
    ]
    protected_files = [".git"]
    destination = os.getcwd().replace("/src", "")

    remote_zip = f"https://github.com/Fuzzy-Team/Fuzzy-Macro/archive/{commit_hash}.zip"
    backup_path = os.path.join(destination, "backup_macro.zip")

    try:
        _create_backup(destination, backup_path, protected_folders, protected_files)
        _mark_backup_pending(destination)
    except Exception:
        pass

    # download zip for the commit
    try:
        req = requests.get(remote_zip, timeout=60)
        req.raise_for_status()
        zipf = zipfile.ZipFile(BytesIO(req.content))
        zipf.extractall(destination)
    except Exception:
        msgBox("Update failed", "Could not download or extract update zip for the specified commit.")
        return False

    # find extracted folder
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
        msgBox("Update failed", "Could not locate extracted update folder.")
        return False

    try:
        _merge_overwrite(extracted, destination, protected_folders, protected_files)
    except Exception:
        msgBox("Update failed", "Error while applying update files.")
        return False

    # merge patterns similar to update()
    try:
        src_patterns = os.path.join(extracted, "settings", "patterns")
        dst_patterns = os.path.join(destination, "settings", "patterns")
        if os.path.exists(src_patterns):
            for root, dirs, files in os.walk(src_patterns):
                rel_root = os.path.relpath(root, src_patterns)
                dest_root = os.path.join(dst_patterns, rel_root) if rel_root != "." else dst_patterns
                os.makedirs(dest_root, exist_ok=True)
                for f in files:
                    src_file = os.path.join(root, f)
                    dest_file = os.path.join(dest_root, f)
                    if not os.path.exists(dest_file):
                        try:
                            shutil.copy2(src_file, dest_file)
                        except Exception:
                            pass
                    else:
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

    msgBox("Update success", "Update complete. You can now relaunch the macro")
    return True
