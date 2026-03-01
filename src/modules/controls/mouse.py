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
    # pydirectinput may not implement `scroll`. Try the current backend first,
    # then fall back to pyautogui, and finally to a Windows API call.
    if hasattr(pag, 'scroll'):
        try:
            pag.scroll(clicks, _pause = pause)
            return
        except TypeError:
            # some implementations don't accept the _pause kwarg
            try:
                pag.scroll(clicks)
                return
            except Exception:
                pass
        except Exception:
            pass

    # fallback to pyautogui if available
    try:
        import pyautogui as _pag
        try:
            _pag.scroll(clicks)
            return
        except Exception:
            pass
    except Exception:
        pass

    # final fallback: on Windows use native mouse_event for wheel
    try:
        if _platform.system() == "Windows":
            import ctypes
            # Boosted to better match pyautogui scroll speed in this macro.
            WHEEL_DELTA = 360
            ctypes.windll.user32.mouse_event(0x0800, 0, 0, int(clicks) * WHEEL_DELTA, 0)
            return
    except Exception:
        pass

    # If we reached here, raise an informative error
    raise RuntimeError("Unable to perform scroll: no suitable backend available")

def getPos():
    return pag.position()