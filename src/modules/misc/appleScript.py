import os
import platform

_IS_MACOS = platform.system() == "Darwin"

def runAppleScript(code):
    if not _IS_MACOS:
        return  # AppleScript is only available on macOS
    cmd = ''' osascript -e '{}' '''.format(code)
    os.system(cmd)
