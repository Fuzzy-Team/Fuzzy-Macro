"""Shared helpers for BloomsAI and Fuzzy AI Gather patterns."""

from __future__ import annotations

import math
import shutil
import subprocess
import threading
import time
from pathlib import Path

try:
    import cv2
except Exception:
    cv2 = None

try:
    import numpy as np
except Exception:
    np = None

try:
    import coremltools as ct
except Exception:
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
            "bbox": (left, top, left + width_px, top + height_px),
            "width": width_px,
            "height": height_px,
        }

    raise RuntimeError(f"No supported capture backend found for '{backend}'. Install mss or Pillow.")


def mss_grab_to_array(session, monitor):
    shot = session.grab(monitor)
    return np.frombuffer(shot.raw, dtype=np.uint8).reshape((shot.height, shot.width, 4))


def grab_frame(runtime):
    if runtime["capture"]["backend"] == "mss":
        monitor = runtime["capture"]["monitor"]
        return mss_grab_to_array(runtime["capture"]["session"], monitor)

    image = ImageGrab.grab(bbox=runtime["capture"].get("bbox"))
    return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)


def grab_region_frame(runtime, monitor_key, bbox_key):
    monitor = runtime.get(monitor_key)
    if runtime["capture"]["backend"] == "mss" and monitor:
        return mss_grab_to_array(runtime["capture"]["session"], monitor)
    bbox = runtime.get(bbox_key)
    if bbox and ImageGrab is not None:
        image = ImageGrab.grab(bbox=bbox)
        return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
    return None


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
                    frame = mss_grab_to_array(session, capture["monitor"])
                elif capture.get("backend") == "pil" and ImageGrab is not None:
                    image = ImageGrab.grab(bbox=capture.get("bbox"))
                    frame = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
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
    if sprinkler_candidate.exists():
        sprinkler_model_kind = "coreml"
    else:
        sprinkler_candidate = model_dir / "sprinkler_detection_standard.onnx"
        if sprinkler_candidate.exists():
            sprinkler_model_kind = "opencv_onnx"
        elif download:
            check_missing_models(
                tag,
                ["sprinkler_detection_standard.mlmodelc", "sprinkler_detection_standard.onnx"],
            )
            sprinkler_candidate = model_dir / "sprinkler_detection_standard.mlmodelc"
            if sprinkler_candidate.exists():
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


def start_sprinkler_find(runtime, frame=None, **kwargs):
    holder = {"result": None, "error": None}

    def _worker():
        try:
            holder["result"] = find_sprinkler(runtime, frame=frame, **kwargs)
        except Exception as exc:
            holder["error"] = exc

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    return thread, holder


def finish_sprinkler_find(thread, holder):
    thread.join()
    if holder["error"] is not None:
        raise holder["error"]
    return holder["result"]


def sprinkler_anchor_enabled(field_drift_compensation, use_sprinkler_model):
    return bool(field_drift_compensation and use_sprinkler_model)


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
