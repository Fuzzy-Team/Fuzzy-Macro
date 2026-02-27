import mss
import platform
import numpy as np

_IS_WINDOWS = platform.system() == "Windows"
if not _IS_WINDOWS:
    import mss.darwin
    mss.darwin.IMAGE_OPTIONS = 0

def getPixelColor(X1,Y1):
    region = {'top': Y1, 'left': X1, 'width': 1, 'height': 1}
    
    with mss.mss() as sct:
        img = sct.grab(region)
        im = np.array(img)
        col = tuple(int(c) for c in im[0,0])[:-1][::-1]
        return col
