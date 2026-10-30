import pyautogui as pag
import Quartz
import time
from pynput.mouse import Button, Controller

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

def click():
    mouseDown()
    time.sleep(0.04)
    mouseUp()

def fastClick():
    pynputMouse.press(Button.left)
    pynputMouse.release(Button.left)

def scroll(clicks, pause = False):
    pag.scroll(clicks, _pause = pause)

def getPos():
    return pag.position()