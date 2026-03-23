import eel
import webbrowser
import modules.misc.settingsManager as settingsManager
import os
import modules.misc.update as updateModule
import modules.controls.mouse as mouseControl
import sys
import ast
import json
import webbrowser
import time
import threading
from modules.submacros.autoGiftedBasicBee import AutoGiftedBasicBeeRunner

eel.init('webapp')
run = None
_recent_logs = []
_auto_gifted_basic_bee_runner = AutoGiftedBasicBeeRunner()


class AutoClickerRunner:
    def __init__(self):
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread = None
        self._interval_ms = 100
        self._status = self._fresh_status()

    def _fresh_status(self):
        return {
            "running": False,
            "state": "idle",
            "message": "Ready. Stop it with the macro's configured stop hotkey.",
            "interval_ms": self._interval_ms,
        }

    def get_status(self):
        with self._lock:
            return dict(self._status)

    def is_active(self):
        with self._lock:
            return bool(
                (self._thread and self._thread.is_alive())
                or self._status.get("running")
                or self._status.get("state") == "stopping"
            )

    def _update_status(self, **kwargs):
        with self._lock:
            self._status.update(kwargs)

    def start(self, interval_ms=100, run_state=3):
        try:
            interval_ms = int(interval_ms or 100)
        except Exception:
            interval_ms = 100
        interval_ms = max(10, interval_ms)

        thread_to_join = None
        with self._lock:
            if self._thread and not self._thread.is_alive():
                self._thread = None
            elif self._thread and self._stop_event.is_set():
                thread_to_join = self._thread
            elif self._thread and self._thread.is_alive():
                return {"ok": False, "message": "The tool is already running."}
            if run_state != 3:
                return {"ok": False, "message": "Stop the macro before starting this tool."}

        if thread_to_join:
            thread_to_join.join(timeout=0.3)

        with self._lock:
            if self._thread and self._thread.is_alive():
                return {"ok": False, "message": "The tool is still stopping. Try again in a moment."}
            if run_state != 3:
                return {"ok": False, "message": "Stop the macro before starting this tool."}
            self._stop_event.clear()
            self._interval_ms = interval_ms
            self._status = self._fresh_status()
            self._status.update(
                {
                    "running": True,
                    "state": "running",
                    "message": "Auto clicker running. Stop it with the macro's configured stop hotkey.",
                    "interval_ms": self._interval_ms,
                }
            )
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

        return {"ok": True, "message": "Auto clicker started."}

    def stop(self):
        self._stop_event.set()
        self._update_status(
            running=False,
            state="stopping",
            message="Stopping auto clicker.",
        )
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=0.3)
        return {"ok": True, "message": "Auto clicker stop requested."}

    def _run(self):
        try:
            interval_seconds = self._interval_ms / 1000.0
            while not self._stop_event.is_set():
                mouseControl.fastClick()
                if self._stop_event.wait(interval_seconds):
                    break
        except Exception as exc:
            self._update_status(
                running=False,
                state="finished",
                message=str(exc),
            )
        finally:
            with self._lock:
                self._thread = None
                if self._status.get("state") != "finished" or self._status.get("running"):
                    self._status.update(
                        {
                            "running": False,
                            "state": "idle",
                            "message": "Ready. Stop it with the macro's configured stop hotkey.",
                            "interval_ms": self._interval_ms,
                        }
                    )


_auto_clicker_runner = AutoClickerRunner()
@eel.expose
def openLink(link):
    webbrowser.open(link, autoraise = True)
    
@eel.expose
def start():
    if run.value == 2: return #already running
    if isAnyToolRunning():
        return {"ok": False, "message": "Stop the running tool before starting the macro."}
    run.value = 1
    return {"ok": True}
    
@eel.expose
def stop():
    if run.value == 3: return #already stopped
    run.value = 0
    return {"ok": True}

@eel.expose
def pause():
    if run.value != 2: return #only pause if running
    run.value = 6  # 6 = paused
    return {"ok": True}

