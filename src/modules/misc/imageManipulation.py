import numpy as np
import cv2
import os
from PIL import Image


class ImageHash:
    """Average hash of an image. `a - b` is the number of differing bits."""

    def __init__(self, bits):
        self.bits = bits

    def __sub__(self, other):
        return int(np.count_nonzero(self.bits != other.bits))

    def __eq__(self, other):
        return isinstance(other, ImageHash) and np.array_equal(self.bits, other.bits)

    def __hash__(self):
        return hash(self.bits.tobytes())


#same algorithm as imagehash.average_hash: shrink to 8x8 grayscale and compare each pixel to the mean
def average_hash(img):
    pixels = np.asarray(img.convert("L").resize((8, 8), Image.LANCZOS))
    return ImageHash(pixels > pixels.mean())

#accept a pillow image and return a cv2 one
def pillowToCv2(img):
    return cv2.cvtColor(np.array(img), cv2.COLOR_BGR2RGB)

#resize the image based on the user's screen coordinates
def adjustImage(folder, imageName, display_type):
    #get a list of all images and find the name of the one that matches
    images = os.listdir(folder)
    for x in images:
        #images are named in the format itemname-width
        #width is the width of the monitor used to take the image
        if not "-" in x: continue
        name, res = x.split(".")[0].split("-",1)
        if name == imageName:
            img = Image.open(f"{folder}/{x}")
            break
    else:
        raise FileNotFoundError(f"Could not find the image named {imageName} in {folder}")
    #get original size of image
    width, height = img.size
    #calculate the scaling value 
    #retina has 2x more, built-in is 1x
    if display_type == res:
        scaling = 1
    elif display_type == "built-in": #screen is built-in but image is retina
        scaling = 2
    else: #screen is retina but image is built-in
        scaling = 0.5
    #resize image
    img = img.resize((int(width/scaling), int(height/scaling)))
    #convert to cv2
    return pillowToCv2(img)