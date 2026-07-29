"""
Pattern: BloomsAI
Description: Uses blooms to spawn petals, then prioritizes currently visible petals.
Best for: Petal-focused gathering that collects live petals spawned by blooms.
Width: Expands the leash radius and target clustering range.
Size: Scales each movement step so the pattern still respects the GUI controls.

Requirements:
- coremltools
- opencv-python
- numpy
- mss or Pillow
- blooms-and-petals-standard.mlmodelc, Blooms-and-petals-light.mlmodelc, or Blooms-and-petals-mini.mlmodelc
- sprinkler_detection_standard.mlmodelc or sprinkler_detection_standard.onnx

- Version 1.6
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
SPRINKLER_CONFIDENCE_THRESHOLD = 0.6
PETAL_CONFIDENCE_THRESHOLD = 0.50
RUNTIME_VERSION = 31
MIN_TOKEN_DISTANCE = 0.3
MAX_SPRINKLER_DISTANCE = 10.0
TARGET_SPRINKLER_LABEL = None
DEBUG_MODE = False
RECORD_VIDEO = False
RECORD_VIDEO_FPS = 12.0
CONTINUOUS_SCAN_INTERVAL = 0.08
CONTINUOUS_MIN_REPLAN_DISTANCE = 0.08
TARGET_LOCK_LOST_TIMEOUT = 0.9
TARGET_LOCK_SWITCH_SCORE_MULTIPLIER = 2.25
TARGET_LOCK_SWITCH_DISTANCE = 1.25
TARGET_POSITION_SMOOTHING = 0.35
ANCHOR_REFRESH_INTERVAL = 0.35
ANCHOR_MAX_PASSIVE_DISTANCE = 8.0
LEASH_HARD_MARGIN = 2.5
BLOOM_LABEL = "Bloom"
PETAL_ORBIT_RADIUS = 2.75
PETAL_ORBIT_DURATION = 3.0
PETAL_ORBIT_CORNERS = 4
BLOOM_MAX_DISTANCE = 20.0
BLOOM_SETTLE_DISTANCE = 0.25
BLOOM_MIN_CONFIDENCE = 0.50
BLOOM_SPRINKLER_ANCHOR_INTERVAL = 0.35
BLOOM_FORCE_ANCHOR_DISTANCE = 4.0
BLOOM_CONTACT_DEAD_ZONE = 0.5
BLOOM_CONTACT_MAX_MOVE = 0.3
BLOOM_CONTACT_MOVE_COOLDOWN = 0.25
BLOOM_CONTACT_CONFIRMATIONS = 3
BLOOM_CONTACT_MAX_TOTAL_MOVE = 1.2
IDLE_SPRINKLER_RADIUS = 0.40
IDLE_RETURN_STEP = 1.25
IDLE_SQUARE_STEP = 0.25
BLOOM_MODEL_VARIANTS = {
    "standard": ("Standard", "blooms-and-petals-standard.mlmodelc", 960, "var_1444"),
    "light": ("Light", "Blooms-and-petals-light.mlmodelc", 768, "var_1440"),
    "mini": ("Mini", "Blooms-and-petals-mini.mlmodelc", 512, "var_1440"),
}

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


def _check_missing_models(model_names):
    try:
        from modules.misc.modelManager import ensure_missing_models

        result = ensure_missing_models(model_names)
        if result.get("downloaded"):
            print(f"[blooms_ai] Downloaded missing AI model(s): {', '.join(result['downloaded'])}")
        elif result.get("missing_remote"):
            print(f"[blooms_ai] Missing AI model(s) were not found remotely: {', '.join(result['missing_remote'])}")
        return result
    except Exception as exc:
        print(f"[blooms_ai] Could not check missing AI models: {exc}")
        return {"failures": {"model download": str(exc)}}


SPRINKLER_CONFIDENCE_THRESHOLD = _coerce_float(
    globals().get("pattern_sprinkler_confidence_threshold"),
    SPRINKLER_CONFIDENCE_THRESHOLD,
)
MIN_TOKEN_DISTANCE = _coerce_float(globals().get("pattern_min_token_distance"), MIN_TOKEN_DISTANCE)
MAX_SPRINKLER_DISTANCE = _coerce_float(
    globals().get("pattern_max_sprinkler_distance"),
    MAX_SPRINKLER_DISTANCE,
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
BLOOM_MODEL_SELECTION = _coerce_text(
    globals().get("pattern_blooms_ai_model"),
    "Standard",
).strip().lower()
if BLOOM_MODEL_SELECTION not in BLOOM_MODEL_VARIANTS:
    BLOOM_MODEL_SELECTION = "standard"
IGNORED_TOKENS = _ignored_token_names(globals().get("pattern_ignored_tokens"), IGNORED_TOKENS)
# BloomsAI exists specifically to target blooms. Field token-ranking defaults may
# ignore Bloom for normal gathering, but that setting must never apply here.
IGNORED_TOKENS.discard(BLOOM_LABEL)


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


def _preprocess_petal_image(frame, input_width, input_height):
    """Apply Ultralytics-style centered letterboxing and retain its inverse transform."""
    if frame.ndim == 3 and frame.shape[2] == 4:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB)
    else:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    frame_height, frame_width = rgb.shape[:2]
    scale = min(input_width / float(frame_width), input_height / float(frame_height))
    resized_width = max(1, int(round(frame_width * scale)))
    resized_height = max(1, int(round(frame_height * scale)))
    resized = cv2.resize(rgb, (resized_width, resized_height), interpolation=cv2.INTER_LINEAR)
    pad_x = (input_width - resized_width) // 2
    pad_y = (input_height - resized_height) // 2
    letterboxed = np.full((input_height, input_width, 3), 114, dtype=np.uint8)
    letterboxed[pad_y:pad_y + resized_height, pad_x:pad_x + resized_width] = resized

    if Image is None:
        raise RuntimeError("Pillow is required for CoreML petal inference.")
    return Image.fromarray(letterboxed), {"scale": scale, "pad_x": pad_x, "pad_y": pad_y}


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
    print(f"[blooms_ai][debug] {message}", flush=True)


def _runtime_state():
    state = getattr(self, "_blooms_ai_state", None)
    if isinstance(state, dict):
        return state

    state = globals().get("_BLOOMS_AI_STATE")
    if not isinstance(state, dict):
        state = {}
        globals()["_BLOOMS_AI_STATE"] = state

    try:
        setattr(self, "_blooms_ai_state", state)
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


def _grab_upper_token_frame(runtime):
    monitor = runtime.get("upper_token_monitor")
    if runtime["capture"]["backend"] == "mss" and monitor:
        return _mss_grab_to_array(runtime["capture"]["session"], monitor)
    bbox = runtime.get("upper_token_bbox")
    if bbox and ImageGrab is not None:
        image = ImageGrab.grab(bbox=bbox)
        return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
    return None


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


def _capture_box_to_model(runtime, box):
    left, top, crop_w, crop_h = runtime["token_crop"]
    x1, y1, x2, y2 = box
    return (
        (x1 - left) * INPUT_WIDTH / crop_w,
        (y1 - top) * INPUT_HEIGHT / crop_h,
        (x2 - left) * INPUT_WIDTH / crop_w,
        (y2 - top) * INPUT_HEIGHT / crop_h,
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
    filename = f"blooms_ai_{time.strftime('%Y%m%d_%H%M%S')}.mp4"
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
    _debug_log(f"recording BloomsAI video to {output_path}")
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
            _debug_log(f"saved BloomsAI recording: {runtime['video_path']}")


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

    bloom_detections = [
        detection
        for detection in detections
        if LABELS_TOKENS.get(detection[1]) == BLOOM_LABEL
    ]
    now = time.time()
    petal_detection_age = now - float(runtime.get("latest_petal_detection_time", 0.0))
    petal_detections = runtime.get("latest_petal_detections", [])
    if petal_detection_age > 1.0:
        petal_detections = []
    runtime["latest_recording_overlay"] = {
        "detections": bloom_detections,
        "petal_detections": [dict(detection) for detection in petal_detections],
        "petal_detection_ms": runtime.get("last_petal_detection_ms"),
        "raw_detection_count": len(detections),
        "target": dict(target) if isinstance(target, dict) else None,
        "current_x": runtime.get("current_x", 0.0),
        "current_y": runtime.get("current_y", 0.0),
        "movement_count": runtime.get("movement_count", 0),
        "detection_fps": runtime.get("detection_fps"),
        "last_detection_ms": runtime.get("last_detection_ms"),
        "last_timing_ms": dict(runtime.get("last_timing_ms", {})),
        "candidate_count": runtime.get("last_candidate_count", 0),
        "bloom_mode": runtime.get("bloom_mode", "patrol"),
        "active_bloom": dict(runtime.get("active_bloom", {})) if isinstance(runtime.get("active_bloom"), dict) else None,
        "bloom_contact_distance": runtime.get("bloom_contact_distance", 0.0),
        "petal_orbit_center": tuple(runtime["petal_orbit_center"]) if isinstance(runtime.get("petal_orbit_center"), (tuple, list)) else None,
        "petal_orbit_deadline": runtime.get("petal_orbit_deadline", 0.0),
        "petal_orbit_index": runtime.get("petal_orbit_index"),
        "sprinkler": dict(runtime.get("last_sprinkler_detection", {})),
        "anchor": dict(runtime.get("last_anchor", {})),
        "sprinkler_status": runtime.get("last_sprinkler_status", ""),
        "target_sprinkler_label": TARGET_SPRINKLER_LABEL or "",
        "field_drift_compensation": FIELD_DRIFT_COMPENSATION,
        "use_sprinkler_model_for_drift_compensation": USE_SPRINKLER_MODEL_FOR_DRIFT_COMPENSATION,
        "updated_at": now,
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

    petal_detections = overlay.get("petal_detections", [])
    for detection in petal_detections:
        x1, y1, x2, y2 = detection.get("box", (0, 0, 0, 0))
        left = max(0, min(frame_w - 1, int(round(x1))))
        top = max(0, min(frame_h - 1, int(round(y1))))
        right = max(0, min(frame_w - 1, int(round(x2))))
        bottom = max(0, min(frame_h - 1, int(round(y2))))
        color = (255, 120, 40)
        cv2.rectangle(annotated, (left, top), (right, bottom), color, 2)
        label = f"Petal {detection.get('confidence', 0.0):.2f}"
        _draw_label(annotated, label, left, top - 4, color)

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
        f"mode={overlay.get('bloom_mode', 'patrol')} blooms={len(detections)} petals={len(petal_detections)} candidates={overlay.get('candidate_count', 0)} pos=({overlay.get('current_x', 0.0):.2f},{overlay.get('current_y', 0.0):.2f}) moves={overlay.get('movement_count', 0)}",
        f"target={target['name']} score={target['score']:.2f} move=({target['tx']:.2f},{target['ty']:.2f})" if target else "target=None",
        f"sprinkler_status={overlay.get('sprinkler_status', '')} target={overlay.get('target_sprinkler_label', '') or 'any'} drift={overlay.get('field_drift_compensation')} model={overlay.get('use_sprinkler_model_for_drift_compensation')}",
    ]
    if anchor:
        age = max(0.0, time.time() - float(anchor.get("time", time.time())))
        status_lines.append(
            f"anchor=({anchor.get('x', 0.0):.2f},{anchor.get('y', 0.0):.2f}) sprinkler=({anchor.get('sprinkler_tx', 0.0):.2f},{anchor.get('sprinkler_ty', 0.0):.2f}) age={age:.1f}s"
        )
    active_bloom = overlay.get("active_bloom") or {}
    if active_bloom:
        status_lines.append(
            f"active_bloom=({active_bloom.get('tx', 0.0):.2f},{active_bloom.get('ty', 0.0):.2f}) contact={overlay.get('bloom_contact_distance', 0.0):.2f}/{BLOOM_CONTACT_MAX_TOTAL_MOVE:.2f}"
        )
    orbit_center = overlay.get("petal_orbit_center")
    if isinstance(orbit_center, (tuple, list)) and len(orbit_center) == 2:
        seconds_left = max(0.0, float(overlay.get("petal_orbit_deadline", 0.0)) - time.time())
        status_lines.append(
            f"petal_orbit=({orbit_center[0]:.2f},{orbit_center[1]:.2f}) next={int(overlay.get('petal_orbit_index') or 0) + 1}/{PETAL_ORBIT_CORNERS} left={seconds_left:.1f}s"
        )
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
    petal_detection_ms = overlay.get("petal_detection_ms")
    if petal_detection_ms is not None:
        petal_timing_text = f"petal infer {petal_detection_ms:.0f}ms"
        (petal_w, _petal_h), _petal_baseline = cv2.getTextSize(petal_timing_text, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
        _draw_label(annotated, petal_timing_text, max(10, frame_w - petal_w - 18), 72, (255, 120, 40))

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
    movement_revision = int(runtime.get("movement_revision", 0))
    detection_start = time.time()
    screenshot_start = time.time()
    frame = _grab_upper_token_frame(runtime)
    if frame is None:
        frame = _grab_frame(runtime)
    screenshot_elapsed = time.time() - screenshot_start
    preprocess_start = time.time()
    image, transform = _preprocess_petal_image(
        frame,
        runtime["combined_input_width"],
        runtime["combined_input_height"],
    )
    preprocess_elapsed = time.time() - preprocess_start
    inference_start = time.time()
    output = _run_model(runtime, "combined", image)
    inference_elapsed = time.time() - inference_start
    postprocess_start = time.time()
    scan_stale = (
        runtime.get("movement_active")
        or int(runtime.get("movement_revision", 0)) != movement_revision
    )
    detections = _process_combined_detections(
        runtime,
        output,
        transform,
        inference_elapsed * 1000.0,
        publish_petals=not scan_stale,
    )
    postprocess_elapsed = time.time() - postprocess_start
    _refresh_bloom_sprinkler_anchor(runtime)
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

    # A movement that starts after capture makes these screen-relative
    # detections stale, even if it finishes before inference does.
    if (
        scan_stale
    ):
        runtime["latest_bloom_candidates"] = []
        runtime["latest_petal_detections"] = []
        runtime["latest_petal_detection_time"] = 0.0
        return runtime.get("latest_detections", []), runtime.get("latest_target")

    now = time.time()
    scan_lock = runtime.get("scan_lock")
    if scan_lock is None:
        scan_lock = threading.Lock()
        runtime["scan_lock"] = scan_lock
    with scan_lock:
        runtime["latest_detections"] = detections
        runtime["latest_target"] = target
        runtime["latest_scan_time"] = now
        runtime["movement_requires_fresh_scan"] = False

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
        scan_started = time.time()
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
        remaining = CONTINUOUS_SCAN_INTERVAL - (time.time() - scan_started)
        time.sleep(max(remaining, 0.01))


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


#def _set_start_camera_angle():
#    for _ in range(4):
#        self.keyboard.press("pageup")
#        time.sleep(0.04)


def _load_coreml_model(model_path, compiled_output_name="var_1445"):
    if ct is None:
        raise RuntimeError("coremltools is required for BloomsAI gathering. Install coremltools, then restart the macro.")

    model_path = Path(model_path)
    if model_path.suffix.lower() == ".mlmodelc":
        compiled_model_class = getattr(ct.models, "CompiledMLModel", None)
        if compiled_model_class is None:
            raise RuntimeError("This coremltools version cannot load compiled .mlmodelc bundles. Upgrade coremltools, then restart the macro.")
        model = compiled_model_class(str(model_path), compute_units=ct.ComputeUnit.ALL)
        return model, "image", compiled_output_name

    model = ct.models.MLModel(str(model_path), compute_units=ct.ComputeUnit.ALL)
    description = model.get_spec().description
    input_name = description.input[0].name
    output_name = description.output[0].name
    return model, input_name, output_name


def _load_onnx_model(model_path):
    if cv2 is None:
        raise RuntimeError("OpenCV is required for ONNX BloomsAI.")

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


def _sprinkler_anchor_enabled():
    return FIELD_DRIFT_COMPENSATION and USE_SPRINKLER_MODEL_FOR_DRIFT_COMPENSATION


def _token_metrics():
    max_leash = 4.0 + (0.45 * max(width - 1, 0)) + (0.35 * size)
    max_bloom_distance = max(BLOOM_MAX_DISTANCE, max_leash + 1.0)
    return {
        "max_leash": max_leash,
        "hard_leash": max_leash + LEASH_HARD_MARGIN,
        "soft_leash": max_leash * 0.625,
        "max_consider": max_bloom_distance,
        "cluster_radius": 1.6 + (0.1 * width),
        "proximity_exp": 1.25,
        "toward_home_bonus": 1.4,
        "away_from_home_penalty": 0.8,
        "cluster_bonus_per_token": 0.25,
        "leash_edge_penalty": 0.45,
        "outside_leash_penalty": 0.35,
    }


def _find_best_token(runtime, detections):
    scan_time = time.time()
    metrics = _token_metrics()
    current_x = runtime["current_x"]
    current_y = runtime["current_y"]
    current_dist = math.hypot(current_x, current_y)
    candidates = []
    visible_blooms = []
    rejected = []
    for box, class_id, confidence in detections:
        token_name = LABELS_TOKENS.get(class_id)
        if not token_name:
            rejected.append({"class_id": class_id, "reason": "unknown", "confidence": confidence})
            continue
        if token_name != BLOOM_LABEL:
            rejected.append({"name": token_name, "reason": "not_bloom", "confidence": confidence})
            continue
        if token_name == BLOOM_LABEL and confidence < BLOOM_MIN_CONFIDENCE:
            rejected.append({"name": token_name, "reason": "low_confidence", "confidence": confidence})
            continue

        x1, y1, x2, y2 = box
        center_x, center_y = _model_point_to_capture(runtime, (x1 + x2) / 2.0, (y1 + y2) / 2.0)
        tx, ty = _relative_distance(center_x, center_y, runtime["homography"])
        distance = math.hypot(tx, ty)
        future_x = current_x + tx
        future_y = current_y + ty
        visible_blooms.append({
            "name": token_name,
            "box": box,
            "tx": tx,
            "ty": ty,
            "future_x": future_x,
            "future_y": future_y,
            "score": 0.0,
            "confidence": confidence,
            "seen_at": scan_time,
        })

        if distance < MIN_TOKEN_DISTANCE:
            rejected.append({"name": token_name, "reason": "too_close", "confidence": confidence, "distance": distance, "tx": tx, "ty": ty})
            continue
        if distance > metrics["max_consider"]:
            rejected.append({"name": token_name, "reason": "too_far", "confidence": confidence, "distance": distance, "tx": tx, "ty": ty})
            continue

        future_dist = math.hypot(future_x, future_y)
        # Use the screen-relative distance gate above for bloom reachability;
        # accumulated sprinkler-relative position is only a scoring hint.
        proximity = 1.0 / (0.3 + distance) ** metrics["proximity_exp"]
        home_bonus = 1.0 / (0.25 + future_dist) ** 0.2
        if current_dist > metrics["soft_leash"] and future_dist > current_dist:
            home_bonus *= metrics["leash_edge_penalty"]
        if future_dist > metrics["max_leash"]:
            home_bonus *= metrics["outside_leash_penalty"]
        score = proximity * home_bonus * (0.8 + confidence)
        candidates.append(
            {
                "name": token_name,
                "box": box,
                "tx": tx,
                "ty": ty,
                "future_x": future_x,
                "future_y": future_y,
                "score": score,
                "confidence": confidence,
                "seen_at": scan_time,
            }
        )

    if not candidates:
        runtime["last_candidate_count"] = 0
        runtime["last_rejected_tokens"] = rejected[:8]
        runtime["latest_bloom_candidates"] = visible_blooms
        return None

    candidates.sort(key=lambda item: item["score"], reverse=True)
    runtime["last_candidate_count"] = len(candidates)
    runtime["last_rejected_tokens"] = rejected[:8]
    runtime["latest_bloom_candidates"] = visible_blooms
    return candidates[0]


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
    runtime["movement_revision"] = int(runtime.get("movement_revision", 0)) + 1
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
    finally:
        runtime["movement_active"] = False

    if moved:
        scan_lock = runtime.get("scan_lock")
        if scan_lock is None:
            scan_lock = threading.Lock()
            runtime["scan_lock"] = scan_lock
        with scan_lock:
            runtime["latest_target"] = None
            runtime["latest_bloom_candidates"] = []
            runtime["latest_petal_detection_time"] = 0.0
            runtime["latest_scan_time"] = 0.0
            runtime["movement_requires_fresh_scan"] = True

    return moved


def _execute_movement_to_target(tx, ty):
    magnitude = math.hypot(tx, ty)
    if magnitude <= CONTINUOUS_MIN_REPLAN_DISTANCE:
        return False

    return _execute_movement(tx, ty)


def _execute_sprinkler_patrol(runtime):
    """Return to the sprinkler, then make a small square while waiting."""
    if runtime.get("movement_requires_fresh_scan"):
        return False

    current_x = float(runtime.get("current_x", 0.0))
    current_y = float(runtime.get("current_y", 0.0))
    distance = math.hypot(current_x, current_y)
    if distance > IDLE_SPRINKLER_RADIUS:
        step = min(IDLE_RETURN_STEP, distance)
        scale = step / distance
        tx = -current_x * scale
        ty = -current_y * scale
        _debug_log(
            f"returning to sprinkler move=({tx:.2f},{ty:.2f}) distance={distance:.2f}",
            min_interval=0.25,
            key="idle_return",
        )
        return _execute_movement(tx, ty)

    square_index = int(runtime.get("idle_square_index", 0))
    runtime["idle_square_index"] = square_index + 1
    square = (
        (IDLE_SQUARE_STEP, 0.0),
        (0.0, IDLE_SQUARE_STEP),
        (-IDLE_SQUARE_STEP, 0.0),
        (0.0, -IDLE_SQUARE_STEP),
    )
    tx, ty = square[square_index % len(square)]
    _debug_log(
        f"sprinkler patrol square move=({tx:.2f},{ty:.2f})",
        min_interval=0.25,
        key="idle_square",
    )
    return _execute_movement(tx, ty)


def _active_bloom_detection(runtime):
    # Bloom contact must use a detection made after the last keypress.
    # Otherwise it can bypass normal target invalidation and chase a bloom
    # from the player's old screen position.
    if runtime.get("movement_requires_fresh_scan"):
        return None

    active = runtime.get("active_bloom")
    if not isinstance(active, dict):
        return None
    candidates = runtime.get("latest_bloom_candidates", [])
    for candidate in candidates if isinstance(candidates, list) else []:
        if _same_token_candidate(active, candidate):
            runtime["active_bloom"] = dict(candidate)
            return dict(candidate)
    return None


def _start_bloom_work(runtime, target):
    runtime["bloom_mode"] = "work"
    runtime["active_bloom"] = dict(target)
    runtime["bloom_last_visible_time"] = time.time()
    runtime["bloom_contact_vector"] = None
    runtime["bloom_contact_confirmations"] = 0
    runtime["bloom_contact_last_seen_at"] = 0.0
    runtime["bloom_contact_last_move_time"] = 0.0
    runtime["bloom_contact_distance"] = 0.0
    _clear_locked_target(runtime)


def _start_petal_orbit(runtime):
    now = time.time()
    active_bloom = runtime.get("active_bloom")
    if not isinstance(active_bloom, dict):
        return False
    runtime["bloom_mode"] = "orbit"
    runtime["petal_orbit_center"] = (
        float(active_bloom.get("future_x", runtime.get("current_x", 0.0))),
        float(active_bloom.get("future_y", runtime.get("current_y", 0.0))),
    )
    runtime["petal_orbit_deadline"] = now + PETAL_ORBIT_DURATION
    runtime["petal_orbit_index"] = None
    runtime["active_bloom"] = None
    _clear_locked_target(runtime)
    return True


def _finish_petal_orbit(runtime):
    runtime["bloom_mode"] = "patrol"
    runtime["active_bloom"] = None
    runtime["petal_orbit_center"] = None
    runtime["petal_orbit_deadline"] = 0.0
    runtime["petal_orbit_index"] = None
    _clear_locked_target(runtime)
    # Correct dead-reckoned position without spending time walking back to the
    # sprinkler. Failure is harmless; screen-relative pursuit remains valid.
    _refresh_sprinkler_anchor(runtime, force=True)


def _execute_petal_orbit(runtime):
    if time.time() >= float(runtime.get("petal_orbit_deadline", 0.0)):
        _finish_petal_orbit(runtime)
        return True

    center = runtime.get("petal_orbit_center")
    if not isinstance(center, (tuple, list)) or len(center) != 2:
        _finish_petal_orbit(runtime)
        return True

    corner_offset = PETAL_ORBIT_RADIUS / math.sqrt(2.0)
    points = [
        (float(center[0]) + corner_offset, float(center[1]) + corner_offset),
        (float(center[0]) - corner_offset, float(center[1]) + corner_offset),
        (float(center[0]) - corner_offset, float(center[1]) - corner_offset),
        (float(center[0]) + corner_offset, float(center[1]) - corner_offset),
    ]
    orbit_index = runtime.get("petal_orbit_index")
    if orbit_index is None:
        current_x = float(runtime.get("current_x", 0.0))
        current_y = float(runtime.get("current_y", 0.0))
        orbit_index = min(
            range(PETAL_ORBIT_CORNERS),
            key=lambda index: math.hypot(points[index][0] - current_x, points[index][1] - current_y),
        )
    else:
        orbit_index = int(orbit_index) % PETAL_ORBIT_CORNERS

    # Keep keys flowing through one full square without scanning between sides.
    # The deadline remains a safety limit.
    for _ in range(PETAL_ORBIT_CORNERS + 1):
        if time.time() >= float(runtime.get("petal_orbit_deadline", 0.0)):
            break
        target_x, target_y = points[orbit_index]
        move_x = target_x - float(runtime.get("current_x", 0.0))
        move_y = target_y - float(runtime.get("current_y", 0.0))
        runtime["petal_orbit_index"] = (orbit_index + 1) % PETAL_ORBIT_CORNERS
        _debug_log(
            f"orbiting popped bloom corner={orbit_index + 1}/{PETAL_ORBIT_CORNERS} move=({move_x:.2f},{move_y:.2f})",
            min_interval=0.25,
            key="petal_orbit",
        )
        if not _execute_movement(move_x, move_y):
            break
        orbit_index = runtime["petal_orbit_index"]

    _finish_petal_orbit(runtime)
    return True


def _execute_bloom_sequence(runtime):
    mode = runtime.get("bloom_mode", "patrol")
    now = time.time()
    if mode == "work":
        bloom = _active_bloom_detection(runtime)
        if bloom:
            runtime["bloom_last_visible_time"] = now
            tx = float(bloom.get("tx", 0.0))
            ty = float(bloom.get("ty", 0.0))
            distance = math.hypot(tx, ty)
            seen_at = float(bloom.get("seen_at", now))
            if seen_at <= runtime.get("bloom_contact_last_seen_at", 0.0):
                return True
            runtime["bloom_contact_last_seen_at"] = seen_at

            if distance <= BLOOM_CONTACT_DEAD_ZONE:
                runtime["bloom_contact_vector"] = None
                runtime["bloom_contact_confirmations"] = 0
                _start_petal_orbit(runtime)
                return _execute_petal_orbit(runtime)

            previous = runtime.get("bloom_contact_vector")
            if isinstance(previous, (tuple, list)) and len(previous) == 2:
                same_direction = (previous[0] * tx) + (previous[1] * ty) > 0.0
                filtered_tx = (previous[0] * 0.65) + (tx * 0.35)
                filtered_ty = (previous[1] * 0.65) + (ty * 0.35)
                confirmations = runtime.get("bloom_contact_confirmations", 0) + 1 if same_direction else 1
            else:
                filtered_tx, filtered_ty = tx, ty
                confirmations = 1
            runtime["bloom_contact_vector"] = (filtered_tx, filtered_ty)
            runtime["bloom_contact_confirmations"] = confirmations

            if confirmations < BLOOM_CONTACT_CONFIRMATIONS:
                return True
            if now - runtime.get("bloom_contact_last_move_time", 0.0) < BLOOM_CONTACT_MOVE_COOLDOWN:
                return True

            filtered_distance = math.hypot(filtered_tx, filtered_ty)
            remaining_budget = BLOOM_CONTACT_MAX_TOTAL_MOVE - runtime.get("bloom_contact_distance", 0.0)
            move_distance = min(
                BLOOM_CONTACT_MAX_MOVE,
                max(filtered_distance - BLOOM_CONTACT_DEAD_ZONE, 0.0),
                remaining_budget,
            )
            if move_distance <= CONTINUOUS_MIN_REPLAN_DISTANCE:
                return True
            scale = move_distance / filtered_distance
            runtime["bloom_contact_confirmations"] = 0
            runtime["bloom_contact_last_move_time"] = now
            runtime["bloom_contact_distance"] += move_distance
            return _execute_movement(filtered_tx * scale, filtered_ty * scale)

        _start_petal_orbit(runtime)
        mode = "orbit"

    if mode == "orbit":
        return _execute_petal_orbit(runtime)
    return False


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


def _set_locked_target(runtime, target):
    if isinstance(target, dict):
        target = dict(target)
    scan_lock = runtime.get("scan_lock")
    if scan_lock is None:
        runtime["locked_target"] = target
    else:
        with scan_lock:
            runtime["locked_target"] = target


def _clear_locked_target(runtime):
    _set_locked_target(runtime, None)


def _select_movement_target(runtime):
    if runtime.get("movement_requires_fresh_scan"):
        return None

    latest = _latest_target(runtime)
    locked = _locked_target(runtime)
    now = time.time()

    if locked:
        remaining_x = float(locked.get("future_x", runtime["current_x"])) - runtime["current_x"]
        remaining_y = float(locked.get("future_y", runtime["current_y"])) - runtime["current_y"]
        remaining = math.hypot(remaining_x, remaining_y)
        if remaining <= BLOOM_SETTLE_DISTANCE:
            _clear_locked_target(runtime)
            return None

        last_seen = float(locked.get("last_seen", locked.get("locked_at", now)))
        if latest and _same_token_candidate(locked, latest):
            old_future_x = float(locked.get("future_x", latest.get("future_x", 0.0)))
            old_future_y = float(locked.get("future_y", latest.get("future_y", 0.0)))
            new_future_x = float(latest.get("future_x", old_future_x))
            new_future_y = float(latest.get("future_y", old_future_y))
            locked.update(latest)
            locked["future_x"] = old_future_x + ((new_future_x - old_future_x) * TARGET_POSITION_SMOOTHING)
            locked["future_y"] = old_future_y + ((new_future_y - old_future_y) * TARGET_POSITION_SMOOTHING)
            locked["last_seen"] = now
            _set_locked_target(runtime, locked)
            return locked

        if now - last_seen <= TARGET_LOCK_LOST_TIMEOUT:
            return locked

        if latest and latest.get("score", 0.0) >= locked.get("score", 0.0) * TARGET_LOCK_SWITCH_SCORE_MULTIPLIER:
            latest["locked_at"] = now
            latest["last_seen"] = now
            _set_locked_target(runtime, latest)
            return latest

        _clear_locked_target(runtime)
        if latest:
            latest["locked_at"] = now
            latest["last_seen"] = now
            _set_locked_target(runtime, latest)
        return latest

    if latest:
        latest["locked_at"] = now
        latest["last_seen"] = now
        _set_locked_target(runtime, latest)
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
    remaining_distance = math.hypot(remaining_x, remaining_y)
    if remaining_distance <= BLOOM_SETTLE_DISTANCE:
        _clear_locked_target(runtime)
        return False
    _debug_log(
        f"moving toward planned target={target['name']} remaining=({remaining_x:.2f},{remaining_y:.2f}) score={target['score']:.2f}",
        min_interval=0.25,
        key="planned_move",
    )
    return _execute_movement_to_target(remaining_x, remaining_y)


def _process_combined_detections(runtime, output, transform, inference_ms, publish_petals=True):
    detections = _postprocess_tokens(output, min(BLOOM_MIN_CONFIDENCE, PETAL_CONFIDENCE_THRESHOLD))
    bloom_detections = []
    petal_overlays = []
    scale = float(transform["scale"])
    pad_x = float(transform["pad_x"])
    pad_y = float(transform["pad_y"])
    capture_width = float(runtime["capture"]["width"])
    capture_height = float(runtime["capture"]["height"])

    for (x1, y1, x2, y2), class_id, confidence in detections:
        capture_box = (
            max(0.0, min(capture_width, (x1 - pad_x) / scale)),
            max(0.0, min(capture_height, (y1 - pad_y) / scale)),
            max(0.0, min(capture_width, (x2 - pad_x) / scale)),
            max(0.0, min(capture_height, (y2 - pad_y) / scale)),
        )
        if class_id == 0 and confidence >= BLOOM_MIN_CONFIDENCE:
            bloom_detections.append((_capture_box_to_model(runtime, capture_box), 5, confidence))
            continue
        if class_id != 1 or confidence < PETAL_CONFIDENCE_THRESHOLD:
            continue

        petal_overlays.append({
            "box": capture_box,
            "confidence": float(confidence),
        })

    now = time.time()
    if not publish_petals:
        return bloom_detections

    runtime["latest_petal_detections"] = petal_overlays
    runtime["latest_petal_detection_time"] = now
    runtime["last_petal_detection_ms"] = inference_ms
    return bloom_detections


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


def _refresh_bloom_sprinkler_anchor(runtime):
    # A passive model hit can jump the coordinate origin several tiles and turn
    # a deterministic square into an erratic path. Re-anchor only while idle at
    # the origin; explicit recalibration remains available when needed.
    if runtime.get("movement_count", 0) > 0:
        return False
    now = time.time()
    if not force_anchor_needed(runtime) and now - runtime.get("last_anchor_time", 0.0) < BLOOM_SPRINKLER_ANCHOR_INTERVAL:
        return False
    return _refresh_sprinkler_anchor(runtime, force=force_anchor_needed(runtime))


def force_anchor_needed(runtime):
    return math.hypot(runtime.get("current_x", 0.0), runtime.get("current_y", 0.0)) >= BLOOM_FORCE_ANCHOR_DISTANCE


def _initialise_runtime():
    if cv2 is None or np is None:
        raise RuntimeError(
            "Must install opencv-python and numpy before using BloomsAI, please run install dependencies before continuing."
        )

    #_set_start_camera_angle()

    model_label, model_filename, model_size, model_output = BLOOM_MODEL_VARIANTS[BLOOM_MODEL_SELECTION]
    combined_path = MODEL_DIR / model_filename
    if not combined_path.exists():
        download_result = _check_missing_models([model_filename])
    if not combined_path.exists():
        failures = download_result.get("failures", {})
        detail = f" Download attempt failed: {'; '.join(failures.values())}" if failures else ""
        raise FileNotFoundError(f"No combined bloom and petal AI model was found: {combined_path}.{detail}")
    if ct is None:
        try:
            import subprocess
            import sys
            import importlib

            subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "coremltools"])
            globals()["ct"] = importlib.import_module("coremltools")
        except Exception as exc:
            raise RuntimeError(
                "coremltools is required but automatic install failed: " + str(exc) + ". Please install coremltools before using BloomsAI, then restart the macro."
            )
    if Image is None:
        raise RuntimeError("Pillow is required for CoreML BloomsAI, please run install dependencies before continuing.")

    sprinkler_model_kind = None
    sprinkler_candidate = MODEL_DIR / "sprinkler_detection_standard.mlmodelc"
    if sprinkler_candidate.exists():
        sprinkler_model_kind = "coreml"
    else:
        sprinkler_candidate = MODEL_DIR / "sprinkler_detection_standard.onnx"
        if sprinkler_candidate.exists():
            sprinkler_model_kind = "opencv_onnx"
    sprinkler_path = sprinkler_candidate if sprinkler_candidate.exists() else None

    capture = _build_capture()
    token_crop_info = _token_crop_for_capture(capture)
    upper_token_monitor = None
    upper_token_bbox = None
    # Supplemental full-viewport inference catches blooms near every screen edge.
    upper_token_crop = (0, 0, int(capture["width"]), int(capture["height"]))
    if capture["backend"] == "mss":
        monitor = capture["monitor"]
        upper_token_monitor = {
            "left": int(monitor["left"]),
            "top": int(monitor["top"]),
            "width": int(capture["width"]),
            "height": int(capture["height"]),
        }
    elif capture["backend"] == "pil":
        left, top, _right, _bottom = capture["bbox"]
        upper_token_bbox = (
            int(left),
            int(top),
            int(left + capture["width"]),
            int(top + capture["height"]),
        )
    _debug_log(
        f"capture backend={capture['backend']} size={capture['width']}x{capture['height']} combined_model={combined_path} sprinkler_model={sprinkler_path or 'missing'}"
    )
    points = _default_points(capture["width"], capture["height"])

    destination = np.array(
        [[-5, -5], [5, -5], [-5, 5], [5, 5]],
        dtype=np.float32,
    )
    homography, _ = cv2.findHomography(points, destination, cv2.RANSAC)
    if homography is None:
        raise RuntimeError("Could not compute BloomsAI homography.")

    combined_session, combined_input, combined_output = _load_coreml_model(
        combined_path,
        compiled_output_name=model_output,
    )
    sprinkler_session = None
    sprinkler_input = None
    sprinkler_output = None
    if sprinkler_path is not None:
        if sprinkler_model_kind == "opencv_onnx":
            sprinkler_session, sprinkler_input, sprinkler_output = _load_onnx_model(sprinkler_path)
            _delete_model_path(MODEL_DIR / "sprinkler_detection_standard.mlmodelc")
            _delete_model_path(MODEL_DIR / "sprinkler.mlpackage")
        else:
            sprinkler_session, sprinkler_input, sprinkler_output = _load_coreml_model(sprinkler_path)
            _delete_model_path(MODEL_DIR / "sprinkler_detection_standard.onnx")
            _delete_model_path(MODEL_DIR / "sprinkler.onnx")
            _delete_model_path(MODEL_DIR / "sprinkler.mlpackage")

    return {
        "runtime_version": RUNTIME_VERSION,
        "capture": capture,
        "token_crop": token_crop_info["rect"],
        "upper_token_monitor": upper_token_monitor,
        "upper_token_bbox": upper_token_bbox,
        "upper_token_crop": upper_token_crop,
        "combined_session": combined_session,
        "combined_input": combined_input,
        "combined_output": combined_output,
        "combined_model_kind": "coreml",
        "combined_model_selection": BLOOM_MODEL_SELECTION,
        "combined_model_label": model_label,
        "combined_input_width": model_size,
        "combined_input_height": model_size,
        "sprinkler_session": sprinkler_session,
        "sprinkler_input": sprinkler_input,
        "sprinkler_output": sprinkler_output,
        "sprinkler_model_kind": sprinkler_model_kind,
        "homography": homography,
        "current_x": 0.0,
        "current_y": 0.0,
        "movement_count": 0,
        "initialised_at": time.time(),
        "video_writer": None,
        "video_path": "",
        "last_recording_frame_time": 0.0,
        "detection_fps": None,
        "last_detection_ms": None,
        "last_timing_ms": {},
        "latest_detections": [],
        "latest_target": None,
        "latest_bloom_candidates": [],
        "locked_target": None,
        "latest_scan_time": 0.0,
        "last_anchor_time": 0.0,
        "last_anchor": {},
        "last_sprinkler_detection": {},
        "last_sprinkler_status": "",
        "movement_active": False,
        "movement_revision": 0,
        "movement_requires_fresh_scan": False,
        "idle_square_index": 0,
        "scan_lock": threading.Lock(),
        "scanner_stop_event": None,
        "scanner_thread": None,
        "latest_petal_detections": [],
        "latest_petal_detection_time": 0.0,
        "last_petal_detection_ms": None,
        "bloom_mode": "patrol",
        "active_bloom": None,
        "bloom_last_visible_time": 0.0,
        "bloom_contact_vector": None,
        "bloom_contact_confirmations": 0,
        "bloom_contact_last_seen_at": 0.0,
        "bloom_contact_last_move_time": 0.0,
        "bloom_contact_distance": 0.0,
        "petal_orbit_center": None,
        "petal_orbit_deadline": 0.0,
        "petal_orbit_index": None,
    }


runtime = _runtime_state()
if (
    runtime.get("runtime_version") != RUNTIME_VERSION
    or runtime.get("combined_model_selection") != BLOOM_MODEL_SELECTION
):
    _stop_scanner_thread(runtime)
    _release_video_writer(runtime)
    runtime.clear()
if not runtime.get("ready"):
    try:
        runtime.clear()
        runtime.update(_initialise_runtime())
        runtime["ready"] = True
        runtime["error"] = ""
        _debug_log(
            f"runtime ready combined_model={runtime['combined_model_label']} input={runtime['combined_input']} output={runtime['combined_output']} bloom_confidence={BLOOM_MIN_CONFIDENCE} petal_confidence={PETAL_CONFIDENCE_THRESHOLD} record={RECORD_VIDEO}"
        )
    except Exception as exc:
        runtime["ready"] = False
        runtime["error"] = str(exc)
        _debug_log(f"initialisation failed: {exc}")


if not runtime.get("ready"):
    print(f"[blooms_ai] {runtime.get('error', 'initialisation failed')}")
else:
    try:
        if not runtime.get("latest_scan_time"):
            _scan_tokens_once(runtime)
        _ensure_scanner_thread(runtime)
        _refresh_bloom_sprinkler_anchor(runtime)

        target = _locked_target(runtime) or _latest_target(runtime)
        bloom_mode = runtime.get("bloom_mode", "patrol")
        if bloom_mode in ("work", "orbit"):
            _execute_bloom_sequence(runtime)
        elif target:
            _debug_log(
                f"target={target['name']} confidence={target['confidence']:.2f} score={target['score']:.2f} planned=({target['future_x']:.2f},{target['future_y']:.2f})",
                min_interval=0.25,
                key="target",
            )
            if not _execute_planned_movement(runtime):
                if target.get("name") == BLOOM_LABEL:
                    _start_bloom_work(runtime, target)
                    _execute_bloom_sequence(runtime)
        else:
            detections = runtime.get("latest_detections", [])
            _debug_log(
                f"no target from detections={len(detections)} pos=({runtime['current_x']:.2f},{runtime['current_y']:.2f})",
                min_interval=0.5,
                key="no_target",
            )
            _execute_sprinkler_patrol(runtime)
    except Exception as exc:
        runtime["ready"] = False
        runtime["error"] = str(exc)
        _release_video_writer(runtime)
        print(f"[blooms_ai] runtime error: {exc}")
