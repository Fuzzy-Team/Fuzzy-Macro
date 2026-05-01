from modules.misc.imageManipulation import pillowToCv2
from modules.screen.screenshot import mssScreenshot
from modules.misc.appManager import openApp
import modules.misc.settingsManager as settingsManager
from modules.controls.keyboard import keyboard
import numpy as np
import cv2
import time
import pyautogui as pag
from modules.screen.robloxWindow import RobloxWindowBounds
import os

try:
    import onnxruntime as ort
except Exception:
    ort = None

mw, mh = pag.size()

class fieldDriftCompensation():
    def __init__(self, robloxWindow: RobloxWindowBounds):
        self.robloxWindow = robloxWindow
        #double pixel coordinates, double kernel size
        if self.robloxWindow.isRetina:
            self.kernel = cv2.getStructuringElement(cv2.MORPH_RECT,(15,15))
        else:
            self.kernel = cv2.getStructuringElement(cv2.MORPH_RECT,(8,8))
        self._sprinkler_session = None
        self._sprinkler_input_name = None
        self._sprinkler_use_float16 = False
        self._sprinkler_model_failed = False
        self._sprinkler_warning_shown = False
        self._sprinkler_input_size = 736
        self._sprinkler_confidence_threshold = 0.6
        self._sprinkler_nms_threshold = 0.5
        self._sprinkler_label_map = {
            0: "Basic",
            1: "Diamond",
            2: "Gold",
            3: "Silver",
            4: "Supreme",
        }
        self._sprinkler_type_map = {
            "basic": "Basic",
            "silver": "Silver",
            "gold": "Gold",
            "golden": "Gold",
            "diamond": "Diamond",
            "supreme": "Supreme",
            "saturator": "Supreme",
        }
    
    #imgSRC is a cv2 img
    def getSaturatorInImage(self, imgSRC):
        imgHLS = cv2.cvtColor(imgSRC, cv2.COLOR_BGR2HLS)

        sLow = 250
        sHi = 255
        lLow = 120
        lHi = 200
        hLow = 170/2
        hHi = 220/2

        # Apply thresholds to each channel (H, L, S)
        binary_mask = cv2.inRange(
            cv2.cvtColor(imgHLS, cv2.COLOR_BGR2HLS),
            np.array([hLow, lLow, sLow], dtype=np.uint8),
            np.array([hHi, lHi, sHi], dtype=np.uint8)
            )
        
        binary_mask = cv2.erode(binary_mask, self.kernel, iterations=1)
        contours, _ = cv2.findContours(binary_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours: return None
        # return the bounding with the largest area
        x, y, w, h = cv2.boundingRect(max(contours, key=cv2.contourArea))
        #display results
        '''
        cv2.rectangle(imgSRC, (x, y), (x+w, y+h), (0, 255, 0), 2)
        imgRST = cv2.bitwise_and(imgHLS, imgMSK)
        imgBGR = cv2.cvtColor(imgRST, cv2.COLOR_HLS2BGR)
        cv2.imshow("src", imgSRC)
        cv2.imshow("result", imgBGR)
        cv2.waitKey(0)
        cv2.destroyAllWindows()
        '''
        #get the center and return its coordinates
        return (x+w//2, y+h//2)

    def getSaturatorLocation(self):
        screenshot = pillowToCv2(
            mssScreenshot(
                self.robloxWindow.mx,
                self.robloxWindow.my + 100,
                self.robloxWindow.mw,
                self.robloxWindow.mh - 100,
            )
        )
        saturatorLocation = self.getSaturatorInImage(screenshot)
        if saturatorLocation is None: return None
        x,y = saturatorLocation
        if self.robloxWindow.isRetina:
            x /= 2
            y /= 2
        y += 100
        return (x,y)

    def _warn_sprinkler_model(self, message):
        if self._sprinkler_warning_shown:
            return
        print(f"[field drift compensation] {message}. Falling back to the current drift compensation method.")
        self._sprinkler_warning_shown = True

    def _load_sprinkler_model(self):
        if self._sprinkler_session is not None:
            return True
        if self._sprinkler_model_failed:
            return False
        if ort is None:
            self._sprinkler_model_failed = True
            self._warn_sprinkler_model("onnxruntime is not installed")
            return False

        model_path = settingsManager.getFuzzyAIModelPath("sprinkler.onnx")
        if not model_path or not os.path.exists(model_path):
            self._sprinkler_model_failed = True
            self._warn_sprinkler_model("sprinkler.onnx is missing")
            return False

        try:
            available = ort.get_available_providers()
            preferred = [
                "DmlExecutionProvider",
                "CUDAExecutionProvider",
                "CPUExecutionProvider",
            ]
            providers = [provider for provider in preferred if provider in available] or available
            self._sprinkler_session = ort.InferenceSession(str(model_path), providers=providers)
            input_meta = self._sprinkler_session.get_inputs()[0]
            self._sprinkler_input_name = input_meta.name
            self._sprinkler_use_float16 = "float16" in input_meta.type.lower()
            return True
        except Exception as e:
            self._sprinkler_model_failed = True
            self._warn_sprinkler_model(f"could not load sprinkler.onnx ({e})")
            return False

    def _preprocess_sprinkler_image(self, imgSRC):
        resized = cv2.resize(
            imgSRC,
            (self._sprinkler_input_size, self._sprinkler_input_size),
            interpolation=cv2.INTER_LINEAR,
        )
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        dtype = np.float16 if self._sprinkler_use_float16 else np.float32
        normalized = rgb.astype(dtype) / 255.0
        chw = np.transpose(normalized, (2, 0, 1))
        return np.expand_dims(chw, axis=0)

    def _postprocess_sprinkler_output(self, output):
        outputs = np.squeeze(output[0])
        if outputs.ndim != 2 or outputs.shape[0] < 5:
            return []

        class_probs = outputs[4:, :]
        confidences = np.max(class_probs, axis=0)
        mask = confidences > self._sprinkler_confidence_threshold
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
            self._sprinkler_confidence_threshold,
            self._sprinkler_nms_threshold,
        )

        detections = []
        if len(indices) > 0:
            for index in np.array(indices).flatten():
                bx, by, bw, bh = boxes[index]
                detections.append(
                    (
                        (bx, by, bx + bw, by + bh),
                        int(class_ids[index]),
                        float(filtered_confidences[index]),
                    )
                )
        return detections

    def _target_sprinkler_label(self):
        try:
            settings = settingsManager.loadAllSettings()
        except Exception:
            return None
        sprinkler_type = str(settings.get("sprinkler_type", "")).strip().lower()
        return self._sprinkler_type_map.get(sprinkler_type)

    def getSprinklerInImage(self, imgSRC):
        if not self._load_sprinkler_model():
            return None

        try:
            tensor = self._preprocess_sprinkler_image(imgSRC)
            output = self._sprinkler_session.run(None, {self._sprinkler_input_name: tensor})
            detections = self._postprocess_sprinkler_output(output)
        except Exception as e:
            self._sprinkler_model_failed = True
            self._warn_sprinkler_model(f"sprinkler detection failed ({e})")
            return None

        if not detections:
            return None

        target_label = self._target_sprinkler_label()
        scale_x = imgSRC.shape[1] / float(self._sprinkler_input_size)
        scale_y = imgSRC.shape[0] / float(self._sprinkler_input_size)
        best = None
        best_score = None

        for box, class_id, confidence in detections:
            label = self._sprinkler_label_map.get(class_id)
            if target_label and label != target_label:
                continue

            x1, y1, x2, y2 = box
            center_x = ((x1 + x2) / 2.0) * scale_x
            center_y = ((y1 + y2) / 2.0) * scale_y
            score = confidence

            if best is None or score > best_score:
                best = (center_x, center_y)
                best_score = score

        if best is None and target_label:
            for box, _class_id, confidence in detections:
                x1, y1, x2, y2 = box
                center_x = ((x1 + x2) / 2.0) * scale_x
                center_y = ((y1 + y2) / 2.0) * scale_y
                if best is None or confidence > best_score:
                    best = (center_x, center_y)
                    best_score = confidence

        return best

    def getSprinklerLocation(self):
        screenshot = pillowToCv2(
            mssScreenshot(
                self.robloxWindow.mx,
                self.robloxWindow.my + 100,
                self.robloxWindow.mw,
                self.robloxWindow.mh - 100,
            )
        )
        sprinklerLocation = self.getSprinklerInImage(screenshot)
        if sprinklerLocation is None:
            return None
        x, y = sprinklerLocation
        if self.robloxWindow.isRetina:
            x /= 2
            y /= 2
        y += 100
        return (x, y)
        
    def press(self, k,t):
        keyboard.keyDown(k, False)
        time.sleep(t)
        keyboard.keyUp(k, False)
        
    def slowFieldDriftCompensation(self, initialSaturatorLocation):
        winUp, winDown = self.robloxWindow.mh/2.14, self.robloxWindow.mh/1.88
        winLeft, winRight = self.robloxWindow.mw/2.14, self.robloxWindow.mw/1.88
        saturatorLocation = initialSaturatorLocation
        for _ in range(8):
            if saturatorLocation is None: break #cant find saturator
            x,y = saturatorLocation
            if x >= winLeft and x <= winRight and y >= winUp and y <= winDown: 
                break
            if x < winLeft:
                self.press("a",0.2)
            elif x > winRight:
                self.press("d",0.2)
            if y < winUp:
                self.press("w",0.2)
            elif y > winDown:
                self.press("s",0.2)

            saturatorLocation = self.getSaturatorLocation()

    #natro's field drift compensation
    #works well with fast detection times (<0.2s)
    def fastFieldDriftCompensation(self, initialSaturatorLocation):
        
        winUp, winDown = mh/2.14, mh/1.88
        winLeft, winRight = mw/2.14, mw/1.88
        hmove, vmove = "", ""
        st = time.time()
        if initialSaturatorLocation:
            x,y = initialSaturatorLocation

            #move towards saturator
            if x >= winLeft and x <= winRight and y >= winUp and y <= winDown: 
                return
            if x < winLeft:
                keyboard.keyDown("a", False)
                hmove = "a"
            elif x > winRight:
                keyboard.keyDown("d", False)
                hmove = "d"
            if y < winUp:
                keyboard.keyDown("w", False)
                vmove = "w"
            elif y > winDown:
                keyboard.keyDown("s", False)
                vmove = "s"

            i = 0
            while hmove or vmove:
                #check if reached saturator
                if (hmove == "a" and x >= winLeft) or (hmove == "d" and x <= winRight):
                    keyboard.keyUp(hmove, False)
                    hmove = ""
                    
                if (vmove == "w" and y >= winUp) or (vmove == "s" and y <= winDown):
                    keyboard.keyUp(vmove, False)
                    vmove = ""
                
                time.sleep(0.02)
                #taking too long, just give up
                if i >= 100:
                    print("give up")
                    keyboard.releaseMovement()
                    break
                #update saturator location
                saturatorLocation = self.getSaturatorLocation()
                if saturatorLocation is not None:
                    x,y = saturatorLocation

                else: #cant find saturator, pause
                    keyboard.releaseMovement()
                    #try to find saturator
                    for _ in range(10):
                        time.sleep(0.02)
                        saturatorLocation = self.getSaturatorLocation()
                        #saturator found
                        if saturatorLocation:
                            #move towards saturator
                            if hmove:
                                keyboard.keyDown(hmove)
                            if vmove:
                                keyboard.keyDown(vmove)
                            x,y = saturatorLocation
                            break
                    else: #still cant find it, give up
                        return
                i += 1
                
    def run(self):
        try:
            settings = settingsManager.loadAllSettings()
        except Exception:
            settings = {}

        use_sprinkler_model = bool(settings.get("use_sprinkler_model_for_drift_compensation", False))
        locator = self.getSprinklerLocation if use_sprinkler_model else self.getSaturatorLocation

        #calculate how fast it takes to get the saturator and determine if the fast or slow version should be used
        st = time.time()
        saturatorLocation = locator()
        timing = time.time()-st
        if timing > 0.25:
            self.slowFieldDriftCompensation(saturatorLocation)
        else:
            self.fastFieldDriftCompensation(saturatorLocation)
