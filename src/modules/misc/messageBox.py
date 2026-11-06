import subprocess
import sys
from modules.controls.sleep import pause_hang_watchdog

if sys.platform == "win32":
    import ctypes
    MB_OK, MB_OKCANCEL, MB_SETFOREGROUND, MB_TOPMOST = 0x0, 0x1, 0x10000, 0x40000
    IDOK = 1

    def _windowsBox(title, text, style):
        return ctypes.windll.user32.MessageBoxW(None, str(text), str(title), style | MB_SETFOREGROUND | MB_TOPMOST)

def _escapeAppleScript(value):
    return str(value).replace("\\", "\\\\").replace('"', '\\"')

def msgBox(title, text):
    if sys.platform == "win32":
        _windowsBox(title, text, MB_OK)
        return
    # StandardAdditions can display the dialog from osascript without targeting
    # System Events, so it needs no Automation permission.
    script = f'''display dialog "{_escapeAppleScript(text)}" with title "{_escapeAppleScript(title)}"'''
    pause_hang_watchdog()
    subprocess.run(["osascript", "-e", script])

def msgBoxOkCancel(title, text):
    #message box with OK/Cancel buttons and callback functions
    if sys.platform == "win32":
        return _windowsBox(title, text, MB_OKCANCEL) == IDOK
    
    #appleScript
    script = f'''
    try
        set response to display dialog "{_escapeAppleScript(text)}" with title "{_escapeAppleScript(title)}" buttons {{"Cancel", "OK"}} default button "OK" cancel button "Cancel"
        return button returned of response
    on error number -128
        return "Cancel"
    end try
    '''
    
    pause_hang_watchdog()
    try:
        result = subprocess.run(['osascript', '-e', script], 
                              capture_output=True, text=True, check=True)
        user_choice = result.stdout.strip()
        
        return user_choice == "OK"
        
    except subprocess.CalledProcessError:
        return False