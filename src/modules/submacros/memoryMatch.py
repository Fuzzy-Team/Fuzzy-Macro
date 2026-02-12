import time
import random
from typing import List, Tuple, Set, Optional
import imagehash
from PIL import Image

import modules.controls.mouse as mouse
from modules.screen.screenshot import mssScreenshot
from modules.screen.ocr import ocrRead
from modules.misc.imageManipulation import adjustImage
from modules.screen.imageSearch import locateImageOnScreen
from modules.screen.robloxWindow import RobloxWindowBounds


class MemoryMatch:
    """Memory Match game solver with lag compensation."""
    
    # Constants
    TILE_SIZE = (50, 30)
    TILE_OFFSET = (-30, -20)
    GRID_OFFSETS = {
        "extreme": (40, 0),
        "winter": (40, 0),
        "default": (0, 0)
    }
    GRID_SIZES = {
        "extreme": (5, 4),
        "winter": (5, 4),
        "default": (4, 4)
    }
    MAX_WAIT_TIME = 3.0
    TILE_FLIP_DELAY = 0.2
    CLICK_DELAY = 0.3
    MOVE_DELAY = 0.2
    TURN_DELAY = 0.8
    MOUSE_MOVE_OFFSET = 190
    MIN_ATTEMPTS = 3
    MAX_ATTEMPTS = 10
    DEFAULT_ATTEMPTS = 10
    
    def __init__(self, robloxWindow: RobloxWindowBounds):
        self.robloxWindow = robloxWindow
        self.blank_tile_hash = imagehash.average_hash(Image.open("./images/menu/mmempty.png"))

    def _click_tile(self, x: int, y: int) -> None:
        """Click on a tile at the given coordinates."""
        mouse.moveTo(x, y, self.MOVE_DELAY)
        time.sleep(self.CLICK_DELAY)
        mouse.click()

    def _wait_for_tile_flip(self, x: int, y: int) -> imagehash.ImageHash:
        """Wait for a tile to flip over, compensating for lag."""
        start_time = time.time()
        while time.time() - start_time < self.MAX_WAIT_TIME:
            tile_hash = self._screenshot_tile(x, y)
            if not self._are_images_similar(tile_hash, self.blank_tile_hash):
                time.sleep(self.TILE_FLIP_DELAY)
                tile_hash = self._screenshot_tile(x, y)
                break
        return tile_hash
    
    def _are_images_similar(self, img1: imagehash.ImageHash, img2: imagehash.ImageHash) -> bool:
        """Check if two image hashes are similar."""
        return img1 - img2 < 2

    def _screenshot_tile(self, x: int, y: int) -> imagehash.ImageHash:
        """Take a screenshot of a tile and return its hash."""
        offset_x, offset_y = self.TILE_OFFSET
        width, height = self.TILE_SIZE
        screenshot = mssScreenshot(x + offset_x, y + offset_y, width, height)
        return imagehash.average_hash(screenshot)

    def _get_grid_configuration(self, mm_type: str) -> Tuple[List[Tuple[int, int]], Tuple[int, int], Tuple[int, int]]:
        """Get grid coordinates, size, and offsets based on memory match type."""
        mm_type_lower = mm_type.lower()
        
        # Get grid size
        grid_size = self.GRID_SIZES.get(mm_type_lower, self.GRID_SIZES["default"])
        
        # Get offsets
        offset_x, offset_y = self.GRID_OFFSETS.get(mm_type_lower, self.GRID_OFFSETS["default"])
        
        # Calculate grid coordinates
        middle_x = self.robloxWindow.mx + self.robloxWindow.mw // 2
        middle_y = self.robloxWindow.my + self.robloxWindow.mh // 2
        
        grid_coords = []
        for i in range(1, grid_size[0] + 1):
            x = middle_x - 200 + 80 * i
            for j in range(1, grid_size[1] + 1):
                y = middle_y - 200 + 80 * j
                grid_coords.append((x, y))
        
        # Randomize the grid positions
        random.shuffle(grid_coords)
        
        return grid_coords, grid_size, (offset_x, offset_y)

    def _get_attempts_count(self, middle_x: int, middle_y: int, offset_x: int) -> int:
        """Read the number of attempts from the screen."""
        try:
            cap = mssScreenshot(middle_x - 275 - offset_x, middle_y - 146, 100, 100)
            attempts_ocr = int(''.join([x[1][0] for x in ocrRead(cap) if x[1][0].isdigit()]))
            if self.MIN_ATTEMPTS <= attempts_ocr <= self.MAX_ATTEMPTS:
                print(f"Number of attempts: {attempts_ocr}")
                return attempts_ocr
        except (ValueError, IndexError, Exception) as e:
            print(f"Error reading attempts: {e}")
        return self.DEFAULT_ATTEMPTS

    def solveMemoryMatch(self, mm_type: str) -> None:
        """Solve the memory match game."""
        # Get grid configuration
        grid_coords, grid_size, (offset_x, offset_y) = self._get_grid_configuration(mm_type)
        
        # Initialize game state
        checked_coords: Set[Tuple[int, int]] = set()
        claimed_coords: Set[int] = set()
        mm_data: List[Optional[imagehash.ImageHash]] = [None] * (grid_size[0] * grid_size[1])
        
        # Get attempts count
        middle_x = self.robloxWindow.mx + self.robloxWindow.mw // 2
        middle_y = self.robloxWindow.my + self.robloxWindow.mh // 2
        attempts = self._get_attempts_count(middle_x, middle_y, offset_x)
        
        # Game loop
        current_attempt = 0
        while current_attempt <= attempts:
            print(f"Attempt {current_attempt}")
            
            # Check if game is still active
            if current_attempt > attempts:
                self._check_game_active()
            
            # First tile
            first_tile_index, first_tile_hash = self._click_first_tile(
                grid_coords, checked_coords, mm_data, claimed_coords, offset_x, offset_y, middle_x, middle_y
            )
            
            if first_tile_index is None:
                break
                
            time.sleep(self.TURN_DELAY)
            
            # Second tile
            self._click_second_tile(
                grid_coords, checked_coords, mm_data, claimed_coords, 
                first_tile_index, first_tile_hash, offset_x, offset_y, 
                middle_x, middle_y, current_attempt
            )
            
            current_attempt += 1
            time.sleep(self.TURN_DELAY)

    def _check_game_active(self) -> None:
        """Check if the memory match game is still active."""
        mm_img = adjustImage("./images/menu", "mmopen", self.robloxWindow.display_type)
        if not locateImageOnScreen(
            mm_img, 
            self.robloxWindow.mx + self.robloxWindow.mw / 4, 
            self.robloxWindow.my + self.robloxWindow.mh / 4, 
            self.robloxWindow.mw / 4, 
            self.robloxWindow.mh / 3.5, 
            0.8
        ):
            pass  # Game might have ended

    def _click_first_tile(self, grid_coords: List[Tuple[int, int]], checked_coords: Set[Tuple[int, int]], 
                          mm_data: List[Optional[imagehash.ImageHash]], claimed_coords: Set[int], 
                          offset_x: int, offset_y: int, middle_x: int, middle_y: int) -> Tuple[Optional[int], Optional[imagehash.ImageHash]]:
        """Click the first tile and return its index and hash."""
        for i, (x_raw, y_raw) in enumerate(grid_coords):
            if (x_raw, y_raw) in checked_coords:
                continue
                
            x = x_raw - offset_x
            y = y_raw - offset_y
            
            self._click_tile(x, y)
            time.sleep(0.1)
            mouse.moveTo(middle_x, middle_y - self.MOUSE_MOVE_OFFSET)  # Move mouse out of the way
            
            tile_hash = self._wait_for_tile_flip(x, y)
            checked_coords.add((x_raw, y_raw))
            
            # Check for matches with existing tiles
            match_found = self._find_matching_tile(tile_hash, mm_data, claimed_coords)
            if match_found is not None:
                claimed_coords.add(i)
                claimed_coords.add(match_found)
                print("Match found on first tile")
            
            mm_data[i] = tile_hash
            return i, tile_hash
        
        return None, None

    def _click_second_tile(self, grid_coords: List[Tuple[int, int]], checked_coords: Set[Tuple[int, int]], 
                          mm_data: List[Optional[imagehash.ImageHash]], claimed_coords: Set[int], 
                          first_tile_index: int, first_tile_hash: imagehash.ImageHash, 
                          offset_x: int, offset_y: int, middle_x: int, middle_y: int, 
                          current_attempt: int) -> None:
        """Click the second tile and handle matching logic."""
        # If we found a match on first tile, click the matching tile
        match_found = self._find_matching_tile(first_tile_hash, mm_data, claimed_coords)
        if match_found is not None:
            print("Match found, clicking matching tile")
            x, y = grid_coords[match_found]
            self._click_tile(x - offset_x, y - offset_y)
            return
        
        # Otherwise, click a new tile
        for i, (x_raw, y_raw) in enumerate(grid_coords):
            if (x_raw, y_raw) in checked_coords:
                continue
                
            x = x_raw - offset_x
            y = y_raw - offset_y
            
            self._click_tile(x, y)
            time.sleep(0.1)
            mouse.moveTo(middle_x, middle_y - self.MOUSE_MOVE_OFFSET)  # Move mouse out of the way
            
            tile_hash = self._wait_for_tile_flip(x, y)
            checked_coords.add((x_raw, y_raw))
            
            # Check for matches
            match_found = self._find_matching_tile(tile_hash, mm_data, claimed_coords)
            if match_found is not None:
                if match_found == first_tile_index:
                    print("Match found, same attempt")
                    claimed_coords.add(i)
                    claimed_coords.add(match_found)
                else:
                    print("Match found on second tile")
                    # Handle the match in the next turn
                    time.sleep(2)
                    self._click_tile(x, y)  # Click the second tile again
                    time.sleep(1)
                    x2, y2 = grid_coords[match_found]
                    self._click_tile(x2 - offset_x, y2 - offset_y)  # Click the matching tile
                    claimed_coords.add(i)
                    claimed_coords.add(match_found)
            
            mm_data[i] = tile_hash
            break

    def _find_matching_tile(self, tile_hash: imagehash.ImageHash, mm_data: List[Optional[imagehash.ImageHash]], 
                           claimed_coords: Set[int]) -> Optional[int]:
        """Find a matching tile in the existing data."""
        for j, existing_hash in enumerate(mm_data):
            if existing_hash is None or j in claimed_coords:
                continue
            if self._are_images_similar(tile_hash, existing_hash):
                return j
        return None