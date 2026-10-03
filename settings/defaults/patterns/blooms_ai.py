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
- bloom_detection_standard.mlmodelc/.onnx, bloom_detection_light.mlmodelc/.onnx, or bloom_detection_mini.mlmodelc/.onnx
- sprinkler_detection_standard.mlmodelc or sprinkler_detection_standard.onnx

- Version 2.3
"""

import math
import threading
import time

from modules.misc import ai_gather_common as agc

cv2 = agc.cv2
np = agc.np
ct = agc.ct
Image = agc.Image

INPUT_WIDTH = agc.INPUT_WIDTH
INPUT_HEIGHT = agc.INPUT_HEIGHT
MODEL_DIR = agc.MODEL_DIR
SPRINKLER_CONFIDENCE_THRESHOLD = 0.6
PETAL_CONFIDENCE_THRESHOLD = 0.50
RUNTIME_VERSION = 42
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
PETAL_ORBIT_RADIUS = 3.0
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
IDLE_SQUARE_SIDE = 1.2
IDLE_SPRINKLER_NEAR = 0.85
IDLE_RETURN_STEP = 1.35
IDLE_WALK_CHUNK = 0.08
IDLE_PATROL_MAX_SIDES = 4
IDLE_SPRINKLER_MAX_AGE = 1.25
BLOOM_MODEL_VARIANTS = {
    "standard": (
        "Standard",
        "bloom_detection_standard.mlmodelc",
        "bloom_detection_standard.onnx",
        960,
        "var_1555",
    ),
    "light": (
        "Light",
        "bloom_detection_light.mlmodelc",
        "bloom_detection_light.onnx",
        768,
        "var_1444",
    ),
    "mini": (
        "Mini",
        "bloom_detection_mini.mlmodelc",
        "bloom_detection_mini.onnx",
        512,
        "var_1440",
    ),
}

# The Bloom-only model emits class 0.
LABELS_BLOOMS = {
    0: BLOOM_LABEL,
}

IGNORED_TOKENS = set()
_DEBUG_LOG_TIMES = {}


SPRINKLER_CONFIDENCE_THRESHOLD = agc.coerce_float(
    globals().get("pattern_sprinkler_confidence_threshold"),
    SPRINKLER_CONFIDENCE_THRESHOLD,
)
MIN_TOKEN_DISTANCE = agc.coerce_float(globals().get("pattern_min_token_distance"), MIN_TOKEN_DISTANCE)
MAX_SPRINKLER_DISTANCE = agc.coerce_float(
    globals().get("pattern_max_sprinkler_distance"),
    MAX_SPRINKLER_DISTANCE,
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
BLOOM_MODEL_SELECTION = agc.coerce_text(
    globals().get("pattern_blooms_ai_model"),
    "Standard",
).strip().lower()
if BLOOM_MODEL_SELECTION not in BLOOM_MODEL_VARIANTS:
    BLOOM_MODEL_SELECTION = "standard"
IGNORED_TOKENS = agc.ignored_token_names(globals().get("pattern_ignored_tokens"), IGNORED_TOKENS)
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


def _debug_log(message, min_interval=0.0, key=None):
    agc.debug_log("blooms_ai", message, DEBUG_MODE, min_interval=min_interval, key=key, log_times=_DEBUG_LOG_TIMES)


def _runtime_state():
    return agc.get_runtime_state(self, "_blooms_ai_state", "_BLOOMS_AI_STATE", globals())


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


def _record_debug_frame(runtime, frame, detections, target):
    if runtime.get("video_writer") is None:
        mailbox_frame, _, _ = agc.get_latest_frame(runtime, copy=True)
        frame = mailbox_frame if mailbox_frame is not None else agc.grab_frame(runtime)

    writer = agc.ensure_video_writer(
        runtime,
        frame,
        filename_prefix="blooms_ai",
        record_video=RECORD_VIDEO,
        record_video_fps=RECORD_VIDEO_FPS,
        debug_log_fn=_debug_log,
    )
    if writer is None:
        return

    bloom_detections = [
        detection
        for detection in detections
        if LABELS_BLOOMS.get(detection[1]) == BLOOM_LABEL
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
    annotated = agc.bgr_frame(frame)
    frame_h, frame_w = annotated.shape[:2]

    overlay = runtime.get("latest_recording_overlay", {})
    detections = overlay.get("detections", [])
    target = overlay.get("target")
    target_box = target.get("box") if isinstance(target, dict) else None

    for box, class_id, confidence in detections:
        token_name = LABELS_BLOOMS.get(class_id, f"class {class_id}")
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
        agc.draw_label(annotated, label, left, top - 4, color)

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
    petal_detection_ms = overlay.get("petal_detection_ms")
    if petal_detection_ms is not None:
        petal_timing_text = f"petal infer {petal_detection_ms:.0f}ms"
        (petal_w, _petal_h), _petal_baseline = cv2.getTextSize(petal_timing_text, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
        agc.draw_label(annotated, petal_timing_text, max(10, frame_w - petal_w - 18), 72, (255, 120, 40))

    return annotated


def _scan_tokens_once(runtime):
    movement_revision = int(runtime.get("movement_revision", 0))
    detection_start = time.time()
    screenshot_start = time.time()
    after_id = int(runtime.get("token_last_frame_id", 0))
    frame, frame_id, _ = agc.wait_for_latest_frame(
        runtime,
        after_id=after_id,
        timeout=max(CONTINUOUS_SCAN_INTERVAL, 0.02),
        copy=True,
    )
    if frame is None:
        frame = agc.grab_frame(runtime)
        frame_id = after_id
    else:
        runtime["token_last_frame_id"] = frame_id
    screenshot_elapsed = time.time() - screenshot_start
    preprocess_start = time.time()
    if runtime.get("combined_model_kind") == "opencv_onnx":
        image, transform = agc.preprocess_petal_onnx_image(
            frame,
            runtime["combined_input_width"],
            runtime["combined_input_height"],
        )
    else:
        image, transform = agc.preprocess_petal_image(
            frame,
            runtime["combined_input_width"],
            runtime["combined_input_height"],
        )
    preprocess_elapsed = time.time() - preprocess_start
    inference_start = time.time()
    output = agc.run_model(runtime, "combined", image)
    inference_elapsed = time.time() - inference_start
    postprocess_start = time.time()
    # Idle sprinkler patrol keeps walking while watching for blooms, so allow
    # bloom publishes during that movement so the square can abort instantly.
    idle_patrol = bool(runtime.get("idle_patrol_active"))
    scan_stale = (not idle_patrol) and (
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

    if scan_stale:
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


def _token_metrics():
    max_leash = 4.0 + (0.45 * max(width - 1, 0)) + (0.35 * size)
    max_bloom_distance = max(BLOOM_MAX_DISTANCE, max_leash + 1.0)
    return {
        "max_leash": max_leash,
        "hard_leash": max_leash + LEASH_HARD_MARGIN,
        "soft_leash": max_leash * 0.625,
        "max_consider": max_bloom_distance,
        "proximity_exp": 1.25,
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
        token_name = LABELS_BLOOMS.get(class_id)
        if not token_name:
            rejected.append({"class_id": class_id, "reason": "unknown", "confidence": confidence})
            continue
        if token_name != BLOOM_LABEL:
            rejected.append({"name": token_name, "reason": "not_bloom", "confidence": confidence})
            continue
        if confidence < BLOOM_MIN_CONFIDENCE:
            rejected.append({"name": token_name, "reason": "low_confidence", "confidence": confidence})
            continue

        x1, y1, x2, y2 = box
        center_x, center_y = agc.model_point_to_capture(runtime, (x1 + x2) / 2.0, (y1 + y2) / 2.0)
        tx, ty = agc.relative_distance(center_x, center_y, runtime["homography"])
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


def _execute_movement(tx, ty):
    magnitude = math.hypot(tx, ty)
    if magnitude <= 0.001:
        return False

    moved = False
    runtime = _runtime_state()
    runtime["movement_revision"] = int(runtime.get("movement_revision", 0)) + 1
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


def _idle_square_side():
    return max(0.7, min(2.0, IDLE_SQUARE_SIDE + (0.15 * max(size - 1.0, 0.0)) + (0.1 * max(width - 1, 0))))


def _idle_square_sides(side):
    """Relative axis-aligned sides. No inward correction — the loop itself keeps alignment."""
    return (
        (side, 0.0),
        (0.0, side),
        (-side, 0.0),
        (0.0, -side),
    )


def _bloom_seen_for_patrol(runtime):
    target = agc.latest_target(runtime)
    if isinstance(target, dict) and target.get("name") == BLOOM_LABEL:
        return True
    candidates = runtime.get("latest_bloom_candidates", [])
    if isinstance(candidates, list) and candidates:
        return True
    return False


def _latest_sprinkler_offset(runtime):
    """Return (tx, ty, distance) toward a recently seen sprinkler, or None."""
    detection = runtime.get("last_sprinkler_detection")
    if not isinstance(detection, dict) or not detection:
        return None
    age = time.time() - float(detection.get("time", 0.0))
    if age > IDLE_SPRINKLER_MAX_AGE:
        return None
    tx = float(detection.get("tx", 0.0))
    ty = float(detection.get("ty", 0.0))
    distance = float(detection.get("distance", math.hypot(tx, ty)))
    if distance <= 0.001:
        return None
    return tx, ty, distance


def _execute_interruptible_patrol_move(runtime, tx, ty):
    magnitude = math.hypot(tx, ty)
    if magnitude <= 0.001:
        return False, False

    runtime["movement_revision"] = int(runtime.get("movement_revision", 0)) + 1
    runtime["movement_active"] = True
    moved_x = 0.0
    moved_y = 0.0
    interrupted = False
    try:
        moved_x, moved_y, interrupted = agc.interruptible_movement(
            self.keyboard,
            tx,
            ty,
            tcfbkey,
            afcfbkey,
            tclrkey,
            afclrkey,
            should_stop=lambda: _bloom_seen_for_patrol(runtime),
            chunk_tiles=IDLE_WALK_CHUNK,
        )
        if abs(moved_x) > 1e-9 or abs(moved_y) > 1e-9:
            runtime["current_x"] += moved_x
            runtime["current_y"] += moved_y
            runtime["movement_count"] += 1
    finally:
        runtime["movement_active"] = False

    if abs(moved_x) > 1e-9 or abs(moved_y) > 1e-9:
        scan_lock = runtime.get("scan_lock")
        if scan_lock is None:
            scan_lock = threading.Lock()
            runtime["scan_lock"] = scan_lock
        with scan_lock:
            if interrupted:
                # Keep bloom detections so the next tick can chase immediately.
                runtime["movement_requires_fresh_scan"] = False
            else:
                runtime["latest_target"] = None
                runtime["latest_bloom_candidates"] = []
                runtime["latest_petal_detection_time"] = 0.0
                runtime["latest_scan_time"] = 0.0
                runtime["movement_requires_fresh_scan"] = True

    return (abs(moved_x) > 1e-9 or abs(moved_y) > 1e-9), interrupted


def _walk_toward_sprinkler_if_far(runtime, side):
    """If the sprinkler is visible/known and far away, walk toward it. Returns (handled, interrupted)."""
    sprinkler = _latest_sprinkler_offset(runtime)
    if sprinkler is not None:
        sx, sy, sdist = sprinkler
        if sdist > IDLE_SPRINKLER_NEAR:
            step = min(IDLE_RETURN_STEP, sdist)
            scale = step / sdist
            tx, ty = sx * scale, sy * scale
            _debug_log(
                f"patrol walking to sprinkler move=({tx:.2f},{ty:.2f}) distance={sdist:.2f}",
                min_interval=0.25,
                key="idle_return",
            )
            moved, interrupted = _execute_interruptible_patrol_move(runtime, tx, ty)
            return True, interrupted or moved

    current_x = float(runtime.get("current_x", 0.0))
    current_y = float(runtime.get("current_y", 0.0))
    home_dist = math.hypot(current_x, current_y)
    if home_dist > max(IDLE_SPRINKLER_NEAR, side * 0.75):
        step = min(IDLE_RETURN_STEP, home_dist)
        scale = step / home_dist
        tx, ty = -current_x * scale, -current_y * scale
        _debug_log(
            f"patrol returning toward sprinkler origin move=({tx:.2f},{ty:.2f}) distance={home_dist:.2f}",
            min_interval=0.25,
            key="idle_return",
        )
        moved, interrupted = _execute_interruptible_patrol_move(runtime, tx, ty)
        return True, interrupted or moved

    return False, False


def _execute_sprinkler_patrol(runtime):
    """Walk to the sprinkler when far, then box-walk around it until a bloom appears."""
    if runtime.get("movement_requires_fresh_scan") and not runtime.get("idle_patrol_active"):
        return False

    side = _idle_square_side()
    sides = _idle_square_sides(side)
    runtime["idle_patrol_active"] = True
    moved_any = False
    try:
        if _bloom_seen_for_patrol(runtime):
            return False

        handled, result = _walk_toward_sprinkler_if_far(runtime, side)
        if handled:
            return result

        square_index = int(runtime.get("idle_square_index", 0)) % len(sides)
        for _ in range(IDLE_PATROL_MAX_SIDES):
            if _bloom_seen_for_patrol(runtime):
                _debug_log("sprinkler patrol interrupted by bloom", min_interval=0.1, key="idle_interrupt")
                return True

            # If we drift away mid-lap, walk back toward the sprinkler before continuing.
            handled, result = _walk_toward_sprinkler_if_far(runtime, side)
            if handled:
                moved_any = moved_any or result
                if _bloom_seen_for_patrol(runtime):
                    return True
                continue

            tx, ty = sides[square_index]
            _debug_log(
                f"sprinkler patrol square side={square_index + 1}/{len(sides)} "
                f"move=({tx:.2f},{ty:.2f}) side={side:.2f}",
                min_interval=0.25,
                key="idle_square",
            )
            moved, interrupted = _execute_interruptible_patrol_move(runtime, tx, ty)
            moved_any = moved_any or moved
            if interrupted:
                _debug_log("sprinkler patrol interrupted by bloom", min_interval=0.1, key="idle_interrupt")
                runtime["idle_square_index"] = square_index
                return True

            square_index = (square_index + 1) % len(sides)
            runtime["idle_square_index"] = square_index

        return moved_any
    finally:
        runtime["idle_patrol_active"] = False


def _active_bloom_detection(runtime):
    if runtime.get("movement_requires_fresh_scan"):
        return None

    active = runtime.get("active_bloom")
    if not isinstance(active, dict):
        return None
    candidates = runtime.get("latest_bloom_candidates", [])
    for candidate in candidates if isinstance(candidates, list) else []:
        if agc.same_token_candidate(active, candidate, TARGET_LOCK_SWITCH_DISTANCE):
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
    agc.clear_locked_target(runtime)


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
    agc.clear_locked_target(runtime)
    return True


def _finish_petal_orbit(runtime):
    runtime["bloom_mode"] = "patrol"
    runtime["active_bloom"] = None
    runtime["petal_orbit_center"] = None
    runtime["petal_orbit_deadline"] = 0.0
    runtime["petal_orbit_index"] = None
    agc.clear_locked_target(runtime)
    agc.refresh_sprinkler_anchor(runtime, force=True, **_anchor_kwargs())


def _execute_petal_orbit(runtime):
    if time.time() >= float(runtime.get("petal_orbit_deadline", 0.0)):
        _finish_petal_orbit(runtime)
        return True

    center = runtime.get("petal_orbit_center")
    if not isinstance(center, (tuple, list)) or len(center) != 2:
        _finish_petal_orbit(runtime)
        return True

    points = [
        (float(center[0]) + PETAL_ORBIT_RADIUS, float(center[1])),
        (float(center[0]), float(center[1]) + PETAL_ORBIT_RADIUS),
        (float(center[0]) - PETAL_ORBIT_RADIUS, float(center[1])),
        (float(center[0]), float(center[1]) - PETAL_ORBIT_RADIUS),
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


def _select_movement_target(runtime):
    if runtime.get("movement_requires_fresh_scan"):
        return None

    latest = agc.latest_target(runtime)
    locked = agc.locked_target(runtime)
    now = time.time()

    if locked:
        remaining_x = float(locked.get("future_x", runtime["current_x"])) - runtime["current_x"]
        remaining_y = float(locked.get("future_y", runtime["current_y"])) - runtime["current_y"]
        remaining = math.hypot(remaining_x, remaining_y)
        if remaining <= BLOOM_SETTLE_DISTANCE:
            agc.clear_locked_target(runtime)
            return None

        last_seen = float(locked.get("last_seen", locked.get("locked_at", now)))
        if latest and agc.same_token_candidate(locked, latest, TARGET_LOCK_SWITCH_DISTANCE):
            old_future_x = float(locked.get("future_x", latest.get("future_x", 0.0)))
            old_future_y = float(locked.get("future_y", latest.get("future_y", 0.0)))
            new_future_x = float(latest.get("future_x", old_future_x))
            new_future_y = float(latest.get("future_y", old_future_y))
            locked.update(latest)
            locked["future_x"] = old_future_x + ((new_future_x - old_future_x) * TARGET_POSITION_SMOOTHING)
            locked["future_y"] = old_future_y + ((new_future_y - old_future_y) * TARGET_POSITION_SMOOTHING)
            locked["last_seen"] = now
            agc.set_locked_target(runtime, locked)
            return locked

        if now - last_seen <= TARGET_LOCK_LOST_TIMEOUT:
            return locked

        if latest and latest.get("score", 0.0) >= locked.get("score", 0.0) * TARGET_LOCK_SWITCH_SCORE_MULTIPLIER:
            latest["locked_at"] = now
            latest["last_seen"] = now
            agc.set_locked_target(runtime, latest)
            return latest

        agc.clear_locked_target(runtime)
        if latest:
            latest["locked_at"] = now
            latest["last_seen"] = now
            agc.set_locked_target(runtime, latest)
        return latest

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
    remaining_distance = math.hypot(remaining_x, remaining_y)
    if remaining_distance <= BLOOM_SETTLE_DISTANCE:
        agc.clear_locked_target(runtime)
        return False
    _debug_log(
        f"moving toward planned target={target['name']} remaining=({remaining_x:.2f},{remaining_y:.2f}) score={target['score']:.2f}",
        min_interval=0.25,
        key="planned_move",
    )
    return _execute_movement_to_target(remaining_x, remaining_y)


def _process_combined_detections(runtime, output, transform, inference_ms, publish_petals=True):
    detections = agc.decode_detections(
        runtime,
        "combined",
        output,
        min(BLOOM_MIN_CONFIDENCE, PETAL_CONFIDENCE_THRESHOLD),
    )
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
            bloom_detections.append((agc.capture_box_to_model(runtime, capture_box), 0, confidence))
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


def _apply_bloom_sprinkler_result(runtime, result):
    if not _bloom_sprinkler_anchor_should_run(runtime):
        return False
    return agc.maybe_apply_sprinkler_anchor(
        runtime,
        result,
        field_drift_compensation=FIELD_DRIFT_COMPENSATION,
        use_sprinkler_model=USE_SPRINKLER_MODEL_FOR_DRIFT_COMPENSATION,
        anchor_refresh_interval=ANCHOR_REFRESH_INTERVAL,
        max_passive_distance=ANCHOR_MAX_PASSIVE_DISTANCE,
        force=force_anchor_needed(runtime),
        debug_log_fn=_debug_log,
    )


def _bloom_sprinkler_anchor_should_run(runtime):
    if runtime.get("movement_count", 0) > 0:
        return False
    now = time.time()
    force = force_anchor_needed(runtime)
    if not force and now - runtime.get("last_anchor_time", 0.0) < BLOOM_SPRINKLER_ANCHOR_INTERVAL:
        return False
    return agc.sprinkler_anchor_should_run(
        runtime,
        field_drift_compensation=FIELD_DRIFT_COMPENSATION,
        use_sprinkler_model=USE_SPRINKLER_MODEL_FOR_DRIFT_COMPENSATION,
        anchor_refresh_interval=ANCHOR_REFRESH_INTERVAL,
        force=force,
    )


def _refresh_bloom_sprinkler_anchor(runtime):
    if not _bloom_sprinkler_anchor_should_run(runtime):
        return False
    return agc.refresh_sprinkler_anchor(
        runtime,
        force=force_anchor_needed(runtime),
        **_anchor_kwargs(),
    )


def force_anchor_needed(runtime):
    return math.hypot(runtime.get("current_x", 0.0), runtime.get("current_y", 0.0)) >= BLOOM_FORCE_ANCHOR_DISTANCE


def _initialise_runtime():
    agc.require_vision_deps()

    model_label, model_coreml, model_onnx, model_size, model_output = BLOOM_MODEL_VARIANTS[BLOOM_MODEL_SELECTION]
    combined_candidates = [
        (MODEL_DIR / model_coreml, "coreml"),
        (MODEL_DIR / model_onnx, "opencv_onnx"),
    ]
    combined_candidates = [candidate for candidate in combined_candidates if candidate[0].exists()]
    download_result = {}
    if not combined_candidates:
        download_result = agc.check_missing_models("blooms_ai", [model_coreml, model_onnx])
        combined_candidates = [
            (MODEL_DIR / model_coreml, "coreml"),
            (MODEL_DIR / model_onnx, "opencv_onnx"),
        ]
        combined_candidates = [candidate for candidate in combined_candidates if candidate[0].exists()]
    if not combined_candidates:
        failures = download_result.get("failures", {})
        detail = f" Download attempt failed: {'; '.join(failures.values())}" if failures else ""
        raise FileNotFoundError(
            f"No Bloom-only AI model was found for {model_label} "
            f"({model_coreml} or {model_onnx}).{detail}"
        )
    combined_path, combined_model_kind = combined_candidates[0]
    if combined_model_kind == "coreml":
        agc.require_coreml_or_raise()

    sprinkler_path, sprinkler_model_kind = agc.resolve_sprinkler_model(tag="blooms_ai")

    capture = agc.build_capture(getattr(self, "robloxWindow", None), CAPTURE_BACKEND)
    token_crop_info = agc.token_crop_for_capture(capture)
    upper_token_monitor = None
    upper_token_bbox = None
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

    homography = agc.compute_homography(capture["width"], capture["height"])
    if homography is None:
        raise RuntimeError("Could not compute BloomsAI homography.")

    if combined_model_kind == "opencv_onnx":
        combined_session, combined_input, combined_output = agc.load_onnx_model(combined_path)
        agc.delete_model_path(MODEL_DIR / model_coreml, _debug_log)
    else:
        combined_session, combined_input, combined_output = agc.load_coreml_model(
            combined_path,
            compiled_output_name=model_output,
        )
        agc.delete_model_path(MODEL_DIR / model_onnx, _debug_log)

    sprinkler_session, sprinkler_input, sprinkler_output = agc.load_sprinkler_session(
        sprinkler_path,
        sprinkler_model_kind,
        _debug_log,
    )

    return {
        "runtime_version": RUNTIME_VERSION,
        "capture": capture,
        "token_crop": token_crop_info["rect"],
        "upper_token_monitor": upper_token_monitor,
        "upper_token_bbox": upper_token_bbox,
        "combined_session": combined_session,
        "combined_input": combined_input,
        "combined_output": combined_output,
        "combined_model_kind": combined_model_kind,
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
        "idle_patrol_active": False,
        "scan_lock": threading.Lock(),
        "sprinkler_infer_lock": threading.Lock(),
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
        "annotate_recording_frame": _annotate_recording_frame,
    }


runtime = _runtime_state()
if (
    runtime.get("runtime_version") != RUNTIME_VERSION
    or runtime.get("combined_model_selection") != BLOOM_MODEL_SELECTION
):
    agc.stop_all_scanner_threads(runtime)
    agc.release_video_writer(runtime, debug_log_fn=_debug_log)
    runtime.clear()
if not runtime.get("ready"):
    try:
        runtime.clear()
        runtime.update(_initialise_runtime())
        runtime["ready"] = True
        runtime["error"] = ""
        _debug_log(
            f"runtime ready combined_model={runtime['combined_model_label']} kind={runtime['combined_model_kind']} input={runtime['combined_input']} output={runtime['combined_output']} bloom_confidence={BLOOM_MIN_CONFIDENCE} petal_confidence={PETAL_CONFIDENCE_THRESHOLD} record={RECORD_VIDEO}"
        )
    except Exception as exc:
        runtime["ready"] = False
        runtime["error"] = str(exc)
        _debug_log(f"initialisation failed: {exc}")


if not runtime.get("ready"):
    print(f"[blooms_ai] {runtime.get('error', 'initialisation failed')}")
else:
    try:
        agc.ensure_capture_thread(runtime, interval=0.016, debug_log_fn=_debug_log)
        agc.wait_for_capture_ready(runtime, timeout=1.0)
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
            apply_fn=_apply_bloom_sprinkler_result,
        )
        _refresh_bloom_sprinkler_anchor(runtime)

        target = agc.locked_target(runtime) or agc.latest_target(runtime)
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
        agc.release_video_writer(runtime, debug_log_fn=_debug_log)
        print(f"[blooms_ai] runtime error: {exc}")
