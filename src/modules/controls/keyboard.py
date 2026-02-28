import sys
import os
import pyautogui as pag
import time
import platform
from modules.submacros.hasteCompensation import HasteCompensationRevamped
import threading
from collections import deque


_IS_WINDOWS = platform.system() == "Windows"

if _IS_WINDOWS:
    import ctypes

    _KEYEVENTF_KEYUP = 0x0002
    _KEYEVENTF_SCANCODE = 0x0008
    _KEYEVENTF_EXTENDEDKEY = 0x0001
    _INPUT_KEYBOARD = 1

    class _KEYBDINPUT(ctypes.Structure):
        _fields_ = [
            ("wVk", ctypes.c_ushort),
            ("wScan", ctypes.c_ushort),
            ("dwFlags", ctypes.c_uint),
            ("time", ctypes.c_uint),
            ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
        ]

    class _INPUT_UNION(ctypes.Union):
        _fields_ = [("ki", _KEYBDINPUT)]

    class _INPUT(ctypes.Structure):
        _fields_ = [("type", ctypes.c_uint), ("union", _INPUT_UNION)]

    _SCANCODE_MAP = {
        "esc": (0x01, False),
        "1": (0x02, False), "2": (0x03, False), "3": (0x04, False), "4": (0x05, False), "5": (0x06, False),
        "6": (0x07, False), "7": (0x08, False), "8": (0x09, False), "9": (0x0A, False), "0": (0x0B, False),
        "-": (0x0C, False), "=": (0x0D, False),
        "backspace": (0x0E, False),
        "tab": (0x0F, False),
        "q": (0x10, False), "w": (0x11, False), "e": (0x12, False), "r": (0x13, False), "t": (0x14, False),
        "y": (0x15, False), "u": (0x16, False), "i": (0x17, False), "o": (0x18, False), "p": (0x19, False),
        "[": (0x1A, False), "]": (0x1B, False),
        "enter": (0x1C, False),
        "ctrl": (0x1D, False),
        "a": (0x1E, False), "s": (0x1F, False), "d": (0x20, False), "f": (0x21, False), "g": (0x22, False),
        "h": (0x23, False), "j": (0x24, False), "k": (0x25, False), "l": (0x26, False),
        ";": (0x27, False), "'": (0x28, False), "`": (0x29, False),
        "shift": (0x2A, False),
        "\\": (0x2B, False),
        "z": (0x2C, False), "x": (0x2D, False), "c": (0x2E, False), "v": (0x2F, False), "b": (0x30, False),
        "n": (0x31, False), "m": (0x32, False),
        ",": (0x33, False), ".": (0x34, False), "/": (0x35, False),
        "alt": (0x38, False),
        "space": (0x39, False),
        "capslock": (0x3A, False),
        "f1": (0x3B, False), "f2": (0x3C, False), "f3": (0x3D, False), "f4": (0x3E, False),
        "f5": (0x3F, False), "f6": (0x40, False), "f7": (0x41, False), "f8": (0x42, False),
        "f9": (0x43, False), "f10": (0x44, False), "f11": (0x57, False), "f12": (0x58, False),
        "pageup": (0x49, True),
        "pagedown": (0x51, True),
        "home": (0x47, True),
        "end": (0x4F, True),
        "insert": (0x52, True),
        "delete": (0x53, True),
        "up": (0x48, True),
        "down": (0x50, True),
        "left": (0x4B, True),
        "right": (0x4D, True),
        "win": (0x5B, True),
    }

    _WINDOWS_KEY_ALIASES = {
        "escape": "esc",
        "return": "enter",
        "pgup": "pageup",
        "pgdn": "pagedown",
        "option": "alt",
        "command": "win",
        "cmd": "win",
        "windows": "win",
    }

    def _normalize_windows_key(key):
        if not isinstance(key, str):
            key = str(key)
        key = key.strip().lower()
        if key.startswith("key."):
            key = key.split(".", 1)[1]
        return _WINDOWS_KEY_ALIASES.get(key, key)

    def _send_windows_scancode(key, key_up=False):
        normalized = _normalize_windows_key(key)
        code = _SCANCODE_MAP.get(normalized)
        if code is None:
            return False

        scancode, is_extended = code
        flags = _KEYEVENTF_SCANCODE
        if is_extended:
            flags |= _KEYEVENTF_EXTENDEDKEY
        if key_up:
            flags |= _KEYEVENTF_KEYUP

        extra = ctypes.c_ulong(0)
        ki = _KEYBDINPUT(0, scancode, flags, 0, ctypes.pointer(extra))
        inp = _INPUT(_INPUT_KEYBOARD, _INPUT_UNION(ki=ki))
        ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))
        return True


