import ast
import os
import shutil
import json
import zipfile
import tempfile
from datetime import datetime

#returns a dictionary containing the settings
profileName = "a"

# Profile management functions
def getProfilesDir():
    """Get the profiles directory path"""
    return "../settings/profiles"

def listProfiles():
    """List all available profiles"""
    profiles_dir = getProfilesDir()
    if os.path.exists(profiles_dir):
        profiles = [d for d in os.listdir(profiles_dir) 
                   if os.path.isdir(os.path.join(profiles_dir, d)) and not d.startswith('.')]
        return sorted(profiles)
    return []

def getCurrentProfile():
    """Get the current profile name"""
    global profileName
    return profileName

def switchProfile(name):
    """Switch to a different profile"""
    global profileName
    profiles_dir = getProfilesDir()
    profile_path = os.path.join(profiles_dir, name)

    if not os.path.exists(profile_path) or not os.path.isdir(profile_path):
        return False, f"Profile '{name}' not found"

    # Check if required profile files exist
    settings_file = os.path.join(profile_path, "settings.txt")
    fields_file = os.path.join(profile_path, "fields.txt")

    if not os.path.exists(settings_file):
        return False, f"Profile '{name}' is missing settings.txt file"

    if not os.path.exists(fields_file):
        return False, f"Profile '{name}' is missing fields.txt file"

    profileName = name

    # Sync the new profile's field settings to general settings
    initializeFieldSync()

    return True, f"Switched to profile: {name}"

def createProfile(name):
    """Create a new profile by copying the current profile"""
    global profileName
    profiles_dir = getProfilesDir()
    
    # Sanitize the profile name
    name = name.strip().replace(' ', '_').lower()
    if not name:
        return False, "Profile name cannot be empty"
    
    # Check if profile already exists
    new_profile_path = os.path.join(profiles_dir, name)
    if os.path.exists(new_profile_path):
        return False, f"Profile '{name}' already exists"
    
    # Copy current profile to new profile
    current_profile_path = os.path.join(profiles_dir, profileName)
    try:
        shutil.copytree(current_profile_path, new_profile_path)
        return True, f"Created profile: {name}"
    except Exception as e:
        return False, f"Failed to create profile: {str(e)}"

def deleteProfile(name):
    """Delete a profile (cannot delete current or last profile)"""
    global profileName
    profiles_dir = getProfilesDir()
    
    # Cannot delete current profile
    if name == profileName:
        return False, "Cannot delete the currently active profile"
    
    # Cannot delete if it's the only profile
    profiles = listProfiles()
    if len(profiles) <= 1:
        return False, "Cannot delete the only remaining profile"
    
    profile_path = os.path.join(profiles_dir, name)
    if not os.path.exists(profile_path):
        return False, f"Profile '{name}' not found"
    
    try:
        shutil.rmtree(profile_path)
        return True, f"Deleted profile: {name}"
    except Exception as e:
        return False, f"Failed to delete profile: {str(e)}"

def renameProfile(old_name, new_name):
    """Rename a profile"""
    global profileName
    profiles_dir = getProfilesDir()
    
    # Sanitize the new name
    new_name = new_name.strip().replace(' ', '_').lower()
    if not new_name:
        return False, "New profile name cannot be empty"
    
    old_path = os.path.join(profiles_dir, old_name)
    new_path = os.path.join(profiles_dir, new_name)
    
    if not os.path.exists(old_path):
        return False, f"Profile '{old_name}' not found"
    
    if os.path.exists(new_path):
        return False, f"Profile '{new_name}' already exists"
    
    try:
        os.rename(old_path, new_path)
        # If we renamed the current profile, update the reference
        if old_name == profileName:
            profileName = new_name
        return True, f"Renamed profile from '{old_name}' to '{new_name}'"
    except Exception as e:
        return False, f"Failed to rename profile: {str(e)}"

def duplicateProfile(source_name, new_name):
    """Duplicate an existing profile with a new name"""
    profiles_dir = getProfilesDir()
    
    # Sanitize the new name
    new_name = new_name.strip().replace(' ', '_').lower()
    if not new_name:
        return False, "New profile name cannot be empty"
    
    source_path = os.path.join(profiles_dir, source_name)
    new_path = os.path.join(profiles_dir, new_name)
    
    if not os.path.exists(source_path):
        return False, f"Source profile '{source_name}' not found"
    
    if os.path.exists(new_path):
        return False, f"Profile '{new_name}' already exists"
    
    try:
        shutil.copytree(source_path, new_path)
        return True, f"Duplicated profile '{source_name}' as '{new_name}'"
    except Exception as e:
        return False, f"Failed to duplicate profile: {str(e)}"

def readSettingsFile(path):
    #get each line
    #read the file, format it to:
    #[[key, value], [key, value]]
    with open(path) as f:
        data = [[x.strip() for x in y.split("=", 1)] for y in f.read().split("\n") if y]
    f.close()
    #convert to a dict
    out = {}
    for k,v in data:
        try:
            out[k] = ast.literal_eval(v)
        except:
            #check if integer
            if v.isdigit():
                out[k] = int(v)
            elif v.replace(".","",1).isdigit():
                out[k] = float(v)
            out[k] = v
    return out

