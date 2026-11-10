#update the screen user data
import pyautogui as pag
import os
import mss
import mss.darwin
mss.darwin.IMAGE_OPTIONS = 0
from ..misc import settingsManager

BASE_SCREEN_WIDTH = 2880
BASE_SCREEN_HEIGHT = 1800

screenPath = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../data/user/screen.txt'))


def _get_reference_scale(screen_data=None):
    if screen_data is None:
        screen_data = getScreenData()

    screen_width = screen_data.get("screen_width", BASE_SCREEN_WIDTH) or BASE_SCREEN_WIDTH
    screen_height = screen_data.get("screen_height", BASE_SCREEN_HEIGHT) or BASE_SCREEN_HEIGHT
    return (
        screen_width / BASE_SCREEN_WIDTH,
        screen_height / BASE_SCREEN_HEIGHT,
    )


def scaleX(value, screen_data=None):
    scale_x, _ = _get_reference_scale(screen_data)
    return int(round(value * scale_x))


def scaleY(value, screen_data=None):
    _, scale_y = _get_reference_scale(screen_data)
    return int(round(value * scale_y))


def setScreenData():
    wwd, whd = pag.size()
    screenData = {
        "display_type": "built-in",
        "screen_width": wwd,
        "screen_height": whd,
        "reference_width": BASE_SCREEN_WIDTH,
        "reference_height": BASE_SCREEN_HEIGHT,
        "x_scale": 1,
        "y_scale": 1,
        "y_multiplier": 1,
        "x_multiplier": 1,
        "y_length_multiplier": 1,
        "x_length_multiplier": 1
    }

    #for macs: check if its reina, set the screen width and height, set multipliers
    #get a screenshot. The size of the screenshot is the true screen size
    sct=mss.mss()
    region={'top':0,'left':0,'width':150,'height':150}
    shot=sct.grab(region)
    sw, sh = shot.width, shot.height
    if sw == 300: #check if retina (screenshot size is twice)
        screenData["screen_width"] *= 2
        screenData["screen_height"] *= 2
        screenData["display_type"] = "retina"
    ndisplay = "{}x{}".format(sw,sh)
    # Determine the true (physical) screen resolution using mss monitors
    sct = mss.mss()
    try:
        mon = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
        physical_w, physical_h = mon['width'], mon['height']
    except Exception:
        # fallback: grab a full-screen shot
        shot = sct.grab({'top': 0, 'left': 0, 'width': wwd, 'height': whd})
        physical_w, physical_h = shot.width, shot.height

    detected_resolution = f"{physical_w}x{physical_h}"

    # Normal retina detection for everything else
    if physical_w != wwd or physical_h != whd:
        screenData["screen_width"] = physical_w
        screenData["screen_height"] = physical_h
        screenData["display_type"] = "retina"
    else:
        screenData["screen_width"] = wwd
        screenData["screen_height"] = whd

    screenData["x_scale"], screenData["y_scale"] = _get_reference_scale(screenData)
    screenData["x_multiplier"] = BASE_SCREEN_WIDTH / screenData["screen_width"]
    screenData["y_multiplier"] = BASE_SCREEN_HEIGHT / screenData["screen_height"]
    screenData["x_length_multiplier"] = screenData["x_multiplier"]
    screenData["y_length_multiplier"] = screenData["y_multiplier"]

    #save the data
    os.makedirs(os.path.dirname(screenPath), exist_ok=True)
    settingsManager.saveDict(screenPath, screenData)

def getScreenData():
    # This module is imported before main.py gets a chance to refresh display
    # information. Recreate the file here when it has been removed so imports
    # such as modules.screen.screenshot do not fail at startup.
    if not os.path.exists(screenPath):
        setScreenData()
    return settingsManager.readSettingsFile(screenPath)
