"""Shared helpers for BloomsAI and Fuzzy AI Gather patterns."""

from __future__ import annotations

import math
import shutil
import subprocess
import threading
import time
from pathlib import Path

from modules.misc.modelManager import import_coremltools

try:
    import cv2
except Exception:
    cv2 = None

try:
    import numpy as np
except Exception:
    np = None

# None before macOS 12, where AI Gather uses the ONNX models instead
ct = import_coremltools()

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

NORMALIZED_CAL_RATIOS = [
    (0.395314, 0.427995),
    (0.597795, 0.430686),
    (0.320584, 0.721513),
    (0.670597, 0.722439),
]

LABELS_SPRINKLER = {
    0: "Sprinkler",
    1: "Supreme",
}


def src_root():
    """Return the macro `src/` directory (parent of `modules/`)."""
    try:
        return Path(__file__).resolve().parents[2]
    except Exception:
        return Path.cwd().resolve()


MODEL_DIR = (src_root() / "data" / "models").resolve()


def coreml_available():
    """Return whether coremltools loaded successfully in this environment."""
    return ct is not None


def coerce_float(value, default):
    try:
        return float(value)
    except Exception:
        return float(default)


def coerce_int(value, default):
    try:
        return int(float(value))
    except Exception:
        return int(default)


def coerce_text(value, default=""):
    if value is None:
        return default
    return str(value).strip()


def coerce_bool(value, default=False):
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


def parse_token_names(value):
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


def preferred_token_weights(value, default_weights):
    names = parse_token_names(value)
    if not names:
        return dict(default_weights)

    max_weight = 100
    step = 5
    out = {}
    for index, name in enumerate(names):
        out[name] = max(max_weight - (index * step), 5)
    return out


def ignored_token_names(value, default_names):
    names = parse_token_names(value)
    if not names:
        return set(default_names)
    return set(names)


def check_missing_models(tag, model_names):
    try:
        from modules.misc.modelManager import ensure_missing_models

        result = ensure_missing_models(model_names)
        if result.get("downloaded"):
            print(f"[{tag}] Downloaded missing AI model(s): {', '.join(result['downloaded'])}")
        elif result.get("missing_remote"):
            print(f"[{tag}] Missing AI model(s) were not found remotely: {', '.join(result['missing_remote'])}")
        return result
    except Exception as exc:
        print(f"[{tag}] Could not check missing AI models: {exc}")
        return {"failures": {"model download": str(exc)}}


def debug_log(tag, message, debug_mode, min_interval=0.0, key=None, log_times=None):
    if not debug_mode:
        return
    if log_times is None:
        log_times = {}

    now = time.time()
    log_key = key or message
    last = log_times.get(log_key, 0.0)
    if min_interval > 0 and now - last < min_interval:
        return

    log_times[log_key] = now
    print(f"[{tag}][debug] {message}", flush=True)


def get_runtime_state(owner, attr_name, global_name, globals_dict):
    state = getattr(owner, attr_name, None) if owner is not None else None
    if isinstance(state, dict):
        return state

    state = globals_dict.get(global_name)
    if not isinstance(state, dict):
        state = {}
        globals_dict[global_name] = state

    if owner is not None:
        try:
            setattr(owner, attr_name, state)
        except Exception:
            pass

    return state


def default_points(screen_w, screen_h):
    return np.array(
        [[int(round(nx * screen_w)), int(round(ny * screen_h))] for nx, ny in NORMALIZED_CAL_RATIOS],
        dtype=np.float32,
    )


def compute_homography(capture_width, capture_height):
    points = default_points(capture_width, capture_height)
    destination = np.array(
        [[-5, -5], [5, -5], [-5, 5], [5, 5]],
        dtype=np.float32,
    )
    homography, _ = cv2.findHomography(points, destination, cv2.RANSAC)
    return homography


def preprocess_coreml_image(frame, input_width, input_height):
    if frame.shape[1] != int(input_width) or frame.shape[0] != int(input_height):
        frame = cv2.resize(frame, (int(input_width), int(input_height)), interpolation=cv2.INTER_LINEAR)

    if frame.ndim == 3 and frame.shape[2] == 4:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB)
    else:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    if Image is None:
        raise RuntimeError("Pillow is required for CoreML inference.")
    return Image.fromarray(rgb)


def letterbox_rgb(frame, input_width, input_height):
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
    return letterboxed, {"scale": scale, "pad_x": pad_x, "pad_y": pad_y}


def preprocess_petal_image(frame, input_width, input_height):
    letterboxed, transform = letterbox_rgb(frame, input_width, input_height)
    if Image is None:
        raise RuntimeError("Pillow is required for CoreML petal inference.")
    return Image.fromarray(letterboxed), transform


def preprocess_petal_onnx_image(frame, input_width, input_height):
    letterboxed, transform = letterbox_rgb(frame, input_width, input_height)
    normalized = letterboxed.astype(np.float32) / 255.0
    chw = np.transpose(normalized, (2, 0, 1))
    return np.expand_dims(chw, axis=0), transform


def preprocess_onnx_image(frame, input_width, input_height):
    if frame.shape[1] != int(input_width) or frame.shape[0] != int(input_height):
        frame = cv2.resize(frame, (int(input_width), int(input_height)), interpolation=cv2.INTER_LINEAR)

    if frame.ndim == 3 and frame.shape[2] == 4:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB)
    else:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    normalized = rgb.astype(np.float32) / 255.0
    chw = np.transpose(normalized, (2, 0, 1))
    return np.expand_dims(chw, axis=0)


def postprocess(output, confidence_threshold):
    """Decode classic YOLO ONNX output shaped [1, 4+nc, N]."""
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


def postprocess_tokens(output, confidence_threshold):
    """Decode CoreML end2end output shaped [1, max_det, 6] as xyxy/conf/cls."""
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


def decode_detections(runtime, prefix, output, confidence_threshold):
    if runtime.get(f"{prefix}_model_kind") == "opencv_onnx":
        return postprocess(output, confidence_threshold)
    return postprocess_tokens(output, confidence_threshold)


def build_capture(viewport, capture_backend="auto"):
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

    backend = (capture_backend or "auto").lower()
    if backend in ("auto", "mss") and mss is not None:
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
            "viewport": viewport,
            "session": session,
            "monitor": monitor,
            "width": width_px,
            "height": height_px,
        }

    if backend in ("auto", "pil", "pillow") and ImageGrab is not None:
        if width_px <= 0 or height_px <= 0:
            width_px, height_px = ImageGrab.grab().size
            left = 0
            top = 0
        return {
            "backend": "pil",
            "viewport": viewport,
            "bbox": (left, top, left + width_px, top + height_px),
            "width": width_px,
            "height": height_px,
        }

    raise RuntimeError(f"No supported capture backend found for '{backend}'. Install mss or Pillow.")


