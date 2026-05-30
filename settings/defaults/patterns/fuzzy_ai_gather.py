"""
Pattern: Fuzzy AI Gather
Description: Uses CoreML models for token targeting and sprinkler returns.
Best for: Blue-focused gathering where you want token chasing instead of a fixed path.
Width: Expands the leash radius and target clustering range.
Size: Scales each movement step so the pattern still respects the GUI controls.

Requirements:
- coremltools
- opencv-python
- numpy
- mss or Pillow
- best.mlpackage and sprinkler.mlpackage

- Version 2.1
"""

import math
import shutil
import subprocess
import threading
import time
from pathlib import Path

try:
    import cv2
except Exception as _cv2_error:
    cv2 = None

try:
    import numpy as np
except Exception as _numpy_error:
    np = None

try:
    import coremltools as ct
except Exception as _coreml_error:
    ct = None

try:
    import mss
except Exception:
    mss = None

try:
    from PIL import Image, ImageGrab
except Exception:
    Image = None
    ImageGrab = None


ROBLOX_VIEWPORT_WIDTH = 1364
ROBLOX_VIEWPORT_HEIGHT = 732
AT_CROP = (186, 128, 186, 124)  # left, top, right, bottom
INPUT_WIDTH = ROBLOX_VIEWPORT_WIDTH - AT_CROP[0] - AT_CROP[2]
INPUT_HEIGHT = ROBLOX_VIEWPORT_HEIGHT - AT_CROP[1] - AT_CROP[3]
SPRINKLER_INPUT_WIDTH = 736
SPRINKLER_INPUT_HEIGHT = 736
NMS_THRESHOLD = 0.5
CONFIDENCE_THRESHOLD = 0.3
SPRINKLER_CONFIDENCE_THRESHOLD = 0.6
MIN_TOKEN_DISTANCE = 0.3
IDLE_RETURN_INTERVAL = 1.5
NO_TARGET_SWEEP_INTERVAL = 0.35
NO_TOKEN_RECALIBRATION_TIMEOUT = 12.0
MOVEMENTS_BEFORE_RECALIBRATION = 10
SPRINKLER_ARRIVAL_THRESHOLD = 0.8
MAX_SPRINKLER_DISTANCE = 10.0
SPRINKLER_RESCAN_ATTEMPTS = 3
SPRINKLER_RESCAN_DELAY = 0.3
TARGET_SPRINKLER_LABEL = None
DEBUG_MODE = False
RECORD_VIDEO = False
RECORD_VIDEO_FPS = 12.0
CONTINUOUS_SCAN_INTERVAL = 0.08
CONTINUOUS_MIN_REPLAN_DISTANCE = 0.08
TARGET_LOCK_REACHED_DISTANCE = 0.18
TARGET_LOCK_LOST_TIMEOUT = 0.9
TARGET_LOCK_SWITCH_SCORE_MULTIPLIER = 2.25
TARGET_LOCK_SWITCH_DISTANCE = 1.25
ANCHOR_REFRESH_INTERVAL = 0.75
ANCHOR_MAX_PASSIVE_DISTANCE = 8.0
LEASH_HARD_MARGIN = 2.5
LEASH_NEAR_TOKEN_ALLOWANCE = 2.25

PREFERRED_TOKENS = {}
PREFERRED_TOKEN_RANKS = {}
IGNORED_TOKENS = {}

NORMALIZED_CAL_RATIOS = [
    (0.395314, 0.427995),
    (0.597795, 0.430686),
    (0.320584, 0.721513),
    (0.670597, 0.722439),
]

LABELS_TOKENS = {
    0: "Activated Target", 1: "Baby Love", 2: "Beamstorm", 3: "Beesmas Cheer Token",
    4: "Black Bear Morph", 5: "Bloom", 6: "Blue Bomb Sync", 7: "Blue Boost",
    8: "Blueberry", 9: "Bomb", 10: "Brown Bear Morph", 11: "Coconut",
    12: "ComboCoconut", 13: "Duped Baby Love", 14: "Duped Beamstorm",
    15: "Duped Beesmas Cheer Token", 16: "Duped Black Bear Morph",
    17: "Duped Blue Bomb Sync", 18: "Duped Blue Boost", 19: "Duped Blueberry",
    20: "Duped Bomb", 21: "Duped Brown Bear Morph", 22: "Duped Festive Blessing Token",
    23: "Duped Festive Gift Token", 24: "Duped Festive Mark Token", 25: "Duped Fetch",
    26: "Duped Flame Fuel", 27: "Duped Focus", 28: "Duped Fuzz Bombs Token",
    29: "Duped Glitch Token", 30: "Duped Glob", 31: "Duped Gumdrop Barrage",
    32: "Duped Haste", 33: "Duped Honey Mark Token", 34: "Duped Honey Token",
    35: "Duped Impale", 36: "Duped Inferno Token", 37: "Duped Inflate Balloons",
    38: "Duped Inspire Token", 39: "Duped Jelly Bean", 40: "Duped Map Corruption",
    41: "Duped Mark Surge Token", 42: "Duped Melody", 43: "Duped Mind Hack",
    44: "Duped Mother Bear Morph", 45: "Duped Panda Bear Morph", 46: "Duped Pineapple",
    47: "Duped Polar Bear Morph", 48: "Duped Pollen Haze", 49: "Duped Pollen Mark Token",
    50: "Duped Pulse", 51: "Duped Puppy Love", 52: "Duped Rage Token",
    53: "Duped Rain Cloud", 54: "Duped Red Bomb Sync", 55: "Duped Red Boost",
    56: "Duped Science Bear Morph", 57: "Duped Scratch", 58: "Duped Snowflake",
    59: "Duped Snowglobe Shake", 60: "Duped Strawberry", 61: "Duped Summon Frog Token",
    62: "Duped Sunflower Seed", 63: "Duped Surprise Party", 64: "Duped Tabby Love",
    65: "Duped Target Practice Token", 66: "Duped Token Link", 67: "Duped Tornado",
    68: "Duped Treat", 69: "Duped Triangulate Token", 70: "Duped White Boost",
    71: "Falling Star", 72: "Festive Blessing Token", 73: "Festive Gift Token",
    74: "Festive Mark Station", 75: "Festive Mark Token", 76: "Fetch",
    77: "Flame Fuel", 78: "Focus", 79: "Fully Collected Target",
    80: "Fuzz Bombs Token", 81: "Glitch Token", 82: "Glob",
    83: "Gumdrop Barrage", 84: "Haste", 85: "Honey Mark Station",
    86: "Honey Mark Token", 87: "Honey Token", 88: "Impale",
    89: "Inferno Token", 90: "Inflate Balloons", 91: "Inspire Token",
    92: "Jelly Bean", 93: "Map Corruption", 94: "Mark Surge Token",
    95: "Melody", 96: "Mind Hack", 97: "Mother Bear Morph",
    98: "Panda Bear Morph", 99: "Pineapple", 100: "Polar Bear Morph",
    101: "Pollen Haze", 102: "Pollen Mark Station", 103: "Pollen Mark Token",
    104: "Precise Mark Station", 105: "Precise Mark Target", 106: "Pulse",
    107: "Puppy Love", 108: "Rage Token", 109: "Rain Cloud",
    110: "Red Bomb Sync", 111: "Red Boost", 112: "Science Bear Morph",
    113: "Scratch", 114: "Smiley", 115: "Snowflake",
    116: "Snowglobe Shake", 117: "Strawberry", 118: "Summon Frog Token",
    119: "Sunflower Seed", 120: "Surprise Party", 121: "Tabby Love",
    122: "Target Practice Token", 123: "TennisBall", 124: "Token Link",
    125: "Tornado", 126: "Treat", 127: "Triangulate Token",
    128: "Unactivated Target", 129: "White Boost",
}

LABELS_SPRINKLER = {
    0: "Sprinkler",
    1: "Supreme",
}


def _coerce_float(value, default):
    try:
        return float(value)
    except Exception:
        return float(default)


def _coerce_int(value, default):
    try:
        return int(float(value))
    except Exception:
        return int(default)


def _coerce_text(value, default=""):
    if value is None:
        return default
    return str(value).strip()


