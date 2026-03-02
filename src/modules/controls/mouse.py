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

def scroll(clicks, pause=False):
    if hasattr(pag, 'scroll'):
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

    try:
        import pyautogui as _pag
        _pag.scroll(clicks)
        return
    except Exception:
        pass

    # Final fallback: Windows native wheel scrolling
    try:
        if _platform.system() == "Windows":
            import ctypes
            import time

            WHEEL_DELTA = 120

            # How many "notches" to send per click
            WINDOWS_TICKS_PER_CLICK = 8  # tweak this (6–12 is usually good)

            for _ in range(abs(int(clicks)) * WINDOWS_TICKS_PER_CLICK):
                delta = WHEEL_DELTA if clicks > 0 else -WHEEL_DELTA
                ctypes.windll.user32.mouse_event(0x0800, 0, 0, delta, 0)
                time.sleep(0.001)  # tiny delay makes it more reliable

            return
    except Exception:
        pass

    raise RuntimeError("Unable to perform scroll: no suitable backend available")
    
def getPos():
    return pag.position()