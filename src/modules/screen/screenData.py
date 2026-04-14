#update the screen user data
import pyautogui as pag
import os
import mss
import mss.darwin
mss.darwin.IMAGE_OPTIONS = 0
from ..misc import settingsManager

BASE_SCREEN_WIDTH = 2880
BASE_SCREEN_HEIGHT = 1800

screenPath = os.path.join(settingsManager.getProjectRoot(), "src", "data", "user", "screen.txt")


def _valid_dimension_pair(width, height):
    return width and height and width > 0 and height > 0


def _normalize_dimensions(width, height):
    if _valid_dimension_pair(width, height):
        return width, height

    return BASE_SCREEN_WIDTH, BASE_SCREEN_HEIGHT


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


def scaleRegion(left, top, width, height, anchor_x="left", anchor_y="top", screen_data=None):
    if screen_data is None:
        screen_data = getScreenData()

    screen_width = screen_data.get("screen_width", BASE_SCREEN_WIDTH) or BASE_SCREEN_WIDTH
    screen_height = screen_data.get("screen_height", BASE_SCREEN_HEIGHT) or BASE_SCREEN_HEIGHT
    scaled_width = max(1, scaleX(width, screen_data))
    scaled_height = max(1, scaleY(height, screen_data))

    if anchor_x == "center":
        base_center_x = left + width / 2
        center_offset_x = base_center_x - (BASE_SCREEN_WIDTH / 2)
        scaled_center_x = (screen_width / 2) + (center_offset_x * screen_width / BASE_SCREEN_WIDTH)
        scaled_left = int(round(scaled_center_x - (scaled_width / 2)))
    elif anchor_x == "right":
        base_right_margin = BASE_SCREEN_WIDTH - (left + width)
        scaled_right_margin = scaleX(base_right_margin, screen_data)
        scaled_left = int(round(screen_width - scaled_right_margin - scaled_width))
    else:
        scaled_left = scaleX(left, screen_data)

    if anchor_y == "center":
        base_center_y = top + height / 2
        center_offset_y = base_center_y - (BASE_SCREEN_HEIGHT / 2)
        scaled_center_y = (screen_height / 2) + (center_offset_y * screen_height / BASE_SCREEN_HEIGHT)
        scaled_top = int(round(scaled_center_y - (scaled_height / 2)))
    elif anchor_y == "bottom":
        base_bottom_margin = BASE_SCREEN_HEIGHT - (top + height)
        scaled_bottom_margin = scaleY(base_bottom_margin, screen_data)
        scaled_top = int(round(screen_height - scaled_bottom_margin - scaled_height))
    else:
        scaled_top = scaleY(top, screen_data)

    scaled_left = max(0, min(int(screen_width - scaled_width), scaled_left))
    scaled_top = max(0, min(int(screen_height - scaled_height), scaled_top))
    return (scaled_left, scaled_top, scaled_width, scaled_height)


def setScreenData():
    wwd, whd = pag.size()
    wwd, whd = _normalize_dimensions(wwd, whd)
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

    # For Macs, mss gives the true physical screen size, but it can fail before
    # Screen Recording permission is granted. Fall back so the GUI can still open.
    try:
        sct = mss.mss()
        region = {'top': 0, 'left': 0, 'width': 150, 'height': 150}
        shot = sct.grab(region)
        sw, sh = shot.width, shot.height
        if sw == 300:
            screenData["screen_width"] *= 2
            screenData["screen_height"] *= 2
            screenData["display_type"] = "retina"

        try:
            mon = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
            physical_w, physical_h = mon['width'], mon['height']
        except Exception:
            shot = sct.grab({'top': 0, 'left': 0, 'width': wwd, 'height': whd})
            physical_w, physical_h = shot.width, shot.height
    except Exception as e:
        print(f"Warning: Could not capture screen data, using display size fallback: {e}")
        physical_w, physical_h = wwd, whd
    physical_w, physical_h = _normalize_dimensions(physical_w, physical_h)

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
    settingsManager.saveDict(screenPath, screenData)

def getScreenData():
    return settingsManager.readSettingsFile(screenPath)
