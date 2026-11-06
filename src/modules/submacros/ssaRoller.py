import os
import re
import tempfile
import threading
import time

import pyautogui as pag

from modules.controls.keyboard import keys

import modules.controls.mouse as mouse
import modules.misc.appManager as appManager
from modules.screen.robloxWindow import RobloxWindowBounds
from modules.screen.screenshot import mssScreenshot

# In-game layout, ported from NatroMacroDev PR #113 (its SSA() roller). Unlike
# Natro's Windows client pixels these are Roblox window points, like the other
# tools, so they still need checking on a Mac.
# The purchase prompt is a blue panel at the window center (just below the
# middle) with a green button on its left and a red one on its right, each
# 5.5% of the window width away (clamped to MIN/MAX_ROLL_OFFSET). A single
# roll clicks the right button, Double Passive the left one.
# The result text is read from a box just right of center.
RESULT_OFFSET = (20, 20)  # from the window's horizontal center and 0.4 * height
RESULT_SIZE = (188, 160)
# The generator's E prompt ("Spend 10,000,000,000 Honey to Generate a Supreme Star Amulet.")
# sits top-center under the honey bar. Measured on a 1920x1080 capture: its box spans
# x 780-1135 and y 60-120 while the honey bar ends at y 56 (yOffset is 21).
E_PROMPT_BOX = (-250, 35, 500, 80)  # x from the window center, y below yOffset, width, height
MIN_ROLL_OFFSET = 70
MAX_ROLL_OFFSET = 110
ROLL_INTERVAL = 0.9  # seconds between roll clicks
SETTLE_AFTER_ROLL = 0.75  # seconds for the result to appear after the prompt closes


# Roll prices in billions of honey (from Natro's SSA roller).
ROLL_COST_B = {False: 10, True: 500}
STATS_PER_ROLL = 5
OPEN_PROMPT_TIMEOUT = 2.5
READ_TIMEOUT = 8.0  # seconds without a verified roll before Safety stops the tool

PASSIVES = {
    # key: words that must all appear in a line (any spelling in a group is fine)
    "pop": (("pop",), ("star",)),
    "scorch": (("scorch", "scorching"), ("star",)),
    "gummy": (("gummy", "cummy", "gurnrny", "gurnmy", "gurnny"), ("star",)),
    "guiding": (("guiding",), ("star",)),
    "saw": (("saw",), ("star",)),
    "shower": (("shower",), ("star",)),
}

# key: (min % range users can ask for / range a valid roll shows)
STAT_RANGES = {
    "pollen": (5, 20),
    "white": (15, 70),
    "red": (15, 70),
    "blue": (15, 70),
    "gather": (15, 70),
    "convert": (105, 125),
    "critical": (1, 7),
    "instant": (3, 12),
    "ability": (1, 7),
}


# ------------------------------ OCR parsing --------------------------------

def _distance(a, b):
    """Levenshtein distance."""
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb)))
        previous = current
    return previous[-1]


def _has_word(tokens, word):
    max_distance = 2 if len(word) >= 6 else 1
    return any(
        token == word or (abs(len(token) - len(word)) <= max_distance and _distance(token, word) <= max_distance)
        for token in tokens
    )


def _tokens(line):
    """Lowercase letters only, with the digits OCR confuses for letters swapped back."""
    line = line.lower().replace("0", "o").replace("1", "l").replace("5", "s")
    return re.sub(r"[^a-z]+", " ", line).split()


def _is_passive(key, tokens):
    return all(any(_has_word(tokens, word) for word in group) for group in PASSIVES[key])


def _is_stat_line(key, tokens):
    if key == "pollen":
        return _has_word(tokens, "pollen") and not any(
            _has_word(tokens, word) for word in ("red", "blue", "white", "bee", "gather")
        )
    if key == "gather":
        return _has_word(tokens, "gather") and _has_word(tokens, "pollen")
    if key == "critical":
        return _has_word(tokens, "critical") and _has_word(tokens, "chance")
    if key == "instant":
        return _has_word(tokens, "instant") and _has_word(tokens, "conversion")
    if key == "ability":
        return _has_word(tokens, "ability") and _has_word(tokens, "rate")
    if key == "convert":
        return _has_word(tokens, "convert") and _has_word(tokens, "rate")
    return _has_word(tokens, key)  # red, blue, white


