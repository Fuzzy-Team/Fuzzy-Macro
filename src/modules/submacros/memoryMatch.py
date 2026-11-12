import os
import random
from typing import Dict, List, Tuple, Set, Optional

import cv2
import numpy as np
from PIL import Image

import modules.controls.mouse as mouse
from modules.controls.sleep import is_stopped, pause_aware_time as time, paused_seconds, wait_while_paused
from modules.screen.screenshot import mssScreenshot, mssScreenshotNP
from modules.screen.ocr import ocrRead, readBlueText
from modules.misc.imageManipulation import adjustImage, average_hash, ImageHash
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
        self.blank_tile_hash = average_hash(Image.open("./images/menu/mmempty.png"))
        # Buckets of seen tile hashes for the current memory match game.
        # Each entry is a tuple: (ImageHash, [indices_where_seen])
        self.seen_buckets = []
        # Optional templates for identifying selected reward types.
        self.reward_templates_by_type = self._load_reward_templates()
        self.reward_templates = {}
        # Whether the last attempt count came from OCR or the DEFAULT_ATTEMPTS fallback.
        self.used_default_attempts = False

    def _click_tile(self, x: int, y: int) -> None:
        """Click on a tile at the given coordinates."""
        if wait_while_paused() or is_stopped():
            return
        mouse.moveTo(x, y, self.MOVE_DELAY)
        time.sleep(self.CLICK_DELAY)
        if is_stopped():
            return
        mouse.click()

    def _wait_for_tile_flip(self, x: int, y: int) -> ImageHash:
        """Wait for a tile to flip over, compensating for lag."""
        start_time = time.time()
        tile_hash = self.blank_tile_hash
        while not is_stopped() and time.time() - start_time < self.MAX_WAIT_TIME:
            paused_before = paused_seconds()
            if wait_while_paused():
                break
            tile_hash = self._screenshot_tile(x, y)
            if not self._are_images_similar(tile_hash, self.blank_tile_hash):
                time.sleep(self.TILE_FLIP_DELAY)
                if is_stopped():
                    break
                tile_hash = self._screenshot_tile(x, y)
                break
            # Time spent paused is not spent waiting for the flip, so it doesn't count against MAX_WAIT_TIME.
            start_time += paused_seconds() - paused_before
        return tile_hash
    
    def _are_images_similar(self, img1: ImageHash, img2: ImageHash) -> bool:
        """Check if two image hashes are similar."""
        return img1 - img2 < 2

    def _capture_tile(self, x: int, y: int) -> Image.Image:
        """Take a screenshot of a tile."""
        offset_x, offset_y = self.TILE_OFFSET
        width, height = self.TILE_SIZE
        return mssScreenshot(x + offset_x, y + offset_y, width, height)

    def _screenshot_tile(self, x: int, y: int) -> ImageHash:
        """Take a screenshot of a tile and return its hash."""
        screenshot = self._capture_tile(x, y)
        return average_hash(screenshot)

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

    def _read_chances(self, middle_x: int, middle_y: int, offset_x: int) -> Optional[int]:
        """Read the number of attempts shown next to the board, or None if unreadable."""
        try:
            cap = mssScreenshot(middle_x - 275 - offset_x, middle_y - 146, 100, 100)
            return int(''.join([x[1][0] for x in ocrRead(cap) if x[1][0].isdigit()]))
        except Exception as e:
            print(f"Error reading attempts: {e}")
            return None

    def _get_attempts_count(self, middle_x: int, middle_y: int, offset_x: int) -> int:
        """Read the number of attempts from the screen.

        Sets `used_default_attempts` so callers know whether the count came from
        OCR or fell back to DEFAULT_ATTEMPTS.
        """
        attempts_ocr = self._read_chances(middle_x, middle_y, offset_x)
        if attempts_ocr is not None and self.MIN_ATTEMPTS <= attempts_ocr <= self.MAX_ATTEMPTS:
            print(f"Number of attempts: {attempts_ocr}")
            self.used_default_attempts = False
            return attempts_ocr
        self.used_default_attempts = True
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
        mm_data: List[Optional[ImageHash]] = [None] * (grid_size[0] * grid_size[1])
        tile_rewards: List[Optional[str]] = [None] * (grid_size[0] * grid_size[1])
        
        # Get attempts count
        middle_x = self.robloxWindow.mx + self.robloxWindow.mw // 2
        middle_y = self.robloxWindow.my + self.robloxWindow.mh // 2
        if wait_while_paused() or is_stopped():
            return
        attempts = self._get_attempts_count(middle_x, middle_y, offset_x)
        used_default_attempts = self.used_default_attempts
        if is_stopped():
            return

        # Base attempts are guaranteed (5 for extreme/winter, 3 otherwise). When OCR
        # cannot read the count we fall back to DEFAULT_ATTEMPTS, so the board must be
        # re-verified once the base attempts are used. A valid OCR count already
        # includes badge bonuses, so it can be trusted without the board check.
        min_attempts = 5 if self._normalize_mm_type(mm_type) in ("extreme", "winter") else 3
        
        # Game loop
        current_attempt = 0
        while current_attempt < attempts and not is_stopped():
            print(f"Attempt {current_attempt}")

            # Only the fallback count can outlast the real board, so verify it is
            # still open before clicking any tile. Trust a valid OCR count directly.
            if used_default_attempts and current_attempt >= min_attempts:
                game_active = self._check_game_active()
                if is_stopped():
                    break
                if not game_active:
                    break
            
            target_pair = self._find_known_preferred_pair(tile_rewards, preferred_rewards, claimed_coords)
            if target_pair is not None:
                first_idx, second_idx = target_pair
                print(f"Preferred reward match found: {tile_rewards[first_idx]}")
                x1, y1 = grid_coords[first_idx]
                x2, y2 = grid_coords[second_idx]
                self._click_tile(x1 - offset_x, y1 - offset_y)
                if is_stopped():
                    break
                time.sleep(self.TURN_DELAY)
                if is_stopped():
                    break
                self._click_tile(x2 - offset_x, y2 - offset_y)
                if is_stopped():
                    break
                claimed_coords.add(first_idx)
                claimed_coords.add(second_idx)
                current_attempt += 1
                time.sleep(self.TURN_DELAY)
                if is_stopped():
                    break
                try:
                    won = self._check_for_winnings()
                except Exception:
                    won = False
                if won:
                    break
                continue

            # First tile
            first_tile_index, first_tile_hash = self._click_first_tile(
                grid_coords, checked_coords, mm_data, tile_rewards, claimed_coords, preferred_rewards, offset_x, offset_y, middle_x, middle_y
            )
            
            if first_tile_index is None:
                break
                
            time.sleep(self.TURN_DELAY)
            if is_stopped():
                break
            
            # Second tile
            consumed_attempts = self._click_second_tile(
                grid_coords, checked_coords, mm_data, tile_rewards, claimed_coords, preferred_rewards,
                first_tile_index, first_tile_hash, offset_x, offset_y, 
                middle_x, middle_y, current_attempt, attempts, used_default_attempts, min_attempts
            )
            if is_stopped():
                break
            current_attempt += consumed_attempts
            time.sleep(self.TURN_DELAY)
            if is_stopped():
                break
            # After each match attempt, do a quick check for winnings/payout UI
            try:
                won = self._check_for_winnings()
            except Exception:
                won = False
            if won:
                break

        if not is_stopped():
            self._wait_for_winnings_text()

    def _wait_for_winnings_text(self) -> None:
        """Wait for winnings text or payout background to appear."""
        bluetexts = ""
        found = False
        for _ in range(6):
            if wait_while_paused() or is_stopped():
                return
            try:
                txt = readBlueText().lower()
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
            if is_stopped():
                return
        if not is_stopped():
            time.sleep(0.2)

    def _check_for_winnings(self) -> bool:
        """Quick non-blocking check for winnings/payout UI.

        Returns True if a winnings message or payout background is detected.
        """
        try:
            txt = readBlueText().lower()
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

    def _check_game_active(self) -> bool:
        """Return whether the memory match board is still on screen."""
        if wait_while_paused() or is_stopped():
            return False
        mm_img = adjustImage("./images/menu", "mmopen", self.robloxWindow.display_type)
        return bool(locateImageOnScreen(
            mm_img, 
            self.robloxWindow.mx + self.robloxWindow.mw / 4, 
            self.robloxWindow.my + self.robloxWindow.mh / 4, 
            self.robloxWindow.mw / 4, 
            self.robloxWindow.mh / 3.5, 
            0.8
        ))

    def _click_first_tile(self, grid_coords: List[Tuple[int, int]], checked_coords: Set[Tuple[int, int]], 
                          mm_data: List[Optional[ImageHash]], tile_rewards: List[Optional[str]],
                          claimed_coords: Set[int], preferred_rewards: Set[str],
                          offset_x: int, offset_y: int, middle_x: int, middle_y: int) -> Tuple[Optional[int], Optional[ImageHash]]:
        """Click the first tile and return its index and hash."""
        for i, (x_raw, y_raw) in enumerate(grid_coords):
            if is_stopped():
                return None, None
            if (x_raw, y_raw) in checked_coords:
                continue
                
            x = x_raw - offset_x
            y = y_raw - offset_y
            
            self._click_tile(x, y)
            if is_stopped():
                return None, None
            time.sleep(0.1)
            if wait_while_paused() or is_stopped():
                return None, None
            mouse.moveTo(middle_x, middle_y - self.MOUSE_MOVE_OFFSET)  # Move mouse out of the way
            
            tile_image = self._capture_tile(x, y)
            tile_hash = average_hash(tile_image)
            if self._are_images_similar(tile_hash, self.blank_tile_hash):
                tile_hash = self._wait_for_tile_flip(x, y)
                if is_stopped():
                    return None, None
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
                          mm_data: List[Optional[ImageHash]], tile_rewards: List[Optional[str]],
                          claimed_coords: Set[int], preferred_rewards: Set[str],
                          first_tile_index: int, first_tile_hash: ImageHash, 
                          offset_x: int, offset_y: int, middle_x: int, middle_y: int, 
                          current_attempt: int, attempts: int, used_default_attempts: bool,
                          min_attempts: int) -> int:
        """Click the second tile and handle matching logic.

        Returns the number of attempts consumed: 0 when stopped, 1 for a normal
        turn, or 2 when it also claims the known match on the following turn.
        """
        if is_stopped():
            return 0
        consumed_attempts = 1
        # If we found a match on first tile, click the matching tile
        match_found = self._lookup_seen(first_tile_hash, claimed_coords, exclude_index=first_tile_index)
        if match_found is not None:
            if wait_while_paused() or is_stopped():
                return 0
            # On the last chance there is nothing left to save the pair for, so take it even if not preferred.
            if (not self._should_claim_match(tile_rewards[first_tile_index], tile_rewards[match_found], preferred_rewards)
                    and self._read_chances(middle_x, middle_y, offset_x) != 1):
                match_found = None
            else:
                print("Match found, clicking matching tile")
                x, y = grid_coords[match_found]
                self._click_tile(x - offset_x, y - offset_y)
                if is_stopped():
                    return 0
                claimed_coords.add(first_tile_index)
                claimed_coords.add(match_found)
                return 1

        # Otherwise, click a new tile
        for i, (x_raw, y_raw) in enumerate(grid_coords):
            if is_stopped():
                return 0
            if (x_raw, y_raw) in checked_coords:
                continue

            x = x_raw - offset_x
            y = y_raw - offset_y

            self._click_tile(x, y)
            if is_stopped():
                return 0
            time.sleep(0.1)
            if wait_while_paused() or is_stopped():
                return 0
            mouse.moveTo(middle_x, middle_y - self.MOUSE_MOVE_OFFSET)  # Move mouse out of the way

            tile_image = self._capture_tile(x, y)
            tile_hash = average_hash(tile_image)
            if self._are_images_similar(tile_hash, self.blank_tile_hash):
                tile_hash = self._wait_for_tile_flip(x, y)
                if is_stopped():
                    return 0
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
                        return 1
                    # Claiming this pair needs another turn. Only start it if the
                    # board has an attempt left to spend.
                    if current_attempt + 1 < attempts:
                        # Let the mismatched tiles flip back before checking the
                        # board: with the fallback attempt count the last chance
                        # can close it during that animation.
                        time.sleep(2)
                        if is_stopped():
                            return 0
                        can_claim_extra_turn = True
                        if used_default_attempts and current_attempt + 1 >= min_attempts:
                            if not self._check_game_active():
                                can_claim_extra_turn = False
                            if is_stopped():
                                return 0
                        if can_claim_extra_turn:
                            # Handle the match on the next turn
                            self._click_tile(x, y)  # Click the second tile again
                            if is_stopped():
                                return 0
                            consumed_attempts = 2
                            time.sleep(1)
                            if is_stopped():
                                return 0
                            x2, y2 = grid_coords[match_found]
                            self._click_tile(x2 - offset_x, y2 - offset_y)  # Click the matching tile
                            if is_stopped():
                                return 0
                            claimed_coords.add(i)
                            claimed_coords.add(match_found)
            mm_data[i] = tile_hash
            tile_rewards[i] = tile_reward
            # Record seen tile for future matches (hash-bucket)
            self._record_seen(tile_hash, i)
            return consumed_attempts

        return consumed_attempts

    def _record_seen(self, tile_hash: ImageHash, index: int) -> None:
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

    def _lookup_seen(self, tile_hash: ImageHash, claimed_coords: Set[int], exclude_index: Optional[int] = None) -> Optional[int]:
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
