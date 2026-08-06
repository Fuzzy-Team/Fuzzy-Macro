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
- token_detection_standard.mlmodelc or token_detection_standard.onnx
- sprinkler_detection_standard.mlmodelc or sprinkler_detection_standard.onnx

- Version 2.3
"""

import math
import threading
import time

from modules.misc import ai_gather_common as agc

cv2 = agc.cv2
np = agc.np
Image = agc.Image

INPUT_WIDTH = agc.INPUT_WIDTH
INPUT_HEIGHT = agc.INPUT_HEIGHT
MODEL_DIR = agc.MODEL_DIR
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
IGNORED_TOKENS = set()
_DEBUG_LOG_TIMES = {}

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

LABELS_TOKENS_LIGHT = {
    0: "Baby Love", 1: "Bear Morph", 2: "Bomb", 3: "Boost",
    4: "Festive Gift Token", 5: "Focus", 6: "Summon Frog Token",
    7: "Fuzz Bombs Token", 8: "Haste", 9: "Honey Token",
    10: "Inflate Balloons", 11: "Inspire Token", 12: "Loot",
    13: "Mark", 14: "Melody", 15: "Party Balloons",
    16: "Tabby Love", 17: "Token Link",
}

LABELS_TOKENS_MINI = {
    0: "Balloon", 1: "Bear Morph", 2: "Bomb", 3: "Boost",
    4: "Summon Frog Token", 5: "Haste", 6: "Inspire Token",
    7: "Long Buff", 8: "Loot", 9: "Mark", 10: "Token Link",
}

LABELS_LOOT_LIGHT = {
    0: "Beans", 1: "Berry", 2: "Buffs", 3: "Consumables",
    4: "Eggs", 5: "Fruits", 6: "Passes", 7: "Rare Items",
    8: "Tickets", 9: "Token Link", 10: "Waxes",
}

LABELS_LOOT_MINI = {
    0: "Token Link", 1: "Loot",
}

TOKEN_MODEL_OPTIONS = {
    "standard": ("Standard", None, LABELS_TOKENS, INPUT_WIDTH, INPUT_HEIGHT),
    "light": ("Light", "token_detection_small.mlmodelc", LABELS_TOKENS_LIGHT, 768, 416),
    "mini": ("Mini", "token_detection_mini.mlmodelc", LABELS_TOKENS_MINI, 768, 416),
}


CONFIDENCE_THRESHOLD = agc.coerce_float(globals().get("pattern_confidence_threshold"), CONFIDENCE_THRESHOLD)
SPRINKLER_CONFIDENCE_THRESHOLD = agc.coerce_float(
    globals().get("pattern_sprinkler_confidence_threshold"),
    SPRINKLER_CONFIDENCE_THRESHOLD,
)
MIN_TOKEN_DISTANCE = agc.coerce_float(globals().get("pattern_min_token_distance"), MIN_TOKEN_DISTANCE)
IDLE_RETURN_INTERVAL = agc.coerce_float(globals().get("pattern_idle_return_interval"), IDLE_RETURN_INTERVAL)
NO_TARGET_SWEEP_INTERVAL = agc.coerce_float(
    globals().get("pattern_no_target_sweep_interval"),
    NO_TARGET_SWEEP_INTERVAL,
)
NO_TOKEN_RECALIBRATION_TIMEOUT = agc.coerce_float(
    globals().get("pattern_no_token_recalibration_timeout"),
    NO_TOKEN_RECALIBRATION_TIMEOUT,
)
MOVEMENTS_BEFORE_RECALIBRATION = agc.coerce_int(
    globals().get("pattern_movements_before_recalibration"),
    MOVEMENTS_BEFORE_RECALIBRATION,
)
SPRINKLER_ARRIVAL_THRESHOLD = agc.coerce_float(
    globals().get("pattern_sprinkler_arrival_threshold"),
    SPRINKLER_ARRIVAL_THRESHOLD,
)
MAX_SPRINKLER_DISTANCE = agc.coerce_float(
    globals().get("pattern_max_sprinkler_distance"),
    MAX_SPRINKLER_DISTANCE,
)
SPRINKLER_RESCAN_ATTEMPTS = agc.coerce_int(
    globals().get("pattern_sprinkler_rescan_attempts"),
    SPRINKLER_RESCAN_ATTEMPTS,
)
SPRINKLER_RESCAN_DELAY = agc.coerce_float(
    globals().get("pattern_sprinkler_rescan_delay"),
    SPRINKLER_RESCAN_DELAY,
)
TARGET_SPRINKLER_LABEL = agc.coerce_text(
    globals().get("pattern_target_sprinkler_label"),
    "",
) or None
FIELD_DRIFT_COMPENSATION = agc.coerce_bool(globals().get("pattern_field_drift_compensation"), False)
USE_SPRINKLER_MODEL_FOR_DRIFT_COMPENSATION = agc.coerce_bool(
    globals().get("pattern_use_sprinkler_model_for_drift_compensation"),
    False,
)
CAPTURE_BACKEND = agc.coerce_text(globals().get("pattern_capture_backend"), "auto").lower()
DEBUG_MODE = agc.coerce_bool(globals().get("pattern_debug_mode"), DEBUG_MODE)
RECORD_VIDEO = agc.coerce_bool(globals().get("pattern_record_video"), RECORD_VIDEO)
RECORD_VIDEO_FPS = agc.coerce_float(globals().get("pattern_record_video_fps"), RECORD_VIDEO_FPS)
PREFERRED_TOKENS = agc.preferred_token_weights(globals().get("pattern_preferred_tokens"), PREFERRED_TOKENS)
PREFERRED_TOKEN_RANKS = {name: index for index, name in enumerate(PREFERRED_TOKENS.keys())}
IGNORED_TOKENS = agc.ignored_token_names(globals().get("pattern_ignored_tokens"), IGNORED_TOKENS)
SPROUT_IDLE_SQUARE = agc.coerce_bool(globals().get("pattern_sprout_idle_square"), False)


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


def _debug_log(message, min_interval=0.0, key=None):
    agc.debug_log("fuzzy_ai_gather", message, DEBUG_MODE, min_interval=min_interval, key=key, log_times=_DEBUG_LOG_TIMES)


def _runtime_state():
    return agc.get_runtime_state(self, "_fuzzy_ai_gather_state", "_FUZZY_AI_GATHER_STATE", globals())


def _sprinkler_kwargs():
    return {
        "confidence_threshold": SPRINKLER_CONFIDENCE_THRESHOLD,
        "max_distance": MAX_SPRINKLER_DISTANCE,
        "target_label": TARGET_SPRINKLER_LABEL,
    }


def _anchor_kwargs():
    return {
        "field_drift_compensation": FIELD_DRIFT_COMPENSATION,
        "use_sprinkler_model": USE_SPRINKLER_MODEL_FOR_DRIFT_COMPENSATION,
        "anchor_refresh_interval": ANCHOR_REFRESH_INTERVAL,
        "max_passive_distance": ANCHOR_MAX_PASSIVE_DISTANCE,
        "confidence_threshold": SPRINKLER_CONFIDENCE_THRESHOLD,
        "max_distance": MAX_SPRINKLER_DISTANCE,
        "target_label": TARGET_SPRINKLER_LABEL,
        "debug_log_fn": _debug_log,
    }


def onGatherEnd():
    runtime = _runtime_state()
    agc.stop_all_scanner_threads(runtime)
    agc.release_video_writer(runtime, debug_log_fn=_debug_log)


def _preprocess_token_frame(frame, runtime):
    if runtime.get("token_frame_is_crop"):
        cropped = frame
    else:
        left, top, width_px, height_px = runtime["token_crop"]
        cropped = frame[top:top + height_px, left:left + width_px]

    input_width = int(runtime.get("token_input_width", INPUT_WIDTH))
    input_height = int(runtime.get("token_input_height", INPUT_HEIGHT))
    if cropped.shape[1] != input_width or cropped.shape[0] != input_height:
        cropped = cv2.resize(cropped, (input_width, input_height), interpolation=cv2.INTER_LINEAR)

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


def _record_debug_frame(runtime, frame, detections, target):
    if runtime.get("video_writer") is None:
        frame = agc.grab_frame(runtime)

    writer = agc.ensure_video_writer(
        runtime,
        frame,
        filename_prefix="fuzzy_ai_gather",
        record_video=RECORD_VIDEO,
        record_video_fps=RECORD_VIDEO_FPS,
        debug_log_fn=_debug_log,
    )
    if writer is None:
        return

    runtime["latest_recording_overlay"] = {
        "detections": list(detections),
        "target": dict(target) if isinstance(target, dict) else None,
        "token_model_label": runtime.get("token_model_label", "Standard"),
        "token_model_kind": runtime.get("token_model_kind", "unknown"),
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
    annotated = agc.bgr_frame(frame)
    frame_h, frame_w = annotated.shape[:2]

    overlay = runtime.get("latest_recording_overlay", {})
    token_labels = runtime.get("token_labels", LABELS_TOKENS)
    detections = overlay.get("detections", [])
    target = overlay.get("target")
    target_box = target.get("box") if isinstance(target, dict) else None

    for box, class_id, confidence in detections:
        token_name = token_labels.get(class_id, f"class {class_id}")
        x1, y1, x2, y2 = box
        left_f, top_f = agc.model_point_to_capture(runtime, x1, y1)
        right_f, bottom_f = agc.model_point_to_capture(runtime, x2, y2)
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
        agc.draw_label(annotated, f"{token_name} {confidence:.2f}", left, top - 4, color)

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
        agc.draw_label(
            annotated,
            f"sprinkler {match_text} {sprinkler.get('label', '?')} {sprinkler.get('confidence', 0.0):.2f} d={sprinkler.get('distance', 0.0):.2f}",
            left,
            top - 4,
            (255, 180, 0),
        )

    anchor = overlay.get("anchor") or {}
    status_lines = [
        f"token_model={overlay.get('token_model_label', 'Standard')} ({overlay.get('token_model_kind', 'unknown')}) tokens={len(detections)} candidates={overlay.get('candidate_count', 0)} pos=({overlay.get('current_x', 0.0):.2f},{overlay.get('current_y', 0.0):.2f}) moves={overlay.get('movement_count', 0)}",
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
        agc.draw_label(annotated, line, 10, 24 + (index * 24), (255, 255, 255))

    detection_fps = overlay.get("detection_fps")
    detection_ms = overlay.get("last_detection_ms")
    fps_text = "detect FPS: --" if detection_fps is None else f"detect FPS: {detection_fps:.1f}"
    if detection_ms is not None:
        fps_text += f" ({detection_ms:.0f}ms)"
    (text_w, _text_h), _baseline = cv2.getTextSize(fps_text, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
    agc.draw_label(annotated, fps_text, max(10, frame_w - text_w - 18), 24, (255, 255, 255))
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
        agc.draw_label(annotated, timing_text, max(10, frame_w - timing_w - 18), 48, (255, 255, 255))

    return annotated


def _scan_tokens_once(runtime):
    detection_start = time.time()
    screenshot_start = time.time()
    frame = agc.grab_region_frame(runtime, "token_monitor", "token_bbox")
    if frame is None:
        frame = agc.grab_frame(runtime)
    screenshot_elapsed = time.time() - screenshot_start
    preprocess_start = time.time()
    image = _preprocess_token_frame(frame, runtime)
    preprocess_elapsed = time.time() - preprocess_start
    inference_start = time.time()
    output = agc.run_model(runtime, "token", image)
    inference_elapsed = time.time() - inference_start
    postprocess_start = time.time()
    detections = agc.decode_detections(runtime, "token", output, CONFIDENCE_THRESHOLD)
    input_width = float(runtime.get("token_input_width", INPUT_WIDTH))
    input_height = float(runtime.get("token_input_height", INPUT_HEIGHT))
    if input_width != INPUT_WIDTH or input_height != INPUT_HEIGHT:
        scale_x = INPUT_WIDTH / input_width
        scale_y = INPUT_HEIGHT / input_height
        detections = [
            ((box[0] * scale_x, box[1] * scale_y, box[2] * scale_x, box[3] * scale_y), class_id, confidence)
            for box, class_id, confidence in detections
        ]
    postprocess_elapsed = time.time() - postprocess_start
    scoring_start = time.time()
    target = _find_best_token(runtime, detections)
    if (
        target is None
        and not runtime.get("movement_active")
        and any(item.get("reason") in ("leash", "hard_leash") for item in runtime.get("last_rejected_tokens", []))
        and agc.refresh_sprinkler_anchor(runtime, force=True, **_anchor_kwargs())
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
    agc.update_detection_fps(runtime, total_elapsed)
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


def _get_importance(token_name):
    return PREFERRED_TOKENS.get(token_name, 1)


def _get_priority_rank(token_name):
    return PREFERRED_TOKEN_RANKS.get(token_name, len(PREFERRED_TOKEN_RANKS) + 100)


def _candidate_priority_rank(candidate):
    if not isinstance(candidate, dict):
        return len(PREFERRED_TOKEN_RANKS) + 100
    return int(candidate.get("priority_rank", _get_priority_rank(candidate.get("name", ""))))


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
        token_name = runtime.get("token_labels", LABELS_TOKENS).get(class_id)
        if not token_name:
            rejected.append({"class_id": class_id, "reason": "unknown", "confidence": confidence})
            continue
        if token_name in IGNORED_TOKENS:
            rejected.append({"name": token_name, "reason": "ignored", "confidence": confidence})
            continue

        x1, y1, x2, y2 = box
        center_x, center_y = agc.model_point_to_capture(runtime, (x1 + x2) / 2.0, (y1 + y2) / 2.0)
        tx, ty = agc.relative_distance(center_x, center_y, runtime["homography"])
        distance = math.hypot(tx, ty)

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
        runtime["latest_targets"] = []
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
    ranked_candidates = sorted(candidates, key=lambda item: (-item["priority_rank"], item["score"]), reverse=True)
    runtime["latest_targets"] = [dict(candidate) for candidate in ranked_candidates[:6]]
    return ranked_candidates[0]


def _execute_movement(tx, ty, update_token_time=True):
    magnitude = math.hypot(tx, ty)
    if magnitude <= 0.001:
        return False

    moved = False
    runtime = _runtime_state()
    runtime["movement_active"] = True
    try:
        for segment_type, keys, distance in agc.movement_segments(tx, ty, tcfbkey, afcfbkey, tclrkey, afclrkey):
            if segment_type == "diagonal":
                agc.tile_multi_walk(self.keyboard, keys, distance)
            else:
                agc.tile_walk(self.keyboard, keys[0], distance)
            moved = True
        if moved:
            runtime["current_x"] += tx
            runtime["current_y"] += ty
            runtime["movement_count"] += 1
            if update_token_time:
                runtime["last_token_time"] = time.time()
    finally:
        runtime["movement_active"] = False

    return moved


def _execute_movement_to_target(tx, ty):
    magnitude = math.hypot(tx, ty)
    if magnitude <= CONTINUOUS_MIN_REPLAN_DISTANCE:
        return False
    return _execute_movement(tx, ty)


def _execute_idle_movement(tx, ty):
    return _execute_movement(tx, ty, update_token_time=False)


def _execute_active_sweep(runtime):
    now = time.time()
    if now - runtime.get("last_no_target_sweep_time", 0.0) < NO_TARGET_SWEEP_INTERVAL:
        return False

    runtime["last_no_target_sweep_time"] = now
    metrics = _token_metrics()
    step = max(0.18, min(0.45, 0.18 + (0.05 * size)))
    sweep_index = int(runtime.get("sweep_index", 0))
    runtime["sweep_index"] = sweep_index + 1

    current_x = runtime["current_x"]
    current_y = runtime["current_y"]
    current_dist = math.hypot(current_x, current_y)
    if current_dist > metrics["soft_leash"]:
        scale = min(step / max(current_dist, 0.001), 1.0)
        tx = -current_x * scale
        ty = -current_y * scale
    else:
        sweep = (
            (step, 0.0),
            (0.0, step),
            (-step, 0.0),
            (0.0, -step),
            (step * 0.7, step * 0.7),
            (-step * 0.7, step * 0.7),
            (-step * 0.7, -step * 0.7),
            (step * 0.7, -step * 0.7),
        )
        tx, ty = sweep[sweep_index % len(sweep)]

    _debug_log(
        f"active sweep move=({tx:.2f},{ty:.2f}) pos=({current_x:.2f},{current_y:.2f})",
        min_interval=0.5,
        key="active_sweep",
    )
    return _execute_movement(tx, ty)


def _execute_sprinkler_idle_square(runtime):
    now = time.time()
    if now - runtime.get("last_no_target_sweep_time", 0.0) < NO_TARGET_SWEEP_INTERVAL:
        return False

    runtime["last_no_target_sweep_time"] = now
    current_x = runtime.get("current_x", 0.0)
    current_y = runtime.get("current_y", 0.0)
    current_dist = math.hypot(current_x, current_y)
    if current_dist > SPRINKLER_ARRIVAL_THRESHOLD:
        if now - runtime.get("last_idle_return_time", 0.0) >= IDLE_RETURN_INTERVAL:
            runtime["last_idle_return_time"] = now
            return _recalibrate(runtime)
        return False

    step = max(0.06, min(0.12, 0.08 + (0.01 * min(int(width), 4))))
    square_index = int(runtime.get("idle_square_index", 0))
    runtime["idle_square_index"] = square_index + 1
    square = (
        (step, 0.0),
        (0.0, step),
        (-step, 0.0),
        (0.0, -step),
    )
    tx, ty = square[square_index % len(square)]
    _debug_log(
        f"idle sprinkler square move=({tx:.2f},{ty:.2f}) pos=({current_x:.2f},{current_y:.2f})",
        min_interval=0.5,
        key="idle_sprinkler_square",
    )
    return _execute_idle_movement(tx, ty)


def _latest_target_lineup(runtime):
    scan_lock = runtime.get("scan_lock")
    if scan_lock is None:
        lineup = runtime.get("latest_targets", [])
    else:
        with scan_lock:
            lineup = runtime.get("latest_targets", [])
    if not isinstance(lineup, list):
        return []
    return [dict(target) for target in lineup if isinstance(target, dict)]


def _pop_lineup_target(runtime, excluded=None):
    scan_lock = runtime.get("scan_lock")
    if scan_lock is None:
        lineup = runtime.get("latest_targets", [])
        for index, target in enumerate(list(lineup)):
            if not isinstance(target, dict):
                continue
            if excluded and agc.same_token_candidate(excluded, target, TARGET_LOCK_SWITCH_DISTANCE):
                continue
            runtime["latest_targets"] = lineup[index + 1:]
            return dict(target)
        runtime["latest_targets"] = []
        return None

    with scan_lock:
        lineup = runtime.get("latest_targets", [])
        for index, target in enumerate(list(lineup)):
            if not isinstance(target, dict):
                continue
            if excluded and agc.same_token_candidate(excluded, target, TARGET_LOCK_SWITCH_DISTANCE):
                continue
            runtime["latest_targets"] = lineup[index + 1:]
            return dict(target)
        runtime["latest_targets"] = []
    return None


def _select_movement_target(runtime):
    latest_lineup = _latest_target_lineup(runtime)
    latest = latest_lineup[0] if latest_lineup else agc.latest_target(runtime)
    locked = agc.locked_target(runtime)
    now = time.time()

    if locked:
        remaining_x = float(locked.get("future_x", runtime["current_x"])) - runtime["current_x"]
        remaining_y = float(locked.get("future_y", runtime["current_y"])) - runtime["current_y"]
        remaining = math.hypot(remaining_x, remaining_y)
        if remaining <= TARGET_LOCK_REACHED_DISTANCE:
            agc.clear_locked_target(runtime)
            next_target = _pop_lineup_target(runtime, excluded=locked) or latest
            if next_target:
                next_target["locked_at"] = now
                next_target["last_seen"] = now
                agc.set_locked_target(runtime, next_target)
            return next_target

        last_seen = float(locked.get("last_seen", locked.get("locked_at", now)))
        if latest and agc.same_token_candidate(locked, latest, TARGET_LOCK_SWITCH_DISTANCE):
            locked.update(latest)
            locked["last_seen"] = now
            agc.set_locked_target(runtime, locked)
            return locked

        if latest and _candidate_priority_rank(latest) < _candidate_priority_rank(locked):
            latest["locked_at"] = now
            latest["last_seen"] = now
            agc.set_locked_target(runtime, latest)
            return latest

        if now - last_seen <= TARGET_LOCK_LOST_TIMEOUT:
            return locked

        if latest and latest.get("score", 0.0) >= locked.get("score", 0.0) * TARGET_LOCK_SWITCH_SCORE_MULTIPLIER:
            latest["locked_at"] = now
            latest["last_seen"] = now
            agc.set_locked_target(runtime, latest)
            return latest

        agc.clear_locked_target(runtime)
        next_target = _pop_lineup_target(runtime, excluded=locked) or latest
        if next_target:
            next_target["locked_at"] = now
            next_target["last_seen"] = now
            agc.set_locked_target(runtime, next_target)
        return next_target

    if latest:
        latest["locked_at"] = now
        latest["last_seen"] = now
        agc.set_locked_target(runtime, latest)
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
        agc.clear_locked_target(runtime)
        next_target = _pop_lineup_target(runtime, excluded=target)
        if not next_target:
            return False
        next_x = next_target.get("future_x")
        next_y = next_target.get("future_y")
        if next_x is None or next_y is None:
            return _execute_movement_to_target(next_target.get("tx", 0.0), next_target.get("ty", 0.0))
        remaining_x = float(next_x) - runtime["current_x"]
        remaining_y = float(next_y) - runtime["current_y"]
        if math.hypot(remaining_x, remaining_y) <= CONTINUOUS_MIN_REPLAN_DISTANCE:
            return False
        next_target["locked_at"] = time.time()
        next_target["last_seen"] = next_target["locked_at"]
        agc.set_locked_target(runtime, next_target)
        target = next_target

    _debug_log(
        f"moving toward planned target={target['name']} remaining=({remaining_x:.2f},{remaining_y:.2f}) score={target['score']:.2f}",
        min_interval=0.25,
        key="planned_move",
    )
    return _execute_movement_to_target(remaining_x, remaining_y)


def _find_sprinkler_with_retry(runtime):
    for attempt in range(SPRINKLER_RESCAN_ATTEMPTS):
        result = agc.find_sprinkler(runtime, **_sprinkler_kwargs())
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
        runtime["latest_targets"] = []
        runtime["locked_target"] = None
    else:
        with scan_lock:
            runtime["latest_target"] = None
            runtime["latest_targets"] = []
            runtime["locked_target"] = None


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
    _debug_log("running fallback sweep pattern", min_interval=1.0, key="fallback")
    travel = 0.12 * max(size, 0.75)
    for _ in range(max(1, min(int(width), 2))):
        self.keyboard.multiWalk([tcfbkey, tclrkey], travel)
        self.keyboard.multiWalk([afcfbkey, afclrkey], travel)
        self.keyboard.multiWalk([tcfbkey, afclrkey], travel)
        self.keyboard.multiWalk([afcfbkey, tclrkey], travel)


def _initialise_runtime():
    agc.require_vision_deps()

    requested_model = agc.coerce_text(globals().get("pattern_ai_gather_model"), "Standard").strip().lower()
    requested_label, requested_filename, requested_labels, requested_width, requested_height = TOKEN_MODEL_OPTIONS.get(
        requested_model, TOKEN_MODEL_OPTIONS["standard"]
    )
    requested_filename_override = agc.coerce_text(globals().get("pattern_ai_gather_model_file"), "")
    if requested_filename_override:
        requested_filename = requested_filename_override
        if requested_filename_override == "loot_detection_small.mlmodelc":
            requested_label = "Light Loot"
            requested_labels = LABELS_LOOT_LIGHT
        elif requested_filename_override == "loot_detection_mini.mlmodelc":
            requested_label = "Mini Loot"
            requested_labels = LABELS_LOOT_MINI
        elif requested_filename_override.startswith("loot_detection_"):
            requested_label = f"{requested_label} Loot"
            requested_labels = {0: "Loot"}
    standard_candidates = [
        (MODEL_DIR / "token_detection_standard.mlmodelc", "coreml", LABELS_TOKENS, "Standard", INPUT_WIDTH, INPUT_HEIGHT),
        (MODEL_DIR / "token_detection_standard.onnx", "opencv_onnx", LABELS_TOKENS, "Standard", INPUT_WIDTH, INPUT_HEIGHT),
    ]
    token_candidates = []
    if requested_filename is not None:
        token_candidates.append((MODEL_DIR / requested_filename, "coreml", requested_labels, requested_label, requested_width, requested_height))
    token_candidates.extend(standard_candidates)
    token_candidates = [candidate for candidate in token_candidates if candidate[0].exists()]
    download_result = {}
    if not token_candidates:
        missing_model_names = []
        if requested_filename is not None:
            missing_model_names.append(requested_filename)
        missing_model_names.extend(["token_detection_standard.mlmodelc", "token_detection_standard.onnx"])
        download_result = agc.check_missing_models("fuzzy_ai_gather", missing_model_names)
        token_candidates = []
        if requested_filename is not None:
            token_candidates.append((MODEL_DIR / requested_filename, "coreml", requested_labels, requested_label, requested_width, requested_height))
        token_candidates.extend(standard_candidates)
        token_candidates = [candidate for candidate in token_candidates if candidate[0].exists()]
    if not token_candidates:
        failures = download_result.get("failures", {})
        detail = f" Download attempt failed: {'; '.join(failures.values())}" if failures else ""
        raise FileNotFoundError(
            f"No usable token AI model was found after attempting to download it. "
            f"Checked selected {requested_label} model and Standard models in {MODEL_DIR}.{detail}"
        )
    token_path, token_model_kind, token_labels, token_model_label, token_input_width, token_input_height = token_candidates[0]
    if token_model_kind == "coreml":
        agc.require_coreml_or_raise()

    sprinkler_path, sprinkler_model_kind = agc.resolve_sprinkler_model(tag="fuzzy_ai_gather", download=False)

    capture = agc.build_capture(getattr(self, "robloxWindow", None), CAPTURE_BACKEND)
    token_crop_info = agc.token_crop_for_capture(capture)
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

    homography = agc.compute_homography(capture["width"], capture["height"])
    if homography is None:
        raise RuntimeError("Could not compute AI gather homography.")

    token_load_errors = []
    token_session = token_input = token_output = None
    for candidate_path, candidate_kind, candidate_labels, candidate_label, candidate_width, candidate_height in token_candidates:
        try:
            if candidate_kind == "opencv_onnx":
                token_session, token_input, token_output = agc.load_onnx_model(candidate_path)
            else:
                token_session, token_input, token_output = agc.load_coreml_model(candidate_path)
            if candidate_label != requested_label:
                print(
                    f"[fuzzy_ai_gather] {requested_label} model failed or was unavailable; falling back to Standard ({candidate_path.name})"
                )
            token_path = candidate_path
            token_model_kind = candidate_kind
            token_labels = candidate_labels
            token_model_label = candidate_label
            token_input_width = candidate_width
            token_input_height = candidate_height
            globals()["LABELS_TOKENS"] = dict(token_labels)
            break
        except Exception as exc:
            error_message = f"{candidate_label} ({candidate_path.name}): {exc}"
            token_load_errors.append(error_message)
            print(f"[fuzzy_ai_gather] token model load failed: {error_message}")
    else:
        raise RuntimeError("Could not load any token AI model: " + "; ".join(token_load_errors))

    if token_path.name == "token_detection_standard.onnx":
        agc.delete_model_path(MODEL_DIR / "token_detection_standard.mlmodelc", _debug_log)
    elif token_path.name == "token_detection_standard.mlmodelc":
        agc.delete_model_path(MODEL_DIR / "token_detection_standard.onnx", _debug_log)

    sprinkler_session, sprinkler_input, sprinkler_output = agc.load_sprinkler_session(
        sprinkler_path,
        sprinkler_model_kind,
        _debug_log,
    )

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
        "token_model_label": token_model_label,
        "token_model_path": str(token_path),
        "token_labels": dict(token_labels),
        "token_input_width": token_input_width,
        "token_input_height": token_input_height,
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
        "sweep_index": 0,
        "idle_square_index": 0,
        "initialised_at": time.time(),
        "video_writer": None,
        "video_path": "",
        "detection_fps": None,
        "last_detection_ms": None,
        "last_timing_ms": {},
        "latest_detections": [],
        "latest_target": None,
        "latest_targets": [],
        "locked_target": None,
        "latest_scan_time": 0.0,
        "last_anchor_time": 0.0,
        "last_anchor": {},
        "last_sprinkler_detection": {},
        "last_sprinkler_status": "",
        "movement_active": False,
        "scan_lock": threading.Lock(),
        "sprinkler_infer_lock": threading.Lock(),
        "scanner_stop_event": None,
        "scanner_thread": None,
        "annotate_recording_frame": _annotate_recording_frame,
    }


runtime = _runtime_state()
if not runtime.get("ready"):
    try:
        runtime.clear()
        runtime.update(_initialise_runtime())
        runtime["ready"] = True
        runtime["error"] = ""
        _debug_log(
            f"runtime ready token_model={runtime['token_model_label']} kind={runtime['token_model_kind']} input={runtime['token_input']} output={runtime['token_output']} confidence={CONFIDENCE_THRESHOLD} ignored={sorted(IGNORED_TOKENS)} record={RECORD_VIDEO}"
        )
    except Exception as exc:
        runtime["ready"] = False
        runtime["error"] = str(exc)
        _debug_log(f"initialisation failed: {exc}")


warmup_only = agc.coerce_bool(globals().get("pattern_ai_warmup_only"), False)

if not runtime.get("ready"):
    print(f"[fuzzy_ai_gather] {runtime.get('error', 'initialisation failed')}")
    if not warmup_only:
        _fallback_pattern()
elif warmup_only:
    _debug_log("warmup complete; movement skipped", min_interval=0.5, key="warmup")
else:
    try:
        if not runtime.get("latest_scan_time"):
            _scan_tokens_once(runtime)
        agc.ensure_scanner_thread(
            runtime,
            _scan_tokens_once,
            CONTINUOUS_SCAN_INTERVAL,
            debug_log_fn=_debug_log,
            on_error=lambda _exc: agc.release_video_writer(runtime, debug_log_fn=_debug_log),
        )
        agc.ensure_sprinkler_scanner_thread(
            runtime,
            CONTINUOUS_SCAN_INTERVAL,
            _sprinkler_kwargs(),
            _anchor_kwargs(),
            debug_log_fn=_debug_log,
        )
        agc.refresh_sprinkler_anchor(runtime, **_anchor_kwargs())

        if _should_recalibrate(runtime):
            _recalibrate(runtime)

        target = agc.locked_target(runtime) or agc.latest_target(runtime)
        if target:
            _debug_log(
                f"target={target['name']} confidence={target['confidence']:.2f} score={target['score']:.2f} planned=({target['future_x']:.2f},{target['future_y']:.2f})",
                min_interval=0.25,
                key="target",
            )
            if not _execute_planned_movement(runtime):
                _execute_active_sweep(runtime)
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
            elif SPROUT_IDLE_SQUARE and _execute_sprinkler_idle_square(runtime):
                pass
            elif not SPROUT_IDLE_SQUARE and _execute_active_sweep(runtime):
                pass
            elif now - runtime["last_idle_return_time"] >= IDLE_RETURN_INTERVAL:
                runtime["last_idle_return_time"] = now
                if _recalibrate(runtime):
                    runtime["last_token_time"] = time.time()
    except Exception as exc:
        runtime["ready"] = False
        runtime["error"] = str(exc)
        agc.release_video_writer(runtime, debug_log_fn=_debug_log)
        print(f"[fuzzy_ai_gather] runtime error: {exc}")
        _fallback_pattern()