def _digits(text):
    """OCR often reads 1 as l/i and 5 as s inside numbers."""
    return text.translate(str.maketrans("lis", "115"))


def _stat_value(line, key):
    """The number on a stat line: 15 for '+15%', 125 for 'x1.25 Convert Rate'. None if unreadable."""
    line = re.sub(r"x\s*[li]", "x1", line.lower())
    line = re.sub(r"(\d)\s+(?=\d)", r"\1", line)
    line = re.sub(r"(\.)\s+(?=\d)", r"\1", line)
    if key == "convert":
        match = re.search(r"x?\s*([0-9lis.\s]+)\s*convert\s*rate", line)
        if match:
            raw = re.sub(r"[^0-9.]", "", _digits(re.sub(r"\s+", "", match.group(1))))
            if re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", raw) and 1.0 <= float(raw) <= 2.0:
                return int(round(float(raw) * 100))
        return None
    match = re.search(r"(?<![a-z])([0-9lis][0-9lis\s]*)%", line)
    if match:
        raw = _digits(re.sub(r"\s+", "", match.group(1)))
        if raw.isdigit():
            return int(raw)
    return None


def parse_roll(texts, double_passive=False):
    """Turn OCR text boxes into {"stats": {key: value}, "passives": set}.
    Returns None unless it reads as a complete roll: five in-range stats and one
    passive (two for Double Passive)."""
    stats = {}
    passives = set()
    for text in texts:
        for line in re.split(r"[|\n]", text or ""):
            line = line.strip()
            if not line:
                continue
            tokens = _tokens(line)
            for key, (low, high) in STAT_RANGES.items():
                if key in stats or not _is_stat_line(key, tokens):
                    continue
                value = _stat_value(line, key)
                if value is not None and low <= value <= high:
                    stats[key] = value
            for key in PASSIVES:
                if _is_passive(key, tokens):
                    passives.add(key)
    if len(stats) != STATS_PER_ROLL or len(passives) < (2 if double_passive else 1):
        return None
    return {"stats": stats, "passives": passives}


def is_e_prompt(texts):
    """True if OCR text reads as the Supreme Star Amulet generator's E prompt."""
    tokens = _tokens(" ".join(texts))
    return _has_word(tokens, "supreme") and _has_word(tokens, "amulet")


def roll_matches(roll, config):
    if config["main_passive"] not in roll["passives"]:
        return False
    if config["double_passive"] and config["side_passives"]:
        if not any(side in roll["passives"] for side in config["side_passives"]):
            return False
    for key, minimum in config["stats"].items():
        value = roll["stats"].get(key)
        if value is None or value < minimum:
            return False
    return True


def normalize_config(raw):
    """Validate the settings from the UI. Raises ValueError with a message for the user."""
    raw = raw or {}
    main = raw.get("main_passive")
    if main not in PASSIVES:
        raise ValueError("Pick a main passive.")
    double = bool(raw.get("double_passive"))
    sides = [key for key in raw.get("side_passives") or [] if key in PASSIVES and key != main]
    stats = {}
    for entry in raw.get("stats") or []:
        key = entry.get("key")
        if not key:
            continue
        if key not in STAT_RANGES:
            raise ValueError("Unknown stat: {}.".format(key))
        if key in stats:
            raise ValueError("Each stat can only be picked once.")
        try:
            minimum = int(entry.get("min") or 0)
        except (TypeError, ValueError):
            raise ValueError("Min % must be a number.")
        low, high = STAT_RANGES[key]
        stats[key] = 0 if minimum <= 0 else max(low, min(high, minimum))
    if len(stats) > STATS_PER_ROLL:
        raise ValueError("Pick up to {} stats.".format(STATS_PER_ROLL))
    try:
        honey_limit = max(0, int(raw.get("honey_limit") or 0))
    except (TypeError, ValueError):
        raise ValueError("Honey limit must be a whole number of trillions.")
    return {
        "main_passive": main,
        "wait_for_command": bool(raw.get("wait_for_command")),
        "manual_review": bool(raw.get("manual_review")),
        "double_passive": double,
        "side_passives": sides,
        "stats": stats,
        "honey_limit": honey_limit,
        "safety": bool(raw.get("safety")),
    }


