import os
import sys
import subprocess

def msgBox(title, text):
    os.system(f'''osascript -e 'Tell application "System Events" to display dialog "{text}" with title "{title}"' ''')

def msgBoxOkCancel(title, text):
    #message box with OK/Cancel buttons and callback functions
    
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