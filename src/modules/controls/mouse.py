import platform as _platform
if _platform.system() == "Windows":
    try:
        import pydirectinput as pag
    except ModuleNotFoundError:
        import pyautogui as pag
else:
    import pyautogui as pag
import time
from pynput.mouse import Button, Controller

pynputMouse = Controller()
#move the mouse instantly
def teleport(x,y):
    pag.moveTo(int(x),int(y))

def moveTo(x,y, delay = 0.1):
    pag.moveTo(int(x),int(y), delay)
    pynputMouse.position = (int(x), int(y))

def mouseDown():
    pynputMouse.press(Button.left)
    pag.mouseDown()

def mouseUp():
    pynputMouse.release(Button.left)
    pag.mouseUp()

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
    # Use pyautogui's built-in scroll. Try passing the _pause kwarg first,
    # fall back to the signature without it if necessary.
    import pyautogui as pag
    try:
        pag.scroll(clicks, _pause=pause)
        return
    except TypeError:
        try:
            pag.scroll(clicks)
            return
        except Exception:
            pass
    except Exception:
        pass

    raise RuntimeError("Unable to perform scroll: pyautogui backend not available")

def getPos():
    return pag.position()