@eel.expose
def resume():
    if run.value != 6: return #only resume if paused
    run.value = 2  # 2 = running (resume)
    return {"ok": True}

@eel.expose
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


@eel.expose
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

@eel.expose
def clearManualPlanters():
    settingsManager.clearFile("./data/user/manualplanters.txt")

@eel.expose
def getManualPlanterData():
    with open("./data/user/manualplanters.txt", "r") as f:
        planterDataRaw = f.read()
    if planterDataRaw.strip():
        return ast.literal_eval(planterDataRaw)
    else: 
        return ""

def emptyAutoPlanterSlot():
    return {
        "planter": "",
        "nectar": "",
        "field": "",
        "harvest_time": 0,
        "nectar_est_percent": 0,
        "placed_time": 0,
        "grow_duration": 0,
        "natural_grow_duration": 0
    }

def emptyAutoPlanterFieldDegradation():
    return {
        field: {
            "hours": 0.0,
            "updated_at": 0.0
        }
        for field in [
            "dandelion",
            "bamboo",
            "pine tree",
            "mushroom",
            "spider",
            "stump",
            "rose",
            "sunflower",
            "pineapple",
            "pumpkin",
            "blue flower",
            "strawberry",
            "coconut",
            "clover",
            "cactus",
            "mountain top",
            "pepper"
        ]
    }

def defaultAutoPlanterData():
    return {
        "planters": [
            emptyAutoPlanterSlot(),
            emptyAutoPlanterSlot(),
            emptyAutoPlanterSlot()
        ],
        "nectar_last_field": {
            "comforting": "",
            "refreshing": "",
            "satisfying": "",
            "motivating": "",
            "invigorating": ""
        },
        "gather": False,
        "field_degradation": emptyAutoPlanterFieldDegradation()
    }

def normalizeAutoPlanterData(data):
    normalized = defaultAutoPlanterData()
    if not isinstance(data, dict):
        return normalized

    for key in ("gather",):
        if key in data:
            normalized[key] = data[key]

    if isinstance(data.get("nectar_last_field"), dict):
        for nectar, value in data["nectar_last_field"].items():
            if nectar in normalized["nectar_last_field"]:
                normalized["nectar_last_field"][nectar] = value

    if isinstance(data.get("field_degradation"), dict):
        for field, value in data["field_degradation"].items():
            if field in normalized["field_degradation"] and isinstance(value, dict):
                normalized["field_degradation"][field]["hours"] = value.get("hours", value.get("value", 0.0) or 0.0)
                normalized["field_degradation"][field]["updated_at"] = value.get("updated_at", 0.0) or 0.0

    if isinstance(data.get("planters"), list):
        normalized["planters"] = []
        for planter in data["planters"][:3]:
            slot = emptyAutoPlanterSlot()
            if isinstance(planter, dict):
                for key in slot:
                    slot[key] = planter.get(key, slot[key])
            normalized["planters"].append(slot)
        while len(normalized["planters"]) < 3:
            normalized["planters"].append(emptyAutoPlanterSlot())

    return normalized
    
@eel.expose
def getAutoPlanterData():
    try:
        with open("./data/user/auto_planters.json", "r") as f:
            return normalizeAutoPlanterData(json.load(f))
    except Exception:
        return defaultAutoPlanterData()

@eel.expose
def clearAutoPlanters():
    data = defaultAutoPlanterData()
    with open("./data/user/auto_planters.json", "w") as f:
        json.dump(data, f, indent=3)


@eel.expose
def setAutoPlanterGather(val):
    """Set the global 'gather' flag in data/user/auto_planters.json"""
    try:
        try:
            with open("./data/user/auto_planters.json", "r") as f:
                current = normalizeAutoPlanterData(json.load(f))
        except Exception:
            current = None

        if not current:
            current = defaultAutoPlanterData()

        current["gather"] = bool(val)

        with open("./data/user/auto_planters.json", "w") as f:
            json.dump(current, f, indent=3)
        return True
    except Exception:
        return False

