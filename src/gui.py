import webbrowser
import modules.misc.settingsManager as settingsManager
import os
import modules.misc.update as updateModule
import sys
import ast
import json
import webbrowser
import time
import threading
import platform
import importlib.util

try:
    from AppKit import NSApplication, NSImage
except Exception:
    NSApplication = None
    NSImage = None

try:
    import webview
except ImportError:
    webview = None

run = None
_recent_logs = []
_frontend_window = None
_frontend_ready = False
_shutdown_requested = False


def _get_save_dialog_type():
    """Return the save dialog constant across pywebview versions."""
    file_dialog = getattr(webview, "FileDialog", None)
    if file_dialog is not None and hasattr(file_dialog, "SAVE"):
        return file_dialog.SAVE
    return getattr(webview, "SAVE_DIALOG", None)


def _normalize_dialog_path(dialog_result):
    """Normalize pywebview file dialog result to a single string path."""
    if not dialog_result:
        return None
    if isinstance(dialog_result, (list, tuple)):
        if len(dialog_result) == 0:
            return None
        return dialog_result[0]
    return dialog_result


def _module_available(module_name):
    """Best-effort module availability check without importing the module."""
    try:
        return importlib.util.find_spec(module_name) is not None
    except Exception:
        return False


_keybind_recording_state = {
    "start": False,
    "pause": False,
    "stop": False,
}
_keybind_recording_lock = threading.Lock()


def _dispatch_frontend(event_name, *args, await_result=False):
    if _frontend_window is None or not _frontend_ready:
        return None

    script = (
        "window.AppBridge && window.AppBridge.dispatch("
        f"{json.dumps(event_name)}, ...{json.dumps(list(args))})"
    )
    return _frontend_window.evaluate_js(script)


def isShutdownRequested():
    return _shutdown_requested


def ensureSettingsSaved():
    """Best-effort: persist any settings/state to disk on close."""
    try:
        # Persist the selected profile
        settingsManager.saveCurrentProfile()
    except Exception:
        pass

    try:
        # Load the current profile settings and write them back to ensure
        # any in-memory defaults or migrations are persisted.
        profile_settings = settingsManager.loadSettings()
        settingsManager.saveDictProfileSettings(profile_settings)
    except Exception:
        pass

    try:
        # Ensure fields sync between profile and general settings
        settingsManager.initializeFieldSync()
    except Exception:
        pass


def closeWindow():
    global _shutdown_requested
    _shutdown_requested = True
    # Ensure settings are persisted before the window is destroyed
    try:
        ensureSettingsSaved()
    except Exception:
        pass
    if _frontend_window is not None:
        try:
            _frontend_window.destroy()
        except Exception:
            pass
    return True


def openLink(link):
    webbrowser.open(link, autoraise = True)
    
def start():
    if run.value == 2: return #already running
    run.value = 1
    
def stop():
    if run.value == 3: return #already stopped
    run.value = 0

def pause():
    if run.value != 2: return #only pause if running
    run.value = 6  # 6 = paused

def resume():
    if run.value != 6: return #only resume if paused
    run.value = 2  # 2 = running (resume)

def getPatterns():
    patterns = []
    try:
        for x in os.listdir("../settings/patterns"):
            if x.endswith('.py') or x.endswith('.ahk'):
                patterns.append(os.path.splitext(x)[0])
    except Exception:
        # folder may not exist yet
        pass
    return patterns

def importPatterns(patterns):
    """Import pattern files sent from the frontend.
    `patterns` should be a list of dicts: {"name": "filename.py", "content": "..."}
    Writes files into ../settings/patterns/ and returns a report dict.
    """
    results = {"saved": [], "errors": []}
    target_dir = os.path.join(os.path.dirname(__file__), "..", "settings", "patterns")
    # normalize path
    target_dir = os.path.normpath(target_dir)
    try:
        os.makedirs(target_dir, exist_ok=True)
    except Exception as e:
        results["errors"].append(f"Could not ensure patterns dir: {e}")
        return results

    for p in patterns:
        try:
            name = p.get("name") or p.get("filename")
            content = p.get("content", "")
            if not name:
                results["errors"].append("Missing filename for one of the uploads")
                continue
            # sanitize name to avoid directory traversal
            name = os.path.basename(name)
            # normalize extension: allow .py and .ahk, default to .py
            root, ext = os.path.splitext(name)
            ext = ext.lower() or '.py'
            if ext not in ('.py', '.ahk'):
                ext = '.py'
            name = root + ext
            dest_path = os.path.join(target_dir, name)
            with open(dest_path, "w", encoding="utf-8") as f:
                f.write(content)
            results["saved"].append(name)
        except Exception as e:
            results["errors"].append(f"{name}: {e}")

    return results

