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


def similarHashes(hash1, hash2, threshold):
    return hash1-hash2 < threshold

def locateImageWithMaskOnScreen(image, mask, x, y, w, h, threshold=0, scales=None, return_scale=False, img_interp=cv2.INTER_AREA, mask_interp=cv2.INTER_NEAREST, early_exit_thresh=0.995):
    """
    Scale-aware masked template matching.

    - `image` / `mask` may be numpy arrays (image: BGR/BGRA, mask: single-channel or BGRA/alpha) or path strings.
      If a path string is provided, loader prefers display-specific assets and caches results.
    - `scales`: iterable of scale factors to try (if None, built from screenData display multi).
    - Returns (max_val, max_loc) or (max_val, max_loc, scale) if return_scale True.
    - Returns None when no match reaches `threshold`.
    """
    # capture screen region (same as other locate* functions)
    screen = mssScreenshotNP(x, y, w, h)
    screen = cv2.cvtColor(screen, cv2.COLOR_BGRA2BGR)
    screen = _to_uint8(screen)
    if screen is None:
        return None

    # Helper to load/normalize an image (preserve alpha if present)
    def _load_img_or_pass(obj):
        if isinstance(obj, str):
            base = obj
            if base.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.webp')):
                base = base.rsplit('.', 1)[0]
            try:
                return load_template_for_display(base)
            except Exception:
                return None
        return obj

    # load template (may be numpy image or path)
    img_target = _load_img_or_pass(image)
    if img_target is None:
        return None

    # prepare mask_target variable (may remain None)
    mask_target = None

    # If caller provided an explicit mask (path or array), load it and strip any alpha from template
    if mask is not None:
        mask_target = _load_img_or_pass(mask)
        # if template had alpha, remove it because we're using a separate mask
        if img_target.ndim == 3 and img_target.shape[2] == 4:
            img_target = cv2.cvtColor(img_target, cv2.COLOR_BGRA2BGR)
    else:
        # If no explicit mask and template contains an alpha channel, use that alpha as the mask
        if img_target.ndim == 3 and img_target.shape[2] == 4:
            mask_target = img_target[..., 3]
            img_target = cv2.cvtColor(img_target, cv2.COLOR_BGRA2BGR)

    # Normalize mask to single channel 8-bit binary (0/255)
    def _mask_to_binary(m):
        if m is None:
            return None
        # if mask has alpha channel, use it
        if m.ndim == 3 and m.shape[2] in (4, 3):
            # if 4 channels, alpha is last; if 3 channels, assume single channel mask in one band
            if m.shape[2] == 4:
                alpha = m[..., 3]
                bin_mask = cv2.threshold(alpha, 0, 255, cv2.THRESH_BINARY)[1]
                return bin_mask
            else:
                # convert to gray then threshold
                gray = cv2.cvtColor(m, cv2.COLOR_BGR2GRAY)
                return cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY)[1]
        elif m.ndim == 2:
            # already single channel
            # ensure binary 0/255
            return cv2.threshold(m, 0, 255, cv2.THRESH_BINARY)[1]
        else:
            # fallback: convert to uint8 zeros
            return None

    mask_target = _mask_to_binary(mask_target)

    # Validate template shape
    try:
        t_h, t_w = img_target.shape[:2]
    except Exception:
        return None

    # Build default scales if not provided (same logic as scaled locate)
    if scales is None:
        sd = getScreenData()
        multi = 2 if sd.get("display_type") == "retina" else 1
        candidates = [1.0]
        if multi not in candidates:
            candidates.append(multi)
        neighbors = [0.95, 1.05]
        candidates += [round(c * n, 3) for c in list(candidates) for n in neighbors]
        scales = sorted(set(candidates), reverse=True)

    best_val = -1.0
    best_loc = None
    best_scale = None

    # Quick direct try if image came from a path and already matches display
    is_path = isinstance(image, str)
    img_base = None
    mask_base = None
    if is_path:
        img_base = image
        if img_base.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.webp')):
            img_base = img_base.rsplit('.', 1)[0]
    if isinstance(mask, str):
        mask_base = mask
        if mask_base.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.webp')):
            mask_base = mask_base.rsplit('.', 1)[0]

    if is_path:
        try:
            # If mask exists, ensure it's same size as template for this direct trial
            if mask_target is not None and (mask_target.shape[0] != t_h or mask_target.shape[1] != t_w):
                # if mask size mismatch, skip direct try
                raise TemplateTooLargeError((t_w, t_h), (t_w, t_h))
            tt, ss = _ensure_channel_compat(_to_uint8(img_target), screen)
            if tt is None or ss is None:
                raise Exception("Invalid images for direct masked match")
            res = cv2.matchTemplate(ss, tt, cv2.TM_CCORR_NORMED, mask=mask_target)
            _, val, _, loc = cv2.minMaxLoc(res)
            if val > best_val:
                best_val, best_loc, best_scale = val, loc, 1.0
                if best_val >= early_exit_thresh and best_val >= threshold:
                    return (best_val, best_loc) if not return_scale else (best_val, best_loc, best_scale)
        except TemplateTooLargeError:
            # proceed to scaled attempts (e.g., template larger than region)
            pass
        except Exception:
            # any other failure, continue to scaled attempts
            pass

    # Try scales, resizing both image and mask with same factor
    for scale in scales:
        new_w = max(1, int(round(t_w * scale)))
        new_h = max(1, int(round(t_h * scale)))

        # Skip if resized template is larger than search area
        if new_h > screen.shape[0] or new_w > screen.shape[1]:
            continue

        # Prepare resized image (use cache when we have a path)
        resized_img = None
        resized_mask = None
        scale_key = int(round(scale * 1000))

        if is_path and img_base is not None:
            resized_img = _cached_resized_from_path(img_base, scale_key, need_alpha=False)
            if resized_img is None:
                continue
        else:
            try:
                resized_img = cv2.resize(img_target, (new_w, new_h), interpolation=img_interp)
            except Exception:
                continue

        # Prepare resized mask (use cache when mask is a path)
        if mask_target is not None:
            if mask_base is not None:
                resized_mask = _cached_resized_mask_from_path(mask_base, scale_key)
                if resized_mask is None:
                    # fall back to resizing in-memory mask_target
                    try:
                        resized_mask = cv2.resize(mask_target, (new_w, new_h), interpolation=mask_interp)
                    except Exception:
                        resized_mask = None
            else:
                try:
                    resized_mask = cv2.resize(mask_target, (new_w, new_h), interpolation=mask_interp)
                except Exception:
                    resized_mask = None

            if resized_mask is not None:
                if resized_mask.ndim == 3:
                    resized_mask = cv2.cvtColor(resized_mask, cv2.COLOR_BGR2GRAY)
                _, resized_mask = cv2.threshold(resized_mask, 0, 255, cv2.THRESH_BINARY)

        # ensure types and channel compatibility
        resized_img = _to_uint8(resized_img)
        if resized_img is None:
            continue
        tt, ss = _ensure_channel_compat(resized_img, screen)
        if tt is None or ss is None:
            continue

        try:
            res = cv2.matchTemplate(ss, tt, cv2.TM_CCORR_NORMED, mask=resized_mask)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)
        except Exception:
            # TemplateTooLargeError unlikely here due to earlier check; skip on error
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