def _coerce_bool(value, default=False):
    if isinstance(value, bool):
        return value
    if value is None:
        return bool(default)
    text = str(value).strip().lower()
    if text in ("1", "true", "yes", "y", "on", "enabled", "enable"):
        return True
    if text in ("0", "false", "no", "n", "off", "disabled", "disable"):
        return False
    return bool(default)


def _parse_token_names(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        items = value
    else:
        items = str(value).replace("\n", ",").split(",")
    out = []
    seen = set()
    for item in items:
        name = str(item).strip()
        if name and name not in seen:
            out.append(name)
            seen.add(name)
    return out


def _preferred_token_weights(value, default_weights):
    names = _parse_token_names(value)
    if not names:
        return dict(default_weights)

    max_weight = 100
    step = 5
    out = {}
    for index, name in enumerate(names):
        out[name] = max(max_weight - (index * step), 5)
    return out


def _ignored_token_names(value, default_names):
    names = _parse_token_names(value)
    if not names:
        return set(default_names)
    return set(names)


def _project_root():
    try:
        return Path(__file__).resolve().parents[2]
    except Exception:
        return Path.cwd().resolve()


MODEL_DIR = (_project_root() / "src" / "data" / "models").resolve()


CONFIDENCE_THRESHOLD = _coerce_float(globals().get("pattern_confidence_threshold"), CONFIDENCE_THRESHOLD)
SPRINKLER_CONFIDENCE_THRESHOLD = _coerce_float(
    globals().get("pattern_sprinkler_confidence_threshold"),
    SPRINKLER_CONFIDENCE_THRESHOLD,
)
MIN_TOKEN_DISTANCE = _coerce_float(globals().get("pattern_min_token_distance"), MIN_TOKEN_DISTANCE)
IDLE_RETURN_INTERVAL = _coerce_float(globals().get("pattern_idle_return_interval"), IDLE_RETURN_INTERVAL)
NO_TARGET_SWEEP_INTERVAL = _coerce_float(
    globals().get("pattern_no_target_sweep_interval"),
    NO_TARGET_SWEEP_INTERVAL,
)
NO_TOKEN_RECALIBRATION_TIMEOUT = _coerce_float(
    globals().get("pattern_no_token_recalibration_timeout"),
    NO_TOKEN_RECALIBRATION_TIMEOUT,
)
MOVEMENTS_BEFORE_RECALIBRATION = _coerce_int(
    globals().get("pattern_movements_before_recalibration"),
    MOVEMENTS_BEFORE_RECALIBRATION,
)
SPRINKLER_ARRIVAL_THRESHOLD = _coerce_float(
    globals().get("pattern_sprinkler_arrival_threshold"),
    SPRINKLER_ARRIVAL_THRESHOLD,
)
MAX_SPRINKLER_DISTANCE = _coerce_float(
    globals().get("pattern_max_sprinkler_distance"),
    MAX_SPRINKLER_DISTANCE,
)
SPRINKLER_RESCAN_ATTEMPTS = _coerce_int(
    globals().get("pattern_sprinkler_rescan_attempts"),
    SPRINKLER_RESCAN_ATTEMPTS,
)
SPRINKLER_RESCAN_DELAY = _coerce_float(
    globals().get("pattern_sprinkler_rescan_delay"),
    SPRINKLER_RESCAN_DELAY,
)
TARGET_SPRINKLER_LABEL = _coerce_text(
    globals().get("pattern_target_sprinkler_label"),
    "",
) or None
FIELD_DRIFT_COMPENSATION = _coerce_bool(globals().get("pattern_field_drift_compensation"), False)
USE_SPRINKLER_MODEL_FOR_DRIFT_COMPENSATION = _coerce_bool(
    globals().get("pattern_use_sprinkler_model_for_drift_compensation"),
    False,
)
CAPTURE_BACKEND = _coerce_text(globals().get("pattern_capture_backend"), "auto").lower()
DEBUG_MODE = _coerce_bool(globals().get("pattern_debug_mode"), DEBUG_MODE)
RECORD_VIDEO = _coerce_bool(globals().get("pattern_record_video"), RECORD_VIDEO)
RECORD_VIDEO_FPS = _coerce_float(globals().get("pattern_record_video_fps"), RECORD_VIDEO_FPS)
PREFERRED_TOKENS = _preferred_token_weights(globals().get("pattern_preferred_tokens"), PREFERRED_TOKENS)
PREFERRED_TOKEN_RANKS = {name: index for index, name in enumerate(PREFERRED_TOKENS.keys())}
IGNORED_TOKENS = _ignored_token_names(globals().get("pattern_ignored_tokens"), IGNORED_TOKENS)


try:
    size = float(size)
except Exception:
    if sizeword.lower() == "xs":
        size = 0.25
    elif sizeword.lower() == "s":
        size = 0.5
    elif sizeword.lower() == "l":
        size = 1.5
    elif sizeword.lower() == "xl":
        size = 2
    else:
        size = 1

try:
    width = int(width)
except Exception:
    width = 1


def _default_points(screen_w, screen_h):
    return np.array(
        [[int(round(nx * screen_w)), int(round(ny * screen_h))] for nx, ny in NORMALIZED_CAL_RATIOS],
        dtype=np.float32,
    )


def _preprocess(frame, input_width, input_height, use_float16, crop=None, resize=True):
    if crop:
        left, top, width_px, height_px = crop
        frame = frame[top:top + height_px, left:left + width_px]

    if resize or frame.shape[1] != int(input_width) or frame.shape[0] != int(input_height):
        if not resize:
            _debug_log(
                f"token crop was {frame.shape[1]}x{frame.shape[0]}, resizing to {input_width}x{input_height}",
                min_interval=5.0,
                key="token_crop_resize_fallback",
            )
        frame = cv2.resize(frame, (int(input_width), int(input_height)), interpolation=cv2.INTER_LINEAR)

    if frame.ndim == 3 and frame.shape[2] == 4:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB)
    else:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    dtype = np.float16 if use_float16 else np.float32
    normalized = rgb.astype(dtype) / 255.0
    chw = np.transpose(normalized, (2, 0, 1))
    return np.expand_dims(chw, axis=0)


def _preprocess_token_frame(frame, runtime):
    if runtime.get("token_frame_is_crop"):
        cropped = frame
    else:
        left, top, width_px, height_px = runtime["token_crop"]
        cropped = frame[top:top + height_px, left:left + width_px]

    if cropped.shape[1] != INPUT_WIDTH or cropped.shape[0] != INPUT_HEIGHT:
        cropped = cv2.resize(cropped, (INPUT_WIDTH, INPUT_HEIGHT), interpolation=cv2.INTER_LINEAR)

    if cropped.ndim == 3 and cropped.shape[2] == 4:
        rgb = cv2.cvtColor(cropped, cv2.COLOR_BGRA2RGB)
    else:
        rgb = cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB)

    if runtime.get("token_model_kind") == "opencv_onnx":
        normalized = rgb.astype(np.float32) / 255.0
        chw = np.transpose(normalized, (2, 0, 1))
        return np.expand_dims(chw, axis=0)

    if Image is None:
        raise RuntimeError("Pillow is required for CoreML token inference.")
    return Image.fromarray(rgb)


def _preprocess_coreml_image(frame, input_width, input_height):
    if frame.shape[1] != int(input_width) or frame.shape[0] != int(input_height):
        frame = cv2.resize(frame, (int(input_width), int(input_height)), interpolation=cv2.INTER_LINEAR)

    if frame.ndim == 3 and frame.shape[2] == 4:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB)
    else:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    if Image is None:
        raise RuntimeError("Pillow is required for CoreML inference.")
    return Image.fromarray(rgb)


def _preprocess_onnx_image(frame, input_width, input_height):
    if frame.shape[1] != int(input_width) or frame.shape[0] != int(input_height):
        frame = cv2.resize(frame, (int(input_width), int(input_height)), interpolation=cv2.INTER_LINEAR)

    if frame.ndim == 3 and frame.shape[2] == 4:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB)
    else:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    normalized = rgb.astype(np.float32) / 255.0
    chw = np.transpose(normalized, (2, 0, 1))
    return np.expand_dims(chw, axis=0)


