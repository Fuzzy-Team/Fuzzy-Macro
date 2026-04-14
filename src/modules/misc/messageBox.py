import subprocess


def _apple_script_string(value):
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def msgBox(title, text):
    script = f"display dialog {_apple_script_string(text)} with title {_apple_script_string(title)}"
    subprocess.run(["osascript", "-e", script], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def msgBoxOkCancel(title, text):
    #message box with OK/Cancel buttons and callback functions
    
    #appleScript
    script = f'''
    try
        display dialog {_apple_script_string(text)} with title {_apple_script_string(title)} buttons {{"Cancel", "OK"}} default button "OK"
        return "OK"
    on error
        return "Cancel"
    end try
    '''
    
    try:
        result = subprocess.run(['osascript', '-e', script], 
                              capture_output=True, text=True, check=True)
        user_choice = result.stdout.strip()
        
        return user_choice == "OK"
        
    except subprocess.CalledProcessError:
        return False