class keyboard:
    def __init__(self, walkspeed, enableHasteCompensation, hasteCompensation: HasteCompensationRevamped):
        self.ws = walkspeed
        self.enableHasteCompensation = enableHasteCompensation
        self.hasteCompensation = hasteCompensation

        self.detection_interval = 0.01
        
        #drift compensation
        self.accumulated_error = 0
        self.error_correction_factor = 0.1
    
    
    def predictiveTimeWait(self, duration):
        base_speed = 28
        target_distance = base_speed * duration
        corrected_target = target_distance - self.accumulated_error
        
        traveled_distance = 0
        start_time = time.perf_counter()
        last_time = start_time
        
        #safety distance, just in case of infinite drifting
        max_time = duration * 1.2

        #sleep_interval = 0.01  # Or even 0.02 would probably work fine
        
        while traveled_distance < corrected_target:
            current_time = time.perf_counter()
            elapsed = current_time - start_time
            
            # Safety timeout
            if elapsed >= max_time:
                break

            speed = self.getMoveSpeed()
            
            delta_t = current_time - last_time
            distance_increment = speed * delta_t
            traveled_distance += distance_increment
            
            last_time = current_time
            #time.sleep(sleep_interval)
        
        #calculate drift and update accumulated error
        distance_error = traveled_distance - target_distance
        
        #self.accumulated_error = (self.accumulated_error * 0.9 + distance_error * self.error_correction_factor)
    
    
    def walk(self, k, t, applyHaste=True, method='predictive'):
        if applyHaste and self.enableHasteCompensation:
            keyboard.keyDown(k, False)
            
            if method == 'predictive':
                self.predictiveTimeWait(t)
            else:
                self.timeWait(t)  # Original method
                
            keyboard.keyUp(k, False)
        else:
            self.press(k, t * 28 / self.ws)
    
    def multiWalk(self, keys, t, applyHaste=True, method='predictive'):
        for k in keys:
            keyboard.keyDown(k, False)
        
        if applyHaste and self.enableHasteCompensation:
            if method == 'predictive':
                self.predictiveTimeWait(t)
            else:
                self.timeWait(t)
        else:
            time.sleep(t * 28 / self.ws)
        
        for k in keys:
            keyboard.keyUp(k, False)

    @staticmethod
    #call the press function of the pag library
    def pagPress(k):
        keyboard.keyDown(k, False)
        time.sleep(0.02)
        keyboard.keyUp(k, False)
    @staticmethod
    def keyDown(k, pause = True):
        #for some reason, the function key is sometimes held down, causing it to open the dock or enable dictation
        if not _IS_WINDOWS:
            try:
                keyboard.keyUp('fn', False)
            except Exception:
                pass
        if _IS_WINDOWS and _send_windows_scancode(k, key_up=False):
            return
        pag.keyDown(k, _pause = pause)

    @staticmethod
    def keyUp(k, pause = True):
        if _IS_WINDOWS and _send_windows_scancode(k, key_up=True):
            return
        pag.keyUp(k, _pause = pause)

    #pyautogui without the pause
    def press(self,key, delay = 0.02):
        keyboard.keyDown(key, False)
        time.sleep(delay)
        keyboard.keyUp(key, False)

    def write(self, text, interval = 0.1):
        pag.typewrite(text, interval)
    #pyautogui with the pause
    def slowPress(self,k):
        pag.keyDown(k)
        time.sleep(0.08)
        pag.keyUp(k)

    def getMoveSpeed(self):
        movespeed = self.hasteCompensation.getHaste()
        return movespeed
    
    def timeWaitNoHasteCompensation(self, duration):
        time.sleep(duration* 28 / self.ws)

    def timeWait(self, duration):

        baseSpeed = 28
        target_distance = baseSpeed * duration  # Total distance the player should travel
        traveledDistance = 0
        maxTime = baseSpeed/24*duration

        st = time.perf_counter()
        prevTime = st
        prevSpeed = self.getMoveSpeed()

        while traveledDistance < target_distance and prevTime-st < maxTime:
            currentTime = time.perf_counter()
            speed = self.getMoveSpeed()

            delta_t = currentTime - prevTime

            # Apply trapezoidal integration to calculate traveled distance
            traveledDistance += ((prevSpeed + speed) / 2) * delta_t

            # Update previous values
            prevTime = currentTime
            prevSpeed = speed

        elapsed_time = time.perf_counter() - st
        #print(f"current speed: {speed}, original time: {duration}, actual travel time: {elapsed_time}")

    #recreate natro's walk function
    def tileWait(self, n, hasteCap=0):
        #self.getMoveSpeed takes too fast to run
        def a():
            st = time.perf_counter()
            a = self.hasteCompensation.getHaste()
            et = time.perf_counter()
            return st, et, a
        freq = 1  # Simulated frequency constant
        d = freq / 8
        l = n * freq * 4

        s, f, v = a()
        d += v * (f - s) 

        st = time.time()
        while d < l:
            prev_v = v
            s, f, v = a()
            d += ((prev_v + v) / 2) * (f - s) 
        
    
    def tileWalk(self, key, tiles, applyHaste = True):
        if applyHaste:
            self.keyDown(key, False)
            self.tileWait(tiles)
            self.keyUp(key, False)
        else:
            self.press(key,(tiles/8.3)*28/self.haste.value)

    #release all movement keys (wasd, space)
    @staticmethod
    def releaseMovement():
        keys = ["w","a","s","d","space"]
        for k in keys:
            keyboard.keyUp(k, False)
