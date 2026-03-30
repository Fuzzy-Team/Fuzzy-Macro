from dataclasses import dataclass
import math

import cv2
import numpy as np


@dataclass
class BloomCandidate:
    x: int
    y: int
    area: float
    radius: float
    circularity: float
    center_fill_ratio: float
    petal_ratio: float
    score: float


class BloomDetector:
    CENTER_HUE_RANGES = [(16, 32)]
    CENTER_SAT_RANGE = (50, 125)
    CENTER_VAL_RANGE = (85, 255)

    MIN_BLOB_AREA = 20
    MAX_BLOB_AREA = 800
    MIN_CIRCULARITY = 0.75
    MIN_CENTER_FILL_RATIO = 0.68

    RING_INNER_RADIUS_PERCENT = 105
    RING_OUTER_RADIUS_PERCENT = 225
    MIN_PETAL_RATIO = 0.18

    _PETAL_COLOR_HUES = {
        "red": [(0, 10), (170, 179)],
        "pink": [(145, 179)],
        "blue": [(95, 130)],
        "cyan": [(80, 100)],
        "green": [(36, 90)],
        "white": [],
        "yellow": [(16, 40)],
    }

    def _range_mask(self, hsv, hue_ranges, sat_range, val_range):
        h = hsv[:, :, 0]
        s = hsv[:, :, 1]
        v = hsv[:, :, 2]

        if hue_ranges:
            hue_mask = np.zeros(h.shape, dtype=np.uint8)
            for start, end in hue_ranges:
                if start <= end:
                    hue_mask |= ((h >= start) & (h <= end)).astype(np.uint8)
                else:
                    hue_mask |= (((h >= start) | (h <= end))).astype(np.uint8)
        else:
            hue_mask = np.ones(h.shape, dtype=np.uint8)

        sat_mask = ((s >= sat_range[0]) & (s <= sat_range[1])).astype(np.uint8)
        val_mask = ((v >= val_range[0]) & (v <= val_range[1])).astype(np.uint8)
        return (hue_mask & sat_mask & val_mask).astype(np.uint8) * 255

    def _generic_petal_mask(self, hsv):
        masks = [
            self._range_mask(hsv, [(0, 10), (170, 179)], (80, 255), (90, 255)),
            self._range_mask(hsv, [(145, 179)], (40, 255), (120, 255)),
            self._range_mask(hsv, [(95, 130)], (50, 255), (90, 255)),
            self._range_mask(hsv, [(80, 100)], (40, 255), (120, 255)),
            self._range_mask(hsv, [(36, 90)], (35, 255), (60, 255)),
            self._range_mask(hsv, [], (0, 55), (175, 255)),
        ]
        out = np.zeros(hsv.shape[:2], dtype=np.uint8)
        for mask in masks:
            out |= mask
        return out

    def _preferred_petal_mask(self, hsv, preferred_color):
        color = str(preferred_color or "").strip().lower()
        if color == "white":
            return self._range_mask(hsv, [], (0, 60), (180, 255))
        hue_ranges = self._PETAL_COLOR_HUES.get(color)
        if hue_ranges is None:
            return self._generic_petal_mask(hsv)
        return self._range_mask(hsv, hue_ranges, (35, 255), (90, 255))

    def _center_mask(self, bgr):
        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
        mask = self._range_mask(
            hsv,
            self.CENTER_HUE_RANGES,
            self.CENTER_SAT_RANGE,
            self.CENTER_VAL_RANGE,
        )
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8), iterations=1)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8), iterations=1)
        mask = cv2.dilate(mask, np.ones((3, 3), np.uint8), iterations=1)
        return hsv, mask

    def detect_candidates(self, bgr, preferred_color=None):
        if bgr is None or getattr(bgr, "size", 0) == 0:
            return []

        hsv, center_mask = self._center_mask(bgr)
        petal_mask = self._preferred_petal_mask(hsv, preferred_color)
        generic_mask = self._generic_petal_mask(hsv)

        contours, _ = cv2.findContours(center_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        candidates = []
        height, width = center_mask.shape[:2]

        for contour in contours:
            area = cv2.contourArea(contour)
            if area < self.MIN_BLOB_AREA or area > self.MAX_BLOB_AREA:
                continue

            perimeter = cv2.arcLength(contour, True)
            if perimeter <= 0:
                continue
            circularity = (4.0 * math.pi * area) / (perimeter * perimeter)
            if circularity < self.MIN_CIRCULARITY:
                continue

            moments = cv2.moments(contour)
            if not moments["m00"]:
                continue
            cx = int(moments["m10"] / moments["m00"])
            cy = int(moments["m01"] / moments["m00"])

            (_, _), radius = cv2.minEnclosingCircle(contour)
            radius = max(float(radius), 1.0)
            circle_area = math.pi * radius * radius
            center_fill_ratio = float(area) / float(circle_area) if circle_area > 0 else 0.0
            if center_fill_ratio < self.MIN_CENTER_FILL_RATIO:
                continue

            outer_radius = max(radius * self.RING_OUTER_RADIUS_PERCENT / 100.0, radius + 1.0)
            outer_radius_i = int(math.ceil(outer_radius))
            x0 = max(0, cx - outer_radius_i)
            y0 = max(0, cy - outer_radius_i)
            x1 = min(width, cx + outer_radius_i + 1)
            y1 = min(height, cy + outer_radius_i + 1)

            yy, xx = np.ogrid[y0:y1, x0:x1]
            dist2 = (xx - cx) ** 2 + (yy - cy) ** 2
            inner2 = (radius * self.RING_INNER_RADIUS_PERCENT / 100.0) ** 2
            outer2 = outer_radius ** 2
            annulus = (dist2 >= inner2) & (dist2 <= outer2)
            annulus_pixels = int(np.count_nonzero(annulus))
            if not annulus_pixels:
                continue

            petal_region = petal_mask[y0:y1, x0:x1] > 0
            petal_ratio = float(np.count_nonzero(petal_region & annulus)) / float(annulus_pixels)

            # Use a slightly more permissive fallback for candidates with strong circular yellow centers.
            if petal_ratio < self.MIN_PETAL_RATIO:
                generic_region = generic_mask[y0:y1, x0:x1] > 0
                generic_ratio = float(np.count_nonzero(generic_region & annulus)) / float(annulus_pixels)
                petal_ratio = max(petal_ratio, generic_ratio)
                if petal_ratio < (self.MIN_PETAL_RATIO * 0.6) and not (
                    circularity >= 0.86 and center_fill_ratio >= 0.82
                ):
                    continue

            score = (circularity * 1.2) + center_fill_ratio + (petal_ratio * 2.0)
            candidates.append(
                BloomCandidate(
                    x=cx,
                    y=cy,
                    area=float(area),
                    radius=radius,
                    circularity=float(circularity),
                    center_fill_ratio=float(center_fill_ratio),
                    petal_ratio=float(petal_ratio),
                    score=float(score),
                )
            )

        candidates.sort(key=lambda c: c.score, reverse=True)
        return candidates
