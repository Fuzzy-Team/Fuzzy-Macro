import cv2
from modules.screen.screenshot import mssScreenshot, mssScreenshotNP
import numpy as np
import time
from functools import lru_cache
from modules.screen.template_loader import load_template_for_display
from modules.screen.screenData import getScreenData

class TemplateTooLargeError(Exception):
    def __init__(self, template_size, image_size):
        self.template_size = template_size
        self.image_size = image_size
        super().__init__(f"Template size {template_size} is larger than image size {image_size}")

def templateMatch(smallImg, bigImg):
    if smallImg.shape[0] > bigImg.shape[0] or smallImg.shape[1] > bigImg.shape[1]:
        raise TemplateTooLargeError(
            template_size=(smallImg.shape[1], smallImg.shape[0]),  # (width, height)
            image_size=(bigImg.shape[1], bigImg.shape[0])          # (width, height)
        )
    res = cv2.matchTemplate(bigImg, smallImg, cv2.TM_CCOEFF_NORMED)
    return cv2.minMaxLoc(res)

# helpers for safe matching / conversions
def _to_uint8(img):
    if img is None:
        return None
    if img.dtype != np.uint8:
        try:
            img = img.astype(np.uint8)
        except Exception:
            return None
    return img

def _ensure_channel_compat(template, image):
    """
    Ensure template and image have matching channel counts for matchTemplate.
    Returns (template, image) possibly converted.
    """
    if template is None or image is None:
        return template, image

    # if template grayscale and image BGR -> convert template to BGR
    if template.ndim == 2 and image.ndim == 3:
        template = cv2.cvtColor(template, cv2.COLOR_GRAY2BGR)
    # if template BGR and image grayscale -> convert image to BGR
    if template.ndim == 3 and image.ndim == 2:
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)

    return template, image

# helper cache for resized templates loaded from disk

@lru_cache(maxsize=128)
def _cached_resized_from_path(path_base, scale_key, need_alpha):
    """
    Return a resized template loaded from `path_base`.
    - path_base: string without extension (matching load_template_for_display convention)
    - scale_key: int, e.g. int(scale * 1000)
    - need_alpha: bool, whether to preserve alpha channel (True) or convert BGRA->BGR (False)
    """
    try:
        scale = scale_key / 1000.0
        img = load_template_for_display(path_base)  # ensures display-specific asset selection
    except Exception:
        return None

    if img is None:
        return None

    # if alpha present but not needed, convert to BGR
    if not need_alpha and img.ndim == 3 and img.shape[2] == 4:
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

    h, w = img.shape[:2]
    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))

    interp = cv2.INTER_LINEAR if scale > 1 else cv2.INTER_AREA
    try:
        resized = cv2.resize(img, (new_w, new_h), interpolation=interp)
    except Exception:
        return None
    return resized


@lru_cache(maxsize=128)
def _cached_resized_mask_from_path(path_base, scale_key):
    """
    Return a binary single-channel mask (0/255) resized from `path_base`.
    - Extract alpha if present, otherwise convert to gray then threshold.
    - Use INTER_NEAREST to keep mask crisp.
    """
    try:
        scale = scale_key / 1000.0
        img = load_template_for_display(path_base)
    except Exception:
        return None

    if img is None:
        return None

    # extract mask: prefer alpha channel if present
    if img.ndim == 3 and img.shape[2] == 4:
        mask = img[..., 3]
    elif img.ndim == 3:
        mask = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        mask = img

    h, w = mask.shape[:2]
    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))

    try:
        resized = cv2.resize(mask, (new_w, new_h), interpolation=cv2.INTER_NEAREST)
        _, bin_mask = cv2.threshold(resized, 0, 255, cv2.THRESH_BINARY)
    except Exception:
        return None
    return bin_mask

