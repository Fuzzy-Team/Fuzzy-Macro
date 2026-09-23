import threading
import time
from collections import defaultdict
from pynput import keyboard
import modules.controls.mouse as mouse
from modules.controls.keyboard import keyboard as keyboardModule
import modules.misc.settingsManager as settingsManager
from modules.misc import messageBox

DEBOUNCE_SECONDS = 0.3
STUCK_KEY_RESET_SECONDS = 5.0
SETTINGS_CACHE_SECONDS = 1.0
RECORDING_CACHE_SECONDS = 0.5

# keybind inputs in the GUI that can be recording a new keybind
RECORDABLE_KEYBINDS = ("start", "pause", "stop", "hotbar_buff_start", "autoclicker", "auto_gifted_basic_bee_start")
# (setting, default keybind, gui function, display name) for tools startable from a hotkey
TOOL_KEYBINDS = (
    ("hotbar_buff_start_keybind", "F4", "startHotbarBuffTool", "Hotbar Buff"),
    ("autoclicker_keybind", "", "startAutoClickerTool", "Auto Clicker"),
    ("auto_gifted_basic_bee_start_keybind", "", "startAutoGiftedBasicBeeTool", "Auto Gifted Basic Bee"),
)

MODIFIER_KEYS = ["Ctrl", "Alt", "Shift", "Cmd"]
IGNORED_KEYS = {"Fn"}
KEY_ALIASES = {
    "ctrl_l": "Ctrl", "ctrl_r": "Ctrl", "control": "Ctrl", "ctrl": "Ctrl",
    "alt_l": "Alt", "alt_r": "Alt", "option": "Alt", "alt": "Alt",
    "shift_l": "Shift", "shift_r": "Shift", "shift": "Shift",
    "cmd_l": "Cmd", "cmd_r": "Cmd", "cmd": "Cmd", "meta": "Cmd", "command": "Cmd",
    "space": "Space", "spacebar": "Space",
    "enter": "Enter", "return": "Enter",
    "tab": "Tab",
    "backspace": "Backspace",
    "delete": "Delete", "del": "Delete",
    "esc": "Escape", "escape": "Escape",
    "caps_lock": "CapsLock", "capslock": "CapsLock",
    "left": "ArrowLeft", "arrowleft": "ArrowLeft",
    "right": "ArrowRight", "arrowright": "ArrowRight",
    "up": "ArrowUp", "arrowup": "ArrowUp",
    "down": "ArrowDown", "arrowdown": "ArrowDown",
    "home": "Home",
    "end": "End",
    "page_up": "PageUp", "pageup": "PageUp",
    "page_down": "PageDown", "pagedown": "PageDown",
    "insert": "Insert",
    "fn": "Fn",
    # characters macOS produces when Option is held
    "¡": "1", "™": "2", "£": "3", "¢": "4", "∞": "5",
    "§": "6", "¶": "7", "•": "8", "ª": "9", "º": "0",
    "å": "A", "∫": "B", "ç": "C", "∂": "D", "ƒ": "F",
    "©": "G", "˙": "H", "∆": "J", "˚": "K", "¬": "L",
    "µ": "M", "ø": "O", "π": "P", "œ": "Q", "®": "R",
    "ß": "S", "†": "T", "√": "V", "∑": "W", "≈": "X",
    "¥": "Y", "Ω": "Z", "ω": "Z",
}


def normalize_key_name(key_name):
    """Convert a key to the canonical name the UI saves in keybind settings."""
    key_name = str(key_name or "").strip()
    if not key_name:
        return ""
    if key_name.startswith("Key."):
        key_name = key_name[4:]
    if key_name.startswith("'") and key_name.endswith("'") and len(key_name) >= 2:
        key_name = key_name[1:-1]

    alias = KEY_ALIASES.get(key_name.lower())
    if alias:
        return alias
    if key_name.lower().startswith("f") and key_name[1:].isdigit():
        return key_name.upper()
    if len(key_name) == 1:
        return key_name.upper()
    return key_name


def parse_keybind(keybind):
    keys = []
    for raw_key in str(keybind or "").split("+"):
        key_name = normalize_key_name(raw_key)
        if key_name and key_name not in IGNORED_KEYS and key_name not in keys:
            keys.append(key_name)
    ordered = [key for key in MODIFIER_KEYS if key in keys]
    ordered.extend(sorted(key for key in keys if key not in MODIFIER_KEYS))
    return tuple(ordered)


def release_inputs():
    try:
        keyboardModule.releaseMovement()
        mouse.mouseUp()
    except Exception:
        pass


