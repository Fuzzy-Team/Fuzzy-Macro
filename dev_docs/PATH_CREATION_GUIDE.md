# Existance Macro:  Path Creation Guide

This guide explains how to create custom navigation paths for the Existance Macro.

---

## Table of Contents

1. [What are Paths?](#what-are-paths)
2. [Path Types & Directory Structure](#path-types--directory-structure)
3. [Path File Structure](#path-file-structure)
4. [Available Methods & Variables](#available-methods--variables)
5. [Path Examples](#path-examples)
6. [Best Practices](#best-practices)
7. [Testing & Debugging](#testing--debugging)
8. [Advanced Techniques](#advanced-techniques)

---

## What are Paths? 

Paths are navigation scripts that move your character from one location to another in Bee Swarm Simulator. They handle movement between: 

- Hive → Cannon → Fields
- Fields → Dispensers/Collectibles
- Field → Field (during mob runs)
- Any location → Quest givers
- Vicious Bee search and combat

Paths are stored as Python scripts (`.py`) or macOS Automator workflows (`.workflow`) in subdirectories under the `paths/` folder.

---

## Path Types & Directory Structure

```
paths/
├── cannon_to_field/     # From cannon landing spot to field center
│   ├── sunflower.py
│   ├── dandelion.py
│   ├── mushroom.py
│   └── ... 
│
├── collect/             # Navigation to dispensers and collectibles
│   ├── wealth_clock.py
│   ├── blueberry_dispenser.py
│   ├── glue_dispenser.py
│   ├── blender.py
│   └── ... 
│
├── field_to_hive/       # Return paths from fields (rarely used)
│   └── ... 
│
├── mob_runs/            # Inter-field navigation during mob runs
│   ├── clover.py
│   ├── spider.py
│   └── ...
│
├── planters/            # Planter placement locations
│   └── ...
│
├── quests/              # Quest giver navigation
│   ├── polar_bear.py
│   ├── bucko_bee.py
│   ├── riley_bee.py
│   └── ...
│
└── vic/                 # Vicious Bee hunt paths
    ├── find_vic/        # Search patterns for each field
    │   ├── pepper.py
    │   ├── rose.py
    │   ├── cactus.py
    │   └── ...
    └── kill_vic/        # Dodge/combat patterns for each field
        ├── pepper.py
        ├── rose.py
        ├── cactus.py
        └── ...
```

### Path Type Details

| Path Type | Purpose | Execution Context |
|-----------|---------|-------------------|
| **cannon_to_field** | Navigate from cannon landing to field center | After `cannon()` is called |
| **collect** | Walk to dispensers/collectibles | From spawn or after `cannon()` |
| **field_to_hive** | Return from field to hive | Rarely used (reset is preferred) |
| **mob_runs** | Move between areas during mob combat | After killing mob in field |
| **planters** | Position for planter placement | During planter cycles |
| **quests** | Navigate to quest givers | During quest routines |
| **vic/find_vic** | Search field for Vicious Bee | During stinger hunt |
| **vic/kill_vic** | Dodge Vicious Bee attacks | During Vicious Bee combat |

---

## Path File Structure

### Python Paths (. py)

Paths are Python scripts with access to the macro instance:

```python
# Basic path structure
# Available:  self, ws (walk speed)

# Navigate to location
self.keyboard.walk("w", 2.5)
self.keyboard.walk("d", 1.0)
self.keyboard.walk("w", 1.8)

# Adjust camera if needed
for _ in range(2):
    self.keyboard.press(".")
```

### Automator Workflows (.workflow) - macOS Only

- Place `.workflow` files in path directories
- Macro prioritizes `.workflow` over `.py` if both exist
- Only works on macOS
- Most users should use Python paths for cross-platform compatibility

### File Naming Convention

Path files must match the field or collectible name (lowercase with underscores):

```python
# Field paths
sunflower.py          # For "Sunflower" field
blue_flower.py        # For "Blue Flower" field
mountain_top.py       # For "Mountain Top" field

# Collectible paths
wealth_clock.py       # For Wealth Clock
blueberry_dispenser.py # For Blueberry Dispenser
ant_pass_dispenser.py  # For Ant Pass Dispenser
```

---

## Available Methods & Variables

### Variables in Path Namespace

```python
self        # The macro instance (access all macro methods)
ws          # Walk speed from settings (self.setdat["movespeed"])
```

### Essential Macro Methods

#### Movement

```python
# Walk in single direction
self.keyboard.walk(key, duration)
# Examples:
self.keyboard.walk("w", 2.5)      # Walk forward 2.5 seconds
self.keyboard.walk("a", 1.0)      # Walk left 1 second

# Walk in multiple directions simultaneously (diagonal)
self.keyboard.multiWalk([keys], duration)
# Examples:
self.keyboard.multiWalk(["w", "a"], 1.5)  # Walk diagonally forward-left
self.keyboard.multiWalk(["s", "d"], 2.0)  # Walk diagonally backward-right

# Press key once
self.keyboard.press(key)
# Examples:
self.keyboard.press(".")          # Rotate camera right
self.keyboard.press("space")      # Jump
```

#### Camera Control

```python
self.keyboard.press(",")          # Rotate left
self.keyboard.press(".")          # Rotate right
self. keyboard.press("pageup")     # Rotate up
self.keyboard.press("pagedown")   # Rotate down
self.keyboard.press("i")          # Zoom in
self.keyboard.press("o")          # Zoom out
```

#### Timing & Sleeps

```python
sleep(seconds)                    # Pause execution
# Example:
sleep(0.5)                        # Wait 0.5 seconds
```

#### Move Speed Adjustments

```python
# Account for different move speeds
moveSpeedFactor = 18 / self.setdat["movespeed"]
self.keyboard.walk("w", 2.0 * moveSpeedFactor)
```

### Special Variables for Vicious Bee Paths

In `vic/find_vic/` paths, a special function is available:

```python
vicSearchWalk(key, duration)      # Walk with Vic detection interrupt
# The macro provides this function - it stops path if Vic is found
```

---

## Path Examples

### Example 1: Simple Cannon-to-Field Path

**File:** `paths/cannon_to_field/sunflower.py`

```python
# Path from cannon landing to Sunflower Field center
# Sunflower is close to spawn, simple path

self.keyboard.walk("w", 1.5)
self.keyboard.walk("a", 0.8)
self.keyboard.walk("w", 3.2)
```

**How it works:**
1. Land from cannon
2. Walk forward toward field
3. Walk left to align
4. Walk forward into field center

---

### Example 2: Collect Path with Camera Adjustment

**File:** `paths/collect/wealth_clock.py`

```python
# Navigate to Wealth Clock dispenser from spawn
# Includes camera rotation to face dispenser

# Walk to clock area
self.keyboard.walk("w", 4.0)
self.keyboard.walk("d", 2.5)
self.keyboard.walk("w", 1.0)

# Rotate camera to face dispenser (optional but helpful)
for _ in range(2):
    self.keyboard.press(".")

# Small adjustment for final positioning
self.keyboard.walk("w", 0.3)
```

**How it works:**
1. Walk from spawn toward clock
2. Turn right to approach
3. Walk forward to clock
4. Rotate camera to face dispenser
5. Fine-tune position

---

### Example 3: Complex Multi-Stage Path

**File:** `paths/collect/blender.py`

```python
# Navigate to Blender (requires climbing ramps)
# Complex path with elevation changes

# Initial approach
self.keyboard.walk("w", 3.0)
self.keyboard.walk("d", 4.5)

# Climb first ramp (requires multiple movements)
for _ in range(3):
    self.keyboard.walk("w", 1.0)
    sleep(0.1)  # Brief pause for stability

# Navigate platform
self.keyboard.walk("d", 1.5)
self.keyboard.walk("w", 2.0)

# Climb second ramp
for _ in range(2):
    self.keyboard.walk("w", 0.8)
    sleep(0.1)

# Final positioning at blender
self.keyboard.walk("d", 0.5)
self.keyboard.walk("w", 1.2)
```

**How it works:**
1. Walk from spawn to base of ramps
2. Climb first ramp with controlled movements
3. Navigate across platform
4. Climb second ramp
5. Position at blender interface

---

### Example 4: Mob Run Inter-Field Path

**File:** `paths/mob_runs/clover.py`

```python
# Walk between Clover Field sections during mob runs
# Helps collect loot across entire field

# Move to opposite corner
self.keyboard.walk("w", 2.0)
self.keyboard.walk("d", 1.5)

# Sweep back
self.keyboard.walk("s", 2.5)
self.keyboard.walk("a", 1.5)
```

**How it works:**
- After killing mob in one area, sweep to other areas
- Collects any missed loot tokens
- Optional (macro works without these paths)

---

### Example 5: Quest Giver Path

**File:** `paths/quests/polar_bear.py`

```python
# Navigate to Polar Bear (in far corner of map)
# Long path requiring multiple stages

# Exit spawn area
self.keyboard.walk("w", 5.0)

# Navigate to far side of map
self.keyboard.walk("a", 8.0)
self.keyboard.walk("w", 10.0)

# Approach Polar Bear area
self.keyboard.walk("d", 2.0)
self.keyboard.walk("w", 3.0)

# Fine positioning
self.keyboard.walk("a", 0.5)
```

**How it works:**
1. Leave spawn heading forward
2. Walk left toward far corner
3. Walk forward to Polar Bear area
4. Approach and position near NPC

---

### Example 6: Vicious Bee Search Path

**File:** `paths/vic/find_vic/pepper. py`

```python
# Search pattern for Vicious Bee in Pepper Patch
# Uses special vicSearchWalk function

# Sweep pattern across field
vicSearchWalk("w", 2.0)
vicSearchWalk("d", 1.0)
vicSearchWalk("s", 4.0)
vicSearchWalk("d", 1.0)
vicSearchWalk("w", 4.0)
vicSearchWalk("d", 1.0)
vicSearchWalk("s", 4.0)
vicSearchWalk("d", 1.0)
vicSearchWalk("w", 4.0)

# Continue sweeping... 
vicSearchWalk("a", 3.0)
vicSearchWalk("s", 2.0)
```

**How it works:**
- `vicSearchWalk()` interrupts if Vicious Bee is detected
- Sweeps back and forth across field
- Covers entire field systematically

---

### Example 7: Vicious Bee Combat Path

**File:** `paths/vic/kill_vic/rose.py`

```python
# Dodge pattern for Vicious Bee in Rose Field
# Macro executes line-by-line, checking for defeat/death

# Circular dodge pattern
self.keyboard.walk("w", 2.0)
self.keyboard.walk("a", 1.5)
self.keyboard.walk("s", 2.0)
self.keyboard.walk("d", 1.5)

# Figure-8 pattern
for _ in range(2):
    self.keyboard.walk("w", 1.5)
    self.keyboard.press(".")  # Rotate while moving
    sleep(0.1)
    self.keyboard.walk("w", 1.5)
    self.keyboard.press(",")
    sleep(0.1)

# Side-to-side dodging
for _ in range(3):
    self.keyboard.walk("a", 1.0)
    self.keyboard.walk("d", 1.0)
```

**How it works:**
- Keeps character moving to avoid Vicious Bee attacks
- Macro checks after each line if Vic is defeated or player died
- Repeats pattern until combat ends

---

### Example 8: Move Speed Adjusted Path

**File:** `paths/cannon_to_field/mountain_top.py`

```python
# Navigate to Mountain Top (far field)
# Adjusts for different move speed settings

# Calculate move speed adjustment
moveSpeedFactor = 18 / self.setdat["movespeed"]

# Long journey with speed adjustment
self.keyboard.walk("w", 8.0 * moveSpeedFactor)
self.keyboard.walk("d", 3.0 * moveSpeedFactor)
self.keyboard.walk("w", 5.0 * moveSpeedFactor)

# Climb mountain
for _ in range(5):
    self.keyboard.walk("w", 1.5 * moveSpeedFactor)
    sleep(0.2)

# Final positioning
self.keyboard. walk("w", 2.0 * moveSpeedFactor)
```

**How it works:**
- Calculates scaling factor based on move speed
- All walk durations scale proportionally
- Works correctly regardless of speed settings

---

## Best Practices

### 1. Start from Known Positions

**Cannon-to-Field Paths:**
- Always start from cannon landing position
- Macro calls `cannon()` before these paths

**Collect Paths:**
- Usually start from spawn (after `cannon()`)
- Sometimes start from specific field (check macro code)

**Quest Paths:**
- Start from spawn after `cannon()`

### 2. Keep Paths Simple

```python
# ✅ GOOD - Direct, simple path
self.keyboard.walk("w", 3.0)
self.keyboard.walk("d", 2.0)
self.keyboard.walk("w", 1.5)

# ❌ BAD - Overly complex with unnecessary movements
self.keyboard.walk("w", 1.0)
self.keyboard.walk("d", 0.5)
self.keyboard.walk("w", 0.5)
self.keyboard.walk("d", 0.5)
self.keyboard.walk("w", 1.0)
self.keyboard.walk("d", 0.5)
self.keyboard.walk("w", 0.5)
```

### 3. Test with Different Configurations

Test paths with: 
- Different hive numbers (1-6)
- Different move speeds
- Lag/lower FPS
- Day and night time

### 4. Don't Include Verification

```python
# ❌ BAD - Don't add verification in paths
self.keyboard.walk("w", 3.0)
if not self.isBesideE(["wealth", "clock"]):
    self.keyboard.walk("w", 1.0)

# ✅ GOOD - Just navigation
self.keyboard.walk("w", 3.0)
# Macro handles verification after path
```

### 5. Account for Elevation Changes

```python
# For ramps, stairs, hills:
# Use shorter segments with pauses

# Climbing ramp
for _ in range(3):
    self.keyboard.walk("w", 1.0)
    sleep(0.1)  # Stability pause

# Going down stairs
self.keyboard.walk("s", 2.0)
sleep(0.2)  # Let character land
```

### 6. Add Helpful Comments

```python
# Exit spawn platform
self.keyboard.walk("w", 2.0)

# Cross bridge to main area
self.keyboard.walk("w", 5.0)

# Navigate around obstacle
self.keyboard.walk("d", 1.5)

# Final approach to dispenser
self.keyboard.walk("w", 2.5)
```

### 7. Use Diagonal Movement When Appropriate

```python
# Instead of: 
self.keyboard.walk("w", 2.0)
self.keyboard.walk("d", 2.0)

# More efficient: 
self.keyboard.multiWalk(["w", "d"], 2.0)
```

### 8. Measure Distances Incrementally

Build paths gradually: 

```python
# Start with rough estimates
self.keyboard.walk("w", 3.0)  # Test - too short
self.keyboard.walk("w", 5.0)  # Test - too far
self.keyboard.walk("w", 4.0)  # Test - just right! 

# Then refine
self.keyboard.walk("w", 4.2)  # Perfect
```

### 9. Optional Paths

Some paths are optional:

```python
# In macro code:
self.runPath(f"mob_runs/{field}", fileMustExist=False)
# If path doesn't exist, macro continues without error
```

For optional paths: 
- Create only if needed
- Test without path first
- Add only if it improves efficiency

### 10. Handle Field-Specific Cases

```python
# If path behavior varies by field:
# (Usually not needed, but possible)

# Get current field from macro
field = self.location

if field == "bamboo":
    self.keyboard. walk("w", 3.0)
elif field == "pine tree":
    self.keyboard.walk("w", 2.5)
else:
    self.keyboard.walk("w", 2.8)
```

---

## Testing & Debugging

### Manual Path Testing

Test paths directly from Python console or test script:

```python
# Create macro instance
macro = MacroInstance(...)

# Test cannon-to-field path
macro.cannon()
macro.runPath("cannon_to_field/sunflower")

# Test collect path
macro. cannon()
macro.runPath("collect/wealth_clock")
```

### Check End Position

After running path: 

1. **For collect paths**: Check if player is beside dispenser
   ```python
   # Macro will verify: 
   reached = self.isBesideE(["wealth", "clock"])
   ```

2. **For field paths**: Check if player is in field center
   - Observe where character ends up
   - Should be near center of field

3. **For quest paths**: Check if E prompt appears
   ```python
   # Macro will verify:
   reached = self.isBesideE(["talk", "polar", "bear"])
   ```

### Adjust Timings

If path over/undershoots: 

```python
# Undershoots (too short)
self.keyboard.walk("w", 3.0)  # Original
self.keyboard.walk("w", 3.5)  # Add 0.5 seconds

# Overshoots (too far)
self.keyboard.walk("w", 3.0)  # Original
self.keyboard.walk("w", 2.5)  # Subtract 0.5 seconds
```

Make small adjustments (0.1-0.3 seconds) and re-test.

### Test with Different Move Speeds

```python
# Test with slower move speed
self.setdat["movespeed"] = 12

# Test with faster move speed
self.setdat["movespeed"] = 24

# If path fails, add speed adjustment: 
moveSpeedFactor = 18 / self.setdat["movespeed"]
self.keyboard.walk("w", 3.0 * moveSpeedFactor)
```

### Use Screen Recording

1. Enable screen recording/streaming in macro
2. Record path execution
3. Review frame-by-frame
4. Identify exact failure point
5. Adjust specific segment

### Common Path Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| Path overshoots | Walk duration too long | Decrease walk times |
| Path undershoots | Walk duration too short | Increase walk times |
| Character gets stuck | Obstacle in path | Add navigation around obstacle |
| Path works on one hive but not others | Hive-specific positioning | Macro handles this before path |
| Path fails at night | Visual navigation | Paths should work day/night |
| Path fails with lag | Timing-dependent movements | Add small sleeps, make more forgiving |

### Debug with Logs

Add temporary debug output:

```python
# Before path
print("Starting path to Wealth Clock")

# During path
self.keyboard.walk("w", 3.0)
print("Walked forward 3.0 seconds")

self.keyboard.walk("d", 2.0)
print("Walked right 2.0 seconds")

# After path
print("Path complete")
```

---

## Advanced Techniques

### Dynamic Path Adjustment

```python
# Adjust based on game state
if self.night:
    # Slower at night
    duration = 3.0 * 1.1
else:
    duration = 3.0

self.keyboard.walk("w", duration)
```

### Conditional Navigation

```python
# Different paths based on configuration
if self.setdat["hive_number"] <= 3:
    # Left side hives
    self.keyboard.walk("a", 2.0)
else:
    # Right side hives
    self.keyboard.walk("d", 2.0)
```

### Reusable Path Segments

Create helper functions for common sequences:

```python
# Define reusable segment
def crossBridge():
    self.keyboard.walk("w", 5.0)
    self.keyboard.walk("d", 0.5)
    self.keyboard.walk("w", 2.0)

# Use in path
crossBridge()
self.keyboard.walk("w", 3.0)
```

### Camera-Relative Navigation

Maintain orientation during complex paths:

```python
# Reset camera to known position
for _ in range(4):
    self.keyboard.press("pageup")

# Navigate with known camera angle
self.keyboard.walk("w", 3.0)
self.keyboard.press(".")  # Turn 45° right
self.keyboard.walk("w", 2.0)
```

### Handling Interrupts in Vic Paths

Vic search paths need special handling:

```python
# In find_vic paths:
# Check if Vic found between movements
try:
    vicSearchWalk("w", 2.0)
    vicSearchWalk("d", 1.0)
    vicSearchWalk("s", 2.0)
except VicStopPathException:
    # Vic found, path will exit
    pass
```

---

## Path Troubleshooting

### Path Not Executing

**Check file name:**
```python
# File must match field/collectible name exactly
sunflower. py        # ✅ Correct
Sunflower.py        # ❌ Wrong case
sun_flower.py       # ❌ Wrong format
```

**Check file location:**
```python
paths/cannon_to_field/sunflower.py  # ✅ Correct location
paths/sunflower.py                   # ❌ Wrong location
```

### Path Partially Works

**Check for syntax errors:**
```python
# Missing colon
for _ in range(3)
    self.keyboard.walk("w", 1.0)  # ❌ Error

# Correct
for _ in range(3):
    self.keyboard.walk("w", 1.0)  # ✅ OK
```

**Check indentation:**
```python
# Wrong indentation
for _ in range(3):
self.keyboard.walk("w", 1.0)  # ❌ Error

# Correct indentation
for _ in range(3):
    self.keyboard.walk("w", 1.0)  # ✅ OK
```

### Path Fails Verification

**Adjust final positioning:**
```python
# Path ends too far from target
self.keyboard.walk("w", 5.0)

# Add fine adjustment
self.keyboard.walk("w", 5.0)
self.keyboard.walk("w", 0.5)  # Extra 0.5s to reach E prompt
```

---

## Contributing Paths

### Before Submitting

1. **Test thoroughly**: 
   - Test 10+ times
   - Test from full stop
   - Test with different move speeds
   - Test day and night

2. **Verify success rate**:
   - Should succeed 95%+ of time
   - Note any failure conditions

3. **Document**:
   - Add comments explaining path
   - Note any special requirements

4. **Follow conventions**:
   - Use standard file naming
   - Place in correct directory
   - Keep code clean and simple

### Submission Template

```python
"""
Path: [Path Name]
Type: [cannon_to_field / collect / mob_run / etc.]
Description: [What this path does]
Start Position: [Where path begins]
End Position: [Where path ends]
Requirements: [Any special requirements]
Tested: [Yes/No and conditions]
Author: [Your Name]
Date: [Creation Date]
"""

# Path code here
```

---

## Additional Resources

- **Existing Paths**: Browse `paths/` directory for examples
- **Discord Community**: Get help at https://discord.gg/3qf8bgqCVu
- **Documentation**: https://existance-macro.gitbook.io/existance-macro-docs/
- **Video Guides**: Check Discord for path creation videos

---

## Credits

- **Macro Developers**:  Existance, Sev, Logan
- **Path System**: Inspired by Natro Macro
- **Community Contributors**: Many paths created by community members

---

**Happy path creating!  🐝**