def clearManualPlanters():
    settingsManager.clearFile("./data/user/manualplanters.txt")

def getManualPlanterData():
    with open("./data/user/manualplanters.txt", "r") as f:
        planterDataRaw = f.read()
    if planterDataRaw.strip():
        return ast.literal_eval(planterDataRaw)
    else: 
        return ""
    
def getAutoPlanterData():
    try:
        with open("./data/user/auto_planters.json", "r") as f:
            return json.load(f)
    except Exception:
        # Return sensible default if file missing or invalid
        return {
            "planters": [
                {"planter": "", "nectar": "", "field": "", "harvest_time": 0, "nectar_est_percent": 0},
                {"planter": "", "nectar": "", "field": "", "harvest_time": 0, "nectar_est_percent": 0},
                {"planter": "", "nectar": "", "field": "", "harvest_time": 0, "nectar_est_percent": 0}
            ],
            "nectar_last_field": {
                "comforting": "",
                "refreshing": "",
                "satisfying": "",
                "motivating": "",
                "invigorating": ""
            },
            "gather": False
        }

def clearAutoPlanters():
    data = {
        "planters": [
            {
                "planter": "",
                "nectar": "",
                "field": "",
                "harvest_time": 0,
                "nectar_est_percent": 0
            },
            {
                "planter": "",
                "nectar": "",
                "field": "",
                "harvest_time": 0,
                "nectar_est_percent": 0
            },
            {
                "planter": "",
                "nectar": "",
                "field": "",
                "harvest_time": 0,
                "nectar_est_percent": 0
            }
        ],
        "nectar_last_field": {
            "comforting": "",
            "refreshing": "",
            "satisfying": "",
            "motivating": "",
            "invigorating": ""
        }
        ,
        "gather": False
    }
    with open("./data/user/auto_planters.json", "w") as f:
        json.dump(data, f, indent=3)


def setAutoPlanterGather(val):
    """Set the global 'gather' flag in data/user/auto_planters.json"""
    try:
        try:
            with open("./data/user/auto_planters.json", "r") as f:
                current = json.load(f)
        except Exception:
            current = None

        if not current:
            current = getAutoPlanterData()

        current["gather"] = bool(val)

        with open("./data/user/auto_planters.json", "w") as f:
            json.dump(current, f, indent=3)
        return True
    except Exception:
        return False

def resetManualPlanterTimer(index):
    """Reset a specific manual planter timer by index (0-2)"""
    try:
        with open("./data/user/manualplanters.txt", "r") as f:
            planterDataRaw = f.read()
        
        if not planterDataRaw.strip():
            return False
        
        planterData = ast.literal_eval(planterDataRaw)
        
        # Check if index is valid
        if index < 0 or index >= len(planterData.get("planters", [])):
            return False
        
        # Clear the specific planter
        if "planters" in planterData and len(planterData["planters"]) > index:
            planterData["planters"][index] = ""
        if "fields" in planterData and len(planterData["fields"]) > index:
            planterData["fields"][index] = ""
        if "harvestTimes" in planterData and len(planterData["harvestTimes"]) > index:
            planterData["harvestTimes"][index] = 0
        
        with open("./data/user/manualplanters.txt", "w") as f:
            f.write(str(planterData))
        
        return True
    except Exception as e:
        print(f"Error resetting manual planter {index}: {e}")
        return False

def resetAutoPlanterTimer(index):
    """Reset a specific auto planter timer by index (0-2)"""
    try:
        with open("./data/user/auto_planters.json", "r") as f:
            data = json.load(f)
        
        # Check if index is valid
        if index < 0 or index >= len(data.get("planters", [])):
            return False
        
        # Clear the specific planter
        data["planters"][index] = {
            "planter": "",
            "nectar": "",
            "field": "",
            "harvest_time": 0,
            "nectar_est_percent": 0
        }
        
        with open("./data/user/auto_planters.json", "w") as f:
            json.dump(data, f, indent=3)
        
        return True
    except Exception as e:
        print(f"Error resetting auto planter {index}: {e}")
        return False
    