def watch_for_hotkeys(run):
    """Return a function that starts the hotkey listener. Call it on the main thread."""
    pressed_keys = set()
    key_lock = threading.Lock()
    last_trigger_time = defaultdict(float)
    last_stuck_key_reset = 0
    settings_cache = {}
    last_settings_load = 0
    recording = False
    last_recording_check = 0

    def get_settings():
        nonlocal settings_cache, last_settings_load
        if time.time() - last_settings_load > SETTINGS_CACHE_SECONDS:
            settings_cache = settingsManager.loadAllSettings()
            last_settings_load = time.time()
        return settings_cache

    def is_recording_keybind():
        nonlocal recording, last_recording_check
        if time.time() - last_recording_check > RECORDING_CACHE_SECONDS:
            try:
                import eel
                recording = any(
                    eel.getElementProperty(f"{name}_keybind", "dataset.recording")() == "true"
                    for name in RECORDABLE_KEYBINDS
                )
                last_recording_check = time.time()
            except Exception:
                recording = False
        return recording

    def keys_match_keybind(keybind):
        expected_keys = parse_keybind(keybind)
        active_keys = {key for key in pressed_keys if key not in IGNORED_KEYS}
        return bool(expected_keys) and active_keys == set(expected_keys)

    def is_stop_keybind_held():
        settings = get_settings()
        expected_keys = parse_keybind(settings.get("stop_keybind", "F3")) if settings else ()
        return bool(expected_keys) and all(key in pressed_keys for key in expected_keys)

    def debounced(action):
        """True if `action` fired too recently; otherwise records this trigger."""
        now = time.time()
        if now - last_trigger_time[action] < DEBOUNCE_SECONDS:
            return True
        last_trigger_time[action] = now
        return False

    def gui_call(name, *args):
        # the GUI may not be ready yet; hotkeys must keep working without it
        try:
            import gui
            return getattr(gui, name)(*args)
        except Exception:
            return None

    def set_run_state(value, gui_state):
        run.value = value
        gui_call("setRunState", gui_state)
        gui_call("toggleStartStop")

    def on_press(key):
        nonlocal last_stuck_key_reset
        with key_lock:
            try:
                if time.time() - last_stuck_key_reset > STUCK_KEY_RESET_SECONDS:
                    pressed_keys.clear()
                    last_stuck_key_reset = time.time()

                settings = get_settings()
                pressed_keys.add(normalize_key_name(getattr(key, "char", None) or str(key)))

                if is_recording_keybind():
                    return

                # stop works any time the stop keybind is held, even alongside other keys
                if is_stop_keybind_held():
                    gui_call("stopAllTools")
                    if run.value != 0:
                        release_inputs()
                        set_run_state(0, 0)

                if keys_match_keybind(settings.get("start_keybind", "F1")):
                    if run.value != 3:  # only start from fully stopped
                        return
                    if gui_call("isAnyToolRunning"):
                        messageBox.msgBox(title="Tool Running", text="Stop the running tool before starting the macro.")
                        return
                    if debounced("start"):
                        return
                    set_run_state(1, 2)  # show running immediately
                    return

                for setting, default, start_tool, title in TOOL_KEYBINDS:
                    if keys_match_keybind(settings.get(setting, default)):
                        if run.value != 3 or debounced(setting):
                            return
                        result = gui_call(start_tool)
                        if result is not None and not result.get("ok") and not gui_call("isAnyToolRunning"):
                            messageBox.msgBox(title=title, text=result.get("message", f"Could not start {title}."))
                        return

                if keys_match_keybind(settings.get("pause_keybind", "F2")):
                    if debounced("pause"):
                        return
                    if run.value == 2:
                        release_inputs()
                        set_run_state(6, 6)
                    elif run.value == 6:
                        run.value = 2
            except Exception as e:
                print(f"Error in on_press: {e}")

    def on_release(key):
        with key_lock:
            pressed_keys.discard(normalize_key_name(getattr(key, "char", None) or str(key)))

    def start_keyboard_listener():
        # pynput must start on the main thread on macOS
        if threading.current_thread() is not threading.main_thread():
            print("Warning: Keyboard listener should be started on main thread on macOS")
        try:
            listener = keyboard.Listener(on_press=on_press, on_release=on_release)
            listener.start()
            return listener
        except Exception as e:
            print(f"Failed to start keyboard listener: {e}")

        def retry():
            time.sleep(1)
            try:
                keyboard.Listener(on_press=on_press, on_release=on_release).start()
                print("Keyboard listener restarted successfully")
            except Exception as e:
                print(f"Failed to restart keyboard listener: {e}")

        threading.Thread(target=retry, daemon=True).start()

    return start_keyboard_listener
