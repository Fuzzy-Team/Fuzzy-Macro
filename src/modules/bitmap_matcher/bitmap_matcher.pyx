# bitmap_matcher.pyx
import numpy as np
cimport numpy as cnp
cimport cython
from libc.string cimport memcmp
from libc.stdlib cimport malloc, free, abs
import base64
import binascii
import io
from PIL import Image

ctypedef cnp.uint8_t DTYPE_t

@cython.boundscheck(False)
@cython.wraparound(False)
def find_bitmap_hash_based_fast(cnp.ndarray[DTYPE_t, ndim=3] main_array, cnp.ndarray[DTYPE_t, ndim=3] bitmap_rgb, cnp.ndarray[cnp.uint8_t, ndim=2] alpha_mask=None, int search_x=0, int search_y=0, int search_w=-1, int search_h=-1, int variance=0):
    """
    Fast Cython implementation for bitmap matching with search area constraints and variance support.
    
    Args:
        main_array: The main image array to search in
        bitmap_rgb: The bitmap to search for
        alpha_mask: Optional alpha mask for transparent pixels
        search_x: X coordinate of search area (default: 0)
        search_y: Y coordinate of search area (default: 0)
        search_w: Width of search area (default: -1 for full width)
        search_h: Height of search area (default: -1 for full height)
        variance: Allowed color variance per channel 0-255 (default: 0 for exact match)
    """
    cdef int main_h = main_array.shape[0]
    cdef int main_w = main_array.shape[1]
    cdef int bitmap_h = bitmap_rgb.shape[0]
    cdef int bitmap_w = bitmap_rgb.shape[1]
    cdef int channels = 3
    
    # Calculate search boundaries
    cdef int search_start_x = max(0, search_x)
    cdef int search_start_y = max(0, search_y)
    cdef int search_end_x
    cdef int search_end_y
    
    if search_w == -1:
        search_end_x = main_w
    else:
        search_end_x = min(main_w, search_x + search_w)
    
    if search_h == -1:
        search_end_y = main_h
    else:
        search_end_y = min(main_h, search_y + search_h)
    
    #ensure we don't search beyond the bitmap's bounds
    search_end_x = min(search_end_x, main_w - bitmap_w + 1)
    search_end_y = min(search_end_y, main_h - bitmap_h + 1)
    
    #validate search area
    if search_start_x >= search_end_x or search_start_y >= search_end_y:
        return None
    
    cdef int y, x, i, j, k
    cdef int match_found
    cdef int bytes_per_row = bitmap_w * channels
    cdef int color_diff
    
    for x in range(search_start_x, search_end_x):
        for y in range(search_start_y, search_end_y):
            match_found = 1
            
            for i in range(bitmap_h):
                for j in range(bitmap_w):
                    if alpha_mask is None or alpha_mask[i, j]:  # Only check non-transparent pixels
                        for k in range(3):  # RGB channels
                            if variance == 0:
                                if main_array[y + i, x + j, k] != bitmap_rgb[i, j, k]:
                                    match_found = 0
                                    break
                            else:
                                color_diff = abs(<int>main_array[y + i, x + j, k] - <int>bitmap_rgb[i, j, k])
                                if color_diff > variance:
                                    match_found = 0
                                    break
                        if not match_found:
                            break
                if not match_found:
                    break
            
            if match_found:
                return (x, y)
    
    return None


@cython.boundscheck(False)
@cython.wraparound(False)
def find_all_bitmap_matches(cnp.ndarray[DTYPE_t, ndim=3] main_array, cnp.ndarray[DTYPE_t, ndim=3] bitmap_rgb, cnp.ndarray[cnp.uint8_t, ndim=2] alpha_mask=None, int search_x=0, int search_y=0, int search_w=-1, int search_h=-1, int variance=0, int max_matches=-1):
    """
    Find all matching locations of a bitmap in the main image with variance support.
    
    Args:
        main_array: The main image array to search in
        bitmap_rgb: The bitmap to search for
        alpha_mask: Optional alpha mask for transparent pixels
        search_x: X coordinate of search area (default: 0)
        search_y: Y coordinate of search area (default: 0)
        search_w: Width of search area (default: -1 for full width)
        search_h: Height of search area (default: -1 for full height)
        variance: Allowed color variance per channel 0-255 (default: 0 for exact match)
        max_matches: Maximum number of matches to find (default: -1 for all matches)
    
    Returns:
        list: List of (x, y) tuples representing match locations
    """
    cdef int main_h = main_array.shape[0]
    cdef int main_w = main_array.shape[1]
    cdef int bitmap_h = bitmap_rgb.shape[0]
    cdef int bitmap_w = bitmap_rgb.shape[1]
    

    cdef int search_start_x = max(0, search_x)
    cdef int search_start_y = max(0, search_y)
    cdef int search_end_x, search_end_y
    
    if search_w == -1:
        search_end_x = main_w
    else:
        search_end_x = min(main_w, search_x + search_w)
    
    if search_h == -1:
        search_end_y = main_h
    else:
        search_end_y = min(main_h, search_y + search_h)
    
    search_end_x = min(search_end_x, main_w - bitmap_w + 1)
    search_end_y = min(search_end_y, main_h - bitmap_h + 1)

    if search_start_x >= search_end_x or search_start_y >= search_end_y:
        return []
    
    cdef int y, x, i, j, k
    cdef int match_found
    cdef int color_diff
    cdef int matches_found = 0
    cdef list matches = []
    cdef object append_match = matches.append
    
    #search for all matches
    for x in range(search_start_x, search_end_x):
        for y in range(search_start_y, search_end_y):
            match_found = 1
            for i in range(bitmap_h):
                for j in range(bitmap_w):
                    if alpha_mask is None or alpha_mask[i, j]:
                        for k in range(3):  # RGB channels
                            if variance == 0:
                                if main_array[y + i, x + j, k] != bitmap_rgb[i, j, k]:
                                    match_found = 0
                                    break
                            else:
                                color_diff = abs(<int>main_array[y + i, x + j, k] - <int>bitmap_rgb[i, j, k])
                                if color_diff > variance:
                                    match_found = 0
                                    break
                        if not match_found:
                            break
                if not match_found:
                    break
            
            if match_found:
                append_match((x, y))
                matches_found += 1
                if max_matches > 0 and matches_found >= max_matches:
                    break
        
        if max_matches > 0 and matches_found >= max_matches:
            break
    
    return matches