def normalize_capture_frame(frame, capture):
    """Return a frame in the logical point space used by the AI geometry."""
    if cv2 is None or getattr(frame, "shape", None) is None or len(frame.shape) < 2:
        return frame
    width_px = int(capture.get("width") or 0)
    height_px = int(capture.get("height") or 0)
    if width_px <= 0 or height_px <= 0:
        return frame
    if frame.shape[1] == width_px and frame.shape[0] == height_px:
        return frame
    return cv2.resize(frame, (width_px, height_px), interpolation=cv2.INTER_AREA)


def mss_grab_to_array(session, monitor, capture=None):
    shot = session.grab(monitor)
    frame = np.frombuffer(shot.raw, dtype=np.uint8).reshape((shot.height, shot.width, 4))
    if capture is not None:
        frame = normalize_capture_frame(frame, capture)
    return frame


def grab_frame(runtime):
    capture = runtime["capture"]
    if capture["backend"] == "mss":
        monitor = capture["monitor"]
        return mss_grab_to_array(capture["session"], monitor, capture=capture)

    image = ImageGrab.grab(bbox=capture.get("bbox"))
    frame = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
    return normalize_capture_frame(frame, capture)



def crop_rect(frame, rect):
    left, top, width_px, height_px = rect
    return frame[top:top + height_px, left:left + width_px]


def init_frame_mailbox(runtime):
    if runtime.get("frame_lock") is None:
        runtime["frame_lock"] = threading.Lock()
    runtime.setdefault("latest_frame", None)
    runtime.setdefault("latest_frame_time", 0.0)
    runtime.setdefault("latest_frame_id", 0)
    runtime.setdefault("token_last_frame_id", 0)
    runtime.setdefault("sprinkler_last_frame_id", 0)


def publish_frame(runtime, frame):
    viewport = runtime.get("capture", {}).get("viewport")
    if getattr(viewport, "questMenuVisibleForAI", False):
        # The quest panel uses logical screen coordinates; capture pixels may be Retina-scaled.
        capture = runtime["capture"]
        right = min(frame.shape[1], round(300 * frame.shape[1] / capture["width"]))
        top = round(150 * frame.shape[0] / capture["height"])
        frame = frame.copy()
        frame[top:, :right] = 0
    lock = runtime.get("frame_lock")
    if lock is None:
        init_frame_mailbox(runtime)
        lock = runtime["frame_lock"]
    with lock:
        runtime["latest_frame"] = frame
        runtime["latest_frame_time"] = time.time()
        runtime["latest_frame_id"] = int(runtime.get("latest_frame_id", 0)) + 1
        return runtime["latest_frame_id"]


def get_latest_frame(runtime, *, copy=True, after_id=None):
    lock = runtime.get("frame_lock")
    if lock is None:
        return None, 0, 0.0
    with lock:
        frame = runtime.get("latest_frame")
        frame_id = int(runtime.get("latest_frame_id", 0))
        frame_time = float(runtime.get("latest_frame_time", 0.0))
        if frame is None:
            return None, frame_id, frame_time
        if after_id is not None and frame_id <= int(after_id):
            return None, frame_id, frame_time
        return (frame.copy() if copy else frame), frame_id, frame_time


def wait_for_latest_frame(runtime, *, after_id=0, timeout=0.05, copy=True):
    """Return the newest mailbox frame, waiting briefly for a newer id when possible."""
    deadline = time.time() + max(timeout, 0.0)
    last_id = int(after_id or 0)
    while True:
        frame, frame_id, frame_time = get_latest_frame(runtime, copy=copy, after_id=last_id)
        if frame is not None:
            return frame, frame_id, frame_time
        if time.time() >= deadline:
            # Fall back to whatever is currently published (may be the same id).
            return get_latest_frame(runtime, copy=copy, after_id=None)
        time.sleep(0.001)


def capture_loop(runtime, interval, debug_log_fn=None):
    """Dedicated capture owner: publishes latest full frames into the mailbox."""
    stop_event = runtime.get("capture_stop_event")
    capture = runtime.get("capture") or {}
    session = None
    try:
        if capture.get("backend") == "mss" and mss is not None:
            session = mss.mss()
        while stop_event is not None and not stop_event.is_set():
            started = time.time()
            try:
                if not runtime.get("ready"):
                    return
                if session is not None:
                    frame = mss_grab_to_array(session, capture["monitor"], capture=capture)
                elif capture.get("backend") == "pil" and ImageGrab is not None:
                    image = ImageGrab.grab(bbox=capture.get("bbox"))
                    frame = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
                    frame = normalize_capture_frame(frame, capture)
                else:
                    frame = grab_frame(runtime)
                publish_frame(runtime, frame)
            except Exception as exc:
                if debug_log_fn:
                    debug_log_fn(f"capture error: {exc}", min_interval=1.0, key="capture_error")
                time.sleep(max(interval, 0.02))
                continue
            remaining = interval - (time.time() - started)
            time.sleep(max(remaining, 0.0))
    finally:
        if session is not None:
            try:
                session.close()
            except Exception:
                pass


def ensure_capture_thread(runtime, interval=0.016, debug_log_fn=None):
    init_frame_mailbox(runtime)
    thread = runtime.get("capture_thread")
    if thread is not None and thread.is_alive():
        return

    stop_event = runtime.get("capture_stop_event")
    if stop_event is None or stop_event.is_set():
        stop_event = threading.Event()
        runtime["capture_stop_event"] = stop_event

    thread = threading.Thread(
        target=capture_loop,
        args=(runtime, max(float(interval), 0.008)),
        kwargs={"debug_log_fn": debug_log_fn},
        daemon=True,
    )
    runtime["capture_thread"] = thread
    thread.start()
    if debug_log_fn:
        debug_log_fn("continuous capture thread started", min_interval=1.0, key="capture_started")


def stop_capture_thread(runtime=None):
    if not isinstance(runtime, dict):
        return
    stop_event = runtime.get("capture_stop_event")
    if stop_event is not None:
        stop_event.set()
    thread = runtime.get("capture_thread")
    if thread is not None and thread.is_alive() and thread is not threading.current_thread():
        try:
            thread.join(timeout=1)
        except Exception:
            pass
    runtime["capture_thread"] = None


