import os
import urllib.request

import numpy as np


class VicDetector:
    def __init__(self, logger=None, confidence=0.3):
        self.logger = logger
        self.confidence = confidence
        self.enabled = False
        self.model = None

        try:
            from ultralytics import YOLO
        except Exception:
            self._log("[VicDetector] ultralytics is not installed; using legacy Vicious Bee detection")
            return

        model_path = self._get_model_path()
        if not os.path.exists(model_path):
            self._log(f"[VicDetector] model file missing: {model_path}")
            return

        try:
            self.model = YOLO(model_path)
            self.enabled = True
            self._log(f"[VicDetector] loaded model: {os.path.basename(model_path)}")
        except Exception as e:
            self._log(f"[VicDetector] failed to load model: {e}")

    def _log(self, msg):
        if self.logger:
            self.logger.log(msg)
        else:
            print(msg)

    def _fetch_beesmas_enabled(self):
        url = "https://raw.githubusercontent.com/nosyliam/revolution-macro/refs/heads/main/versions/beesmas"
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                text = resp.read().decode().strip()
                return bool(int(text))
        except Exception:
            return False

    def _get_model_path(self):
        base_dir = os.path.dirname(__file__)
        model_dir = os.path.abspath(os.path.join(base_dir, "..", "..", "data", "bss", "vic_models"))
        beesmas_enabled = self._fetch_beesmas_enabled()
        model_name = "vic_beesmas.pt" if beesmas_enabled else "vic_plain.pt"
        return os.path.join(model_dir, model_name)

    def detect(self, bgra_image):
        if not self.enabled or self.model is None:
            return False

        if bgra_image is None or not isinstance(bgra_image, np.ndarray):
            return False

        if bgra_image.ndim != 3 or bgra_image.shape[2] not in (3, 4):
            return False

        if bgra_image.shape[2] == 4:
            image = bgra_image[:, :, :3]
        else:
            image = bgra_image

        try:
            results = self.model(image, conf=self.confidence, verbose=False)
            if not results:
                return False
            return len(results[0].boxes) > 0
        except Exception as e:
            self._log(f"[VicDetector] detect failed: {e}")
            return False