def clearBlender():
    blenderData = {
        "item": 1,
        "collectTime": 0
    }
    with open("data/user/blender.txt", "w") as f:
        f.write(str(blenderData))
    f.close()

def clearAFB():
    AFBData = {
        "AFB_dice_cd": 0,
        "AFB_glitter_cd": 0,
        "AFB_limit": 0
    }

    # convert to format like in timings.txt
    data_str = "\n".join([f"{key}={value}" for key, value in AFBData.items()])

    with open("data/user/AFB.txt", "w") as f:
        f.write(data_str)

def resetFieldToDefault(field_name):
    """Reset a field's settings to the default values"""
    try:
        # Load default field settings
        with open("data/default_settings/fields.txt", "r") as f:
            default_fields = ast.literal_eval(f.read())

        # Get the default settings for the specified field
        if field_name in default_fields:
            default_settings = default_fields[field_name]
            # Save the default settings for this field
            settingsManager.saveField(field_name, default_settings)
            return True
        else:
            print(f"Warning: Field '{field_name}' not found in default settings")
            return False
    except Exception as e:
        print(f"Error resetting field to default: {e}")
        return False

def exportFieldSettings(field_name):
    """Export field settings as JSON string"""
    try:
        return settingsManager.exportFieldSettings(field_name)
    except Exception as e:
        print(f"Error exporting field settings: {e}")
        return None


