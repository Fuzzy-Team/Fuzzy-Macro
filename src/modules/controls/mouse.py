import pyautogui as pag
import sys
import time
from pynput.mouse import Button, Controller

IS_WINDOWS = sys.platform == "win32"
if IS_WINDOWS:
    import ctypes
    MOUSEEVENTF_MOVE = 0x0001
    MOUSEEVENTF_WHEEL = 0x0800
    MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP = 0x0002, 0x0004
    MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP = 0x0008, 0x0010
else:
    import Quartz

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
    if IS_WINDOWS:
        ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTDOWN if eventType == "down" else MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        time.sleep(pag.PAUSE)
        return
    event = Quartz.CGEventCreateMouseEvent(None, eventType, tuple(pag.position()), Quartz.kCGMouseButtonLeft)
    Quartz.CGEventSetIntegerValueField(event, Quartz.kCGMouseEventClickState, 1)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)
    time.sleep(pag.PAUSE) #pyautogui pauses after every call

#send a single press/release; posting through both pynput and pyautogui doubled every event
def mouseDown():
    postLeftButton("down" if IS_WINDOWS else Quartz.kCGEventLeftMouseDown)

def mouseUp():
    postLeftButton("up" if IS_WINDOWS else Quartz.kCGEventLeftMouseUp)

def moveBy(x = 0,y = 0, pause=True):
    pag.move(x, y, _pause=pause)  

def rightDragBy(x, y):
    """Send relative camera motion while the caller holds the right button."""
    if IS_WINDOWS:
        #Roblox reads relative motion while the right button is held, so absolute moves don't turn the camera
        ctypes.windll.user32.mouse_event(MOUSEEVENTF_MOVE, int(x), int(y), 0, 0)
        return
    currentX, currentY = pag.position()
    event = Quartz.CGEventCreateMouseEvent(
        None, Quartz.kCGEventRightMouseDragged,
        (currentX + x, currentY + y), Quartz.kCGMouseButtonRight,
    )
    Quartz.CGEventSetIntegerValueField(event, Quartz.kCGMouseEventDeltaX, int(x))
    Quartz.CGEventSetIntegerValueField(event, Quartz.kCGMouseEventDeltaY, int(y))
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)


def click():
    mouseDown()
    time.sleep(0.04)
    mouseUp()

def fastClick():
    pynputMouse.press(Button.left)
    pynputMouse.release(Button.left)

def scroll(clicks, pause = False):
    if IS_WINDOWS:
        #pyautogui passes the click count as the raw wheel delta, and one notch is 120. 200 per click is what
        #worked on the old windows branch; tune on real hardware
        ctypes.windll.user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, int(clicks * 200), 0)
        return
    pag.scroll(clicks, _pause = pause)

def getPos():
    return pag.position()