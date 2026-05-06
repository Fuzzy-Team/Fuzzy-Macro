"""
Pattern: Fuzzy AI Gather
Description: Uses blue.onnx for token targeting and sprinkler.onnx for returns.
Best for: Blue-focused gathering where you want token chasing instead of a fixed path.
Width: Expands the leash radius and target clustering range.
Size: Scales each movement step so the pattern still respects the GUI controls.

Requirements:
- onnxruntime
- opencv-python
- numpy
- mss or Pillow
- blue.onnx and sprinkler.onnx

- Version 1.4
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
    import onnxruntime as ort
except Exception as _onnx_error:
    ort = None

try:
    import mss
except Exception:
    mss = None

try:
    from PIL import ImageGrab
except Exception:
    ImageGrab = None


INPUT_WIDTH = 864
INPUT_HEIGHT = 864
SPRINKLER_INPUT_WIDTH = 736
SPRINKLER_INPUT_HEIGHT = 736
NMS_THRESHOLD = 0.5
CONFIDENCE_THRESHOLD = 0.4
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

PREFERRED_TOKENS = {
    "Token Link": 100,
    "Focus": 80,
    "Melody": 70,
    "Blue Boost": 65,
    "Honey Mark": 60,
    "Honey Mark Token": 60,
    "Pollen Mark": 50,
    "Pollen Mark Token": 50,
    "Haste": 40,
}
IGNORED_TOKENS = {"Honey", "Blueberry"}

NORMALIZED_CAL_RATIOS = [
    (0.395314, 0.427995),
    (0.597795, 0.430686),
    (0.320584, 0.721513),
    (0.670597, 0.722439),
]

LABELS_BLUE = {
    0: "Baby Love", 1: "Beamstorm", 2: "Beesmas Cheer", 3: "Black Bear Morph",
    4: "Blue Bomb", 5: "Blue Bomb Sync", 6: "Blue Boost", 7: "Blue Pulse",
    8: "Blueberry", 9: "Brown Bear Morph", 10: "Buzz Bomb", 11: "Festive Blessing",
    12: "Festive Gift", 13: "Festive Mark", 14: "Festive Mark Token", 15: "Fetch",
    16: "Focus", 17: "Fuzz Bomb Field", 18: "Fuzz Bombs Token", 19: "Glitch Token",
    20: "Glob", 21: "Gumdrop Barrage", 22: "Haste", 23: "Honey",
    24: "Honey Mark", 25: "Honey Mark Token", 26: "Impale", 27: "Inflate Balloons",
    28: "Inspire", 29: "Map Corruption", 30: "Melody", 31: "Mind Hack",
    32: "Mother Bear Morph", 33: "Panda Bear Morph", 34: "Pineapple", 35: "Polar Bear Morph",
    36: "Pollen Haze", 37: "Pollen Mark", 38: "Pollen Mark Token", 39: "Puppy Ball",
    40: "Puppy Love", 41: "Rain Cloud", 42: "Red Bomb", 43: "Red Boost",
    44: "Science Bear Morph", 45: "Scratch", 46: "Snowflake", 47: "Snowglobe Shake",
    48: "Strawberry", 49: "Summon Frog", 50: "Sunflower Seed", 51: "Surprise Party",
    52: "Tabby Love", 53: "Token Link", 54: "Tornado", 55: "White Boost",
}

LABELS_SPRINKLER = {
    0: "Basic",
    1: "Diamond",
    2: "Gold",
    3: "Silver",
    4: "Supreme",
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
CAPTURE_BACKEND = _coerce_text(globals().get("pattern_capture_backend"), "auto").lower()
DEBUG_MODE = _coerce_bool(globals().get("pattern_debug_mode"), DEBUG_MODE)
RECORD_VIDEO = _coerce_bool(globals().get("pattern_record_video"), RECORD_VIDEO)
RECORD_VIDEO_FPS = _coerce_float(globals().get("pattern_record_video_fps"), RECORD_VIDEO_FPS)
PREFERRED_TOKENS = _preferred_token_weights(globals().get("pattern_preferred_tokens"), PREFERRED_TOKENS)
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


def _preprocess(frame, input_width, input_height, use_float16):
    resized = cv2.resize(frame, (int(input_width), int(input_height)), interpolation=cv2.INTER_LINEAR)
    if resized.ndim == 3 and resized.shape[2] == 4:
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGRA2RGB)
    else:
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)

    dtype = np.float16 if use_float16 else np.float32
    normalized = rgb.astype(dtype) / 255.0
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
    if CAPTURE_BACKEND in ("auto", "mss") and mss is not None:
        session = mss.mss()
        monitor = session.monitors[1]
        return {
            "backend": "mss",
            "session": session,
            "monitor": monitor,
            "width": monitor["width"],
            "height": monitor["height"],
        }

    if CAPTURE_BACKEND in ("auto", "pil", "pillow") and ImageGrab is not None:
        width, height = ImageGrab.grab().size
        return {"backend": "pil", "width": width, "height": height}

    raise RuntimeError(f"No supported capture backend found for '{CAPTURE_BACKEND}'. Install mss or Pillow.")


def _grab_frame(runtime):
    if runtime["capture"]["backend"] == "mss":
        monitor = runtime["capture"]["monitor"]
        return np.array(runtime["capture"]["session"].grab(monitor))

    image = ImageGrab.grab()
    return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)


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
        "updated_at": time.time(),
    }


def _annotate_recording_frame(runtime, frame):
    annotated = _bgr_frame(frame)
    frame_h, frame_w = annotated.shape[:2]
    scale_x = frame_w / float(INPUT_WIDTH)
    scale_y = frame_h / float(INPUT_HEIGHT)

    overlay = runtime.get("latest_recording_overlay", {})
    detections = overlay.get("detections", [])
    target = overlay.get("target")
    target_box = target.get("box") if isinstance(target, dict) else None

    for box, class_id, confidence in detections:
        token_name = LABELS_BLUE.get(class_id, f"class {class_id}")
        x1, y1, x2, y2 = box
        left = max(0, min(frame_w - 1, int(round(x1 * scale_x))))
        top = max(0, min(frame_h - 1, int(round(y1 * scale_y))))
        right = max(0, min(frame_w - 1, int(round(x2 * scale_x))))
        bottom = max(0, min(frame_h - 1, int(round(y2 * scale_y))))
        is_target = target_box == box
        if token_name in IGNORED_TOKENS:
            color = (120, 120, 120)
        elif is_target:
            color = (0, 255, 255)
        else:
            color = (80, 220, 80)
        cv2.rectangle(annotated, (left, top), (right, bottom), color, 2 if is_target else 1)
        _draw_label(annotated, f"{token_name} {confidence:.2f}", left, top - 4, color)

    status_lines = [
        f"tokens={len(detections)} pos=({overlay.get('current_x', 0.0):.2f},{overlay.get('current_y', 0.0):.2f}) moves={overlay.get('movement_count', 0)}",
        f"target={target['name']} score={target['score']:.2f} move=({target['tx']:.2f},{target['ty']:.2f})" if target else "target=None",
    ]
    for index, line in enumerate(status_lines):
        _draw_label(annotated, line, 10, 24 + (index * 24), (255, 255, 255))

    detection_fps = overlay.get("detection_fps")
    detection_ms = overlay.get("last_detection_ms")
    fps_text = "detect FPS: --" if detection_fps is None else f"detect FPS: {detection_fps:.1f}"
    if detection_ms is not None:
        fps_text += f" ({detection_ms:.0f}ms)"
    (text_w, _text_h), _baseline = cv2.getTextSize(fps_text, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
    _draw_label(annotated, fps_text, max(10, frame_w - text_w - 18), 24, (255, 255, 255))

    return annotated


def _recording_thread(runtime):
    frame_interval = 1.0 / max(RECORD_VIDEO_FPS, 1.0)
    next_frame_time = time.time()
    stop_event = runtime.get("recording_stop_event")

    while stop_event is not None and not stop_event.is_set():
        now = time.time()
        if now < next_frame_time:
            time.sleep(min(next_frame_time - now, 0.05))
            continue

        try:
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


def _load_session(model_path):
    available = ort.get_available_providers()
    preferred = [
        "CoreMLExecutionProvider",
        "AzureExecutionProvider",
        "DmlExecutionProvider",
        "CUDAExecutionProvider",
        "CPUExecutionProvider",
    ]
    providers = [provider for provider in preferred if provider in available] or available
    session_options = ort.SessionOptions()
    session_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    session_options.enable_mem_pattern = True
    session_options.enable_cpu_mem_arena = True
    session_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    session = ort.InferenceSession(str(model_path), sess_options=session_options, providers=providers)
    input_meta = session.get_inputs()[0]
    return session, input_meta.name, "float16" in input_meta.type.lower()


def _relative_distance(x, y, homography):
    point = np.array([[[x, y + 15]]], dtype=np.float32)
    transformed = cv2.perspectiveTransform(point, homography)
    tx, ty = transformed[0][0]
    return float(tx), float(-ty)


def _get_importance(token_name):
    return PREFERRED_TOKENS.get(token_name, 1)


def _token_metrics():
    max_leash = 4.0 + (0.45 * max(width - 1, 0)) + (0.35 * size)
    return {
        "max_leash": max_leash,
        "soft_leash": max_leash * 0.625,
        "max_consider": max_leash + 1.0 + (0.15 * width),
        "cluster_radius": 1.6 + (0.1 * width),
        "proximity_exp": 1.25,
        "toward_home_bonus": 1.4,
        "away_from_home_penalty": 0.8,
        "cluster_bonus_per_token": 0.25,
        "leash_edge_penalty": 0.5,
    }


def _find_best_token(runtime, detections):
    metrics = _token_metrics()
    current_x = runtime["current_x"]
    current_y = runtime["current_y"]
    current_dist = math.hypot(current_x, current_y)

    scale_x = runtime["capture"]["width"] / float(INPUT_WIDTH)
    scale_y = runtime["capture"]["height"] / float(INPUT_HEIGHT)

    candidates = []
    for box, class_id, confidence in detections:
        token_name = LABELS_BLUE.get(class_id)
        if not token_name or token_name in IGNORED_TOKENS:
            continue

        x1, y1, x2, y2 = box
        center_x = ((x1 + x2) / 2.0) * scale_x
        center_y = ((y1 + y2) / 2.0) * scale_y
        tx, ty = _relative_distance(center_x, center_y, runtime["homography"])
        distance = math.hypot(tx, ty)

        if distance < MIN_TOKEN_DISTANCE or distance > metrics["max_consider"]:
            continue

        future_x = current_x + tx
        future_y = current_y + ty
        future_dist = math.hypot(future_x, future_y)
        if future_dist > metrics["max_leash"]:
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
                "confidence": confidence,
            }
        )

    if not candidates:
        return None

    for candidate in candidates:
        nearby = 0
        for other in candidates:
            if other is candidate:
                continue
            if math.hypot(candidate["future_x"] - other["future_x"], candidate["future_y"] - other["future_y"]) < metrics["cluster_radius"]:
                nearby += 1
        candidate["score"] *= 1.0 + (nearby * metrics["cluster_bonus_per_token"])

    return max(candidates, key=lambda item: item["score"])


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
    for segment_type, keys, distance in _movement_segments(tx, ty):
        if segment_type == "diagonal":
            _tile_multi_walk(keys, distance)
        else:
            _tile_walk(keys[0], distance)
        moved = True

    if moved:
        runtime = _runtime_state()
        runtime["current_x"] += tx
        runtime["current_y"] += ty
        runtime["movement_count"] += 1
        runtime["last_token_time"] = time.time()

    return moved


def _find_sprinkler(runtime):
    if runtime.get("sprinkler_session") is None:
        return None

    frame = _grab_frame(runtime)
    tensor = _preprocess(
        frame,
        SPRINKLER_INPUT_WIDTH,
        SPRINKLER_INPUT_HEIGHT,
        runtime["sprinkler_use_float16"],
    )
    output = runtime["sprinkler_session"].run(None, {runtime["sprinkler_input"]: tensor})
    detections = _postprocess(output, SPRINKLER_CONFIDENCE_THRESHOLD)

    scale_x = runtime["capture"]["width"] / float(SPRINKLER_INPUT_WIDTH)
    scale_y = runtime["capture"]["height"] / float(SPRINKLER_INPUT_HEIGHT)

    best = None
    best_distance = float("inf")
    for box, class_id, confidence in detections:
        label = LABELS_SPRINKLER.get(class_id)
        if TARGET_SPRINKLER_LABEL and label != TARGET_SPRINKLER_LABEL:
            continue

        x1, y1, x2, y2 = box
        center_x = ((x1 + x2) / 2.0) * scale_x
        center_y = ((y1 + y2) / 2.0) * scale_y
        tx, ty = _relative_distance(center_x, center_y, runtime["homography"])
        distance = math.hypot(tx, ty)

        if distance > MAX_SPRINKLER_DISTANCE:
            continue

        if distance < best_distance:
            best_distance = distance
            best = (tx, ty, distance, label, confidence)

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

    tx, ty, distance, _label, _confidence = result
    if distance >= SPRINKLER_ARRIVAL_THRESHOLD:
        _debug_log(f"returning to sprinkler: move=({tx:.2f},{ty:.2f}) distance={distance:.2f}")
        _execute_movement(tx, ty)

    runtime["current_x"] = 0.0
    runtime["current_y"] = 0.0
    runtime["movement_count"] = 0
    runtime["last_idle_return_time"] = time.time()
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
    self.keyboard.press("pageup")
    self.keyboard.press("pageup")

    global ort
    if ort is None:
        # Try to install onnxruntime into the active Python environment and import it.
        try:
            import subprocess
            import sys
            import importlib

            subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "onnxruntime"])
            ort = importlib.import_module("onnxruntime")
            globals()["ort"] = ort
        except Exception as exc:
            raise RuntimeError(
                "onnxruntime is required but automatic install failed: " + str(exc) + ". Please install onnxruntime before using AI Gathering, then restart the macro."
            )

    if cv2 is None or np is None:
        raise RuntimeError(
            "Must install opencv-python and numpy before using AI Gathering, please run install dependencies before continuing."
        )


    token_path = MODEL_DIR / "blue.onnx"
    if not token_path.exists():
        raise FileNotFoundError(f"blue.onnx was not found at fixed path: {token_path}")

    sprinkler_candidate = MODEL_DIR / "sprinkler.onnx"
    sprinkler_path = sprinkler_candidate if sprinkler_candidate.exists() else None

    capture = _build_capture()
    _debug_log(
        f"capture backend={capture['backend']} size={capture['width']}x{capture['height']} token_model={token_path} sprinkler_model={sprinkler_path or 'missing'}"
    )
    points = _default_points(capture["width"], capture["height"])

    destination = np.array(
        [[-5, -5], [5, -5], [-5, 5], [5, 5]],
        dtype=np.float32,
    )
    homography, _ = cv2.findHomography(points, destination, cv2.RANSAC)
    if homography is None:
        raise RuntimeError("Could not compute AI gather homography.")

    token_session, token_input, token_use_float16 = _load_session(token_path)
    sprinkler_session = None
    sprinkler_input = None
    sprinkler_use_float16 = False
    if sprinkler_path is not None:
        sprinkler_session, sprinkler_input, sprinkler_use_float16 = _load_session(sprinkler_path)

    return {
        "capture": capture,
        "token_session": token_session,
        "token_input": token_input,
        "token_use_float16": token_use_float16,
        "sprinkler_session": sprinkler_session,
        "sprinkler_input": sprinkler_input,
        "sprinkler_use_float16": sprinkler_use_float16,
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
    }


runtime = _runtime_state()
if not runtime.get("ready"):
    try:
        runtime.clear()
        runtime.update(_initialise_runtime())
        runtime["ready"] = True
        runtime["error"] = ""
        _debug_log(
            f"runtime ready providers={runtime['token_session'].get_providers()} confidence={CONFIDENCE_THRESHOLD} ignored={sorted(IGNORED_TOKENS)} record={RECORD_VIDEO}"
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
        if _should_recalibrate(runtime):
            _recalibrate(runtime)

        detection_start = time.time()
        frame = _grab_frame(runtime)
        tensor = _preprocess(frame, INPUT_WIDTH, INPUT_HEIGHT, runtime["token_use_float16"])
        output = runtime["token_session"].run(None, {runtime["token_input"]: tensor})
        detections = _postprocess(output, CONFIDENCE_THRESHOLD)
        target = _find_best_token(runtime, detections)
        _update_detection_fps(runtime, time.time() - detection_start)
        _record_debug_frame(runtime, frame, detections, target)

        if target:
            _debug_log(
                f"target={target['name']} confidence={target['confidence']:.2f} score={target['score']:.2f} move=({target['tx']:.2f},{target['ty']:.2f}) detections={len(detections)}",
                min_interval=0.25,
                key="target",
            )
            _execute_movement(target["tx"], target["ty"])
        else:
            _debug_log(
                f"no target from detections={len(detections)} pos=({runtime['current_x']:.2f},{runtime['current_y']:.2f})",
                min_interval=0.5,
                key="no_target",
            )
            now = time.time()
            should_sweep = now - runtime.get("last_no_target_sweep_time", 0.0) >= NO_TARGET_SWEEP_INTERVAL
            if now - runtime["last_idle_return_time"] >= IDLE_RETURN_INTERVAL:
                runtime["last_idle_return_time"] = now
                if _recalibrate(runtime):
                    runtime["last_token_time"] = time.time()
                elif should_sweep:
                    runtime["last_no_target_sweep_time"] = now
                    _fallback_pattern()
            elif should_sweep:
                runtime["last_no_target_sweep_time"] = now
                _fallback_pattern()
    except Exception as exc:
        runtime["ready"] = False
        runtime["error"] = str(exc)
        _release_video_writer(runtime)
        print(f"[fuzzy_ai_gather] runtime error: {exc}")
        _fallback_pattern()