def fastFeatureMatching(haystack, needle):

    # Load images (downscale for speed if needed)
    img1 = needle
    img2 = haystack

    # Downscale images to speed up processing (adjust scale factor as needed)

    # Use ORB for keypoint detection and descriptor extraction
    orb = cv2.ORB_create(nfeatures=500, scoreType=cv2.ORB_FAST_SCORE)  

    # Detect keypoints and compute descriptors
    kp1, des1 = orb.detectAndCompute(img1, None)
    kp2, des2 = orb.detectAndCompute(img2, None)
    if des1 is None or des2 is None or len(kp1) < 2 or len(kp2) < 2:
        return None

    # Use FLANN-based matcher for faster approximate matching
    FLANN_INDEX_LSH = 6
    index_params = dict(algorithm=FLANN_INDEX_LSH, table_number=6, key_size=12, multi_probe_level=1)
    search_params = dict(checks=80) 
    flann = cv2.FlannBasedMatcher(index_params, search_params)

    # Perform knnMatch
    matches = flann.knnMatch(des1, des2, k=2)

    # Apply ratio test
    good = []
    for x in matches:
        if len(x) != 2: continue
        m, n = x
        if m.distance < 0.7 * n.distance:
            good.append(m)

    # If there are enough good matches, find the object's location
    if len(good) < 5:
        return None
    
    # Extract location of good matches
    src_pts = np.float32([kp1[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
    dst_pts = np.float32([kp2[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)

    # Find homography
    M, _ = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)


    if M is None:
        return None
    #homography is found
    h, w = img1.shape[:2]
    pts = np.float32([[0, 0], [w, 0], [w, h], [0, h]]).reshape(-1, 1, 2)
    dst = cv2.perspectiveTransform(pts, M)

    # Calculate and display center of the bounding box
    center_x = int(np.mean(dst[:, 0, 0]))
    center_y = int(np.mean(dst[:, 0, 1]))
    return (center_x, center_y)
