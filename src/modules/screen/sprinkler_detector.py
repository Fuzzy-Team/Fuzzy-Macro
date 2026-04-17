from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

try:
    import onnxruntime as ort
except Exception:
    ort = None


@dataclass
class SprinklerCandidate:
    x: float
    y: float
    label: str
    confidence: float
    box: tuple


@dataclass
class SprinklerTarget:
    tx: float
    ty: float
    distance: float
    candidate: SprinklerCandidate


class SprinklerDetector:
    INPUT_WIDTH = 736
    INPUT_HEIGHT = 736
    CONFIDENCE_THRESHOLD = 0.6
    NMS_THRESHOLD = 0.5
    MAX_DISTANCE_TILES = 10.0

    LABELS = {
        0: "Basic",
        1: "Diamond",
        2: "Gold",
        3: "Silver",
        4: "Supreme",
    }

    NORMALIZED_CAL_RATIOS = [
        (0.395314, 0.427995),
        (0.597795, 0.430686),
        (0.320584, 0.721513),
        (0.670597, 0.722439),
    ]

    def __init__(self, model_path=None, confidence_threshold=None):
        if model_path is None:
            model_path = Path(__file__).resolve().parents[2] / "data" / "models" / "sprinkler.onnx"
        self.model_path = Path(model_path)
        self.confidence_threshold = (
            float(confidence_threshold)
            if confidence_threshold is not None
            else self.CONFIDENCE_THRESHOLD
        )
        self.session = None
        self.input_name = None
        self.use_float16 = False
        self.error = ""

    def ensure_loaded(self):
        if self.session is not None:
            return True
        if ort is None:
            self.error = "onnxruntime is not installed"
            return False
        if not self.model_path.exists():
            self.error = f"sprinkler model not found: {self.model_path}"
            return False

        try:
            available = ort.get_available_providers()
            preferred = [
                "DmlExecutionProvider",
                "CUDAExecutionProvider",
                "CPUExecutionProvider",
            ]
            providers = [provider for provider in preferred if provider in available] or available
            self.session = ort.InferenceSession(str(self.model_path), providers=providers)
            input_meta = self.session.get_inputs()[0]
            self.input_name = input_meta.name
            self.use_float16 = "float16" in input_meta.type.lower()
            self.error = ""
            return True
        except Exception as exc:
            self.session = None
            self.input_name = None
            self.error = str(exc)
            return False

    def _preprocess(self, frame):
        resized = cv2.resize(
            frame,
            (self.INPUT_WIDTH, self.INPUT_HEIGHT),
            interpolation=cv2.INTER_LINEAR,
        )
        if resized.ndim == 3 and resized.shape[2] == 4:
            rgb = cv2.cvtColor(resized, cv2.COLOR_BGRA2RGB)
        else:
            rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)

        dtype = np.float16 if self.use_float16 else np.float32
        normalized = rgb.astype(dtype) / 255.0
        chw = np.transpose(normalized, (2, 0, 1))
        return np.expand_dims(chw, axis=0)

    def _postprocess(self, output):
        outputs = np.squeeze(output[0])
        if outputs.ndim != 2 or outputs.shape[0] < 5:
            return []

        class_probs = outputs[4:, :]
        confidences = np.max(class_probs, axis=0)
        mask = confidences > self.confidence_threshold
        if not np.any(mask):
            return []

        filtered_confidences = confidences[mask]
        class_ids = np.argmax(class_probs[:, mask], axis=0)
        boxes_data = outputs[:4, mask]
        cx, cy, box_w, box_h = boxes_data
        x1 = cx - box_w / 2.0
        y1 = cy - box_h / 2.0
        boxes = np.stack((x1, y1, box_w, box_h), axis=1)

        indices = cv2.dnn.NMSBoxes(
            boxes.tolist(),
            filtered_confidences.tolist(),
            self.confidence_threshold,
            self.NMS_THRESHOLD,
        )

        detections = []
        if len(indices) > 0:
            for index in np.array(indices).flatten():
                bx, by, bw, bh = boxes[index]
                detections.append(
                    (
                        (float(bx), float(by), float(bx + bw), float(by + bh)),
                        int(class_ids[index]),
                        float(filtered_confidences[index]),
                    )
                )
        return detections

    def detect_candidates(self, frame):
        if frame is None or getattr(frame, "size", 0) == 0:
            return []
        if not self.ensure_loaded():
            return []

        output = self.session.run(None, {self.input_name: self._preprocess(frame)})
        height, width = frame.shape[:2]
        scale_x = width / float(self.INPUT_WIDTH)
        scale_y = height / float(self.INPUT_HEIGHT)

        candidates = []
        for box, class_id, confidence in self._postprocess(output):
            label = self.LABELS.get(class_id)
            if not label:
                continue
            x1, y1, x2, y2 = box
            center_x = ((x1 + x2) / 2.0) * scale_x
            center_y = ((y1 + y2) / 2.0) * scale_y
            candidates.append(
                SprinklerCandidate(
                    x=float(center_x),
                    y=float(center_y),
                    label=label,
                    confidence=float(confidence),
                    box=(x1 * scale_x, y1 * scale_y, x2 * scale_x, y2 * scale_y),
                )
            )
        return candidates

    def _homography(self, width, height):
        source = np.array(
            [
                [float(nx * width), float(ny * height)]
                for nx, ny in self.NORMALIZED_CAL_RATIOS
            ],
            dtype=np.float32,
        )
        destination = np.array(
            [[-5, -5], [5, -5], [-5, 5], [5, 5]],
            dtype=np.float32,
        )
        homography, _ = cv2.findHomography(source, destination, cv2.RANSAC)
        return homography

    def relative_distance(self, x, y, width, height):
        homography = self._homography(width, height)
        if homography is None:
            return None
        point = np.array([[[float(x), float(y) + 15.0]]], dtype=np.float32)
        transformed = cv2.perspectiveTransform(point, homography)
        tx, ty = transformed[0][0]
        return float(tx), float(-ty)

    def find_nearest(self, frame, target_label=None, max_distance_tiles=None):
        if max_distance_tiles is None:
            max_distance_tiles = self.MAX_DISTANCE_TILES

        height, width = frame.shape[:2]
        best = None
        for candidate in self.detect_candidates(frame):
            if target_label and candidate.label != target_label:
                continue
            distance = self.relative_distance(candidate.x, candidate.y, width, height)
            if distance is None:
                continue
            tx, ty = distance
            magnitude = float(np.hypot(tx, ty))
            if magnitude > max_distance_tiles:
                continue
            target = SprinklerTarget(tx=tx, ty=ty, distance=magnitude, candidate=candidate)
            if best is None or target.distance < best.distance:
                best = target
        return best
