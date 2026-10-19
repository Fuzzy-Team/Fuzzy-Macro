'''
Runs Roblox on a dedicated virtual display, based on DeskPad
(https://github.com/Stengo/DeskPad).

The display is created by a small helper (virtual_display/FuzzyVirtualDisplay.m)
that is compiled with the Xcode command line tools on first use. The helper
keeps the display alive for as long as it runs and shows a live preview of it
in a window. The display is 1920x1080, non-retina (100% scaling) and uses the
"sRGB IEC61966-2.1" color profile, so the macro sees the same pixels on every
Mac regardless of the user's real screen.
'''
import hashlib
import os
import select
import subprocess
import time

HELPER_NAME = "FuzzyVirtualDisplay"
DISPLAY_NAME = "Fuzzy Macro Display"
DISPLAY_WIDTH = 1920
DISPLAY_HEIGHT = 1080
SRGB_PROFILE_PATH = "/System/Library/ColorSync/Profiles/sRGB Profile.icc"

_sourcePath = os.path.join(os.path.dirname(os.path.abspath(__file__)), "virtual_display", f"{HELPER_NAME}.m")
_buildDir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../data/user/virtual_display"))
_binaryPath = os.path.join(_buildDir, HELPER_NAME)
_hashPath = _binaryPath + ".sha1"

_process = None
_displayID = 0


def _sourceHash():
    with open(_sourcePath, "rb") as f:
        return hashlib.sha1(f.read()).hexdigest()


def buildHelper():
    '''Compile the helper if it is missing or out of date. Returns the binary
    path, or None if it could not be built.'''
    try:
        sourceHash = _sourceHash()
    except OSError as e:
        print(f"Virtual display helper source missing: {e}")
        return None
    if os.path.exists(_binaryPath) and os.path.exists(_hashPath):
        with open(_hashPath) as f:
            if f.read().strip() == sourceHash:
                return _binaryPath

    os.makedirs(_buildDir, exist_ok=True)
    tmpPath = _binaryPath + ".tmp"
    cmd = [
        "clang", "-fobjc-arc", "-O2", "-Wno-deprecated-declarations",
        # CGDisplayStream is marked unavailable from macOS 15 onwards in the
        # SDK, but still works at runtime. An older target keeps it usable.
        "-mmacosx-version-min=10.13",
        "-framework", "Cocoa", "-framework", "CoreGraphics",
        "-framework", "IOSurface", "-framework", "QuartzCore",
        _sourcePath, "-o", tmpPath,
    ]
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as e:
        print(f"Failed to build the virtual display helper: {e}")
        return None
    if result.returncode != 0:
        print("Failed to build the virtual display helper:\n" + result.stderr.decode(errors="replace"))
        return None
    os.replace(tmpPath, _binaryPath)
    with open(_hashPath, "w") as f:
        f.write(sourceHash)
    return _binaryPath


def isRunning():
    return _process is not None and _process.poll() is None


def displayID():
    '''ID of the virtual display, or 0 if it is not running.'''
    return _displayID if isRunning() else 0


def _readReadyLine(proc, timeout):
    deadline = time.time() + timeout
    line = b""
    while time.time() < deadline:
        ready, _, _ = select.select([proc.stdout], [], [], max(0, deadline - time.time()))
        if not ready:
            break
        chunk = os.read(proc.stdout.fileno(), 1)
        if not chunk:
            break
        if chunk == b"\n":
            return line.decode(errors="replace")
        line += chunk
    return None


def applyColorProfile(displayID):
    try:
        from modules.misc.ColorProfile import DisplayColorProfile
        profiles = DisplayColorProfile()
        if "sRGB" not in str(profiles.getCurrentColorProfile(displayID)):
            profiles.setCustomProfile(SRGB_PROFILE_PATH, displayID)
        return True
    except Exception as e:
        print(f"Failed to set the virtual display color profile: {e}")
        return False


def start(showPreview=True):
    '''Create the virtual display (if not already running). Returns its ID,
    or 0 if virtual displays are unavailable.'''
    global _process, _displayID
    if isRunning():
        return _displayID

    binary = buildHelper()
    if not binary:
        return 0
    cmd = [
        binary,
        "--width", str(DISPLAY_WIDTH),
        "--height", str(DISPLAY_HEIGHT),
        "--name", DISPLAY_NAME,
        "--parent-pid", str(os.getpid()),
    ]
    if not showPreview:
        cmd.append("--no-preview")
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stdin=subprocess.DEVNULL)
    except OSError as e:
        print(f"Failed to start the virtual display helper: {e}")
        return 0

    line = _readReadyLine(proc, timeout=15)
    if not line or not line.startswith("READY "):
        print("The virtual display helper did not start; Roblox will use the main display.")
        _terminate(proc)
        return 0

    _process = proc
    _displayID = int(line.split()[1])
    # Give WindowServer a moment to finish configuring the new display.
    time.sleep(1)
    applyColorProfile(_displayID)
    return _displayID


def _terminate(proc):
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=3)


def stop():
    '''Remove the virtual display. macOS moves its windows back to the main
    display.'''
    global _process, _displayID
    if _process is not None:
        _terminate(_process)
    _process = None
    _displayID = 0


def sync(enabled):
    '''Start or stop the virtual display to match the setting. Returns the
    display ID Roblox should use (0 for the main display).'''
    if enabled:
        return start()
    stop()
    return 0
