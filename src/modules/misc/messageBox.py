import subprocess

def _escapeAppleScript(value):
    return str(value).replace("\\", "\\\\").replace('"', '\\"')

def msgBox(title, text):
    script = f'''tell application "System Events" to display dialog "{_escapeAppleScript(text)}" with title "{_escapeAppleScript(title)}"'''
    subprocess.run(["osascript", "-e", script])

def msgBoxOkCancel(title, text):
    #message box with OK/Cancel buttons and callback functions
    
    #appleScript
    script = f'''
    tell application "System Events"
        try
            display dialog "{_escapeAppleScript(text)}" with title "{_escapeAppleScript(title)}" buttons {{"Cancel", "OK"}} default button "OK"
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