# Existance Macro:  Pattern & Path Creation Guide

This guide explains how to create custom gathering patterns and navigation paths for the Existance Macro.

---

## Table of Contents

1. [Patterns](#patterns)
   - [What are Patterns?](#what-are-patterns)
   - [Pattern File Structure](#pattern-file-structure)
   - [Available Variables](#available-variables)
   - [Pattern Examples](#pattern-examples)
   - [Best Practices](#best-practices)
2. [Paths](#paths)
   - [What are Paths?](#what-are-paths)
   - [Path Types](#path-types)
   - [Path File Structure](#path-file-structure)
   - [Path Examples](#path-examples)
3. [Testing & Debugging](#testing--debugging)
4. [Converting AHK Patterns](#converting-ahk-patterns)

---

## Patterns

### What are Patterns?

Patterns define the movement your character performs while gathering in fields. They determine how efficiently you collect pollen from flowers.  Patterns are Python scripts located in `settings/patterns/`.

### Pattern File Structure

Patterns are `.py` files that execute within the macro's gather function context. Basic structure:

```python
# Size conversion (standard for all patterns)
if sizeword.lower() == "xs":
    size = 0.5
elif sizeword.lower() == "s":
    size = 1
elif sizeword.lower() == "l":
    size = 2
elif sizeword. lower() == "xl":
    size = 2.5
else:
    size = 1.5  # Default:  M

# Pattern movement logic
self.keyboard.walk(tcfbkey, 0.5 * size)
for _ in range(width):
    self.keyboard.walk(tclrkey, 0.17)
    self.keyboard.walk(afcfbkey, 0.5 * size)
```

### Available Variables

When your pattern executes, these variables are available in the namespace:

#### Movement Keys
```python
tcfbkey     # True camera forward/backward key (affected by invert_fb)
afcfbkey    # Alternate forward/backward key (opposite of tcfbkey)
tclrkey     # True camera left/right key (affected by invert_lr)
afclrkey    # Alternate left/right key (opposite of tclrkey)

# Base keys (unaffected by inversions)
fwdkey      # "w" - forward
backkey     # "s" - backward
leftkey     # "a" - left
rightkey    # "d" - right
```

#### Camera Controls
```python
rotleft     # "," - rotate camera left
rotright    # "." - rotate camera right
rotup       # "pageup" - rotate camera up
rotdown     # "pagedown" - rotate camera down
zoomin      # "i" - zoom in
zoomout     # "o" - zoom out
sc_space    # "space" - space key
```

#### Pattern Settings
```python
size        # Float:  Calculated from sizeword (XS=0.5, S=1, M=1.5, L=2, XL=2.5)
sizeword    # String: "XS", "S", "M", "L", or "XL" from GUI
width       # Integer: 1-8, number of pattern repetitions from GUI
```

#### Macro Methods
```python
self.keyboard.walk(key, duration)        # Walk in direction for duration seconds
self.keyboard.multiWalk([keys], duration) # Walk multiple directions simultaneously
self.keyboard.press(key)                 # Press key once
sleep(seconds)                           # Sleep for specified time
```

### Pattern Examples

#### Example 1: Simple E Pattern (e_lol.py)
```python
if sizeword.lower() == "xs":
    size = 0.5
elif sizeword. lower() == "s":
    size = 1
elif sizeword.lower() == "l":
    size = 2
elif sizeword.lower() == "xl":
    size = 2.5
else:
    size = 1.5

# Move back to start position
self.keyboard. walk(afcfbkey, 0.5 * size)

# Top horizontal line
for _ in range(width):
    self.keyboard.walk(tclrkey, 0.17)
    self.keyboard.walk(tclrkey, 0.17)

# Downward zigzag (first half of E)
for _ in range(width):
    self.keyboard.walk(tcfbkey, 0.5 * size)
    self.keyboard.walk(afclrkey, 0.17)
    self.keyboard.walk(afcfbkey, 0.5 * size)
    self.keyboard.walk(afclrkey, 0.17)

# Middle horizontal line
self.keyboard.walk(tcfbkey, 0.5 * size)
for _ in range(width):
    self.keyboard. walk(tclrkey, 0.17)
    self.keyboard.walk(tclrkey, 0.17)

# Downward zigzag (second half of E)
for _ in range(width):
    self.keyboard. walk(afcfbkey, 0.5 * size)
    self.keyboard.walk(afclrkey, 0.17)
    self.keyboard.walk(tcfbkey, 0.5 * size)
    self.keyboard.walk(afclrkey, 0.17)
```

#### Example 2: Bambe Pattern (bambe.py)
```python
# Size conversion
if sizeword.lower() == "xs":
    size = 0.25
elif sizeword.lower() == "s":
    size = 0.5
elif sizeword.lower() == "l":
    size = 1
elif sizeword.lower() == "xl":
    size = 1.25
else:
    size = 0.75

size = size / 5. 5

# Setup walk function compatibility
nm_walk = self.keyboard.walk
fwdkey = tcfbkey
backkey = afcfbkey
leftkey = tclrkey
rightkey = afclrkey

# Position at start
nm_walk(rightkey, 13 * size)
nm_walk(backkey, 9 * size)
nm_walk(leftkey, 4.5 * size)
nm_walk(fwdkey, 6 * size)

# Main pattern loop
for i in range(width):
    nm_walk(fwdkey, 9 * size)
    nm_walk(leftkey, 2 * size)
    nm_walk(backkey, 9 * size)
    nm_walk(leftkey, 2 * size)
    nm_walk(fwdkey, 9 * size)
    nm_walk(leftkey, 2 * size)
    nm_walk(backkey, 9 * size)
    nm_walk(leftkey, 2 * size)
     
    nm_walk(fwdkey, 9 * size)
    nm_walk(rightkey, 2 * size)
    nm_walk(backkey, 9 * size)
    nm_walk(rightkey, 2 * size)
    nm_walk(fwdkey, 9 * size)
    nm_walk(rightkey, 2 * size)
    nm_walk(backkey, 9 * size)
    nm_walk(rightkey, 2 * size)
```

#### Example 3: Bowl Pattern with Camera Rotation (bowl.py)
```python
# Configuration
digistops = False  # Set True for Digital Bee
passivefdc = 0.3   # Field drift compensation

# Variables
stepsize = 3
rightdrift = 2
rightoff = 2
downdrift = 1
downoff = 3

# Size conversion
if sizeword.lower() == "xs":
    size = 0.5
elif sizeword.lower() == "s":
    size = 1
elif sizeword.lower() == "l":
    size = 2
elif sizeword.lower() == "xl":
    size = 2.5
else:
    size = 1.5

sizemulti = 1/10 * 1.2
size *= sizemulti
passivefdc *= sizemulti

# Rotate camera up
for _ in range(4):
    self.keyboard.press(rotup)

# Pattern movement with camera rotations
self.keyboard.walk(backkey, stepsize * size)
self.keyboard.walk(rightkey, stepsize * size)
self.keyboard.walk(fwdkey, stepsize * size)

# Rotate left
self.keyboard.press(rotleft)
self.keyboard.press(rotleft)
sleep(0.05)

# Compensation movements
self.keyboard.walk(backkey, (rightdrift + rightoff) * sizemulti)
self.keyboard.walk(fwdkey, rightoff * sizemulti)
if digistops:  
    sleep(0.8)

# Rotate back right
self.keyboard.press(rotright)
self.keyboard.press(rotright)
sleep(0.05)

self.keyboard.walk(leftkey, stepsize * size * 2)
if digistops: 
    sleep(0.85)

# Diagonal movements
self.keyboard.press(rotleft)
sleep(0.05)
self.keyboard.multiWalk([backkey, leftkey], stepsize * size)
self.keyboard.multiWalk([backkey, rightkey], stepsize * size)
self.keyboard.multiWalk([fwdkey, rightkey], stepsize * size * 2)
```

### Best Practices

1. **Always Include Size Handling**
   ```python
   if sizeword. lower() == "xs":
       size = 0.5
   elif sizeword.lower() == "s":
       size = 1
   # ... etc
   ```

2. **Scale All Movements by Size**
   ```python
   self.keyboard.walk(tcfbkey, 0.5 * size)  # Good
   self.keyboard.walk(tcfbkey, 0.5)         # Bad - ignores size
   ```

3. **Use Width for Repetitions**
   ```python
   for _ in range(width):
       # Pattern movements
   ```

4. **Use Inverted Keys for Pattern Logic**
   - Use `tcfbkey`/`afcfbkey` instead of `fwdkey`/`backkey`
   - Use `tclrkey`/`afclrkey` instead of `leftkey`/`rightkey`
   - This respects the "Invert L/R" and "Invert F/B" settings

5. **Test Multiple Sizes**
   - Test XS, S, M, L, XL to ensure pattern scales correctly
   - Adjust size multipliers if needed

6. **Add Comments**
   ```python
   # Position character at pattern start
   self.keyboard.walk(afcfbkey, 0.5 * size)
   
   # Top horizontal line of E shape
   for _ in range(width):
       self.keyboard.walk(tclrkey, 0.17)
   ```

7. **Handle Special Cases**
   ```python
   # For Digital Bee users - add pause after turns
   if digistops: 
       sleep(0.8)
   ```

---

## Paths

### What are Paths?

Paths are navigation scripts that move your character from one location to another (e.g., hive to field, field to dispenser, etc.). They're stored in subdirectories under `paths/`.

### Path Types

The macro uses several path categories:

```
paths/
├── cannon_to_field/     # From cannon landing to field center
├── collect/             # Navigation to dispensers/collectibles
├── field_to_hive/       # Return paths from fields (rarely used)
├── mob_runs/            # Inter-field navigation during mob runs
├── planters/            # Planter placement locations
├── quests/              # Quest giver navigation
└── vic/                 # Vicious Bee hunt paths
    ├── find_vic/        # Search patterns per field
    └── kill_vic/        # Dodge patterns per field
```

### Path File Structure

Paths can be either: 
1. **Python scripts (. py)** - Cross-platform
2. **Automator workflows (.workflow)** - macOS only (prioritized if both exist)

#### Python Path Format
```python
# Available in path namespace: 
# - self:  The macro instance
# - ws: Walk speed from settings (self.setdat["movespeed"])

# Basic movement
self.keyboard.walk("w", 2. 5)
self.keyboard.walk("d", 1.0)

# Complex movements
self.keyboard.multiWalk(["w", "a"], 1.5)  # Walk diagonally

# Camera adjustments
self.keyboard.press(".")  # Rotate right
self.keyboard.press(",")  # Rotate left

# Timing adjustments based on move speed
moveSpeedFactor = 18 / self.setdat["movespeed"]
self.keyboard.walk("w", 2.0 * moveSpeedFactor)
```

### Path Examples

#### Example 1: Cannon to Field (cannon_to_field/sunflower. py)
```python
# Path from cannon landing to Sunflower Field center
self.keyboard.walk("w", 1.5)
self.keyboard.walk("a", 0.8)
self.keyboard.walk("w", 3.2)
```

#### Example 2: Collect Path (collect/wealth_clock.py)
```python
# Navigate to Wealth Clock dispenser
self.keyboard. walk("w", 4.0)
self.keyboard.walk("d", 2.5)
self.keyboard.walk("w", 1.0)

# Face the dispenser (optional camera rotation)
for _ in range(2):
    self.keyboard.press(".")
```

#### Example 3: Mob Run Path (mob_runs/clover.py)
```python
# Walk between clover field sections during mob runs
self.keyboard.walk("w", 2.0)
self.keyboard.walk("d", 1.5)
self.keyboard.walk("s", 1.0)
```

#### Example 4: Complex Collect Path (collect/blender.py)
```python
# Navigate to Blender (complex multi-stage path)
self.keyboard.walk("w", 3.0)
self.keyboard.walk("d", 4.5)

# Climb ramp
for _ in range(3):
    self.keyboard.walk("w", 1.0)
    sleep(0.1)

# Final positioning
self.keyboard.walk("d", 0.5)
self.keyboard.walk("w", 2.0)
```

#### Example 5: Vicious Bee Search Path (vic/find_vic/dandelion.py)
```python
# Search pattern for Vicious Bee in Dandelion Field
# Uses custom walk function with interrupts

def vicSearchWalk(key, t):
    # This function is provided by stingerHunt()
    # It allows stopping mid-path if Vicious Bee is found
    pass

# Search pattern - back and forth sweeps
vicSearchWalk("w", 2.0)
vicSearchWalk("d", 1.0)
vicSearchWalk("s", 4.0)
vicSearchWalk("d", 1.0)
vicSearchWalk("w", 4.0)
vicSearchWalk("d", 1.0)
vicSearchWalk("s", 4.0)
```

#### Example 6: Vicious Bee Kill Path (vic/kill_vic/clover.py)
```python
# Dodge pattern for Vicious Bee in Clover Field
# The macro executes this line-by-line and checks for defeat/death

# Move in evasive pattern
self.keyboard. walk("w", 2.0)
self.keyboard.walk("a", 1.5)
self.keyboard.walk("s", 2.0)
self.keyboard.walk("d", 1.5)

# Circle pattern
for _ in range(4):
    self.keyboard.walk("w", 1.0)
    self.keyboard.press(".")  # Rotate camera
    sleep(0.1)
```

### Path Creation Tips

1. **Start from Cannon for Field Paths**
   - All field paths start from where you land after using the cannon
   - The macro uses `cannon()` then `goToField()` which runs these paths

2. **Measure Distances**
   - Test walk times incrementally
   - Account for different move speeds (default is 18)
   - Use `moveSpeedFactor = 18 / self.setdat["movespeed"]` for scaling

3. **Keep Paths Simple**
   - Break complex navigation into segments
   - Avoid unnecessary movements
   - Don't include verification logic (macro handles that)

4. **Test in Different Scenarios**
   - Test from full stop
   - Test with different hive numbers (positioning varies)
   - Test with lag/lower FPS

5. **Use Comments**
   ```python
   # Exit hive platform
   self.keyboard.walk("w", 1.0)
   
   # Cross bridge
   self.keyboard.walk("w", 3.5)
   
   # Enter field area
   self.keyboard.walk("d", 2.0)
   ```

6. **Optional Paths**
   - Not all paths need to exist
   - Mob run paths are optional (only if you need inter-field movement)
   - The macro checks `fileMustExist` parameter:  `self.runPath(f"mob_runs/{field}", fileMustExist=False)`

---

## Testing & Debugging

### Testing Patterns

1. **Enable a Test Field**
   - Set a field to use your pattern in the GUI
   - Set gathering time to 1-2 minutes for quick tests
   - Enable only that field

2. **Watch the Pattern Execute**
   - Start the macro
   - Observe if the pattern covers the field well
   - Check for drift or missed areas

3. **Adjust Size Scaling**
   - If pattern is too large/small, adjust size multipliers: 
   ```python
   size = size * 0.8  # Make pattern 20% smaller
   ```

4. **Test All Sizes**
   ```python
   # Test command in terminal or adjust GUI: 
   # XS, S, M, L, XL
   ```

5. **Check Pattern Output**
   - Look for errors in logs/terminal
   - Pattern errors appear as:  "Incompatible pattern" webhook

### Testing Paths

1. **Manual Testing**
   ```python
   # In main. py or test script: 
   macro_instance.cannon()
   macro_instance.runPath("cannon_to_field/sunflower")
   ```

2. **Check End Position**
   - Does the path end at the intended location?
   - Is verification successful?  (for collect paths)

3. **Adjust Timings**
   - Add/subtract walk time in small increments (0.1-0.2s)
   - Test with different move speeds if needed

4. **Use Screen Recording**
   - Record path execution
   - Review frame-by-frame if needed

### Common Issues

**Pattern Issues:**
- **Pattern too large/small**: Adjust size multipliers
- **Pattern doesn't respect inversions**: Use `tcfbkey`/`tclrkey` not `fwdkey`/`leftkey`
- **Error on execution**: Check for syntax errors, missing variables
- **Drift during pattern**: Add `if fieldSetting["field_drift_compensation"]:  self.fieldDriftCompensation. run()` between loops

**Path Issues:**
- **Overshooting/undershooting**: Adjust walk times
- **Path fails verification**: Make sure you end at exact location
- **Path differs by hive number**: Paths are universal; macro handles hive-specific movement before paths

---

## Converting AHK Patterns

The macro includes an automatic AHK-to-Python converter for Natro Macro patterns. 

### Automatic Conversion

Place `.ahk` pattern files in `settings/patterns/`. On startup: 
```python
# Macro automatically converts . ahk files to . py
ahkPatterns = [x for x in os.listdir(patterns_dir) if ".ahk" in x]
for pattern in ahkPatterns: 
    python = ahkPatternToPython(ahk)
    # Saves as .py file
```

### Manual Conversion

If automatic conversion fails, convert manually:

**AHK to Python Equivalents:**
```ahk
; AHK
Send {w down}
Sleep 1000
Send {w up}
```
```python
# Python
self.keyboard.walk("w", 1.0)
```

```ahk
; AHK
Loop %reps%
{
    ; Movement
}
```
```python
# Python
for i in range(width):
    # Movement
```

```ahk
; AHK
nm_Walk(2, FwdKey)
```
```python
# Python
self.keyboard.walk(tcfbkey, 2)
```

**Common Replacements:**
- `reps` → `width`
- `a_index` → `i`
- `&&` → `and`
- `||` → `or`
- `;` → `#`
- `:=` → `=`
- `sqrt` → `math.sqrt`

### Conversion Example

**Before (AHK):**
```ahk
Loop %reps%
{
    Send {w down}
    Sleep 500
    Send {w up}
    Send {a down}
    Sleep 200
    Send {a up}
}
```

**After (Python):**
```python
for i in range(width):
    self.keyboard.walk("w", 0.5)
    self.keyboard.walk("a", 0.2)
```

---

## Additional Resources

- **Pattern Inspiration**: Check existing patterns in `settings/patterns/`
- **Natro Macro Patterns**: Many patterns are compatible (with conversion)
- **Discord Community**: Share patterns and get help at https://discord.gg/3qf8bgqCVu
- **Documentation**: https://existance-macro.gitbook.io/existance-macro-docs/

---

## Contributing

If you create useful patterns or paths: 

1. Test thoroughly across different fields/scenarios
2. Add clear comments explaining the pattern logic
3. Include size handling and width support
4. Share in the Discord community
5. Consider submitting a pull request

---

## Credits

- **Pattern System**: Inspired by Natro Macro
- **Pattern Makers**: Existance, NatroTeam, tvojamamkajenic, sev, dully176, chillketchup
- **Conversion Tool**: Existance, based on AHK patterns from Natro Macro

---

**Happy pattern making!  🐝**
