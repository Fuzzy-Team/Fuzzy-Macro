import argparse
import math
import os
import sys
import time

import cv2

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if os.getcwd() != SCRIPT_DIR:
    os.chdir(SCRIPT_DIR)
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from modules.screen.bloom_detector import BloomDetector
from modules.screen.robloxWindow import RobloxWindowBounds
from modules.screen.screenshot import mssScreenshotNP
import modules.misc.settingsManager as settingsManager
from modules.controls.keyboard import keyboard
from modules.submacros.hasteCompensation import HasteCompensationRevamped


def annotate_candidates(bgr, candidates, limit=10):
    output = bgr.copy()
    for idx, candidate in enumerate(candidates[:limit], start=1):
        center = (int(candidate.x), int(candidate.y))
        radius = max(6, int(round(candidate.radius)))
        cv2.circle(output, center, radius, (0, 255, 255), 2)
        cv2.circle(output, center, 3, (0, 0, 255), -1)
        label = (
            f"{idx}: score={candidate.score:.2f} "
            f"petal={candidate.petal_ratio:.2f} circ={candidate.circularity:.2f}"
        )
        cv2.putText(
            output,
            label,
            (center[0] + 8, max(20, center[1] - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
    return output


def capture_candidates(window, detector, preferred_color=None):
    raw = mssScreenshotNP(window.mx, window.my, window.mw, window.mh)
    bgr = cv2.cvtColor(raw, cv2.COLOR_BGRA2BGR)
    candidates = detector.detect_candidates(bgr, preferred_color=preferred_color)
    return bgr, candidates


def print_summary(candidates):
    if not candidates:
        print("No bloom candidates detected.")
        return
    print(f"Detected {len(candidates)} bloom candidate(s).")
    for idx, candidate in enumerate(candidates[:5], start=1):
        print(
            f"  {idx}. x={candidate.x} y={candidate.y} "
            f"score={candidate.score:.3f} petal={candidate.petal_ratio:.3f} "
            f"circ={candidate.circularity:.3f} fill={candidate.center_fill_ratio:.3f}"
        )


class BloomMover:
    def __init__(self, window):
        settings = settingsManager.loadAllSettings()
        self.window = window
        self.haste_comp = HasteCompensationRevamped(window, settings["movespeed"])
        self.keyboard = keyboard(settings["movespeed"], settings["haste_compensation"], self.haste_comp)
        self.calibration = {
            "ready": False,
            "vf_x": 0.0,
            "vf_y": 0.0,
            "vr_x": 0.0,
            "vr_y": 0.0,
            "forward_pos_key": "w",
            "forward_neg_key": "s",
            "strafe_pos_key": "d",
            "strafe_neg_key": "a",
        }

    def reset_calibration(self):
        self.calibration["ready"] = False

    def walk_tiles(self, key, tiles):
        tiles = float(tiles)
        if abs(tiles) < 0.15:
            return
        print(f"  move {key} {abs(tiles):.2f} tile(s)")
        self.keyboard.tileWalk(key, abs(tiles))

    def find_nearest(self, candidates, x, y):
        if not candidates:
            return None
        return min(candidates, key=lambda candidate: (candidate.x - x) ** 2 + (candidate.y - y) ** 2)

    def measure_shift(self, detector_fn, move_key, undo_key, tiles, target):
        self.walk_tiles(move_key, tiles)
        time.sleep(0.08)
        moved_target = self.find_nearest(detector_fn(), target.x, target.y)
        self.walk_tiles(undo_key, tiles)
        time.sleep(0.06)
        if moved_target is None:
            return None
        return moved_target.x - target.x, moved_target.y - target.y

    def probe_direction(self, detector_fn, move_key, undo_key, tiles, target):
        shift = self.measure_shift(detector_fn, move_key, undo_key, tiles, target)
        if shift is None:
            return None
        center_x = self.window.mw / 2.0
        center_y = self.window.mh / 2.0
        base_dx = target.x - center_x
        base_dy = target.y - center_y
        moved_dx = base_dx + shift[0]
        moved_dy = base_dy + shift[1]
        base_d2 = (base_dx * base_dx) + (base_dy * base_dy)
        moved_d2 = (moved_dx * moved_dx) + (moved_dy * moved_dy)
        return {
            "move_key": move_key,
            "undo_key": undo_key,
            "shift_x": shift[0],
            "shift_y": shift[1],
            "improvement": base_d2 - moved_d2,
        }

    def choose_probe(self, detector_fn, target, options, tiles):
        probes = []
        for move_key, undo_key in options:
            probe = self.probe_direction(detector_fn, move_key, undo_key, tiles, target)
            if probe is not None:
                probes.append(probe)
        if not probes:
            return None
        return max(
            probes,
            key=lambda probe: (
                probe["improvement"],
                abs(probe["shift_x"]) + abs(probe["shift_y"]),
            ),
        )

    def try_calibrate(self, detector_fn, target, calib_tiles=3.0):
        forward_probe = self.choose_probe(detector_fn, target, [("w", "s"), ("s", "w")], calib_tiles)
        strafe_probe = self.choose_probe(detector_fn, target, [("d", "a"), ("a", "d")], calib_tiles)
        if forward_probe is None or strafe_probe is None:
            print("Calibration failed: lost bloom during probe.")
            return False

        vf_x = forward_probe["shift_x"] / calib_tiles
        vf_y = forward_probe["shift_y"] / calib_tiles
        vr_x = strafe_probe["shift_x"] / calib_tiles
        vr_y = strafe_probe["shift_y"] / calib_tiles
        det = (vf_x * vr_y) - (vf_y * vr_x)
        if abs(det) < 1e-6:
            print("Calibration failed: degenerate movement matrix.")
            return False

        self.calibration = {
            "ready": True,
            "vf_x": vf_x,
            "vf_y": vf_y,
            "vr_x": vr_x,
            "vr_y": vr_y,
            "forward_pos_key": forward_probe["move_key"],
            "forward_neg_key": forward_probe["undo_key"],
            "strafe_pos_key": strafe_probe["move_key"],
            "strafe_neg_key": strafe_probe["undo_key"],
        }
        print(
            "Calibration ready: "
            f"vf=({vf_x:.3f}, {vf_y:.3f}) [{forward_probe['move_key']}] "
            f"vr=({vr_x:.3f}, {vr_y:.3f}) [{strafe_probe['move_key']}]"
        )
        return True

    def sweep_area(self, radius_tiles=5.0):
        print(f"  sweep radius {radius_tiles:.2f}")
        self.keyboard.multiWalk(["w", "d"], radius_tiles / 8.3)
        self.keyboard.multiWalk(["s", "d"], radius_tiles / 8.3)
        self.keyboard.multiWalk(["s", "a"], radius_tiles / 8.3)
        self.keyboard.multiWalk(["w", "a"], radius_tiles / 8.3)
        self.walk_tiles("w", radius_tiles * 0.6)
        self.walk_tiles("s", radius_tiles * 0.6)

    def compute_step(self, target):
        if not self.calibration["ready"]:
            return None

        center_x = self.window.mw / 2.0
        center_y = self.window.mh / 2.0
        dx = target.x - center_x
        dy = target.y - center_y

        vf_x = self.calibration["vf_x"]
        vf_y = self.calibration["vf_y"]
        vr_x = self.calibration["vr_x"]
        vr_y = self.calibration["vr_y"]
        det = (vf_x * vr_y) - (vf_y * vr_x)
        if abs(det) < 1e-6:
            print("Calibration invalidated.")
            self.calibration["ready"] = False
            return None

        forward_tiles = (((-dx) * vr_y) - ((-dy) * vr_x)) / det
        strafe_tiles = ((vf_x * (-dy)) - (vf_y * (-dx))) / det
        return {
            "dx": dx,
            "dy": dy,
            "forward_tiles": forward_tiles,
            "strafe_tiles": strafe_tiles,
            "distance_px": math.hypot(dx, dy),
        }

    def apply_step(self, forward_tiles, strafe_tiles):
        forward_tiles = max(min(forward_tiles, 4.5), -4.5)
        strafe_tiles = max(min(strafe_tiles, 4.5), -4.5)
        forward_pos_key = self.calibration["forward_pos_key"]
        forward_neg_key = self.calibration["forward_neg_key"]
        strafe_pos_key = self.calibration["strafe_pos_key"]
        strafe_neg_key = self.calibration["strafe_neg_key"]

        if forward_tiles > 0:
            self.walk_tiles(forward_pos_key, forward_tiles)
        elif forward_tiles < 0:
            self.walk_tiles(forward_neg_key, -forward_tiles)

        if strafe_tiles > 0:
            self.walk_tiles(strafe_pos_key, strafe_tiles)
        elif strafe_tiles < 0:
            self.walk_tiles(strafe_neg_key, -strafe_tiles)

        time.sleep(0.1)

    def chase_and_sweep(self, detector_fn, max_steps=5, settle_px=70.0):
        if not self.calibration["ready"]:
            return False

        last_target = None
        for _ in range(max_steps):
            candidates = detector_fn()
            if not candidates:
                break
            target = max(
                candidates,
                key=lambda candidate: (
                    candidate.score,
                    -(
                        (candidate.x - (self.window.mw / 2.0)) ** 2
                        + (candidate.y - (self.window.mh / 2.0)) ** 2
                    ),
                ),
            )
            last_target = target
            step = self.compute_step(target)
            if step is None:
                return False

            print(
                f"Target offset dx={step['dx']:.1f} dy={step['dy']:.1f} -> "
                f"forward={step['forward_tiles']:.2f} strafe={step['strafe_tiles']:.2f}"
            )

            if step["distance_px"] <= settle_px or (
                abs(step["forward_tiles"]) < 0.2 and abs(step["strafe_tiles"]) < 0.2
            ):
                self.sweep_area()
                return True

            self.apply_step(step["forward_tiles"], step["strafe_tiles"])

        if last_target is not None:
            self.sweep_area()
            return True
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Manual bloom detector test for the Roblox window."
    )
    parser.add_argument(
        "--color",
        default=None,
        help="Preferred bloom petal color: red, blue, white, pink, green, cyan, yellow.",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="Seconds between captures in watch mode.",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Continuously capture and overwrite the output image.",
    )
    parser.add_argument(
        "--move",
        action="store_true",
        help="Calibrate movement and walk toward the nearest detected bloom.",
    )
    parser.add_argument(
        "--max-cycles",
        type=int,
        default=0,
        help="Stop after this many watch cycles in --move mode. 0 means unlimited.",
    )
    parser.add_argument(
        "--output",
        default="../data/user/bloom_test_latest.png",
        help="Output PNG path for the annotated capture.",
    )
    args = parser.parse_args()

    window = RobloxWindowBounds()
    window.setRobloxWindowBounds()
    if window.mw <= 0 or window.mh <= 0:
        print("Could not find a Roblox window.")
        return 1

    detector = BloomDetector()
    mover = BloomMover(window) if args.move else None
    output_path = os.path.abspath(args.output)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    print(
        f"Using Roblox window at x={window.mx}, y={window.my}, "
        f"w={window.mw}, h={window.mh}"
    )
    if args.color:
        print(f"Preferred color filter: {args.color}")
    if args.move:
        print("Movement mode enabled.")
    print(f"Annotated output: {output_path}")

    cycles = 0

    def detect_only():
        _bgr, _candidates = capture_candidates(window, detector, preferred_color=args.color)
        return _candidates

    while True:
        bgr, candidates = capture_candidates(window, detector, preferred_color=args.color)
        print_summary(candidates)
        if candidates:
            annotated = annotate_candidates(bgr, candidates)
            cv2.imwrite(output_path, annotated)
            print(f"Saved bloom screenshot: {output_path}")

        if args.move and candidates:
            target = max(
                candidates,
                key=lambda candidate: (
                    candidate.score,
                    -(
                        (candidate.x - (window.mw / 2.0)) ** 2
                        + (candidate.y - (window.mh / 2.0)) ** 2
                    ),
                ),
            )
            print(
                f"Selected target x={target.x} y={target.y} "
                f"score={target.score:.2f} radius={target.radius:.1f}"
            )
            if not mover.calibration["ready"]:
                mover.try_calibrate(detect_only, target)
            if mover.calibration["ready"]:
                mover.chase_and_sweep(detect_only)
        elif args.move:
            print("No candidates available for movement.")

        if not args.watch:
            break

        cycles += 1
        if args.max_cycles and cycles >= args.max_cycles:
            break
        print(f"Sleeping {args.interval:.2f}s. Press Ctrl+C to stop.\n")
        time.sleep(args.interval)

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nStopped.")
        raise SystemExit(130)