def _postprocess(output, confidence_threshold):
    outputs = np.squeeze(output[0])
    if outputs.ndim != 2 or outputs.shape[0] < 5:
        return []

    class_probs = outputs[4:, :]
    confidences = np.max(class_probs, axis=0)
    mask = confidences > confidence_threshold

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
        confidence_threshold,
        NMS_THRESHOLD,
    )

    detections = []
    if len(indices) > 0:
        for index in np.array(indices).flatten():
            bx, by, bw, bh = boxes[index]
            detections.append(((bx, by, bx + bw, by + bh), int(class_ids[index]), float(filtered_confidences[index])))
    return detections


def _postprocess_tokens(output, confidence_threshold):
    pred = output[0]
    if pred.ndim != 3 or pred.shape[0] < 1 or pred.shape[2] < 6:
        return []

    detections = []
    for row in pred[0]:
        x1, y1, x2, y2, confidence, class_id = row[:6]
        confidence = float(confidence)
        if confidence < confidence_threshold:
            continue

        x1 = float(x1)
        y1 = float(y1)
        x2 = float(x2)
        y2 = float(y2)
        if x2 <= x1 or y2 <= y1:
            continue

        detections.append(((x1, y1, x2, y2), int(round(float(class_id))), confidence))
    return detections


def _debug_log(message, min_interval=0.0, key=None):
    if not DEBUG_MODE:
        return

    now = time.time()
    log_state = globals().setdefault("_FUZZY_AI_DEBUG_LOG_TIMES", {})
    log_key = key or message
    last = log_state.get(log_key, 0.0)
    if min_interval > 0 and now - last < min_interval:
        return

    log_state[log_key] = now
    print(f"[fuzzy_ai_gather][debug] {message}", flush=True)


def _runtime_state():
    state = getattr(self, "_fuzzy_ai_gather_state", None)
    if isinstance(state, dict):
        return state

    state = globals().get("_FUZZY_AI_GATHER_STATE")
    if not isinstance(state, dict):
        state = {}
        globals()["_FUZZY_AI_GATHER_STATE"] = state

    try:
        setattr(self, "_fuzzy_ai_gather_state", state)
    except Exception:
        pass

    return state


def _build_capture():
    viewport = getattr(self, "robloxWindow", None)
    if viewport is not None:
        left = int(getattr(viewport, "mx", 0))
        top = int(getattr(viewport, "my", 0))
        width_px = int(getattr(viewport, "mw", 0))
        height_px = int(getattr(viewport, "mh", 0))
    else:
        left = 0
        top = 0
        width_px = 0
        height_px = 0

    if CAPTURE_BACKEND in ("auto", "mss") and mss is not None:
        session = mss.mss()
        if width_px <= 0 or height_px <= 0:
            monitor = session.monitors[1]
            left = int(monitor["left"])
            top = int(monitor["top"])
            width_px = int(monitor["width"])
            height_px = int(monitor["height"])
        monitor = {"left": left, "top": top, "width": width_px, "height": height_px}
        return {
            "backend": "mss",
            "session": session,
            "monitor": monitor,
            "width": width_px,
            "height": height_px,
        }

    if CAPTURE_BACKEND in ("auto", "pil", "pillow") and ImageGrab is not None:
        if width_px <= 0 or height_px <= 0:
            width_px, height_px = ImageGrab.grab().size
            left = 0
            top = 0
        return {
            "backend": "pil",
            "bbox": (left, top, left + width_px, top + height_px),
            "width": width_px,
            "height": height_px,
        }

    raise RuntimeError(f"No supported capture backend found for '{CAPTURE_BACKEND}'. Install mss or Pillow.")


def _grab_frame(runtime):
    if runtime["capture"]["backend"] == "mss":
        monitor = runtime["capture"]["monitor"]
        return _mss_grab_to_array(runtime["capture"]["session"], monitor)

    image = ImageGrab.grab(bbox=runtime["capture"].get("bbox"))
    return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)


def _grab_token_frame(runtime):
    capture = runtime["capture"]
    token_monitor = runtime.get("token_monitor")
    if capture["backend"] == "mss" and token_monitor:
        return _mss_grab_to_array(capture["session"], token_monitor)

    token_bbox = runtime.get("token_bbox")
    if token_bbox:
        image = ImageGrab.grab(bbox=token_bbox)
        return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)

    return _grab_frame(runtime)


def _mss_grab_to_array(session, monitor):
    shot = session.grab(monitor)
    return np.frombuffer(shot.raw, dtype=np.uint8).reshape((shot.height, shot.width, 4))


def _token_crop_for_capture(capture):
    capture_w = int(capture["width"])
    capture_h = int(capture["height"])

    left = int(round(capture_w * (AT_CROP[0] / ROBLOX_VIEWPORT_WIDTH)))
    top = int(round(capture_h * (AT_CROP[1] / ROBLOX_VIEWPORT_HEIGHT)))
    right = int(round(capture_w * (AT_CROP[2] / ROBLOX_VIEWPORT_WIDTH)))
    bottom = int(round(capture_h * (AT_CROP[3] / ROBLOX_VIEWPORT_HEIGHT)))
    crop_w = max(capture_w - left - right, 1)
    crop_h = max(capture_h - top - bottom, 1)
    resize = crop_w != INPUT_WIDTH or crop_h != INPUT_HEIGHT
    return {"rect": (left, top, crop_w, crop_h), "resize": resize}


def _model_point_to_capture(runtime, x, y):
    left, top, crop_w, crop_h = runtime["token_crop"]
    return (
        left + (x * crop_w / float(INPUT_WIDTH)),
        top + (y * crop_h / float(INPUT_HEIGHT)),
    )


def _bgr_frame(frame):
    if frame.ndim == 3 and frame.shape[2] == 4:
        return cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
    return frame.copy()


def _recording_dir():
    path = _project_root() / "src" / "data" / "user" / "fuzzy_ai_recordings"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _ensure_video_writer(runtime, frame):
    if not RECORD_VIDEO or cv2 is None:
        return None

    writer = runtime.get("video_writer")
    if writer is not None:
        return writer

    bgr = _bgr_frame(frame)
    height, width_px = bgr.shape[:2]
    filename = f"fuzzy_ai_gather_{time.strftime('%Y%m%d_%H%M%S')}.mp4"
    output_path = _recording_dir() / filename

    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        command = [
            ffmpeg_path,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "bgr24",
            "-s",
            f"{width_px}x{height}",
            "-r",
            str(max(RECORD_VIDEO_FPS, 1.0)),
            "-i",
            "-",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "frag_keyframe+empty_moov+default_base_moof",
            str(output_path),
        ]
        try:
            process = subprocess.Popen(command, stdin=subprocess.PIPE)
            writer = {"kind": "ffmpeg", "process": process, "path": str(output_path)}
        except Exception as exc:
            writer = None
            _debug_log(f"ffmpeg recording failed to start: {exc}", min_interval=5.0, key="record_ffmpeg_failed")
    else:
        writer = None

    if writer is None:
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        cv_writer = cv2.VideoWriter(str(output_path), fourcc, max(RECORD_VIDEO_FPS, 1.0), (width_px, height))
        if not cv_writer.isOpened():
            runtime["video_writer"] = None
            _debug_log(f"video recording failed to open: {output_path}", min_interval=5.0, key="record_open_failed")
            return None
        writer = {"kind": "opencv", "writer": cv_writer, "path": str(output_path)}

    runtime["video_writer"] = writer
    runtime["video_path"] = str(output_path)
    runtime["recording_stop_event"] = threading.Event()
    runtime["recording_lock"] = threading.Lock()
    runtime["recording_thread"] = threading.Thread(target=_recording_thread, args=(runtime,), daemon=True)
    runtime["recording_thread"].start()
    _debug_log(f"recording AI gather video to {output_path}")
    return writer


def _release_video_writer(runtime=None):
    if runtime is None:
        runtime = _runtime_state()
    writer = runtime.get("video_writer") if isinstance(runtime, dict) else None
    if writer is not None:
        stop_event = runtime.get("recording_stop_event")
        if stop_event is not None:
            stop_event.set()
        thread = runtime.get("recording_thread")
        if thread is not None and thread.is_alive() and thread is not threading.current_thread():
            try:
                thread.join(timeout=2)
            except Exception:
                pass
        try:
            if isinstance(writer, dict) and writer.get("kind") == "ffmpeg":
                process = writer.get("process")
                if process and process.stdin:
                    process.stdin.close()
                if process:
                    process.wait(timeout=5)
            elif isinstance(writer, dict) and writer.get("kind") == "opencv":
                writer["writer"].release()
            else:
                writer.release()
        except Exception:
            pass
        runtime["video_writer"] = None
        runtime["recording_thread"] = None
        runtime["recording_stop_event"] = None
        if runtime.get("video_path"):
            _debug_log(f"saved AI gather recording: {runtime['video_path']}")


