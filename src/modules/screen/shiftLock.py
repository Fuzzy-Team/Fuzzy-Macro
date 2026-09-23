"""Detect the Roblox shift lock button and whether shift lock is on."""
import os
import time

import cv2
import numpy as np

from modules.screen.screenshot import mssScreenshotNP

_template_cache = None


def _load_templates():
    global _template_cache
    if _template_cache is not None:
        return _template_cache

    src_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

    def load_variant(filename):
        template_path = os.path.join(src_dir, "images", "menu", filename)
        template = cv2.imread(template_path, cv2.IMREAD_UNCHANGED)
        if template is None:
            raise FileNotFoundError(f"Shift lock template not found: {template_path}")

        if len(template.shape) == 2:
            color = cv2.cvtColor(template, cv2.COLOR_GRAY2BGR)
            mask = None
        else:
            color = template[:, :, :3]
            mask = template[:, :, 3] if template.shape[2] == 4 else None

        return {
            "color": color,
            "mask": mask,
        }

    _template_cache = {
        "on": load_variant("shiftlock-on.png"),
        "off": load_variant("shiftlock-off.png"),
    }
    return _template_cache

def _resize_template(color, mask, scale):
    if scale == 1.0:
        return color, mask

    interpolation = cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR
    resized_color = cv2.resize(color, None, fx=scale, fy=scale, interpolation=interpolation)
    resized_mask = None
    if mask is not None:
        resized_mask = cv2.resize(mask, None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST)
    return resized_color, resized_mask

def _template_pixel_diff(icon_crop_bgr, icon_template_bgr, icon_mask):
    if icon_crop_bgr.size == 0:
        return float("inf")

    if icon_mask is not None:
        active_pixels = icon_mask > 0
        pixels = icon_crop_bgr[active_pixels]
        template_pixels = icon_template_bgr[active_pixels]
    else:
        pixels = icon_crop_bgr.reshape(-1, 3)
        template_pixels = icon_template_bgr.reshape(-1, 3)

    if pixels.size == 0:
        return float("inf")

    return float(np.mean(np.abs(pixels.astype(np.int16) - template_pixels.astype(np.int16))))

def _search_regions(roblox_window):
    mx, my, mw, mh = roblox_window.mx, roblox_window.my, roblox_window.mw, roblox_window.mh
    return [
        (
            mx,
            my + mh - min(mh, max(145, int(mh * 0.16))),
            min(mw, max(130, int(mw * 0.13))),
            min(mh, max(145, int(mh * 0.16))),
        ),
        (
            mx,
            my + mh - min(mh, max(210, int(mh * 0.22))),
            min(mw, max(210, int(mw * 0.18))),
            min(mh, max(210, int(mh * 0.22))),
        ),
        (
            mx,
            my + mh - min(mh, max(270, int(mh * 0.28))),
            min(mw, max(280, int(mw * 0.24))),
            min(mh, max(270, int(mh * 0.28))),
        ),
    ]

def _score_candidate(score, pixel_diff, center_x, center_y, roblox_window):
    x_penalty = ((center_x - roblox_window.mx) / max(roblox_window.mw, 1)) * 0.08
    bottom_penalty = (((roblox_window.my + roblox_window.mh) - center_y) / max(roblox_window.mh, 1)) * 0.12
    diff_penalty = (min(pixel_diff, 255.0) / 255.0) * 0.2
    return score - x_penalty - bottom_penalty - diff_penalty

def detect_shift_lock(roblox_window):
    """Find the shift lock button. Returns a dict with "state" (True = on); raises if not found."""
    template_data = _load_templates()
    search_regions = _search_regions(roblox_window)
    scales = (0.5, 0.65, 0.8, 1.0, 1.2, 1.4, 1.6, 2.0)

    best_match = None
    for search_x, search_y, search_w, search_h in search_regions:
        screen = mssScreenshotNP(search_x, search_y, search_w, search_h)
        screen_bgr = cv2.cvtColor(screen, cv2.COLOR_BGRA2BGR)

        for variant_name, variant_state in (("on", True), ("off", False)):
            variant = template_data[variant_name]
            for scale in scales:
                scaled_template_color, scaled_mask = _resize_template(
                    variant["color"],
                    variant["mask"],
                    scale,
                )
                template_h, template_w = scaled_template_color.shape[:2]
                if template_h > screen_bgr.shape[0] or template_w > screen_bgr.shape[1]:
                    continue

                result = cv2.matchTemplate(
                    screen_bgr,
                    scaled_template_color,
                    cv2.TM_CCORR_NORMED,
                    mask=scaled_mask,
                )
                _, max_val, _, max_loc = cv2.minMaxLoc(result)
                match_x, match_y = max_loc
                icon_crop = screen_bgr[match_y:match_y + template_h, match_x:match_x + template_w]
                center_x = search_x + match_x + template_w // 2
                center_y = search_y + match_y + template_h // 2
                pixel_diff = _template_pixel_diff(icon_crop, scaled_template_color, scaled_mask)
                weighted_score = _score_candidate(
                    max_val,
                    pixel_diff,
                    center_x,
                    center_y,
                    roblox_window,
                )
                if best_match is None or weighted_score > best_match["weighted_score"]:
                    best_match = {
                        "score": max_val,
                        "weighted_score": weighted_score,
                        "center_x": center_x,
                        "center_y": center_y,
                        "state": variant_state,
                        "variant": variant_name,
                        "pixel_diff": pixel_diff,
                    }

        if best_match and best_match["score"] >= 0.8 and best_match["pixel_diff"] <= 40:
            break

    if not best_match or best_match["score"] < 0.68:
        raise RuntimeError("Could not locate the shift lock button on screen.")

    return best_match


def detect_shift_lock_with_retries(detect, retries=4, delay=0.2, sleep=time.sleep, log_failures=False):
    """Call `detect()` until it reports a state. Returns the last detection or None."""
    last_detection = None
    for attempt in range(retries):
        try:
            last_detection = detect()
        except Exception as error:
            if log_failures:
                print(f"Shift lock detection attempt {attempt + 1} failed: {error}")
            last_detection = None

        if last_detection and last_detection.get("state") is not None:
            return last_detection

        if attempt < retries - 1:
            sleep(delay)

    return last_detection
