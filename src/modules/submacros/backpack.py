import mss
import mss.darwin
import numpy as np
from modules.screen import virtual_display

mss.darwin.IMAGE_OPTIONS = 0


def getPixelColor(x, y):
    x, y = virtual_display.to_global(x, y)
    region = {'top': y, 'left': x, 'width': 1, 'height': 1}
    with mss.mss() as sct:
        img = sct.grab(region)
        im = np.array(img)
        return tuple(int(c) for c in im[0, 0])[:-1][::-1]


def rgb_to_dec(r, g, b):
      if not (0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255):
            raise ValueError(f"RGB values out of range: r={r}, g={g}, b={b}")
      return (r * 256 * 256) + (g * 256) + b
    
def bpc(x,y):
    pix = getPixelColor(x,y)
    col = rgb_to_dec(*pix)
    perc = 0
    #natro's backpack calc
    if col & 0xFF0000 <= 0x690000: # less or equal to 50%
        if(col & 0xFF0000 <= 0x4B0000) : #less or equal to 25%
            if(col & 0xFF0000 <= 0x420000) : #less or equal to 10%
                if((col & 0xFF0000 <= 0x410000) and (col & 0x00FFFF <= 0x00FF80) and (col & 0x00FFFF > 0x00FF86)): #less or equal to 5%
                    perc=0
                elif((col & 0xFF0000 > 0x410000) and (col & 0x00FFFF <= 0x00FF80) and (col & 0x00FFFF > 0x00FC85)): #greater than 5%
                    perc=5
                else:
                    perc=0
                            
            else: #greater than 10%
                if((col & 0xFF0000 <= 0x470000)) : #less or equal to 20%
                    if((col & 0xFF0000 <= 0x440000) and (col & 0x00FFFF <= 0x00FE85) and (col & 0x00FFFF > 0x00F984)): #less or equal to 15%
                        perc=10
                    elif((col & 0xFF0000 > 0x440000) and (col & 0x00FFFF <= 0x00FB84) and (col & 0x00FFFF > 0x00F582)): #greater than 15%
                        perc=15
                    else:
                        perc=0
                                    
                elif((col & 0xFF0000 > 0x470000) and (col & 0x00FFFF <= 0x00F782) and (col & 0x00FFFF > 0x00F080)): #greater than 20%
                    perc=20
                else:
                    perc=0
                            
                    
        else: #greater than 25%
            if(col & 0xFF0000 <= 0x5B0000) : #less or equal to 40%
                if((col & 0xFF0000 <= 0x4F0000) and (col & 0x00FFFF <= 0x00F280) and (col & 0x00FFFF > 0x00EA7D)): #less or equal to 30%
                    perc=25
                else : #greater than 30%
                    if((col & 0xFF0000 <= 0x550000) and (col & 0x00FFFF <= 0x00EC7D) and (col & 0x00FFFF > 0x00E37A)): #less or equal to 35%
                        perc=30
                    elif((col & 0xFF0000 > 0x550000) and (col & 0x00FFFF <= 0x00E57A) and (col & 0x00FFFF > 0x00DA76)): #greater than 35%
                        perc=35
                    else:
                        perc=0
                        
                
            else: #greater than 40%
                if((col & 0xFF0000 <= 0x620000) and (col & 0x00FFFF <= 0x00DC76) and (col & 0x00FFFF > 0x00D072)): #less or equal to 45%
                    perc=40
                elif((col & 0xFF0000 > 0x620000) and (col & 0x00FFFF <= 0x00D272) and (col & 0x00FFFF > 0x00C66D)): #greater than 45%
                    perc=45
                else:
                    perc=0
                            
                    
            
    else : #greater than 50%
        if(col & 0xFF0000 <= 0x9C0000) : #less or equal to 75%
            if(col & 0xFF0000 <= 0x850000) : #less or equal to 65%
                if(col & 0xFF0000 <= 0x7B0000) : #less or equal to 60%
                    if((col & 0xFF0000 <= 0x720000) and (col & 0x00FFFF <= 0x00C86D) and (col & 0x00FFFF > 0x00BA68)): #less or equal to 55%
                        perc=50
                    elif ((col & 0xFF0000 > 0x720000) and (col & 0x00FFFF <= 0x00BC68) and (col & 0x00FFFF > 0x00AD62)): #greater than 55%
                        perc=55
                    else:
                        perc=0
                                    
                elif((col & 0xFF0000 > 0x7B0000) and (col & 0x00FFFF <= 0x00AF62) and (col & 0x00FFFF > 0x009E5C)): #greater than 60%
                    perc=60
                else:
                    perc=0      
            else : #greater than 65%
                if((col & 0xFF0000 <= 0x900000) and (col & 0x00FFFF <= 0x00A05C) and (col & 0x00FFFF > 0x008F55)): #less or equal to 70%
                    perc=65
                elif((col & 0xFF0000 > 0x900000) and (col & 0x00FFFF <= 0x009155) and (col & 0x00FFFF > 0x007E4E)): #greater than 70%
                    perc=70
                else:
                    perc=0
                            
                    
        else: #greater than 75%
            if((col & 0xFF0000 <= 0xC40000)): #less or equal to 90%
                if((col & 0xFF0000 <= 0xA90000) and (col & 0x00FFFF <= 0x00804E) and (col & 0x00FFFF > 0x006C46)) : #less or equal to 80%
                    perc=75
                else: #greater than 80%
                    if((col & 0xFF0000 <= 0xB60000) and (col & 0x00FFFF <= 0x006E46) and (col & 0x00FFFF > 0x005A3F)) : #less or equal to 85%
                        perc=80
                    elif((col & 0xFF0000 > 0xB60000) and (col & 0x00FFFF <= 0x005D3F) and (col & 0x00FFFF > 0x004637)): #greater than 85%
                        perc=85
                    else:
                        perc=0
                                    
                            
            else: #greater than 90%
                if((col & 0xFF0000 <= 0xD30000) and (col & 0x00FFFF <= 0x004A37) and (col & 0x00FFFF > 0x00322E)) : #less or equal to 95%
                    perc=90
                else: #greater than 95%
                    if col == 0xF70017 or ((col & 0xFF0000 >= 0xE00000) and (col & 0x00FFFF <= 0x002427) and (col & 0x00FFFF > 0x001000)): #is equal to 100%
                        perc=100
                    elif((col & 0x00FFFF <= 0x00342E)):
                        perc=95
                    else:
                        perc=0
    #print("X: {}, Y:{}, Pixel Colour: {}, Backpack Percentage: {}.".format(x,y,col, perc))
    return perc
