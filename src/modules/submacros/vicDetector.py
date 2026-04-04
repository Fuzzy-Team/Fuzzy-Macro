import os

import cv2
import numpy as np


class VicDetector:
    MODEL_INPUT_WIDTH = 736
    MODEL_INPUT_HEIGHT = 736
    CONFIDENCE_THRESHOLD = 0.4
    NMS_THRESHOLD = 0.5

    def __init__(self, logger=None):
        self.logger = logger
        self.enabled = False
        self.model = None
        self.input_name = None

        try:
            import onnxruntime
        except Exception:
            self._log("[VicDetector] onnxruntime is not installed; using blue-text fallback")
            return

        model_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "data", "models", "vic.onnx")
        )
        if not os.path.exists(model_path):
            self._log(f"[VicDetector] model file missing: {model_path}")
            return

        providers = onnxruntime.get_available_providers()
        preferred_providers = [
            provider
            for provider in ("CoreMLExecutionProvider", "CPUExecutionProvider")
            if provider in providers
        ]
        if not preferred_providers:
            preferred_providers = providers

        try:
            self.model = onnxruntime.InferenceSession(model_path, providers=preferred_providers)
            self.input_name = self.model.get_inputs()[0].name
            self.enabled = True
            self._log(f"[VicDetector] loaded model: {os.path.basename(model_path)}")
        except Exception as e:
            self._log(f"[VicDetector] failed to load model: {e}")

    def _log(self, message):
        if self.logger:
            self.logger.log(message)
        else:
            print(message)

    def _preprocess(self, bgra_image):
        resized = cv2.resize(
            bgra_image,
            (self.MODEL_INPUT_WIDTH, self.MODEL_INPUT_HEIGHT),
            interpolation=cv2.INTER_LINEAR,
        )
        if resized.shape[2] == 4:
            rgb = cv2.cvtColor(resized, cv2.COLOR_BGRA2RGB)
        else:
            rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        normalized = rgb.astype(np.float16) / 255.0
        chw = np.transpose(normalized, (2, 0, 1))
        return np.expand_dims(chw, axis=0)

    def _postprocess(self, output):
        outputs = np.squeeze(output[0])
        if outputs.ndim != 2 or outputs.shape[0] < 5:
            return False

        class_probs = outputs[4:, :]
        confidences = np.max(class_probs, axis=0)
        mask = confidences > self.CONFIDENCE_THRESHOLD
        filtered_confidences = confidences[mask]
        if len(filtered_confidences) == 0:
            return False

        boxes_data = outputs[:4, mask]
        cx, cy, w, h = boxes_data
        x1 = cx - w / 2
        y1 = cy - h / 2
        boxes_for_nms = np.stack((x1, y1, w, h), axis=1)
        indices = cv2.dnn.NMSBoxes(
            boxes_for_nms.tolist(),
            filtered_confidences.tolist(),
            self.CONFIDENCE_THRESHOLD,
            self.NMS_THRESHOLD,
        )
        return len(indices) > 0

    def detect(self, bgra_image):
        if not self.enabled or self.model is None or self.input_name is None:
            return False
        if bgra_image is None or not isinstance(bgra_image, np.ndarray):
            return False
        if bgra_image.ndim != 3 or bgra_image.shape[2] not in (3, 4):
            return False

        try:
            tensor = self._preprocess(bgra_image)
            output = self.model.run(None, {self.input_name: tensor})
            return self._postprocess(output)
        except Exception as e:
            self._log(f"[VicDetector] detect failed: {e}")
            return False
