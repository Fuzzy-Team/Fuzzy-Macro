import pyautogui as pag
import platform
import time
from pynput.mouse import Button, Controller

if platform.system() == "Darwin":
    import Quartz

pynputMouse = Controller()


def _use_quartz_mouse():
    return platform.system() == "Darwin"


def _quartz_mouse_position():
    event = Quartz.CGEventCreate(None)
    point = Quartz.CGEventGetLocation(event)
    return int(point.x), int(point.y)


def _quartz_post_mouse_event(event_type, x=None, y=None):
    if x is None or y is None:
        x, y = _quartz_mouse_position()
    mouse_event = Quartz.CGEventCreateMouseEvent(
        None,
        event_type,
        (int(x), int(y)),
        Quartz.kCGMouseButtonLeft,
    )
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, mouse_event)


#move the mouse instantly
def teleport(x,y):
    if _use_quartz_mouse():
        _quartz_post_mouse_event(Quartz.kCGEventMouseMoved, x, y)
        return
    pag.moveTo(int(x),int(y))

def moveTo(x,y, delay = 0.1):
    if _use_quartz_mouse():
        _quartz_post_mouse_event(Quartz.kCGEventMouseMoved, x, y)
        if delay:
            time.sleep(delay)
        return
    pag.moveTo(int(x),int(y), delay)
    pynputMouse.position = (int(x), int(y))

def mouseDown():
    if _use_quartz_mouse():
        _quartz_post_mouse_event(Quartz.kCGEventLeftMouseDown)
        return
    pynputMouse.press(Button.left)
    pag.mouseDown()

def mouseUp():
    if _use_quartz_mouse():
        _quartz_post_mouse_event(Quartz.kCGEventLeftMouseUp)
        return
    pynputMouse.release(Button.left)
    pag.mouseUp()

def moveBy(x = 0,y = 0, pause=True):
    if _use_quartz_mouse():
        current_x, current_y = _quartz_mouse_position()
        _quartz_post_mouse_event(Quartz.kCGEventMouseMoved, current_x + x, current_y + y)
        if pause:
            time.sleep(pag.PAUSE)
        return
    pag.move(x, y, _pause=pause)  

def click():
    mouseDown()
    time.sleep(0.04)
    mouseUp()

def fastClick():
    if _use_quartz_mouse():
        mouseDown()
        mouseUp()
        return
    pynputMouse.press(Button.left)
    pynputMouse.release(Button.left)

def scroll(clicks, pause = False):
    pag.scroll(clicks, _pause = pause)

def getPos():
    if _use_quartz_mouse():
        return _quartz_mouse_position()
    return pag.position()
