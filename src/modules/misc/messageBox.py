import os
import subprocess
import sys

if sys.platform == "win32":
    import ctypes
    MB_OK, MB_OKCANCEL, MB_SETFOREGROUND, MB_TOPMOST = 0x0, 0x1, 0x10000, 0x40000
    IDOK = 1

    def _windowsBox(title, text, style):
        return ctypes.windll.user32.MessageBoxW(None, str(text), str(title), style | MB_SETFOREGROUND | MB_TOPMOST)

def msgBox(title, text):
    if sys.platform == "win32":
        _windowsBox(title, text, MB_OK)
        return
    os.system(f'''osascript -e 'Tell application "System Events" to display dialog "{text}" with title "{title}"' ''')

def msgBoxOkCancel(title, text):
    #message box with OK/Cancel buttons and callback functions
    if sys.platform == "win32":
        return _windowsBox(title, text, MB_OKCANCEL) == IDOK
    
    #appleScript
    script = f'''
    tell application "System Events"
        try
            display dialog "{text}" with title "{title}" buttons {{"Cancel", "OK"}} default button "OK"
            return "OK"
        on error
            return "Cancel"
        end try
    end tell
    '''
    
    try:
        result = subprocess.run(['osascript', '-e', script], 
                              capture_output=True, text=True, check=True)
        user_choice = result.stdout.strip()
        
        return user_choice == "OK"
        
    except subprocess.CalledProcessError:
        return False