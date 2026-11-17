import pyautogui as pag
import Quartz
from modules.screen import virtual_display
import time
from pynput.mouse import Button, Controller
from modules.controls.sleep import heartbeat

pynputMouse = Controller()
#move the mouse instantly
def teleport(x,y):
    pag.moveTo(*virtual_display.to_global(x, y))

def moveTo(x,y, delay = 0.1):
    x, y = virtual_display.to_global(x, y)
    pag.moveTo(x, y, delay)
    pynputMouse.position = (x, y)

#pyautogui posts left button events without a click state, which makes WindowServer's gesture
#handling lag on macOS 27. Post them the way pyautogui does, plus click state 1.
def postLeftButton(eventType):
    heartbeat()
    event = Quartz.CGEventCreateMouseEvent(None, eventType, tuple(pag.position()), Quartz.kCGMouseButtonLeft)
    Quartz.CGEventSetIntegerValueField(event, Quartz.kCGMouseEventClickState, 1)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)
    time.sleep(pag.PAUSE) #pyautogui pauses after every call

#send a single press/release; posting through both pynput and pyautogui doubled every event
def mouseDown():
    if virtual_display.active(): virtual_display.state(require_window=True)
    postLeftButton(Quartz.kCGEventLeftMouseDown)

def mouseUp():
    postLeftButton(Quartz.kCGEventLeftMouseUp)

def moveBy(x = 0,y = 0, pause=True):
    if virtual_display.active(): virtual_display.state(require_window=True)
    pag.move(x, y, _pause=pause)  

def rightDragBy(x, y):
    """Send relative camera motion while the caller holds the right button."""
    if virtual_display.active(): virtual_display.state(require_window=True)
    currentX, currentY = pag.position()
    event = Quartz.CGEventCreateMouseEvent(
        None, Quartz.kCGEventRightMouseDragged,
        (currentX + x, currentY + y), Quartz.kCGMouseButtonRight,
    )
    Quartz.CGEventSetIntegerValueField(event, Quartz.kCGMouseEventDeltaX, int(x))
    Quartz.CGEventSetIntegerValueField(event, Quartz.kCGMouseEventDeltaY, int(y))
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)


def click():
    try:
        mouseDown()
        time.sleep(0.04)
    finally:
        mouseUp()

def fastClick():
    if virtual_display.active(): virtual_display.state(require_window=True)
    try:
        pynputMouse.press(Button.left)
    finally:
        pynputMouse.release(Button.left)

def scroll(clicks, pause = False):
    if virtual_display.active(): virtual_display.state(require_window=True)
    pag.scroll(clicks, _pause = pause)

def getPos():
    return virtual_display.to_local(*pag.position())

def dragTo(x, y, duration=0.6, button="left"):
    x, y = virtual_display.to_global(x, y)
    pag.dragTo(x, y, duration, button=button)
