import time
import random
from typing import List, Tuple, Set, Optional

import cv2
import imagehash
import numpy as np
from PIL import Image

import modules.controls.mouse as mouse
from modules.screen.screenshot import mssScreenshot, mssScreenshotNP
from modules.screen.ocr import ocrRead, imToString
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
    
    def __init__(self, robloxWindow: RobloxWindowBounds, debug: bool = False):
        self.robloxWindow = robloxWindow
        self.debug = debug
        self.blank_tile_hash = imagehash.average_hash(Image.open("./images/menu/mmempty.png"))
        # Buckets of seen tile hashes for the current memory match game.
        # Each entry is a tuple: (imagehash.ImageHash, [indices_where_seen])
        self.seen_buckets = []
        # (hash-only mode) no reference images loaded

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
        # Reset seen buckets for this memory match game
        self.seen_buckets = []
        
        # Initialize game state
        checked_coords: Set[Tuple[int, int]] = set()
        claimed_coords: Set[int] = set()
        mm_data: List[Optional[imagehash.ImageHash]] = [None] * (grid_size[0] * grid_size[1])
        # per-tile item names are not used in hash-only mode
        
        # Get attempts count
        middle_x = self.robloxWindow.mx + self.robloxWindow.mw // 2
        middle_y = self.robloxWindow.my + self.robloxWindow.mh // 2
        attempts = self._get_attempts_count(middle_x, middle_y, offset_x)
        
        # Game loop
        current_attempt = 0
        matched_indices = set()
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

        self._wait_for_winnings_text()

    def _wait_for_winnings_text(self) -> None:
        """Wait for winnings text or payout background to appear."""
        bluetexts = ""
        found = False
        for _ in range(6):
            try:
                txt = imToString("blue").lower()
            except Exception:
                txt = ""
            bluetexts += txt
            if "winner" in txt or "better luck" in txt or "next time" in txt:
                found = True
                break
            try:
                bx = int(self.robloxWindow.mx + self.robloxWindow.mw * 3 / 4)
                by = int(self.robloxWindow.my + self.robloxWindow.mh * 2 / 3)
                bw = int(self.robloxWindow.mw // 4)
                bh = int(self.robloxWindow.mh // 6)
                screen_np = mssScreenshotNP(bx, by, bw, bh)
                bgr = cv2.cvtColor(screen_np, cv2.COLOR_BGRA2BGR)
                hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
                lower_y = np.array([15, 90, 90])
                upper_y = np.array([40, 255, 255])
                mask = cv2.inRange(hsv, lower_y, upper_y)
                ratio = np.count_nonzero(mask) / (mask.size if mask.size else 1)
                if ratio > 0.03:
                    found = True
                    break
            except Exception:
                pass
            time.sleep(0.4)
        time.sleep(0.2)

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
            
            # Check for matches with existing tiles (hash-bucket based)
            match_found = self._lookup_seen(tile_hash, claimed_coords, exclude_index=None)
            if match_found is not None:
                claimed_coords.add(i)
                claimed_coords.add(match_found)
                if self.debug:
                    print(f"[MM] Match found on first tile: indices {i} & {match_found}")
                else:
                    print("Match found on first tile")
            
            mm_data[i] = tile_hash
            # Record this tile in seen buckets so future tiles can find it
            self._record_seen(tile_hash, i)
            return i, tile_hash
        
        return None, None

    def _click_second_tile(self, grid_coords: List[Tuple[int, int]], checked_coords: Set[Tuple[int, int]], 
                          mm_data: List[Optional[imagehash.ImageHash]], claimed_coords: Set[int], 
                          first_tile_index: int, first_tile_hash: imagehash.ImageHash, 
                          offset_x: int, offset_y: int, middle_x: int, middle_y: int, 
                          current_attempt: int) -> None:
        """Click the second tile and handle matching logic."""
        # If we found a match on first tile, click the matching tile
        match_found = self._lookup_seen(first_tile_hash, claimed_coords, exclude_index=first_tile_index)
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

            # Check for matches (hash-bucket based)
            match_found = self._lookup_seen(tile_hash, claimed_coords, exclude_index=i)
            if match_found is not None:
                if match_found == first_tile_index:
                    if self.debug:
                        print(f"[MM] Match found on second tile, same attempt: indices {i} & {match_found}")
                    else:
                        print("Match found, same attempt")
                    claimed_coords.add(i)
                    claimed_coords.add(match_found)
                else:
                    if self.debug:
                        print(f"[MM] Match found on second tile: indices {i} & {match_found}")
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
            # Record seen tile for future matches (hash-bucket)
            self._record_seen(tile_hash, i)
            break

    def _find_matching_tile(self, tile_hash: imagehash.ImageHash, mm_data: List[Optional[imagehash.ImageHash]], 
                           claimed_coords: Set[int], exclude_index: Optional[int] = None) -> Optional[int]:
        """Find a matching tile in the existing data, optionally excluding an index.

        Args:
            tile_hash: The hash of the tile to find a match for.
            mm_data: List of hashes for tiles already seen.
            claimed_coords: Set of indices already claimed/matched.
            exclude_index: Optional index to skip when searching (prevents matching a tile with itself).
        """
        for j, existing_hash in enumerate(mm_data):
            if existing_hash is None or j in claimed_coords:
                continue
            if exclude_index is not None and j == exclude_index:
                continue
            if self._are_images_similar(tile_hash, existing_hash):
                return j
        return None

    def _record_seen(self, tile_hash: imagehash.ImageHash, index: int) -> None:
        """Record a seen tile hash into buckets for the current game."""
        for k, (bucket_hash, indices) in enumerate(self.seen_buckets):
            if self._are_images_similar(tile_hash, bucket_hash):
                indices.append(index)
                if self.debug:
                    print(f"[MM] Recorded hash-bucket index {index} (bucket {k})")
                return
        # No similar bucket found; add a new one
        self.seen_buckets.append((tile_hash, [index]))
        if self.debug:
            print(f"[MM] Created new hash-bucket for index {index}")

    # Reference-image support removed: operating in hash-only mode

    def _lookup_seen(self, tile_hash: imagehash.ImageHash, claimed_coords: Set[int], exclude_index: Optional[int] = None) -> Optional[int]:
        """Lookup a previously seen index for a tile hash using only hash-buckets.

        Returns an index that isn't in `claimed_coords` and isn't `exclude_index`, or None.
        """
        for bucket_hash, indices in self.seen_buckets:
            if self._are_images_similar(tile_hash, bucket_hash):
                for idx in indices:
                    if idx in claimed_coords:
                        continue
                    if exclude_index is not None and idx == exclude_index:
                        continue
                    if self.debug:
                        print(f"[MM] Found hash-match in bucket for index {idx}")
                    return idx
        return None