@eel.expose
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

@eel.expose
def resetAutoPlanterTimer(index):
    """Reset a specific auto planter timer by index (0-2)"""
    try:
        with open("./data/user/auto_planters.json", "r") as f:
            data = normalizeAutoPlanterData(json.load(f))
        
        # Check if index is valid
        if index < 0 or index >= len(data.get("planters", [])):
            return False
        
        # Clear the specific planter
        data["planters"][index] = emptyAutoPlanterSlot()
        
        with open("./data/user/auto_planters.json", "w") as f:
            json.dump(data, f, indent=3)
        
        return True
    except Exception as e:
        print(f"Error resetting auto planter {index}: {e}")
        return False
    
@eel.expose
def clearBlender():
    blenderData = {
        "item": 1,
        "collectTime": 0
    }
    with open("data/user/blender.txt", "w") as f:
        f.write(str(blenderData))
    f.close()

@eel.expose
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

@eel.expose
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

@eel.expose
def exportFieldSettings(field_name):
    """Export field settings as JSON string"""
    try:
        return settingsManager.exportFieldSettings(field_name)
    except Exception as e:
        print(f"Error exporting field settings: {e}")
        return None


@eel.expose
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

@eel.expose
def importFieldSettings(field_name, json_settings):
    """Import field settings from JSON string"""
    try:
        return settingsManager.importFieldSettings(field_name, json_settings)
    except Exception as e:
        print(f"Error importing field settings: {e}")
        return False
        
@eel.expose
def getMacroVersion():
    """Get the macro version from version.txt"""
    return settingsManager.getMacroVersion()

@eel.expose
def autoClickerClick():
    """Perform a single fast left click for the tools tab auto clicker."""
    try:
        mouseControl.fastClick()
        return True
    except Exception:
        return False

@eel.expose
def startAutoClickerTool(interval_ms=100):
    return _auto_clicker_runner.start(interval_ms, getRunState())

@eel.expose
def stopAutoClickerTool():
    return _auto_clicker_runner.stop()

@eel.expose
def getAutoClickerStatus():
    return _auto_clicker_runner.get_status()

@eel.expose
def startAutoGiftedBasicBeeTool(capture_delay_seconds=3, pause_settings=None):
    return _auto_gifted_basic_bee_runner.start(capture_delay_seconds, getRunState(), pause_settings)

@eel.expose
def stopAutoGiftedBasicBeeTool():
    return _auto_gifted_basic_bee_runner.stop()

@eel.expose
def getAutoGiftedBasicBeeStatus():
    return _auto_gifted_basic_bee_runner.get_status()

@eel.expose
def isAnyToolRunning():
    return _auto_clicker_runner.is_active() or _auto_gifted_basic_bee_runner.is_active()

@eel.expose
def stopAllTools():
    results = {
        "auto_clicker": stopAutoClickerTool(),
        "auto_gifted_basic_bee": stopAutoGiftedBasicBeeTool(),
    }
    return {"ok": True, "results": results}

@eel.expose
def update():
    try:
        # Get the update channel preference
        generalsettings_path = os.path.join(settingsManager.getProfilePath(), "generalsettings.txt")
        settings = settingsManager.readSettingsFile(generalsettings_path)
        update_channel = settings.get("update_channel", "stable")
        
        updated = updateModule.update(update_channel=update_channel)
    except Exception:
        updated = False
    if updated:
        eel.closeWindow()
        sys.exit()
    else:
        try:
            eel.updateButtonReset()()
        except Exception:
            pass
    return


@eel.expose
def updateFromHash(commit_hash):
    try:
        updated = updateModule.update_from_commit(commit_hash)
    except Exception:
        updated = False
    if updated:
        eel.closeWindow()
        sys.exit()
    else:
        try:
            eel.updateButtonReset()()
        except Exception:
            pass
    return

