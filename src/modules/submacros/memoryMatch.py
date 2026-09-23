import os
import time
import random
from typing import Dict, List, Tuple, Set, Optional

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

# reward icons, one folder per memory match type: <type>/<reward name>.webp
REWARD_TEMPLATE_DIR = "./images/memorymatch"

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
    REWARD_MATCH_THRESHOLD = 0.58
    
    def __init__(self, robloxWindow: RobloxWindowBounds, debug: bool = False):
        self.robloxWindow = robloxWindow
        self.debug = debug
        self.blank_tile_hash = imagehash.average_hash(Image.open("./images/menu/mmempty.png"))
        # Buckets of seen tile hashes for the current memory match game.
        # Each entry is a tuple: (imagehash.ImageHash, [indices_where_seen])
        self.seen_buckets = []
        # Optional templates for identifying selected reward types.
        self.reward_templates_by_type = self._load_reward_templates()
        self.reward_templates = {}

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

    def _capture_tile(self, x: int, y: int) -> Image.Image:
        """Take a screenshot of a tile."""
        offset_x, offset_y = self.TILE_OFFSET
        width, height = self.TILE_SIZE
        return mssScreenshot(x + offset_x, y + offset_y, width, height)

    def _screenshot_tile(self, x: int, y: int) -> imagehash.ImageHash:
        """Take a screenshot of a tile and return its hash."""
        screenshot = self._capture_tile(x, y)
        return imagehash.average_hash(screenshot)

    def _load_reward_templates(self) -> Dict[str, Dict[str, List[np.ndarray]]]:
        """Load reward icon templates used to identify preferred rewards."""
        templates_by_type = {}
        for mm_type in sorted(os.listdir(REWARD_TEMPLATE_DIR)):
            type_dir = os.path.join(REWARD_TEMPLATE_DIR, mm_type)
            if not os.path.isdir(type_dir):
                continue
            templates_by_type[mm_type] = {}
            for filename in sorted(os.listdir(type_dir)):
                reward, ext = os.path.splitext(filename)
                if ext.lower() != ".webp":
                    continue
                try:
                    image = Image.open(os.path.join(type_dir, filename)).convert("RGBA")
                    template = cv2.cvtColor(np.array(image), cv2.COLOR_RGBA2BGRA)
                except Exception as e:
                    if self.debug:
                        print(f"[MM] Failed to load reward template '{reward}': {e}")
                    continue
                if template is not None and template.size:
                    templates_by_type[mm_type][reward] = [template]
        return templates_by_type

    def _normalize_mm_type(self, mm_type: str) -> str:
        """Normalize memory match type names to generated reward data buckets."""
        mm_type = str(mm_type).strip().lower()
        if mm_type in ("normal", "memory", "memory_match", "memory match", "default"):
            return "normal"
        if mm_type in ("mega", "mega_memory_match", "mega memory match"):
            return "mega"
        if mm_type in ("extreme", "extreme_memory_match", "extreme memory match"):
            return "extreme"
        if mm_type in ("winter", "winter_memory_match", "winter memory match"):
            return "winter"
        return mm_type

    def _classify_reward(self, tile_image: Image.Image) -> Optional[str]:
        """Classify a flipped tile against known reward templates."""
        if not self.reward_templates:
            return None

        tile = cv2.cvtColor(np.array(tile_image.convert("RGBA")), cv2.COLOR_RGBA2BGRA)
        tile_bgr = cv2.cvtColor(tile, cv2.COLOR_BGRA2BGR)
        best_reward = None
        best_score = 0.0

        for reward, templates in self.reward_templates.items():
            for template in templates:
                score = self._template_score(tile_bgr, template)
                if score > best_score:
                    best_reward = reward
                    best_score = score

        if best_score >= self.REWARD_MATCH_THRESHOLD:
            if self.debug:
                print(f"[MM] Classified reward '{best_reward}' with score {best_score:.2f}")
            return best_reward
        return None

    def _template_score(self, tile_bgr: np.ndarray, template: np.ndarray) -> float:
        """Return the best template-match score for a template inside a tile."""
        if len(template.shape) == 2:
            template_bgr = cv2.cvtColor(template, cv2.COLOR_GRAY2BGR)
            template_gray = template
        elif template.shape[2] == 4:
            alpha = template[:, :, 3]
            coords = cv2.findNonZero(alpha)
            if coords is not None:
                x, y, w, h = cv2.boundingRect(coords)
                template = template[y:y + h, x:x + w]
            template_bgr = cv2.cvtColor(template, cv2.COLOR_BGRA2BGR)
            template_gray = cv2.cvtColor(template_bgr, cv2.COLOR_BGR2GRAY)
        else:
            template_bgr = template
            template_gray = cv2.cvtColor(template_bgr, cv2.COLOR_BGR2GRAY)
        tile_gray = cv2.cvtColor(tile_bgr, cv2.COLOR_BGR2GRAY)

        best = 0.0
        max_h, max_w = tile_gray.shape[:2]
        for target_h in (16, 20, 24, 28, 32):
            scale = target_h / template_gray.shape[0]
            target_w = int(template_gray.shape[1] * scale)
            if target_w < 8 or target_h < 8 or target_w > max_w or target_h > max_h:
                continue
            resized = cv2.resize(template_gray, (target_w, target_h), interpolation=cv2.INTER_AREA)
            res = cv2.matchTemplate(tile_gray, resized, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(res)
            if np.isfinite(max_val):
                best = max(best, float(max_val))
        return best

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

    def solveMemoryMatch(self, mm_type: str, preferred_rewards: Optional[List[str]] = None) -> None:
        """Solve the memory match game."""
        # Get grid configuration
        grid_coords, grid_size, (offset_x, offset_y) = self._get_grid_configuration(mm_type)
        self.reward_templates = self.reward_templates_by_type.get(self._normalize_mm_type(mm_type), {})
        # Reset seen buckets for this memory match game
        self.seen_buckets = []
        preferred_rewards = set(self._normalize_reward_name(x) for x in (preferred_rewards or []))
        preferred_rewards = preferred_rewards.intersection(self.reward_templates.keys())
        
        # Initialize game state
        checked_coords: Set[Tuple[int, int]] = set()
        claimed_coords: Set[int] = set()
        mm_data: List[Optional[imagehash.ImageHash]] = [None] * (grid_size[0] * grid_size[1])
        tile_rewards: List[Optional[str]] = [None] * (grid_size[0] * grid_size[1])
        
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
            
            target_pair = self._find_known_preferred_pair(tile_rewards, preferred_rewards, claimed_coords)
            if target_pair is not None:
                first_idx, second_idx = target_pair
                print(f"Preferred reward match found: {tile_rewards[first_idx]}")
                x1, y1 = grid_coords[first_idx]
                x2, y2 = grid_coords[second_idx]
                self._click_tile(x1 - offset_x, y1 - offset_y)
                time.sleep(self.TURN_DELAY)
                self._click_tile(x2 - offset_x, y2 - offset_y)
                claimed_coords.add(first_idx)
                claimed_coords.add(second_idx)
                current_attempt += 1
                time.sleep(self.TURN_DELAY)
                try:
                    if self._check_for_winnings():
                        self._wait_for_winnings_text()
                        return
                except Exception:
                    pass
                continue

            # First tile
            first_tile_index, first_tile_hash = self._click_first_tile(
                grid_coords, checked_coords, mm_data, tile_rewards, claimed_coords, preferred_rewards, offset_x, offset_y, middle_x, middle_y
            )
            
            if first_tile_index is None:
                break
                
            time.sleep(self.TURN_DELAY)
            
            # Second tile
            self._click_second_tile(
                grid_coords, checked_coords, mm_data, tile_rewards, claimed_coords, preferred_rewards,
                first_tile_index, first_tile_hash, offset_x, offset_y, 
                middle_x, middle_y, current_attempt
            )
            
            
            current_attempt += 1
            time.sleep(self.TURN_DELAY)
            # After each match attempt, do a quick check for winnings/payout UI
            try:
                if self._check_for_winnings():
                    self._wait_for_winnings_text()
                    return
            except Exception:
                pass

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

    def _check_for_winnings(self) -> bool:
        """Quick non-blocking check for winnings/payout UI.

        Returns True if a winnings message or payout background is detected.
        """
        try:
            txt = imToString("blue").lower()
            if "winner" in txt or "better luck" in txt or "next time" in txt:
                return True
        except Exception:
            pass
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
                return True
        except Exception:
            pass
        return False

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
                          mm_data: List[Optional[imagehash.ImageHash]], tile_rewards: List[Optional[str]],
                          claimed_coords: Set[int], preferred_rewards: Set[str],
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
            
            tile_image = self._capture_tile(x, y)
            tile_hash = imagehash.average_hash(tile_image)
            if self._are_images_similar(tile_hash, self.blank_tile_hash):
                tile_hash = self._wait_for_tile_flip(x, y)
                tile_image = self._capture_tile(x, y)
            tile_reward = self._classify_reward(tile_image)
            checked_coords.add((x_raw, y_raw))
            
            # Check for matches with existing tiles (hash-bucket based)
            match_found = self._lookup_seen(tile_hash, claimed_coords, exclude_index=None)
            if match_found is not None:
                if self.debug:
                    print(f"[MM] Match found on first tile: indices {i} & {match_found}")
                else:
                    print("Match found on first tile")
            
            mm_data[i] = tile_hash
            tile_rewards[i] = tile_reward
            # Record this tile in seen buckets so future tiles can find it
            self._record_seen(tile_hash, i)
            return i, tile_hash
        
        return None, None

    def _click_second_tile(self, grid_coords: List[Tuple[int, int]], checked_coords: Set[Tuple[int, int]], 
                          mm_data: List[Optional[imagehash.ImageHash]], tile_rewards: List[Optional[str]],
                          claimed_coords: Set[int], preferred_rewards: Set[str],
                          first_tile_index: int, first_tile_hash: imagehash.ImageHash, 
                          offset_x: int, offset_y: int, middle_x: int, middle_y: int, 
                          current_attempt: int) -> None:
        """Click the second tile and handle matching logic."""
        # If we found a match on first tile, click the matching tile
        match_found = self._lookup_seen(first_tile_hash, claimed_coords, exclude_index=first_tile_index)
        if match_found is not None:
            if not self._should_claim_match(tile_rewards[first_tile_index], tile_rewards[match_found], preferred_rewards):
                match_found = None
            else:
                print("Match found, clicking matching tile")
                x, y = grid_coords[match_found]
                self._click_tile(x - offset_x, y - offset_y)
                claimed_coords.add(first_tile_index)
                claimed_coords.add(match_found)
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

            tile_image = self._capture_tile(x, y)
            tile_hash = imagehash.average_hash(tile_image)
            if self._are_images_similar(tile_hash, self.blank_tile_hash):
                tile_hash = self._wait_for_tile_flip(x, y)
                tile_image = self._capture_tile(x, y)
            tile_reward = self._classify_reward(tile_image)
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
                    if not self._should_claim_match(tile_reward, tile_rewards[match_found], preferred_rewards):
                        mm_data[i] = tile_hash
                        tile_rewards[i] = tile_reward
                        self._record_seen(tile_hash, i)
                        break
                    # Handle the match in the next turn
                    time.sleep(2)
                    self._click_tile(x, y)  # Click the second tile again
                    time.sleep(1)
                    x2, y2 = grid_coords[match_found]
                    self._click_tile(x2 - offset_x, y2 - offset_y)  # Click the matching tile
                    claimed_coords.add(i)
                    claimed_coords.add(match_found)
            mm_data[i] = tile_hash
            tile_rewards[i] = tile_reward
            # Record seen tile for future matches (hash-bucket)
            self._record_seen(tile_hash, i)
            break

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

    def _normalize_reward_name(self, reward: str) -> str:
        return str(reward).strip().lower().replace("_", " ")

    def _is_preferred_reward(self, reward: Optional[str], preferred_rewards: Set[str]) -> bool:
        return reward is not None and self._normalize_reward_name(reward) in preferred_rewards

    def _should_claim_match(self, reward_a: Optional[str], reward_b: Optional[str], preferred_rewards: Set[str]) -> bool:
        """Return whether a known matching pair should be claimed now."""
        if not preferred_rewards:
            return True
        if self._is_preferred_reward(reward_a, preferred_rewards) or self._is_preferred_reward(reward_b, preferred_rewards):
            return True
        # Avoid only when at least one side was recognized as a non-preferred reward.
        # If both sides are unknown, fall back to normal match behavior.
        return reward_a is None and reward_b is None

    def _find_known_preferred_pair(self, tile_rewards: List[Optional[str]], preferred_rewards: Set[str], claimed_coords: Set[int]) -> Optional[Tuple[int, int]]:
        if not preferred_rewards:
            return None
        for _, indices in self.seen_buckets:
            candidates = [
                idx for idx in indices
                if idx not in claimed_coords and self._is_preferred_reward(tile_rewards[idx], preferred_rewards)
            ]
            if len(candidates) >= 2:
                return candidates[0], candidates[1]
        return None

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
