import pyautogui as pag
import Quartz
import time
from pynput.mouse import Button, Controller
from modules.controls.sleep import heartbeat

pynputMouse = Controller()
#move the mouse instantly
def teleport(x,y):
    pag.moveTo(int(x),int(y))

def moveTo(x,y, delay = 0.1):
    pag.moveTo(int(x),int(y), delay)
    pynputMouse.position = (int(x), int(y))

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
    postLeftButton(Quartz.kCGEventLeftMouseDown)

def mouseUp():
    postLeftButton(Quartz.kCGEventLeftMouseUp)

def moveBy(x = 0,y = 0, pause=True):
    pag.move(x, y, _pause=pause)  

def rightDragBy(x, y):
    """Send relative camera motion while the caller holds the right button."""
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
    try:
        pynputMouse.press(Button.left)
    finally:
        pynputMouse.release(Button.left)

def scroll(clicks, pause = False):
    pag.scroll(clicks, _pause = pause)

def getPos():
    return pag.position()