def exportDebugZip(profile_name=None):
    """Create a zip containing the exported profile, recent logs, and system info. Returns (True, base64zip, filename) or (False, error)."""
    try:
        import base64
        import io
        import zipfile
        import platform

        # Decide profile to export
        if not profile_name:
            profile_name = settingsManager.getCurrentProfile()

        # Try to get exported profile JSON
        try:
            exported = settingsManager.exportProfile(profile_name)
        except Exception as e:
            exported = (False, f"Export profile error: {e}")

        mem = io.BytesIO()
        with zipfile.ZipFile(mem, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            # Add profile export
            try:
                if isinstance(exported, (list, tuple)) and exported and exported[0] is True:
                    _, json_content, json_fname = exported
                    zf.writestr(json_fname, json_content.encode("utf-8"))
                else:
                    # include error text
                    err = exported[1] if isinstance(exported, (list, tuple)) and len(exported) > 1 else str(exported)
                    zf.writestr("profile_export_error.txt", str(err).encode("utf-8"))
            except Exception as e:
                zf.writestr("profile_export_error.txt", f"Failed to include profile: {e}".encode("utf-8"))

            # Add recent logs from in-memory store
            try:
                logs = list(_recent_logs) if _recent_logs else []
                log_lines = []
                for entry in logs:
                    try:
                        # entries may be dicts
                        if isinstance(entry, dict):
                            log_lines.append(json.dumps(entry, ensure_ascii=False))
                        else:
                            log_lines.append(str(entry))
                    except Exception:
                        log_lines.append(str(entry))
                zf.writestr("logs.txt", ("\n".join(log_lines)).encode("utf-8"))
            except Exception as e:
                zf.writestr("logs.txt", f"Failed to collect logs: {e}".encode("utf-8"))

            # Add system info
            try:
                machine = platform.machine() or "unknown"
                plat = platform.platform() or "unknown"
                pyv = platform.python_version()
                # include fuller python info (version string and executable path)
                py_full = sys.version.replace('\n', ' ')
                py_exec = sys.executable or "unknown"
                macrov = settingsManager.getMacroVersion()
                # Determine chip label
                mlow = machine.lower()
                if "x86" in mlow or "amd64" in mlow:
                    chip = "Intel"
                elif "arm" in mlow or "aarch" in mlow:
                    chip = "Apple Silicon"
                else:
                    chip = machine

                sysinfo = (
                    f"platform={plat}\n"
                    f"machine={machine}\n"
                    f"chip={chip}\n"
                    f"python_version={pyv}\n"
                    f"python_full_version={py_full}\n"
                    f"python_executable={py_exec}\n"
                    f"macro_version={macrov}\n"
                )
                zf.writestr("system_info.txt", sysinfo.encode("utf-8"))
            except Exception as e:
                zf.writestr("system_info.txt", f"Failed to gather system info: {e}".encode("utf-8"))

        mem.seek(0)
        b64 = base64.b64encode(mem.read()).decode("ascii")
        filename = f"fuzzy_debug_{int(time.time())}.zip"
        return True, b64, filename
    except Exception as e:
        return False, str(e)


def exportFieldSettingsWithDialog(field_name):
    """Export field settings and show native save dialog to save JSON file"""
    try:
        json_content = settingsManager.exportFieldSettings(field_name)
        # Suggest filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        suggested = f"{field_name}_settings_{timestamp}.json"

        if _frontend_window is None:
            return False, "Window not available"

        save_dialog_type = _get_save_dialog_type()
        if save_dialog_type is None:
            return False, "Installed pywebview version does not expose a save file dialog API"
        save_path = _frontend_window.create_file_dialog(
            dialog_type=save_dialog_type,
            save_filename=suggested,
            file_types=("JSON Files (*.json)",),
        )
        save_path = _normalize_dialog_path(save_path)

        if not save_path:
            return False, "Export cancelled"

        if not save_path.endswith('.json'):
            save_path += '.json'

        with open(save_path, 'w', encoding='utf-8') as f:
            f.write(json_content)

        # Provide basic metadata to the frontend
        try:
            parsed = json.loads(json_content)
            metadata = parsed.get('metadata', {}) if isinstance(parsed, dict) else {}
        except Exception:
            metadata = {}

        return True, f"Saved to {os.path.basename(save_path)}", metadata
    except Exception as e:
        return False, f"Failed to export field settings: {str(e)}"


def exportDebugZipWithDialog(profile_name=None):
    """Create debug zip (reuse exportDebugZip) and show save dialog to save zip file"""
    try:
        res = exportDebugZip(profile_name)
        if not res or res[0] is not True:
            # res may be (False, error)
            err = res[1] if isinstance(res, (list, tuple)) and len(res) > 1 else str(res)
            return False, err

        # res == (True, b64, filename)
        _, b64, filename = res

        if _frontend_window is None:
            return False, "Window not available"

        save_dialog_type = _get_save_dialog_type()
        if save_dialog_type is None:
            return False, "Installed pywebview version does not expose a save file dialog API"
        save_path = _frontend_window.create_file_dialog(
            dialog_type=save_dialog_type,
            save_filename=filename,
            file_types=("Zip Files (*.zip)",),
        )
        save_path = _normalize_dialog_path(save_path)

        if not save_path:
            return False, "Export cancelled"

        if not save_path.endswith('.zip'):
            save_path += '.zip'

        import base64
        data = base64.b64decode(b64)
        with open(save_path, 'wb') as f:
            f.write(data)

        return True, f"Saved to {os.path.basename(save_path)}"
    except Exception as e:
        return False, f"Failed to export debug zip: {str(e)}"


def importFieldSettings(field_name, json_settings):
    """Import field settings from JSON string"""
    try:
        return settingsManager.importFieldSettings(field_name, json_settings)
    except Exception as e:
        print(f"Error importing field settings: {e}")
        return False

def exportProfileWithDialog(profile_name):
    """Export a profile using native save dialog"""
    try:
        # Get the export data from settingsManager
        result = settingsManager.exportProfile(profile_name)
        
        if not result[0]:
            return False, result[1]
        
        success, json_content, suggested_filename = result
        
        # Show save file dialog
        if _frontend_window is None:
            return False, "Window not available"
        
        save_dialog_type = _get_save_dialog_type()
        if save_dialog_type is None:
            return False, "Installed pywebview version does not expose a save file dialog API"
        save_path = _frontend_window.create_file_dialog(
            dialog_type=save_dialog_type,
            save_filename=suggested_filename,
            file_types=('JSON Files (*.json)',)
        )
        save_path = _normalize_dialog_path(save_path)
        
        if not save_path:
            # User cancelled
            return False, "Export cancelled"
        
        # Ensure .json extension
        if not save_path.endswith('.json'):
            save_path += '.json'
        
        # Write the file
        with open(save_path, 'w', encoding='utf-8') as f:
            f.write(json_content)
        
        return True, f"Profile exported to {os.path.basename(save_path)}"
        
    except Exception as e:
        return False, f"Failed to export profile: {str(e)}"
        
def getMacroVersion():
    """Get the macro version from version.txt"""
    return settingsManager.getMacroVersion()

def update():
    try:
        updated = updateModule.update()
    except Exception:
        updated = False
    if updated:
        if _frontend_window is not None:
            try:
                ensureSettingsSaved()
            except Exception:
                pass
            _frontend_window.destroy()
        sys.exit()
    else:
        try:
            _dispatch_frontend("updateButtonReset", await_result=True)
        except Exception:
            pass
    return


def updateFromHash(commit_hash):
    try:
        updated = updateModule.update_from_commit(commit_hash)
    except Exception:
        updated = False
    if updated:
        if _frontend_window is not None:
            try:
                ensureSettingsSaved()
            except Exception:
                pass
            _frontend_window.destroy()
        sys.exit()
    else:
        try:
            _dispatch_frontend("updateButtonReset", await_result=True)
        except Exception:
            pass
    return


def updateMacroMode():
    _dispatch_frontend("updateMacroMode")


def setKeybindRecordingState(element_id, is_recording):
    key_name = str(element_id or "").replace("_keybind", "")
    if key_name not in _keybind_recording_state:
        return False

    with _keybind_recording_lock:
        _keybind_recording_state[key_name] = bool(is_recording)
    return True


def getKeybindRecordingState():
    with _keybind_recording_lock:
        return dict(_keybind_recording_state)


def isAnyKeybindRecording():
    with _keybind_recording_lock:
        return any(_keybind_recording_state.values())

def log(time = "", msg = "", color = ""):
    _dispatch_frontend("log", time, msg, color)

def updateGUI():
    # Load settings, ensure Brown Bear keys exist, then load into frontend
    settings = settingsManager.loadAllSettings()

    # Ensure any missing default settings are present in the profile.
    try:
        default_path = os.path.join(settingsManager.getDefaultSettingsPath(), "settings.txt")
        defaults = settingsManager.readSettingsFile(default_path)

        # Add any top-level default keys missing from the loaded settings
        for k, v in defaults.items():
            if k not in settings:
                try:
                    settingsManager.saveProfileSetting(k, v)
                    settings[k] = v
                except Exception:
                    # ignore individual save failures
                    pass

        # Ensure task_priority_order contains all default priority entries
        try:
            default_order = defaults.get("task_priority_order", []) or []
            tlist = settings.get("task_priority_order", []) or []
            changed = False
            for item in default_order:
                if item not in tlist:
                    tlist.append(item)
                    changed = True
            if changed:
                settingsManager.saveProfileSetting("task_priority_order", tlist)
                settings["task_priority_order"] = tlist
        except Exception:
            pass
    except Exception:
        pass


def _set_dock_icon_if_available():
    """Set the macOS Dock icon at runtime if AppKit is available.

    icon_path may be a .icns or a PNG; returns True if set, False otherwise.
    """
    try:
        if platform.system() != "Darwin":
            return False
        if NSApplication is None or NSImage is None:
            return False
        if not os.path.exists(os.path.join(os.path.dirname(__file__), "webapp", "assets", "general", "appicon.png")):
            return False
        app = NSApplication.sharedApplication()
        img = NSImage.alloc().initWithContentsOfFile_(os.path.join(os.path.dirname(__file__), "webapp", "assets", "general", "appicon.png"))
        if not img:
            return False
        app.setApplicationIconImage_(img)
        return True
    except Exception as e:
        print(f"Failed to set dock icon: {e}")
        return False

    _dispatch_frontend("loadInputs", settings)
    _dispatch_frontend("loadTasks")
    try:
        _dispatch_frontend("refreshCurrentTabContent", await_result=True)
    except Exception:
        pass

def toggleStartStop():
    _dispatch_frontend("toggleStartStop")

# Global variable to store run state
# 0=stop request, 1=start request, 2=running, 3=stopped, 4=disconnected, 6=paused
_run_state = 3

def setRunState(state):
    global _run_state
    _run_state = state

def getRunState():
    return _run_state

def setRecentLogs(logs):
    global _recent_logs
    _recent_logs = logs

def getRecentLogs():
    # Return as a list of dicts for the frontend
    return list(_recent_logs)

def clearRecentLogs():
    global _recent_logs
    # Clear the shared list
    try:
        # If it's a multiprocessing.Manager.list, we use del or clear()
        if hasattr(_recent_logs, 'clear'):
            _recent_logs.clear()
        else:
            del _recent_logs[:]
    except Exception as e:
        print(f"Error clearing logs: {e}")
        # Fallback to re-initializing if clear fails
        _recent_logs = []

def _build_gui_api():
    api_methods = {
        "closeWindow": closeWindow,
        "openLink": openLink,
        "start": start,
        "stop": stop,
        "pause": pause,
        "resume": resume,
        "getPatterns": getPatterns,
        "importPatterns": importPatterns,
        "clearManualPlanters": clearManualPlanters,
        "getManualPlanterData": getManualPlanterData,
        "getAutoPlanterData": getAutoPlanterData,
        "clearAutoPlanters": clearAutoPlanters,
        "setAutoPlanterGather": setAutoPlanterGather,
        "resetManualPlanterTimer": resetManualPlanterTimer,
        "resetAutoPlanterTimer": resetAutoPlanterTimer,
        "clearBlender": clearBlender,
        "clearAFB": clearAFB,
        "resetFieldToDefault": resetFieldToDefault,
        "exportFieldSettings": exportFieldSettings,
        "exportFieldSettingsWithDialog": exportFieldSettingsWithDialog,
        "exportDebugZip": exportDebugZip,
        "exportDebugZipWithDialog": exportDebugZipWithDialog,
        "importFieldSettings": importFieldSettings,
        "getMacroVersion": getMacroVersion,
        "update": update,
        "updateFromHash": updateFromHash,
        "loadFields": settingsManager.loadFields,
        "saveField": settingsManager.saveField,
        "loadSettings": settingsManager.loadSettings,
        "loadAllSettings": settingsManager.loadAllSettings,
        "saveProfileSetting": settingsManager.saveProfileSetting,
        "saveGeneralSetting": settingsManager.saveGeneralSetting,
        "saveDictProfileSettings": settingsManager.saveDictProfileSettings,
        "initializeFieldSync": settingsManager.initializeFieldSync,
        "listProfiles": settingsManager.listProfiles,
        "getCurrentProfile": settingsManager.getCurrentProfile,
        "switchProfile": settingsManager.switchProfile,
        "createProfile": settingsManager.createProfile,
        "deleteProfile": settingsManager.deleteProfile,
        "renameProfile": settingsManager.renameProfile,
        "duplicateProfile": settingsManager.duplicateProfile,
        "exportProfile": settingsManager.exportProfile,
        "exportProfileWithDialog": exportProfileWithDialog,
        "importProfile": settingsManager.importProfile,
        "importProfileContent": settingsManager.importProfileContent,
        "getRunState": getRunState,
        "setRunState": setRunState,
        "getRecentLogs": getRecentLogs,
        "clearRecentLogs": clearRecentLogs,
        "setKeybindRecordingState": setKeybindRecordingState,
        "getKeybindRecordingState": getKeybindRecordingState,
    }

    def _make_method(func):
        def method(self, *args, **kwargs):
            return func(*args, **kwargs)
        method.__name__ = func.__name__
        return method

    api_class = type("GuiApi", (), {})
    for name, fn in api_methods.items():
        setattr(api_class, name, _make_method(fn))
    return api_class()


def launch(runtime_callback=None, runtime_args=(), keyboard_listener_callback=None):
    global _frontend_window, _frontend_ready, _shutdown_requested

    if webview is None:
        raise RuntimeError(
            "pywebview is not installed. Install dependencies before launching the GUI."
        )

    index_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "webapp", "index.html")
    )
    _frontend_ready = False
    _shutdown_requested = False

    _set_dock_icon_if_available()
    preferred_gui = None

    if platform.system() == "Darwin":
        has_pyqt5 = _module_available("PyQt5")
        has_webkit = _module_available("WebKit")

        # Prefer Qt on macOS when available for broader pywebview compatibility.
        if has_pyqt5:
            preferred_gui = "qt"
        elif not has_webkit:
            raise RuntimeError(
                "No supported pywebview backend found on macOS. "
                "Missing both PyQt5 and WebKit. "
                "Re-run install_dependencies.command or install one backend manually: "
                "pip install 'pywebview[qt]' PyQt5==5.15.9 "
                "or pip install pyobjc-core pyobjc-framework-Cocoa pyobjc-framework-WebKit"
            )

    try:
        # Build kwargs in a version-safe way: older pywebview releases reject
        # newer parameters such as `text_select`.
        import inspect

        create_window_fn = webview.create_window
        kwargs = {
            "width": 1312,
            "height": 1022,
            "text_select": True,
        }
        if preferred_gui:
            kwargs["gui"] = preferred_gui

        signature_kwargs = None
        try:
            sig = inspect.signature(create_window_fn)
            params = sig.parameters
            accepts_var_kw = any(
                p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()
            )

            if "js_api" in params or accepts_var_kw:
                kwargs["js_api"] = _build_gui_api()

            if not accepts_var_kw:
                signature_kwargs = {k: v for k, v in kwargs.items() if k in params}
            else:
                signature_kwargs = kwargs
        except Exception:
            # If signature inspection fails, try the full kwargs and rely on
            # TypeError fallback below to remove unsupported keys.
            signature_kwargs = kwargs

        # Retry once without a reported unexpected keyword argument.
        active_kwargs = dict(signature_kwargs)
        for _ in range(2):
            try:
                _frontend_window = create_window_fn("Fuzzy Macro", index_path, **active_kwargs)
                break
            except TypeError as exc:
                msg = str(exc)
                marker = "unexpected keyword argument "
                if marker in msg:
                    bad_key = msg.split(marker, 1)[1].strip().strip("'\"")
                    if bad_key in active_kwargs:
                        active_kwargs.pop(bad_key, None)
                        continue
                raise
    except Exception as exc:
        # Some pywebview backends can fail to initialize on certain platforms
        # (notably on Windows when WebView2/runtime or other backends are missing).
        # Provide a clear message and fall back to opening the UI in the
        # system browser so the user still has access to the web frontend.
        print(f"pywebview.create_window failed: {exc}")
        if platform.system() == "Windows":
            print(
                "Windows detected: ensure Microsoft Edge WebView2 runtime is installed"
            )
            print(
                "Or install a supported pywebview backend (cef, qt) and the required dependencies."
            )
            raise RuntimeError(
                "Failed to initialize pywebview."
                " On Windows, this often means the WebView2 runtime is missing."
                " Please ensure it's installed and try again."
            ) from exc
        elif platform.system() == "Darwin":
            # On macOS the default Cocoa/WebKit backend can be incompatible
            # with older macOS versions. Provide actionable guidance so users
            # on macOS 10.12+ can install an alternative backend.
            print(
                "macOS detected: pywebview failed to initialize."
            )
            print(
                "On older macOS releases (10.12+), the default Cocoa backend may be incompatible."
            )
            print(
                "Try installing the Qt backend: pip install pywebview[qt] PyQt5==5.15.9"
            )
            print(
                "Alternatively install a CEF backend (cefpython3) or update macOS/Python as needed."
            )
            raise RuntimeError(
                "Failed to initialize pywebview on macOS. "
                "See above for suggested backend installation commands."
            ) from exc

    listener_started = {"value": False}

    # If a keyboard listener callback was provided, start it now on the
    # main thread (required on macOS). Keep the on_shown handler as a
    # fallback for backends that only expose the shown event on the main
    # thread.
    if keyboard_listener_callback and not listener_started["value"]:
        try:
            keyboard_listener_callback()
            listener_started["value"] = True
            print("Keyboard listener started on main thread during launch")
        except Exception as exc:
            print(f"Failed to start keyboard listener during launch: {exc}")

    def on_loaded(window):
        global _frontend_ready
        _frontend_ready = True
        try:
            updateGUI()
        except Exception:
            pass

    def on_closed(*_args):
        global _frontend_ready, _frontend_window, _shutdown_requested
        _frontend_ready = False
        _shutdown_requested = True
        # Persist settings on close (best-effort)
        try:
            ensureSettingsSaved()
        except Exception:
            pass
        _frontend_window = None

    def on_shown(*_args):
        if keyboard_listener_callback and not listener_started["value"]:
            listener_started["value"] = True
            try:
                keyboard_listener_callback()
                print("Keyboard listener started successfully")
            except Exception as exc:
                print(f"Failed to start keyboard listener after GUI launch: {exc}")

    _frontend_window.events.loaded += on_loaded
    _frontend_window.events.closed += on_closed
    _frontend_window.events.shown += on_shown

    start_kwargs = {"http_server": True}
    if runtime_callback is not None:
        start_kwargs["func"] = runtime_callback
        if runtime_args:
            start_kwargs["args"] = runtime_args

    # On macOS we install the Qt backend for better compatibility across
    # older OS versions and pywebview releases.
    if preferred_gui:
        start_kwargs["gui"] = preferred_gui

    try:
        webview.start(**start_kwargs)
    except TypeError as exc:
        # Fallback for pywebview versions that do not accept `gui`.
        if "gui" in start_kwargs and "gui" in str(exc):
            start_kwargs.pop("gui", None)
            webview.start(**start_kwargs)
        else:
            raise
