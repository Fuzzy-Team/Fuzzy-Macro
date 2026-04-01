import base64
import io
import re
import threading
import time
from difflib import SequenceMatcher

import cv2
import imagehash
import numpy as np
import pyautogui as pag
from PIL import Image

import modules.controls.mouse as mouse
import modules.misc.appManager as appManager
from modules.misc import messageBox
import modules.screen.ocr as ocr
from modules.misc.imageManipulation import adjustImage
from modules.screen.imageSearch import locateImageOnScreen, templateMatch
from modules.screen.robloxWindow import RobloxWindowBounds
from modules.screen.screenshot import mssScreenshot, mssScreenshotNP


class AutoGiftedBasicBeeRunner:
    BASIC_EGG_IMAGE_NAME = "basic-egg"
    ROYAL_JELLY_B64 = (
        "iVBORw0KGgoAAAANSUhEUgAAAGwAAAAcCAMAAACzmqo+AAAB+FBMVEUbKjUcKzYdLDceLDceLTgfLjkgLzohMDoiMDsjMTwkMj0kMz0lND4mND8nNUAoNkApN0EpOEIqOEMrOUMsOkQtO0UuPEYvPEYvPUcwPkgyQEkzQUo0QUs1Qkw1Q0w3RU44RU85Rk86SFE7SVI8SVM+S1Q/TFVDUFlEUVlFUVpGUltGU1xIVV1KVl9LV19MWWFPW2NWYWlXYmpXY2tbZm5cZ29daG9daXBga3JibXRibnVlcHdpdHttd35weoFxe4FyfIJzfYN0foR1f4V2gIZ3gYd4god5goh6hIp7hYt8hot+h41/iI6Aio+BipCCi5GFjpSFjpOGj5SHkJWIkZaJkpeKk5iKk5eLlJmMlZqNlpqPl5yQmJ2QmZ2Rmp6Sm5+UnKCVnaGaoqabo6ecpKigp6ujq66kq6+lrLCor7Ots7avtrmwt7mxt7qyuLu1vL62vL+3vcC5wMK6wMO8wsS9w8W/xcfAxsjDyMrDycvEyszGzM3HzM7Jzs/K0NHL0NLN0tPO09TP1NXQ1dbR1tfS19jT2NjV2drV2tvW29zX3NzY3N3a39/b4ODc4OHd4eLe4uLf4+Pg5OTg5eXi5ubj5+fk6Ojm6enm6urn6+vo7Ovp7ezq7e3r7u7r7+7s8O/t8fDu8fHv8vHw8/Lx9fTy9fTz9vX09/a7z3nGAAACf0lEQVR42u3W+VOMcQDH8Y9KVkUUkXQqJEqH0OWokHLlzplyRSgJFZWjnEmOtqhWx77/TbNPzHeenbZtZk3GjPcPO7O73/m8dvZ5fnjEPKb/2L+IpcqTI+sBc6s9d2RuR8xBb0wKaWEuXZe+Y69Beul9ZPrVJ6Z1bvBf7eyYOVI7M7YHGMiROucLo0tqwmdtRfEL4/YN/insmfQC+FyW4EiqGIRT1nvr81LeBk//0c5ZMFd1UujaiiEbZlsx2NBOpQMD8fKU8pX3QaoEqJSeQlni0frt0knf2FSOPKW7bJhtReYGWfwEKFdks6txsY5AtmImYDJWGcDYBEwlKds3Vqfo5pGWKF2yYbYVgwV1A1NLdBo4qFVwU7oF96Q64HXB8pA1S5XpG9ugGqBamXbMrJhr1ig1Ax+kx1jfDeNapm1QqLBh6IuR1Raf2NgCTRdhx8yKwcajVAR0Sr1Ah/QK9iq43+lQMVCu5K4fvSm+sZ4B/W7ChpkVg7Fb4SPwUWoDmqxz7VJNvfQI2KR6IMMbw9kHcE3qH5XOznjrmxWDtUo3wB3965rFA6xXSqbSsJhzM2CTu8K2TgIlWuEmWXnAuB2zrRjMHa9s4LAi7rpuO6Z/5UVJugxQqpUPnVcWeWHsl3b0OOtCVAXHteDqWGtsXpsXZlYMxiEF9YMzTZ7SRwA+hUihXwDezXyDuApktXkURjfKU+Rzb8ysGKxbugAMVyU7Uo+NYpUvFYKlFa92ZJXkHrBjuBuyYxelnrCOD1cmhMYVv8EbMytits5L9wkks+IfS1eimwAyK/6xDukMgWRW/GMlCu4ngMyKf+xbuPIJJLPiH6uT7hBAZuVvPMr9BDBOM9MqS26gAAAAAElFTkSuQmCC"
    )
    GIFTED_STAR_B64 = (
        "iVBORw0KGgoAAAANSUhEUgAAAAgAAAAIAgMAAAC5YVYYAAAACVBMVEX9rDT+rDT/rDOj6H2ZAAAAFElEQVR42mNYtYoBgVYyrFoBYQMAf4AKnlh184sAAAAASUVORK5CYII="
    )
    MYTHIC_NAMES = {"buoyant", "fuzzy", "precise", "spicy", "tadpole", "vector"}
    LEGENDARY_NAMES = {"baby", "carpenter", "demon", "diamond", "lion", "music", "ninja", "shy"}
    KNOWN_BEE_NAMES = {
        "basic", "bomber", "brave", "bumble", "cool", "hasty", "looker", "rad", "rascal", "stubborn",
        "bubble", "bucko", "commander", "demo", "exhausted", "fire", "frosty", "honey", "rage", "riley",
        "baby", "carpenter", "demon", "diamond", "lion", "music", "ninja", "shy",
        "buoyant", "fuzzy", "precise", "spicy", "tadpole", "vector",
    }

    def __init__(self, event_callback=None):
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread = None
        self._pause_settings = self._default_pause_settings()
        self._status = self._fresh_status()
        self._roblox_window = None
        self._cached_inventory_positions = {}
        self._templates = {}
        self._inventory_open = False
        self._event_callback = event_callback
        self._final_event_sent = False

    def _default_pause_settings(self):
        return {
            "pause_on_gifted_basic": True,
            "pause_on_gifted_other": True,
            "pause_on_mythic": False,
            "pause_on_legendary": False,
            "pause_on_basic": False,
            "pause_on_other": False,
        }

    def _fresh_status(self):
        return {
            "running": False,
            "state": "idle",
            "message": "Ready",
            "result": "",
            "rolls": 0,
            "basic_eggs_used": 0,
            "royal_jellies_used": 0,
            "last_detected_text": "",
            "bee_slot_x": None,
            "bee_slot_y": None,
            "pause_on_gifted_basic": self._pause_settings["pause_on_gifted_basic"],
            "pause_on_gifted_other": self._pause_settings["pause_on_gifted_other"],
            "pause_on_mythic": self._pause_settings["pause_on_mythic"],
            "pause_on_legendary": self._pause_settings["pause_on_legendary"],
            "pause_on_basic": self._pause_settings["pause_on_basic"],
            "pause_on_other": self._pause_settings["pause_on_other"],
        }

    def get_status(self):
        with self._lock:
            return dict(self._status)

    def is_active(self):
        with self._lock:
            return bool(
                (self._thread and self._thread.is_alive())
                or self._status.get("running")
                or self._status.get("state") == "stopping"
            )

    def _update_status(self, **kwargs):
        with self._lock:
            self._status.update(kwargs)

    def _emit_event(self, event_name, **payload):
        if not self._event_callback:
            return
        try:
            self._event_callback(event_name, payload)
        except Exception:
            pass

    def _emit_finished_once(self, result, message):
        with self._lock:
            if self._final_event_sent:
                return
            self._final_event_sent = True
        self._emit_event("finished", result=result, message=message)

    def start(self, capture_delay_seconds=3, run_state=3, pause_settings=None):
        capture_delay_seconds = int(capture_delay_seconds or 3)
        capture_delay_seconds = max(1, min(capture_delay_seconds, 10))

        thread_to_join = None
        with self._lock:
            if self._thread and not self._thread.is_alive():
                self._thread = None
            elif self._thread and self._stop_event.is_set():
                thread_to_join = self._thread
            elif self._thread and self._thread.is_alive():
                return {"ok": False, "message": "The tool is already running."}
            if run_state != 3:
                return {"ok": False, "message": "Stop the macro before starting this tool."}

        if thread_to_join:
            thread_to_join.join(timeout=0.5)

        with self._lock:
            if self._thread and self._thread.is_alive():
                return {"ok": False, "message": "The tool is still stopping. Try again in a moment."}
            if run_state != 3:
                return {"ok": False, "message": "Stop the macro before starting this tool."}
            merged_pause_settings = self._default_pause_settings()
            if isinstance(pause_settings, dict):
                for key in merged_pause_settings:
                    if key in pause_settings:
                        merged_pause_settings[key] = bool(pause_settings[key])
            merged_pause_settings["pause_on_gifted_basic"] = True
            self._pause_settings = merged_pause_settings
            self._stop_event.clear()
            self._final_event_sent = False
            self._cached_inventory_positions = {}
            self._roblox_window = None
            self._inventory_open = False
            self._status = self._fresh_status()
            self._status.update(
                {
                    "running": True,
                    "state": "starting",
                    "message": "Preparing Roblox window.",
                    **self._pause_settings,
                }
            )
            self._thread = threading.Thread(
                target=self._run,
                args=(capture_delay_seconds,),
                daemon=True,
            )
            self._thread.start()

        self._emit_event("started", message="Tool started. Roblox will be focused automatically.")
        return {"ok": True, "message": "Tool started. Roblox will be focused automatically."}

    def stop(self):
        self._stop_event.set()
        self._update_status(message="Stopping after the current step.")
        thread = self._thread
        if thread and thread.is_alive():
            thread.join(timeout=0.5)
        return {"ok": True, "message": "Stop requested."}

    def _raise_if_stopped(self):
        if self._stop_event.is_set():
            raise RuntimeError("Stopped by user.")

    def _decode_template(self, encoded):
        img = Image.open(io.BytesIO(base64.b64decode(encoded))).convert("RGBA")
        if self._roblox_window and self._roblox_window.isRetina:
            img = img.resize((img.width * 2, img.height * 2), Image.Resampling.NEAREST)
        return img

    def _prepare_templates(self):
        self._templates = {
            "royal_jelly_pil": self._decode_template(self.ROYAL_JELLY_B64),
            "gifted_star_pil": self._decode_template(self.GIFTED_STAR_B64),
            "yes_cv2": adjustImage("./images/menu", "yes", self._roblox_window.display_type),
        }
        self._templates["royal_jelly_cv2"] = cv2.cvtColor(
            self._as_np(self._templates["royal_jelly_pil"]),
            cv2.COLOR_RGBA2BGR,
        )
        self._templates["gifted_star_cv2"] = cv2.cvtColor(
            self._as_np(self._templates["gifted_star_pil"]),
            cv2.COLOR_RGBA2BGR,
        )

    def _as_np(self, img):
        return np.array(img)

    def _activate_roblox(self):
        if not appManager.isAppOpen("Roblox"):
            raise RuntimeError("Roblox is not open.")
        appManager.openApp("Roblox")
        time.sleep(0.5)
        self._roblox_window = RobloxWindowBounds()
        self._roblox_window.setRobloxWindowBounds()
        if self._roblox_window.mw <= 0 or self._roblox_window.mh <= 0:
            raise RuntimeError("Unable to detect the Roblox window.")
        self._prepare_templates()

    def _move_mouse_to_default(self):
        mouse.moveTo(
            self._roblox_window.mx + 370,
            self._roblox_window.my + self._roblox_window.yOffset + 110,
        )

    def _toggle_inventory(self, mode):
        def click_inventory_button():
            mouse.moveTo(self._roblox_window.mx + 30, self._roblox_window.my + 113)
            time.sleep(0.1)
            mouse.moveBy(0, 3)
            time.sleep(0.1)
            mouse.click()
            time.sleep(0.1)

        if mode == "open":
            mouse.moveTo(self._roblox_window.mx + 245, self._roblox_window.my + 113)
            time.sleep(0.1)
            mouse.moveBy(0, 3)
            time.sleep(0.1)
            mouse.click()
            click_inventory_button()
            time.sleep(0.1)
            self._inventory_open = True
        else:
            click_inventory_button()
            self._inventory_open = False
        self._move_mouse_to_default()
        time.sleep(0.3)

    def _focus_inventory_scroll_area(self, click=False):
        mouse.moveTo(self._roblox_window.mx + 150, self._roblox_window.my + 300)
        time.sleep(0.03)
        if click:
            mouse.click()
            time.sleep(0.05)

    def _scroll_inventory_to_top(self):
        previous_hash = None
        for _ in range(40):
            self._focus_inventory_scroll_area()
            mouse.scroll(100)
            time.sleep(0.05)
            screen = cv2.cvtColor(
                mssScreenshotNP(self._roblox_window.mx, self._roblox_window.my + 100, 100, 200),
                cv2.COLOR_BGRA2RGB,
            )
            current_hash = imagehash.average_hash(Image.fromarray(screen))
            if previous_hash is not None and previous_hash == current_hash:
                break
            previous_hash = current_hash

    def _normalize_text(self, text):
        lowered = (text or "").lower()
        collapsed = re.sub(r"[^a-z]", "", lowered)
        return lowered, collapsed

    def _word_tokens(self, text):
        return [token for token in re.findall(r"[a-z]+", (text or "").lower()) if token]

    def _similar(self, left, right):
        return SequenceMatcher(None, left, right).ratio()

    def _contains_fuzzy_token(self, tokens, target, threshold=0.8):
        for token in tokens:
            if token == target or self._similar(token, target) >= threshold:
                return True
        return False

    def _contains_fuzzy_name(self, tokens, names, threshold=0.82):
        for token in tokens:
            for name in names:
                if token == name or self._similar(token, name) >= threshold:
                    return True
        return False

    def _inventory_icon_point_from_bbox(self, bbox, crop_x, crop_y):
        xs = [point[0] for point in bbox]
        ys = [point[1] for point in bbox]
        min_x = min(xs)
        min_y = min(ys)
        max_y = max(ys)
        icon_center_y = int((min_y + max_y) / 2) + 18
        icon_x = max(12, min_x - 100)
        return (
            (crop_x - self._roblox_window.mx) + icon_x,
            (crop_y - self._roblox_window.my) + icon_center_y,
        )

    def _get_inventory_search_region(self):
        crop_x = self._roblox_window.mx + 55
        crop_y = self._roblox_window.my + 90
        crop_w = 210
        crop_h = min(max(self._roblox_window.mh - 180, 120), 220)
        return crop_x, crop_y, crop_w, crop_h

    def _find_item_in_visible_inventory(self, item_name):
        target_text = "basicegg" if item_name == "basicegg" else "royaljelly"
        crop_x, crop_y, crop_w, crop_h = self._get_inventory_search_region()
        inventory_image = mssScreenshot(crop_x, crop_y, crop_w, crop_h)
        for entry in ocr.ocrRead(inventory_image):
            if not entry or len(entry) < 2:
                continue
            bbox, data = entry
            text = data[0] if data else ""
            _, normalized = self._normalize_text(text)
            if not normalized:
                continue
            if target_text in normalized or self._similar(normalized, target_text) > 0.78:
                return self._inventory_icon_point_from_bbox(bbox, crop_x, crop_y)
        return None

    def _find_item_in_inventory(self, item_name):
        if not self._inventory_open:
            self._toggle_inventory("open")
            time.sleep(0.3)

        mouse.moveTo(self._roblox_window.mx + 312, self._roblox_window.my + 200)
        mouse.click()

        visible_position = self._find_item_in_visible_inventory(item_name)
        if visible_position:
            return visible_position

        self._scroll_inventory_to_top()
        time.sleep(0.12)

        visible_position = self._find_item_in_visible_inventory(item_name)
        if visible_position:
            return visible_position

        previous_hash = None

        for _ in range(180):
            self._raise_if_stopped()
            self._focus_inventory_scroll_area()
            mouse.scroll(-2, True)
            time.sleep(0.06)

            visible_position = self._find_item_in_visible_inventory(item_name)
            if visible_position:
                return visible_position

            scan = cv2.cvtColor(
                mssScreenshotNP(self._roblox_window.mx, self._roblox_window.my + 100, 100, 200),
                cv2.COLOR_BGRA2RGB,
            )
            current_hash = imagehash.average_hash(Image.fromarray(scan))
            if previous_hash is not None and previous_hash == current_hash:
                break
            previous_hash = current_hash
        return None

    def _drag_item_to_bee_slot(self, item_pos, bee_slot):
        item_x = self._roblox_window.mx + item_pos[0]
        item_y = self._roblox_window.my + item_pos[1]
        mouse.moveTo(item_x, item_y)
        time.sleep(0.15)
        pag.mouseDown(button="left")
        time.sleep(0.1)
        pag.moveTo(int(bee_slot[0]), int(bee_slot[1]), duration=0.25)
        time.sleep(0.1)
        pag.mouseUp(button="left")

    def _find_yes_button(self):
        x = self._roblox_window.mx + self._roblox_window.mw // 2 - 270
        y = self._roblox_window.my + self._roblox_window.mh // 2 - 60
        result = locateImageOnScreen(self._templates["yes_cv2"], x, y, 580, 265, 0.75)
        if not result:
            return None
        _, loc = result
        best_x, best_y = [value // self._roblox_window.multi for value in loc]
        return best_x + x, best_y + y

    def _click_yes_button(self):
        button_pos = self._find_yes_button()
        if not button_pos:
            return False
        best_x, best_y = button_pos
        mouse.moveTo(best_x, best_y)
        time.sleep(0.2)
        mouse.moveBy(5, 5)
        time.sleep(0.1)
        mouse.click()
        return True

    def _wait_for_yes_and_click(self):
        for _ in range(6):
            self._raise_if_stopped()
            time.sleep(0.12)
            if not self._click_yes_button():
                continue
            for _ in range(8):
                self._raise_if_stopped()
                time.sleep(0.08)
                if not self._find_yes_button():
                    return True
        return False

    def _match_template_on_image(self, image_pil, template_cv2, threshold):
        screen_bgr = cv2.cvtColor(np.array(image_pil.convert("RGB")), cv2.COLOR_RGB2BGR)
        if template_cv2.shape[0] > screen_bgr.shape[0] or template_cv2.shape[1] > screen_bgr.shape[1]:
            return False
        _, max_val, _, _ = templateMatch(template_cv2, screen_bgr)
        return max_val >= threshold

    def _should_pause_for(self, result_code):
        mapping = {
            "success": "pause_on_gifted_basic",
            "gifted_other": "pause_on_gifted_other",
            "mythic": "pause_on_mythic",
            "legendary": "pause_on_legendary",
        }
        setting = mapping.get(result_code)
        return bool(setting and self._pause_settings.get(setting))

    def _prompt_pause_decision(self, title, body):
        keep = messageBox.msgBoxOkCancel(title, body)
        if keep:
            self._update_status(
                running=False,
                state="finished",
                result="stopped",
                message="Stopped after a paused result was kept.",
            )
            return True
        return False

    def _inspect_roll_result(self):
        region_x = self._roblox_window.mx + self._roblox_window.mw // 2 - 155
        region_y = self._roblox_window.my + self._roblox_window.yOffset + ((4 * self._roblox_window.mh) // 10 - 135)
        result_image = mssScreenshot(region_x, region_y, 310, 205)
        raw_text = " ".join(
            x[1][0] for x in ocr.ocrRead(result_image) if x and len(x) > 1 and x[1][0]
        )
        lowered, collapsed = self._normalize_text(raw_text)
        tokens = self._word_tokens(raw_text)
        has_gifted_star = self._match_template_on_image(result_image, self._templates["gifted_star_cv2"], 0.84)
        has_gifted_word = "gifted" in lowered or "gifted" in collapsed or self._contains_fuzzy_token(tokens, "gifted", 0.8)
        has_bee_word = "bee" in lowered or collapsed.endswith("bee") or self._contains_fuzzy_token(tokens, "bee", 0.72)
        has_known_bee_name = self._contains_fuzzy_name(tokens, self.KNOWN_BEE_NAMES, 0.82)
        is_gifted = has_gifted_word and (has_bee_word or has_known_bee_name or has_gifted_star)
        is_basic = "basicbee" in collapsed or ("basic" in lowered and "bee" in lowered)
        is_mythic = "mythic" in lowered or any(name in collapsed for name in self.MYTHIC_NAMES)
        is_legendary = "legendary" in lowered or any(name in collapsed for name in self.LEGENDARY_NAMES)

        result = {
            "raw_text": raw_text.strip(),
            "next_item": "basicegg",
            "result_code": "other",
            "message": "",
            "is_gifted": is_gifted,
        }

        if is_gifted and is_basic:
            result["result_code"] = "success"
            result["message"] = "Gifted Basic Bee detected."
            return result

        if is_mythic:
            result["result_code"] = "mythic"
            result["message"] = "Mythic bee detected."
            return result

        if is_gifted:
            result["result_code"] = "gifted_other"
            result["message"] = "Gifted non-Basic bee detected."
            return result

        if is_legendary:
            result["result_code"] = "legendary"
            result["message"] = "Legendary bee detected."
            return result

        if is_basic:
            result["result_code"] = "basic"
            result["message"] = "Basic Bee detected. Returning to Basic Eggs."
        else:
            result["message"] = "No Basic Bee detected. Returning to Basic Eggs."
        return result

    def _run(self, capture_delay_seconds):
        try:
            self._activate_roblox()
            self._update_status(state="positioning", message="Hover over the target bee slot in Roblox.")

            for remaining in range(capture_delay_seconds, 0, -1):
                self._raise_if_stopped()
                self._update_status(
                    message=f"Hover over the target bee slot. Capturing in {remaining}s."
                )
                time.sleep(1)

            bee_slot = pag.position()
            self._update_status(
                state="rolling",
                message="Bee slot captured. Starting rolls.",
                bee_slot_x=int(bee_slot[0]),
                bee_slot_y=int(bee_slot[1]),
            )

            self._toggle_inventory("open")
            time.sleep(0.3)
            mouse.moveTo(self._roblox_window.mx + 312, self._roblox_window.my + 200)
            mouse.click()
            time.sleep(0.1)

            next_item = "royaljelly"

            while not self._stop_event.is_set():
                self._raise_if_stopped()
                item_name = next_item
                readable_name = "Basic Eggs" if item_name == "basicegg" else "Royal Jellies"
                self._update_status(message=f"Looking for {readable_name}.")
                item_position = self._find_item_in_inventory(item_name)
                if not item_position:
                    raise RuntimeError(
                        "You ran out of Basic Eggs." if item_name == "basicegg" else "You ran out of Royal Jellies."
                    )

                self._update_status(message=f"Using {readable_name}.")
                self._drag_item_to_bee_slot(item_position, bee_slot)

                if not self._wait_for_yes_and_click():
                    raise RuntimeError("Could not find the confirmation prompt.")

                if item_name == "basicegg":
                    self._update_status(basic_eggs_used=self.get_status()["basic_eggs_used"] + 1)
                else:
                    self._update_status(royal_jellies_used=self.get_status()["royal_jellies_used"] + 1)
                self._update_status(rolls=self.get_status()["rolls"] + 1)

                if item_name == "basicegg":
                    time.sleep(0.75)
                    next_item = "royaljelly"
                    self._update_status(message="Basic Egg applied. Using Royal Jelly next.")
                    continue

                time.sleep(0.75)
                inspection = self._inspect_roll_result()
                self._update_status(
                    last_detected_text=inspection["raw_text"],
                    message=inspection["message"],
                )

                if inspection["result_code"] == "success":
                    if self._should_pause_for("success"):
                        if self._prompt_pause_decision(
                            "Auto Gifted Basic Bee Tool",
                            "Gifted Basic Bee detected.\nPress OK to keep it and stop, or Cancel to continue rerolling.",
                        ):
                            return
                        inspection["next_item"] = "basicegg"
                        inspection["message"] = "Gifted Basic skipped. Returning to Basic Eggs."
                        self._update_status(message=inspection["message"])
                        next_item = inspection["next_item"]
                        continue
                    self._update_status(
                        running=False,
                        state="finished",
                        result="success",
                        message=inspection["message"],
                    )
                    return

                if inspection["result_code"] == "mythic":
                    if self._should_pause_for("mythic"):
                        if self._prompt_pause_decision(
                            "Auto Gifted Basic Bee Tool",
                            "Mythic bee detected.\nPress OK to keep it and stop, or Cancel to continue rerolling.",
                        ):
                            return
                    inspection["next_item"] = "basicegg"
                    inspection["message"] = "Mythic skipped. Returning to Basic Eggs."
                    self._update_status(message=inspection["message"])

                if inspection["result_code"] == "legendary":
                    if self._should_pause_for("legendary"):
                        if self._prompt_pause_decision(
                            "Auto Gifted Basic Bee Tool",
                            "Legendary bee detected.\nPress OK to keep it and stop, or Cancel to continue rerolling.",
                        ):
                            return
                    inspection["next_item"] = "basicegg"
                    inspection["message"] = "Legendary skipped. Returning to Basic Eggs."
                    self._update_status(message=inspection["message"])

                if inspection["result_code"] == "gifted_other":
                    if self._should_pause_for("gifted_other"):
                        if self._prompt_pause_decision(
                            "Auto Gifted Basic Bee Tool",
                            "Gifted non-Basic bee detected.\nPress OK to keep it and stop, or Cancel to continue rerolling.",
                        ):
                            return
                    inspection["next_item"] = "basicegg"
                    inspection["message"] = "Gifted non-Basic skipped. Returning to Basic Eggs."
                    self._update_status(message=inspection["message"])

                next_item = inspection["next_item"]

            raise RuntimeError("Stopped by user.")
        except Exception as exc:
            result = "stopped" if self._stop_event.is_set() else "error"
            message = str(exc)
            if message == "Stopped by user.":
                result = "stopped"
            self._update_status(running=False, state="finished", result=result, message=message)
            self._emit_finished_once(result, message)
        finally:
            try:
                if self._inventory_open:
                    self._toggle_inventory("close")
            except Exception:
                pass
            try:
                mouse.mouseUp()
            except Exception:
                pass
            self._update_status(running=False)
            with self._lock:
                result = self._status.get("result", "")
                message = self._status.get("message", "Tool finished.")
                self._thread = None
            if result:
                self._emit_finished_once(result, message)