def onGatherEnd():
    _stop_scanner_thread()
    _release_video_writer()


def _draw_label(frame, text, x, y, color):
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.45
    thickness = 1
    (text_w, text_h), baseline = cv2.getTextSize(text, font, font_scale, thickness)
    y = max(y, text_h + 6)
    cv2.rectangle(frame, (x, y - text_h - baseline - 4), (x + text_w + 4, y + 2), color, -1)
    cv2.putText(frame, text, (x + 2, y - baseline - 1), font, font_scale, (0, 0, 0), thickness, cv2.LINE_AA)


def _record_debug_frame(runtime, frame, detections, target):
    if runtime.get("video_writer") is None:
        frame = _grab_frame(runtime)

    writer = _ensure_video_writer(runtime, frame)
    if writer is None:
        return

    runtime["latest_recording_overlay"] = {
        "detections": list(detections),
        "target": dict(target) if isinstance(target, dict) else None,
        "current_x": runtime.get("current_x", 0.0),
        "current_y": runtime.get("current_y", 0.0),
        "movement_count": runtime.get("movement_count", 0),
        "detection_fps": runtime.get("detection_fps"),
        "last_detection_ms": runtime.get("last_detection_ms"),
        "last_timing_ms": dict(runtime.get("last_timing_ms", {})),
        "candidate_count": runtime.get("last_candidate_count", 0),
        "rejected_tokens": list(runtime.get("last_rejected_tokens", [])),
        "sprinkler": dict(runtime.get("last_sprinkler_detection", {})),
        "anchor": dict(runtime.get("last_anchor", {})),
        "sprinkler_status": runtime.get("last_sprinkler_status", ""),
        "target_sprinkler_label": TARGET_SPRINKLER_LABEL or "",
        "field_drift_compensation": FIELD_DRIFT_COMPENSATION,
        "use_sprinkler_model_for_drift_compensation": USE_SPRINKLER_MODEL_FOR_DRIFT_COMPENSATION,
        "preferred_tokens": list(PREFERRED_TOKENS.keys())[:8],
        "ignored_count": len(IGNORED_TOKENS),
        "updated_at": time.time(),
    }


