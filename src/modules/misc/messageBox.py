import os
import shutil
import subprocess
import platform

_IS_WINDOWS = platform.system() == "Windows"
_IS_MACOS = platform.system() == "Darwin"

# Win32 MessageBox flags
MB_OK = 0x00000000
MB_OKCANCEL = 0x00000001
MB_SETFOREGROUND = 0x00010000
MB_TOPMOST = 0x00040000

def _tk_info(title, text):
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        try:
            root.attributes('-topmost', True)
        except Exception:
            pass
        messagebox.showinfo(title, text, parent=root)
        root.destroy()
        return True
    except Exception:
        print(f"[{title}] {text}")
        return False

def _tk_ok_cancel(title, text):
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        try:
            root.attributes('-topmost', True)
        except Exception:
            pass
        result = messagebox.askokcancel(title, text, parent=root)
        root.destroy()
        return result
    except Exception:
        return False

def _zenity_info(title, text):
    try:
        subprocess.run(
            ["zenity", "--info", f"--title={title}", f"--text={text}", "--width=420"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except Exception:
        return False

def _zenity_ok_cancel(title, text):
    try:
        result = subprocess.run(
            ["zenity", "--question", f"--title={title}", f"--text={text}", "--width=420"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return result.returncode == 0
    except Exception:
        return False

def msgBox(title, text):
    if _IS_WINDOWS:
        try:
            import ctypes
            flags = MB_OK | MB_SETFOREGROUND | MB_TOPMOST
            ctypes.windll.user32.MessageBoxW(0, text, title, flags)
        except Exception:
            _tk_info(title, text)
    elif _IS_MACOS:
        os.system(f'''osascript -e 'Tell application "System Events" to display dialog "{text}" with title "{title}"' ''')
    else:
        if not _zenity_info(title, text):
            _tk_info(title, text)

def msgBoxOkCancel(title, text):
    #message box with OK/Cancel buttons and callback functions
    if _IS_WINDOWS:
        try:
            import ctypes
            # MB_OKCANCEL = 1, returns 1 for OK, 2 for Cancel
            flags = MB_OKCANCEL | MB_SETFOREGROUND | MB_TOPMOST
            result = ctypes.windll.user32.MessageBoxW(0, text, title, flags)
            return result == 1
        except Exception:
            return _tk_ok_cancel(title, text)
    elif _IS_MACOS:
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
    else:
        if shutil.which("zenity"):
            return _zenity_ok_cancel(title, text)
        return _tk_ok_cancel(title, text)
