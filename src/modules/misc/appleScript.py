import subprocess

from modules.misc import macPermissions


def runAppleScript(code):
    result = subprocess.run(["osascript", "-e", code], capture_output=True, text=True)
    stderr = result.stderr or ""
    if result.returncode != 0 and ("-1743" in stderr or "not authorized" in stderr.lower()):
        macPermissions.show_permission_message(
            "Automation",
            "Automation",
            title="Automation Permission",
            details="This is required when Fuzzy Macro asks macOS to activate or control other apps.",
        )
    return result.returncode == 0