@eel.expose
def checkForUpdates():
    """Check for updates silently and return update information"""
    try:
        # Get the update channel preference
        generalsettings_path = os.path.join(settingsManager.getProfilePath(), "generalsettings.txt")
        settings = settingsManager.readSettingsFile(generalsettings_path)
        update_channel = settings.get("update_channel", "stable")
        
        update_info = updateModule.check_for_updates_silent(update_channel)
        return update_info
    except Exception as e:
        print(f"Error checking for updates: {e}")
        return None

@eel.expose
def disableAutoUpdateCheck():
    """Disable automatic update checking by saving preference to generalsettings"""
    try:
        settingsManager.saveGeneralSetting("auto_update_check_disabled", True)
        return True
    except Exception as e:
        print(f"Error disabling auto update check: {e}")
        return False

@eel.expose
def getAutoUpdateCheckDisabled():
    """Check if automatic update checking is disabled"""
    try:
        generalsettings_path = os.path.join(settingsManager.getProfilePath(), "generalsettings.txt")
        settings = settingsManager.readSettingsFile(generalsettings_path)
        return settings.get("auto_update_check_disabled", False)
    except Exception:
        return False

def log(time = "", msg = "", color = ""):
    eel.log(time, msg, color)

eel.expose(settingsManager.loadFields)
eel.expose(settingsManager.saveField) 
eel.expose(settingsManager.loadSettings)
eel.expose(settingsManager.loadAllSettings)
eel.expose(settingsManager.saveProfileSetting)
eel.expose(settingsManager.saveGeneralSetting)
eel.expose(settingsManager.saveDictProfileSettings)
eel.expose(settingsManager.initializeFieldSync)

# Profile management functions
eel.expose(settingsManager.listProfiles)
eel.expose(settingsManager.getCurrentProfile)
eel.expose(settingsManager.switchProfile)
eel.expose(settingsManager.createProfile)
eel.expose(settingsManager.deleteProfile)
eel.expose(settingsManager.renameProfile)
eel.expose(settingsManager.duplicateProfile)
eel.expose(settingsManager.exportProfile)
eel.expose(settingsManager.importProfile)
eel.expose(settingsManager.importProfileContent)

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

    eel.loadInputs(settings)
    eel.loadTasks()
    try:
        eel.refreshCurrentTabContent()()
    except Exception:
        pass

def toggleStartStop():
    eel.toggleStartStop()

# Global variable to store run state
# 0=stop request, 1=start request, 2=running, 3=stopped, 4=disconnected, 6=paused
_run_state = 3

def setRunState(state):
    global _run_state
    _run_state = state

def getRunState():
    return _run_state

# Expose functions to eel
eel.expose(getRunState)
eel.expose(setRunState)

def setRecentLogs(logs):
    global _recent_logs
    _recent_logs = logs

@eel.expose
def getRecentLogs():
    # Return as a list of dicts for the frontend
    return list(_recent_logs)

@eel.expose
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

def launch():

    import socket
    def get_free_port(start_port=8000, max_tries=100):
        port = start_port
        for _ in range(max_tries):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.bind(("localhost", port))
                    return port
                except OSError:
                    port += 1
        raise RuntimeError(f"No free port found in range {start_port}-{port}")

    port = get_free_port(8000, 100)
    port_url = f"http://localhost:{port}"

    # Ensure important functions are exposed to the frontend before eel starts
    try:
        eel.expose(getRecentLogs)
    except Exception:
        # ignore if already exposed or if exposure fails at import time
        pass

    try:
        eel.start('index.html', mode = "chrome", app_mode = True, block = False, port=port, cmdline_args=["--incognito", f"--app={port_url}"])
    except EnvironmentError:
        try:
            eel.start('index.html', mode = "chrome-app", app_mode = True, block = False, port=port, cmdline_args=["--incognito", f"--app={port_url}"])
        except EnvironmentError:
            print("Chrome/Chromium could not be found. Opening in default browser...")
            eel.start('index.html', block=False, mode=None, port=port)
            time.sleep(2)
            webbrowser.open(f"{port_url}/", new=2)
