# Existance Macro:  Pattern Creation Guide

This guide explains how to create custom gathering patterns for the Existance Macro.

---

## Table of Contents

1. [What are Patterns?](#what-are-patterns)
2. [Pattern File Structure](#pattern-file-structure)
3. [Available Variables](#available-variables)
4. [Pattern Examples](#pattern-examples)
5. [Best Practices](#best-practices)
6. [Testing & Debugging](#testing--debugging)
7. [Converting AHK Patterns](#converting-ahk-patterns)

---

## What are Patterns? 

Patterns define the movement your character performs while gathering in fields. They determine how efficiently you collect pollen from flowers.  Patterns are Python scripts located in `settings/patterns/`.

When gathering is active, the macro:
1. Navigates to your selected field
2. Positions at the start location
3. Executes your pattern repeatedly
4. Collects pollen while moving

---

## Pattern File Structure

Patterns are `.py` files that execute within the macro's gather function context. Basic structure:

```python
# Size conversion (standard for all patterns)
if sizeword. lower() == "xs":
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

**File Naming:**
- Use lowercase with underscores:  `my_pattern.py`
- Avoid spaces or special characters
- Name should be descriptive:  `zigzag_tight.py`, `circle_large.py`

---

## Available Variables

When your pattern executes, these variables are available in the namespace:

### Movement Keys
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

**Why use inverted keys?**
- Using `tcfbkey` instead of `fwdkey` respects user's "Invert Forward/Back" setting
- Using `tclrkey` instead of `leftkey` respects user's "Invert Left/Right" setting
- This makes your pattern work correctly regardless of user preferences

### Camera Controls
```python
rotleft     # "," - rotate camera left
rotright    # "." - rotate camera right
rotup       # "pageup" - rotate camera up
rotdown     # "pagedown" - rotate camera down
zoomin      # "i" - zoom in
zoomout     # "o" - zoom out
sc_space    # "space" - space key
```

### Pattern Settings
```python
size        # Float:  Calculated from sizeword (XS=0.5, S=1, M=1.5, L=2, XL=2.5)
sizeword    # String: "XS", "S", "M", "L", or "XL" from GUI
width       # Integer: 1-8, number of pattern repetitions from GUI
```

### Macro Methods
```python
self.keyboard.walk(key, duration)        # Walk in direction for duration seconds
self.keyboard.multiWalk([keys], duration) # Walk multiple directions simultaneously
self.keyboard.press(key)                 # Press key once
sleep(seconds)                           # Sleep for specified time
```

**Walk Method Details:**
```python
# Walk forward for 1.5 seconds
self.keyboard.walk("w", 1.5)

# Walk diagonally (forward + left) for 2 seconds
self.keyboard.multiWalk(["w", "a"], 2.0)

# Press rotate right (single tap)
self.keyboard.press(".")
```

---

## Pattern Examples

### Example 1: Simple E Pattern (e_lol. py)

This pattern traces an "E" shape, ideal for rectangular fields. 

```python
if sizeword. lower() == "xs":
    size = 0.5
elif sizeword.lower() == "s":
    size = 1
elif sizeword.lower() == "l":
    size = 2
elif sizeword. lower() == "xl":
    size = 2.5
else:
    size = 1.5

# Move back to start position
self.keyboard.walk(afcfbkey, 0.5 * size)

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
    self.keyboard.walk(tclrkey, 0.17)
    self.keyboard.walk(tclrkey, 0.17)

# Downward zigzag (second half of E)
for _ in range(width):
    self.keyboard. walk(afcfbkey, 0.5 * size)
    self.keyboard.walk(afclrkey, 0.17)
    self.keyboard.walk(tcfbkey, 0.5 * size)
    self.keyboard.walk(afclrkey, 0.17)
```

**How it works:**
1. Moves back slightly to position
2. Walks right to form top of "E"
3. Zigzags down and back to form top section
4. Walks right to form middle of "E"
5. Zigzags down and back to form bottom section

---

### Example 2: Bambe Pattern (bambe.py)

A complex pattern with tight movements, good for dense fields.

```python
# Size conversion (custom scaling)
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

# Setup walk function compatibility (for Natro pattern conversion)
nm_walk = self.keyboard.walk
fwdkey = tcfbkey
backkey = afcfbkey
leftkey = tclrkey
rightkey = afclrkey

# Position at start
nm_walk(rightkey, 13 * size)
nm_walk(backkey, 9 * size)
nm_walk(leftkey, 4. 5 * size)
nm_walk(fwdkey, 6 * size)

# Main pattern loop
for i in range(width):
    # Left sweep
    nm_walk(fwdkey, 9 * size)
    nm_walk(leftkey, 2 * size)
    nm_walk(backkey, 9 * size)
    nm_walk(leftkey, 2 * size)
    nm_walk(fwdkey, 9 * size)
    nm_walk(leftkey, 2 * size)
    nm_walk(backkey, 9 * size)
    nm_walk(leftkey, 2 * size)
     
    # Right sweep
    nm_walk(fwdkey, 9 * size)
    nm_walk(rightkey, 2 * size)
    nm_walk(backkey, 9 * size)
    nm_walk(rightkey, 2 * size)
    nm_walk(fwdkey, 9 * size)
    nm_walk(rightkey, 2 * size)
    nm_walk(backkey, 9 * size)
    nm_walk(rightkey, 2 * size)
```

**How it works:**
1. Positions character at specific start point
2. Performs serpentine pattern moving left
3. Performs serpentine pattern moving right
4. Repeats for each width increment

---

### Example 3: Bowl Pattern with Camera Rotation (bowl.py)

Advanced pattern using camera rotation and diagonal movements.

```python
# Configuration variables
digistops = False  # Set True if using Digital Bee
passivefdc = 0.3   # Field drift compensation amount

# Pattern-specific variables
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

# Rotate camera up (reset camera angle)
for _ in range(4):
    self.keyboard.press(rotup)

# Pattern movement with camera rotations
self.keyboard.walk(backkey, stepsize * size)
self.keyboard.walk(rightkey, stepsize * size)
self.keyboard.walk(fwdkey, stepsize * size)

# Rotate left and compensate for drift
self.keyboard. press(rotleft)
self.keyboard.press(rotleft)
sleep(0.05)

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

self.keyboard.press(rotright)
sleep(0.05)

# Continue pattern... 
self.keyboard.multiWalk([backkey, rightkey], stepsize * size + passivefdc)
if digistops:  
    sleep(0.85)
```

**Advanced features:**
- Camera rotation to change perspective
- Diagonal walking with `multiWalk()`
- Digital Bee compatibility with sleep delays
- Custom drift compensation
- Complex multi-directional sweeps

---

## Best Practices

### 1. Always Include Size Handling

Every pattern must convert the size setting: 

```python
if sizeword. lower() == "xs":
    size = 0.5
elif sizeword.lower() == "s":
    size = 1
elif sizeword.lower() == "l":
    size = 2
elif sizeword. lower() == "xl":
    size = 2.5
else:
    size = 1.5  # Medium (default)
```

You can customize the multipliers for your pattern's needs: 

```python
# Tighter pattern
if sizeword.lower() == "xs":
    size = 0.25
elif sizeword. lower() == "s":
    size = 0.5
# ... 

# Or add additional scaling
size = size / 5.5  # Make pattern much tighter
```

### 2. Scale All Movements by Size

```python
# ✅ GOOD - Scales with size
self.keyboard.walk(tcfbkey, 0.5 * size)  

# ❌ BAD - Ignores user's size setting
self.keyboard.walk(tcfbkey, 0.5)
```

### 3. Use Width for Repetitions

```python
# ✅ GOOD - Respects width setting
for _ in range(width):
    self.keyboard.walk(tcfbkey, 1.0 * size)
    self.keyboard.walk(tclrkey, 0.5 * size)

# ❌ BAD - Hardcoded repetitions
for _ in range(5):
    self.keyboard.walk(tcfbkey, 1.0 * size)
```

### 4. Use Inverted Keys for Pattern Logic

```python
# ✅ GOOD - Respects invert settings
self.keyboard.walk(tcfbkey, 1.0)   # Forward (respects Invert F/B)
self.keyboard.walk(tclrkey, 0.5)   # Left (respects Invert L/R)

# ❌ BAD - Ignores invert settings
self.keyboard.walk(fwdkey, 1.0)    # Always forward
self.keyboard.walk(leftkey, 0.5)   # Always left
```

### 5. Test Multiple Sizes

Always test your pattern with different size settings: 
- **XS**: Very tight, small areas
- **S**: Small fields or dense gathering
- **M**: Default, balanced coverage
- **L**: Large fields, spread out
- **XL**: Very large fields, maximum coverage

### 6. Add Clear Comments

```python
# Position character at pattern start point
self.keyboard.walk(afcfbkey, 0.5 * size)

# Top horizontal line of E shape
for _ in range(width):
    self.keyboard.walk(tclrkey, 0.17)
    
# Downward vertical sweep with lateral movement
for _ in range(width):
    self.keyboard.walk(tcfbkey, 0.5 * size)
    self.keyboard.walk(afclrkey, 0.17)
```

### 7. Handle Special Cases

```python
# For Digital Bee users - add pause after camera rotations
digistops = False  # User can change this at top of pattern

if digistops:  
    sleep(0.8)

# Field-specific adjustments
passivefdc = 0.3  # Passive field drift compensation

# Adjust for different field shapes
if "bamboo" in field_name:   # Would need to pass field name
    size *= 1.2  # Bamboo is larger
```

### 8. Keep Patterns Efficient

```python
# ✅ GOOD - Continuous movement
self.keyboard.walk("w", 2.0)
self.keyboard.walk("a", 1.0)

# ❌ BAD - Unnecessary stops
self.keyboard.walk("w", 1.0)
sleep(0.5)
self.keyboard.walk("w", 1.0)
sleep(0.5)
```

### 9. Consider Field Coverage

Good patterns should: 
- Cover most of the field area
- Avoid revisiting the same spots too much
- Work in fields of different shapes
- Adapt to size/width settings

```python
# Balanced coverage example
for _ in range(width):
    # Forward sweep
    self.keyboard.walk(tcfbkey, 2.0 * size)
    # Lateral shift
    self.keyboard.walk(tclrkey, 0.3 * size)
    # Backward sweep
    self.keyboard. walk(afcfbkey, 2.0 * size)
    # Lateral shift
    self.keyboard.walk(tclrkey, 0.3 * size)
```

### 10. Document Pattern Behavior

Add a header comment explaining your pattern:

```python
"""
Pattern:  Spiral Outward
Description: Starts at center and spirals outward in expanding squares
Best for: Square fields (Clover, Dandelion, Sunflower)
Width: Controls number of spiral loops
Size: Controls distance between spiral rings
Author: YourName
"""

# Pattern code here... 
```

---

## Testing & Debugging

### Testing Patterns

#### 1. Enable a Test Field

In the macro GUI: 
- Select a field to use your pattern
- Set gathering time to 1-2 minutes (quick tests)
- Enable only that field
- Disable other tasks

#### 2. Watch the Pattern Execute

- Start the macro
- Observe if the pattern covers the field well
- Look for: 
  - Missed areas
  - Overlapping paths
  - Drift over time
  - Getting stuck

#### 3. Adjust Size Scaling

If pattern is too large/small, adjust size multipliers:

```python
# Pattern is too large
size = size * 0.8  # Make pattern 20% smaller

# Pattern is too small
size = size * 1.2  # Make pattern 20% larger

# Pattern needs different proportions
size_horizontal = size * 1.0
size_vertical = size * 0.7  # Make vertical movements shorter
```

#### 4. Test All Size Settings

Test each size from the GUI:
```
XS → Should work in very tight spaces
S  → Should work in small areas
M  → Should be balanced (most common)
L  → Should cover large areas
XL → Should maximize coverage
```

#### 5. Test All Width Settings

Test width values 1-8:
```
Width 1 → Minimal repetitions
Width 4 → Moderate coverage
Width 8 → Maximum repetitions
```

### Check Pattern Output

#### View Logs

Pattern errors appear in:
- Terminal/console output
- Macro logs
- Discord webhook (if enabled): "Incompatible pattern"

#### Common Errors

```python
# Error: NameError: name 'tcfbkey' is not defined
# Fix: Check spelling, use correct variable names

# Error: TypeError: unsupported operand type(s)
# Fix:  Ensure size is defined, check math operations

# Error: SyntaxError
# Fix: Check for missing colons, parentheses, quotes
```

### Debug with Print Statements

```python
# Add debug prints to see what's happening
print(f"Size: {size}, Width: {width}")
print(f"Moving forward for {1.0 * size} seconds")

self.keyboard.walk(tcfbkey, 1.0 * size)
print("Forward movement complete")
```

### Test in Different Fields

Your pattern should work reasonably well in:
- Small fields (Sunflower, Dandelion, Mushroom)
- Medium fields (Blue Flower, Bamboo, Rose)
- Large fields (Pepper, Pumpkin, Cactus)

### Record and Review

- Enable screen recording in macro settings
- Record a full pattern cycle
- Review footage to identify issues
- Make adjustments based on observations

---

## Converting AHK Patterns

The macro includes an automatic AHK-to-Python converter for Natro Macro patterns. 

### Automatic Conversion

Place `.ahk` pattern files in `settings/patterns/`. On macro startup: 
```python
# Macro automatically converts . ahk files to .py
ahkPatterns = [x for x in os.listdir(patterns_dir) if ".ahk" in x]
for pattern in ahkPatterns: 
    python = ahkPatternToPython(ahk)
    # Saves as .py file with same name
```

### Manual Conversion

If automatic conversion fails, convert manually using these equivalents:

#### Basic Movement

**AHK:**
```ahk
Send {w down}
Sleep 1000
Send {w up}
```

**Python:**
```python
self.keyboard.walk("w", 1.0)
```

#### Loops

**AHK:**
```ahk
Loop %reps%
{
    ; Movement commands
}
```

**Python:**
```python
for i in range(width):
    # Movement commands
```

#### Natro's nm_Walk Function

**AHK:**
```ahk
nm_Walk(2, FwdKey)
nm_Walk(1. 5, LeftKey)
```

**Python:**
```python
self.keyboard.walk(tcfbkey, 2)
self.keyboard.walk(tclrkey, 1.5)
```

#### Common Replacements

| AHK | Python |
|-----|--------|
| `reps` | `width` |
| `a_index` | `i` |
| `&&` | `and` |
| `||` | `or` |
| `;` (comment) | `#` (comment) |
| `:=` | `=` |
| `sqrt` | `math.sqrt` |
| `Sleep 500` | `sleep(0.5)` |

### Full Conversion Example

**Before (AHK):**
```ahk
; Simple zigzag pattern
Loop %reps%
{
    Send {w down}
    Sleep 500
    Send {w up}
    
    Send {a down}
    Sleep 200
    Send {a up}
    
    Send {s down}
    Sleep 500
    Send {s up}
    
    Send {a down}
    Sleep 200
    Send {a up}
}
```

**After (Python):**
```python
# Simple zigzag pattern
for i in range(width):
    self.keyboard.walk("w", 0.5)
    self.keyboard.walk("a", 0.2)
    self.keyboard.walk("s", 0.5)
    self.keyboard.walk("a", 0.2)
```

**Better (Python with proper keys):**
```python
# Simple zigzag pattern (respects inversions)
for i in range(width):
    self.keyboard. walk(tcfbkey, 0.5 * size)
    self.keyboard.walk(tclrkey, 0.2 * size)
    self.keyboard.walk(afcfbkey, 0.5 * size)
    self.keyboard.walk(tclrkey, 0.2 * size)
```

---

## Additional Resources

- **Pattern Inspiration**: Check existing patterns in `settings/patterns/`
- **Natro Macro Patterns**: Many patterns are compatible with conversion
- **Discord Community**: Share patterns and get help at https://discord.gg/3qf8bgqCVu
- **Documentation**:  https://existance-macro.gitbook.io/existance-macro-docs/

---

## Contributing Patterns

If you create useful patterns: 

1. **Test thoroughly** across different fields and scenarios
2. **Add clear comments** explaining the pattern logic
3. **Include size handling** and width support
4. **Test all size/width combinations**
5. **Share in Discord** community
6. **Consider submitting a PR** to the repository

### Pattern Template

```python
"""
Pattern Name: [Your Pattern Name]
Description: [What the pattern does]
Best For: [Which fields work best]
Width: [What width controls]
Size: [What size controls]
Author: [Your Name]
Date: [Creation Date]
"""

# Size conversion
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

# Configuration (optional)
# Add any user-configurable variables here

# Pattern logic
# Your pattern movement code here
```

---

## Credits

- **Pattern System**: Inspired by Natro Macro
- **Pattern Makers**: Existance, NatroTeam, tvojamamkajenic, sev, dully176, chillketchup
- **Conversion Tool**: Based on AHK patterns from Natro Macro
- **Macro Developer**: Existance, Sev, Logan

---

**Happy pattern making!  🐝**
