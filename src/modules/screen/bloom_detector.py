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


@dataclass
class BloomTarget:
    tx: float
    ty: float
    distance: float
    candidate: BloomCandidate


class BloomDetector:
    HEALTHBAR_TARGET_Y_OFFSET = 80
    NAMEPLATE_TARGET_Y_MULTIPLIER = 2.0

    def _in_play_area(self, x, y, width, height):
        if y < 170 or y > height - 125:
            return False
        if x > width - 360 and y > height - 240:
            return False
        return True

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

    def _detect_healthbar_candidates(self, bgr):
        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
        height, width = bgr.shape[:2]

        green_mask = self._range_mask(hsv, [(20, 90)], (70, 255), (80, 255))
        green_mask = cv2.morphologyEx(green_mask, cv2.MORPH_CLOSE, np.ones((7, 3), np.uint8), iterations=1)
        pink_mask = self._range_mask(hsv, [(135, 176)], (70, 255), (120, 255))
        white_mask = self._range_mask(hsv, [], (0, 75), (170, 255))
        dark_mask = self._range_mask(hsv, [], (0, 220), (0, 80))
        dark_search_mask = cv2.morphologyEx(dark_mask, cv2.MORPH_CLOSE, np.ones((13, 5), np.uint8), iterations=2)
        dark_search_mask = cv2.morphologyEx(dark_search_mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8), iterations=1)

        contours, _ = cv2.findContours(green_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        candidates = []
        seen = []

        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            area = cv2.contourArea(contour)
            if w < 10 or w > 120 or h < 3 or h > 24:
                continue
            if area < 24 or area > 1800:
                continue
            if w / float(max(h, 1)) < 1.8:
                continue

            label_x0 = max(0, x - 42)
            label_y0 = max(0, y - 12)
            label_x1 = min(width, x + max(w + 85, 95))
            label_y1 = min(height, y + h + 16)
            roi_area = max((label_x1 - label_x0) * (label_y1 - label_y0), 1)

            pink_count = int(np.count_nonzero(pink_mask[label_y0:label_y1, label_x0:label_x1]))
            white_count = int(np.count_nonzero(white_mask[label_y0:label_y1, label_x0:label_x1]))
            dark_count = int(np.count_nonzero(dark_mask[label_y0:label_y1, label_x0:label_x1]))
            green_count = int(np.count_nonzero(green_mask[label_y0:label_y1, label_x0:label_x1]))

            if pink_count < 2 or white_count < 8:
                continue
            if dark_count / float(roi_area) < 0.08:
                continue

            cx = int(round(label_x0 + ((label_x1 - label_x0) / 2.0)))
            cy = int(round(min(height - 1, y + h + self.HEALTHBAR_TARGET_Y_OFFSET)))
            if not self._in_play_area(cx, cy, width, height):
                continue
            if any((cx - px) ** 2 + (cy - py) ** 2 < 2500 for px, py in seen):
                continue
            seen.append((cx, cy))

            score = (
                min(green_count / 80.0, 2.0)
                + min(pink_count / 20.0, 1.5)
                + min(white_count / 80.0, 1.5)
                + min((dark_count / float(roi_area)) * 5.0, 1.0)
            )
            candidates.append(
                BloomCandidate(
                    x=cx,
                    y=cy,
                    area=float(area),
                    radius=55.0,
                    circularity=1.0,
                    center_fill_ratio=min(green_count / 80.0, 1.0),
                    petal_ratio=min(pink_count / 20.0, 1.0),
                    score=float(score),
                )
            )

        dark_contours, _ = cv2.findContours(dark_search_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for contour in dark_contours:
            x, y, w, h = cv2.boundingRect(contour)
            area = cv2.contourArea(contour)
            if w < 26 or w > 140 or h < 6 or h > 24:
                continue
            if area < 90 or area > 2500:
                continue
            if w / float(max(h, 1)) < 2.2:
                continue

            label_x0 = max(0, x - 42)
            label_y0 = max(0, y - 14)
            label_x1 = min(width, x + max(w + 90, 105))
            label_y1 = min(height, y + h + 18)
            roi_area = max((label_x1 - label_x0) * (label_y1 - label_y0), 1)

            pink_count = int(np.count_nonzero(pink_mask[label_y0:label_y1, label_x0:label_x1]))
            white_count = int(np.count_nonzero(white_mask[label_y0:label_y1, label_x0:label_x1]))
            green_count = int(np.count_nonzero(green_mask[label_y0:label_y1, label_x0:label_x1]))
            dark_count = int(np.count_nonzero(dark_mask[label_y0:label_y1, label_x0:label_x1]))

            if green_count < 10 or white_count < 8:
                continue
            if pink_count < 1 and green_count < 30:
                continue

            cx = int(round(label_x0 + ((label_x1 - label_x0) / 2.0)))
            cy = int(round(min(height - 1, y + h + self.HEALTHBAR_TARGET_Y_OFFSET)))
            if not self._in_play_area(cx, cy, width, height):
                continue
            if any((cx - px) ** 2 + (cy - py) ** 2 < 2500 for px, py in seen):
                continue
            seen.append((cx, cy))

            score = (
                min(green_count / 55.0, 2.0)
                + min(white_count / 70.0, 1.5)
                + min(pink_count / 12.0, 1.2)
                + min((dark_count / float(roi_area)) * 5.0, 1.0)
            )
            candidates.append(
                BloomCandidate(
                    x=cx,
                    y=cy,
                    area=float(area),
                    radius=55.0,
                    circularity=1.0,
                    center_fill_ratio=min(green_count / 55.0, 1.0),
                    petal_ratio=min(pink_count / 12.0, 1.0),
                    score=float(score),
                )
            )

        candidates.sort(key=lambda c: c.score, reverse=True)
        return candidates

    def _detect_nameplate_candidates(self, bgr):
        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
        height, width = bgr.shape[:2]

        dark_mask = self._range_mask(hsv, [], (0, 210), (0, 95))
        dark_mask = cv2.morphologyEx(dark_mask, cv2.MORPH_CLOSE, np.ones((13, 5), np.uint8), iterations=2)
        dark_mask = cv2.morphologyEx(dark_mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8), iterations=1)

        green_mask = self._range_mask(hsv, [(38, 86)], (80, 255), (120, 255))
        white_mask = self._range_mask(hsv, [], (0, 70), (175, 255))
        pink_mask = self._range_mask(hsv, [(135, 175)], (70, 255), (120, 255))
        cyan_mask = self._range_mask(hsv, [(88, 110)], (70, 255), (110, 255))

        contours, _ = cv2.findContours(dark_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        candidates = []
        seen = []

        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            area = cv2.contourArea(contour)
            if w < 42 or w > 280 or h < 14 or h > 95:
                continue
            if area < 350 or area > 18000:
                continue

            aspect = w / float(h)
            if aspect < 1.3 or aspect > 8.5:
                continue

            pad = max(4, int(round(h * 0.35)))
            x0 = max(0, x - pad)
            y0 = max(0, y - pad)
            x1 = min(width, x + w + pad)
            y1 = min(height, y + h + pad)
            roi_area = max((x1 - x0) * (y1 - y0), 1)

            green_count = int(np.count_nonzero(green_mask[y0:y1, x0:x1]))
            white_count = int(np.count_nonzero(white_mask[y0:y1, x0:x1]))
            pink_count = int(np.count_nonzero(pink_mask[y0:y1, x0:x1]))
            cyan_count = int(np.count_nonzero(cyan_mask[y0:y1, x0:x1]))
            bright_count = green_count + white_count + pink_count + cyan_count

            if green_count < 8 or white_count < 8 or bright_count < 24:
                continue

            cx = int(round(x + (w / 2.0)))
            cy = int(round(min(height - 1, y + (h * self.NAMEPLATE_TARGET_Y_MULTIPLIER))))
            radius = float(max(w, h) / 2.0)
            body_area = float(area)
            circularity = 1.0
            fill_ratio = min(green_count / 80.0, 1.0)

            if not self._in_play_area(cx, cy, width, height):
                continue

            if any((cx - px) ** 2 + (cy - py) ** 2 < 900 for px, py in seen):
                continue
            seen.append((cx, cy))

            health_signal = min(green_count / 80.0, 1.8)
            text_signal = min(white_count / 120.0, 1.4)
            bloom_icon_signal = min((pink_count + cyan_count) / 40.0, 1.0)
            density = bright_count / float(roi_area)
            score = health_signal + text_signal + bloom_icon_signal + min(density * 8.0, 1.0)

            candidates.append(
                BloomCandidate(
                    x=cx,
                    y=cy,
                    area=body_area,
                    radius=radius,
                    circularity=circularity,
                    center_fill_ratio=fill_ratio,
                    petal_ratio=min((pink_count + cyan_count) / 40.0, 1.0),
                    score=float(score),
                )
            )

        candidates.sort(key=lambda c: c.score, reverse=True)
        return candidates

    def detect_candidates(self, bgr, preferred_color=None):
        if bgr is None or getattr(bgr, "size", 0) == 0:
            return []

        candidates = self._detect_healthbar_candidates(bgr)
        candidates.extend(self._detect_nameplate_candidates(bgr))
        candidates.sort(key=lambda c: c.score, reverse=True)

        deduped = []
        for candidate in candidates:
            if any(
                (candidate.x - existing.x) ** 2 + (candidate.y - existing.y) ** 2
                < max(candidate.radius, existing.radius, 35.0) ** 2
                for existing in deduped
            ):
                continue
            deduped.append(candidate)
        return deduped

    def aligned_targets(self, bgr, sprinkler_detector, preferred_color=None, max_distance_tiles=None):
        if bgr is None or getattr(bgr, "size", 0) == 0:
            return []

        height, width = bgr.shape[:2]
        targets = []
        for candidate in self.detect_candidates(bgr, preferred_color=preferred_color):
            distance = sprinkler_detector.relative_distance(candidate.x, candidate.y, width, height)
            if distance is None:
                continue
            tx, ty = distance
            magnitude = float(math.hypot(tx, ty))
            if max_distance_tiles is not None and magnitude > max_distance_tiles:
                continue
            targets.append(
                BloomTarget(
                    tx=float(tx),
                    ty=float(ty),
                    distance=magnitude,
                    candidate=candidate,
                )
            )

        targets.sort(
            key=lambda target: (
                target.candidate.score,
                -target.distance,
            ),
            reverse=True,
        )
        return targets

    def find_best_aligned_target(self, bgr, sprinkler_detector, preferred_color=None, max_distance_tiles=None):
        targets = self.aligned_targets(
            bgr,
            sprinkler_detector,
            preferred_color=preferred_color,
            max_distance_tiles=max_distance_tiles,
        )
        return targets[0] if targets else None
