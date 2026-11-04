"""Lifecycle and coordinates for the bundled, single-client Fuzzy Display helper."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import tarfile
import tempfile
import time
import uuid

ENV = "FUZZY_DISPLAY_SESSION"
WIDTH, HEIGHT = 1920, 1080
ASSETS = Path(__file__).resolve().parents[2] / "assets" / "fuzzy-display"


class DisplayError(RuntimeError):
    pass


def active():
    return bool(os.environ.get(ENV))


def state(require_window=False, allow_error=False):
    if not active():
        raise DisplayError("1080p display mode is not active.")
    try:
        with open(os.path.join(os.environ[ENV], "status.json")) as handle:
            result = json.load(handle)
        if result.get("protocol") != 1 or time.time() - result["updated"] > 3:
            raise DisplayError("Fuzzy Display stopped responding. Restart the macro.")
        if result.get("error") and not allow_error:
            raise DisplayError(result["error"])
        if require_window and not result.get("window_ready"):
            raise DisplayError("Roblox has no verified game area on Fuzzy Display.")
        return result
    except (OSError, ValueError, KeyError) as error:
        raise DisplayError("Cannot read Fuzzy Display status: {}".format(error))


def command(action, timeout=8):
    # GUI lifecycle and macro placement may request commands from different processes.
    with open(os.path.join(os.environ[ENV], "command.lock"), "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        return _command(action, timeout)


def _command(action, timeout=8):
    request = {"id": uuid.uuid4().hex, "action": action}
    directory = Path(os.environ[ENV])
    temporary = directory / (request["id"] + ".json")
    temporary.write_text(json.dumps(request))
    temporary.replace(directory / "command.json")
    if action == "quit":
        return None
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = state(allow_error=True)
        if result.get("command") == request["id"]:
            if result.get("error"):
                raise DisplayError(result["error"])
            return result
        time.sleep(0.05)
    raise DisplayError("Fuzzy Display did not complete {}.".format(action))


def prepare_window():
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        result = command("prepare")
        if not result.get("settling") and (result.get("window_ready") or not result.get("window_pid")):
            return result
        time.sleep(0.2)
    raise DisplayError("Roblox could not settle on Fuzzy Display.")


def origin():
    result = state(require_window=True)
    x, y, width, height = result["content"]
    if (width, height) != (WIDTH, HEIGHT):
        raise DisplayError("Roblox's game area is not 1920x1080.")
    return int(x), int(y)


def to_global(x, y):
    if active():
        left, top = origin()
        return int(left + x), int(top + y)
    return int(x), int(y)


def to_local(x, y):
    if active():
        left, top = origin()
        return x - left, y - top
    return x, y


def screen_size():
    if active():
        return WIDTH, HEIGHT
    import pyautogui
    return pyautogui.size()


class DisplaySession:
    """Owned by the GUI process so stopping a macro child retains its display."""
    def __init__(self):
        self.process = None
        self.directory = None
        self.log = None

    def start(self):
        if self.process is not None and self.process.poll() is None:
            result = prepare_window()
            command("show")
            return result
        if self.directory is not None:
            self.close()
        version = platform.mac_ver()[0].split(".")[0]
        if platform.system() != "Darwin" or not version.isdigit() or int(version) < 13:
            raise DisplayError("1080p virtual display mode requires macOS 13 or later.")
        manifest = json.loads((ASSETS / "manifest.json").read_text())
        archive = ASSETS / "FuzzyDisplay.tar.gz"
        if hashlib.sha256(archive.read_bytes()).hexdigest() != manifest["sha256"]:
            raise DisplayError("The bundled Fuzzy Display archive is damaged. Reinstall Fuzzy Macro.")
        self.directory = tempfile.TemporaryDirectory(prefix="fuzzy-display-")
        directory = Path(self.directory.name)
        # A stable app path keeps macOS privacy permissions attached across starts.
        from modules.misc import settingsManager
        installed = Path(settingsManager.getUserDataPath("fuzzy-display")) / manifest["sha256"]
        installed.mkdir(parents=True, exist_ok=True)
        installed = installed.resolve()
        try:
            with tarfile.open(str(archive), "r:gz") as bundle:
                for member in bundle.getmembers():
                    target = installed / member.name
                    if member.issym() or member.islnk() or not (member.isfile() or member.isdir()) or not str(target.resolve()).startswith(str(installed) + os.sep):
                        raise DisplayError("The Fuzzy Display archive contains an invalid entry.")
                bundle.extractall(str(installed))
            executable = installed / "Fuzzy Display.app/Contents/MacOS/FuzzyDisplay"
            if hashlib.sha256(executable.read_bytes()).hexdigest() != manifest["executable_sha256"]:
                raise DisplayError("The installed Fuzzy Display binary is damaged.")
            executable.chmod(0o755)
            self.log = open(str(directory / "helper.log"), "w+")
            self.process = subprocess.Popen([str(executable), str(directory), str(os.getpid())], stdout=self.log, stderr=self.log)
            os.environ[ENV] = str(directory)
            deadline = time.monotonic() + 10
            while not (directory / "status.json").exists():
                if self.process.poll() is not None or time.monotonic() >= deadline:
                    self.log.seek(0)
                    raise DisplayError("Fuzzy Display could not start. {}".format(self.log.read()[-2000:]))
                time.sleep(0.05)
            return prepare_window()
        except Exception:
            self.close()
            raise

    def close(self):
        # Only this Popen's process is ours. The helper restores saved placement.
        if self.process is not None and self.process.poll() is None:
            try:
                command("quit")
            except DisplayError:
                # Still wait for or terminate our process if its command channel failed.
                pass
            try:
                self.process.wait(timeout=4)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                try:
                    self.process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=2)
        self.process = None
        os.environ.pop(ENV, None)
        if self.log is not None:
            self.log.close()
            self.log = None
        if self.directory is not None:
            self.directory.cleanup()
            self.directory = None