def locateImageOnScreen(target, x, y, w, h, threshold=0, scales=None, return_scale=False, resize_interp=cv2.INTER_AREA, early_exit_thresh=0.995):
    """
    Scale-aware locateImageOnScreen replacement.

    - `target` may be:
        * a numpy image (BGR/BGRA) already loaded, or
        * a path string like "./images/menu/honeybar" or "./images/menu/honeybar.png".
          When a path string is given, the loader will prefer display-specific assets
          (e.g. honeybar-retina.png) and cache reads/resizes.
    - `scales`: optional iterable of scale factors to try (e.g. [1.0, 2.0, 0.95, 1.05]).
      If None, the function builds a small list including the display "multi".
    - Returns (max_val, max_loc) or (max_val, max_loc, scale) if return_scale True.
    - Returns None when no match reaches `threshold`.
    """
    # capture screen region (same as before)
    screen = mssScreenshot(x, y, w, h)
    screen = cv2.cvtColor(np.array(screen), cv2.COLOR_RGB2BGR)
    screen = _to_uint8(screen)
    if screen is None:
        return None

    # If target is a string path, use the loader which prefers display-specific assets and caches results.
    is_path = isinstance(target, str)
    base = None
    if is_path:
        # allow target with extension or without
        base = target
        if base.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.webp')):
            base = base.rsplit('.', 1)[0]
        try:
            img_target = load_template_for_display(base)
        except Exception:
            return None
        if img_target is None:
            return None
        # For non-masked matching we can drop alpha channel now so template and screen match (3 channels)
        if img_target.ndim == 3 and img_target.shape[2] == 4:
            img_target = cv2.cvtColor(img_target, cv2.COLOR_BGRA2BGR)
    else:
        img_target = target

    # Validate template shape
    try:
        t_h, t_w = img_target.shape[:2]
    except Exception:
        return None

    # Build default scales if not provided
    if scales is None:
        sd = getScreenData()
        multi = 2 if sd.get("display_type") == "retina" else 1
        # include 1.0, multi, and reciprocal scales (handles retina asset on non-retina screen)
        candidates = {1.0, multi, 1.0/multi}
        neighbors = [0.95, 1.05]
        for c in list(candidates):
            for n in neighbors:
                candidates.add(round(c*n, 3))
        scales = sorted(candidates, reverse=True)

    best_val = -1.0
    best_loc = None
    best_scale = None

    # If the chosen template file already matches display_type and no scaling needed,
    # try a quick direct match first (saves time).
    if is_path:
        try:
            # prepare types
            tt, ss = _ensure_channel_compat(_to_uint8(img_target), screen)
            if tt is None or ss is None:
                raise Exception("Invalid images for direct match")
            _, val, _, loc = templateMatch(tt, ss)
            if val > best_val:
                best_val, best_loc, best_scale = val, loc, 1.0
                if best_val >= early_exit_thresh and best_val >= threshold:
                    return (best_val, best_loc) if not return_scale else (best_val, best_loc, best_scale)
        except TemplateTooLargeError:
            # if template is larger than screen, we'll try scaled-down variants below
            pass
        except Exception:
            # ignore other direct-match errors, proceed to scaled attempts
            pass

    # Try the list of scales (resizing the template as needed)
    for scale in scales:
        new_w = max(1, int(round(t_w * scale)))
        new_h = max(1, int(round(t_h * scale)))

        # Skip if resized template is larger than search area
        if new_h > screen.shape[0] or new_w > screen.shape[1]:
            continue

        if is_path:
            scale_key = int(round(scale * 1000))
            resized = _cached_resized_from_path(base, scale_key, need_alpha=False)
            if resized is None:
                continue
        else:
            try:
                resized = cv2.resize(img_target, (new_w, new_h), interpolation=resize_interp)
            except Exception:
                continue

        # ensure types and channels
        resized = _to_uint8(resized)
        if resized is None:
            continue
        tt, ss = _ensure_channel_compat(resized, screen)
        if tt is None or ss is None:
            continue

        try:
            _, max_val, _, max_loc = templateMatch(tt, ss)
        except TemplateTooLargeError:
            continue
        except Exception:
            continue

        if max_val > best_val:
            best_val = max_val
            best_loc = max_loc
            best_scale = scale

        if best_val >= early_exit_thresh:
            break

    if best_val < threshold:
        return None

    if return_scale:
        return (best_val, best_loc, best_scale)
    return (best_val, best_loc)

# used for locating templates with transparency
# this is done by template matching with the gray color space
def _to_gray(img):
    if img is None:
        return None
    if img.ndim == 3 and img.shape[2] == 4:
        return cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)
    if img.ndim == 3 and img.shape[2] == 3:
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    if img.ndim == 2:
        return img
    return None

def locateTransparentImage(target, screen, threshold):
    screen_gray = _to_gray(screen)
    target_gray = _to_gray(target)
    if screen_gray is None or target_gray is None:
        return None
    try:
        _, max_val, _, max_loc = templateMatch(target_gray, screen_gray)
    except TemplateTooLargeError:
        return None
    if max_val < threshold: return None
    return (max_val, max_loc)
    
