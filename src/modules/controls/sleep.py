#custom sleep function with pause support
import faulthandler
import time
import threading

# Module-level reference to the run state (multiprocessing.Value)
_run_state = None
_interrupt_action = None
_resume_callback = None

INTERRUPT_NONE = 0
INTERRUPT_SKIP = 1
INTERRUPT_RESET = 2
INTERRUPT_AFB_REROLL = 3
INTERRUPT_COLLECT_PLANTER = 4
INTERRUPT_STICKER_SPROUT = 5


class InterruptRequested(Exception):
    def __init__(self, action):
        self.action = action
        super().__init__(f"Interrupt requested: {action}")

def set_run_state(run):
    """Set the shared run state for pause checking"""
    global _run_state
    _run_state = run


def set_interrupt_action(interrupt_action):
    """Set the shared interrupt action for task interruption checks."""
    global _interrupt_action
    _interrupt_action = interrupt_action


def set_resume_callback(callback):
    """Set a callback to run after a paused macro resumes."""
    global _resume_callback
    _resume_callback = callback


def get_interrupt_action():
    if _interrupt_action is None:
        return INTERRUPT_NONE
    try:
        return int(_interrupt_action.value)
    except Exception:
        return INTERRUPT_NONE


def clear_interrupt_action():
    if _interrupt_action is None:
        return
    try:
        _interrupt_action.value = INTERRUPT_NONE
    except Exception:
        pass


def raise_if_interrupted():
    action = get_interrupt_action()
    if action != INTERRUPT_NONE:
        raise InterruptRequested(action)

# A screen capture, text read, window query or input event can hang inside macOS and never return.
# The macro's main thread checks pause/stop, takes screenshots or clicks at least every few seconds
# while it is healthy, and each of those calls heartbeat(). If HANG_SECS pass without one,
# faulthandler writes every thread's stack to HANG_FILE and exits with code 1, and the main app
# reports the crash and restarts the macro.
HANG_SECS = 180
HANG_FILE = "hang.txt"
_hangFile = None
_hangThread = None
_lastBeat = 0.0

def start_hang_watchdog(path):
    """Call once from the macro process's main thread. Only that thread's heartbeats count."""
    global _hangFile, _hangThread
    _hangFile = open(path, "w")
    _hangThread = threading.get_ident()

def heartbeat(anyThread=False):
    """Push the hang deadline back. Re-arms the timer at most once a second."""
    global _lastBeat
    if _hangFile is None or (not anyThread and threading.get_ident() != _hangThread):
        return
    now = time.monotonic()
    if now - _lastBeat >= 1:
        _lastBeat = now
        faulthandler.dump_traceback_later(HANG_SECS, exit=True, file=_hangFile)

def pause_hang_watchdog():
    """Turn the timer off while the main thread waits on something with no time limit, such as a
    dialog or a model download. The next heartbeat turns it back on."""
    global _lastBeat
    if _hangFile is None or threading.get_ident() != _hangThread:
        return
    faulthandler.cancel_dump_traceback_later()
    _lastBeat = 0.0

def is_paused():
    """Check if macro is currently paused (state 6)"""
    paused = _run_state is not None and _run_state.value == 6
    # while paused every thread waits on purpose, even a main thread joining a worker,
    # so any thread's check keeps the macro alive
    heartbeat(anyThread=paused)
    return paused

def is_stopped():
    """Check if macro stop was requested (state 0)"""
    heartbeat()
    if _run_state is None:
        return False
    return _run_state.value == 0

def wait_while_paused():
    """Wait while the macro is paused, return True if stop was requested"""
    was_paused = False
    while is_paused():
        was_paused = True
        time.sleep(0.1)
    if was_paused and not is_stopped() and _resume_callback is not None:
        try:
            _resume_callback()
        except Exception:
            pass
    return is_stopped()

def sleep(duration, get_now=time.perf_counter):
    """Pause-aware sleep function"""
    if duration <= 0:
        return

    raise_if_interrupted()

    # Check for pause before sleeping
    if wait_while_paused():
        return  # Stop was requested

    now = get_now()
    end = now + duration
    while now < end:
        raise_if_interrupted()
        if is_stopped():
            return
        if is_paused() and wait_while_paused():
            return

        remaining = end - now
        chunk = min(0.05, remaining)
        if chunk > 0:
            time.sleep(chunk)
        now = get_now()

def high_precision_sleep(duration):
    """Pause-aware high precision sleep"""
    raise_if_interrupted()

    # Check for pause before sleeping
    if wait_while_paused():
        return  # Stop was requested
    
    start_time = time.perf_counter()
    while True:
        elapsed_time = time.perf_counter() - start_time
        remaining_time = duration - elapsed_time
        if remaining_time <= 0:
            break
        raise_if_interrupted()
        if remaining_time > 0.02:  # Sleep for 5ms if remaining time is greater
            time.sleep(max(remaining_time/2, 0.0001))  # Sleep for the remaining time or minimum sleep interval
        else:
            pass
        # Check for pause during sleep
        if is_paused():
            if wait_while_paused():
                return  # Stop was requested

def pauseable_sleep(duration):
    """A time.sleep replacement that respects pause state"""
    if duration <= 0:
        return

    raise_if_interrupted()

    # Check for pause before sleeping
    if wait_while_paused():
        return  # Stop was requested

    # Sleep in short chunks so pause interrupts quickly
    start = time.perf_counter()
    while time.perf_counter() - start < duration:
        raise_if_interrupted()
        if is_stopped():
            return
        if is_paused() and wait_while_paused():
            return

        # Sleep in small chunks
        remaining = duration - (time.perf_counter() - start)
        chunk = min(0.05, remaining)
        if chunk > 0:
            time.sleep(chunk)
