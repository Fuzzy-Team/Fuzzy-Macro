import mss 
import mss.darwin
mss.darwin.IMAGE_OPTIONS = 0
import numpy as np
from modules.screen import macroDisplay

#X1, Y1 are relative to the display the macro runs on
def getPixelColor(X1,Y1):
    X1, Y1 = macroDisplay.toGlobal(X1, Y1)
    region = {'top': Y1, 'left': X1, 'width': 1, 'height': 1}
    
    with mss.mss() as sct:
        img = sct.grab(region)
        im = np.array(img)
        col = tuple(int(c) for c in im[0,0])[:-1][::-1]
        return col