def _annotate_recording_frame(runtime, frame):
    annotated = _bgr_frame(frame)
    frame_h, frame_w = annotated.shape[:2]

    overlay = runtime.get("latest_recording_overlay", {})
    detections = overlay.get("detections", [])
    target = overlay.get("target")
    target_box = target.get("box") if isinstance(target, dict) else None

    for box, class_id, confidence in detections:
        token_name = LABELS_TOKENS.get(class_id, f"class {class_id}")
        x1, y1, x2, y2 = box
        left_f, top_f = _model_point_to_capture(runtime, x1, y1)
        right_f, bottom_f = _model_point_to_capture(runtime, x2, y2)
        left = max(0, min(frame_w - 1, int(round(left_f))))
        top = max(0, min(frame_h - 1, int(round(top_f))))
        right = max(0, min(frame_w - 1, int(round(right_f))))
        bottom = max(0, min(frame_h - 1, int(round(bottom_f))))
        is_target = target_box == box
        if token_name in IGNORED_TOKENS:
            color = (120, 120, 120)
        elif is_target:
            color = (0, 255, 255)
        else:
            color = (80, 220, 80)
        cv2.rectangle(annotated, (left, top), (right, bottom), color, 2 if is_target else 1)
        _draw_label(annotated, f"{token_name} {confidence:.2f}", left, top - 4, color)

    sprinkler = overlay.get("sprinkler") or {}
    sprinkler_box = sprinkler.get("box")
    if sprinkler_box:
        x1, y1, x2, y2 = sprinkler_box
        left = max(0, min(frame_w - 1, int(round(x1))))
        top = max(0, min(frame_h - 1, int(round(y1))))
        right = max(0, min(frame_w - 1, int(round(x2))))
        bottom = max(0, min(frame_h - 1, int(round(y2))))
        cv2.rectangle(annotated, (left, top), (right, bottom), (255, 180, 0), 3)
        match_text = "match" if sprinkler.get("target_match") else "seen"
        _draw_label(
            annotated,
            f"sprinkler {match_text} {sprinkler.get('label', '?')} {sprinkler.get('confidence', 0.0):.2f} d={sprinkler.get('distance', 0.0):.2f}",
            left,
            top - 4,
            (255, 180, 0),
        )

    anchor = overlay.get("anchor") or {}
    status_lines = [
        f"tokens={len(detections)} candidates={overlay.get('candidate_count', 0)} pos=({overlay.get('current_x', 0.0):.2f},{overlay.get('current_y', 0.0):.2f}) moves={overlay.get('movement_count', 0)}",
        f"target={target['name']} score={target['score']:.2f} move=({target['tx']:.2f},{target['ty']:.2f})" if target else "target=None",
        f"sprinkler_status={overlay.get('sprinkler_status', '')} target={overlay.get('target_sprinkler_label', '') or 'any'} drift={overlay.get('field_drift_compensation')} model={overlay.get('use_sprinkler_model_for_drift_compensation')}",
    ]
    if anchor:
        age = max(0.0, time.time() - float(anchor.get("time", time.time())))
        status_lines.append(
            f"anchor=({anchor.get('x', 0.0):.2f},{anchor.get('y', 0.0):.2f}) sprinkler=({anchor.get('sprinkler_tx', 0.0):.2f},{anchor.get('sprinkler_ty', 0.0):.2f}) age={age:.1f}s"
        )
    rejected = overlay.get("rejected_tokens", [])
    if rejected:
        summary = []
        for item in rejected[:4]:
            name = item.get("name", f"class {item.get('class_id', '?')}")
            reason = item.get("reason", "?")
            if "distance" in item:
                summary.append(f"{name}:{reason}:{item['distance']:.1f}")
            elif "future_dist" in item:
                summary.append(f"{name}:{reason}:{item['future_dist']:.1f}")
            else:
                summary.append(f"{name}:{reason}")
        status_lines.append("skip " + ", ".join(summary))
    for index, line in enumerate(status_lines):
        _draw_label(annotated, line, 10, 24 + (index * 24), (255, 255, 255))

    detection_fps = overlay.get("detection_fps")
    detection_ms = overlay.get("last_detection_ms")
    fps_text = "detect FPS: --" if detection_fps is None else f"detect FPS: {detection_fps:.1f}"
    if detection_ms is not None:
        fps_text += f" ({detection_ms:.0f}ms)"
    (text_w, _text_h), _baseline = cv2.getTextSize(fps_text, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
    _draw_label(annotated, fps_text, max(10, frame_w - text_w - 18), 24, (255, 255, 255))
    timing = overlay.get("last_timing_ms") or {}
    if timing:
        timing_text = (
            f"cap {timing.get('screenshot', 0.0):.0f} "
            f"prep {timing.get('preprocess', 0.0):.0f} "
            f"infer {timing.get('inference', 0.0):.0f} "
            f"post {timing.get('postprocess', 0.0):.0f} "
            f"score {timing.get('scoring', 0.0):.0f}ms"
        )
        (timing_w, _timing_h), _timing_baseline = cv2.getTextSize(timing_text, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
        _draw_label(annotated, timing_text, max(10, frame_w - timing_w - 18), 48, (255, 255, 255))

    return annotated


def _recording_thread(runtime):
    frame_interval = 1.0 / max(RECORD_VIDEO_FPS, 1.0)
    next_frame_time = time.time()
    stop_event = runtime.get("recording_stop_event")
    recording_session = None
    if runtime["capture"]["backend"] == "mss" and mss is not None:
        recording_session = mss.mss()

    try:
        while stop_event is not None and not stop_event.is_set():
            now = time.time()
            if now < next_frame_time:
                time.sleep(min(next_frame_time - now, 0.05))
                continue

            try:
                if recording_session is not None:
                    frame = _mss_grab_to_array(recording_session, runtime["capture"]["monitor"])
                else:
                    frame = _grab_frame(runtime)
                annotated = _annotate_recording_frame(runtime, frame)
                writer = runtime.get("video_writer")
                if writer is None:
                    return
                _write_recording_frame(runtime, writer, annotated, frame_count=1)
            except Exception as exc:
                _debug_log(f"recording frame failed: {exc}", min_interval=5.0, key="record_frame_failed")

            next_frame_time += frame_interval
            if next_frame_time < time.time() - frame_interval:
                next_frame_time = time.time() + frame_interval
    finally:
        if recording_session is not None:
            try:
                recording_session.close()
            except Exception:
                pass


def _write_recording_frame(runtime, writer, annotated, frame_count=1):
    try:
        lock = runtime.get("recording_lock")
        if lock is None:
            lock = threading.Lock()
            runtime["recording_lock"] = lock
        with lock:
            if isinstance(writer, dict) and writer.get("kind") == "ffmpeg":
                process = writer.get("process")
                if process and process.stdin and process.poll() is None:
                    payload = annotated.tobytes()
                    for _ in range(frame_count):
                        process.stdin.write(payload)
            elif isinstance(writer, dict) and writer.get("kind") == "opencv":
                for _ in range(frame_count):
                    writer["writer"].write(annotated)
            else:
                for _ in range(frame_count):
                    writer.write(annotated)
    except Exception as exc:
        _debug_log(f"recording write failed: {exc}", min_interval=5.0, key="record_write_failed")
        _release_video_writer(runtime)


def _update_detection_fps(runtime, elapsed):
    if elapsed <= 0:
        return
    fps = 1.0 / elapsed
    previous = runtime.get("detection_fps")
    runtime["detection_fps"] = fps if previous is None else ((previous * 0.8) + (fps * 0.2))
    runtime["last_detection_ms"] = elapsed * 1000.0


def _scan_tokens_once(runtime):
    detection_start = time.time()
    screenshot_start = time.time()
    frame = _grab_token_frame(runtime)
    screenshot_elapsed = time.time() - screenshot_start
    preprocess_start = time.time()
    image = _preprocess_token_frame(frame, runtime)
    preprocess_elapsed = time.time() - preprocess_start
    inference_start = time.time()
    output = _run_model(runtime, "token", image)
    inference_elapsed = time.time() - inference_start
    postprocess_start = time.time()
    detections = _postprocess_tokens(output, CONFIDENCE_THRESHOLD)
    postprocess_elapsed = time.time() - postprocess_start
    _refresh_sprinkler_anchor(runtime)
    scoring_start = time.time()
    target = _find_best_token(runtime, detections)
    if (
        target is None
        and not runtime.get("movement_active")
        and any(item.get("reason") in ("leash", "hard_leash") for item in runtime.get("last_rejected_tokens", []))
        and _refresh_sprinkler_anchor(runtime, force=True)
    ):
        target = _find_best_token(runtime, detections)
    scoring_elapsed = time.time() - scoring_start
    total_elapsed = time.time() - detection_start

    runtime["last_timing_ms"] = {
        "screenshot": screenshot_elapsed * 1000.0,
        "preprocess": preprocess_elapsed * 1000.0,
        "inference": inference_elapsed * 1000.0,
        "postprocess": postprocess_elapsed * 1000.0,
        "scoring": scoring_elapsed * 1000.0,
        "total": total_elapsed * 1000.0,
    }
    _debug_log(
        "timing "
        f"screenshot={runtime['last_timing_ms']['screenshot']:.1f}ms "
        f"preprocess={runtime['last_timing_ms']['preprocess']:.1f}ms "
        f"inference={runtime['last_timing_ms']['inference']:.1f}ms "
        f"postprocess={runtime['last_timing_ms']['postprocess']:.1f}ms "
        f"scoring={runtime['last_timing_ms']['scoring']:.1f}ms "
        f"total={runtime['last_timing_ms']['total']:.1f}ms",
        min_interval=1.0,
        key="timing",
    )
    _update_detection_fps(runtime, total_elapsed)
    _record_debug_frame(runtime, frame, detections, target)

    now = time.time()
    scan_lock = runtime.get("scan_lock")
    if scan_lock is None:
        scan_lock = threading.Lock()
        runtime["scan_lock"] = scan_lock
    with scan_lock:
        runtime["latest_detections"] = detections
        runtime["latest_target"] = target
        runtime["latest_scan_time"] = now

    return detections, target


def _same_token_candidate(a, b):
    if not isinstance(a, dict) or not isinstance(b, dict):
        return False
    if a.get("name") != b.get("name"):
        return False
    ax = a.get("future_x")
    ay = a.get("future_y")
    bx = b.get("future_x")
    by = b.get("future_y")
    if ax is None or ay is None or bx is None or by is None:
        return False
    return math.hypot(float(ax) - float(bx), float(ay) - float(by)) <= TARGET_LOCK_SWITCH_DISTANCE


def _scanner_loop(runtime):
    stop_event = runtime.get("scanner_stop_event")
    while stop_event is not None and not stop_event.is_set():
        try:
            if not runtime.get("ready"):
                return
            _scan_tokens_once(runtime)
        except Exception as exc:
            runtime["ready"] = False
            runtime["error"] = str(exc)
            _release_video_writer(runtime)
            _debug_log(f"scanner error: {exc}", min_interval=1.0, key="scanner_error")
            return
        time.sleep(max(CONTINUOUS_SCAN_INTERVAL, 0.01))


def _ensure_scanner_thread(runtime):
    thread = runtime.get("scanner_thread")
    if thread is not None and thread.is_alive():
        return

    stop_event = runtime.get("scanner_stop_event")
    if stop_event is None or stop_event.is_set():
        stop_event = threading.Event()
        runtime["scanner_stop_event"] = stop_event

    thread = threading.Thread(target=_scanner_loop, args=(runtime,), daemon=True)
    runtime["scanner_thread"] = thread
    thread.start()
    _debug_log("continuous token scanner started", min_interval=1.0, key="scanner_started")


def _stop_scanner_thread(runtime=None):
    if runtime is None:
        runtime = _runtime_state()
    if not isinstance(runtime, dict):
        return

    stop_event = runtime.get("scanner_stop_event")
    if stop_event is not None:
        stop_event.set()

    thread = runtime.get("scanner_thread")
    if thread is not None and thread.is_alive() and thread is not threading.current_thread():
        try:
            thread.join(timeout=1)
        except Exception:
            pass
    runtime["scanner_thread"] = None


def _load_coreml_model(model_path):
    if ct is None:
        raise RuntimeError("coremltools is required for AI token gathering. Install coremltools, then restart the macro.")

    model = ct.models.MLModel(str(model_path), compute_units=ct.ComputeUnit.ALL)
    description = model.get_spec().description
    input_name = description.input[0].name
    output_name = description.output[0].name
    return model, input_name, output_name


def _load_onnx_model(model_path):
    if cv2 is None:
        raise RuntimeError("OpenCV is required for ONNX AI gathering.")

    model = cv2.dnn.readNetFromONNX(str(model_path))
    return model, None, None


def _delete_model_path(model_path):
    try:
        path = Path(model_path)
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()
    except Exception as exc:
        _debug_log(f"could not delete alternate model {model_path}: {exc}", min_interval=10.0, key=f"delete_model_{model_path}")


def _run_model(runtime, prefix, image):
    if runtime.get(f"{prefix}_model_kind") == "opencv_onnx":
        session = runtime[f"{prefix}_session"]
        session.setInput(image)
        return [session.forward()]

    return [
        runtime[f"{prefix}_session"].predict(
            {runtime[f"{prefix}_input"]: image}
        )[runtime[f"{prefix}_output"]]
    ]


def _relative_distance(x, y, homography):
    point = np.array([[[x, y + 15]]], dtype=np.float32)
    transformed = cv2.perspectiveTransform(point, homography)
    tx, ty = transformed[0][0]
    return float(tx), float(-ty)


def _get_importance(token_name):
    return PREFERRED_TOKENS.get(token_name, 1)


def _get_priority_rank(token_name):
    return PREFERRED_TOKEN_RANKS.get(token_name, len(PREFERRED_TOKEN_RANKS) + 100)


def _candidate_priority_rank(candidate):
    if not isinstance(candidate, dict):
        return len(PREFERRED_TOKEN_RANKS) + 100
    return int(candidate.get("priority_rank", _get_priority_rank(candidate.get("name", ""))))


def _sprinkler_anchor_enabled():
    return FIELD_DRIFT_COMPENSATION and USE_SPRINKLER_MODEL_FOR_DRIFT_COMPENSATION


def _token_metrics():
    max_leash = 4.0 + (0.45 * max(width - 1, 0)) + (0.35 * size)
    return {
        "max_leash": max_leash,
        "hard_leash": max_leash + LEASH_HARD_MARGIN,
        "soft_leash": max_leash * 0.625,
        "max_consider": max_leash + 1.0 + (0.15 * width),
        "cluster_radius": 1.6 + (0.1 * width),
        "proximity_exp": 1.25,
        "toward_home_bonus": 1.4,
        "away_from_home_penalty": 0.8,
        "cluster_bonus_per_token": 0.25,
        "leash_edge_penalty": 0.45,
        "outside_leash_penalty": 0.35,
    }


def _find_best_token(runtime, detections):
    metrics = _token_metrics()
    current_x = runtime["current_x"]
    current_y = runtime["current_y"]
    current_dist = math.hypot(current_x, current_y)

    candidates = []
    rejected = []
    for box, class_id, confidence in detections:
        token_name = LABELS_TOKENS.get(class_id)
        if not token_name:
            rejected.append({"class_id": class_id, "reason": "unknown", "confidence": confidence})
            continue
        if token_name in IGNORED_TOKENS:
            rejected.append({"name": token_name, "reason": "ignored", "confidence": confidence})
            continue

        x1, y1, x2, y2 = box
        center_x, center_y = _model_point_to_capture(runtime, (x1 + x2) / 2.0, (y1 + y2) / 2.0)
        tx, ty = _relative_distance(center_x, center_y, runtime["homography"])
        distance = math.hypot(tx, ty)

        if distance < MIN_TOKEN_DISTANCE:
            rejected.append({"name": token_name, "reason": "too_close", "confidence": confidence, "distance": distance, "tx": tx, "ty": ty})
            continue
        if distance > metrics["max_consider"]:
            rejected.append({"name": token_name, "reason": "too_far", "confidence": confidence, "distance": distance, "tx": tx, "ty": ty})
            continue

        future_x = current_x + tx
        future_y = current_y + ty
        future_dist = math.hypot(future_x, future_y)
        if future_dist > metrics["hard_leash"] and distance > LEASH_NEAR_TOKEN_ALLOWANCE:
            rejected.append({"name": token_name, "reason": "hard_leash", "confidence": confidence, "distance": distance, "future_dist": future_dist, "tx": tx, "ty": ty})
            continue

        proximity = 1.0 / (0.3 + distance) ** metrics["proximity_exp"]
        dist_change = future_dist - current_dist

        if dist_change < -0.5:
            direction_score = metrics["toward_home_bonus"]
        elif dist_change < 0:
            direction_score = 1.0 + ((metrics["toward_home_bonus"] - 1.0) * 0.5)
        elif dist_change < 0.5:
            direction_score = 1.0
        elif dist_change < 1.5:
            direction_score = metrics["away_from_home_penalty"]
        else:
            direction_score = metrics["away_from_home_penalty"] * 0.7

        if current_dist > metrics["soft_leash"] and future_dist > current_dist:
            direction_score *= metrics["leash_edge_penalty"]
        if future_dist > metrics["max_leash"]:
            direction_score *= metrics["outside_leash_penalty"]

        score = proximity * direction_score * (math.log(_get_importance(token_name) + 1.0) + 1.0)
        candidates.append(
            {
                "name": token_name,
                "box": box,
                "tx": tx,
                "ty": ty,
                "future_x": future_x,
                "future_y": future_y,
                "score": score,
                "priority_rank": _get_priority_rank(token_name),
                "confidence": confidence,
            }
        )

    if not candidates:
        runtime["last_candidate_count"] = 0
        runtime["last_rejected_tokens"] = rejected[:8]
        return None

    for candidate in candidates:
        nearby = 0
        for other in candidates:
            if other is candidate:
                continue
            if math.hypot(candidate["future_x"] - other["future_x"], candidate["future_y"] - other["future_y"]) < metrics["cluster_radius"]:
                nearby += 1
        candidate["score"] *= 1.0 + (nearby * metrics["cluster_bonus_per_token"])

    runtime["last_candidate_count"] = len(candidates)
    runtime["last_rejected_tokens"] = rejected[:8]
    return max(candidates, key=lambda item: (-item["priority_rank"], item["score"]))


def _movement_keys(tx, ty):
    fb_key = tcfbkey if ty >= 0 else afcfbkey
    lr_key = afclrkey if tx >= 0 else tclrkey
    return fb_key, lr_key


def _movement_segments(tx, ty):
    diagonal_component = min(abs(tx), abs(ty))
    diagonal_distance = math.sqrt(2) * diagonal_component
    axial_distance = abs(abs(tx) - abs(ty))
    fb_key, lr_key = _movement_keys(tx, ty)

    segments = []
    if diagonal_distance >= 0.01:
        segments.append(("diagonal", [fb_key, lr_key], diagonal_distance))

    if axial_distance >= 0.01:
        if abs(ty) >= abs(tx):
            segments.append(("axial", [fb_key], axial_distance))
        else:
            segments.append(("axial", [lr_key], axial_distance))

    return segments


def _tile_walk(key, tiles):
    if tiles <= 0:
        return False

    self.keyboard.keyDown(key, False)
    self.keyboard.tileWait(tiles)
    self.keyboard.keyUp(key, False)
    return True


def _tile_multi_walk(keys, tiles):
    if tiles <= 0:
        return False

    for key in keys:
        self.keyboard.keyDown(key, False)
    self.keyboard.tileWait(tiles)
    for key in reversed(keys):
        self.keyboard.keyUp(key, False)
    return True


def _execute_movement(tx, ty):
    magnitude = math.hypot(tx, ty)
    if magnitude <= 0.001:
        return False

    moved = False
    runtime = _runtime_state()
    runtime["movement_active"] = True
    try:
        for segment_type, keys, distance in _movement_segments(tx, ty):
            if segment_type == "diagonal":
                _tile_multi_walk(keys, distance)
            else:
                _tile_walk(keys[0], distance)
            moved = True
        if moved:
            runtime["current_x"] += tx
            runtime["current_y"] += ty
            runtime["movement_count"] += 1
            runtime["last_token_time"] = time.time()
    finally:
        runtime["movement_active"] = False

    return moved


def _execute_movement_to_target(tx, ty):
    magnitude = math.hypot(tx, ty)
    if magnitude <= CONTINUOUS_MIN_REPLAN_DISTANCE:
        return False

    return _execute_movement(tx, ty)


def _latest_target(runtime):
    scan_lock = runtime.get("scan_lock")
    if scan_lock is None:
        return runtime.get("latest_target")
    with scan_lock:
        target = runtime.get("latest_target")
        return dict(target) if isinstance(target, dict) else target


def _locked_target(runtime):
    lock = runtime.get("locked_target")
    return dict(lock) if isinstance(lock, dict) else None


def _clear_locked_target(runtime):
    scan_lock = runtime.get("scan_lock")
    if scan_lock is None:
        runtime["locked_target"] = None
    else:
        with scan_lock:
            runtime["locked_target"] = None


def _select_movement_target(runtime):
    latest = _latest_target(runtime)
    locked = _locked_target(runtime)
    now = time.time()

    if locked:
        remaining_x = float(locked.get("future_x", runtime["current_x"])) - runtime["current_x"]
        remaining_y = float(locked.get("future_y", runtime["current_y"])) - runtime["current_y"]
        remaining = math.hypot(remaining_x, remaining_y)
        if remaining <= TARGET_LOCK_REACHED_DISTANCE:
            _clear_locked_target(runtime)
            return latest

        last_seen = float(locked.get("last_seen", locked.get("locked_at", now)))
        if latest and _same_token_candidate(locked, latest):
            locked.update(latest)
            locked["last_seen"] = now
            runtime["locked_target"] = locked
            return locked

        if latest and _candidate_priority_rank(latest) < _candidate_priority_rank(locked):
            latest["locked_at"] = now
            latest["last_seen"] = now
            runtime["locked_target"] = latest
            return latest

        if now - last_seen <= TARGET_LOCK_LOST_TIMEOUT:
            return locked

        if latest and latest.get("score", 0.0) >= locked.get("score", 0.0) * TARGET_LOCK_SWITCH_SCORE_MULTIPLIER:
            latest["locked_at"] = now
            latest["last_seen"] = now
            runtime["locked_target"] = latest
            return latest

        _clear_locked_target(runtime)
        return latest

    if latest:
        latest["locked_at"] = now
        latest["last_seen"] = now
        runtime["locked_target"] = latest
    return latest


def _execute_planned_movement(runtime):
    target = _select_movement_target(runtime)
    if not target:
        return False

    target_x = target.get("future_x")
    target_y = target.get("future_y")
    if target_x is None or target_y is None:
        return _execute_movement_to_target(target.get("tx", 0.0), target.get("ty", 0.0))

    remaining_x = float(target_x) - runtime["current_x"]
    remaining_y = float(target_y) - runtime["current_y"]
    if math.hypot(remaining_x, remaining_y) <= CONTINUOUS_MIN_REPLAN_DISTANCE:
        _clear_locked_target(runtime)
        return False

    _debug_log(
        f"moving toward planned target={target['name']} remaining=({remaining_x:.2f},{remaining_y:.2f}) score={target['score']:.2f}",
        min_interval=0.25,
        key="planned_move",
    )
    return _execute_movement_to_target(remaining_x, remaining_y)


def _find_sprinkler(runtime):
    if runtime.get("sprinkler_session") is None:
        runtime["last_sprinkler_status"] = "model_missing"
        return None

    frame = _grab_frame(runtime)
    if runtime.get("sprinkler_model_kind") == "opencv_onnx":
        image = _preprocess_onnx_image(frame, SPRINKLER_INPUT_WIDTH, SPRINKLER_INPUT_HEIGHT)
    else:
        image = _preprocess_coreml_image(frame, SPRINKLER_INPUT_WIDTH, SPRINKLER_INPUT_HEIGHT)
    output = _run_model(runtime, "sprinkler", image)
    detections = _postprocess_tokens(output, SPRINKLER_CONFIDENCE_THRESHOLD)

    scale_x = runtime["capture"]["width"] / float(SPRINKLER_INPUT_WIDTH)
    scale_y = runtime["capture"]["height"] / float(SPRINKLER_INPUT_HEIGHT)

    best = None
    best_distance = float("inf")
    best_any = None
    best_any_distance = float("inf")
    status = "no_detection"
    for box, class_id, confidence in detections:
        label = LABELS_SPRINKLER.get(class_id)

        x1, y1, x2, y2 = box
        center_x = ((x1 + x2) / 2.0) * scale_x
        center_y = ((y1 + y2) / 2.0) * scale_y
        tx, ty = _relative_distance(center_x, center_y, runtime["homography"])
        distance = math.hypot(tx, ty)
        scaled_box = (x1 * scale_x, y1 * scale_y, x2 * scale_x, y2 * scale_y)

        if distance > MAX_SPRINKLER_DISTANCE:
            continue

        if distance < best_any_distance:
            best_any_distance = distance
            best_any = (tx, ty, distance, label, confidence, scaled_box)

        if TARGET_SPRINKLER_LABEL and label != TARGET_SPRINKLER_LABEL:
            status = f"label_mismatch:{label or 'unknown'}"
            continue

        if distance < best_distance:
            best_distance = distance
            best = (tx, ty, distance, label, confidence, scaled_box)

    overlay_detection = best or best_any
    if overlay_detection:
        tx, ty, distance, label, confidence, scaled_box = overlay_detection
        runtime["last_sprinkler_detection"] = {
            "tx": tx,
            "ty": ty,
            "distance": distance,
            "label": label,
            "confidence": confidence,
            "box": scaled_box,
            "target_match": bool(best),
            "time": time.time(),
        }
        status = "target_match" if best else status
    else:
        runtime["last_sprinkler_detection"] = {}
    runtime["last_sprinkler_status"] = status
    return best


def _find_sprinkler_with_retry(runtime):
    for attempt in range(SPRINKLER_RESCAN_ATTEMPTS):
        result = _find_sprinkler(runtime)
        if result:
            _debug_log(
                f"sprinkler found on attempt {attempt + 1}: label={result[3]} confidence={result[4]:.2f} distance={result[2]:.2f}",
                min_interval=1.0,
                key="sprinkler_found",
            )
            return result
        _debug_log(
            f"sprinkler scan attempt {attempt + 1}/{SPRINKLER_RESCAN_ATTEMPTS} found no match",
            min_interval=1.0,
            key="sprinkler_missing",
        )
        if attempt < SPRINKLER_RESCAN_ATTEMPTS - 1:
            time.sleep(SPRINKLER_RESCAN_DELAY)
    return None


def _clear_targets(runtime):
    scan_lock = runtime.get("scan_lock")
    if scan_lock is None:
        runtime["latest_target"] = None
        runtime["locked_target"] = None
    else:
        with scan_lock:
            runtime["latest_target"] = None
            runtime["locked_target"] = None


def _refresh_sprinkler_anchor(runtime, force=False):
    if not _sprinkler_anchor_enabled():
        runtime["last_sprinkler_status"] = (
            "disabled:field_drift_compensation"
            if not FIELD_DRIFT_COMPENSATION
            else "disabled:use_sprinkler_model_for_drift_compensation"
        )
        return False
    if runtime.get("sprinkler_session") is None:
        runtime["last_sprinkler_status"] = "model_missing"
        return False
    if runtime.get("movement_active") and not force:
        return False

    now = time.time()
    if not force and now - runtime.get("last_anchor_time", 0.0) < ANCHOR_REFRESH_INTERVAL:
        return False

    result = _find_sprinkler(runtime)
    runtime["last_anchor_time"] = now
    if not result:
        return False

    tx, ty, distance, label, confidence = result[:5]
    if distance > ANCHOR_MAX_PASSIVE_DISTANCE:
        return False

    old_x = runtime.get("current_x", 0.0)
    old_y = runtime.get("current_y", 0.0)
    runtime["current_x"] = -tx
    runtime["current_y"] = -ty
    runtime["last_anchor"] = {
        "x": runtime["current_x"],
        "y": runtime["current_y"],
        "sprinkler_tx": tx,
        "sprinkler_ty": ty,
        "distance": distance,
        "label": label,
        "confidence": confidence,
        "time": time.time(),
    }
    _debug_log(
        f"anchor refreshed from sprinkler label={label} confidence={confidence:.2f} pos=({old_x:.2f},{old_y:.2f})->({runtime['current_x']:.2f},{runtime['current_y']:.2f})",
        min_interval=1.0,
        key="anchor_refresh",
    )
    return True


def _recalibrate(runtime):
    _debug_log(
        f"recalibrating from pos=({runtime['current_x']:.2f},{runtime['current_y']:.2f}) moves={runtime['movement_count']}",
        min_interval=1.0,
        key="recalibrate_start",
    )
    result = _find_sprinkler_with_retry(runtime)
    if not result:
        _debug_log("recalibration failed: no sprinkler found", min_interval=1.0, key="recalibrate_failed")
        return False

    tx, ty, distance, _label, _confidence = result[:5]
    if distance >= SPRINKLER_ARRIVAL_THRESHOLD:
        _debug_log(f"returning to sprinkler: move=({tx:.2f},{ty:.2f}) distance={distance:.2f}")
        _execute_movement(tx, ty)

    runtime["current_x"] = 0.0
    runtime["current_y"] = 0.0
    runtime["movement_count"] = 0
    runtime["last_idle_return_time"] = time.time()
    runtime["last_anchor_time"] = time.time()
    _clear_targets(runtime)
    _debug_log("recalibration complete; position reset to sprinkler")
    return True


def _should_recalibrate(runtime):
    if runtime["movement_count"] >= MOVEMENTS_BEFORE_RECALIBRATION:
        return True

    last_token_time = runtime.get("last_token_time", 0.0)
    if last_token_time and (time.time() - last_token_time) > NO_TOKEN_RECALIBRATION_TIMEOUT:
        return True

    return False


def _fallback_pattern():
    # Tiny figure-eight around the current spot so the pattern still works if AI deps are missing.
    _debug_log("running fallback sweep pattern", min_interval=1.0, key="fallback")
    travel = 0.12 * max(size, 0.75)
    for _ in range(max(1, min(int(width), 2))):
        self.keyboard.multiWalk([tcfbkey, tclrkey], travel)
        self.keyboard.multiWalk([afcfbkey, afclrkey], travel)
        self.keyboard.multiWalk([tcfbkey, afclrkey], travel)
        self.keyboard.multiWalk([afcfbkey, tclrkey], travel)


def _initialise_runtime():
    if cv2 is None or np is None:
        raise RuntimeError(
            "Must install opencv-python and numpy before using AI Gathering, please run install dependencies before continuing."
        )

    token_path = MODEL_DIR / "best.mlpackage"
    token_model_kind = "coreml"
    if not token_path.exists():
        token_path = MODEL_DIR / "tokens.onnx"
        token_model_kind = "opencv_onnx"
    if not token_path.exists():
        raise FileNotFoundError(f"No token AI model was found at fixed path: {MODEL_DIR / 'tokens.onnx'} or {MODEL_DIR / 'best.mlpackage'}")
    if token_model_kind == "coreml" and ct is None:
        try:
            import subprocess
            import sys
            import importlib

            subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "coremltools"])
            globals()["ct"] = importlib.import_module("coremltools")
        except Exception as exc:
            raise RuntimeError(
                "coremltools is required but automatic install failed: " + str(exc) + ". Please install coremltools before using AI Gathering, then restart the macro."
            )
    if token_model_kind == "coreml" and Image is None:
        raise RuntimeError("Pillow is required for CoreML AI Gathering, please run install dependencies before continuing.")

    sprinkler_model_kind = None
    sprinkler_candidate = MODEL_DIR / "sprinkler.mlpackage"
    if sprinkler_candidate.exists():
        sprinkler_model_kind = "coreml"
    else:
        sprinkler_candidate = MODEL_DIR / "sprinkler.onnx"
        if sprinkler_candidate.exists():
            sprinkler_model_kind = "opencv_onnx"
    sprinkler_path = sprinkler_candidate if sprinkler_candidate.exists() else None

    capture = _build_capture()
    token_crop_info = _token_crop_for_capture(capture)
    token_left, token_top, token_width, token_height = token_crop_info["rect"]
    token_monitor = None
    token_bbox = None
    if capture["backend"] == "mss":
        monitor = capture["monitor"]
        token_monitor = {
            "left": int(monitor["left"] + token_left),
            "top": int(monitor["top"] + token_top),
            "width": int(token_width),
            "height": int(token_height),
        }
    elif capture["backend"] == "pil":
        left, top, _right, _bottom = capture["bbox"]
        token_bbox = (
            int(left + token_left),
            int(top + token_top),
            int(left + token_left + token_width),
            int(top + token_top + token_height),
        )
    _debug_log(
        f"capture backend={capture['backend']} size={capture['width']}x{capture['height']} token_capture={token_monitor or token_bbox or token_crop_info['rect']} token_resize={token_crop_info['resize']} token_model={token_path} sprinkler_model={sprinkler_path or 'missing'}"
    )
    points = _default_points(capture["width"], capture["height"])

    destination = np.array(
        [[-5, -5], [5, -5], [-5, 5], [5, 5]],
        dtype=np.float32,
    )
    homography, _ = cv2.findHomography(points, destination, cv2.RANSAC)
    if homography is None:
        raise RuntimeError("Could not compute AI gather homography.")

    if token_model_kind == "opencv_onnx":
        token_session, token_input, token_output = _load_onnx_model(token_path)
        _delete_model_path(MODEL_DIR / "best.mlpackage")
    else:
        token_session, token_input, token_output = _load_coreml_model(token_path)
        _delete_model_path(MODEL_DIR / "tokens.onnx")
    sprinkler_session = None
    sprinkler_input = None
    sprinkler_output = None
    if sprinkler_path is not None:
        if sprinkler_model_kind == "opencv_onnx":
            sprinkler_session, sprinkler_input, sprinkler_output = _load_onnx_model(sprinkler_path)
            _delete_model_path(MODEL_DIR / "sprinkler.mlpackage")
        else:
            sprinkler_session, sprinkler_input, sprinkler_output = _load_coreml_model(sprinkler_path)
            _delete_model_path(MODEL_DIR / "sprinkler.onnx")

    return {
        "capture": capture,
        "token_crop": token_crop_info["rect"],
        "token_monitor": token_monitor,
        "token_bbox": token_bbox,
        "token_frame_is_crop": token_monitor is not None or token_bbox is not None,
        "token_resize": token_crop_info["resize"],
        "token_session": token_session,
        "token_input": token_input,
        "token_output": token_output,
        "token_model_kind": token_model_kind,
        "sprinkler_session": sprinkler_session,
        "sprinkler_input": sprinkler_input,
        "sprinkler_output": sprinkler_output,
        "sprinkler_model_kind": sprinkler_model_kind,
        "homography": homography,
        "current_x": 0.0,
        "current_y": 0.0,
        "movement_count": 0,
        "last_token_time": time.time(),
        "last_idle_return_time": time.time(),
        "last_no_target_sweep_time": time.time(),
        "initialised_at": time.time(),
        "video_writer": None,
        "video_path": "",
        "last_recording_frame_time": 0.0,
        "detection_fps": None,
        "last_detection_ms": None,
        "last_timing_ms": {},
        "latest_detections": [],
        "latest_target": None,
        "locked_target": None,
        "latest_scan_time": 0.0,
        "last_anchor_time": 0.0,
        "last_anchor": {},
        "last_sprinkler_detection": {},
        "last_sprinkler_status": "",
        "movement_active": False,
        "scan_lock": threading.Lock(),
        "scanner_stop_event": None,
        "scanner_thread": None,
    }


