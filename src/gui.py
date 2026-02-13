import eel
import webbrowser
import modules.misc.settingsManager as settingsManager
import os
import modules.misc.update as updateModule
import sys
import ast
import json
import webbrowser
import time

eel.init('webapp')
run = None
_recent_logs = []
@eel.expose
def openLink(link):
    webbrowser.open(link, autoraise = True)
    
@eel.expose
def start():
    if run.value == 2: return #already running
    run.value = 1
    
@eel.expose
def stop():
    if run.value == 3: return #already stopped
    run.value = 0

@eel.expose
def pause():
    if run.value != 2: return #only pause if running
    run.value = 5  # 5 = pause request

@eel.expose
def resume():
    if run.value != 6: return #only resume if paused
    run.value = 2  # 2 = running (resume)

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
    
@eel.expose
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

@eel.expose
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


@eel.expose
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
def update():
    try:
        updated = updateModule.update()
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

def toggleStartStop():
    eel.toggleStartStop()

# Global variable to store run state
# 0=stop request, 1=start request, 2=running, 3=stopped, 4=disconnected, 5=pause request, 6=paused
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