def locateTransparentImageOnScreen(target, x,y,w,h, threshold = 0):
    screen = mssScreenshotNP(x,y,w,h)
    return locateTransparentImage(target, screen, threshold)


def findColorObjectHSL(img, hslRange, kernel=None, mode="point", best=1, draw=False):
    """
    Find objects of a specific color in the HSL range.

    Args:
        img (numpy.ndarray): Input image in BGR format.
        hslRange (list): HSL range [(H_min, S_min, L_min), (H_max, S_max, L_max)].
        kernel (numpy.ndarray): Kernel for erosion (optional).
        mode (str): "point" to return center of bounding box, "box" to return bounding boxes.
        best (int): Number of top contours to return (default 1).
        draw (bool): Whether to draw bounding boxes on the image.

    Returns:
        tuple or list: Coordinates of the center or bounding boxes.
    """
    hLow, sLow, lLow = hslRange[0][0] / 2, hslRange[0][1] / 100 * 255, hslRange[0][2] / 100 * 255
    hHigh, sHigh, lHigh = hslRange[1][0] / 2, hslRange[1][1] / 100 * 255, hslRange[1][2] / 100 * 255

    binary_mask = cv2.inRange(
        cv2.cvtColor(img, cv2.COLOR_BGR2HLS),
        np.array([hLow, lLow, sLow], dtype=np.uint8),
        np.array([hHigh, lHigh, sHigh], dtype=np.uint8)
    )

    if kernel is not None:
        binary_mask = cv2.erode(binary_mask, kernel, iterations=1)

    contours, _ = cv2.findContours(binary_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        return None
    
    if best > 1:
        contours = sorted(contours, key=cv2.contourArea, reverse=True)[:best]

    results = []
    for contour in (contours if best > 1 else [max(contours, key=cv2.contourArea)]):
        x, y, w, h = cv2.boundingRect(contour)
        results.append((x + w // 2, y + h // 2) if mode == "point" else (x, y, w, h))
        if draw:
            cv2.rectangle(img, (x, y), (x + w, y + h), (0, 255, 0), 2)

    if draw:
        cv2.imwrite(f"{time.time()}.png", img)
        cv2.imshow("Result", img)
        cv2.waitKey(0)

    return results if best > 1 else results[0]

def findColorObjectRGB(img, rgbTarget, variance=0, kernel=None, mode="point", best=1, draw=False):
    """
    Quickly find objects of a specific color in the RGB range with variance.

    Args:
        img (numpy.ndarray): Input image in BGR format.
        rgbTarget (tuple): Target RGB color (R, G, B), values 0-255.
        variance (int): Allowed variation (0-255) for each color component.
        kernel (numpy.ndarray): Kernel for erosion (optional).
        mode (str): "point" to return center of bounding box, "box" to return bounding boxes.
        best (int): Number of top contours to return (default 1).
        draw (bool): Whether to draw bounding boxes on the image.

    Returns:
        tuple or list: Coordinates of the center or bounding boxes.
    """
    
    # Convert image from BGR to RGB
    imgRGB = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    
    # Compute lower and upper bounds
    lower_bound = np.clip(np.array(rgbTarget) - variance, 0, 255).astype(np.uint8)
    upper_bound = np.clip(np.array(rgbTarget) + variance, 0, 255).astype(np.uint8)
    
    # Thresholding to create a binary mask
    binary_mask = cv2.inRange(imgRGB, lower_bound, upper_bound)
    
    if kernel is not None:
        binary_mask = cv2.erode(binary_mask, kernel, iterations=1)
    
    contours, _ = cv2.findContours(binary_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if not contours:
        return None
    
    if best > 1:
        contours = sorted(contours, key=cv2.contourArea, reverse=True)[:best]
    
    results = []
    for contour in (contours if best > 1 else [max(contours, key=cv2.contourArea)]):
        x, y, w, h = cv2.boundingRect(contour)
        results.append((x + w // 2, y + h // 2) if mode == "point" else (x, y, w, h))
        if draw:
            cv2.rectangle(img, (x, y), (x + w, y + h), (0, 0, 255), 2)
    
    if draw:
        cv2.imshow("Result", img)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
    
    return results if best > 1 else results[0]

