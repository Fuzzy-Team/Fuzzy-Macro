import eel
import webbrowser
import modules.misc.settingsManager as settingsManager
import os
from modules.misc.update import update as updateFunc
import sys
import ast
import json
import webbrowser
import time

eel.init('webapp')
run = None
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
    return [x.replace(".py","") for x in os.listdir("../settings/patterns") if ".py" in x]

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
    with open("./data/user/auto_planters.json", "r") as f:
        return json.load(f)

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
    }
    with open("./data/user/auto_planters.json", "w") as f:
        json.dump(data, f, indent=3)
    
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
        updated = updateFunc()
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
    settings = settingsManager.loadAllSettings()
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

def launch():

    pass
    
    try:
        eel.start('index.html', mode = "chrome", app_mode = True, block = False, cmdline_args=["--incognito", "--app=http://localhost:8000"])
    except EnvironmentError:
        try:
            eel.start('index.html', mode = "chrome-app", app_mode = True, block = False, cmdline_args=["--incognito", "--app=http://localhost:8000"])
        except EnvironmentError:
            print("Chrome/Chromium could not be found. Opening in default browser...")
            eel.start('index.html', block=False, mode=None)
            time.sleep(2)
            webbrowser.open("http://localhost:8000/", new=2)
