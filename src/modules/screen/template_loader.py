import os
import cv2
import numpy as np
from modules.screen.screenData import getScreenData
from functools import lru_cache

def _read_image(path):
    # read image preserving alpha if present
    return cv2.imread(path, cv2.IMREAD_UNCHANGED)

@lru_cache(maxsize=256)
def load_template_for_display(path_without_ext):
    """
    path_without_ext: full path without the extension suffix, e.g. "./images/menu/honeybar"
    Behavior:
      - tries path + f"-{display_type}.png" first (e.g. honeybar-retina.png)
      - else tries path + ".png"
      - scales the chosen image by the display multi if required
    Returns: numpy array (BGR or BGRA) ready for OpenCV use
    """
    sd = getScreenData()
    display_type = sd.get("display_type", "")
    multi = 2 if display_type == "retina" else 1

    # likely filenames
    ext = ".png"
    retina_path = f"{path_without_ext}-{display_type}{ext}"
    base_path = f"{path_without_ext}{ext}"

    # pick file to load: prefer display-specific
    chosen = None
    if os.path.exists(retina_path):
        chosen = retina_path
    elif os.path.exists(base_path):
        chosen = base_path
    else:
        # try any existing variant
        for p in [retina_path, base_path]:
            if os.path.exists(p):
                chosen = p
                break
    if chosen is None:
        raise FileNotFoundError(f"No template found for {path_without_ext} (tried {retina_path} and {base_path})")

    img = _read_image(chosen)
    if img is None:
        raise IOError(f"Failed to read image {chosen}")

    # If chosen file is already the display-specific asset and display is retina, keep as-is.
    filename = os.path.basename(chosen)
    if display_type and f"-{display_type}" in filename:
        # If the asset matches display_type, return it directly (most accurate & fastest)
        return img

    # Otherwise scale based on the 'multi' (retina factor) if multi != 1
    if multi != 1:
        h, w = img.shape[:2]
        new_w = max(1, int(round(w * multi)))
        new_h = max(1, int(round(h * multi)))
        # Choose interpolation based on enlarging/reducing
        interp = cv2.INTER_LINEAR if multi > 1 else cv2.INTER_AREA
        resized = cv2.resize(img, (new_w, new_h), interpolation=interp)
        return resized

    return img
