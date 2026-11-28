import pyautogui as pag
import sys
from modules.screen import virtual_display
import time
from pynput.mouse import Button, Controller
from modules.controls.sleep import heartbeat

IS_WINDOWS = sys.platform == "win32"
if IS_WINDOWS:
    import ctypes
    from modules.misc.appManager import robloxWindowGone
    MOUSEEVENTF_MOVE = 0x0001
    MOUSEEVENTF_WHEEL = 0x0800
    MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP = 0x0002, 0x0004
else:
    import Quartz

pynputMouse = Controller()

#On Windows, pyautogui and pynput place the cursor without sending any mouse input, so Roblox never
#saw it move and clicks did nothing. A pixel there and back tells it where the cursor is.
def reportMove():
    if IS_WINDOWS:
        ctypes.windll.user32.mouse_event(MOUSEEVENTF_MOVE, 1, 0, 0, 0)
        time.sleep(0.02)
        ctypes.windll.user32.mouse_event(MOUSEEVENTF_MOVE, -1, 0, 0, 0)

#move the mouse instantly
def teleport(x,y):
    pag.moveTo(*virtual_display.to_global(x, y))
    reportMove()

def moveTo(x,y, delay = 0.1):
    x, y = virtual_display.to_global(x, y)
    pag.moveTo(x, y, delay)
    pynputMouse.position = (x, y)
    reportMove()

#pyautogui posts left button events without a click state, which makes WindowServer's gesture
#handling lag on macOS 27. Post them the way pyautogui does, plus click state 1.
def postLeftButton(eventType):
    heartbeat()
    if IS_WINDOWS:
        #like key presses, a click while Roblox has no window would land on whatever is in front. Releases still go through.
        if eventType == "down" and robloxWindowGone():
            return
        ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTDOWN if eventType == "down" else MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        time.sleep(pag.PAUSE)
        return
    event = Quartz.CGEventCreateMouseEvent(None, eventType, tuple(pag.position()), Quartz.kCGMouseButtonLeft)
    Quartz.CGEventSetIntegerValueField(event, Quartz.kCGMouseEventClickState, 1)
    Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)
    time.sleep(pag.PAUSE) #pyautogui pauses after every call

#send a single press/release; posting through both pynput and pyautogui doubled every event
def mouseDown():
    if virtual_display.active(): virtual_display.state(require_window=True)
    postLeftButton("down" if IS_WINDOWS else Quartz.kCGEventLeftMouseDown)

def mouseUp():
    postLeftButton("up" if IS_WINDOWS else Quartz.kCGEventLeftMouseUp)

def moveBy(x = 0,y = 0, pause=True):
    if virtual_display.active(): virtual_display.state(require_window=True)
    pag.move(x, y, _pause=pause)  
    reportMove()

def rightDragBy(x, y):
    """Send relative camera motion while the caller holds the right button."""
    if virtual_display.active(): virtual_display.state(require_window=True)
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
    if IS_WINDOWS:
        if robloxWindowGone():
            return
        #pyautogui passes the click count as the raw wheel delta, and one notch is 120. 200 per click is what
        #worked on the old windows branch; tune on real hardware
        ctypes.windll.user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, int(clicks * 200), 0)
        if pause:
            time.sleep(pag.PAUSE)
        return
    pag.scroll(clicks, _pause = pause)

def getPos():
    return virtual_display.to_local(*pag.position())

def dragTo(x, y, duration=0.6, button="left"):
    x, y = virtual_display.to_global(x, y)
    pag.dragTo(x, y, duration, button=button)
