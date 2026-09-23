#custom sleep function with pause support
import time

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



def raise_if_interrupted():
    action = get_interrupt_action()
    if action != INTERRUPT_NONE:
        raise InterruptRequested(action)

def is_paused():
    """Check if macro is currently paused (state 6)"""
    if _run_state is None:
        return False
    return _run_state.value == 6

def is_stopped():
    """Check if macro stop was requested (state 0)"""
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


class _PauseAwareTimeModule:
    """The time module, but sleep() respects pause and interrupt state."""

    def __init__(self, time_module):
        self._time = time_module

    def sleep(self, duration):
        return pauseable_sleep(duration)

    def __getattr__(self, name):
        return getattr(self._time, name)


pause_aware_time = _PauseAwareTimeModule(time)
