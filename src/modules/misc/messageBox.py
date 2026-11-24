import subprocess
from modules.controls.sleep import pause_hang_watchdog

def _escapeAppleScript(value):
    return str(value).replace("\\", "\\\\").replace('"', '\\"')

def msgBox(title, text):
    # StandardAdditions can display the dialog from osascript without targeting
    # System Events, so it needs no Automation permission.
    script = f'''display dialog "{_escapeAppleScript(text)}" with title "{_escapeAppleScript(title)}"'''
    pause_hang_watchdog()
    subprocess.run(["osascript", "-e", script])

def msgBoxOkCancel(title, text):
    #message box with OK/Cancel buttons and callback functions
    
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