# -------------------------------- Runner -----------------------------------

class SsaRollerRunner:
    def __init__(self, event_callback=None):
        # Shared with the Discord bot (set by gui.configureToolRuntime). The roller sets it to
        # "" (not running), "rolling", "waiting" (for /ssa go) or "reviewing" (for /ssa approve|deny);
        # the bot answers with "go", "approve", "deny" or "end" (stops like F3).
        self.command = None
        self._image = None  # the last result crop that was read
        self._event_callback = event_callback
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread = None
        self._status = self._fresh_status()
        self._window = None

    def _fresh_status(self):
        return {
            "running": False,
            "state": "idle",
            "message": "Ready",
            "result": "",
            "rolls": 0,
            "honey_spent_b": 0,
            "last_detected_text": "",
        }

    def get_status(self):
        with self._lock:
            return dict(self._status)

    def is_active(self):
        with self._lock:
            return bool(self._thread and self._thread.is_alive())

    def _update_status(self, **kwargs):
        with self._lock:
            self._status.update(kwargs)

    def _emit(self, event_name, **payload):
        if self._event_callback:
            try:
                self._event_callback(event_name, payload)
            except Exception:
                pass  # a failed Discord message must not stop the roller

    def _refuse(self, message):
        """Refuse to start. The message goes in the status too, since the UI polls it."""
        if not self.is_active():
            self._update_status(message=message)
        return {"ok": False, "message": message}

    def start(self, config, run_state=3):
        if run_state != 3:
            return self._refuse("Stop the macro before starting this tool.")
        try:
            config = normalize_config(config)
        except ValueError as exc:
            return self._refuse(str(exc))
        with self._lock:
            if self._thread and self._thread.is_alive():
                return {"ok": False, "message": "The tool is already running."}
            self._stop_event.clear()
            self._status = self._fresh_status()
            self._status.update(running=True, state="starting", message="Preparing Roblox window.")
            self._thread = threading.Thread(target=self._run, args=(config,), daemon=True)
            self._thread.start()
        return {"ok": True, "message": "Tool started. Roblox will be focused automatically."}

    def stop(self):
        self._stop_event.set()
        thread = self._thread
        if thread and thread.is_alive():
            self._update_status(message="Stopping after the current step.")
            thread.join(timeout=0.5)
        return {"ok": True, "message": "Stop requested."}

    def _set_command(self, value):
        if self.command is not None:
            self.command.value = value

    def _raise_if_stopped(self):
        if self.command is not None and self.command.value == "end":
            self._stop_event.set()
        if self._stop_event.is_set():
            raise RuntimeError("Stopped by user.")

    def _wait(self, seconds):
        end = time.time() + seconds
        while time.time() < end:
            self._raise_if_stopped()
            time.sleep(min(0.05, max(0, end - time.time())))
        self._raise_if_stopped()

    def _roll_offset(self):
        return min(MAX_ROLL_OFFSET, max(MIN_ROLL_OFFSET, round(self._window.mw * 0.055)))

    def _prompt_center(self):
        window = self._window
        return window.mx + window.mw // 2, window.my + window.yOffset + window.mh // 2 + 30

    def _prompt_visible(self):
        """Natro's colour check: blue panel at the center, green button left, red button right."""
        x, y = self._prompt_center()
        offset = self._roll_offset()
        width = 2 * offset + 17
        image = mssScreenshot(x - offset - 8, y - 8, width, 17)
        scale = image.width / width  # 2 on Retina

        def pixel(px, py):
            return image.getpixel((min(image.width - 1, round(px * scale)), min(image.height - 1, round(py * scale))))

        r, g, b = pixel(offset + 8, 8)
        if b < r + 60 or b < g + 20:
            return False
        green = red = 0
        for dx in (-8, 0, 8):
            for dy in (-8, 0, 8):
                r, g, b = pixel(8 + dx, 8 + dy)
                green += g > r * 1.5 and g > b * 1.25
                r, g, b = pixel(2 * offset + 8 + dx, 8 + dy)
                red += r > g * 1.6 and r > b * 1.25
        return green >= 2 and red >= 2

    def _click_roll(self, double_passive):
        x, y = self._prompt_center()
        offset = self._roll_offset()
        mouse.moveTo(x - offset if double_passive else x + offset, y)
        self._wait(0.075)
        if not self._prompt_visible():
            return False
        mouse.click()
        # park the cursor so it doesn't sit over the result
        mouse.moveTo(self._window.mx + 10, self._window.my + self._window.mh - 10)
        return True

    def _ocr(self, x, y, width, height):
        import modules.screen.ocr as ocr

        image = self._image = mssScreenshot(x, y, width, height)
        return [entry[1][0] for entry in ocr.ocrRead(image) if entry and len(entry) > 1 and entry[1][0]]

    def _read_texts(self):
        window = self._window
        x = window.mx + window.mw // 2 + RESULT_OFFSET[0]
        y = window.my + window.yOffset + round(0.4 * window.mh + RESULT_OFFSET[1])
        return self._ocr(x, y, RESULT_SIZE[0], RESULT_SIZE[1])

    def _save_roll_image(self, rolls):
        """Save the last result crop for Discord. Names cycle so old files get replaced."""
        path = os.path.join(tempfile.gettempdir(), "ssa_roll_{}.png".format(rolls % 20))
        self._image.save(path)
        return path

    def _e_prompt_visible(self):
        window = self._window
        x = window.mx + window.mw // 2 + E_PROMPT_BOX[0]
        y = window.my + window.yOffset + E_PROMPT_BOX[1]
        return is_e_prompt(self._ocr(x, y, E_PROMPT_BOX[2], E_PROMPT_BOX[3]))

    def _read_roll(self, double_passive, previous, timeout):
        """Read the result until two reads agree on a complete roll that differs from `previous`.
        Returns (key, roll), or None if that doesn't happen within `timeout` seconds."""
        end = time.time() + timeout
        last_key = None
        while time.time() < end:
            self._raise_if_stopped()
            texts = self._read_texts()
            roll = parse_roll(texts, double_passive)
            key = None
            if roll:
                key = (tuple(sorted(roll["stats"].items())), tuple(sorted(roll["passives"])))
            if key and key == last_key and key != previous:
                self._update_status(last_detected_text=" | ".join(texts))
                return key, roll
            last_key = key
            self._wait(0.15)
        return None

    def _await_roll(self, config, previous):
        while True:
            found = self._read_roll(config["double_passive"], previous, READ_TIMEOUT)
            if found:
                return found
            if config["safety"]:
                raise RuntimeError("Safety stop: couldn't verify a full roll in time. Check the SSA menu.")
            self._update_status(message="Can't read the roll yet. Waiting without rerolling.")

    def _open_prompt(self):
        if self._prompt_visible():
            return
        keys.press("e")
        end = time.time() + OPEN_PROMPT_TIMEOUT
        while not self._prompt_visible():
            if time.time() >= end:
                raise RuntimeError(
                    "The purchase prompt didn't appear. Stand at the generator with its E prompt visible."
                )
            self._wait(0.05)

    def _finish(self, result, message):
        self._update_status(running=False, state="finished", result=result, message=message)
        self._emit("finished", result=result, message=message)

    def _look(self, double_passive):
        """Read-only look at the screen: (purchase prompt is up, E prompt is up, open roll result or None)."""
        if self._prompt_visible():
            return True, False, None
        return False, self._e_prompt_visible(), self._read_roll(double_passive, None, 1.5)

    @staticmethod
    def _describe(purchase, e_prompt, found):
        if purchase:
            return "The purchase prompt is open."
        seen = []
        if found:
            roll = found[1]
            seen.append("A roll result is open. Passives: {}. Stats: {}.".format(
                ", ".join(sorted(roll["passives"])),
                ", ".join("{} {}".format(key, value) for key, value in sorted(roll["stats"].items())),
            ))
        if e_prompt:
            seen.append("The generator's E prompt is visible.")
        return " ".join(seen) or "Neither the E prompt, the purchase prompt nor a readable roll result is on screen."

    def _wait_for_go(self, double_passive):
        """Report what the tool sees, then do nothing until /ssa go arrives from Discord."""
        seen = self._describe(*self._look(double_passive))
        self._set_command("waiting")
        self._update_status(state="waiting", message="Waiting for /ssa go in Discord. {}".format(seen))
        self._emit("waiting", message=seen)
        while self.command.value == "waiting":
            self._wait(0.25)
        self._raise_if_stopped()  # /ssa end
        self._set_command("rolling")
        self._update_status(state="rolling", message="Starting rolls.")

    def _wait_for_review(self):
        """Wait for /ssa approve or /ssa deny (or the buttons). True means approved."""
        self._set_command("reviewing")
        self._update_status(state="reviewing", message="Match found. Waiting for approve or deny in Discord.")
        while self.command.value == "reviewing":
            self._wait(0.25)
        self._raise_if_stopped()  # /ssa end
        approved = self.command.value == "approve"
        self._set_command("rolling")
        self._update_status(state="rolling", message="Approved." if approved else "Denied. Rolling again.")
        return approved

    def _run(self, config):
        try:
            if not appManager.isAppOpen("Roblox"):
                raise RuntimeError("Roblox is not open.")
            appManager.openApp("Roblox")
            time.sleep(0.5)
            self._window = RobloxWindowBounds()
            self._window.setRobloxWindowBounds()
            if self._window.mw <= 0 or self._window.mh <= 0:
                raise RuntimeError("Unable to detect the Roblox window.")

            double = config["double_passive"]
            cost = ROLL_COST_B[double]
            limit_b = config["honey_limit"] * 1000
            if (config["wait_for_command"] or config["manual_review"]) and self.command is None:
                raise RuntimeError(
                    "Discord control isn't available. Turn off 'Wait for a Discord command' and 'Manual review' to roll without it."
                )
            self._set_command("rolling")
            if config["wait_for_command"]:
                self._wait_for_go(double)
            self._update_status(state="rolling", message="Starting rolls.")

            previous = None
            last_click = 0
            # a result left open before Start counts as the first roll
            purchase, e_prompt, found = self._look(double)
            if not (purchase or e_prompt or found):
                raise RuntimeError(
                    "Stand at the generator with its E prompt visible, or leave an SSA result open."
                )
            while True:
                if found:
                    previous, roll = found
                    found = None
                    status = self.get_status()
                    matched = roll_matches(roll, config)
                    review = matched and config["manual_review"]
                    self._emit(
                        "rolled", rolls=status["rolls"], honey_spent_b=status["honey_spent_b"], review=review,
                        image=self._save_roll_image(status["rolls"]),
                    )
                    if matched and (not review or self._wait_for_review()):
                        self._finish(
                            "success",
                            "{}. The result is left open: choose Keep or Replace in-game.".format(
                                "Approved" if review else "Found a match"
                            ),
                        )
                        return
                spent = self.get_status()["honey_spent_b"]
                if limit_b and spent + cost > limit_b:
                    self._finish("stopped", "Honey limit reached.")
                    return
                self._open_prompt()
                self._wait(max(0, ROLL_INTERVAL - (time.time() - last_click)))
                if not self._click_roll(double):
                    continue  # the prompt closed under us; open it again
                last_click = time.time()
                self._update_status(
                    rolls=self.get_status()["rolls"] + 1,
                    honey_spent_b=spent + cost,
                    message="Rolled. Reading the result.",
                )
                end = time.time() + OPEN_PROMPT_TIMEOUT
                while self._prompt_visible():
                    if time.time() >= end:
                        raise RuntimeError("The roll click wasn't accepted. Stopped without clicking again.")
                    self._wait(0.05)
                self._wait(SETTLE_AFTER_ROLL)
                found = self._await_roll(config, previous)
        except Exception as exc:
            message = str(exc)
            stopped = self._stop_event.is_set() or message == "Stopped by user."
            self._finish("stopped" if stopped else "error", "Stopped by user." if stopped else message)
        finally:
            self._set_command("")
            self._update_status(running=False)