runtime = _runtime_state()
if not runtime.get("ready"):
    try:
        runtime.clear()
        runtime.update(_initialise_runtime())
        runtime["ready"] = True
        runtime["error"] = ""
        _debug_log(
            f"runtime ready token_model={runtime['token_model_kind']} input={runtime['token_input']} output={runtime['token_output']} confidence={CONFIDENCE_THRESHOLD} ignored={sorted(IGNORED_TOKENS)} record={RECORD_VIDEO}"
        )
    except Exception as exc:
        runtime["ready"] = False
        runtime["error"] = str(exc)
        _debug_log(f"initialisation failed: {exc}")


if not runtime.get("ready"):
    print(f"[fuzzy_ai_gather] {runtime.get('error', 'initialisation failed')}")
    _fallback_pattern()
else:
    try:
        if not runtime.get("latest_scan_time"):
            _scan_tokens_once(runtime)
        _ensure_scanner_thread(runtime)
        _refresh_sprinkler_anchor(runtime)

        if _should_recalibrate(runtime):
            _recalibrate(runtime)

        target = _locked_target(runtime) or _latest_target(runtime)
        if target:
            _debug_log(
                f"target={target['name']} confidence={target['confidence']:.2f} score={target['score']:.2f} planned=({target['future_x']:.2f},{target['future_y']:.2f})",
                min_interval=0.25,
                key="target",
            )
            _execute_planned_movement(runtime)
        else:
            detections = runtime.get("latest_detections", [])
            _debug_log(
                f"no target from detections={len(detections)} pos=({runtime['current_x']:.2f},{runtime['current_y']:.2f})",
                min_interval=0.5,
                key="no_target",
            )
            now = time.time()
            rejected_reasons = {item.get("reason") for item in runtime.get("last_rejected_tokens", [])}
            recalibrated = False
            if detections and rejected_reasons.intersection({"leash", "hard_leash"}) and _recalibrate(runtime):
                runtime["last_token_time"] = time.time()
                recalibrated = True

            if recalibrated:
                pass
            elif now - runtime["last_idle_return_time"] >= IDLE_RETURN_INTERVAL:
                runtime["last_idle_return_time"] = now
                if _recalibrate(runtime):
                    runtime["last_token_time"] = time.time()
    except Exception as exc:
        runtime["ready"] = False
        runtime["error"] = str(exc)
        _release_video_writer(runtime)
        print(f"[fuzzy_ai_gather] runtime error: {exc}")
        _fallback_pattern()