def saveDict(path, data):
    out = "\n".join([f"{k}={v}" for k,v in data.items()])
    with open(path, "w") as f:
        f.write(str(out))
    f.close()

#update one property of a setting
def saveSettingFile(setting,value, path):
    #get the dictionary
    data = readSettingsFile(path)
    #update the dictionary
    data[setting] = value
    #write it
    saveDict(path, data)

def loadFields():
    with open(f"../settings/profiles/{profileName}/fields.txt") as f:
        out = ast.literal_eval(f.read())
    f.close()
    
    # Auto-add missing goo settings for backward compatibility
    # This ensures users upgrading from older versions get the new goo functionality
    fieldsUpdated = False
    for field, settings in out.items():
        # Add missing goo settings if they don't exist
        if "goo" not in settings:
            settings["goo"] = False  # Default to disabled
            fieldsUpdated = True
        if "goo_interval" not in settings:
            settings["goo_interval"] = 3  # Default to 3 seconds (minimum allowed)
            fieldsUpdated = True
    
    # Save the updated fields if any were modified
    if fieldsUpdated:
        with open(f"../settings/profiles/{profileName}/fields.txt", "w") as f:
            f.write(str(out))
        f.close()
    
    for field,settings in out.items():
        for k,v in settings.items():
            #check if integer
            if isinstance(v,str): 
                if v.isdigit(): out[field][k] = int(v)
                elif v.replace(".","",1).isdigit(): out[field][k] = float(v)
    return out

def saveField(field, settings):
    fieldsData = loadFields()
    fieldsData[field] = settings
    with open(f"../settings/profiles/{profileName}/fields.txt", "w") as f:
        f.write(str(fieldsData))
    f.close()

def syncFieldSettings(setting, value):
    """Synchronize field settings from profile to general settings"""
    try:
        # Update the general settings file
        generalSettingsPath = "../settings/generalsettings.txt"
        generalData = readSettingsFile(generalSettingsPath)
        generalData[setting] = value
        saveDict(generalSettingsPath, generalData)
    except Exception as e:
        print(f"Warning: Could not sync field settings to general settings: {e}")

def syncFieldSettingsToProfile(setting, value):
    """Synchronize field settings from general to profile settings"""
    try:
        # Update the profile settings file
        profileSettingsPath = f"../settings/profiles/{profileName}/settings.txt"
        profileData = readSettingsFile(profileSettingsPath)
        profileData[setting] = value
        saveDict(profileSettingsPath, profileData)
    except Exception as e:
        print(f"Warning: Could not sync field settings to profile settings: {e}")

def saveProfileSetting(setting, value):
    saveSettingFile(setting, value, f"../settings/profiles/{profileName}/settings.txt")
    # Synchronize field settings with general settings
    if setting in ["fields", "fields_enabled"]:
        syncFieldSettings(setting, value)

def saveDictProfileSettings(dict):

    saveDict(f"../settings/profiles/{profileName}/settings.txt", {**readSettingsFile(f"../settings/profiles/{profileName}/settings.txt"), **dict})

#increment a setting, and return the dictionary for the setting
def incrementProfileSetting(setting, incrValue):
    #get the dictionary
    data = readSettingsFile(f"../settings/profiles/{profileName}/settings.txt")
    #update the dictionary
    data[setting] += incrValue
    #write it
    saveDict(f"../settings/profiles/{profileName}/settings.txt", data)
    return data

def saveGeneralSetting(setting, value):
    saveSettingFile(setting, value, "../settings/generalsettings.txt")
    # Synchronize field settings with profile settings
    if setting in ["fields", "fields_enabled"]:
        syncFieldSettingsToProfile(setting, value)

def loadSettings():
    try:
        settings = readSettingsFile(f"../settings/profiles/{profileName}/settings.txt")
    except FileNotFoundError:
        print(f"Warning: Profile '{profileName}' settings file not found, using defaults")
        # Fall back to default settings if profile file is missing
        settings = readSettingsFile("./data/default_settings/settings.txt")

    # Ensure fields and fields_enabled arrays have 5 elements
    defaultSettings = readSettingsFile("./data/default_settings/settings.txt")
    defaultFields = defaultSettings.get("fields", ['pine tree', 'sunflower', 'dandelion', 'pine tree', 'sunflower'])
    defaultFieldsEnabled = defaultSettings.get("fields_enabled", [True, False, False, False, False])
    
    fields = settings.get("fields", [])
    fieldsEnabled = settings.get("fields_enabled", [])
    
    # Extend arrays to 5 elements if needed
    updated = False
    while len(fields) < 5:
        fields.append(defaultFields[len(fields)] if len(fields) < len(defaultFields) else defaultFields[-1])
        updated = True
    while len(fieldsEnabled) < 5:
        fieldsEnabled.append(defaultFieldsEnabled[len(fieldsEnabled)] if len(fieldsEnabled) < len(defaultFieldsEnabled) else False)
        updated = True
    
    if updated:
        settings["fields"] = fields
        settings["fields_enabled"] = fieldsEnabled
        saveDict(f"../settings/profiles/{profileName}/settings.txt", settings)
    
    return settings