def create_bitmap_from_base64(base64_string):
    """
    Reads a base64 string and converts it into a PIL Image object for searching.

    Args:
        base64_string (str): The base64-encoded image data.

    Returns:
        PIL.Image.Image: The bitmap image object in RGBA mode.
        None: If the base64 string is invalid or cannot be processed.
    """
    try:
        #decode the base64 string into bytes
        image_bytes = base64.b64decode(base64_string)
        image_stream = io.BytesIO(image_bytes)

        #open the image from the stream and convert to RGBA
        bitmap = Image.open(image_stream).convert('RGBA')
        return bitmap
    except (base64.binascii.Error, IOError) as e:
        print(f"Error processing base64 string: {e}")
        return None


#python wrapper function
def find_bitmap_cython(main_image, bitmap_image, x=0, y=0, w=None, h=None, variance=0):
    """
    Python wrapper for the Cython bitmap matching function
    
    Args:
        main_image: PIL Image object to search in
        bitmap_image: PIL Image object to search for
        x: X coordinate of search area (default: 0)
        y: Y coordinate of search area (default: 0)
        w: Width of search area (default: None for full width)
        h: Height of search area (default: None for full height)
        variance: Allowed color variance per channel 0-255 (default: 0 for exact match)
    
    Returns:
        tuple: (x, y) coordinates of the match, or None if not found
    """
    main_array = np.asarray(main_image.convert('RGB'), dtype=np.uint8)
    
    #set default search area. Set to -1 for compatibility with cython function
    search_w = w if w is not None else -1
    search_h = h if h is not None else -1
    
    #clamp variance range
    variance = max(0, min(255, variance))
    
    if bitmap_image.mode == 'RGBA':
        bitmap_array = np.asarray(bitmap_image, dtype=np.uint8)
        bitmap_rgb = bitmap_array[:, :, :3]
        alpha_mask = bitmap_array[:, :, 3] > 128
        
        # Check if there are any non-transparent pixels
        if not np.any(alpha_mask):
            return None
    else:
        bitmap_rgb = np.asarray(bitmap_image.convert('RGB'), dtype=np.uint8)
        alpha_mask = None
    
    return find_bitmap_hash_based_fast(main_array, bitmap_rgb, alpha_mask, x, y, search_w, search_h, variance)


def find_all_bitmap_cython(main_image, bitmap_image, x=0, y=0, w=None, h=None, variance=0, max_matches=-1):
    """
    Python wrapper to find all matching locations of a bitmap in the main image.
    
    Args:
        main_image: PIL Image object to search in
        bitmap_image: PIL Image object to search for
        x: X coordinate of search area (default: 0)
        y: Y coordinate of search area (default: 0)
        w: Width of search area (default: None for full width)
        h: Height of search area (default: None for full height)
        variance: Allowed color variance per channel 0-255 (default: 0 for exact match)
        max_matches: Maximum number of matches to find (default: -1 for all matches)
    
    Returns:
        list: List of (x, y) tuples representing match locations
    """
    main_array = np.asarray(main_image.convert('RGB'), dtype=np.uint8)
    
    # Set default search dimensions if not provided
    search_w = w if w is not None else -1
    search_h = h if h is not None else -1
    
    # Clamp variance to valid range
    variance = max(0, min(255, variance))
    
    if bitmap_image.mode == 'RGBA':
        bitmap_array = np.asarray(bitmap_image, dtype=np.uint8)
        bitmap_rgb = bitmap_array[:, :, :3]
        alpha_mask = bitmap_array[:, :, 3] > 128
        
        # Check if there are any non-transparent pixels
        if not np.any(alpha_mask):
            return []
    else:
        bitmap_rgb = np.asarray(bitmap_image.convert('RGB'), dtype=np.uint8)
        alpha_mask = None
    
    return find_all_bitmap_matches(main_array, bitmap_rgb, alpha_mask, x, y, search_w, search_h, variance, max_matches)