import os
import sys
import subprocess
import platform

_IS_WINDOWS = platform.system() == "Windows"

def msgBox(title, text):
    if _IS_WINDOWS:
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, text, title, 0)
        except Exception:
            try:
                import tkinter as tk
                from tkinter import messagebox
                root = tk.Tk()
                root.withdraw()
                messagebox.showinfo(title, text)
                root.destroy()
            except Exception:
                print(f"[{title}] {text}")
    else:
        os.system(f'''osascript -e 'Tell application "System Events" to display dialog "{text}" with title "{title}"' ''')

def msgBoxOkCancel(title, text):
    #message box with OK/Cancel buttons and callback functions
    if _IS_WINDOWS:
        try:
            import ctypes
            # MB_OKCANCEL = 1, returns 1 for OK, 2 for Cancel
            result = ctypes.windll.user32.MessageBoxW(0, text, title, 1)
            return result == 1
        except Exception:
            try:
                import tkinter as tk
                from tkinter import messagebox
                root = tk.Tk()
                root.withdraw()
                result = messagebox.askokcancel(title, text)
                root.destroy()
                return result
            except Exception:
                return False
    else:
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