#return a dict containing all settings except field (general, profile, planters)
def loadAllSettings():
    return {**loadSettings(), **readSettingsFile("../settings/generalsettings.txt")}

def initializeFieldSync():
    """Initialize field synchronization between profile and general settings"""
    try:
        try:
            profileData = readSettingsFile(f"../settings/profiles/{profileName}/settings.txt")
        except FileNotFoundError:
            print(f"Warning: Profile '{profileName}' settings file not found during sync, skipping")
            return

        generalData = readSettingsFile("../settings/generalsettings.txt")
        
        # Check if field settings exist in both files
        profileFields = profileData.get("fields", [])
        generalFields = generalData.get("fields", [])
        
        # If general settings has different fields, sync from profile to general
        if profileFields != generalFields and profileFields:
            generalData["fields"] = profileFields
            saveDict("../settings/generalsettings.txt", generalData)
            
        # Sync fields_enabled as well
        profileFieldsEnabled = profileData.get("fields_enabled", [])
        generalFieldsEnabled = generalData.get("fields_enabled", [])
        
        if profileFieldsEnabled != generalFieldsEnabled and profileFieldsEnabled:
            generalData["fields_enabled"] = profileFieldsEnabled
            saveDict("../settings/generalsettings.txt", generalData)
            
    except Exception as e:
        print(f"Warning: Could not initialize field synchronization: {e}")

def exportProfile(profile_name):
    """Export a profile to JSON content for browser download"""
    profiles_dir = getProfilesDir()
    profile_path = os.path.join(profiles_dir, profile_name)

    if not os.path.exists(profile_path):
        return False, f"Profile '{profile_name}' not found"

    # Read profile data
    try:
        settings_file = os.path.join(profile_path, "settings.txt")
        fields_file = os.path.join(profile_path, "fields.txt")

        if not os.path.exists(settings_file) or not os.path.exists(fields_file):
            return False, f"Profile '{profile_name}' is missing required files"

        settings_data = readSettingsFile(settings_file)
        fields_data = loadFields() if profile_name == getCurrentProfile() else ast.literal_eval(open(fields_file).read())

        # Create export data structure
        export_data = {
            "profile_name": profile_name,
            "export_date": datetime.now().isoformat(),
            "version": "1.0",
            "settings": settings_data,
            "fields": fields_data
        }

        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"profile_{profile_name}_{timestamp}.json"

        # Return JSON content and filename
        json_content = json.dumps(export_data, indent=2, ensure_ascii=False)
        return True, json_content, filename

    except Exception as e:
        return False, f"Failed to export profile: {str(e)}"

def importProfile(import_path, new_profile_name=None):
    """Import a profile from a JSON file"""
    if not os.path.exists(import_path):
        return False, f"Import file '{import_path}' not found"

    try:
        # Read and validate import data
        with open(import_path, 'r', encoding='utf-8') as f:
            import_data = json.load(f)

        return _importProfileData(import_data, new_profile_name)
    except Exception as e:
        return False, f"Failed to import profile: {str(e)}"

def importProfileContent(json_content, new_profile_name=None):
    """Import a profile from JSON content string"""
    try:
        import_data = json.loads(json_content)
        return _importProfileData(import_data, new_profile_name)
    except json.JSONDecodeError:
        return False, "Invalid JSON content"
    except Exception as e:
        return False, f"Failed to import profile: {str(e)}"

def _importProfileData(import_data, new_profile_name=None):
    """Internal function to import profile data"""
    try:
        # Validate structure
        required_keys = ["profile_name", "settings", "fields"]
        for key in required_keys:
            if key not in import_data:
                return False, f"Invalid import file: missing '{key}' key"

        # Determine new profile name
        if new_profile_name is None:
            original_name = import_data["profile_name"]
            new_profile_name = original_name
            counter = 1
            while os.path.exists(os.path.join(getProfilesDir(), new_profile_name)):
                new_profile_name = f"{original_name}_imported_{counter}"
                counter += 1

        # Sanitize profile name
        new_profile_name = new_profile_name.strip().replace(' ', '_').lower()
        if not new_profile_name:
            return False, "Profile name cannot be empty"

        # Check if profile already exists
        new_profile_path = os.path.join(getProfilesDir(), new_profile_name)
        if os.path.exists(new_profile_path):
            return False, f"Profile '{new_profile_name}' already exists"

        # Create profile directory
        os.makedirs(new_profile_path)

        # Write settings file
        settings_file = os.path.join(new_profile_path, "settings.txt")
        saveDict(settings_file, import_data["settings"])

        # Write fields file
        fields_file = os.path.join(new_profile_path, "fields.txt")
        with open(fields_file, 'w') as f:
            f.write(str(import_data["fields"]))

        return True, f"Profile imported successfully as '{new_profile_name}'"

    except Exception as e:
        return False, f"Failed to import profile: {str(e)}"

#clear a file
def clearFile(filePath):
    open(filePath, 'w').close()