def wait_for_capture_ready(runtime, timeout=1.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        frame, frame_id, _ = get_latest_frame(runtime, copy=False)
        if frame is not None and frame_id > 0:
            return True
        time.sleep(0.01)
    return False


def token_crop_for_capture(capture):
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


def model_point_to_capture(runtime, x, y):
    left, top, crop_w, crop_h = runtime["token_crop"]
    return (
        left + (x * crop_w / float(INPUT_WIDTH)),
        top + (y * crop_h / float(INPUT_HEIGHT)),
    )


def capture_box_to_model(runtime, box):
    left, top, crop_w, crop_h = runtime["token_crop"]
    x1, y1, x2, y2 = box
    return (
        (x1 - left) * INPUT_WIDTH / crop_w,
        (y1 - top) * INPUT_HEIGHT / crop_h,
        (x2 - left) * INPUT_WIDTH / crop_w,
        (y2 - top) * INPUT_HEIGHT / crop_h,
    )


def bgr_frame(frame):
    if frame.ndim == 3 and frame.shape[2] == 4:
        return cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
    return frame.copy()


def recording_dir():
    path = src_root() / "data" / "user" / "fuzzy_ai_recordings"
    path.mkdir(parents=True, exist_ok=True)
    return path


def draw_label(frame, text, x, y, color):
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.45
    thickness = 1
    (text_w, text_h), baseline = cv2.getTextSize(text, font, font_scale, thickness)
    y = max(y, text_h + 6)
    cv2.rectangle(frame, (x, y - text_h - baseline - 4), (x + text_w + 4, y + 2), color, -1)
    cv2.putText(frame, text, (x + 2, y - baseline - 1), font, font_scale, (0, 0, 0), thickness, cv2.LINE_AA)


def write_recording_frame(runtime, writer, annotated, frame_count=1, debug_log_fn=None):
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
        if debug_log_fn:
            debug_log_fn(f"recording write failed: {exc}", min_interval=5.0, key="record_write_failed")
        release_video_writer(runtime, debug_log_fn=debug_log_fn)


def recording_thread(runtime, debug_log_fn=None):
    fps = max(float(runtime.get("record_video_fps", 12.0)), 1.0)
    frame_interval = 1.0 / fps
    next_frame_time = time.time()
    stop_event = runtime.get("recording_stop_event")
    last_frame_id = 0

    try:
        while stop_event is not None and not stop_event.is_set():
            now = time.time()
            if now < next_frame_time:
                time.sleep(min(next_frame_time - now, 0.05))
                continue

            try:
                frame, frame_id, _ = wait_for_latest_frame(
                    runtime,
                    after_id=last_frame_id,
                    timeout=frame_interval,
                    copy=True,
                )
                if frame is None:
                    frame = grab_frame(runtime)
                else:
                    last_frame_id = frame_id
                annotate_fn = runtime.get("annotate_recording_frame")
                annotated = annotate_fn(runtime, frame) if callable(annotate_fn) else bgr_frame(frame)
                writer = runtime.get("video_writer")
                if writer is None:
                    return
                write_recording_frame(runtime, writer, annotated, frame_count=1, debug_log_fn=debug_log_fn)
            except Exception as exc:
                if debug_log_fn:
                    debug_log_fn(f"recording frame failed: {exc}", min_interval=5.0, key="record_frame_failed")

            next_frame_time += frame_interval
            if next_frame_time < time.time() - frame_interval:
                next_frame_time = time.time() + frame_interval
    finally:
        pass


def ensure_video_writer(runtime, frame, *, filename_prefix, record_video, record_video_fps, debug_log_fn=None):
    if not record_video or cv2 is None:
        return None

    writer = runtime.get("video_writer")
    if writer is not None:
        return writer

    bgr = bgr_frame(frame)
    height, width_px = bgr.shape[:2]
    filename = f"{filename_prefix}_{time.strftime('%Y%m%d_%H%M%S')}.mp4"
    output_path = recording_dir() / filename
    runtime["record_video_fps"] = record_video_fps

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
            str(max(record_video_fps, 1.0)),
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
            if debug_log_fn:
                debug_log_fn(f"ffmpeg recording failed to start: {exc}", min_interval=5.0, key="record_ffmpeg_failed")
    else:
        writer = None

    if writer is None:
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        cv_writer = cv2.VideoWriter(str(output_path), fourcc, max(record_video_fps, 1.0), (width_px, height))
        if not cv_writer.isOpened():
            runtime["video_writer"] = None
            if debug_log_fn:
                debug_log_fn(f"video recording failed to open: {output_path}", min_interval=5.0, key="record_open_failed")
            return None
        writer = {"kind": "opencv", "writer": cv_writer, "path": str(output_path)}

    runtime["video_writer"] = writer
    runtime["video_path"] = str(output_path)
    runtime["recording_stop_event"] = threading.Event()
    runtime["recording_lock"] = threading.Lock()
    runtime["recording_thread"] = threading.Thread(
        target=recording_thread,
        args=(runtime,),
        kwargs={"debug_log_fn": debug_log_fn},
        daemon=True,
    )
    runtime["recording_thread"].start()
    if debug_log_fn:
        debug_log_fn(f"recording video to {output_path}")
    return writer


def release_video_writer(runtime=None, debug_log_fn=None):
    if not isinstance(runtime, dict):
        return
    writer = runtime.get("video_writer")
    if writer is None:
        return

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
    if runtime.get("video_path") and debug_log_fn:
        debug_log_fn(f"saved recording: {runtime['video_path']}")


def update_detection_fps(runtime, elapsed):
    if elapsed <= 0:
        return
    fps = 1.0 / elapsed
    previous = runtime.get("detection_fps")
    runtime["detection_fps"] = fps if previous is None else ((previous * 0.8) + (fps * 0.2))
    runtime["last_detection_ms"] = elapsed * 1000.0


def load_coreml_model(model_path, compiled_output_name="var_1445"):
    if ct is None:
        raise RuntimeError("coremltools is required. Install coremltools, then restart the macro.")

    model_path = Path(model_path)
    if model_path.suffix.lower() == ".mlmodelc":
        compiled_model_class = getattr(ct.models, "CompiledMLModel", None)
        if compiled_model_class is None:
            raise RuntimeError(
                "This coremltools version cannot load compiled .mlmodelc bundles. Upgrade coremltools, then restart the macro."
            )
        model = compiled_model_class(str(model_path), compute_units=ct.ComputeUnit.ALL)
        return model, "image", compiled_output_name

    model = ct.models.MLModel(str(model_path), compute_units=ct.ComputeUnit.ALL)
    description = model.get_spec().description
    input_name = description.input[0].name
    output_name = description.output[0].name
    return model, input_name, output_name


def load_onnx_model(model_path):
    if cv2 is None:
        raise RuntimeError("OpenCV is required for ONNX AI gathering.")

    model = cv2.dnn.readNetFromONNX(str(model_path))
    return model, None, None


def delete_model_path(model_path, debug_log_fn=None):
    try:
        path = Path(model_path)
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()
    except Exception as exc:
        if debug_log_fn:
            debug_log_fn(
                f"could not delete alternate model {model_path}: {exc}",
                min_interval=10.0,
                key=f"delete_model_{model_path}",
            )


def run_model(runtime, prefix, image):
    if runtime.get(f"{prefix}_model_kind") == "opencv_onnx":
        session = runtime[f"{prefix}_session"]
        session.setInput(image)
        return [session.forward()]

    return [
        runtime[f"{prefix}_session"].predict(
            {runtime[f"{prefix}_input"]: image}
        )[runtime[f"{prefix}_output"]]
    ]


def relative_distance(x, y, homography):
    point = np.array([[[x, y + 15]]], dtype=np.float32)
    transformed = cv2.perspectiveTransform(point, homography)
    tx, ty = transformed[0][0]
    return float(tx), float(-ty)


def resolve_sprinkler_model(model_dir=None, tag="ai_gather", download=True):
    model_dir = Path(model_dir or MODEL_DIR)
    sprinkler_model_kind = None
    sprinkler_candidate = model_dir / "sprinkler_detection_standard.mlmodelc"
    if coreml_available() and sprinkler_candidate.exists():
        sprinkler_model_kind = "coreml"
    else:
        sprinkler_candidate = model_dir / "sprinkler_detection_standard.onnx"
        if sprinkler_candidate.exists():
            sprinkler_model_kind = "opencv_onnx"
        elif download:
            requested = ["sprinkler_detection_standard.onnx"]
            if coreml_available():
                requested.insert(0, "sprinkler_detection_standard.mlmodelc")
            check_missing_models(tag, requested)
            if coreml_available() and (model_dir / "sprinkler_detection_standard.mlmodelc").exists():
                sprinkler_candidate = model_dir / "sprinkler_detection_standard.mlmodelc"
                sprinkler_model_kind = "coreml"
            else:
                sprinkler_candidate = model_dir / "sprinkler_detection_standard.onnx"
                if sprinkler_candidate.exists():
                    sprinkler_model_kind = "opencv_onnx"
    sprinkler_path = sprinkler_candidate if sprinkler_candidate.exists() else None
    return sprinkler_path, sprinkler_model_kind


def load_sprinkler_session(sprinkler_path, sprinkler_model_kind, debug_log_fn=None):
    if sprinkler_path is None:
        return None, None, None
    if sprinkler_model_kind == "opencv_onnx":
        session, input_name, output_name = load_onnx_model(sprinkler_path)
        delete_model_path(MODEL_DIR / "sprinkler_detection_standard.mlmodelc", debug_log_fn)
        delete_model_path(MODEL_DIR / "sprinkler.mlpackage", debug_log_fn)
        return session, input_name, output_name

    session, input_name, output_name = load_coreml_model(sprinkler_path)
    delete_model_path(MODEL_DIR / "sprinkler_detection_standard.onnx", debug_log_fn)
    delete_model_path(MODEL_DIR / "sprinkler.onnx", debug_log_fn)
    delete_model_path(MODEL_DIR / "sprinkler.mlpackage", debug_log_fn)
    return session, input_name, output_name


def sprinkler_infer_lock(runtime):
    lock = runtime.get("sprinkler_infer_lock")
    if lock is None:
        lock = threading.Lock()
        runtime["sprinkler_infer_lock"] = lock
    return lock


def find_sprinkler(
    runtime,
    frame=None,
    *,
    confidence_threshold,
    max_distance,
    target_label=None,
):
    if runtime.get("sprinkler_session") is None:
        runtime["last_sprinkler_status"] = "model_missing"
        return None

    if frame is None:
        frame, _, _ = get_latest_frame(runtime, copy=True)
        if frame is None:
            frame = grab_frame(runtime)
    if runtime.get("sprinkler_model_kind") == "opencv_onnx":
        image = preprocess_onnx_image(frame, SPRINKLER_INPUT_WIDTH, SPRINKLER_INPUT_HEIGHT)
    else:
        image = preprocess_coreml_image(frame, SPRINKLER_INPUT_WIDTH, SPRINKLER_INPUT_HEIGHT)
    with sprinkler_infer_lock(runtime):
        output = run_model(runtime, "sprinkler", image)
    detections = decode_detections(runtime, "sprinkler", output, confidence_threshold)

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
        tx, ty = relative_distance(center_x, center_y, runtime["homography"])
        distance = math.hypot(tx, ty)
        scaled_box = (x1 * scale_x, y1 * scale_y, x2 * scale_x, y2 * scale_y)

        if distance > max_distance:
            continue

        if distance < best_any_distance:
            best_any_distance = distance
            best_any = (tx, ty, distance, label, confidence, scaled_box)

        if target_label and label != target_label:
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




def sprinkler_anchor_enabled(field_drift_compensation, use_sprinkler_model):
    return bool(field_drift_compensation and use_sprinkler_model)


def field_safe_radius(field_dimensions, fallback=None):
    """Convert the narrow field axis to a conservative center-to-edge tile radius."""
    try:
        narrow_axis = min(float(value) for value in field_dimensions if float(value) > 0)
    except (TypeError, ValueError):
        return fallback
    if narrow_axis <= 0:
        return fallback

    # Field dimensions are reference-speed milliseconds. At 18 studs/second
    # and roughly four studs per flower tile, 800 ms is about 3.6 tiles. Keep
    # twenty percent in reserve for imperfect movement and field geometry.
    return round(narrow_axis * 18.0 / 4000.0 * 0.8, 3)


def sprinkler_detect_should_run(runtime):
    """Run sprinkler inference whenever the model is loaded (same cadence as tokens)."""
    if runtime.get("sprinkler_session") is None:
        runtime["last_sprinkler_status"] = "model_missing"
        return False
    return True


def sprinkler_anchor_should_run(
    runtime,
    *,
    field_drift_compensation,
    use_sprinkler_model,
    anchor_refresh_interval,
    force=False,
):
    """Throttle only position anchoring — detection can still run every scan."""
    if not sprinkler_anchor_enabled(field_drift_compensation, use_sprinkler_model):
        return False
    if runtime.get("sprinkler_session") is None:
        return False
    if runtime.get("movement_active") and not force:
        return False
    if not force and time.time() - runtime.get("last_anchor_time", 0.0) < anchor_refresh_interval:
        return False
    return True


def apply_sprinkler_anchor_result(runtime, result, *, max_passive_distance, debug_log_fn=None):
    runtime["last_anchor_time"] = time.time()
    if not result:
        return False

    tx, ty, distance, label, confidence = result[:5]
    if distance > max_passive_distance:
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
    if debug_log_fn:
        debug_log_fn(
            f"anchor refreshed from sprinkler label={label} confidence={confidence:.2f} "
            f"pos=({old_x:.2f},{old_y:.2f})->({runtime['current_x']:.2f},{runtime['current_y']:.2f})",
            min_interval=1.0,
            key="anchor_refresh",
        )
    return True


def maybe_apply_sprinkler_anchor(
    runtime,
    result,
    *,
    field_drift_compensation,
    use_sprinkler_model,
    anchor_refresh_interval,
    max_passive_distance,
    force=False,
    debug_log_fn=None,
):
    if not sprinkler_anchor_should_run(
        runtime,
        field_drift_compensation=field_drift_compensation,
        use_sprinkler_model=use_sprinkler_model,
        anchor_refresh_interval=anchor_refresh_interval,
        force=force,
    ):
        return False
    return apply_sprinkler_anchor_result(
        runtime,
        result,
        max_passive_distance=max_passive_distance,
        debug_log_fn=debug_log_fn,
    )


def refresh_sprinkler_anchor(
    runtime,
    *,
    field_drift_compensation,
    use_sprinkler_model,
    anchor_refresh_interval,
    max_passive_distance,
    confidence_threshold,
    max_distance,
    target_label=None,
    force=False,
    frame=None,
    debug_log_fn=None,
):
    if not sprinkler_anchor_should_run(
        runtime,
        field_drift_compensation=field_drift_compensation,
        use_sprinkler_model=use_sprinkler_model,
        anchor_refresh_interval=anchor_refresh_interval,
        force=force,
    ):
        return False
    result = find_sprinkler(
        runtime,
        frame=frame,
        confidence_threshold=confidence_threshold,
        max_distance=max_distance,
        target_label=target_label,
    )
    return apply_sprinkler_anchor_result(
        runtime,
        result,
        max_passive_distance=max_passive_distance,
        debug_log_fn=debug_log_fn,
    )


def movement_keys(tx, ty, tcfbkey, afcfbkey, tclrkey, afclrkey):
    fb_key = tcfbkey if ty >= 0 else afcfbkey
    lr_key = afclrkey if tx >= 0 else tclrkey
    return fb_key, lr_key


def movement_segments(tx, ty, tcfbkey, afcfbkey, tclrkey, afclrkey):
    diagonal_component = min(abs(tx), abs(ty))
    diagonal_distance = math.sqrt(2) * diagonal_component
    axial_distance = abs(abs(tx) - abs(ty))
    fb_key, lr_key = movement_keys(tx, ty, tcfbkey, afcfbkey, tclrkey, afclrkey)

    segments = []
    if diagonal_distance >= 0.01:
        segments.append(("diagonal", [fb_key, lr_key], diagonal_distance))

    if axial_distance >= 0.01:
        if abs(ty) >= abs(tx):
            segments.append(("axial", [fb_key], axial_distance))
        else:
            segments.append(("axial", [lr_key], axial_distance))

    return segments


def tile_walk(keyboard, key, tiles):
    if tiles <= 0:
        return False

    keyboard.keyDown(key, False)
    keyboard.tileWait(tiles)
    keyboard.keyUp(key, False)
    return True


def tile_multi_walk(keyboard, keys, tiles):
    if tiles <= 0:
        return False

    for key in keys:
        keyboard.keyDown(key, False)
    keyboard.tileWait(tiles)
    for key in reversed(keys):
        keyboard.keyUp(key, False)
    return True


def interruptible_tile_walk(keyboard, keys, tiles, should_stop=None, chunk_tiles=0.1):
    """Hold movement keys and walk in small chunks so a stop predicate can abort early.

    Returns (tiles_walked, interrupted).
    """
    if tiles <= 0:
        return 0.0, False

    if isinstance(keys, str):
        key_list = [keys]
    else:
        key_list = [key for key in keys if key]
    if not key_list:
        return 0.0, False

    chunk = max(0.04, float(chunk_tiles))
    walked = 0.0
    interrupted = False
    try:
        for key in key_list:
            keyboard.keyDown(key, False)
        while walked < tiles - 1e-9:
            if should_stop is not None and should_stop():
                interrupted = True
                break
            step = min(chunk, tiles - walked)
            keyboard.tileWait(step)
            walked += step
    finally:
        for key in reversed(key_list):
            keyboard.keyUp(key, False)
    return walked, interrupted


def interruptible_movement(
    keyboard,
    tx,
    ty,
    tcfbkey,
    afcfbkey,
    tclrkey,
    afclrkey,
    should_stop=None,
    chunk_tiles=0.1,
):
    """Walk a relative (tx, ty) move in interruptible chunks.

    Returns (moved_x, moved_y, interrupted).
    """
    magnitude = math.hypot(tx, ty)
    if magnitude <= 0.001:
        return 0.0, 0.0, False

    moved_x = 0.0
    moved_y = 0.0
    for segment_type, keys, distance in movement_segments(tx, ty, tcfbkey, afcfbkey, tclrkey, afclrkey):
        if should_stop is not None and should_stop():
            return moved_x, moved_y, True
        if distance <= 0:
            continue

        if segment_type == "diagonal":
            component = min(abs(tx), abs(ty))
            seg_tx = math.copysign(component, tx) if component else 0.0
            seg_ty = math.copysign(component, ty) if component else 0.0
        elif abs(ty) >= abs(tx):
            seg_tx = 0.0
            seg_ty = math.copysign(distance, ty)
        else:
            seg_tx = math.copysign(distance, tx)
            seg_ty = 0.0

        walked, interrupted = interruptible_tile_walk(
            keyboard,
            keys,
            distance,
            should_stop=should_stop,
            chunk_tiles=chunk_tiles,
        )
        if distance > 1e-9:
            frac = walked / distance
            moved_x += seg_tx * frac
            moved_y += seg_ty * frac
        if interrupted:
            return moved_x, moved_y, True

    return moved_x, moved_y, False


def same_token_candidate(a, b, switch_distance):
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
    return math.hypot(float(ax) - float(bx), float(ay) - float(by)) <= switch_distance


def latest_target(runtime):
    scan_lock = runtime.get("scan_lock")
    if scan_lock is None:
        target = runtime.get("latest_target")
    else:
        with scan_lock:
            target = runtime.get("latest_target")
    return dict(target) if isinstance(target, dict) else target


def locked_target(runtime):
    lock = runtime.get("locked_target")
    return dict(lock) if isinstance(lock, dict) else None


def set_locked_target(runtime, target):
    if isinstance(target, dict):
        target = dict(target)
    scan_lock = runtime.get("scan_lock")
    if scan_lock is None:
        runtime["locked_target"] = target
    else:
        with scan_lock:
            runtime["locked_target"] = target


def clear_locked_target(runtime):
    set_locked_target(runtime, None)


def scanner_loop(runtime, scan_fn, interval, debug_log_fn=None, on_error=None):
    stop_event = runtime.get("scanner_stop_event")
    while stop_event is not None and not stop_event.is_set():
        scan_started = time.time()
        try:
            if not runtime.get("ready"):
                return
            scan_fn(runtime)
        except Exception as exc:
            runtime["ready"] = False
            runtime["error"] = str(exc)
            if on_error:
                on_error(exc)
            if debug_log_fn:
                debug_log_fn(f"scanner error: {exc}", min_interval=1.0, key="scanner_error")
            return
        remaining = interval - (time.time() - scan_started)
        time.sleep(max(remaining, 0.01))


def ensure_scanner_thread(runtime, scan_fn, interval, debug_log_fn=None, on_error=None):
    thread = runtime.get("scanner_thread")
    if thread is not None and thread.is_alive():
        return

    stop_event = runtime.get("scanner_stop_event")
    if stop_event is None or stop_event.is_set():
        stop_event = threading.Event()
        runtime["scanner_stop_event"] = stop_event

    thread = threading.Thread(
        target=scanner_loop,
        args=(runtime, scan_fn, interval),
        kwargs={"debug_log_fn": debug_log_fn, "on_error": on_error},
        daemon=True,
    )
    runtime["scanner_thread"] = thread
    thread.start()
    if debug_log_fn:
        debug_log_fn("continuous token scanner started", min_interval=1.0, key="scanner_started")


def stop_scanner_thread(runtime=None):
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


def sprinkler_scanner_loop(
    runtime,
    interval,
    find_kwargs,
    anchor_kwargs,
    debug_log_fn=None,
    apply_fn=None,
):
    """Independent sprinkler loop reading frames from the capture mailbox."""
    stop_event = runtime.get("sprinkler_scanner_stop_event")
    while stop_event is not None and not stop_event.is_set():
        scan_started = time.time()
        try:
            if not runtime.get("ready"):
                return
            if not sprinkler_detect_should_run(runtime):
                time.sleep(max(interval, 0.05))
                continue

            after_id = int(runtime.get("sprinkler_last_frame_id", 0))
            frame, frame_id, _ = wait_for_latest_frame(
                runtime,
                after_id=after_id,
                timeout=max(interval, 0.02),
                copy=True,
            )
            if frame is None:
                time.sleep(0.01)
                continue
            runtime["sprinkler_last_frame_id"] = frame_id

            result = find_sprinkler(runtime, frame=frame, **find_kwargs)
            if apply_fn is not None:
                apply_fn(runtime, result)
            else:
                maybe_apply_sprinkler_anchor(runtime, result, **anchor_kwargs)
        except Exception as exc:
            if debug_log_fn:
                debug_log_fn(f"sprinkler scanner error: {exc}", min_interval=1.0, key="sprinkler_scanner_error")
            time.sleep(max(interval, 0.05))
            continue

        remaining = interval - (time.time() - scan_started)
        time.sleep(max(remaining, 0.0))


def ensure_sprinkler_scanner_thread(
    runtime,
    interval,
    find_kwargs,
    anchor_kwargs,
    debug_log_fn=None,
    apply_fn=None,
):
    thread = runtime.get("sprinkler_scanner_thread")
    if thread is not None and thread.is_alive():
        return
    if runtime.get("sprinkler_session") is None:
        return

    stop_event = runtime.get("sprinkler_scanner_stop_event")
    if stop_event is None or stop_event.is_set():
        stop_event = threading.Event()
        runtime["sprinkler_scanner_stop_event"] = stop_event

    thread = threading.Thread(
        target=sprinkler_scanner_loop,
        args=(runtime, interval, find_kwargs, anchor_kwargs),
        kwargs={"debug_log_fn": debug_log_fn, "apply_fn": apply_fn},
        daemon=True,
    )
    runtime["sprinkler_scanner_thread"] = thread
    thread.start()
    if debug_log_fn:
        debug_log_fn("continuous sprinkler scanner started", min_interval=1.0, key="sprinkler_scanner_started")


def stop_sprinkler_scanner_thread(runtime=None):
    if not isinstance(runtime, dict):
        return

    stop_event = runtime.get("sprinkler_scanner_stop_event")
    if stop_event is not None:
        stop_event.set()

    thread = runtime.get("sprinkler_scanner_thread")
    if thread is not None and thread.is_alive() and thread is not threading.current_thread():
        try:
            thread.join(timeout=1)
        except Exception:
            pass
    runtime["sprinkler_scanner_thread"] = None


def stop_all_scanner_threads(runtime=None):
    stop_scanner_thread(runtime)
    stop_sprinkler_scanner_thread(runtime)
    stop_capture_thread(runtime)


def require_vision_deps():
    if cv2 is None or np is None:
        raise RuntimeError(
            "Must install opencv-python and numpy before using AI Gathering, please run install dependencies before continuing."
        )
    return cv2, np


def require_coreml_or_raise():
    if ct is None:
        raise RuntimeError(
            "coremltools is required for CoreML AI gathering. Install coremltools, then restart the macro."
        )
    if Image is None:
        raise RuntimeError("Pillow is required for CoreML AI Gathering, please run install dependencies before continuing.")
    return ct


# --- Helpers shared by the AI gather patterns (BloomsAI, Fuzzy AI Gather) ---


def common_pattern_settings(
    pattern_globals,
    sprinkler_confidence_threshold,
    max_sprinkler_distance,
    debug_mode,
    record_video,
    record_video_fps,
):
    """Read the settings both patterns share from their `pattern_*` globals.

    The arguments are the pattern's built-in defaults. Returns, in order:
    sprinkler confidence, max sprinkler distance, target sprinkler label,
    field drift compensation, field dimensions, sprinkler-model drift compensation,
    capture backend, debug mode, record video, record video fps.
    """
    get = pattern_globals.get
    return (
        coerce_float(get("pattern_sprinkler_confidence_threshold"), sprinkler_confidence_threshold),
        coerce_float(get("pattern_max_sprinkler_distance"), max_sprinkler_distance),
        coerce_text(get("pattern_target_sprinkler_label"), "") or None,
        coerce_bool(get("pattern_field_drift_compensation"), False),
        get("pattern_field_dimensions"),
        coerce_bool(get("pattern_use_sprinkler_model_for_drift_compensation"), False),
        coerce_text(get("pattern_capture_backend"), "auto").lower(),
        coerce_bool(get("pattern_debug_mode"), debug_mode),
        coerce_bool(get("pattern_record_video"), record_video),
        coerce_float(get("pattern_record_video_fps"), record_video_fps),
    )


def parse_size_and_width(size, sizeword, width):
    """Turn the field's size/width pattern variables into a float size and int width."""
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
    return size, width


def shutdown_runtime(runtime, debug_log_fn):
    stop_all_scanner_threads(runtime)
    release_video_writer(runtime, debug_log_fn=debug_log_fn)


def start_runtime(runtime, initialise_fn, debug_log_fn, ready_message_fn):
    """Fill `runtime` from initialise_fn; on failure leave it not ready with the error text."""
    try:
        runtime.clear()
        runtime.update(initialise_fn())
        runtime["ready"] = True
        runtime["error"] = ""
        debug_log_fn(ready_message_fn())
    except Exception as exc:
        runtime["ready"] = False
        runtime["error"] = str(exc)
        debug_log_fn(f"initialisation failed: {exc}")


def start_scanners(runtime, scan_fn, scan_interval, sprinkler_kwargs, anchor_kwargs, debug_log_fn, sprinkler_apply_fn=None):
    """Start the capture, token and sprinkler threads, running one scan first if none has happened."""
    ensure_capture_thread(runtime, interval=0.016, debug_log_fn=debug_log_fn)
    wait_for_capture_ready(runtime, timeout=1.0)
    if not runtime.get("latest_scan_time"):
        scan_fn(runtime)
    ensure_scanner_thread(
        runtime,
        scan_fn,
        scan_interval,
        debug_log_fn=debug_log_fn,
        on_error=lambda _exc: release_video_writer(runtime, debug_log_fn=debug_log_fn),
    )
    ensure_sprinkler_scanner_thread(
        runtime,
        scan_interval,
        sprinkler_kwargs,
        anchor_kwargs,
        debug_log_fn=debug_log_fn,
        apply_fn=sprinkler_apply_fn,
    )


def next_scan_frame(runtime, scan_interval):
    """Newest captured frame, or a direct grab when the capture thread has nothing new."""
    after_id = int(runtime.get("token_last_frame_id", 0))
    frame, frame_id, _ = wait_for_latest_frame(
        runtime,
        after_id=after_id,
        timeout=max(scan_interval, 0.02),
        copy=True,
    )
    if frame is None:
        return grab_frame(runtime)
    runtime["token_last_frame_id"] = frame_id
    return frame


def best_target_with_anchor_retry(runtime, detections, find_best_fn, anchor_kwargs):
    """Pick a target; if every candidate was outside the hard leash, re-anchor on the sprinkler and pick again."""
    target = find_best_fn(runtime, detections)
    if (
        target is None
        and not runtime.get("movement_active")
        and any(item.get("reason") == "hard_leash" for item in runtime.get("last_rejected_tokens", []))
        and refresh_sprinkler_anchor(runtime, force=True, **anchor_kwargs)
    ):
        target = find_best_fn(runtime, detections)
    return target


def record_scan_timing(
    runtime,
    debug_log_fn,
    screenshot_elapsed,
    preprocess_elapsed,
    inference_elapsed,
    postprocess_elapsed,
    scoring_elapsed,
    total_elapsed,
):
    """Store per-stage scan timings (seconds in, milliseconds stored) and update the detection FPS."""
    runtime["last_timing_ms"] = {
        "screenshot": screenshot_elapsed * 1000.0,
        "preprocess": preprocess_elapsed * 1000.0,
        "inference": inference_elapsed * 1000.0,
        "postprocess": postprocess_elapsed * 1000.0,
        "scoring": scoring_elapsed * 1000.0,
        "total": total_elapsed * 1000.0,
    }
    debug_log_fn(
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
    update_detection_fps(runtime, total_elapsed)


def scan_lock_for(runtime):
    """The runtime's scan lock, created on first use."""
    scan_lock = runtime.get("scan_lock")
    if scan_lock is None:
        scan_lock = threading.Lock()
        runtime["scan_lock"] = scan_lock
    return scan_lock


def leash_metrics(width, size, field_drift_compensation, field_dimensions, hard_margin):
    """Leash limits and scoring penalties shared by both patterns; each pattern adds its own keys."""
    configured_leash = 4.0 + (0.45 * max(width - 1, 0)) + (0.35 * size)
    field_radius = field_safe_radius(field_dimensions) if field_drift_compensation else None
    max_leash = min(configured_leash, field_radius) if field_radius is not None else configured_leash
    hard_leash = min(configured_leash + hard_margin, field_radius) if field_radius is not None else configured_leash + hard_margin
    return {
        "max_leash": max_leash,
        "hard_leash": hard_leash,
        "field_bounded": field_radius is not None,
        "soft_leash": max_leash * 0.625,
        "proximity_exp": 1.25,
        "leash_edge_penalty": 0.45,
        "outside_leash_penalty": 0.35,
    }


def walk_tracked(runtime, keyboard, tx, ty, tcfbkey, afcfbkey, tclrkey, afclrkey):
    """Walk the (tx, ty) tile offset and add it to the tracked position. Returns whether any key was walked."""
    moved = False
    runtime["movement_active"] = True
    try:
        for segment_type, keys, distance in movement_segments(tx, ty, tcfbkey, afcfbkey, tclrkey, afclrkey):
            if segment_type == "diagonal":
                tile_multi_walk(keyboard, keys, distance)
            else:
                tile_walk(keyboard, keys[0], distance)
            moved = True
        if moved:
            runtime["current_x"] += tx
            runtime["current_y"] += ty
            runtime["movement_count"] += 1
    finally:
        runtime["movement_active"] = False
    return moved


def move_if_far_enough(tx, ty, min_distance, move_fn):
    if math.hypot(tx, ty) <= min_distance:
        return False
    return move_fn(tx, ty)


def prepare_recording(runtime, frame, filename_prefix, record_video, record_video_fps, debug_log_fn):
    """Make sure a video writer exists for the debug recording. Returns False when not recording."""
    if runtime.get("video_writer") is None:
        mailbox_frame, _, _ = get_latest_frame(runtime, copy=True)
        frame = mailbox_frame if mailbox_frame is not None else grab_frame(runtime)

    writer = ensure_video_writer(
        runtime,
        frame,
        filename_prefix=filename_prefix,
        record_video=record_video,
        record_video_fps=record_video_fps,
        debug_log_fn=debug_log_fn,
    )
    return writer is not None


def recording_overlay_base(runtime, target, target_sprinkler_label, field_drift_compensation, use_sprinkler_model):
    """Overlay fields both patterns draw; each pattern adds its own keys and `updated_at`."""
    return {
        "target": dict(target) if isinstance(target, dict) else None,
        "current_x": runtime.get("current_x", 0.0),
        "current_y": runtime.get("current_y", 0.0),
        "movement_count": runtime.get("movement_count", 0),
        "detection_fps": runtime.get("detection_fps"),
        "last_detection_ms": runtime.get("last_detection_ms"),
        "last_timing_ms": dict(runtime.get("last_timing_ms", {})),
        "candidate_count": runtime.get("last_candidate_count", 0),
        "sprinkler": dict(runtime.get("last_sprinkler_detection", {})),
        "anchor": dict(runtime.get("last_anchor", {})),
        "sprinkler_status": runtime.get("last_sprinkler_status", ""),
        "target_sprinkler_label": target_sprinkler_label or "",
        "field_drift_compensation": field_drift_compensation,
        "use_sprinkler_model_for_drift_compensation": use_sprinkler_model,
    }


def draw_detection_boxes(annotated, runtime, detections, target, labels, ignored_tokens):
    frame_h, frame_w = annotated.shape[:2]
    target_box = target.get("box") if isinstance(target, dict) else None
    for box, class_id, confidence in detections:
        token_name = labels.get(class_id, f"class {class_id}")
        x1, y1, x2, y2 = box
        left_f, top_f = model_point_to_capture(runtime, x1, y1)
        right_f, bottom_f = model_point_to_capture(runtime, x2, y2)
        left = max(0, min(frame_w - 1, int(round(left_f))))
        top = max(0, min(frame_h - 1, int(round(top_f))))
        right = max(0, min(frame_w - 1, int(round(right_f))))
        bottom = max(0, min(frame_h - 1, int(round(bottom_f))))
        is_target = target_box == box
        if token_name in ignored_tokens:
            color = (120, 120, 120)
        elif is_target:
            color = (0, 255, 255)
        else:
            color = (80, 220, 80)
        cv2.rectangle(annotated, (left, top), (right, bottom), color, 2 if is_target else 1)
        draw_label(annotated, f"{token_name} {confidence:.2f}", left, top - 4, color)


def draw_sprinkler_box(annotated, sprinkler):
    sprinkler_box = sprinkler.get("box")
    if not sprinkler_box:
        return
    frame_h, frame_w = annotated.shape[:2]
    x1, y1, x2, y2 = sprinkler_box
    left = max(0, min(frame_w - 1, int(round(x1))))
    top = max(0, min(frame_h - 1, int(round(y1))))
    right = max(0, min(frame_w - 1, int(round(x2))))
    bottom = max(0, min(frame_h - 1, int(round(y2))))
    cv2.rectangle(annotated, (left, top), (right, bottom), (255, 180, 0), 3)
    match_text = "match" if sprinkler.get("target_match") else "seen"
    draw_label(
        annotated,
        f"sprinkler {match_text} {sprinkler.get('label', '?')} {sprinkler.get('confidence', 0.0):.2f} d={sprinkler.get('distance', 0.0):.2f}",
        left,
        top - 4,
        (255, 180, 0),
    )


def base_status_lines(overlay, headline):
    """The headline plus the target, sprinkler and anchor lines; patterns append their own after."""
    target = overlay.get("target")
    status_lines = [
        headline,
        f"target={target['name']} score={target['score']:.2f} move=({target['tx']:.2f},{target['ty']:.2f})" if target else "target=None",
        f"sprinkler_status={overlay.get('sprinkler_status', '')} target={overlay.get('target_sprinkler_label', '') or 'any'} drift={overlay.get('field_drift_compensation')} model={overlay.get('use_sprinkler_model_for_drift_compensation')}",
    ]
    anchor = overlay.get("anchor") or {}
    if anchor:
        age = max(0.0, time.time() - float(anchor.get("time", time.time())))
        status_lines.append(
            f"anchor=({anchor.get('x', 0.0):.2f},{anchor.get('y', 0.0):.2f}) sprinkler=({anchor.get('sprinkler_tx', 0.0):.2f},{anchor.get('sprinkler_ty', 0.0):.2f}) age={age:.1f}s"
        )
    return status_lines


def draw_status_and_timing(annotated, status_lines, overlay):
    """Draw the status lines top-left and the detection FPS and stage timings top-right."""
    frame_w = annotated.shape[1]
    for index, line in enumerate(status_lines):
        draw_label(annotated, line, 10, 24 + (index * 24), (255, 255, 255))

    detection_fps = overlay.get("detection_fps")
    detection_ms = overlay.get("last_detection_ms")
    fps_text = "detect FPS: --" if detection_fps is None else f"detect FPS: {detection_fps:.1f}"
    if detection_ms is not None:
        fps_text += f" ({detection_ms:.0f}ms)"
    (text_w, _text_h), _baseline = cv2.getTextSize(fps_text, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
    draw_label(annotated, fps_text, max(10, frame_w - text_w - 18), 24, (255, 255, 255))
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
        draw_label(annotated, timing_text, max(10, frame_w - timing_w - 18), 48, (255, 255, 255))
