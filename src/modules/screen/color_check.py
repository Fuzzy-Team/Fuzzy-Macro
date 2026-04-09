import numpy as np
from modules.screen.screenshot import mssScreenshotNP


def get_sample_colors():
    """Return the configured light and dark colors directly.

    This function no longer reads sample images — it always returns the
    two canonical colors to check: light (255,255,255) and dark (18,18,21).
    """
    return [(255, 255, 255), (18, 18, 21)]


def _color_distance(c1, c2):
    return sum((int(a) - int(b)) ** 2 for a, b in zip(c1, c2)) ** 0.5


def percent_pixels_similar_to_color(x, y, w, h, target_color, tolerance=40):
    """Capture the region (x,y,w,h) and return fraction (0..1) of pixels
    within `tolerance` Euclidean distance of `target_color`.
    """
    try:
        arr = mssScreenshotNP(int(x), int(y), int(w), int(h))
        # arr is BGRA (mss) — convert to RGB
        if arr.ndim == 3 and arr.shape[2] >= 3:
            rgb = arr[..., :3][..., ::-1]
        else:
            return 0.0
        # downsample for speed
        small = rgb[::max(1, rgb.shape[0]//120), ::max(1, rgb.shape[1]//120), :]
        # Use squared-distance math in wider integer types to avoid overflow.
        tc = np.array(target_color, dtype=np.int32)
        delta = small.astype(np.int32) - tc
        dist2 = np.sum(delta * delta, axis=2, dtype=np.int64)
        tol2 = int(tolerance) * int(tolerance)
        cnt = np.sum(dist2 <= tol2)
        total = dist2.size
        return float(cnt) / float(total) if total else 0.0
    except Exception:
        return 0.0
