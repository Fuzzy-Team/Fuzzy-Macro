import os
import platform

_IS_WINDOWS = platform.system() == "Windows"

def runAppleScript(code):
    if _IS_WINDOWS:
        return  # AppleScript is not available on Windows
    cmd = ''' osascript -e '{}' '''.format(code)
    os.system(cmd)